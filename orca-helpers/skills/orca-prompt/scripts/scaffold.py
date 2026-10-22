"""Scaffold a workstream's prompt set from `_config.json` and `_plan.md`.

Reads `<workstream-dir>/_config.json` (schema documented in
`../SKILL.md`) and `<workstream-dir>/_plan.md`, and writes into
that same directory: one `<id>.prompt.md` per work item and
`_orchestration.prompt.md`. It also writes back what it derived: each
`workItems[]` entry's `wave` and `title` into `_config.json`, and the rendered
Orchestration Rules block into `_plan.md`'s `## Orchestration Rules` section.

`_plan.md` must carry a `## Work Items` section with one subsection per work
item, matched by id against `_config.json`'s `workItems[].id`:

    ### <id>: <title>

    <prose — the specific work>

    **Definition of Done**: what must hold for this Work Item to be complete
    **Skills**: skill-one, skill-two
    **Closes**: #12
    **Wave**: 1

Every field line is optional: `**Definition of Done**` falls back to a generic
one, `**Skills**` to none, `**Closes**` to no linked issue, and `**Wave**` to
wave 1. `**Phase**: N` is read as an alias of `**Wave**: N`, and a plain
`Definition of Done:` line counts the same as the bold one.

Usage:
    python3 scaffold.py <workstream-dir>   # scaffold that workstream
    python3 scaffold.py                    # run the self-check
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_rules import (
    INTEGRATIONS,
    harness_display_name,
    model_slot_problems,
    normalize_model_slot,
    render_rules,
)

# Agent Harnesses whose `worker-start` launch accepts `--model`/`--effort`.
LAUNCH_OPTION_HARNESSES = ("claude", "codex", "agy")
# Orca agent ids that differ from the Agent Harness name; `worker-start --agent` takes the Orca id.
ORCA_AGENT_IDS = {"agy": "antigravity"}

REQUIRED_CONFIG_KEYS = {
    "workstream", "targetBranch", "harnesses", "mainOrchestratorHarness",
    "maxConcurrency", "integration", "tickets", "workItems",
}

# Agent Harness Tiers, lightest first; `route_harness` falls back by distance in this order.
TIERS = ("light", "standard")
# Integrations whose Work Items open a PR, and those whose results merge into the target branch.
PR_INTEGRATIONS = ("pr", "pr-merge")
MERGE_INTEGRATIONS = ("commit", "pr-merge")

WORK_ITEM_RE = re.compile(r"^### (?P<id>[\w.-]+): (?P<title>.+)$", re.MULTILINE)
FIELD_RE = re.compile(r"^(?:\*\*(Skills|Closes|Wave|Phase|Definition of Done)\*\*|(Definition of Done)):\s*(.+)$\n?", re.MULTILINE)
DONE_SECTION_RE = re.compile(r"^## Definition of Done\n(?P<body>.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
RULES_SECTION_RE = re.compile(r"^## Orchestration Rules\n.*?(?=^## |\Z)", re.DOTALL | re.MULTILINE)


def write_json_atomic(directory, filename, data, prefix):
    """Stamp `updatedAt`, then write `data` to `directory/filename` via a temp file and rename."""
    data["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, Path(directory) / filename)
    except BaseException:
        os.unlink(tmp)
        raise


def claim(band_file):
    """Make the Claude Code session running this script the band's Owning Session (ADR 0011)."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session:
        Path(f"{band_file}.owner").write_text(session)


def load_config(workstream_dir):
    config = json.loads((workstream_dir / "_config.json").read_text())
    missing = REQUIRED_CONFIG_KEYS - config.keys()
    if missing:
        raise ValueError(f"_config.json missing required keys: {sorted(missing)}")
    slot_problems = model_slot_problems(config)
    if slot_problems:
        raise ValueError("; ".join(slot_problems))
    if config["integration"] not in INTEGRATIONS:
        raise ValueError(f"integration must be one of {'|'.join(INTEGRATIONS)}, got {config['integration']!r}")
    if not isinstance(config["tickets"], bool):
        raise ValueError(f"tickets must be true or false, got {config['tickets']!r}")
    for h in config["harnesses"]:
        check_tier(f"harness {h.get('name')!r} tier", h.get("tier"))
    for wi in config["workItems"]:
        check_tier(f"work item {wi.get('id')!r} size", wi.get("size"))
    return config


