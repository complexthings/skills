"""Validate and write the repo-level Prompt Settings file.

Prompt Settings are the defaults a Workstream would otherwise be asked for
every time — Agent Harnesses, Model Slots, target branch, concurrency,
Priority File. They live in `.orca/prompts/prompt-settings.json`
and hold nothing Workstream-specific: a `workstream`, `workItems` or `waves`
key is a FAIL, not an extra.

Both the `orca-prompt-settings` interview and `orca-prompt` go through this
script, so there is exactly one validator and one reader.

Older files may still hold `reasoningLevel` (ADR 0010). Both the reader and
the writer drop it, so the next save removes it. The reader also gives each
plain-string Model Slot the Priority File's suggested effort for that model.

Usage:
    python3 write_settings.py [path]          # settings JSON on stdin -> validated, written
    python3 write_settings.py --read [path]   # print the stored settings as JSON
    python3 write_settings.py --demo          # run the self-check

`path` defaults to `.orca/prompts/prompt-settings.json`. Every problem prints
as its own `FAIL:` line and the exit code is 1 when there is any.
"""
import json
import sys
from pathlib import Path

# One definition of a Model Slot for the whole pattern; `orca-prompt` owns it.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt" / "scripts"))
from render_rules import normalize_model_slot
from list_models import DATA_DIR, load_priority, normalise, slot_ranking

DEFAULT_PATH = Path(".orca/prompts/prompt-settings.json")

REQUIRED_KEYS = {
    "harnesses",
    "mainOrchestratorHarness",
    "targetBranch",
    "maxConcurrency",
    "priorityFile",
}
MODEL_SLOTS = {"mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple"}
TIERS = ("light", "standard")
# Retired by ADR 0010: ignored when read, dropped on the next save.
RETIRED_KEYS = ("reasoningLevel",)
# The provider used for effort lookup (not a fixed whitelist of Agent Harnesses).
HARNESS_PROVIDERS = {"claude": "anthropic", "copilot": "github-copilot", "codex": "openai-codex"}


def _nonempty_string(value):
    return isinstance(value, str) and value.strip() != ""


def _harness_problems(index, harness):
    where = f"harnesses[{index}]"
    if not isinstance(harness, dict):
        return [f"{where} must be an object, got {harness!r}"]
    problems = []
    if not _nonempty_string(harness.get("name")):
        problems.append(f"{where}.name must be a non-empty string, got {harness.get('name')!r}")
    if harness.get("cli") is not None and not _nonempty_string(harness.get("cli")):
        problems.append(f"{where}.cli must be null or a non-empty string, got {harness.get('cli')!r}")
    if harness.get("tier") not in TIERS:
        problems.append(f"{where}.tier must be one of {'|'.join(TIERS)}, got {harness.get('tier')!r}")

    models = harness.get("models")
    if not isinstance(models, dict):
        problems.append(f"{where}.models must be an object, got {models!r}")
        return problems
    missing = MODEL_SLOTS - models.keys()
    unknown = models.keys() - MODEL_SLOTS
    if missing:
        problems.append(f"{where}.models is missing model slots: {sorted(missing)}")
    if unknown:
        problems.append(f"{where}.models has unknown model slots: {sorted(unknown)}")
    for slot in sorted(models.keys() & MODEL_SLOTS):
        try:
            normalize_model_slot(models[slot])
        except ValueError as e:
            problems.append(f"{where}.models.{slot}: {e}")
    return problems


