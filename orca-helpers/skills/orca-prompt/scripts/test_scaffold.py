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
import subprocess
from scaffold import DECISION_LOG_HEADER, launch_flags, render_resume, worker_start_command, repo_slug, scaffold, write_text_atomic
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

        # Each step reports progress with the exact command line, in any Agent Harness.
        set_status = Path(__file__).resolve().parent / "set_status.py"
        assert f'python3 {set_status} {workstream_dir.resolve()} 01-skeleton progress <done>/<total> "<note>"' in skeleton
        assert "never stops the work" in skeleton
        # No taskTime in _config.json: every prompt carries the default Task Time, Medium.
        assert "## Task Time\n\nMedium, under 10 minutes. This Work Item is meant to take that long." in skeleton
        # The Global Rules tell every Orchestration Worker it may use its subagent Model Slots.
        assert "- **Subagent Model Slots**: An Orchestration Worker may spawn subagents" in (workstream_dir / "_rules.md").read_text()

        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert "Wave 1" in orchestration and "Wave 2" in orchestration
        assert "## Task Time\n\nMedium, under 10 minutes. Each Work Item is meant to take that long" in orchestration
        # The generated prompts call the scripts instead of spelling out their steps.
        scripts = "${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts"
        assert f"python3 {scripts}/dispatch.py .orca/prompts/fixture-ws/\n" in orchestration
        assert "dispatch.py .orca/prompts/fixture-ws/ --resume" in orchestration
        assert f"python3 {scripts}/set_status.py .orca/prompts/fixture-ws/ run <runId>" in orchestration
        assert f"python3 {scripts}/integrate.py .orca/prompts/fixture-ws/ <id> --dispatch <dispatchId> --worktree <worker worktree>" in orchestration
        assert "merges the PR into `main` with `gh`" in orchestration
        assert f'python3 {scripts}/set_status.py .orca/prompts/fixture-ws/ log "<title>" "<body>" --commit <repo>@<sha>' in orchestration
        assert "kb.py update fixture-ws-lessons" in orchestration
        finish = Path(__file__).resolve().parent / "finish_work_item.py"
        assert f"python3 {finish} .orca/prompts/fixture-ws/ 01-skeleton --terminal <your handle>" in skeleton
        for gone in ("<taskId of", "Release deletes a", "**Merge the PR**", "TaskCreate", "fall back to plain `git`"):
            assert all(gone not in (workstream_dir / n).read_text() for n in ("01-skeleton.prompt.md", "02-detection.prompt.md", "_orchestration.prompt.md", "_rules.md")), gone
        # The compact guide is the default load; `--full` is only the fallback for a rejected `--reference`.
        assert "`orca skills get orchestration`, the compact guide" in orchestration
        assert "--reference references/<file>.md" in orchestration and "run `--full` once only when the CLI rejects `--reference`" in orchestration
        # Waiting: the Run, paging, a `none` nextAction, positive proof.
        assert orchestration.count("worker-list --run <runId> --include-remote --json") == 2
        assert "while `page.hasMore` is true, run it again with `--cursor <page.nextCursor>`" in orchestration
        assert "A `none` nextAction means read `liveness.reason` and keep waiting." in orchestration
        assert "only on positive proof" in orchestration and "`unverifiable` authorizes nothing." in orchestration
        # Release closes the worker's terminal; worktree rm is its own step.
        assert "deletes a `new-child` worktree" not in orchestration
        assert "closes only the worker's own agent terminal" in orchestration
        assert "ORCA_CLI_COMMAND" in orchestration
        assert "orca orchestration run-create --objective" in orchestration
        assert "--worktree new-child" in orchestration
        # dispatch.py prints the worker-start lines, so the prompt carries none.
        assert "--setup run --json" not in orchestration
        assert "`pi` takes no launch `--model`" in orchestration
        assert "--parent-worktree" not in orchestration and "--no-parent" not in orchestration
        assert "check --wait --types worker_done,escalation,question" in orchestration
        # An empty Decision Log, read before each Wave and appended through set_status.py log.
        assert (workstream_dir / "_decisions.md").read_text() == DECISION_LOG_HEADER
        assert "Read the Decision Log, `.orca/prompts/fixture-ws/_decisions.md`, before you start each Wave" in orchestration
        assert "set_status.py .orca/prompts/fixture-ws/ log" in orchestration
        # A Wave Retro after each Wave: one bullet per failure, or one line when nothing failed.
        assert "After each Wave settles, and before the next one starts, write its Wave Retro" in orchestration
        assert 'set_status.py .orca/prompts/fixture-ws/ log "Wave N retro" "<body>"' in orchestration
        assert "`- <what failed>: <the rule, test or doc that would have prevented it>`" in orchestration
        assert "the one line `No failures.`" in orchestration
        # A resume reads the four docs before any dispatch, stops on a missing one, and attests with Read:.
        resume = orchestration.split("## Resume")[1].split("## Dispatch")[0]
        for doc in ("_plan.md", "_orchestration.prompt.md", "_decisions.md", "_status.json"):
            assert f"`.orca/prompts/fixture-ws/{doc}`" in resume
        assert "stop the resume. Dispatch nothing" in resume
        assert "starts with one `Read:` line" in resume
        assert "`Read: _plan.md, _orchestration.prompt.md, _decisions.md, _status.json`" in resume
        # The resume eval embeds the section, since its sandbox cannot read the plugin directory.
        resume_eval = Path(__file__).parents[3] / "evals" / "orchestrator-resume-read-attestation" / "prompt.md"
        assert f"<!-- RESUME START -->\n{render_resume('auth-refactor')}<!-- RESUME END -->" in resume_eval.read_text()
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

        # Review off, or absent, renders today's output byte for byte and writes no reviewer brief.
        names = ("01-skeleton.prompt.md", "02-detection.prompt.md", "_orchestration.prompt.md")
        before = [(workstream_dir / n).read_text() for n in names]
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, integration="pr", review=False, planGate=False)))
        scaffold(workstream_dir)
        assert [(workstream_dir / n).read_text() for n in names] == before
        assert not (workstream_dir / "_review.prompt.md").exists()

        # Review on renders the review loop into the orchestration prompt only, and writes the brief.
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, integration="pr", review=True, planGate=False, evidenceCommand="pnpm test")))
        scaffold(workstream_dir)
        texts = [(workstream_dir / n).read_text() for n in names]
        assert texts[:2] == before[:2]
        orchestration = texts[2]
        assert "## Work Item Review" in orchestration and "## Work Item Review" not in before[2]
        assert orchestration.index("## Work Item Review") < orchestration.index("## Per completed worker")
        assert "1. **Wait for `VERDICT: SHIP`**" in orchestration
        assert "every Work Item's last review round signed `VERDICT: SHIP`" in orchestration
        # Each author gets a reviewer from the other Agent Harness, on its Orchestration Worker slot.
        assert "- Author `claude`: reviewer `pi`." in orchestration and "--agent pi --json" in orchestration
        assert "- Author `pi`: reviewer `claude`." in orchestration and "--agent claude --model Claude Sonnet 5.5 --json" in orchestration
        assert '--worktree "path:<author worktree>"' in orchestration
        # A NO-SHIP fix round starts a fresh worker on the author's Agent Harness, never on its settled terminal.
        assert ('--task-title "Fix · <id> · round <n>" --worktree "path:<author worktree>" --agent claude --model Claude Sonnet 5.5 --json'
                in orchestration)
        assert '--task-title "Fix · <id> · round <n>" --worktree "path:<author worktree>" --agent pi --json' in orchestration
        assert "--terminal <author handle>" not in orchestration and "`agent_unconfigured`" in orchestration
        assert f"set_status.py .orca/prompts/fixture-ws/ <id> review <n> <reviewer> --report .orca/prompts/fixture-ws/_reviews/<id>.round-<n>.md" in orchestration and "review: 3 NO-SHIP rounds" in orchestration
        assert ".orca/prompts/fixture-ws/_reviews/<id>.round-<n>.md" in orchestration
        # The evidence command runs once per reviewed commit, stored by SHA, and every review spec carries it.
        assert "2. **Record the evidence** once per reviewed commit:" in orchestration
        assert f"`python3 {scripts}/evidence.py .orca/prompts/fixture-ws/ <id> <author worktree>`" in orchestration
        assert "It runs `pnpm test` in the author worktree at its head SHA and writes `.orca/prompts/fixture-ws/_reviews/<id>.<sha>.evidence.md`" in orchestration
        assert "`Evidence Record, commit <sha>, exit <code>`" in orchestration and "the reviewer never runs tests" in orchestration
        brief = (workstream_dir / "_review.prompt.md").read_text()
        assert "VERDICT: SHIP" in brief and "Demonstrated Failure" in brief and "read-only" in brief
        # The review eval embeds the brief, since its sandbox cannot read the plugin directory.
        eval_prompt = Path(__file__).parents[3] / "evals" / "work-item-review-no-ship-then-ship" / "prompt.md"
        assert f"<!-- BRIEF START -->\n{brief}<!-- BRIEF END -->" in eval_prompt.read_text()
        assert validate(workstream_dir) == []
        written = json.loads((workstream_dir / "_config.json").read_text())
        assert (written["review"], written["planGate"], written["evidenceCommand"]) == (True, False, "pnpm test")
        assert "Plan Gate" not in before[2] and not (workstream_dir / "_plan-gate.prompt.md").exists()

        # Plan Gate on: a Plan Gate step before the Wave Tasks, and a reviewer prompt beside the plan.
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, integration="pr", planGate=True)))
        scaffold(workstream_dir)
        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert orchestration.index("### Plan Gate") < orchestration.index("### Wave Tasks") < orchestration.index("dispatch.py .orca/prompts/fixture-ws/\n")
        assert 'task-create --spec "Execute .orca/prompts/fixture-ws/_plan-gate.prompt.md"' in orchestration
        # Plan Gate starts in the current worktree, so the line carries no creation flags.
        assert "worker-start --task <taskId> --worktree current --agent pi --json" in orchestration
        assert "--worktree current --name" not in orchestration
        assert "`VERDICT: GO`: go on to Wave Tasks below and start Wave 1." in orchestration
        assert """gate-create --task <Plan Gate taskId>""" in orchestration and """'["Revise plan","Start anyway"]'""" in orchestration
        gate = (workstream_dir / "_plan-gate.prompt.md").read_text()
        assert ".orca/prompts/fixture-ws/_plan-review.md" in gate
        assert "`VERDICT: GO` or `VERDICT: NO-GO`" in gate and "_rules.md" in gate and "### Global Rules" not in gate
        assert "write `_plan-review.md` and no other file" in gate
        assert validate(workstream_dir) == []
        # ...and turning it off again removes the step and the reviewer prompt.
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, integration="pr", planGate=False)))
        scaffold(workstream_dir)
        assert (workstream_dir / "_orchestration.prompt.md").read_text() == before[2]
        assert not (workstream_dir / "_plan-gate.prompt.md").exists()

        # One Agent Harness reviews itself on another Model Slot, and the header says so.
        solo = dict(CONFIG, harnesses=CONFIG["harnesses"][:1], integration="pr", review=True)
        solo["harnesses"] = [dict(solo["harnesses"][0], models=dict(solo["harnesses"][0]["models"], subagent="Claude Opus 5.5"))]
        (workstream_dir / "_config.json").write_text(json.dumps(solo))
        scaffold(workstream_dir)
        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert "- Author `claude`: reviewer `claude` on its `subagent` Model Slot." in orchestration
        assert "same Agent Harness on another Model Slot" in orchestration
        assert "--agent claude --model Claude Opus 5.5 --json" in orchestration
        # No evidence command: the review header says so, and nothing runs.
        assert "2. **No evidence command is set**" in orchestration and "`Evidence Record: none: no evidence command is set`" in orchestration
        assert "Record the evidence" not in orchestration
        (workstream_dir / "_review.prompt.md").unlink()
        (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, review="on", evidenceCommand="")))
        problems = validate(workstream_dir)
        assert len(problems) == 1 and "review must be true or false" in problems[0], problems
        # taskTime is optional and reads as medium; present, it is one of the five Task Time ids.
        for bad in (None, "Medium", "max", 10):
            (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, taskTime=bad)))
            problems = validate(workstream_dir)
            assert problems == [f"_config.json is invalid: taskTime must be one of low|medium|high|xhigh|ultra, got {bad!r}"], problems
        for task_time, label in (("low", "Low, under 5 minutes"), ("xhigh", "Extra High, under 30 minutes"), ("ultra", "Ultra High, 30 minutes or more")):
            (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, taskTime=task_time)))
            scaffold(workstream_dir)
            for name in names:
                assert f"## Task Time\n\n{label}." in (workstream_dir / name).read_text(), (task_time, name)
            assert validate(workstream_dir) == []
        # budgetUsd is optional; present, it is a positive number or null.
        for budget in (None, 30, 0.5):
            (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, budgetUsd=budget)))
            assert not any("budgetUsd" in p for p in validate(workstream_dir)), budget
        for budget in ("30", 0, -1, True, [30], float("inf"), float("nan")):
            (workstream_dir / "_config.json").write_text(json.dumps(dict(CONFIG, budgetUsd=budget)))
            problems = validate(workstream_dir)
            assert problems == [f"_config.json is invalid: budgetUsd must be a positive number or null, got {budget!r}"], problems

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
        # It also keeps a Decision Log that already has entries.
        (workstream_dir / "_decisions.md").write_text(DECISION_LOG_HEADER + "\n### 2026-01-01 · Kept\n\nBody.\n")
        scaffold(workstream_dir)
        assert not (workstream_dir / "01-skeleton.prompt.md").exists()
        assert "### 2026-01-01 · Kept" in (workstream_dir / "_decisions.md").read_text()


