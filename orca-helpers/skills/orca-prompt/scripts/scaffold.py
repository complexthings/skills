"""Scaffold a workstream's prompt set from `_config.json` and `_plan.md`.

Reads `<workstream-dir>/_config.json` (schema documented in
`../references/config-schema.md`) and `<workstream-dir>/_plan.md`, and writes into
that same directory: one `<id>.prompt.md` per work item and
`_orchestration.prompt.md`, the Global Rules once in `_rules.md`, plus an empty Decision Log, `_decisions.md`, when
the Workstream has none, and the reviewer brief `_review.prompt.md` when
`review` is true. It also writes back what it derived: each
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
    python3 scaffold.py --check <dir>      # FAIL: per missing wave, title, integration or tickets key; exit 1
    python3 scaffold.py                    # run the self-check
"""
import json
import math
import os
import re
import shlex
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
    render_global_rules,
    render_harness_rules,
    render_rules,
    task_time_label,
    task_time_problem,
)

# Agent Harnesses whose `worker-start` launch accepts `--model`, per `orca orchestration worker-start --help`.
# OpenCode is left out: it takes `--model` only in an existing worktree, and its Work Item lines open a new one.
LAUNCH_OPTION_HARNESSES = ("claude", "codex", "cursor", "agy", "muse", "omp")
# Of those, the ones that take `--model` but reject `--effort`.
MODEL_ONLY_HARNESSES = ("omp",)
# Orca agent ids that differ from the Agent Harness name; `worker-start --agent` takes the Orca id.
ORCA_AGENT_IDS = {"agy": "antigravity"}

# Generated prompts call the plugin's scripts through this root.
SCRIPTS = "${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts"
# The reviewer brief scaffold copies into a Workstream with review on.
REVIEW_BRIEF = Path(__file__).parent.parent / "references" / "work-item-review.md"
REVIEW_FILE = "_review.prompt.md"
# The Global Rules, written once beside the prompts; each Work Item prompt points here.
RULES_FILE = "_rules.md"
# The Model Slots a lone Agent Harness tries, in order, for a reviewer model unlike its author's.
REVIEWER_SLOTS = ("subagent", "mainOrchestrator", "subagentSimple")

REQUIRED_CONFIG_KEYS = {
    "workstream", "targetBranch", "harnesses", "mainOrchestratorHarness",
    "maxConcurrency", "integration", "tickets", "workItems",
}

# Agent Harness Tiers, lightest first; `route_harness` falls back by distance in this order.
TIERS = ("light", "standard")
# Integrations whose Work Items open a PR, and those whose results merge into the target branch.
PR_INTEGRATIONS = ("pr", "pr-merge")
MERGE_INTEGRATIONS = ("commit", "pr-merge")
# The Decision Log: `set_status.py log` appends entries after this header.
DECISION_LOG = "_decisions.md"
DECISION_LOG_HEADER = """# Decision Log

What the Main Orchestrator decided and learned during this Workstream, oldest first. Append entries with `set_status.py <workstream-dir> log`; a changed fact is a new entry that supersedes the old one, never an edit.
"""