def settings_problems(settings):
    """Return a list of problem strings; empty means the settings object is valid."""
    if not isinstance(settings, dict):
        return [f"settings must be a JSON object, got {settings!r}"]

    problems = []
    missing = REQUIRED_KEYS - settings.keys()
    unknown = settings.keys() - REQUIRED_KEYS
    if missing:
        problems.append(f"settings is missing required keys: {sorted(missing)}")
    if unknown:
        # Workstream-specific keys belong in `_config.json`, never here.
        problems.append(f"settings has keys that do not belong in Prompt Settings: {sorted(unknown)}")

    harnesses = settings.get("harnesses")
    names = []
    if not isinstance(harnesses, list) or not harnesses:
        problems.append(f"harnesses must be a non-empty list, got {harnesses!r}")
    else:
        for index, harness in enumerate(harnesses):
            problems.extend(_harness_problems(index, harness))
            if isinstance(harness, dict) and _nonempty_string(harness.get("name")):
                names.append(harness["name"])

    main = settings.get("mainOrchestratorHarness")
    if main is not None and not _nonempty_string(main):
        problems.append(f"mainOrchestratorHarness must be a harness name or null, got {main!r}")
    elif isinstance(main, str) and names and main not in names:
        problems.append(f"mainOrchestratorHarness {main!r} is not one of the configured harnesses: {names}")

    if not _nonempty_string(settings.get("targetBranch")):
        problems.append(f"targetBranch must be a non-empty string, got {settings.get('targetBranch')!r}")

    concurrency = settings.get("maxConcurrency")
    if concurrency is not None and (not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1):
        problems.append(f"maxConcurrency must be a positive integer or null, got {concurrency!r}")

    if not _nonempty_string(settings.get("priorityFile")):
        problems.append(f"priorityFile must be a non-empty string, got {settings.get('priorityFile')!r}")

    return problems


def write_settings(settings, path=DEFAULT_PATH):
    """Validate `settings` and write it to `path`. Raises `ValueError` listing every problem."""
    settings = _drop_retired(settings)
    problems = settings_problems(settings)
    if problems:
        raise ValueError(problems)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    return path


def _drop_retired(settings):
    if not isinstance(settings, dict):
        return settings
    return {key: value for key, value in settings.items() if key not in RETIRED_KEYS}


def _priority_path(priority_file):
    """Resolve `priorityFile`: a path as written, else a file name in orca-prompt's `data/`."""
    for candidate in (Path(priority_file), Path(DATA_DIR) / priority_file):
        if candidate.is_file():
            return candidate
    return None


def suggested_effort(priority, harness_name, slot, model):
    """The Priority File's suggested effort for `model` in `slot`, or `None` where it ranks none.

    A discovered Agent Harness names the provider in the model id (`openai-codex/gpt-6-luna`);
    a fixed-set one maps to its provider. Every other provider is the fallback.
    """
    provider, _, bare = model.rpartition("/")
    providers = [provider or HARNESS_PROVIDERS.get(harness_name)] + list(priority.get("modelOrder", {}))
    for candidate in filter(None, providers):
        rank = slot_ranking(priority, candidate, slot).get(normalise(bare))
        if rank and rank[1]:
            return rank[1]
    return None


def fill_plain_slots(settings):
    """Turn each plain-string Model Slot into `{model, effort}` with the Priority File's suggested effort.

    A slot the Priority File does not rank, or a Priority File that cannot be found, stays a string.
    """
    path = _priority_path(settings.get("priorityFile") or "")
    if path is None:
        return settings
    priority = load_priority(path)
    for harness in settings.get("harnesses") or []:
        models = harness.get("models") or {}
        for slot, value in models.items():
            if isinstance(value, str):
                effort = suggested_effort(priority, harness.get("name"), slot, value)
                if effort:
                    models[slot] = {"model": value, "effort": effort}
    return settings


def read_settings(path=DEFAULT_PATH):
    """Return the stored settings, or `None` when the file does not exist.

    `reasoningLevel` is dropped and plain-string slots take the Priority File's suggested effort.
    """
    path = Path(path)
    if not path.exists():
        return None
    return fill_plain_slots(_drop_retired(json.loads(path.read_text())))


def _valid_settings():
    return {
        "harnesses": [
            {
                "name": "claude",
                "cli": "claude",
                "tier": "standard",
                "models": {
                    "mainOrchestrator": {"model": "claude-opus-5-5", "effort": "medium"},
                    "orchestrationWorker": {"model": "claude-opus-5-5", "effort": "medium"},
                    "subagent": "claude-opus-5-5",
                    "subagentSimple": None,
                },
            }
        ],
        "mainOrchestratorHarness": "claude",
        "targetBranch": "main",
        "maxConcurrency": 6,
        "priorityFile": "model-priority.json",
    }


