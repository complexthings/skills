"""Render the `Orchestration Rules` block from a workstream's `_config.json`.

Assembled once per workstream: one Agent Harness section per `harnesses[]`
entry, followed by the static Global Rules. `scaffold.py` writes the full
block into `_orchestration.prompt.md` and the Global Rules alone into
`_rules.md`; each Work Item prompt carries the Agent Harness sections and a
pointer to `_rules.md`.

Usage:
    python3 render_rules.py <path-to-_config.json>   # print the block
    python3 render_rules.py                          # run the self-check
"""
import json
import sys

DISPLAY_NAMES = {
    "claude": "Claude Code",
    "opencode": "OpenCode",
    "copilot": "GitHub Copilot",
    "codex": "OpenAI Codex",
    "pi": "Pi",
    "agy": "Antigravity",
}

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# Every Model Slot `_config.json` must carry per Agent Harness. `null` is a
# valid value for any of them — a missing key is not (see the schema notes in
# `../references/config-schema.md`).
REQUIRED_SLOTS = ("mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple")

EFFORT_LABELS = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "x-high",
    "max": "max",
}

# Task Time: how long each Work Item is meant to take. `_config.json` and
# Prompt Settings store the id; an absent `taskTime` reads as the default.
TASK_TIMES = {
    "low": ("Low", "under 5 minutes"),
    "medium": ("Medium", "under 10 minutes"),
    "high": ("High", "under 15 minutes"),
    "xhigh": ("Extra High", "under 30 minutes"),
    "ultra": ("Ultra High", "30 minutes or more"),
}
DEFAULT_TASK_TIME = "medium"


def task_time_problem(values):
    """A problem string when `values` holds a `taskTime` that is not a Task Time id, else None."""
    if "taskTime" in values and not (isinstance(values["taskTime"], str) and values["taskTime"] in TASK_TIMES):
        return f"taskTime must be one of {'|'.join(TASK_TIMES)}, got {values['taskTime']!r}"


def task_time_label(config):
    """`Medium, under 10 minutes`: the Task Time `config` names, or the default."""
    label, span = TASK_TIMES[config.get("taskTime", DEFAULT_TASK_TIME)]
    return f"{label}, {span}"


GLOBAL_RULES = """### Global Rules

- **Nested Subagents**: Subagents may spawn their own subagents through the Agent Harness's native mechanism — Claude Code's Agent tool or the equivalent — up to 3 layers below the main conversation and within Maximum Concurrency. Two gates: the assigning subagent owns the result, and the deepest layer does its own work and returns one summary. Where an Agent Harness blocks nested spawning, a subagent may ask the orchestrator to spawn on its behalf under the same limits. Orca dispatch is the Main Orchestrator's alone unless Orca's nested worker depth setting is raised above `1`; an Orchestration Worker that needs a **Nested Worker** asks the Main Orchestrator to start it.
- **Subagent Model Slots**: An Orchestration Worker may spawn subagents to reach its Work Item's goal: on its Agent Harness's **Subagent Model** for ordinary work, and on its **Subagent Model, Simple Tasks** for lookups and mechanical edits. Spawning through the Agent Harness's native mechanism is not Orca dispatch, so it needs no `worker-start`. Each subagent counts toward Maximum Concurrency, and the worker checks every result before relying on it.
- **Worktree Nesting**: An Orchestration Worker's worktree is created as a child of the Main Orchestrator's worktree — `orca orchestration worker-start --worktree new-child` — so Orca records the parent relationship and the workstream's worktrees stay together. Use `--worktree new-top-level` only when the work is genuinely independent of the orchestrator's.
- **Git & Branching**: Writing agents work in isolated worktrees. Subagents write files locally and leave commit, push and `gh` writes to the agent that owns the worktree — concurrent writers on one branch lose each other's work. {integration_rule}
- **Permissions**: Orchestrator and subagents run in auto mode with full read/write in the repo.
- **Asking Questions**: An Orchestration Worker asks with `orca orchestration ask` and never opens a local question tool, because the Main Orchestrator cannot see or answer one. Only the Main Orchestrator asks the user through its question tool — `askUserQuestion`, `askQuestions`, `ask_user`, `question`, `ask_user_question` or the Agent Harness equivalent — rather than in prose, because prose questions scroll past unanswered and the run stalls. Label your recommended answer **(Recommended)**. Subagents route questions through the agent that spawned them.
- **Progress**: The Wave Band reads `_status.json`, so every Work Item state change goes through `set_status.py`, and a worker reports each finished step with the `progress` command its prompt names.
- **Execution**: Read the actual files before writing, and reason from what they say rather than from what the plan implies. Read what the change touches, not the whole repo — an unread file that the change touches is the expensive miss, not an unread one it does not.
- **CLI**: Where `rtk` is installed (`which rtk`), orchestrator and subagents use it for CLI commands — `rtk python` for `python3`, plus `grep`, `rg`, `ls`, `tree`, `read`, `git`, `gh`, `pnpm`, `json`. Where it is not installed, use the plain command.
  - **rtk gotcha**: `rtk ls` and `rtk gh issue list` **silently truncate long output**. Confirm absence with `rtk proxy find <path> -maxdepth N` or `rtk proxy gh issue list --json` before concluding a directory or issue does not exist. A previous session burned most of its budget regenerating work that was already on disk.
- **Parallelism**: Spawn parallel subagents whenever subtasks are independent. Keep work serial where subtasks depend on each other or edit the same files, and stay within Maximum Concurrency — parallel writers on one file cost more to reconcile than they save.
- **Codegraph**: Use Codegraph where a `.codegraph/` directory exists at the repo root."""