def check_tier(what, value):
    if value not in TIERS:
        raise ValueError(f"{what} must be one of {'|'.join(TIERS)}, got {value!r}")


def parse_plan(workstream_dir):
    text = (workstream_dir / "_plan.md").read_text()
    matches = list(WORK_ITEM_RE.finditer(text))
    items = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # A Work Item's body stops at the next `## ` section too, e.g. a trailing appendix.
        body = re.split(r"^## ", text[m.end():end], maxsplit=1, flags=re.MULTILINE)[0].strip()
        fields = {(f[0] or f[1]).replace("Phase", "Wave"): f[2].strip() for f in FIELD_RE.findall(body)}
        wave = fields.get("Wave", "1")
        if not wave.isdigit():
            raise ValueError(f"work item {m.group('id')!r}: Wave must be a number, got {wave!r}")
        items[m.group("id")] = {
            "title": m.group("title").strip(),
            "work": re.sub(r"\n{3,}", "\n\n", FIELD_RE.sub("", body)).strip(),
            "done": fields.get("Definition of Done"),
            "skills": [s.strip() for s in fields["Skills"].split(",")] if "Skills" in fields else [],
            "closes": [c.strip() for c in fields["Closes"].split(",")] if "Closes" in fields else [],
            "wave": int(wave),
        }
    return items


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
    """The first Agent Harness whose tier matches `size`, else the one with the nearest tier."""
    check_tier("size", size)
    for h in harnesses:
        check_tier(f"harness {h.get('name')!r} tier", h.get("tier"))
    return min(harnesses, key=lambda h: abs(TIERS.index(h["tier"]) - TIERS.index(size)))


def item_number(item_id):
    m = re.match(r"0*(\d+)", item_id)
    return int(m.group(1)) if m else "?"


def harness_cli(harness):
    return harness.get("cli") or harness["name"]


def orca_agent(harness):
    """The Orca agent id `worker-start --agent` takes for `harness`."""
    return ORCA_AGENT_IDS.get(harness["name"], harness_cli(harness))


def workstream_done(plan_text):
    """The body of `_plan.md`'s `## Definition of Done` section, or None when it has none."""
    m = DONE_SECTION_RE.search(plan_text)
    return m.group("body").strip() or None if m else None


def worker_start_command(harness):
    """The exact `worker-start` line for `harness`, Model Slot flags included.

    Only Claude, Codex and Antigravity take launch `--model`/`--effort`; every other Agent
    Harness reads its model from the Orchestration Rules block in its prompt.
    """
    flags = ""
    if harness["name"] in LAUNCH_OPTION_HARNESSES:
        model, effort = normalize_model_slot(harness.get("models", {}).get("orchestrationWorker"))
        if model:
            flags = f" --model {model}" + (f" --effort {effort}" if effort else "")
    return (
        "orca orchestration worker-start --task <taskId> --worktree new-child "
        f"--name <work item id> --agent {orca_agent(harness)}{flags} --setup run --json"
    )


DEFAULT_DONE = "The work above is done, and every test and check it touches passes."


