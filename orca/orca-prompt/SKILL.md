---
name: orca-prompt
description: Start a new Orca workstream — interviews the user for the workstream name, target branch, and Scope of Work, settles the scope with grill-with-docs, and writes _config.json and _plan.md under .orca/prompts/<workstream>/. Use when the user wants to start a new workstream, plan a set of work item prompts for Orca orchestration, or says "orca-prompt", "new workstream", "plan this as a workstream".
---

# orca-prompt

Starts a new Orca workstream. A **Workstream** is a named body of work that one plan file scopes and one set of generated prompt files delivers, living under `.orca/prompts/<workstream>/`. A full run writes `_config.json` and `_plan.md`, then scaffolds every generated file from them: one prompt file per work item, `_run-order.md`, and `_orchestration.prompt.md`.

## Steps

### 1. Round 1: name, branch, scope source

Ask these three questions with the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent), one recommended answer per question marked **(Recommended)**:

1. **Workstream name** — the identifier used for `.orca/prompts/<workstream>/` and inside prompts as `<workstream>`. Recommend a kebab-case name derived from what the user has already said in this conversation; if nothing points to one, ask for free text with no recommendation.
2. **Target branch** — the branch the Main Orchestrator merges every work item's PR into. Recommend `main` **(Recommended)** unless the repo's default branch is something else (check `git remote show origin` or `git branch --show-current` on a clean checkout).
3. **Where the Scope of Work comes from**:
   - **Interview me now (Recommended)** — nothing is settled yet; the next step interviews the user from scratch.
   - **I already have it written down** — the user points at a file, issue, or pastes it; skip straight to using `grill-with-docs` to sharpen what they gave you instead of starting blank.

Do not proceed to step 2 until all three are answered.

### 2. Round 2: which Agent Harnesses, and who orchestrates

Run `orca/orca-prompt/scripts/detect_harnesses.py` (stdlib Python, no args) and read its JSON report of which of the seven known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `prime-agent`, `agy`) are on PATH. The report already comes back in the priority order `data/model-priority.json` sets, so offer the installed Agent Harnesses in the order it lists them — do not re-sort and do not re-rank them yourself.

Ask, with the Agent Harness question tool, one recommended answer marked **(Recommended)**:

1. **Which Agent Harnesses to use for this workstream** — multi-select, options are every Agent Harness the probe found installed, plus a free-text path: the user types a name and the CLI command for an Agent Harness the probe missed. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select, same option set as question 1 (installed Agent Harnesses plus free text), asked independently so it never depends on question 1's answer. This is a separate decision from being a worker Agent Harness: the Main Orchestrator merges PRs, drives dispatch, and owns the worktree lifecycle. If the answer isn't already in question 1's selection, add it to the Agent Harness list — the orchestrator's Agent Harness always needs an entry.

### 3. Round 3: models, tier, concurrency, reasoning

Ask, with the Agent Harness question tool, one recommended answer marked **(Recommended)** per question:

1. **Per Agent Harness selected in Round 2**, three Model Slots — Orchestration Worker, Subagent, Subagent for simple tasks. Every model ordering and its suggested Effort Level lives in `orca/orca-prompt/data/model-priority.json`, keyed by provider (`anthropic`, `github-copilot`, `openai-codex`) and then by Model Slot (`orchestrationWorker`, `subagent`, `subagentSimple`) — read that file, never this prose, and offer each slot's options in the order it lists them, top entry marked **(Recommended)** with the `effort` it names. Its `cautions` array holds the effort-level traps worth repeating to the user. Claude Code (`anthropic`) and OpenAI Codex (`openai-codex`) have small known sets, so their options come straight from the file; GitHub Copilot's option list is the file's `github-copilot` entries plus free-form text for anything else the user has access to.
2. **For Pi, Prime Agent, OpenCode and Antigravity**, discover the models instead of guessing them — these Agent Harnesses publish what they can run, and the list is too long and too changeable to hard-code. Per Agent Harness, run `orca/orca-prompt/scripts/list_models.py <name> <slot>` (`pi`, `prime-agent`, `opencode`, `agy`; slot is `orchestrationWorker`, `subagent` or `subagentSimple`) and read its JSON: `{"harness": ..., "providers": {"<provider>": [{"model": ..., "efforts": [...], "suggestedEffort": ...}]}}`. The script ranks the live model list against `data/model-priority.json` for that slot, so offer the models in the order it returns them and mark the first **(Recommended)** with its `suggestedEffort`. A model the priority file does not know still appears, below every ranked one — offer it too, never drop it.
   - **Which provider to use for this Agent Harness** — single-select over the report's `providers` keys, one question per Agent Harness. Ask it first: the model question's options come from the chosen provider alone.
   - **One model per Model Slot** — three single-selects (Orchestration Worker, Subagent, Subagent for simple tasks), options being that provider's `model` values from the run for that slot.

   Antigravity bakes its Effort Level into the model id (`gemini-3.7-flash-high`); `list_models.py` strips the suffix and reports it under `efforts`, so the user picks a base model once and never sees two entries differing only by effort. Where a chosen `agy` model has a non-empty `efforts`, ask which one and write the slot as `{"model": ..., "effort": ...}` — that effort is what `agy --effort` receives.
