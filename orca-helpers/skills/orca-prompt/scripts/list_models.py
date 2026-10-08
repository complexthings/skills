#!/usr/bin/env python3
"""List the models one Agent Harness can actually run, pre-filtered and grouped by provider.

Usage:
    python3 list_models.py [--recommended] <pi|prime-agent|opencode|agy> [mainOrchestrator|orchestrationWorker|subagent|subagentSimple]

Prints compact JSON to stdout so the interviewing agent spends few tokens
reading it — provider keys, and under each one model entry per base model:

    {"harness": "agy",
     "providers": {"gemini": [{"model": "gemini-3.7-flash",
                               "efforts": ["low", "medium", "high"]}]}}

Pass a Model Slot as the second argument to order each provider's models by
the chosen Priority File instead of alphabetically: ranked models first in
file order, each carrying the `suggestedEffort` that file recommends, then
every model the file does not rank, alphabetically, below all of them. A model
missing from the file is never dropped — the file is a preference, not a
whitelist.

Two Priority Files ship. The Seeded Set, `data/model-priority.json`, is the
default: it ranks on capability per dollar from DeepSWE v1.1 and Artificial
Analysis figures. `--recommended` reads the Opinionated Set,
`data/recommended-priority.json`, ranked by hand from day-to-day use instead of
benchmark output. Both have the same shape, so the flag changes which file is
read and nothing else.

`efforts` is empty for every Agent Harness but `agy`, whose model ids bake the
Effort Level in (`gemini-3.7-flash-high`). The suffix is stripped and reported
as the efforts the base model accepts, so Round 3 writes the pick as a Model
Slot `{"model": "gemini-3.7-flash", "effort": "high"}` and `agy --effort` gets
it — and the user never sees two entries differing only by effort suffix.

Exits non-zero with a one-line `error:` on stderr when the CLI is missing or
its output does not parse.
"""
import json
import os
import re
import shutil
import subprocess
import sys

# Agent Harness -> the argv that lists its models.
COMMANDS = {
    "pi": ["pi", "--list-models"],
    "prime-agent": ["prime-agent", "model", "list"],
    "opencode": ["opencode", "models"],
    "agy": ["agy", "models"],
}

# Rankings live in data, not in prose: the model landscape changes monthly.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PRIORITY_PATH = os.path.join(DATA_DIR, "model-priority.json")
RECOMMENDED_PATH = os.path.join(DATA_DIR, "recommended-priority.json")
SLOTS = ("mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple")
# The Priority Files rank no models for the Main Orchestrator of their own: the
# two jobs want similar models, so the slot reads `orchestrationWorker`.
SLOT_RANKINGS = {"mainOrchestrator": "orchestrationWorker"}

EFFORT_SUFFIXES = ("low", "medium", "high", "xhigh")
# Dated snapshot alias of an undated model, e.g. claude-haiku-4-5-20251001.
DATED_ALIAS = re.compile(r"^(?P<base>.+)-20\d{6}$")


def parse_columns(text):
    """`provider  model  context  max-out  thinking  images` — pi and prime-agent."""
    pairs = []
    for line in text.splitlines():
        fields = line.split()
        # Exactly the six columns — anything else is a header or a stray
        # warning line (prime-agent prints its table on stderr alongside them).
        if len(fields) != 6 or fields[0] == "provider":
            continue
        pairs.append((fields[0], fields[1]))
    return pairs


def parse_slugs(text):
    """One `provider/model` slug per line — opencode."""
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if "/" not in line:
            continue
        provider, model = line.split("/", 1)
        pairs.append((provider, model))
    return pairs


def parse_tabbed(text):
    """`id<TAB>Label` — agy. Provider is the id's vendor prefix."""
    pairs = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        model = line.split("\t", 1)[0].strip()
        if model:
            pairs.append((model.split("-", 1)[0], model))
    return pairs


PARSERS = {
    "pi": parse_columns,
    "prime-agent": parse_columns,
    "opencode": parse_slugs,
    "agy": parse_tabbed,
}


def split_effort(model):
    """Return `(base_model, effort_or_none)` for an effort-suffixed model id."""
    for effort in EFFORT_SUFFIXES:
        suffix = "-" + effort
        if model.endswith(suffix) and len(model) > len(suffix):
            return model[: -len(suffix)], effort
    return model, None