def test_plan_gate_with_one_harness():
    harness = dict(CONFIG["harnesses"][0])
    config = dict(CONFIG, harnesses=[harness], integration="pr", planGate=True, review=True,
                  workItems=[{"id": "01-skeleton", "size": "standard"}])
    with tempfile.TemporaryDirectory() as tmp:
        workstream_dir = Path(tmp)
        (workstream_dir / "_config.json").write_text(json.dumps(config))
        (workstream_dir / "_plan.md").write_text("# Plan\n\n### 01-skeleton: Skeleton\n\nDo it.\n")
        scaffold(workstream_dir)
        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        # One Agent Harness: the reviewer takes the orchestrationWorker slot, never the Main Orchestrator's.
        assert "worker-start --task <taskId> --worktree current --agent claude --model Claude Sonnet 5.5 --json" in orchestration
        assert not [l for l in orchestration.splitlines() if "--worktree current" in l and "Claude Opus 5.5" in l]
        for line in orchestration.splitlines():
            if "--worktree current" in line or '--worktree "path:' in line:
                assert "--name" not in line and "--setup" not in line, line
        # The fix round carries the five-field Task-spec contract, push included.
        for field in ("Target:", "Change:", "Constraints:", "Ownership:", "Observable acceptance:"):
            assert field in orchestration, field
        assert "commit and push the fix to that same branch, so the drain check passes" in orchestration
        gate = (workstream_dir / "_plan-gate.prompt.md").read_text()
        work_item = (workstream_dir / "01-skeleton.prompt.md").read_text()
        assert "--report-path" in gate and "until `count` is 0" in gate
        assert "Keep every flag the preamble's worker_done line carries" in gate
        assert "--report-path .orca/prompts/fixture-ws/_plan-review.md" in gate
        # A worker's finish script drains the inbox and prints worker_done with --files-modified.
        assert "--report-path <path>" in work_item and "drains your inbox" in work_item
        rules = (workstream_dir / "_rules.md").read_text()
        assert "An Orchestration Worker asks with `orca orchestration ask`" in rules
        assert "Only the Main Orchestrator asks the user through its question tool" in rules
        assert "--report-path <report path>" in (workstream_dir / "_review.prompt.md").read_text()