WORK_ITEM_RE = re.compile(r"^### (?P<id>[\w.-]+): (?P<title>.+)$", re.MULTILINE)
FIELD_RE = re.compile(r"^(?:\*\*(Skills|Closes|Wave|Phase|Definition of Done)\*\*|(Definition of Done)):\s*(.+)$\n?", re.MULTILINE)
DONE_SECTION_RE = re.compile(r"^## Definition of Done\n(?P<body>.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
RULES_SECTION_RE = re.compile(r"^## Orchestration Rules\n.*?(?=^## |\Z)", re.DOTALL | re.MULTILINE)


def write_text_atomic(path, text, prefix):
    """Write `text` to `path` via a temp file in the same dir and a rename, so a reader never sees it half-written."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def write_json_atomic(directory, filename, data, prefix):
    """Stamp `updatedAt`, then write `data` to `directory/filename` atomically."""
    data["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_text_atomic(Path(directory) / filename, json.dumps(data, indent=2) + "\n", prefix)


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
    # Optional: a Workstream written before them scaffolds as before.
    for key in ("review", "planGate"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be true or false, got {config[key]!r}")
    command = config.get("evidenceCommand")
    if command is not None and not (isinstance(command, str) and command.strip()):
        raise ValueError(f"evidenceCommand must be a non-empty string or null, got {command!r}")
    budget = config.get("budgetUsd")
    if budget is not None and not (isinstance(budget, (int, float)) and not isinstance(budget, bool) and math.isfinite(budget) and budget > 0):
        raise ValueError(f"budgetUsd must be a positive number or null, got {budget!r}")
    if task_time_problem(config):
        raise ValueError(task_time_problem(config))
    for h in config["harnesses"]:
        check_tier(f"harness {h.get('name')!r} tier", h.get("tier"))
    ids = [wi.get("id") for wi in config["workItems"]]
    if not ids:
        raise ValueError("workItems is empty; a Workstream needs at least one Work Item")
    repeated = sorted({i for i in ids if ids.count(i) > 1}, key=str)
    if repeated:
        raise ValueError(f"workItems repeats id(s) {repeated}")
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


def repo_slug(repo, host=""):
    """Best-effort `owner/repo` from the origin remote of the repo at path `repo`; None if unavailable.

    A non-empty `host` (e.g. "github.com") matches only an origin on exactly that host, and also takes a
    trailing slash. Without `host` a trailing slash matches nothing, so kb's repo_key falls back to the dir name."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except Exception:
        return None
    if host:
        pattern = r"(?:^|[/@])" + re.escape(host) + r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$"
    else:
        pattern = r"[:/]([^/:]+/[^/]+?)(?:\.git)?$"
    m = re.search(pattern, result.stdout.strip())
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


def launch_flags(harness, slot="orchestrationWorker"):
    """`--model`/`--effort` from `harness`'s `slot`.

    Only LAUNCH_OPTION_HARNESSES take launch `--model`, and MODEL_ONLY_HARNESSES no `--effort`; every
    other Agent Harness reads its model from the Orchestration Rules block in its prompt.
    """
    if harness["name"] not in LAUNCH_OPTION_HARNESSES:
        return ""
    model, effort = normalize_model_slot(harness.get("models", {}).get(slot))
    if harness["name"] in MODEL_ONLY_HARNESSES:
        effort = None
    return f" --model {model}" + (f" --effort {effort}" if effort else "") if model else ""


def worker_start_command(harness, worktree="new-child", name="<work item id>"):
    """The exact `worker-start` line for `harness`, Model Slot flags included.

    Creation flags (`--name`, `--setup`) go only on a new worktree: worker-start rejects them on
    `current` or an existing one."""
    new = worktree.startswith("new-")
    return (
        f"orca orchestration worker-start --task <taskId> --worktree {worktree} "
        + (f"--name {name} " if new else "")
        + f"--agent {orca_agent(harness)}{launch_flags(harness, 'orchestrationWorker')}"
        + (" --setup run" if new else "") + " --json"
    )


def reviewer_for(author, harnesses):
    """`(harness, slot)` reviewing `author`'s Work Items: the first other Agent Harness on its
    Orchestration Worker slot, else `author` itself on a Model Slot with a different model."""
    other = next((h for h in harnesses if h["name"] != author["name"]), None)
    if other:
        return other, "orchestrationWorker"
    models = author.get("models", {})
    own = normalize_model_slot(models.get("orchestrationWorker"))[0]
    slot = next((k for k in REVIEWER_SLOTS if normalize_model_slot(models.get(k))[0] not in (None, own)), "orchestrationWorker")
    return author, slot


def render_review(config):
    """The orchestration prompt's Work Item Review section, rendered only when review is on."""
    ws, scripts = config["workstream"], SCRIPTS
    reports = f".orca/prompts/{ws}/_reviews/<id>.round-<n>.md"
    rows = []
    for author in config["harnesses"]:
        reviewer, slot = reviewer_for(author, config["harnesses"])
        same = reviewer is author
        note = (f" on its `{slot}` Model Slot. Only one Agent Harness is configured, so put "
                "`same Agent Harness on another Model Slot` in the review header") if same else ""
        rows.append(
            f"- Author `{author['name']}`: reviewer `{reviewer['name']}`{note}.\n\n"
            f"  ```\n  orca orchestration worker-start --spec \"<review spec>\" --task-title \"Review · <id> · round <n>\" "
            f"--worktree \"path:<author worktree>\" --agent {orca_agent(reviewer)}{launch_flags(reviewer, slot)} --json\n  ```\n\n"
            f"  Its fix round starts a fresh `{author['name']}` worker in the same worktree:\n\n"
            f"  ```\n  orca orchestration worker-start --spec \"{FIX_SPEC}\" "
            f"--task-title \"Fix · <id> · round <n>\" --worktree \"path:<author worktree>\" --agent {orca_agent(author)}{launch_flags(author)} --json\n  ```"
        )
    command = config.get("evidenceCommand")
    evidence_file = f".orca/prompts/{ws}/_reviews/<id>.<sha>.evidence.md"
    if command:
        evidence = (f"**Record the evidence** once per reviewed commit: `python3 {scripts}/evidence.py .orca/prompts/{ws}/ <id> <author worktree>`. "
                    f"It runs `{command}` in the author worktree at its head SHA and writes `{evidence_file}`, "
                    f"a first line `Evidence Record, commit <sha>, exit <code>`, then the full output. It prints that path, or `skip:` when the file already exists. "
                    "A non-zero exit is evidence for the reviewer, not a reason to stop. "
                    "A fix round makes a new commit, so it gets a new Evidence Record. Paste the file into the review spec.")
    else:
        evidence = ("**No evidence command is set**, so there is no Evidence Record. "
                    "Put `Evidence Record: none: no evidence command is set` in the review spec, and the reviewer copies it into the report header.")
    return f"""## Work Item Review

Review is on for this Workstream. Every Work Item passes a Work Item Review between its `worker_done` and its integration. A reviewer from a different Agent Harness than the author reads the diff and signs `VERDICT: SHIP` or `VERDICT: NO-SHIP`. Only a finding with a Demonstrated Failure blocks. The reviewer brief is `.orca/prompts/{ws}/{REVIEW_FILE}`.

Pick the reviewer by the author's Agent Harness. The reviewer starts in the author's worktree, read-only:

{chr(10).join(rows)}

The `<review spec>` names the brief, the Work Item id, the round, the author's Agent Harness, the author's worktree, the base branch `{config["targetBranch"]}` and the absolute report path, `<this worktree>/{reports}`. It carries the Evidence Record from step 2, so the reviewer never runs tests.

Run the rounds for one Work Item in order, from round 1:

1. **Open the round**: `python3 {scripts}/set_status.py .orca/prompts/{ws}/ <id> review <n> <reviewer>`. The Wave Band shows the item as reviewing.
2. {evidence}
3. **Start the reviewer** with its line above, then wait for its `worker_done` in the usual loop.
4. **Record the verdict** from the report: `python3 {scripts}/set_status.py .orca/prompts/{ws}/ <id> review <n> <reviewer> --report {reports}`. It reads `VERDICT: SHIP` or `VERDICT: NO-SHIP` from the report's last line, and a report without that line counts as NO-SHIP, because an unsigned review never ships.
5. **Release the reviewer** with `orca orchestration worker-release --dispatch <reviewer dispatchId> --json`. The reviewer started in an existing worktree, so its release leaves that worktree in place.
6. **On SHIP**, run the per-worker steps below. **On NO-SHIP before round 3**, start the author's fix round line above. It passes no `--terminal`, because the author's terminal settled at its `worker_done` and reusing it fails with `agent_unconfigured`. A worker on the author's Agent Harness fixes the defects, and the reviewer never does. After its `worker_done`, start round n+1. **On the third NO-SHIP**, `set_status.py` has set the item `failed` with the reason `review: 3 NO-SHIP rounds`. Integrate nothing for it, and ask the user with the question tool how to proceed, naming the three report paths.

Release the author's dispatch only in the per-worker steps, after its Work Item ships or fails review. Release closes only the worker's own agent terminal, and `orca worktree rm` stays its own step after it, so every fix round starts its fresh worker in the author's worktree. Release each fix worker after its `worker_done`. It started in an existing worktree, so its release leaves that worktree in place.

"""


# The fix round's spec in the Task-spec contract's five fields.
FIX_SPEC = ("Target: Work Item <id> in <author worktree>. "
            "Change: fix every NO-SHIP finding in <report path>. "
            "Constraints: touch only what those findings need, and keep the Work Item's Definition of Done. "
            "Ownership: you own the author's branch; commit and push the fix to that same branch, so the drain check passes. "
            "Observable acceptance: each finding's Demonstrated Failure now passes, git status --porcelain prints nothing, "
            "the branch has no unpushed commit, and worker_done carries the new commit SHA.")

DEFAULT_DONE = "The work above is done, and every test and check it touches passes."


def render_work_item_prompt(config, work_item, plan_item, rules_block, slug, workstream_dir):
    harness = route_harness(work_item["size"], config["harnesses"])
    target = config["targetBranch"]
    integration = config["integration"]
    closes = ", ".join(issue_link(c, slug) for c in plan_item["closes"])
    wave = plan_item["wave"]
    earlier = [wi["wave"] for wi in config["workItems"] if wi["wave"] < wave]
    blocked = f"Blocked by Wave {max(earlier)}" if earlier else "No blockers"
    skills = ", ".join(f"`{s}`" for s in plan_item["skills"]) or "none"
    # shortcut: absolute paths break on a plugin upgrade or a moved checkout; re-scaffold to fix.
    set_status = shlex.quote(str(Path(__file__).resolve().parent / "set_status.py"))
    progress = f"python3 {set_status} {shlex.quote(str(Path(workstream_dir).resolve()))} {work_item['id']} progress <done>/<total> \"<note>\""
    pr_check = "checks that your branch has its PR, " if integration in PR_INTEGRATIONS else ""
    # Relative dir: the worker files its prompt in its own worktree, not the orchestrator's.
    # shortcut: absolute script path, since a worker on another harness has no ${CLAUDE_PLUGIN_ROOT}; re-scaffold after a plugin upgrade.
    finish = f"python3 {shlex.quote(str(Path(__file__).resolve().parent / 'finish_work_item.py'))} .orca/prompts/{config['workstream']}/ {work_item['id']} --terminal <your handle>"

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

## Task Time

{task_time_label(config)}. This Work Item is meant to take that long. Plan your steps to fit it. When the work will clearly run past it, keep going and name the overrun in the `worker_done` body.

## Branch

Branch off `{target}`. All work happens in your own worktree.

## The work

{plan_item['work']}

Skills required: {skills}.

## Progress

Plan the work as a number of steps. Run this command once as you start, with `0/<total>`, and again each time a step finishes, so the Wave Band shows how far you are:

```
{progress}
```

`<done>` counts the steps finished, `<total>` the steps you plan, and `<note>` names the next step in a few words. A new `<total>` is fine when you re-plan. The command prints nothing on success. A `FAIL:` line from it never stops the work: carry on without it.

## Definition of Done

{plan_item['done'] or DEFAULT_DONE}

## Hard constraints

- You are an Orchestration Worker: never run `orca orchestration worker-start`. Dispatch is the Main Orchestrator's alone; a second dispatcher spends concurrency it is not tracking.
- When you are blocked, use `orca orchestration ask` rather than guessing or stopping. A guess costs a rework cycle, and a silent stop leaves the orchestrator waiting on a report that never arrives.

## Orchestration Rules

Use the {harness_display_name(harness)} rules for this prompt, plus the Global Rules in `.orca/prompts/{config['workstream']}/{RULES_FILE}`. Read that file before you start.

{rules_block}

## Completion

1. {integrate_step}
2. From your worktree root, run the finish script. `<your handle>` is the `--from` terminal handle in the preamble Orca injected. Add `--report-path <path>` when you wrote a report.
   ```
   {finish}
   ```
   It moves this prompt file into `.orca/prompts/{config['workstream']}/_completed`, {pr_check}drains your inbox, and prints the exact `worker_done` command last. Act on every `message:` line it prints. A `FAIL:` line names the step to fix; run it again after the fix.
3. Commit and push the moved prompt file.
4. Run the printed `worker_done` command exactly once, with a real subject and body. Put {report} in the body and `--task-id` from your preamble. Use `--outcome failed` instead of `--outcome succeeded` when the work is not done. Never encode failure only in prose: the orchestrator routes on the outcome flag, not on the body.
"""


def plan_reviewer(config):
    """The Plan Gate reviewer: the first Agent Harness that is not the Main Orchestrator's, else that one."""
    others = [h for h in config["harnesses"] if h["name"] != config.get("mainOrchestratorHarness")]
    return (others or config["harnesses"])[0], not others


def render_plan_gate_prompt(config, rules_block):
    ws = config["workstream"]
    reviewer, same = plan_reviewer(config)
    same_note = (
        " The plan was written in the same Agent Harness you run in, so you run on a different model: name both models in the header."
        if same else ""
    )
    return f"""# Plan Gate: `{ws}`

You are the Plan Gate reviewer for the `{ws}` Workstream. Read `_plan.md` before Wave 1 starts and sign GO or NO-GO on it. A NO-GO stops the run until the user decides, so it costs a person's time: block only on defects you can show.{same_note}

## Done looks like

`.orca/prompts/{ws}/_plan-review.md` exists, its last line is `VERDICT: GO` or `VERDICT: NO-GO`, and one `worker_done` names the verdict and that path.

That is the stop condition. Revising the plan and starting Wave 1 belong to the Main Orchestrator and the user.

## Read

- `.orca/prompts/{ws}/_plan.md`, the plan under review.
- `.orca/prompts/{ws}/_config.json`, for the Waves, sizes and Agent Harnesses.
- Each repo file the plan names, to check that the plan matches the code.

## What blocks

A finding blocks only when you can show it wastes a Wave:

- A Work Item needs another Work Item from its own Wave or a later Wave.
- Two Work Items in one Wave edit the same file.
- A Definition of Done that nobody can check.
- Work the Goal does not cover, or Goal work no Work Item covers.
- A plan claim the repo contradicts.

Sign NO-GO whenever one of these holds, because a flawed plan costs every Wave built on it. Every other finding is a suggestion and never blocks.

## Report

Write `.orca/prompts/{ws}/_plan-review.md` with the Communication Standard (`orca-helpers/references/communication-standard.md`), in this shape:

```markdown
# Plan Gate: {ws}

Reviewer: <Agent Harness> on <model>. Plan: `_plan.md` at <commit SHA>.

1. <Work Item id or section>: <the defect>. Evidence: <path:line or a quote from the plan>. Blocking.

Suggestions:
- <Work Item id or section>: <one line>.

VERDICT: GO
```

Number the blocking findings and leave out a section that has none. The last line is exactly `VERDICT: GO` with no blocking finding, or `VERDICT: NO-GO` with at least one.

## Hard constraints

- Read-only: write `_plan-review.md` and no other file. Never commit, push or edit `_plan.md`, because the user decides what changes in the plan.
- You are an Orchestration Worker: never run `orca orchestration worker-start`. Dispatch is the Main Orchestrator's alone.
- When you are blocked, use `orca orchestration ask` rather than guessing or stopping. A silent stop leaves Wave 1 waiting on a verdict that never arrives.

## Orchestration Rules

Use the {harness_display_name(reviewer)} rules for this prompt, plus the Global Rules in `.orca/prompts/{ws}/{RULES_FILE}`. Read that file before you start.

{rules_block}

## Completion

Send `worker_done` exactly once, from your own terminal, using the `taskId`, `dispatchId` and capability in the preamble Orca injected. Use `--outcome succeeded` once the report is written, whichever verdict it signs, and `--outcome failed` when you could not write it. Put the verdict and the report path in the body. Right before it, run `orca orchestration check --terminal <your handle> --json` and ack each `deliveryId` with `--ack` until `count` is 0, so a redirect lands first. Keep every flag the preamble's worker_done line carries, and append `--report-path .orca/prompts/{ws}/_plan-review.md` with real values.
"""


def render_plan_gate_section(config):
    ws = config["workstream"]
    reviewer, same = plan_reviewer(config)
    model = (
        " It is the Main Orchestrator's Agent Harness, so set `--model` to a model other than yours, and say so to the user."
        if same else ""
    )
    return f"""
### Plan Gate

Run the Plan Gate before you create any Wave's Tasks. One reviewer reads `_plan.md` and signs GO or NO-GO on it.

1. Create the Plan Gate Task:
   ```
   orca orchestration task-create --spec "Execute .orca/prompts/{ws}/_plan-gate.prompt.md" --task-title "Plan Gate · {ws}" --json
   ```
2. Start its reviewer on {harness_display_name(reviewer)}, in this worktree, so it reads the plan as written:{model}
   ```
   {worker_start_command(reviewer, worktree="current", name="plan-gate")}
   ```
3. Wait for its `worker_done`, then read the last line of `.orca/prompts/{ws}/_plan-review.md`.
4. `VERDICT: GO`: go on to Wave Tasks below and start Wave 1.
5. `VERDICT: NO-GO`: raise a Decision Gate on the Plan Gate Task, then ask the user the same question with your question tool. Lead with the report path and the blocking-finding count.
   ```
   orca orchestration gate-create --task <Plan Gate taskId> --question "Plan Gate: NO-GO on _plan.md. Revise the plan or start Wave 1 anyway?" --options '["Revise plan","Start anyway"]' --json
   ```
   Record the answer with `orca orchestration gate-resolve --id <gate_id> --resolution "<answer>" --json`. On **Start anyway**, go on to Wave Tasks below. On **Revise plan**, dispatch nothing: tell the user to revise `_plan.md`, re-run `scaffold.py`, and start this prompt again.

### Wave Tasks
"""


RESUME_DOCS = ["_plan.md", "_orchestration.prompt.md", DECISION_LOG, "_status.json"]


def render_resume(ws):
    """The orchestration prompt's `## Resume` section: the Read: attestation and the missing-doc stop."""
    docs = "\n".join(f"{n}. `.orca/prompts/{ws}/{doc}`" for n, doc in enumerate(RESUME_DOCS, 1))
    return f"""## Resume

This run is a resume when any Work Item in `.orca/prompts/{ws}/_status.json` has left `todo`, or when you continue this Workstream after a compaction or a handover. On a resume, read these four docs in full before any dispatch:

{docs}

When any of the four is missing, stop the resume. Dispatch nothing, start no worker and create no Task. Report the missing path, then its fix, for example: `Resume stopped: .orca/prompts/{ws}/{DECISION_LOG} is missing. Restore it from git, then resume again.` Each doc holds state the run needs, so a resume without one re-dispatches finished work or repeats a rejected approach.

Your first report after a resume starts with one `Read:` line that names every doc you read, these four first: `Read: {", ".join(RESUME_DOCS)}`. Add any other doc you read after them. The user checks this line to confirm the resume picked up the current plan and state.
"""


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

    integrated_by = {
        "commit": f"merges the branch into `{target}` with `git` and pushes it, then checks the worktree is drained",
        "branch": "checks the worktree is drained and merges nothing",
        "pr": "checks the worktree is drained and leaves the PR open for review",
        "pr-merge": f"checks the worktree is drained, then merges the PR into `{target}` with `gh`",
    }[integration]
    closes = ", closes each `**Closes**` issue" if merges else ""
    steps = [
        f"""**Integrate the worker**:
   ```
   python3 {SCRIPTS}/integrate.py .orca/prompts/{ws}/ <id> --dispatch <dispatchId> --worktree <worker worktree>
   ```
   It {integrated_by}. Then it releases the worker, which closes only the worker's own agent terminal, never its setup terminals or configured tabs. It removes the worktree when release left it{closes}, and marks the item complete in `_status.json`. It stops at the first failed step with that step's `FAIL:` line. Fix the cause and run the same command again: it starts at the failed step. The `dispatchId` looks like `ctx_62066a4ef024`; it is in the `worker_done` payload, or from `orca orchestration task-list --json`. Read a released worker's output with `orca orchestration worker-read`; do not keep its terminal open just to re-read it. Retain a worker with `worker-retain` instead only when the user asked to keep it live.""",
        f'**Log what it decided**: when the worker chose between approaches or learned a fact a later Wave needs, record it with `python3 {SCRIPTS}/set_status.py .orca/prompts/{ws}/ log "<title>" "<body>" --commit <repo>@<sha>`.',
    ]
    if integration in PR_INTEGRATIONS:
        tickets = "use `to-spec` / `to-tickets` for new tickets, " if config["tickets"] else ""
        steps.append(
            "**Check the PR** with `gh` for description comments and review comments. If any need action: run `grill-with-docs` to align on the fix (when it refuses to run, follow orca-prompt's `references/grilling.md` instead), "
            f"{tickets}log each decision with the `set_status.py log` call above, update the work item prompts and ADRs with `writing-for-agents`, and `_orchestration.prompt.md`. Commit and push that immediately."
        )
    review = config.get("review") is True
    if review:
        steps.insert(0, "**Wait for `VERDICT: SHIP`** from the Work Item Review above. Run none of the steps below before it.")
    per_worker = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1))
    pending = " At report time the merge has not happened yet, so the worktree must stay." if merges else ""

    return f"""# Main Orchestrator: `{ws}`

You are the Main Orchestrator for the `{ws}` workstream. You dispatch work item prompts to Orchestration Workers, integrate what they produce, and own the worktree lifecycle. The work itself lives in the prompt files; this file carries orchestration only.

## Done looks like

Every Work Item's Definition of Done holds, {"every Work Item's last review round signed `VERDICT: SHIP`, " if review else ""}{"the Workstream Definition of Done below holds, " if done else ""}{integrated}, {issues}and {prompts_done}.

That is the stop condition: keep waiting and dispatching until all of it holds, and stop as soon as it does.

## Task Time

{task_time_label(config)}. Each Work Item is meant to take that long, and every Work Item prompt carries the same Task Time. A worker that sends nothing well past it gets a check with `orca orchestration worker-list --run <runId> --include-remote --json`.
{f'''
## Workstream Definition of Done

{done}

Check every item here yourself after the last Wave settles, and report each one's result.
''' if done else ""}
## Tool routing

Before dispatching anything, load Orca's bundled orchestration skill — `orca skills get orchestration`, the compact guide — and dispatch by what it says. At an action gate the guide names, load only that reference with `orca skills get orchestration --reference references/<file>.md`; run `--full` once only when the CLI rejects `--reference`, not by a copy of it kept in this repo. Use `orca skills get orca-cli` for worktree operations. Target branch: `{target}`.

Choose the Orca CLI executable once for this session: use the value of `ORCA_CLI_COMMAND` when that environment variable is set (Orca exports it for managed WSL sessions); otherwise `orca-dev` in a dev checkout whose session exposes `ORCA_DEV_REPO_ROOT`; otherwise `orca-ide` on Linux outside an Orca-managed terminal, where bare `orca` is the GNOME screen reader; otherwise `orca`. Every command below writes `orca` as a placeholder — substitute the executable you chose.

{render_resume(ws)}
## Dispatch

Run the Waves in order: {wave_list}. Wave N starts only after every Work Item in Wave N-1 is complete.

Read the Decision Log, `.orca/prompts/{ws}/{DECISION_LOG}`, before you start each Wave, so no Wave repeats an approach an entry already rejected. When you choose between approaches, reject one, or learn a fact a later Wave needs, record it at once with `python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/orca-prompt/scripts/set_status.py .orca/prompts/{ws}/ log "<title>" "<body>" [--commit <repo>@<sha>] [--supersedes "<old title>"]`, so it survives compaction. Routine dispatch and state changes belong in `_status.json`, not here. When a fact changes, log a new entry with `--supersedes` instead of editing the old one, so the history shows what was true when. When a Work Item prompt needs an entry, point at its `### <date> · <title>` heading instead of pasting the entry, so the prompt stays small and current.

After each Wave settles, and before the next one starts, write its Wave Retro, so each Wave's failures improve the next: `python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/orca-prompt/scripts/set_status.py .orca/prompts/{ws}/ log "Wave N retro" "<body>"`, with the Wave's number for N. The body holds one bullet per failure in that Wave, `- <what failed>: <the rule, test or doc that would have prevented it>`. A failure is a failed Work Item, a NO-SHIP round, an escalation, or a rework cycle. When nothing failed, the body is the one line `No failures.`, so a missing retro always means the step was skipped. Where a named rule, test or doc fits a remaining Work Item, point that Work Item's prompt at the retro before you dispatch the next Wave. A fix outside every remaining Work Item stays in the retro for the user to act on.

Confirm the runtime, build `_status.json`, then create or bind one Run for this workstream, once, before any dispatch. Record the Run, so `dispatch.py` binds it instead of creating a second one:

```
orca status --json
python3 {SCRIPTS}/set_status.py .orca/prompts/{ws}/ --start
orca orchestration run-create --objective "{ws}" --json
python3 {SCRIPTS}/set_status.py .orca/prompts/{ws}/ run <runId>
```
{render_plan_gate_section(config) if config.get("planGate") else ""}
Then create every Task up front and print the first Wave's `worker-start` lines:

```
python3 {SCRIPTS}/dispatch.py .orca/prompts/{ws}/
```

It creates one Task per Work Item not yet complete, Wave by Wave, each later Wave depending on the whole previous one, and records every `taskId` in `_status.json`. Then it prints one `worker-start` line per ready Work Item, routed to its Agent Harness. Run every printed line. It stops at the first failed step with one `FAIL:` line; after the fix, run it again with `--resume`, which creates only the missing Tasks. When a Wave completes, run `dispatch.py .orca/prompts/{ws}/ --resume` to print the next Wave's lines.{model_note}{merge_wait}

`--worktree new-child` makes the worker's worktree a child of yours, so Orca records the nesting. Use `--worktree new-top-level` only for work genuinely independent of this workstream. Dispatch every ready Task in a Wave at once.

## Waiting

Wait with the orchestration skill's `orca orchestration check --wait --types worker_done,escalation,question --timeout-ms <n> --json` loop rather than a sleep/poll loop; follow its ack rule exactly — process every message in the returned Delivery, reply to any `question`, decide each settled worker's next owner, and only then acknowledge with `--ack <deliveryId>` and wait again until every Dispatch has settled. A timeout or empty result is a checkpoint, not a failure. After three empty waits in a row, list the workers with `orca orchestration worker-list --run <runId> --include-remote --json`. Rows page at 100: while `page.hasMore` is true, run it again with `--cursor <page.nextCursor>`. Act on each row's `projection.nextAction`. A `none` nextAction means read `liveness.reason` and keep waiting. Leave the wait for a worker only on positive proof that it stopped: `exited` liveness, a process exit, or a final turn that sent no `worker_done`. `unverifiable` authorizes nothing.

A valid `worker_done` settles its Task and Dispatch, so never follow it with `task-update --status completed`. Before you report the Workstream done, `orca orchestration worker-list --run <runId> --terminal-state reclaimable --json` must return no rows.

{render_review(config) if review else ""}## Per completed worker

Run these in order.

{per_worker}

## Last step: the Knowledge Graph

After the last Wave settles and before you report the Workstream done, write its lessons and decisions to the Orca Knowledge Graph, so the next Workstream in this repo recalls them. Read `.orca/prompts/{ws}/{DECISION_LOG}` and write one page, slug `{ws}-lessons`, with every lesson a later Workstream needs: `python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/orca-kb/scripts/kb.py update {ws}-lessons --page "<markdown>" --extraction '<json>'`. Give every node the aliases a future task would name it by, because recall seeds only on literal names. The `orca-kb` skill states the extraction format. A `FAIL:` line means nothing was written: fix what it names and run it again.

## Timing gotchas worth the ink

- Release only after the drain check passes, then remove the worktree as its own step: `worker-release` closes the worker's own agent terminal, never the worktree.{pending}
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

    slug = repo_slug(".")
    rules_block = render_rules(config)
    # Work Item prompts carry only the Agent Harness sections; the Global Rules live once in _rules.md.
    harness_block = render_harness_rules(config)

    for work_item in config["workItems"]:
        work_item["wave"] = plan_items[work_item["id"]]["wave"]
        work_item["title"] = plan_items[work_item["id"]]["title"]
    for work_item in config["workItems"]:
        plan_item = plan_items[work_item["id"]]
        if (workstream_dir / "_completed" / f"{work_item['id']}.prompt.md").exists():
            continue  # already done: a second copy would fail validate.py
        prompt = render_work_item_prompt(config, work_item, plan_item, harness_block, slug, workstream_dir)
        (workstream_dir / f"{work_item['id']}.prompt.md").write_text(prompt)

    gate_path = workstream_dir / "_plan-gate.prompt.md"
    if config.get("planGate"):
        gate_path.write_text(render_plan_gate_prompt(config, harness_block))
    else:
        gate_path.unlink(missing_ok=True)

    if config.get("review") is True:
        (workstream_dir / REVIEW_FILE).write_text(REVIEW_BRIEF.read_text())
    (workstream_dir / RULES_FILE).write_text(render_global_rules(config) + "\n")
    waves = sorted({wi["wave"] for wi in config["workItems"]})
    (workstream_dir / "_orchestration.prompt.md").write_text(
        render_orchestration_prompt(config, rules_block, plan_items, waves, workstream_done((workstream_dir / "_plan.md").read_text()))
    )
    if not (workstream_dir / DECISION_LOG).exists():
        (workstream_dir / DECISION_LOG).write_text(DECISION_LOG_HEADER)
    (workstream_dir / "_config.json").write_text(json.dumps(config, indent=2) + "\n")
    plan_path = workstream_dir / "_plan.md"
    plan_path.write_text(inject_rules(plan_path.read_text(), rules_block))
    return waves


def check(workstream_dir):
    """The Wave keys a pre-Wave `_config.json` lacks, one line each; empty when it needs no re-scaffold."""
    try:
        config = json.loads((Path(workstream_dir) / "_config.json").read_text())
    except (OSError, ValueError) as e:
        return [f"cannot read _config.json: {e}"]
    if not isinstance(config, dict):
        return ["_config.json is not a JSON object"]
    lines = [f"_config.json missing {key}" for key in ("integration", "tickets") if key not in config]
    for n, wi in enumerate(config.get("workItems") or []):
        wi = wi if isinstance(wi, dict) else {}
        lines += [f"workItems[{n}] {wi.get('id', '?')} missing {key}" for key in ("wave", "title") if key not in wi]
    return lines


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
        # The Global Rules live once in _rules.md and the orchestrator prompt, never per Work Item.
        assert "### Global Rules" not in first
        assert "Global Rules in `.orca/prompts/demo/_rules.md`" in first
        assert (workstream_dir / "_rules.md").read_text().startswith("### Global Rules")
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
        assert orchestration.index("## Per completed worker") < orchestration.index("## Last step: the Knowledge Graph")
        assert "skills/orca-kb/scripts/kb.py update demo-lessons" in orchestration
        assert "Run the Waves in order: Wave 1, Wave 2." in orchestration
        assert "_run-order.md" not in orchestration
        assert "scripts/dispatch.py .orca/prompts/demo/\n" in orchestration and "dispatch.py .orca/prompts/demo/ --resume" in orchestration
        assert "scripts/integrate.py .orca/prompts/demo/ <id> --dispatch <dispatchId> --worktree <worker worktree>" in orchestration
        assert "<taskId of" not in orchestration and "**Merge the PR**" not in orchestration
        assert "Use the Claude Code rules for this prompt" in orchestration
        assert "`orca skills get orchestration`, the compact guide" in orchestration
        assert "--reference references/<file>.md" in orchestration
        assert "ORCA_CLI_COMMAND" in orchestration
        assert "orca orchestration run-create --objective" in orchestration
        assert "--worktree new-child" in orchestration
        assert "--parent-worktree" not in orchestration and "--no-parent" not in orchestration
        assert "check --wait --types worker_done,escalation,question" in orchestration
        assert "to-tickets" not in orchestration  # tickets is false
        assert "## Workstream Definition of Done\n\n1. `pytest` passes." in orchestration
        assert "the Workstream Definition of Done below holds" in orchestration
        assert "orca status --json" in orchestration
        assert "--terminal-state reclaimable" in orchestration
        assert "references/grilling.md" in orchestration
        assert workstream_done("# x\n\n## Goal\n\ny\n") is None
        assert orca_agent({"name": "agy", "cli": None}) == "antigravity"
        assert "--agent antigravity --model gemini-3.8-flash --effort high --setup run" in worker_start_command(
            {"name": "agy", "cli": None, "models": {"orchestrationWorker": {"model": "gemini-3.8-flash", "effort": "high"}}}
        )
        assert "**Worktree Nesting**" in (workstream_dir / "_rules.md").read_text()
        assert "Inherit or `Claude Opus 5.5` (high reasoning)" in first

        # A `commit` Workstream's prompts name no PR anywhere.
        (workstream_dir / "_config.json").write_text(json.dumps(dict(config, integration="commit")))
        scaffold(workstream_dir)
        for name in ("01-first.prompt.md", "02-second.prompt.md", "_orchestration.prompt.md", "_rules.md"):
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
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        problems = check(sys.argv[2])
        for line in problems:
            print(f"FAIL: {line}")
        sys.exit(1 if problems else 0)
    if len(sys.argv) == 2:
        waves = scaffold(sys.argv[1])
        print(f"Scaffolded {len(waves)} wave(s) into {sys.argv[1]}")
    else:
        _self_test()