def group(pairs, strip_efforts):
    """Fold `(provider, model)` pairs into the provider -> entries report.

    Drops dated snapshot aliases whose undated base is already listed, and —
    when `strip_efforts` — collapses effort-suffixed ids onto their base model.
    """
    providers = {}
    for provider, model in pairs:
        effort = None
        if strip_efforts:
            model, effort = split_effort(model)
        entries = providers.setdefault(provider, {})
        efforts = entries.setdefault(model, [])
        if effort is not None and effort not in efforts:
            efforts.append(effort)

    report = {}
    for provider in sorted(providers):
        entries = providers[provider]
        report[provider] = [
            {"model": model, "efforts": sorted(entries[model], key=EFFORT_SUFFIXES.index)}
            for model in sorted(entries)
            # A dated alias adds nothing the undated id does not already say.
            if not (DATED_ALIAS.match(model) and DATED_ALIAS.match(model).group("base") in entries)
        ]
    return report


def load_priority(path=PRIORITY_PATH):
    """Read a Priority File — the single source of both orderings."""
    with open(path) as handle:
        return json.load(handle)


def normalise(model):
    """Fold the spelling differences between Agent Harnesses' model ids.

    Pi reports `claude-haiku-4.5` under `github-copilot` and `claude-haiku-4-5`
    under `anthropic` — the same model, so the priority file matches either.
    """
    return model.replace(".", "-")


def slot_ranking(priority, provider, slot):
    """`{model: (rank, suggested_effort)}` for one provider and Model Slot.

    The file lists the same model more than once at different efforts (Luna at
    `max` then `xhigh`); the first entry is the recommendation, so it wins.
    """
    ranking = {}
    slot = SLOT_RANKINGS.get(slot, slot)
    for rank, entry in enumerate(priority.get("modelOrder", {}).get(provider, {}).get(slot) or []):
        ranking.setdefault(normalise(entry["model"]), (rank, entry.get("effort")))
    return ranking


def prioritise(report, slot, priority):
    """Reorder each provider's entries by `slot`'s ranking, unranked models last."""
    for provider, entries in report.items():
        ranking = slot_ranking(priority, provider, slot)
        for entry in entries:
            rank, effort = ranking.get(normalise(entry["model"]), (None, None))
            if effort is not None:
                entry["suggestedEffort"] = effort
        # Unranked models keep their alphabetical order, below every ranked one.
        # The file lists a model twice at different efforts, so ranks are sparse:
        # the sentinel has to clear the highest rank, not the entry count.
        last = 1 + max((rank for rank, _ in ranking.values()), default=-1)
        entries.sort(key=lambda e: (ranking.get(normalise(e["model"]), (last,))[0], e["model"]))
    return report


def list_models(harness, text, slot=None, priority=None):
    """Return the `{harness, providers}` report for one Agent Harness's CLI output."""
    if harness not in PARSERS:
        raise ValueError("unknown Agent Harness: %s" % harness)
    if slot is not None and slot not in SLOTS:
        raise ValueError("unknown Model Slot: %s" % slot)
    pairs = PARSERS[harness](text)
    if not pairs:
        raise ValueError("no models parsed from `%s` output" % " ".join(COMMANDS[harness]))
    providers = group(pairs, strip_efforts=harness == "agy")
    if slot is not None:
        providers = prioritise(providers, slot, priority if priority is not None else load_priority())
    return {"harness": harness, "providers": providers}


def main(argv):
    argv = list(argv)
    recommended = "--recommended" in argv
    if recommended:
        argv.remove("--recommended")
    if not 2 <= len(argv) <= 3 or argv[1] not in COMMANDS or (len(argv) == 3 and argv[2] not in SLOTS):
        sys.stderr.write("usage: list_models.py [--recommended] <%s> [%s]\n" % ("|".join(COMMANDS), "|".join(SLOTS)))
        return 2
    harness = argv[1]
    slot = argv[2] if len(argv) == 3 else None
    command = COMMANDS[harness]
    if shutil.which(command[0]) is None:
        sys.stderr.write("error: %s is not on PATH\n" % command[0])
        return 1
    # prime-agent prints its table on stderr; fold both streams into one.
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        priority = load_priority(RECOMMENDED_PATH) if recommended and slot else None
        report = list_models(harness, result.stdout, slot, priority)
    except ValueError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    json.dump(report, sys.stdout, separators=(",", ":"), sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