def render_work_item_prompt(config, work_item, plan_item, rules_block, slug):
    harness = route_harness(work_item["size"], config["harnesses"])
    target = config["targetBranch"]
    integration = config["integration"]
    closes = ", ".join(issue_link(c, slug) for c in plan_item["closes"])
    wave = plan_item["wave"]
    earlier = [wi["wave"] for wi in config["workItems"] if wi["wave"] < wave]
    blocked = f"Blocked by Wave {max(earlier)}" if earlier else "No blockers"
    skills = ", ".join(f"`{s}`" for s in plan_item["skills"]) or "none"

    if integration in PR_INTEGRATIONS:
        landed = f"a PR into `{target}` is open" + (f" linking {closes}" if closes else "")
        report = "that PR link"
        integrate_step = f"Open a PR into `{target}`" + (", linking the issue it closes in the description." if closes else ".")
    elif integration == "branch":
        landed = "your branch is pushed to `origin`"
        report = "that branch name"
        integrate_step = "Commit the work and push your branch with `git push -u origin HEAD`. It is left there for review."
    else:
        landed = "every change is committed"
        report = "that branch name"
        integrate_step = f"Commit the work on your branch. Do not push to `{target}`: the Main Orchestrator merges your branch."
    orchestrator_owns = {
        "commit": f"Merging your branch into `{target}`, closing the issue and removing the worktree",
        "branch": "Reviewing your branch and removing the worktree",
        "pr": "Reviewing the PR and removing the worktree",
        "pr-merge": "Merging the PR, closing the issue and removing the worktree",
    }[integration]

    return f"""# Work Item {item_number(work_item['id'])}: `{work_item['id']}`: {plan_item['title']}

Closes {closes or "no linked issue"}. Wave {wave}. {blocked}.

## Done looks like

The Definition of Done below holds, the work is on a branch off `{target}`, this prompt file has moved into `_completed/`, {landed}, and one `worker_done` carries {report}.

That is the stop condition. {orchestrator_owns} belong to the Main Orchestrator — stop once `worker_done` is sent, and do not pick up further work.

## Branch

Branch off `{target}`. All work happens in your own worktree.

## The work

{plan_item['work']}

Skills required: {skills}.

## Definition of Done

{plan_item['done'] or DEFAULT_DONE}

## Hard constraints

- You are an Orchestration Worker: never run `orca orchestration worker-start`. Dispatch is the Main Orchestrator's alone; a second dispatcher spends concurrency it is not tracking.
- When you are blocked, use `orca orchestration ask` rather than guessing or stopping. A guess costs a rework cycle, and a silent stop leaves the orchestrator waiting on a report that never arrives.

## Orchestration Rules

Use the {harness_display_name(harness)} rules for this prompt, plus the Global Rules.

{rules_block}

## Completion

1. Move this prompt file into `.orca/prompts/{config['workstream']}/_completed`.
2. {integrate_step}
3. Send `worker_done` exactly once, from your own terminal, using the `taskId`, `dispatchId` and capability in the preamble Orca injected — `--outcome succeeded` when the work is done, `--outcome failed` when it is not. Never encode failure only in prose: the orchestrator routes on the outcome flag, not on the body. Put {report} in the body.
"""


def task_create_lines(config, plan_items):
    """One `task-create` per Work Item, Wave by Wave; each later Wave depends on the whole previous one."""
    by_wave = {}
    for work_item in config["workItems"]:
        by_wave.setdefault(plan_items[work_item["id"]]["wave"], []).append(work_item["id"])
    lines, previous = [], []
    for wave in sorted(by_wave):
        deps = ",".join(f'"<taskId of {i}>"' for i in previous)
        for item_id in by_wave[wave]:
            lines.append(
                f'orca orchestration task-create --spec "Execute .orca/prompts/{config["workstream"]}/{item_id}.prompt.md" '
                f'--task-title "Wave {wave} · {plan_items[item_id]["title"]}"'
                + (f" --deps '[{deps}]'" if previous else "") + " --json"
            )
        previous = by_wave[wave]
    return "\n".join(lines)