# How each Work Item's result reaches the target branch: `_config.json` `integration`.
INTEGRATIONS = ("commit", "branch", "pr", "pr-merge")
INTEGRATION_RULES = {
    "commit": "The orchestrator alone merges each Work Item's branch into `{target_branch}`.",
    "branch": "Each Work Item's branch is pushed and left for review; nothing merges into `{target_branch}` during the run.",
    "pr": "Each Work Item opens a PR into `{target_branch}` and leaves it for review; nothing merges during the run.",
    "pr-merge": "Each Work Item opens a PR into `{target_branch}`. The orchestrator alone merges, and merges each PR without waiting for the user's review.",
}


def normalize_model_slot(value):
    """Return `(model, effort_or_none)` for a Model Slot.

    A slot is either a plain string (or `null`), which carries no effort, or
    `{"model": ..., "effort": ...}`. Anything else raises `ValueError`.
    """
    if value is None or isinstance(value, str):
        return value, None
    if isinstance(value, dict) and set(value) <= {"model", "effort"} and isinstance(value.get("model"), str):
        effort = value.get("effort")
        if effort is None or effort in EFFORT_LEVELS:
            return value["model"], effort
    return _reject(value)


def _reject(value):
    raise ValueError(
        f"model slot must be a string, null, or {{\"model\": str, \"effort\": "
        f"{'|'.join(EFFORT_LEVELS)}}}, got {value!r}"
    )


def model_slot_problems(config):
    """Return a list of problem strings for every malformed Model Slot in `config`."""
    problems = []
    for harness in config.get("harnesses") or []:
        models = harness.get("models") or {}
        for slot in REQUIRED_SLOTS:
            if slot not in models:
                problems.append(f"harness {harness.get('name')!r} is missing the {slot!r} Model Slot")
        for slot, value in models.items():
            try:
                normalize_model_slot(value)
            except ValueError as e:
                problems.append(f"harness {harness.get('name')!r} slot {slot!r}: {e}")
    return problems


def harness_display_name(harness):
    return DISPLAY_NAMES.get(harness["name"], harness.get("cli") or harness["name"].title())


def render_harness_section(harness, max_concurrency):
    models = harness["models"]
    lines = [f"### {harness_display_name(harness)}", ""]

    def slot(key):
        """Return `(model, suffix)`: the suffix names the slot's effort, or is empty without one."""
        model, effort = normalize_model_slot(models.get(key))
        return model, f" ({EFFORT_LABELS[effort]} reasoning)" if effort else ""

    main, label = slot("mainOrchestrator")
    if main:
        lines.append(f"- **Main Orchestrator**: `{main}`{label}")

    orchestrator, label = slot("orchestrationWorker")
    orch_text = f"Inherit or `{orchestrator}`" if orchestrator else "Inherit"
    lines.append(f"- **Orchestrator**: {orch_text}{label}")

    subagent, label = slot("subagent")
    lines.append(f"- **Subagent Model**: {f'`{subagent}`' if subagent else 'Inherit'}{label}")

    simple, label = slot("subagentSimple")
    if simple:
        lines.append(f"- **Subagent Model, Simple Tasks**: `{simple}`{label}")

    lines.append(f"- **Maximum Concurrency**: {max_concurrency}, counting Orchestrator, Subagents and Nested Subagents")
    return "\n".join(lines)


def render_harness_rules(config):
    """Return the Agent Harness sections of the Orchestration Rules block, without the Global Rules."""
    return "\n\n".join(render_harness_section(h, config["maxConcurrency"]) for h in config["harnesses"])


def render_global_rules(config):
    """Return the Global Rules section, with the integration rule for `config` filled in."""
    target = config["targetBranch"]
    rule = INTEGRATION_RULES[config["integration"]].format(target_branch=target)
    return GLOBAL_RULES.format(target_branch=target, integration_rule=rule)


def render_rules(config):
    """Return the full Orchestration Rules block for `config` (a loaded `_config.json`)."""
    return f"{render_harness_rules(config)}\n\n{render_global_rules(config)}"


