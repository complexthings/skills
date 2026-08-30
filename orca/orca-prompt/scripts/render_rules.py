"""Render the `Orchestration Rules` block from a workstream's `_config.json`.

Assembled once per workstream and copied verbatim into every generated
prompt file (work item prompts and `_orchestration.prompt.md`) — one
Agent Harness section per `harnesses[]` entry, followed by the static Global
Rules.

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
    "prime-agent": "Prime Agent",
    "agy": "Antigravity",
}

EFFORT_LEVELS = ("low", "medium", "high", "xhigh")

REASONING_LABELS = {
    "default": "medium",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "x-high",
}

GLOBAL_RULES = """### Global Rules

- **Nested Subagents**: Subagents may spawn their own subagents, up to 3 layers below the main conversation and within Maximum Concurrency. Two gates: the assigning subagent owns the result, and the deepest layer does its own work and returns one summary. Where an Agent Harness blocks nested spawning, a subagent may ask the orchestrator to spawn on its behalf under the same limits.
- **Worktree Nesting**: An Orchestration Worker's worktree is created as a child of the Main Orchestrator's worktree — `orca orchestration worker-start --worktree new-child`, or `--parent-worktree active` when the worktree is created directly — so Orca records the parent relationship. Use `--worktree new-top-level` (or `--no-parent`) only when the work is genuinely independent of the orchestrator's.
- **Git & Branching**: Writing agents work in isolated worktrees. Subagents write files locally — no commit, no push, no `gh` writes. The orchestrator alone merges into `{target_branch}` and opens PRs, and merges its own PRs without waiting for my review.
- **Permissions**: Orchestrator and subagents run in auto mode with full read/write in the repo.
- **Asking Questions**: Use `askUserQuestion`, `askQuestions`, `ask_user`, `question`, `ask_user_question` or the Agent Harness equivalent, and label your recommended answer **(Recommended)**. Subagents route questions through the orchestrator. The orchestrator **MUST USE** its question tool when prompting me.
- **Progress**: Keep a live todo list via `TaskCreate`/`TaskList`/`TaskUpdate`/`TaskGet`, `todo`, `task`, `todowrite` or the Agent Harness equivalent, so I can watch the work land.
- **Execution**: Read the actual files before writing. Reason from facts only.
- **CLI**: Orchestrator and subagents use `rtk` for CLI commands — `rtk python` for `python3`, plus `grep`, `rg`, `ls`, `tree`, `read`, `git`, `gh`, `pnpm`, `json`.
  - **rtk gotcha**: `rtk ls` and `rtk gh issue list` **silently truncate long output**. Confirm absence with `rtk proxy find <path> -maxdepth N` or `rtk proxy gh issue list --json` before concluding a directory or issue does not exist. A previous session burned most of its budget regenerating work that was already on disk.
- **Parallelism**: Spawn parallel subagents whenever subtasks are independent.
- **Codegraph**: Use Codegraph where available; this repo is indexed."""


def normalize_model_slot(value):
    """Return `(model, effort_or_none)` for a Model Slot.

    A slot is either a plain string (or `null`) — meaning "use the Workstream
    `reasoningLevel`" — or `{"model": ..., "effort": ...}` overriding the level
    for that slot alone. Anything else raises `ValueError`.
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
        for slot, value in (harness.get("models") or {}).items():
            try:
                normalize_model_slot(value)
            except ValueError as e:
                problems.append(f"harness {harness.get('name')!r} slot {slot!r}: {e}")
    return problems


def harness_display_name(harness):
    return DISPLAY_NAMES.get(harness["name"], harness.get("cli") or harness["name"].title())


def render_harness_section(harness, reasoning_level, max_concurrency):
    default_label = REASONING_LABELS.get(reasoning_level, reasoning_level)
    models = harness["models"]
    lines = [f"### {harness_display_name(harness)}", ""]

    def slot(key):
        """Return `(model, label)`, the slot's effort overriding the Workstream level."""
        model, effort = normalize_model_slot(models.get(key))
        return model, REASONING_LABELS.get(effort, effort) if effort else default_label

    orchestrator, label = slot("orchestrationWorker")
    orch_text = f"Inherit or `{orchestrator}`" if orchestrator else "Inherit"
    lines.append(f"- **Orchestrator**: {orch_text} ({label} reasoning)")

    subagent, label = slot("subagent")
    lines.append(f"- **Subagent Model**: `{subagent}` ({label} reasoning)")

    simple, label = slot("subagentSimple")
    if simple:
        lines.append(f"- **Subagent Model, Simple Tasks**: `{simple}` ({label} reasoning)")

    lines.append(f"- **Maximum Concurrency**: {max_concurrency}, counting Orchestrator, Subagents and Nested Subagents")
    return "\n".join(lines)


def render_rules(config):
    """Return the full Orchestration Rules block for `config` (a loaded `_config.json`)."""
    reasoning = config.get("reasoningLevel") or "default"
    sections = [
        render_harness_section(h, reasoning, config["maxConcurrency"])
        for h in config["harnesses"]
    ]
    sections.append(GLOBAL_RULES.format(target_branch=config["targetBranch"]))
    return "\n\n".join(sections)


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
                    "orchestrationWorker": "Claude Sonnet 5",
                    "subagent": "Claude Sonnet 5",
                    "subagentSimple": "Claude Haiku 4.5",
                },
            },
            {
                "name": "pi",
                "cli": None,
                "tier": "light",
                "models": {
                    "orchestrationWorker": None,
                    "subagent": "openai-codex/gpt-5.6-luna",
                    "subagentSimple": None,
                },
            },
        ],
        "mainOrchestratorHarness": "claude",
        "reasoningLevel": "default",
        "maxConcurrency": 20,
        "workItems": [],
    }
    block = render_rules(config)
    assert "### Claude Code" in block
    assert "### Pi" in block
    assert "### Global Rules" in block
    assert "Inherit or `Claude Sonnet 5` (medium reasoning)" in block
    assert "**Subagent Model, Simple Tasks**: `Claude Haiku 4.5`" in block
    assert "Inherit (medium reasoning)" in block  # Pi's null orchestrationWorker
    assert "Subagent Model, Simple Tasks" not in block.split("### Pi")[1].split("### Global")[0]
    assert "merges into `main`" in block

    # A per-slot effort overrides the Workstream reasoning level for that slot alone.
    config["harnesses"][0]["models"]["orchestrationWorker"] = {"model": "gpt-5.6-sol", "effort": "high"}
    block = render_rules(config)
    assert "Inherit or `gpt-5.6-sol` (high reasoning)" in block
    assert "**Subagent Model**: `Claude Sonnet 5` (medium reasoning)" in block
    assert model_slot_problems(config) == []

    # A third shape is rejected.
    config["harnesses"][0]["models"]["subagent"] = ["Claude Sonnet 5"]
    assert model_slot_problems(config), "a list slot must be reported"
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
