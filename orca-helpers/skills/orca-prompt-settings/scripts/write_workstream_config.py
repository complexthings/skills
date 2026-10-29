"""Validate and save a Workstream's overrides into its `_config.json`.

The Board's Workstream config modal saves through this script (ADR 0017), so
the overrides get the same checks `write_settings.py` gives Prompt Settings.
Only the keys in `KEYS` may change. Each `<key>` argument is dropped from the
config, so a section whose Override the user switched off follows the repo
default again. A Workstream whose `_status.json` has
`active: true` is running, and its config is never changed under it.

`--new` writes a fresh `_config.json` from orca-prompt's interview answers, the
step 7 writer: every key in `orca-prompt/references/config-schema.md` is
present, the Round 4 keys default as Round 4 does (`review: true`, `planGate:
false`, `evidenceCommand: null`, `budgetUsd: null`, `taskTime: "medium"`), and
the result passes the same `load_config` checks `scaffold.py` runs.

Usage:
    python3 write_workstream_config.py <workstream dir> [<key> ...]   # overrides JSON on stdin -> merged, keys dropped, written
    python3 write_workstream_config.py --new <workstream dir>         # answers JSON on stdin -> a new _config.json

Every problem prints as its own `FAIL:` line and the exit code is 1 when there is any.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt" / "scripts"))
from scaffold import load_config
from write_settings import _harness_problems, _nonempty_string, review_problems

KEYS = ("harnesses", "mainOrchestratorHarness", "maxConcurrency", "targetBranch", "review", "planGate",
        "evidenceCommand", "budgetUsd", "taskTime")

# Every `_config.json` key in schema order; the Round 4 keys carry their defaults.
SCHEMA_KEYS = ("workstream", "targetBranch", "harnesses", "mainOrchestratorHarness", "maxConcurrency", "integration",
               "tickets", "review", "planGate", "evidenceCommand", "budgetUsd", "taskTime", "workItems")
ROUND_4_DEFAULTS = {"review": True, "planGate": False, "evidenceCommand": None, "budgetUsd": None, "taskTime": "medium"}


def _merge(config, overrides, clear):
    return {**{k: v for k, v in config.items() if k not in clear}, **overrides}


def override_problems(overrides, config, clear=()):
    """Problems with `overrides` merged over `config` less the `clear` keys; empty means it saves."""
    if not isinstance(overrides, dict):
        return [f"overrides must be a JSON object, got {overrides!r}"]
    problems = []
    unknown = sorted((overrides.keys() | set(clear)) - set(KEYS))
    if unknown:
        problems.append(f"overrides has keys a Workstream cannot override: {unknown}")
    both = sorted(overrides.keys() & set(clear))
    if both:
        problems.append(f"keys are both overridden and cleared: {both}")
    merged = _merge(config, overrides, clear)
    names = []
    if "harnesses" in overrides:
        harnesses = overrides["harnesses"]
        if not isinstance(harnesses, list) or not harnesses:
            problems.append(f"harnesses must be a non-empty list, got {harnesses!r}")
        else:
            for index, harness in enumerate(harnesses):
                problems.extend(_harness_problems(index, harness))
    if isinstance(merged.get("harnesses"), list):
        names = [h["name"] for h in merged["harnesses"] if isinstance(h, dict) and _nonempty_string(h.get("name"))]
    main = merged.get("mainOrchestratorHarness")
    if main is not None and not _nonempty_string(main):
        problems.append(f"mainOrchestratorHarness must be a harness name or null, got {main!r}")
    elif isinstance(main, str) and names and main not in names:
        problems.append(f"mainOrchestratorHarness {main!r} is not one of the configured harnesses: {names}")
    if "targetBranch" in overrides and not _nonempty_string(overrides["targetBranch"]):
        problems.append(f"targetBranch must be a non-empty string, got {overrides['targetBranch']!r}")
    concurrency = overrides.get("maxConcurrency")
    if concurrency is not None and (not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1):
        problems.append(f"maxConcurrency must be a positive integer or null, got {concurrency!r}")
    problems.extend(review_problems(overrides))
    return problems


def _running_problem(directory, name):
    try:
        status = json.loads((Path(directory) / "_status.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(status, dict) and status.get("active") is True:
        return f"Workstream {name or Path(directory).name} is running: stop it before changing its config"
    return None


def _write(directory, config):
    fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=directory)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(config, indent=2) + "\n")
    os.replace(tmp, Path(directory) / "_config.json")
    return Path(directory) / "_config.json"


def new_config(directory, answers):
    """Write `<directory>/_config.json` from interview `answers`. Raises `ValueError` listing every problem."""
    directory = Path(directory)
    if not isinstance(answers, dict):
        raise ValueError([f"answers must be a JSON object, got {answers!r}"])
    problems = []
    unknown = sorted(answers.keys() - set(SCHEMA_KEYS))
    if unknown:
        problems.append(f"answers has keys _config.json does not hold: {unknown}")
    missing = sorted(set(SCHEMA_KEYS) - answers.keys() - ROUND_4_DEFAULTS.keys())
    if missing:
        problems.append(f"answers is missing required keys: {missing}")
    if "workstream" in answers and answers["workstream"] != directory.name:
        problems.append(f"workstream {answers['workstream']!r} must match the directory name {directory.name!r}")
    harnesses = answers.get("harnesses")
    if isinstance(harnesses, list):
        for index, harness in enumerate(harnesses):
            problems.extend(_harness_problems(index, harness))
    problems.extend(review_problems(answers))
    if problems:
        raise ValueError(problems)
    config = {key: answers.get(key, ROUND_4_DEFAULTS.get(key)) for key in SCHEMA_KEYS}
    # The checks scaffold.py runs, on a scratch copy so a bad config is never written.
    with tempfile.TemporaryDirectory() as scratch:
        _write(scratch, config)
        try:
            load_config(Path(scratch))
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise ValueError([f"invalid _config.json: {e}"])
    running = _running_problem(directory, config["workstream"])
    if running:
        raise ValueError([running])
    directory.mkdir(parents=True, exist_ok=True)
    return _write(directory, config)


def write_workstream_config(directory, overrides, clear=()):
    """Merge `overrides` into `<directory>/_config.json` and drop the `clear` keys. Raises `ValueError` listing every problem."""
    directory = Path(directory)
    path = directory / "_config.json"
    try:
        config = json.loads(path.read_text())
    except OSError:
        raise ValueError([f"no Workstream config at {path}"])
    except json.JSONDecodeError as e:
        raise ValueError([f"invalid Workstream config at {path}: not valid JSON: {e}"])
    if not isinstance(config, dict):
        raise ValueError([f"invalid Workstream config at {path}: not a JSON object"])
    running = _running_problem(directory, config.get("workstream"))
    if running:
        raise ValueError([running])
    problems = override_problems(overrides, config, clear)
    if problems:
        raise ValueError(problems)
    return _write(directory, _merge(config, overrides, clear))


if __name__ == "__main__":
    args = sys.argv[1:]
    new = args[:1] == ["--new"]
    if new and len(args) != 2:
        print("FAIL: usage: write_workstream_config.py --new <workstream dir> < answers.json")
        sys.exit(1)
    if args:
        try:
            overrides = json.load(sys.stdin)
        except (json.JSONDecodeError, RecursionError) as e:
            print(f"FAIL: stdin is not valid JSON: {e}")
            sys.exit(1)
        try:
            path = new_config(args[1], overrides) if new else write_workstream_config(args[0], overrides, args[1:])
        except ValueError as e:
            for problem in e.args[0]:
                print(f"FAIL: {problem}")
            sys.exit(1)
        print(f"ok: wrote {path}")
    else:
        print("FAIL: usage: write_workstream_config.py <workstream dir> [<key> ...] < overrides.json")
        sys.exit(1)
