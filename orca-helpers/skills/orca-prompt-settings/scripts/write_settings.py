"""Validate and write the repo-level Prompt Settings file.

Prompt Settings are the defaults a Workstream would otherwise be asked for
every time — Agent Harnesses, Model Slots, target branch, concurrency,
reasoning level, Priority File. They live in `.orca/prompts/prompt-settings.json`
and hold nothing Workstream-specific: a `workstream`, `workItems` or `phases`
key is a FAIL, not an extra.

Both the `orca-prompt-settings` interview and `orca-prompt` go through this
script, so there is exactly one validator and one reader.

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
from render_rules import EFFORT_LEVELS, normalize_model_slot

DEFAULT_PATH = Path(".orca/prompts/prompt-settings.json")

REQUIRED_KEYS = {
    "harnesses",
    "mainOrchestratorHarness",
    "targetBranch",
    "maxConcurrency",
    "reasoningLevel",
    "priorityFile",
}
MODEL_SLOTS = {"mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple"}
TIERS = ("light", "standard")
REASONING_LEVELS = ("default",) + EFFORT_LEVELS


def _nonempty_string(value):
    return isinstance(value, str) and value.strip() != ""


def _harness_problems(index, harness):
    where = f"harnesses[{index}]"
    if not isinstance(harness, dict):
        return [f"{where} must be an object, got {harness!r}"]
    problems = []
    if not _nonempty_string(harness.get("name")):
        problems.append(f"{where}.name must be a non-empty string, got {harness.get('name')!r}")
    if not _nonempty_string(harness.get("cli")):
        problems.append(f"{where}.cli must be a non-empty string, got {harness.get('cli')!r}")
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

    if settings.get("reasoningLevel") not in REASONING_LEVELS:
        problems.append(f"reasoningLevel must be one of {'|'.join(REASONING_LEVELS)}, got {settings.get('reasoningLevel')!r}")

    if not _nonempty_string(settings.get("priorityFile")):
        problems.append(f"priorityFile must be a non-empty string, got {settings.get('priorityFile')!r}")

    return problems


def write_settings(settings, path=DEFAULT_PATH):
    """Validate `settings` and write it to `path`. Raises `ValueError` listing every problem."""
    problems = settings_problems(settings)
    if problems:
        raise ValueError(problems)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    return path


def read_settings(path=DEFAULT_PATH):
    """Return the stored settings, or `None` when the file does not exist."""
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _valid_settings():
    return {
        "harnesses": [
            {
                "name": "claude",
                "cli": "claude",
                "tier": "standard",
                "models": {
                    "mainOrchestrator": {"model": "claude-opus-5", "effort": "medium"},
                    "orchestrationWorker": {"model": "claude-opus-5", "effort": "medium"},
                    "subagent": "claude-opus-5",
                    "subagentSimple": None,
                },
            }
        ],
        "mainOrchestratorHarness": "claude",
        "targetBranch": "main",
        "maxConcurrency": 6,
        "reasoningLevel": "default",
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
    bad["harnesses"][0]["models"]["subagent"] = ["claude-opus-5"]
    del bad["harnesses"][0]["models"]["mainOrchestrator"]
    bad["mainOrchestratorHarness"] = "pi"
    bad["maxConcurrency"] = 0
    bad["reasoningLevel"] = "turbo"
    bad["priorityFile"] = ""
    assert len(settings_problems(bad)) == 7, settings_problems(bad)

    # A round trip through disk returns exactly what was written.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ".orca" / "prompts" / "prompt-settings.json"
        assert read_settings(path) is None
        write_settings(_valid_settings(), path)
        assert read_settings(path) == _valid_settings()
        try:
            write_settings(leaked, path)
            raise AssertionError("invalid settings were written")
        except ValueError:
            pass
        # The rejected write left the stored settings alone.
        assert read_settings(path) == _valid_settings()

    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        demo()
    elif args and args[0] == "--read":
        path = Path(args[1]) if len(args) > 1 else DEFAULT_PATH
        settings = read_settings(path)
        if settings is None:
            print(f"FAIL: no Prompt Settings at {path}")
            sys.exit(1)
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