def render_orchestration_prompt(config, rules_block, plan_items, waves, done=None):
    main_harness = next(
        (h for h in config["harnesses"] if h["name"] == config.get("mainOrchestratorHarness")), None,
    )
    main_display = harness_display_name(main_harness) if main_harness else (config.get("mainOrchestratorHarness") or "the configured Agent Harness")
    target = config["targetBranch"]
    ws = config["workstream"]
    integration = config["integration"]
    merges = integration in MERGE_INTEGRATIONS
    count = len(config["workItems"])
    wave_list = ", ".join(f"Wave {w}" for w in waves)

    start_lines = "\n".join(worker_start_command(h) for h in config["harnesses"])
    no_launch_options = [
        h for h in config["harnesses"] if h["name"] not in LAUNCH_OPTION_HARNESSES
    ]
    model_note = "".join(
        f"\n\n`{orca_agent(h)}` takes no launch `--model`: that worker reads its model from the "
        "Orchestration Rules block in its own prompt file."
        for h in no_launch_options
    )

    integrated = {
        "commit": f"every Work Item's branch merged into `{target}` and pushed",
        "branch": "every Work Item's branch pushed and left for review",
        "pr": f"every Work Item's PR open into `{target}` for review",
        "pr-merge": f"every Work Item's PR merged into `{target}`",
    }[integration]
    linked = any(plan_items[wi["id"]]["closes"] for wi in config["workItems"])
    issues = "every linked issue closed, " if merges and linked else ""
    # Workers move their prompt in their own worktree; only merged integrations bring that back here.
    prompts_done = f"all {count} prompt files are in `_completed/`" if merges else "every Work Item is complete, with a `worker_done` received for each one dispatched in this run"
    merge_wait = (
        f"\n\nOrca settles a Task at `worker_done`, before its merge. Start a later Wave's Tasks only after every merge from the previous Wave has landed in `{target}`."
        if merges else ""
    )

    integrate_step = {
        "commit": f"**Merge the branch** into `{target}` with plain `git`, then push `{target}`.",
        "branch": "**Leave the branch** pushed for review. Merge nothing.",
        "pr": "**Leave the PR** open for review. Merge nothing.",
        "pr-merge": f"**Merge the PR** into `{target}`. Use `gh`; fall back to plain `git` if `gh` fails.",
    }[integration]
    # A squash merge rewrites SHAs, so PR integrations check the pushed branch before merging.
    drained = f"origin/{target}..HEAD" if integration == "commit" else "@{upstream}..HEAD"
    drain_step = f"""**Verify the worktree is drained.** Both must print nothing:
   ```
   cd <worktree> && git status --porcelain
   cd <worktree> && git log {drained}
   ```"""
    steps = [integrate_step, drain_step] if integration == "commit" else [drain_step, integrate_step]
    steps += [
        "**Release the worker**: `orca orchestration worker-release --dispatch <dispatchId> --json`. Release deletes a `new-child` worktree, so run it only after the drain check passes. Every settled worker is reused (`worker-start --task <next> --terminal <handle>`), retained (`worker-retain`, only when the user asked to keep it live), or released — decide before you acknowledge the Delivery and wait again. The `dispatchId` looks like `ctx_62066a4ef024`; it is in the `worker_done` payload, or from `orca orchestration task-list --json`. Read a released worker's output with `orca orchestration worker-read`; do not keep its terminal open just to re-read it.",
        '**Remove the worktree** if release left it: `orca worktree rm --worktree "path:/abs/path/to/worktree" --json`.',
    ]
    if merges:
        steps.append("**Close** any GitHub Issues the merge left open.")
    if integration in PR_INTEGRATIONS:
        tickets = "use `to-spec` / `to-tickets` for new tickets, " if config["tickets"] else ""
        steps.append(
            "**Check the PR** with `gh` for description comments and review comments. If any need action: run `grill-with-docs` to align on the fix (when it refuses to run, follow orca-prompt's `references/grilling.md` instead), "
            f"{tickets}update the work item prompts, decisions and ADRs with `writing-for-agents`, and `_orchestration.prompt.md`. Commit and push that immediately."
        )
    per_worker = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1))
    pending = " At report time the merge has not happened yet, so the worktree must stay." if merges else ""

    return f"""# Main Orchestrator: `{ws}`

You are the Main Orchestrator for the `{ws}` workstream. You dispatch work item prompts to Orchestration Workers, integrate what they produce, and own the worktree lifecycle. The work itself lives in the prompt files; this file carries orchestration only.

## Done looks like

Every Work Item's Definition of Done holds, {"the Workstream Definition of Done below holds, " if done else ""}{integrated}, {issues}and {prompts_done}.

That is the stop condition: keep waiting and dispatching until all of it holds, and stop as soon as it does.
{f"""
## Workstream Definition of Done

