"""Scaffold a workstream's prompt set from `_config.json` and `_plan.md`.

Reads `<workstream-dir>/_config.json` (schema documented in
`orca/orca-prompt/SKILL.md`) and `<workstream-dir>/_plan.md`, and writes into
that same directory: one `<id>.prompt.md` per work item, `_run-order.md`, and
`_orchestration.prompt.md`.

`_plan.md` must carry a `## Work Items` section with one subsection per work
item, matched by id against `_config.json`'s `workItems[].id`:

    ### <id>: <title>

    <prose — the specific work>

    **Skills**: skill-one, skill-two
    **Closes**: #12
    **Phase**: 1

`**Skills**`, `**Closes**`, and `**Phase**` are each optional (empty,
unlinked, and phase 1, respectively, when omitted). An optional `## Goal`
section supplies `_run-order.md`'s goal line.

Usage:
    python3 scaffold.py <workstream-dir>   # scaffold that workstream
    python3 scaffold.py                    # run the self-check
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_rules import harness_display_name, model_slot_problems, render_rules

REQUIRED_CONFIG_KEYS = {
    "workstream", "targetBranch", "harnesses", "mainOrchestratorHarness",
    "reasoningLevel", "maxConcurrency", "workItems",
}

WORK_ITEM_RE = re.compile(r"^### (?P<id>[\w.-]+): (?P<title>.+)$", re.MULTILINE)
GOAL_RE = re.compile(r"^## Goal\n\n(.+?)(?=\n##|\Z)", re.DOTALL | re.MULTILINE)


def load_config(workstream_dir):
    config = json.loads((workstream_dir / "_config.json").read_text())
    missing = REQUIRED_CONFIG_KEYS - config.keys()
    if missing:
        raise ValueError(f"_config.json missing required keys: {sorted(missing)}")
    slot_problems = model_slot_problems(config)
    if slot_problems:
        raise ValueError("; ".join(slot_problems))
    return config


def parse_plan(workstream_dir):
    text = (workstream_dir / "_plan.md").read_text()
    goal_match = GOAL_RE.search(text)
    goal = goal_match.group(1).strip() if goal_match else None

    matches = list(WORK_ITEM_RE.finditer(text))
    items = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        skills_m = re.search(r"^\*\*Skills\*\*:\s*(.+)$", body, re.MULTILINE)
        closes_m = re.search(r"^\*\*Closes\*\*:\s*(.+)$", body, re.MULTILINE)
        phase_m = re.search(r"^\*\*Phase\*\*:\s*(\d+)$", body, re.MULTILINE)
        work = re.sub(r"^\*\*(Skills|Closes|Phase)\*\*:.*$\n?", "", body, flags=re.MULTILINE).strip()
        items[m.group("id")] = {
            "title": m.group("title").strip(),
            "work": work,
            "skills": [s.strip() for s in skills_m.group(1).split(",")] if skills_m else [],
            "closes": [c.strip() for c in closes_m.group(1).split(",")] if closes_m else [],
            "phase": int(phase_m.group(1)) if phase_m else 1,
        }
    return goal, items


def repo_slug():
    """Best-effort `owner/repo` from `git remote get-url origin`; None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
    except Exception:
        return None
    m = re.search(r"[:/]([^/]+/[^/]+?)(\.git)?$", result.stdout.strip())
    return m.group(1) if m else None


def issue_link(ref, slug):
    ref = ref.strip()
    if ref.startswith("http"):
        num = ref.rstrip("/").rsplit("/", 1)[-1]
        return f"[#{num}]({ref})"
    num = ref.lstrip("#")
    label = f"#{num}"
    if slug and num.isdigit():
        return f"[{label}](https://github.com/{slug}/issues/{num})"
    return label


def route_harness(size, harnesses):
    for h in harnesses:
        if h["tier"] == size:
            return h
    raise ValueError(f"no Agent Harness in _config.json has tier {size!r}")


def item_number(item_id):
    m = re.match(r"0*(\d+)", item_id)
    return int(m.group(1)) if m else "?"