def test_launch_flags_follow_worker_start_help():
    models = {"orchestrationWorker": {"model": "m", "effort": "high"}}
    for name in ("claude", "codex", "cursor", "agy", "muse"):
        assert launch_flags({"name": name, "models": models}) == " --model m --effort high", name
    assert launch_flags({"name": "omp", "models": models}) == " --model m"
    for name in ("opencode", "pi", "copilot"):
        assert launch_flags({"name": name, "models": models}) == "", name
    assert worker_start_command({"name": "omp", "models": models}) == (
        "orca orchestration worker-start --task <taskId> --worktree new-child --name <work item id> --agent omp --model m --setup run --json")


def test_check_names_missing_wave_keys():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "_config.json"
        cfg.write_text(json.dumps({"workItems": [{"id": "01-a", "wave": 1}, {"id": "02-b", "wave": 1, "title": "B"}]}))
        run = lambda: subprocess.run([sys.executable, str(Path(__file__).parent / "scaffold.py"), "--check", tmp], capture_output=True, text=True)
        out = run()
        assert out.returncode == 1, out
        assert out.stdout.splitlines() == ["FAIL: _config.json missing integration", "FAIL: _config.json missing tickets", "FAIL: workItems[0] 01-a missing title"], out.stdout
        cfg.write_text(json.dumps({"integration": "pr", "tickets": False, "workItems": [{"id": "01-a", "wave": 1, "title": "A"}]}))
        out = run()
        assert (out.returncode, out.stdout) == (0, ""), out