3. **An effort for any slot that should not use the Workstream reasoning level** — per Agent Harness, multi-select over the three slots, `Use the workstream reasoning level` (Recommended) for each. Where the user picks an effort, ask which of `low`, `medium`, `high`, `xhigh`, and write that slot as `{"model": ..., "effort": ...}` instead of a plain string. Skip a slot whose effort question 2 already answered.
4. **An Agent Harness Tier for each selected Agent Harness** — `light` or `standard`, single-select, used later to route work items by size.
5. **Maximum concurrency** — free-text number, counting Orchestrator, Subagents, and Nested Subagents together.
6. **Reasoning level for Orchestrator and Subagents** — single-select: Default (medium) (Recommended), Low, Medium, High, X-High.

Within Round 3, only the model question depends on its own round: the provider pick in question 2 narrows that Agent Harness's model options, which is the point of asking provider first. Every other question in Round 2 and Round 3 is answerable from a fixed option set. Round 3 as a whole may depend on Round 2's Agent Harness list (it needs to know which Agent Harnesses to ask about); nothing feeds back the other way.

### 4. Settle the scope

Invoke the `grill-with-docs` skill to interview the user until the Scope of Work is fully settled: every work item named, sized (`light` or `standard`), and unambiguous, every skill it depends on has a decided name and behavior. `grill-with-docs` also produces or updates `CONTEXT.md` glossary entries and ADRs as domain terms and decisions surface — let it.

Nothing here scaffolds Agent Harnesses or generates prompt files yet (Work Items 2–4 of this same pattern, applied to itself, build that). This run's output stops at the two files below.

### 5. Write `_plan.md`

Write `.orca/prompts/<workstream>/_plan.md`:

- The settled Scope of Work from step 4, in prose.
- An `## Orchestration Rules` section, built from Rounds 2 and 3: Agent Harness-specific model slots and tier, maximum concurrency, reasoning level, plus the Global Rules below verbatim.
- A `## Work Items` section, one subsection per work item, in the shape `scripts/scaffold.py` reads:

  ```markdown
  ### <id>: <title>

  <prose — the specific work>

  **Skills**: skill-one, skill-two
  **Closes**: #12
  **Phase**: 1
  ```

  `<id>` matches a `workItems[].id` in `_config.json`. `**Skills**`, `**Closes**`, and `**Phase**` are each optional (empty, unlinked, and phase 1 when omitted).

**Global Rules** (copy verbatim into every generated `_plan.md` and work item prompt):

- **Nested Subagents**: Subagents may spawn their own subagents, up to 3 layers below the main conversation and within Maximum Concurrency. Two gates: the assigning subagent owns the result, and the deepest layer does its own work and returns one summary. Where an Agent Harness blocks nested spawning, a subagent may ask the orchestrator to spawn on its behalf under the same limits.
- **Worktree Nesting**: An Orchestration Worker's worktree is created as a child of the Main Orchestrator's worktree — `orca orchestration worker-start --worktree new-child`, or `--parent-worktree active` when the worktree is created directly — so Orca records the parent relationship. Use `--worktree new-top-level` (or `--no-parent`) only when the work is genuinely independent of the orchestrator's.
- **Git & Branching**: Writing agents work in isolated worktrees. Subagents write files locally — no commit, no push, no `gh` writes. The orchestrator alone merges into `<workstream-target>` and opens PRs, and merges its own PRs without waiting for review.
- **Permissions**: Orchestrator and subagents run in auto mode with full read/write in the repo.
- **Asking Questions**: Use `askUserQuestion`, `askQuestions`, `ask_user`, `question`, `ask_user_question` or the Agent Harness equivalent, and label the recommended answer **(Recommended)**. Subagents route questions through the orchestrator.
- **Progress**: Keep a live todo list via `TaskCreate`/`TaskList`/`TaskUpdate`/`TaskGet`, `todo`, `task`, `todowrite` or the Agent Harness equivalent.
- **Execution**: Read the actual files before writing. Reason from facts only.
- **CLI**: Prefer the fastest available CLI tooling for the target Agent Harness (e.g. `rtk` where installed).
- **Parallelism**: Spawn parallel subagents whenever subtasks are independent.
- **Codegraph**: Use Codegraph where available.