def _self_test():
    config = {
        "workstream": "demo",
        "targetBranch": "main",
        "harnesses": [
            {
                "name": "claude",
                "cli": None,
                "tier": "standard",
                "models": {
                    "mainOrchestrator": {"model": "Claude Opus 5.5", "effort": "high"},
                    "orchestrationWorker": "Claude Sonnet 5.5",
                    "subagent": "Claude Sonnet 5.5",
                    "subagentSimple": "Claude Haiku 5.5",
                },
            },
            {
                "name": "pi",
                "cli": None,
                "tier": "light",
                "models": {
                    "mainOrchestrator": None,
                    "orchestrationWorker": None,
                    "subagent": "openai-codex/gpt-6-luna",
                    "subagentSimple": None,
                },
            },
        ],
        "mainOrchestratorHarness": "claude",
        "maxConcurrency": 20,
        "integration": "pr-merge",
        "tickets": False,
        "workItems": [],
    }
    block = render_rules(config)
    assert block == f"{render_harness_rules(config)}\n\n{render_global_rules(config)}"
    assert "### Global Rules" not in render_harness_rules(config)
    assert render_global_rules(config).startswith("### Global Rules")
    assert "### Claude Code" in block
    assert "### Pi" in block
    assert "### Global Rules" in block
    # A plain-string slot carries no effort, so its line names none.
    assert "- **Orchestrator**: Inherit or `Claude Sonnet 5.5`\n" in block
    assert "**Main Orchestrator**: `Claude Opus 5.5` (high reasoning)" in block
    # Pi does not run the Main Orchestrator, so its section carries no such line.
    assert "Main Orchestrator" not in block.split("### Pi")[1].split("### Global")[0]
    assert "**Subagent Model, Simple Tasks**: `Claude Haiku 5.5`" in block
    assert "- **Orchestrator**: Inherit\n" in block  # Pi's null orchestrationWorker
    assert "Subagent Model, Simple Tasks" not in block.split("### Pi")[1].split("### Global")[0]
    assert "The orchestrator alone merges, and merges each PR" in block
    # Only the PR integrations name a PR.
    for integration in ("commit", "branch"):
        assert "PR" not in render_rules(dict(config, integration=integration)), integration
    # Global Rules track the live orchestration guide, not the retired flags.
    assert "--worktree new-child" in block
    assert "--parent-worktree" not in block and "--no-parent" not in block
    assert "nested worker depth" in block and "**Nested Worker**" in block
    assert "Where `rtk` is installed (`which rtk`)" in block
    assert "a `.codegraph/` directory exists" in block
    # Orchestration Workers learn they may use their subagent Model Slots.
    assert "- **Subagent Model Slots**: An Orchestration Worker may spawn subagents" in block
    assert "**Subagent Model, Simple Tasks**" in render_global_rules(config)

    # Task Time: an absent key reads as Medium, every id renders, anything else is a problem.
    assert task_time_label(config) == "Medium, under 10 minutes"
    assert task_time_problem(config) is None
    assert [task_time_label({"taskTime": t}) for t in TASK_TIMES] == [
        "Low, under 5 minutes", "Medium, under 10 minutes", "High, under 15 minutes",
        "Extra High, under 30 minutes", "Ultra High, 30 minutes or more"]
    for bad in (None, "", "Medium", "max", 10, ["low"]):
        assert task_time_problem({"taskTime": bad}) == f"taskTime must be one of low|medium|high|xhigh|ultra, got {bad!r}", bad
    # No first-person voice: the rules address the user in the third person.
    for pronoun in (" my ", " me.", " me ", " I "):
        assert pronoun not in block, pronoun

    # Each slot carries its own effort; no Workstream-wide level fills the rest.
    config["harnesses"][0]["models"]["orchestrationWorker"] = {"model": "gpt-6.1-sol", "effort": "xhigh"}
    block = render_rules(config)
    assert "Inherit or `gpt-6.1-sol` (x-high reasoning)" in block
    assert "- **Subagent Model**: `Claude Sonnet 5.5`\n" in block
    # An old `_config.json` still holding `reasoningLevel` renders the same block.
    assert render_rules(dict(config, reasoningLevel="high")) == block
    assert model_slot_problems(config) == []

    # A missing slot key is reported, not silently defaulted.
    del config["harnesses"][0]["models"]["mainOrchestrator"]
    assert any("missing the 'mainOrchestrator' Model Slot" in p for p in model_slot_problems(config))
    config["harnesses"][0]["models"]["mainOrchestrator"] = None

    # A third shape is rejected.
    config["harnesses"][0]["models"]["subagent"] = ["Claude Sonnet 5.5"]
    assert model_slot_problems(config), "a list slot must be reported"
    # Both Priority Files rank models at `max`, so a slot may carry it.
    assert normalize_model_slot({"model": "gpt-6-luna", "effort": "max"}) == ("gpt-6-luna", "max")
    try:
        normalize_model_slot({"model": "x", "effort": "turbo"})
        raise AssertionError("unknown effort must be rejected")
    except ValueError:
        pass

    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        with open(sys.argv[1]) as f:
            print(render_rules(json.load(f)))
    else:
        _self_test()