{done}

Check every item here yourself after the last Wave settles, and report each one's result.
""" if done else ""}
## Tool routing

Before dispatching anything, load Orca's bundled orchestration skill — `orca skills get orchestration --full` — and dispatch by what it says, not by a copy of it kept in this repo. Use `orca skills get orca-cli` for worktree operations. Target branch: `{target}`.

Choose the Orca CLI executable once for this session: use the value of `ORCA_CLI_COMMAND` when that environment variable is set (Orca exports it for managed WSL sessions); otherwise `orca-dev` in a dev checkout whose session exposes `ORCA_DEV_REPO_ROOT`; otherwise `orca-ide` on Linux outside an Orca-managed terminal, where bare `orca` is the GNOME screen reader; otherwise `orca`. Every command below writes `orca` as a placeholder — substitute the executable you chose.

## Dispatch

Run the Waves in order: {wave_list}. Wave N starts only after every Work Item in Wave N-1 is complete.

Confirm the runtime, then create or bind one Run for this workstream, once, before any dispatch:

```
orca status --json
orca orchestration run-create --objective "{ws}" --json
```

Then create every Task up front, Wave by Wave. A Wave 1 Task takes no `--deps`; each later Task lists the Task ids of the whole previous Wave, so Orca holds it until that Wave settles:

```
{task_create_lines(config, plan_items)}
```

Start one Orchestration Worker on each Task that `orca orchestration task-list --ready --brief --json` lists:

```
{start_lines}
```

Pick the `worker-start` line for the Agent Harness you routed that work item to.{model_note}{merge_wait}

`--worktree new-child` makes the worker's worktree a child of yours, so Orca records the nesting. Use `--worktree new-top-level` only for work genuinely independent of this workstream. Dispatch every ready Task in a Wave at once.

## Waiting

Wait with the orchestration skill's `orca orchestration check --wait --types worker_done,escalation,question --timeout-ms <n> --json` loop rather than a sleep/poll loop; follow its ack rule exactly — process every message in the returned Delivery, reply to any `question`, decide each settled worker's next owner, and only then acknowledge with `--ack <deliveryId>` and wait again until every Dispatch has settled. A timeout or empty result is a checkpoint, not a failure. After three empty waits in a row, list the workers with `orca orchestration worker-list --include-remote --json` and act on each row's `projection.nextAction`.

A valid `worker_done` settles its Task and Dispatch, so never follow it with `task-update --status completed`. Before you report the Workstream done, `orca orchestration worker-list --run <runId> --terminal-state reclaimable --json` must return no rows.

## Per completed worker

Run these in order.

{per_worker}

## Timing gotchas worth the ink

- Release only after the drain check passes: `worker-release` deletes a `new-child` worktree with it.{pending}
- `worker-release` returning `state: retained, reason: user_takeover` just means Orca kept a terminal you opened yourself. Still run `orca worktree rm`.
- A dirty tree means the drain check failed for a reason. Fix the cause instead of reaching for `--force`.

## Orchestration Rules

Use the {main_display} rules for this prompt, plus the Global Rules.

{rules_block}
"""


def inject_rules(plan_text, rules_block):
    """`plan_text` with its `## Orchestration Rules` section body replaced by `rules_block`, or the section appended."""
    section = f"## Orchestration Rules\n\n{rules_block}\n\n"
    if RULES_SECTION_RE.search(plan_text):
        plan_text = RULES_SECTION_RE.sub(lambda _: section, plan_text, count=1)
    else:
        plan_text = plan_text.rstrip("\n") + "\n\n" + section
    return plan_text.rstrip("\n") + "\n"


