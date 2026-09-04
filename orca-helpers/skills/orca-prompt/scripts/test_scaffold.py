#!/usr/bin/env python3
"""The one check for the orca-prompt workstream.

Feeds a fixture `_config.json` / `_plan.md` through detection, rule
rendering, scaffolding, and validation, and asserts on the emitted files.
Fails if `detect_harnesses.py`, `render_rules.py`, `scaffold.py`, or
`validate.py` regresses.

Run: python3 test_scaffold.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from detect_harnesses import KNOWN_HARNESSES, detect_harnesses
from render_rules import render_rules
from scaffold import scaffold
from validate import validate

CONFIG = {
    "workstream": "fixture-ws",
    "targetBranch": "main",
    "harnesses": [
        {
            "name": "claude", "cli": None, "tier": "standard",
            "models": {"mainOrchestrator": {"model": "Claude Opus 5", "effort": "medium"}, "orchestrationWorker": "Claude Sonnet 5", "subagent": "Claude Sonnet 5", "subagentSimple": "Claude Haiku 4.5"},
        },
        {
            "name": "pi", "cli": None, "tier": "light",
            "models": {"mainOrchestrator": None, "orchestrationWorker": None, "subagent": {"model": "gpt-5.6-sol", "effort": "high"}, "subagentSimple": None},
        },
    ],
    "mainOrchestratorHarness": "claude",
    "reasoningLevel": "default",
    "maxConcurrency": 20,
    "workItems": [
        {"id": "01-skeleton", "size": "standard"},
        {"id": "02-detection", "size": "light"},
    ],
}

PLAN = """# Plan: fixture-ws

## Goal

Ship the fixture thing.

## Work Items

### 01-skeleton: Build the skeleton

Build the skeleton end to end.

**Skills**: skill-creator, writing-for-agents
**Closes**: #101

### 02-detection: Add detection

Add the detection step, which needs the skeleton.

**Skills**: writing-for-agents
**Closes**: #102
**Phase**: 2
"""


def test_pipeline():
    # detect_harnesses.py: stdlib probe, shape check only (installed CLIs vary by machine).
    report = detect_harnesses()
    assert {entry["name"] for entry in report} == set(KNOWN_HARNESSES)

    with tempfile.TemporaryDirectory() as tmp:
        workstream_dir = Path(tmp)
        (workstream_dir / "_config.json").write_text(json.dumps(CONFIG))
        (workstream_dir / "_plan.md").write_text(PLAN)

        # render_rules.py: both Agent Harness sections and the Global Rules block.
        block = render_rules(CONFIG)
        assert "### Claude Code" in block
        assert "### Pi" in block
        assert "### Global Rules" in block
        # A plain-string slot uses the Workstream reasoningLevel; a {model, effort}
        # slot overrides it for that slot alone.
        assert "**Subagent Model**: `Claude Sonnet 5` (medium reasoning)" in block
        assert "**Subagent Model**: `gpt-5.6-sol` (high reasoning)" in block
        # Only the Agent Harness running the Main Orchestrator gets that line;
        # Pi's slot is null, so its section has none.
        assert "**Main Orchestrator**: `Claude Opus 5` (medium reasoning)" in block
        assert "Main Orchestrator" not in block.split("### Pi")[1].split("### Global")[0]

        # scaffold.py: one prompt per work item, a run order, an orchestrator prompt.
        phases = scaffold(workstream_dir)
        assert phases == [1, 2]
        assert (workstream_dir / "01-skeleton.prompt.md").exists()
        assert (workstream_dir / "02-detection.prompt.md").exists()
        assert (workstream_dir / "_run-order.md").exists()
        assert (workstream_dir / "_orchestration.prompt.md").exists()

        skeleton = (workstream_dir / "01-skeleton.prompt.md").read_text()
        assert "## Orchestration Rules" in skeleton
        assert "### Claude Code" in skeleton

        # A worker reports its own outcome and never dispatches.
        assert "--outcome succeeded" in skeleton
        assert "never run `orca orchestration worker-start`" in skeleton

        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert "Phase 1" in orchestration and "Phase 2" in orchestration
        assert "orca skills get orchestration --full" in orchestration
        assert "ORCA_CLI_COMMAND" in orchestration
        assert "orca orchestration run-create --objective" in orchestration
        assert "--worktree new-child" in orchestration
        # One worker-start line per Agent Harness, each running repo setup.
        assert orchestration.count("--setup run --json") == len(CONFIG["harnesses"])
        # Claude takes launch options from its orchestrationWorker slot; Pi does not.
        assert "--agent claude --model Claude Sonnet 5 --setup run --json" in orchestration
        assert "--agent pi --setup run --json" in orchestration
        assert "`pi` takes no launch `--model`" in orchestration
        assert "--parent-worktree" not in orchestration and "--no-parent" not in orchestration
        assert "check --wait --types worker_done,escalation,question" in orchestration
        assert "**Worktree Nesting**" in block

        # validate.py: a fresh scaffold meets the Definition of Done...
        assert validate(workstream_dir) == []

        # ...and a regression (a work item with no prompt file) is caught.
        (workstream_dir / "02-detection.prompt.md").unlink()
        problems = validate(workstream_dir)
        assert "work item '02-detection' has no prompt file" in problems

        # ...and a harness missing a Model Slot key is a FAIL line, not a default.
        missing = json.loads(json.dumps(CONFIG))
        del missing["harnesses"][0]["models"]["mainOrchestrator"]
        (workstream_dir / "_config.json").write_text(json.dumps(missing))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and "missing the 'mainOrchestrator' Model Slot" in problems[0], problems

        # ...and a third Model Slot shape is rejected rather than crashing.
        bad = json.loads(json.dumps(CONFIG))
        bad["harnesses"][0]["models"]["subagent"] = {"model": "Claude Sonnet 5", "effort": "turbo"}
        (workstream_dir / "_config.json").write_text(json.dumps(bad))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and problems[0].startswith("_config.json is invalid:"), problems


if __name__ == "__main__":
    test_pipeline()
    print("ok")
