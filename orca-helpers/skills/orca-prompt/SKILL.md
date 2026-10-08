---
name: orca-prompt
description: Start a new Orca Workstream — interviews for its name, target branch and Scope of Work, then writes _config.json, _plan.md and one prompt per Work Item under .orca/prompts/<workstream>/. Use for "orca-prompt", "new workstream", "plan this as a workstream", or splitting a feature into parallel agent tasks for Orca. To schedule one use orca-prompt-scheduler; for stored defaults, orca-prompt-settings.
---

# orca-prompt

Starts a new Orca Workstream. A **Workstream** is a named body of work that one plan file scopes and one set of generated prompt files delivers, living under `.orca/prompts/<workstream>/`. A full run writes `_config.json` and `_plan.md`, then scaffolds every generated file from them: one prompt file per Work Item, `_run-order.md`, and `_orchestration.prompt.md`.

## The interview always runs

Rounds 1-3 and step 4 run in order, before any file is written, even when the Scope of Work looks small, obvious, or already described earlier in the conversation. The interview exists to surface the gaps and trade-offs the user has not stated, and a scope that reads as complete is not evidence that it is.

The one exception is the invoking message itself saying to skip: "skip the interview", "use the scope I already wrote, no questions". Prior context, an earlier message in the session, an existing scope document, a light-looking workload, and your own read of the scope all leave the interview running. On a valid opt-out, take the **(Recommended)** answer for every unasked question, write them into `_plan.md` under an `Assumed, not asked` heading, and list them in your reply so the user can correct them.

Ask every question with the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent), one answer per question marked **(Recommended)**, so the user can accept a sensible default in one click and only stops to think where the default is wrong.

## Steps

### 1. Round 1: name, branch, scope source

1. **Workstream name** — the identifier used for `.orca/prompts/<workstream>/` and inside prompts as `<workstream>`. Recommend a kebab-case name derived from what the user has already said in this conversation; if nothing points to one, ask for free text with no recommendation.
2. **Target branch** — the branch the Main Orchestrator merges every Work Item's PR into. Recommend `main` unless the repo's default branch is something else (check `git remote show origin` or `git branch --show-current` on a clean checkout).
3. **Where the Scope of Work comes from**:
   - **Interview me now (Recommended)** — nothing is settled yet; step 4 interviews the user from scratch.
   - **I already have it written down** — the user points at a file or issue, or pastes it; step 4 sharpens what they gave you instead of starting blank.

### 2. Round 2: which Agent Harnesses, and who orchestrates