def test_validate_fails_on_empty_and_repeated_work_items():
    for items, word in (([], "empty"), ([{"id": "01-a", "size": "light"}, {"id": "01-a", "size": "light"}], "repeats")):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "_config.json").write_text(json.dumps({**CONFIG, "workItems": items}))
            problems = validate(tmp)
            assert len(problems) == 1 and word in problems[0], problems


def test_repo_slug_reads_every_origin_spelling():
    with tempfile.TemporaryDirectory() as tmp:
        assert repo_slug(tmp) is None
        subprocess.run(["git", "init", "-q", tmp], check=True)
        assert repo_slug(tmp) is None
        # origin: (slug with no host, slug with host="github.com")
        table = {
            "git@github.com:acme/widgets.git": ("acme/widgets", "acme/widgets"),
            "ssh://git@github.com/acme/widgets.git": ("acme/widgets", "acme/widgets"),
            "https://github.com/acme/widgets": ("acme/widgets", "acme/widgets"),
            "https://github.com/acme/widgets.git": ("acme/widgets", "acme/widgets"),
            "https://github.com/acme/widgets/": (None, "acme/widgets"),
            "https://mygithub.com/acme/widgets.git": ("acme/widgets", None),
            "git@notgithub.com:acme/widgets.git": ("acme/widgets", None),
            "https://github.com.evil.com/acme/widgets": ("acme/widgets", None),
            "https://gitlab.com/acme/widgets.git": ("acme/widgets", None),
            "git@bitbucket.org:acme/widgets.git": ("acme/widgets", None),
        }
        for url, (plain, github) in table.items():
            subprocess.run(["git", "-C", tmp, "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "-C", tmp, "remote", "add", "origin", url], check=True)
            assert (repo_slug(tmp), repo_slug(tmp, host="github.com")) == (plain, github), url


def test_write_text_atomic_leaves_no_temp_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.txt"
        write_text_atomic(path, "one\n", ".out-")
        write_text_atomic(path, "two\n", ".out-")
        assert path.read_text() == "two\n" and os.listdir(tmp) == ["out.txt"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
