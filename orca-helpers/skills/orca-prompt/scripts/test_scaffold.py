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
from render_rules import render_harness_section, render_rules
from scaffold import scaffold
from validate import validate

CONFIG = {
    "workstream": "fixture-ws",
    "targetBranch": "main",
    "harnesses": [
        {
            "name": "claude", "cli": None, "tier": "standard",
            "models": {"mainOrchestrator": {"model": "Claude Opus 5.5", "effort": "medium"}, "orchestrationWorker": "Claude Sonnet 5.5", "subagent": "Claude Sonnet 5.5", "subagentSimple": "Claude Haiku 5.5"},
        },
        {
            "name": "pi", "cli": None, "tier": "light",
            "models": {"mainOrchestrator": None, "orchestrationWorker": None, "subagent": {"model": "gpt-6.1-sol", "effort": "high"}, "subagentSimple": None},
        },
    ],
    "mainOrchestratorHarness": "claude",
    "maxConcurrency": 20,
    "integration": "pr-merge",
    "tickets": False,
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
        # A plain-string slot names no effort; a {model, effort} slot names its own.
        assert "**Subagent Model**: `Claude Sonnet 5.5`\n" in block
        assert "**Subagent Model**: `gpt-6.1-sol` (high reasoning)" in block
        assert "**Subagent Model**: Inherit\n" in render_harness_section({"name": "claude", "models": {"subagent": None}}, 4)
        # Only the Agent Harness running the Main Orchestrator gets that line;
        # Pi's slot is null, so its section has none.
        assert "**Main Orchestrator**: `Claude Opus 5.5` (medium reasoning)" in block
        assert "Main Orchestrator" not in block.split("### Pi")[1].split("### Global")[0]

        # scaffold.py: one prompt per work item and an orchestrator prompt. `**Phase**`
        # still reads as an alias of `**Wave**`, and _run-order.md is no longer written.
        waves = scaffold(workstream_dir)
        assert waves == [1, 2]
        assert (workstream_dir / "01-skeleton.prompt.md").exists()
        assert (workstream_dir / "02-detection.prompt.md").exists()
        assert not (workstream_dir / "_run-order.md").exists()
        assert (workstream_dir / "_orchestration.prompt.md").exists()
        written = json.loads((workstream_dir / "_config.json").read_text())
        assert [(wi["wave"], wi["title"]) for wi in written["workItems"]] == [(1, "Build the skeleton"), (2, "Add detection")]
        assert "## Orchestration Rules" in (workstream_dir / "_plan.md").read_text()

        skeleton = (workstream_dir / "01-skeleton.prompt.md").read_text()
        assert "## Orchestration Rules" in skeleton
        assert "### Claude Code" in skeleton

        # A worker reports its own outcome and never dispatches.
        assert "--outcome succeeded" in skeleton
        assert "never run `orca orchestration worker-start`" in skeleton

        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert "Wave 1" in orchestration and "Wave 2" in orchestration
        assert """--deps '["<taskId of 01-skeleton>"]'""" in orchestration
        assert "Merge the PR" in orchestration
        assert "orca skills get orchestration --full" in orchestration
        assert "ORCA_CLI_COMMAND" in orchestration
        assert "orca orchestration run-create --objective" in orchestration
        assert "--worktree new-child" in orchestration
        # One worker-start line per Agent Harness, each running repo setup.
        assert orchestration.count("--setup run --json") == len(CONFIG["harnesses"])
        # Claude takes launch options from its orchestrationWorker slot; Pi does not.
        assert "--agent claude --model Claude Sonnet 5.5 --setup run --json" in orchestration
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

        # A `commit` Workstream's prompts name no PR; a `pr` one opens PRs but merges nothing.
        for integration in ("commit", "branch", "pr"):
            (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, integration=integration)))
            scaffold(workstream_dir)
            texts = [(workstream_dir / n).read_text() for n in ("01-skeleton.prompt.md", "02-detection.prompt.md", "_orchestration.prompt.md")]
            assert ("PR" in "".join(texts)) == (integration == "pr"), integration
            assert "Merge the PR" not in texts[2] and "Merging the PR" not in texts[0], integration

        # An old `_config.json` still holding `reasoningLevel` scaffolds with the key ignored.
        (workstream_dir / "02-detection.prompt.md").unlink()
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, reasoningLevel="high")))
        scaffold(workstream_dir)
        assert validate(workstream_dir) == []
        assert "**Subagent Model**: `Claude Sonnet 5.5`\n" in (workstream_dir / "01-skeleton.prompt.md").read_text()

        # ...and a harness missing a Model Slot key is a FAIL line, not a default.
        missing = json.loads(json.dumps(CONFIG))
        del missing["harnesses"][0]["models"]["mainOrchestrator"]
        (workstream_dir / "_config.json").write_text(json.dumps(missing))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and "missing the 'mainOrchestrator' Model Slot" in problems[0], problems

        # ...and a third Model Slot shape is rejected rather than crashing.
        bad = json.loads(json.dumps(CONFIG))
        bad["harnesses"][0]["models"]["subagent"] = {"model": "Claude Sonnet 5.5", "effort": "turbo"}
        (workstream_dir / "_config.json").write_text(json.dumps(bad))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and problems[0].startswith("_config.json is invalid:"), problems

        # ...as is a harness tier outside TIERS.
        bad = json.loads(json.dumps(CONFIG))
        bad["harnesses"][0]["tier"] = "heavy"
        (workstream_dir / "_config.json").write_text(json.dumps(bad))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and "tier must be one of" in problems[0], problems

        # A branch worker pushes with -u, and Waves 1 and 3 mean Wave 3 is blocked by Wave 1.
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, integration="branch")))
        (workstream_dir / "_plan.md").write_text((workstream_dir / "_plan.md").read_text().replace("**Phase**: 2", "**Phase**: 3"))
        scaffold(workstream_dir)
        detection = (workstream_dir / "02-detection.prompt.md").read_text()
        assert "git push -u origin HEAD" in detection and "Blocked by Wave 1" in detection, detection
        # A branch Workstream stops on `worker_done`s, not on prompts that never merge back.
        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert "every Work Item is complete, with a `worker_done`" in orchestration and "prompt files are in `_completed/`" not in orchestration

        # A re-scaffold leaves a finished Work Item's prompt in _completed/ alone.
        (workstream_dir / "_completed").mkdir()
        (workstream_dir / "01-skeleton.prompt.md").rename(workstream_dir / "_completed" / "01-skeleton.prompt.md")
        scaffold(workstream_dir)
        assert not (workstream_dir / "01-skeleton.prompt.md").exists()


if __name__ == "__main__":
    test_pipeline()
    print("ok")