**Stored Prompt Settings.** Before asking anything in this round, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_settings.py --read`. A `FAIL:` line means no settings are stored yet — the ordinary first run, not an error to report — so ask Rounds 2 and 3 in full.

Where it returns settings, check each value before offering it, because a setting valid when written can go stale:

- An Agent Harness in `harnesses[]` that `detect_harnesses.py` (below) no longer reports as installed.
- A Model Slot naming a model the `priorityFile` Priority File does not carry — read that file for the fixed sets (`anthropic`, `github-copilot`, `openai-codex`); run `list_models.py` for the discovered Agent Harnesses (`pi`, `prime-agent`, `opencode`, `agy`).

Keep every still-valid setting. Name each broken one to the user with what is wrong, and re-ask that one question alone with the option set Round 2 or Round 3 would have used; the rest of the stored file stays in force.

Then show the user what the settings hold — the Agent Harnesses and their tiers, the Main Orchestrator Agent Harness, target branch, maximum concurrency, reasoning level, Priority File — and ask:

- **Use these settings for this Workstream (Recommended)** — every stored value becomes this Workstream's answer; skip Rounds 2 and 3 and go to step 4.
- **Override them for this Workstream** — ask Rounds 2 and 3 in full, offering each stored value as that question's **(Recommended)** answer.

Round 1's target branch wins either way: it was asked for this Workstream, so a stored `targetBranch` never overrides it.

**The questions.** Run `python3 ${CLAUDE_SKILL_DIR}/scripts/detect_harnesses.py` (stdlib Python, no args). Its JSON reports which of the seven known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `prime-agent`, `agy`) are on PATH, already in the priority order `data/model-priority.json` sets — offer them in exactly that order.

1. **Which Agent Harnesses to use for this Workstream** — multi-select over every installed Agent Harness, plus a free-text path where the user types the name and CLI command of an Agent Harness the probe missed. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select over the same option set, asked independently of question 1. This is a separate decision from being a worker Agent Harness: the Main Orchestrator merges PRs, drives dispatch, and owns the worktree lifecycle. If the answer is not in question 1's selection, add it to the Agent Harness list — the Main Orchestrator's Agent Harness always needs an entry.

### 3. Round 3: models, tier, concurrency, reasoning

1. **Which Priority File this Workstream ranks models against** — single-select, asked first because questions 2-4 all read the file it picks. Two ship in `${CLAUDE_SKILL_DIR}/data/`: the **Opinionated Set (Recommended)**, `recommended-priority.json`, ranked by hand from day-to-day use; and the **Seeded Set**, `model-priority.json`, ranked on capability per dollar from DeepSWE v1.1 and Artificial Analysis figures. `list_models.py` reads the Seeded Set by default and the Opinionated Set with `--recommended`.
2. **Which model the Main Orchestrator runs** — single-select, asked once, only for the `mainOrchestratorHarness` from Round 2, since that is the only Agent Harness with a `mainOrchestrator` slot to fill. The Main Orchestrator runs for the whole Workstream and mostly decides, so it is a separate pick from the Orchestration Worker, which runs one Work Item and mostly writes. No Priority File ranks this slot on its own: offer the file's `orchestrationWorker` entries for that Agent Harness's provider, in file order, top entry **(Recommended)** with the `effort` it names. Every other Agent Harness gets `"mainOrchestrator": null`.
3. **Per Agent Harness from Round 2, three Model Slots** — Orchestration Worker, Subagent, Subagent for simple tasks. The Priority File is the source of truth for every model ordering and suggested Effort Level, keyed by provider (`anthropic`, `github-copilot`, `openai-codex`) and then by Model Slot (`orchestrationWorker`, `subagent`, `subagentSimple`). Offer each slot's entries in file order, top entry **(Recommended)** with the `effort` it names, and repeat the file's `cautions` — the effort-level traps — to the user. Claude Code (`anthropic`) and OpenAI Codex (`openai-codex`) options come straight from the file; GitHub Copilot's are the file's `github-copilot` entries plus free text for anything else the user has access to.
4. **For Pi, Prime Agent, OpenCode and Antigravity, discover the models** — these Agent Harnesses publish what they can run, and the list is too long and changeable to hard-code. Per Agent Harness and slot, run `python3 ${CLAUDE_SKILL_DIR}/scripts/list_models.py [--recommended] <name> <slot>` (`<name>` is `pi`, `prime-agent`, `opencode` or `agy`; `<slot>` is `mainOrchestrator`, `orchestrationWorker`, `subagent` or `subagentSimple`, and `mainOrchestrator` reads the `orchestrationWorker` ranking; pass `--recommended` when question 1 picked the Opinionated Set). It prints `{"harness": ..., "providers": {"<provider>": [{"model": ..., "efforts": [...], "suggestedEffort": ...}]}}`, ranked against the chosen Priority File. Offer models in the order returned, first one **(Recommended)** with its `suggestedEffort`. A model the Priority File does not rank still appears below every ranked one; offer it too, because the Priority File is never a whitelist.
   - **Which provider to use for this Agent Harness** — single-select over the report's `providers` keys, asked first because the model options come from the chosen provider alone.
   - **One model per Model Slot** — single-selects for Orchestration Worker, Subagent and Subagent for simple tasks, plus the Main Orchestrator on the Agent Harness that runs it, options being that provider's `model` values from the run for that slot.

   Antigravity bakes its Effort Level into the model id (`gemini-3.7-flash-high`); `list_models.py` strips the suffix and reports it under `efforts`, so the user picks a base model once. Where a chosen `agy` model has a non-empty `efforts`, ask which one and write the slot as `{"model": ..., "effort": ...}` — that effort is what `agy --effort` receives.
5. **An effort for any slot that should not use the Workstream reasoning level** — per Agent Harness, multi-select over its slots, `Use the workstream reasoning level` **(Recommended)** for each. Where the user picks an effort, ask which of `low`, `medium`, `high`, `xhigh`, `max`, and write that slot as `{"model": ..., "effort": ...}` instead of a plain string. Skip any slot whose effort question 2 or 4 already answered.
6. **An Agent Harness Tier for each selected Agent Harness** — `light` or `standard`, single-select, used later to route Work Items by size.
7. **Maximum concurrency** — free-text number, counting Orchestrator, Subagents, and Nested Subagents together.
8. **Reasoning level for Orchestrator and Subagents** — single-select: Default (medium) **(Recommended)**, Low, Medium, High, X-High, Max.

**Offer to save these as Prompt Settings.** Only where there were no stored settings or the user chose to override them, ask once after every Round 2 and 3 question is answered: **save these selections as this repo's Prompt Settings?** — **Yes (Recommended)** or **No**. On yes, assemble a Prompt Settings object — `harnesses`, `mainOrchestratorHarness`, `targetBranch`, `maxConcurrency`, `reasoningLevel`, `priorityFile`, and nothing Workstream-specific — and pipe it in:

```
echo '<settings JSON>' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_settings.py
```

The script is the validator. On `ok: wrote <path>`, tell the user the path and what was stored. On `FAIL:` lines, show them verbatim, fix the object and re-run — nothing was written. A failed save never blocks the Workstream.

### 4. Settle the scope

This step runs on `grill-with-docs`, which ships outside `orca-helpers`. Find out whether it is installed by invoking it — `Skill(grill-with-docs)` or the Agent Harness equivalent — and let the invocation decide. A listing or filesystem check gives false negatives: a project-local skill in `<cwd>/.claude/skills/` is invocable while absent from your available-skills listing and from `~/.claude/plugins/`.

**When the invocation runs**, let it interview the user until the Scope of Work is settled: every Work Item named, sized (`light` or `standard`) and unambiguous, and every skill it depends on has a decided name and behavior. Let `grill-with-docs` also write or update `CONTEXT.md` glossary entries and ADRs as domain terms and decisions surface.

**When the invocation fails** because the skill is not found, stop, tell the user this verbatim, and wait for them to install it and re-run `orca-prompt`:

> Step 4 needs `grill-with-docs`, one of Matt Pocock's skills. It is in Claude Code's official marketplace, so there is no marketplace to add first — install it with:
>
> ```
> /plugin install mattpocock-skills
> ```

`grill-with-docs` is the only thing that settles the scope, so on this branch steps 5 onward wait until the invocation succeeds.

### 5. Write `_plan.md`

Write `.orca/prompts/<workstream>/_plan.md`:

- The settled Scope of Work from step 4, in prose.
- An `## Orchestration Rules` section with its body left to the scripts. `scripts/render_rules.py` renders the whole block from `_config.json` (Agent Harness Model Slots and tier, maximum concurrency, reasoning level) and holds the one copy of the **Global Rules** in its `GLOBAL_RULES` string; `scaffold.py` injects the rendered block into `_plan.md` and every generated prompt at step 8. Changing a Global Rule means editing that string.
- A `## Work Items` section, one subsection per Work Item, in the shape `scripts/scaffold.py` reads:

  ```markdown
  ### <id>: <title>

  <prose — the specific work>

  **Skills**: skill-one, skill-two
  **Closes**: #12
  **Phase**: 1
  ```

  `<id>` matches a `workItems[].id` in `_config.json`. `**Skills**`, `**Closes**`, and `**Phase**` are each optional (empty, unlinked, and phase 1 when omitted).