### 6. Write `_config.json`

Write `.orca/prompts/<workstream>/_config.json` against the schema below, filled from Rounds 1–3's answers. Every key must be present — `null` or `[]` only where a round genuinely left it unanswered (e.g. `models.subagentSimple` for an Agent Harness with no simple-task slot) — since every downstream script treats a missing key as an error, not a default to fill in.

### 7. Propose sizes, then confirm

Propose a size (`light` or `standard`) for every work item in `_config.json`'s `workItems[]`, based on its scope in `_plan.md`. Ask the user to confirm or correct each one with the Agent Harness question tool, the proposed size marked **(Recommended)**. Write any corrections back into `_config.json` before scaffolding.

### 8. Scaffold the workstream

Run `scripts/render_rules.py` and `scripts/scaffold.py` (see their module docstrings) against the workstream's `_config.json` and `_plan.md`. This writes one `<id>.prompt.md` per work item, `_run-order.md`, and `_orchestration.prompt.md` into `.orca/prompts/<workstream>/`.

### 9. Validate

Run `scripts/validate.py <workstream-dir>` (see its module docstring) and show the user the result verbatim. A clean run prints `ok: workstream meets the Definition of Done`; a failing run prints one `FAIL:` line per missing piece and exits non-zero — fix `_config.json` or `_plan.md` and re-run step 8 before reporting the workstream ready.

## `_config.json` schema

The contract every later script in this pattern codes against. Do not rename or remove a key without updating every skill that reads it.

```json
{
  "workstream": "string — the workstream name, matches the .orca/prompts/<workstream>/ directory",
  "targetBranch": "string — branch the Main Orchestrator merges work item PRs into",
  "harnesses": [
    {
      "name": "string — Agent Harness identifier: claude | opencode | copilot | codex | pi | prime-agent | agy | <other>",
      "cli": "string — the CLI command to invoke this Agent Harness (only needed when name is not one of the seven built-ins)",
      "tier": "light | standard — routes work items to this Agent Harness by size",
      "models": {
        "orchestrationWorker": "Model Slot | null — model for the Orchestration Worker session",
        "subagent": "Model Slot | null — model for ordinary subagents",
        "subagentSimple": "Model Slot | null — model for subagents doing simple tasks"
      }
    }
  ],
  "mainOrchestratorHarness": "string | null — which harnesses[].name runs the Main Orchestrator",
  "reasoningLevel": "default | low | medium | high | xhigh",
  "maxConcurrency": "number | null — ceiling counting Orchestrator, Subagents, and Nested Subagents combined",
  "workItems": [
    {
      "id": "string — matches the work item prompt filename, e.g. 01-skill-skeleton",
      "size": "light | standard"
    }
  ]
}
```

Notes for the scripts that read this file:

- `harnesses` may hold more than one entry; a work item's Agent Harness is chosen by matching its `workItems[].size` against a `harnesses[].tier`.
- A **Model Slot** is either a plain string — `"claude-sonnet-5"`, meaning "use the Workstream `reasoningLevel`" — or an object `{"model": "gpt-5.6-sol", "effort": "high"}` overriding the level for that slot alone. Valid efforts are `low`, `medium`, `high`, `xhigh`. Scripts read a slot through `render_rules.normalize_model_slot`, which turns either shape into `(model, effort_or_none)`; any third shape is a `FAIL:` from `validate.py`.
- `models.subagentSimple` may be `null` even when the Agent Harness is fully configured — not every Agent Harness distinguishes a simple-task model (see the Pi rules in any generated `_plan.md`'s Orchestration Rules section, which has no simple-task slot).
- Every key in this schema must exist in a written `_config.json`, even where the value is `null` or `[]`. A script encountering a missing key means the file was hand-edited or written by something older than this schema — treat that as an error, not a default to silently fill in.