def scaffold(workstream_dir):
    workstream_dir = Path(workstream_dir)
    config = load_config(workstream_dir)
    plan_items = parse_plan(workstream_dir)

    missing = [wi["id"] for wi in config["workItems"] if wi["id"] not in plan_items]
    if missing:
        raise ValueError(f"_plan.md's Work Items section has no entry for: {missing}")

    slug = repo_slug()
    rules_block = render_rules(config)

    for work_item in config["workItems"]:
        work_item["wave"] = plan_items[work_item["id"]]["wave"]
        work_item["title"] = plan_items[work_item["id"]]["title"]
    for work_item in config["workItems"]:
        plan_item = plan_items[work_item["id"]]
        if (workstream_dir / "_completed" / f"{work_item['id']}.prompt.md").exists():
            continue  # already done: a second copy would fail validate.py
        prompt = render_work_item_prompt(config, work_item, plan_item, rules_block, slug)
        (workstream_dir / f"{work_item['id']}.prompt.md").write_text(prompt)

    waves = sorted({wi["wave"] for wi in config["workItems"]})
    (workstream_dir / "_orchestration.prompt.md").write_text(
        render_orchestration_prompt(config, rules_block, plan_items, waves, workstream_done((workstream_dir / "_plan.md").read_text()))
    )
    (workstream_dir / "_config.json").write_text(json.dumps(config, indent=2) + "\n")
    plan_path = workstream_dir / "_plan.md"
    plan_path.write_text(inject_rules(plan_path.read_text(), rules_block))
    return waves