### 6. Write `_config.json`

Write `.orca/prompts/<workstream>/_config.json` against the schema below, filled from Rounds 1-3. Every key is present, with `null` or `[]` only where a round genuinely left it unanswered (see the schema notes).

### 7. Propose sizes, then confirm

Propose a size (`light` or `standard`) for every Work Item in `_config.json`'s `workItems[]`, based on its scope in `_plan.md`. Ask the user to confirm or correct each, the proposed size marked **(Recommended)**, and write corrections back into `_config.json` before scaffolding.

### 8. Scaffold the Workstream

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold.py .orca/prompts/<workstream>/`. It reads the Workstream's `_config.json` and `_plan.md`, calls `render_rules.py` itself for the Orchestration Rules block, and writes one `<id>.prompt.md` per Work Item, `_run-order.md`, and `_orchestration.prompt.md` into that directory. To preview the rules block alone, run `python3 ${CLAUDE_SKILL_DIR}/scripts/render_rules.py <path-to-_config.json>`; module docstrings cover the rest.

### 9. Validate, then run or schedule

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/validate.py .orca/prompts/<workstream>/` and show the user the result verbatim. A clean run prints `ok: workstream meets the Definition of Done`; a failing run prints one `FAIL:` line per missing piece and exits non-zero. On failure, fix `_config.json` or `_plan.md` and re-run step 8; the Workstream is ready only after a clean validate.