def render_work_item_prompt(config, work_item, plan_item, rules_block, slug):
    harness = route_harness(work_item["size"], config["harnesses"])
    closes = ", ".join(issue_link(c, slug) for c in plan_item["closes"]) or "no linked issue"
    blocked = "No blockers" if plan_item["phase"] <= 1 else f"Blocked by Phase {plan_item['phase'] - 1}"
    skills = ", ".join(f"`{s}`" for s in plan_item["skills"]) or "none"

    return f"""# Work Item {item_number(work_item['id'])}: `{work_item['id']}`: {plan_item['title']}

Closes {closes}. Phase {plan_item['phase']}. {blocked}.

## Branch

Branch off `{config['targetBranch']}`. All work happens in your own worktree.

## The work

{plan_item['work']}

Skills required: {skills}.

## Orchestration Rules

Use the {harness_display_name(harness)} rules for this prompt, plus the Global Rules.

{rules_block}

## Completion

1. Move this prompt file into `.orca/prompts/{config['workstream']}/_completed`.
2. Open a PR into `{config['targetBranch']}`, linking the issue it closes in the description.
3. Report `worker_done` to the Main Orchestrator with the PR link. See the `orchestration` skill.
"""


def render_run_order(config, goal, plan_items, items_by_phase):
    goal_text = goal or f"Ship the `{config['workstream']}` workstream."
    lines = [
        f"# Run Order: `{config['workstream']}`", "",
        "## Goal", "", goal_text, "",
        f"Target branch: `{config['targetBranch']}`.", "",
        "## Phases", "",
    ]
    for phase in sorted(items_by_phase):
        lines += [f"### Phase {phase}", "", "| Prompt | Issue | Status |", "| --- | --- | --- |"]
        for work_item in items_by_phase[phase]:
            plan_item = plan_items[work_item["id"]]
            issue = plan_item["closes"][0] if plan_item["closes"] else "—"
            lines.append(f"| `{work_item['id']}.prompt.md` | {issue} | Not started |")
        lines.append("")
    lines += [
        "## Status vocabulary", "",
        "`Not started` → `Dispatched` → `PR open` → `Merged`.", "",
        "Completed prompt files move into `_completed/`.",
    ]
    return "\n".join(lines) + "\n"


def render_orchestration_prompt(config, rules_block, work_item_count, phases):
    main_harness = next(
        (h for h in config["harnesses"] if h["name"] == config.get("mainOrchestratorHarness")), None,
    )
    main_display = harness_display_name(main_harness) if main_harness else (config.get("mainOrchestratorHarness") or "the configured Agent Harness")
    target = config["targetBranch"]
    ws = config["workstream"]
    phase_list = ", ".join(f"Phase {p}" for p in phases)

    return f"""# Main Orchestrator: `{ws}`

You are the Main Orchestrator for the `{ws}` workstream. You dispatch work item prompts to Orchestration Workers, merge what they produce, and own the worktree lifecycle. The work itself lives in the prompt files; this file carries orchestration only.

Before dispatching anything, load Orca's bundled orchestration skill — `orca skills get orchestration --full` — and dispatch by what it says, not by a copy of it kept in this repo. Use `orca skills get orca-cli` for worktree operations. Target branch: `{target}`.

## Dispatch

Read `_run-order.md`. Work through it in order, one phase at a time: {phase_list}. For each prompt file in a phase, pick the Agent Harness and agent persona, then dispatch it to an Orchestration Worker in a new session. Create the worker's worktree as a child of yours — `orca orchestration worker-start --task <taskId> --worktree new-child --agent <type>`, or `--parent-worktree active` if you create the worktree yourself — so Orca records the nesting. Use `--worktree new-top-level` (or `--no-parent`) only for work genuinely independent of this workstream. Dispatch every prompt in a phase at once; move to the next phase only when every PR from the current one has merged.

After dispatching, wait for each worker's `worker_done` report and its PR link.

## Per completed worker

Run these in order.

1. **Release the worker** at report time: `orca orchestration worker-release --dispatch <dispatchId> --json`. The `dispatchId` looks like `ctx_62066a4ef024`; it is in the `worker_done` payload, or from `orca orchestration task-list --json`. Read a released worker's output with `orca orchestration worker-read`; do not keep its terminal open just to re-read it.
2. **Merge the PR** into `{target}`. Use `gh`; fall back to plain `git` if `gh` fails.
3. **Verify the worktree is drained.** Both must print nothing:
   ```
   cd <worktree> && git status --porcelain
   cd <worktree> && git log origin/{target}..HEAD
   ```
4. **Remove the worktree**: `orca worktree rm --worktree "/abs/path/to/worktree"`.
5. **Close** any GitHub Issues the merge left open.
6. **Update `_run-order.md`** locally, moving the prompt's status along. Push it to `{target}` once all work is done.
7. **Check the PR** with `gh` for description comments and review comments. If any need action: run `grill-with-docs` to align on the fix, use `to-spec` / `to-tickets` for new tickets, update the work item prompts, `_run-order.md`, decisions and ADRs with `writing-for-agents`, and `_orchestration.prompt.md`. Commit and push that immediately.

## Timing gotchas worth the ink

- Release when the worker reports; remove the worktree only after the merge. At report time the PR is still open and the worktree must stay.
- `worker-release` returning `state: retained, reason: user_takeover` just means Orca kept a terminal you opened yourself. Still run `orca worktree rm`.
- A dirty tree means step 3's checks failed for a reason. Fix the cause instead of reaching for `--force`.

## Done

All {work_item_count} PRs merged into `{target}`, all {work_item_count} issues closed, all {work_item_count} prompt files in `_completed/`, and `_run-order.md` showing every row `Merged` and pushed.

## Orchestration Rules

Use the {main_display} rules for this prompt, plus the Global Rules.

{rules_block}
"""