def _self_test():
    config = {
        "workstream": "demo",
        "targetBranch": "main",
        "harnesses": [{
            "name": "claude", "cli": None, "tier": "standard",
            "models": {"mainOrchestrator": {"model": "Claude Opus 5.5", "effort": "medium"}, "orchestrationWorker": {"model": "Claude Opus 5.5", "effort": "high"}, "subagent": "Claude Sonnet 5.5", "subagentSimple": "Claude Haiku 5.5"},
        }],
        "mainOrchestratorHarness": "claude",
        "maxConcurrency": 20,
        "integration": "pr-merge",
        "tickets": False,
        "workItems": [
            {"id": "01-first", "size": "standard"},
            {"id": "02-second", "size": "light"},
        ],
    }
    plan = """# Plan: demo

## Goal

Ship the demo thing.

## Definition of Done

1. `pytest` passes.

**Integration**: each Work Item merges into `main`.

## Orchestration Rules

Left to the scripts.

## Work Items

### 01-first: Do the first thing

Build the first thing end to end.

**Definition of Done**: the first thing ships.
**Skills**: skill-creator, writing-for-agents
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

        waves = scaffold(workstream_dir)
        assert waves == [1, 2], waves
        assert not (workstream_dir / "_run-order.md").exists()

        # Wave and title are written back into _config.json; the rules block into _plan.md.
        written = json.loads((workstream_dir / "_config.json").read_text())
        assert written["workItems"][1] == {"id": "02-second", "size": "light", "wave": 2, "title": "Do the second thing"}
        plan_text = (workstream_dir / "_plan.md").read_text()
        assert "Left to the scripts." not in plan_text and "### Global Rules" in plan_text
        assert plan_text.index("### Global Rules") < plan_text.index("## Work Items")

        first = (workstream_dir / "01-first.prompt.md").read_text()
        assert "# Work Item 1: `01-first`: Do the first thing" in first
        assert "Build the first thing end to end." in first
        assert "Skills required: `skill-creator`, `writing-for-agents`." in first
        assert "## Definition of Done\n\nthe first thing ships." in first
        assert "**Definition of Done**" not in first
        assert "Wave 1. No blockers" in first
        assert "### Claude Code" in first
        assert "### Global Rules" in first
        # Outcome-first: what done looks like leads, hard constraints carry a reason.
        assert first.index("## Done looks like") < first.index("## The work")
        assert "## Hard constraints" in first

        # No light-tier Agent Harness: the light Work Item falls back to the standard one.
        second = (workstream_dir / "02-second.prompt.md").read_text()
        assert "Blocked by Wave 1" in second
        assert f"## Definition of Done\n\n{DEFAULT_DONE}" in second
        assert "Use the Claude Code rules" in second

        assert "--outcome succeeded" in first and "--outcome failed" in first
        assert "never run `orca orchestration worker-start`" in first
        assert "orca orchestration ask" in first
        assert "a PR into `main` is open linking" in first

        orchestration = (workstream_dir / "_orchestration.prompt.md").read_text()
        # Outcome-first: the stop condition leads the file, before Dispatch.
        assert "every Work Item's PR merged into `main`" in orchestration
        assert orchestration.index("## Done looks like") < orchestration.index("## Dispatch")
        assert "Run the Waves in order: Wave 1, Wave 2." in orchestration
        assert "_run-order.md" not in orchestration
        assert '--task-title "Wave 1 · Do the first thing" --json' in orchestration
        assert """--task-title "Wave 2 · Do the second thing" --deps '["<taskId of 01-first>"]' --json""" in orchestration
        assert "task-list --ready" in orchestration
        assert "Use the Claude Code rules for this prompt" in orchestration
        assert "orca skills get orchestration --full" in orchestration
        assert "ORCA_CLI_COMMAND" in orchestration
        assert "orca orchestration run-create --objective" in orchestration
        assert "--worktree new-child" in orchestration
        assert "--setup run --json" in orchestration
        assert "--agent claude --model Claude Opus 5.5 --effort high --setup run" in orchestration
        assert "--parent-worktree" not in orchestration and "--no-parent" not in orchestration
        assert "check --wait --types worker_done,escalation,question" in orchestration
        assert "to-tickets" not in orchestration  # tickets is false
        assert "## Workstream Definition of Done\n\n1. `pytest` passes." in orchestration
        assert "the Workstream Definition of Done below holds" in orchestration
        assert "orca status --json" in orchestration
        assert '--worktree "path:/abs/path/to/worktree"' in orchestration
        assert "--terminal-state reclaimable" in orchestration
        assert "references/grilling.md" in orchestration
        assert workstream_done("# x\n\n## Goal\n\ny\n") is None
        assert orca_agent({"name": "agy", "cli": None}) == "antigravity"
        assert "--agent antigravity --model gemini-3.8-flash --effort high --setup run" in worker_start_command(
            {"name": "agy", "cli": None, "models": {"orchestrationWorker": {"model": "gemini-3.8-flash", "effort": "high"}}}
        )
        assert "**Worktree Nesting**" in first
        assert "Inherit or `Claude Opus 5.5` (high reasoning)" in first

        # A `commit` Workstream's prompts name no PR anywhere.
        (workstream_dir / "_config.json").write_text(json.dumps(dict(config, integration="commit")))
        scaffold(workstream_dir)
        for name in ("01-first.prompt.md", "02-second.prompt.md", "_orchestration.prompt.md"):
            assert "PR" not in (workstream_dir / name).read_text(), name

        # An unknown integration, and a slot that is neither a string nor a {model, effort} object, are rejected.
        bad_slot = dict(config, harnesses=[dict(config["harnesses"][0], models={"mainOrchestrator": None, "orchestrationWorker": 5, "subagent": "x", "subagentSimple": None})])
        for bad in (dict(config, integration="squash"), bad_slot):
            (workstream_dir / "_config.json").write_text(json.dumps(bad))
            try:
                load_config(workstream_dir)
                raise AssertionError(f"must be rejected: {bad}")
            except ValueError:
                pass

    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        waves = scaffold(sys.argv[1])
        print(f"Scaffolded {len(waves)} wave(s) into {sys.argv[1]}")
    else:
        _self_test()
