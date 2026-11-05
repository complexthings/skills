"""Enforce the Definition of Done against a scaffolded workstream directory.

Reports what's missing; never modifies files. Checks:

- Every work item in `_config.json` has exactly one prompt file (in the
  workstream dir or `_completed/`, not both, not neither).
- Every `workItems[]` entry carries the integer `wave` and string `title`
  `scaffold.py` writes back.
- `_orchestration.prompt.md` names every Wave `_config.json` declares.
- Every generated prompt (work items and `_orchestration.prompt.md`) carries
  the `## Orchestration Rules` block.
- `_rules.md`, the Global Rules every Work Item prompt points at, exists.

Usage:
    python3 validate.py <workstream-dir>   # print problems, exit 1 if any
    python3 validate.py                    # run the self-check
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scaffold import load_config, scaffold

def _find_prompt(workstream_dir, item_id):
    """Return the paths where `<item_id>.prompt.md` exists: workstream dir, `_completed/`, both, or neither."""
    candidates = [
        workstream_dir / f"{item_id}.prompt.md",
        workstream_dir / "_completed" / f"{item_id}.prompt.md",
    ]
    return [c for c in candidates if c.exists()]


def validate(workstream_dir):
    """Return a list of problem strings; empty means the workstream meets the DoD."""
    workstream_dir = Path(workstream_dir)
    try:
        config = load_config(workstream_dir)
    except ValueError as e:
        # Malformed `_config.json` — bad Model Slot shape, missing keys — is a DoD failure,
        # not a crash. `load_config` routes slots through `render_rules.normalize_model_slot`.
        return [f"_config.json is invalid: {e}"]
    problems = []

    for work_item in config["workItems"]:
        found = _find_prompt(workstream_dir, work_item["id"])
        if not found:
            problems.append(f"work item {work_item['id']!r} has no prompt file")
        elif len(found) > 1:
            problems.append(f"work item {work_item['id']!r} has a prompt file in both the workstream dir and _completed/")

    for work_item in config["workItems"]:
        if not isinstance(work_item.get("wave"), int) or not isinstance(work_item.get("title"), str):
            problems.append(f"work item {work_item['id']!r} has no wave and title in _config.json; re-run scaffold.py")

    orch_path = workstream_dir / "_orchestration.prompt.md"
    orch_text = orch_path.read_text() if orch_path.exists() else None
    if orch_text is None:
        problems.append("_orchestration.prompt.md is missing")
    else:
        waves = sorted({wi["wave"] for wi in config["workItems"] if isinstance(wi.get("wave"), int)})
        for wave in waves:
            if f"Wave {wave}" not in orch_text:
                problems.append(f"_orchestration.prompt.md does not name Wave {wave}")
        if "## Orchestration Rules" not in orch_text:
            problems.append("_orchestration.prompt.md is missing the Orchestration Rules block")

    if not (workstream_dir / "_rules.md").exists():
        problems.append("_rules.md is missing; re-run scaffold.py")

    for work_item in config["workItems"]:
        found = _find_prompt(workstream_dir, work_item["id"])
        if found and "## Orchestration Rules" not in found[0].read_text():
            problems.append(f"{work_item['id']}.prompt.md is missing the Orchestration Rules block")

    return problems


def _self_test():
    config = {
        "workstream": "demo",
        "targetBranch": "main",
        "harnesses": [{
            "name": "claude", "cli": None, "tier": "standard",
            "models": {"mainOrchestrator": "Claude Opus 5.5", "orchestrationWorker": "Claude Sonnet 5.5", "subagent": "Claude Sonnet 5.5", "subagentSimple": "Claude Haiku 5.5"},
        }],
        "mainOrchestratorHarness": "claude",
        "maxConcurrency": 20,
        "integration": "pr-merge",
        "tickets": False,
        "workItems": [
            {"id": "01-first", "size": "standard"},
            {"id": "02-second", "size": "standard"},
        ],
    }
    plan = """# Plan: demo

## Goal

Ship the demo thing.

## Work Items

### 01-first: Do the first thing

Build the first thing end to end.

**Skills**: skill-creator
**Closes**: #1

### 02-second: Do the second thing

Build the second thing, which needs the first.

**Skills**: writing-for-agents
**Closes**: #2
**Wave**: 2
"""
    with tempfile.TemporaryDirectory() as tmp:
        workstream_dir = Path(tmp)
        (workstream_dir / "_config.json").write_text(json.dumps(config))
        (workstream_dir / "_plan.md").write_text(plan)
        scaffold(workstream_dir)

        assert validate(workstream_dir) == []

        # Missing prompt file.
        (workstream_dir / "02-second.prompt.md").unlink()
        problems = validate(workstream_dir)
        assert "work item '02-second' has no prompt file" in problems

        # Regenerate the missing prompt, then complete 01-first by moving it into _completed/.
        scaffold(workstream_dir)
        (workstream_dir / "_completed").mkdir()
        (workstream_dir / "01-first.prompt.md").rename(workstream_dir / "_completed" / "01-first.prompt.md")
        problems = validate(workstream_dir)
        assert problems == [], problems

        # A Wave missing from the orchestrator prompt is caught.
        orch_path = workstream_dir / "_orchestration.prompt.md"
        orch_path.write_text(orch_path.read_text().replace("Wave 2", "Wave two"))
        problems = validate(workstream_dir)
        assert "_orchestration.prompt.md does not name Wave 2" in problems

        # A prompt missing the Orchestration Rules block is caught.
        first_path = workstream_dir / "_completed" / "01-first.prompt.md"
        first_path.write_text(first_path.read_text().replace("## Orchestration Rules", "## Something Else"))
        problems = validate(workstream_dir)
        assert "01-first.prompt.md is missing the Orchestration Rules block" in problems

        # A missing _rules.md is caught.
        (workstream_dir / "_rules.md").unlink()
        assert "_rules.md is missing; re-run scaffold.py" in validate(workstream_dir)

        # A work item without the wave scaffold.py writes back is caught.
        written = json.loads((workstream_dir / "_config.json").read_text())
        del written["workItems"][0]["wave"]
        (workstream_dir / "_config.json").write_text(json.dumps(written))
        problems = validate(workstream_dir)
        assert "work item '01-first' has no wave and title in _config.json; re-run scaffold.py" in problems

        # A Model Slot that is neither a string nor a {model, effort} object is a FAIL line.
        bad = dict(config)
        bad["harnesses"] = [dict(config["harnesses"][0], models={"mainOrchestrator": None, "orchestrationWorker": ["a"], "subagent": "x", "subagentSimple": None})]
        (workstream_dir / "_config.json").write_text(json.dumps(bad))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and problems[0].startswith("_config.json is invalid:"), problems

    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        problems = validate(sys.argv[1])
        if problems:
            for p in problems:
                print(f"FAIL: {p}")
            sys.exit(1)
        print("ok: workstream meets the Definition of Done")
    else:
        _self_test()