After a clean validate — and only then, since a Workstream that fails validation is never scheduled — ask: **Run it now (Recommended)** or **Schedule it for later**. On "run it now", stop and report the Workstream ready.

On "schedule it for later", invoke `orca-prompt-scheduler` — `Skill(orca-prompt-scheduler)` or the Agent Harness equivalent — and hand it `.orca/prompts/<workstream>/_orchestration.prompt.md` as the prompt to schedule. That skill owns the time interview, the conflict check and the `orca automations` call, so leave time resolution and the CLI to it.

## `_config.json` schema

The contract every later script in this pattern codes against. Renaming or removing a key means updating every skill that reads it.

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
        "mainOrchestrator": "Model Slot | null — model for the Main Orchestrator session; null on every Agent Harness that does not run it",
        "orchestrationWorker": "Model Slot | null — model for the Orchestration Worker session",
        "subagent": "Model Slot | null — model for ordinary subagents",
        "subagentSimple": "Model Slot | null — model for subagents doing simple tasks"
      }
    }
  ],
  "mainOrchestratorHarness": "string | null — which harnesses[].name runs the Main Orchestrator",
  "reasoningLevel": "default | low | medium | high | xhigh | max",
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

- `harnesses` may hold more than one entry; a Work Item's Agent Harness is chosen by matching its `workItems[].size` against a `harnesses[].tier`.
- A **Model Slot** is either a plain string — `"claude-sonnet-5-5"`, meaning "use the Workstream `reasoningLevel`" — or an object `{"model": "gpt-6-sol", "effort": "high"}` overriding the level for that slot alone. Valid efforts are `low`, `medium`, `high`, `xhigh`, `max`. Scripts read a slot through `render_rules.normalize_model_slot`, which turns either shape into `(model, effort_or_none)`; any third shape is a `FAIL:` from `validate.py`.
- `models.mainOrchestrator` is `null` on every Agent Harness but the one `mainOrchestratorHarness` names, and the key is still required there — `validate.py` reports a missing key as a `FAIL:`, the same as any other slot.
- `models.subagentSimple` may be `null` even when the Agent Harness is fully configured — not every Agent Harness distinguishes a simple-task model (see the Pi rules in any generated `_plan.md`'s Orchestration Rules section, which has no simple-task slot).
- Every key in this schema must exist in a written `_config.json`, even where the value is `null` or `[]`. A missing key means the file was hand-edited or written by something older than this schema — an error to report, not a default to fill in.