def scaffold(workstream_dir):
    workstream_dir = Path(workstream_dir)
    config = load_config(workstream_dir)
    goal, plan_items = parse_plan(workstream_dir)

    missing = [wi["id"] for wi in config["workItems"] if wi["id"] not in plan_items]
    if missing:
        raise ValueError(f"_plan.md's Work Items section has no entry for: {missing}")

    slug = repo_slug()
    rules_block = render_rules(config)

    items_by_phase = {}
    for work_item in config["workItems"]:
        plan_item = plan_items[work_item["id"]]
        items_by_phase.setdefault(plan_item["phase"], []).append(work_item)
        prompt = render_work_item_prompt(config, work_item, plan_item, rules_block, slug)
        (workstream_dir / f"{work_item['id']}.prompt.md").write_text(prompt)

    (workstream_dir / "_run-order.md").write_text(
        render_run_order(config, goal, plan_items, items_by_phase)
    )
    phases = sorted(items_by_phase)
    (workstream_dir / "_orchestration.prompt.md").write_text(
        render_orchestration_prompt(config, rules_block, len(config["workItems"]), phases)
    )
    return phases


def _self_test():
    config = {
        "workstream": "demo",
        "targetBranch": "main",
        "harnesses": [{
            "name": "claude", "cli": None, "tier": "standard",
            "models": {"orchestrationWorker": {"model": "Claude Opus 5", "effort": "high"}, "subagent": "Claude Sonnet 5", "subagentSimple": "Claude Haiku 4.5"},
        }],
        "mainOrchestratorHarness": "claude",
        "reasoningLevel": "default",
        "maxConcurrency": 20,
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

**Skills**: skill-creator, writing-for-agents
**Closes**: #1

### 02-second: Do the second thing

Build the second thing, which needs the first.

**Skills**: writing-for-agents
**Closes**: #2
**Phase**: 2
"""
    with tempfile.TemporaryDirectory() as tmp:
        workstream_dir = Path(tmp)
        (workstream_dir / "_config.json").write_text(json.dumps(config))
        (workstream_dir / "_plan.md").write_text(plan)

        phases = scaffold(workstream_dir)
        assert phases == [1, 2], phases

        first = (workstream_dir / "01-first.prompt.md").read_text()
        assert "# Work Item 1: `01-first`: Do the first thing" in first
        assert "Build the first thing end to end." in first
        assert "Skills required: `skill-creator`, `writing-for-agents`." in first
        assert "No blockers" in first
        assert "### Claude Code" in first
        assert "### Global Rules" in first

        second = (workstream_dir / "02-second.prompt.md").read_text()
        assert "Blocked by Phase 1" in second

        run_order = (workstream_dir / "_run-order.md").read_text()
        assert "Ship the demo thing." in run_order
        assert "### Phase 1" in run_order and "### Phase 2" in run_order
        assert "01-first.prompt.md" in run_order and "02-second.prompt.md" in run_order

        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        assert "All 2 PRs merged" in orchestration
        assert "Use the Claude Code rules for this prompt" in orchestration
        assert "orca skills get orchestration --full" in orchestration
        assert "--worktree new-child" in orchestration
        assert "**Worktree Nesting**" in first
        assert "Inherit or `Claude Opus 5` (high reasoning)" in first

        # A slot that is neither a string nor a {model, effort} object is rejected.
        bad = dict(config)
        bad["harnesses"] = [dict(config["harnesses"][0], models={"orchestrationWorker": 5, "subagent": "x", "subagentSimple": None})]
        (workstream_dir / "_config.json").write_text(json.dumps(bad))
        try:
            load_config(workstream_dir)
            raise AssertionError("a non-string, non-object slot must be rejected")
        except ValueError:
            pass

    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        phases = scaffold(sys.argv[1])
        print(f"Scaffolded {len(phases)} phase(s) into {sys.argv[1]}")
    else:
        _self_test()