def demo():
    import tempfile

    assert settings_problems(_valid_settings()) == []

    # A Workstream-specific key is rejected, not stored.
    leaked = dict(_valid_settings(), workItems=[])
    assert any("do not belong" in p for p in settings_problems(leaked))

    # Every malformed field reports its own FAIL line.
    bad = _valid_settings()
    bad["harnesses"][0]["tier"] = "heavy"
    bad["harnesses"][0]["models"]["subagent"] = ["claude-opus-5-5"]
    del bad["harnesses"][0]["models"]["mainOrchestrator"]
    bad["mainOrchestratorHarness"] = "pi"
    bad["maxConcurrency"] = 0
    bad["priorityFile"] = ""
    assert len(settings_problems(bad)) == 6, settings_problems(bad)

    # cli may be null (built-in name); an empty or non-string cli is rejected.
    nullcli = _valid_settings()
    nullcli["harnesses"][0]["cli"] = None
    assert settings_problems(nullcli) == []
    for v in ("", 3):
        nullcli["harnesses"][0]["cli"] = v
        assert len(settings_problems(nullcli)) == 1

    # A round trip through disk returns exactly what was written.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ".orca" / "prompts" / "prompt-settings.json"
        assert read_settings(path) is None
        write_settings(_valid_settings(), path)
        stored = _valid_settings()
        # The plain-string subagent slot reads back with the Seeded Set's suggested effort.
        stored["harnesses"][0]["models"]["subagent"] = {"model": "claude-opus-5-5", "effort": "low"}
        assert read_settings(path) == stored
        try:
            write_settings(leaked, path)
            raise AssertionError("invalid settings were written")
        except ValueError:
            pass
        # The rejected write left the stored settings alone.
        assert read_settings(path) == stored

        # Old settings holding `reasoningLevel` read with the key ignored, and the next save drops it.
        path.write_text(json.dumps(dict(_valid_settings(), reasoningLevel="high")))
        old = read_settings(path)
        assert "reasoningLevel" not in old and settings_problems(old) == []
        write_settings(dict(_valid_settings(), reasoningLevel="high"), path)
        assert "reasoningLevel" not in json.loads(path.read_text())

    # `--read` fails on a corrupt or incomplete file, with a message distinct from "no Prompt Settings".
    import subprocess
    with tempfile.TemporaryDirectory() as tmp:
        for text in ("{not json", json.dumps({"targetBranch": "main"}), json.dumps(dict(_valid_settings(), harnesses=["claude"])), "[]"):
            bad_file = Path(tmp) / "bad.json"
            bad_file.write_text(text)
            r = subprocess.run([sys.executable, __file__, "--read", str(bad_file)], capture_output=True, text=True)
            assert r.returncode == 1 and "FAIL: invalid Prompt Settings" in r.stdout, r.stdout

    # A model the Priority File does not rank stays a plain string.
    unranked = dict(_valid_settings())
    unranked["harnesses"] = [dict(unranked["harnesses"][0], models={"mainOrchestrator": None, "orchestrationWorker": "made-up-model", "subagent": None, "subagentSimple": None})]
    assert fill_plain_slots(unranked)["harnesses"][0]["models"]["orchestrationWorker"] == "made-up-model"

    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        demo()
    elif args and args[0] == "--read":
        path = Path(args[1]) if len(args) > 1 else DEFAULT_PATH
        if not path.exists():
            print(f"FAIL: no Prompt Settings at {path}")
            sys.exit(1)
        try:
            settings = _drop_retired(json.loads(path.read_text()))
        except json.JSONDecodeError as e:
            print(f"FAIL: invalid Prompt Settings at {path}: not valid JSON: {e}")
            sys.exit(1)
        problems = settings_problems(settings)  # validate before fill_plain_slots touches the raw JSON
        if problems:
            for problem in problems:
                print(f"FAIL: invalid Prompt Settings at {path}: {problem}")
            sys.exit(1)
        settings = fill_plain_slots(settings)
        json.dump(settings, sys.stdout, indent=2)
        print()
    else:
        path = Path(args[0]) if args else DEFAULT_PATH
        try:
            settings = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"FAIL: stdin is not valid JSON: {e}")
            sys.exit(1)
        try:
            write_settings(settings, path)
        except ValueError as e:
            for problem in e.args[0]:
                print(f"FAIL: {problem}")
            sys.exit(1)
        print(f"ok: wrote {path}")
