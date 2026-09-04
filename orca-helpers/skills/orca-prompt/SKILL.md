---
name: orca-prompt
description: Start a new Orca workstream — interviews for the workstream name, target branch and Scope of Work, then writes _config.json, _plan.md and one prompt file per work item under .orca/prompts/<workstream>/. Use when the user wants to start a new workstream, plan or generate work item prompts for Orca orchestration, or says "orca-prompt", "new workstream", "plan this as a workstream".
---

# orca-prompt

Starts a new Orca workstream. A **Workstream** is a named body of work that one plan file scopes and one set of generated prompt files delivers, living under `.orca/prompts/<workstream>/`. A full run writes `_config.json` and `_plan.md`, then scaffolds every generated file from them: one prompt file per work item, `_run-order.md`, and `_orchestration.prompt.md`.

## Non-negotiable

This skill is an interview. Rounds 1-3 and Step 4 always run, in order, before any file is written — including when the Scope of Work looks small, obvious, or already described earlier in the conversation. The interview exists to surface the gaps and trade-offs the user has not stated; a scope that reads as complete is not evidence that it is.

Skip only when the message that invoked this skill says to skip — "skip the interview", "use the scope I already wrote, no questions". That message is the only thing that counts: prior context, an earlier message in the session, an existing scope document, a workload that looks light, and your own judgement all leave the interview running.

On a valid opt-out, take the **(Recommended)** answer for every unasked question, write them into `_plan.md` under an `Assumed, not asked` heading, and list them in your reply so the user can correct them.

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

**Stored Prompt Settings first.** Run `python3 orca-helpers/skills/orca-prompt-settings/scripts/write_settings.py --read` before asking anything in this round. A `FAIL:` line means there are no stored settings yet — the ordinary first run, not an error to report to the user. Skip to the questions below and ask Rounds 2 and 3 in full.

Where it returns settings, show the user what they hold — the Agent Harnesses and their tiers, the Main Orchestrator Agent Harness, target branch, maximum concurrency, reasoning level, Priority File — and ask one question with the Agent Harness question tool:

- **Use these settings for this Workstream** **(Recommended)** — every stored value becomes this Workstream's answer, Rounds 2 and 3 are not asked, and the run goes straight to step 4.
- **Override them for this Workstream** — ask Rounds 2 and 3 in full, offering each stored value as that question's **(Recommended)** answer.

Round 1's target branch answer wins either way: it was asked for this Workstream, so a stored `targetBranch` never overrides it.

**Check the stored settings before offering them.** A setting valid when it was written can go stale:

- An Agent Harness in `harnesses[]` that `detect_harnesses.py` no longer reports as installed.
- A Model Slot naming a model the Priority File `priorityFile` points at does not carry — read that file for the fixed sets (`anthropic`, `github-copilot`, `openai-codex`), run `list_models.py` for the discovered Agent Harnesses (`pi`, `prime-agent`, `opencode`, `agy`).

Keep every still-valid setting. Name each broken one to the user with what is wrong with it, and re-ask that one question alone, with the same option set Round 2 or Round 3 would have used. Do not discard the file, and do not fall back to the full interview because one value went stale.

Run `orca-helpers/skills/orca-prompt/scripts/detect_harnesses.py` (stdlib Python, no args) and read its JSON report of which of the seven known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `prime-agent`, `agy`) are on PATH. The report already comes back in the priority order `data/model-priority.json` sets, so offer the installed Agent Harnesses in the order it lists them — do not re-sort and do not re-rank them yourself.

Ask, with the Agent Harness question tool, one recommended answer marked **(Recommended)**:

1. **Which Agent Harnesses to use for this workstream** — multi-select, options are every Agent Harness the probe found installed, plus a free-text path: the user types a name and the CLI command for an Agent Harness the probe missed. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select, same option set as question 1 (installed Agent Harnesses plus free text), asked independently so it never depends on question 1's answer. This is a separate decision from being a worker Agent Harness: the Main Orchestrator merges PRs, drives dispatch, and owns the worktree lifecycle. If the answer isn't already in question 1's selection, add it to the Agent Harness list — the orchestrator's Agent Harness always needs an entry.

### 3. Round 3: models, tier, concurrency, reasoning

Ask, with the Agent Harness question tool, one recommended answer marked **(Recommended)** per question:

1. **Which Priority File this Workstream ranks models against** — single-select, asked before any model question because questions 2, 3 and 4 all read the file it picks. Two ship in `orca-helpers/skills/orca-prompt/data/`: the **Opinionated Set** **(Recommended)**, `recommended-priority.json`, ranked by hand from day-to-day use; and the **Seeded Set**, `model-priority.json`, ranked on capability per dollar from DeepSWE v1.1 and Artificial Analysis figures. The Seeded Set is what `list_models.py` reads by default; the Opinionated Set is what `list_models.py --recommended` reads.
2. **Which model the Main Orchestrator runs** — single-select, asked once and only for the Agent Harness Round 2 picked as `mainOrchestratorHarness`, since that is the only Agent Harness with a `mainOrchestrator` slot to fill. The Main Orchestrator runs for the whole Workstream and mostly decides, so it is a separate pick from the Orchestration Worker that runs one work item and mostly writes. No Priority File ranks this slot on its own: offer the file's `orchestrationWorker` entries for that Agent Harness's provider, in file order, top entry **(Recommended)** with the `effort` it names. Every other Agent Harness gets `"mainOrchestrator": null`.
3. **Per Agent Harness selected in Round 2**, three Model Slots — Orchestration Worker, Subagent, Subagent for simple tasks. Every model ordering and its suggested Effort Level lives in the priority file question 1 chose, keyed by provider (`anthropic`, `github-copilot`, `openai-codex`) and then by Model Slot (`orchestrationWorker`, `subagent`, `subagentSimple`) — read that file for the options — it is the source of truth, and this prose only says where to look — and offer each slot's options in the order it lists them, top entry marked **(Recommended)** with the `effort` it names. Its `cautions` array holds the effort-level traps worth repeating to the user. Claude Code (`anthropic`) and OpenAI Codex (`openai-codex`) have small known sets, so their options come straight from the file; GitHub Copilot's option list is the file's `github-copilot` entries plus free-form text for anything else the user has access to.
4. **For Pi, Prime Agent, OpenCode and Antigravity**, discover the models instead of guessing them — these Agent Harnesses publish what they can run, and the list is too long and too changeable to hard-code. Per Agent Harness, run `orca-helpers/skills/orca-prompt/scripts/list_models.py [--recommended] <name> <slot>` (`pi`, `prime-agent`, `opencode`, `agy`; slot is `mainOrchestrator`, `orchestrationWorker`, `subagent` or `subagentSimple`, and `mainOrchestrator` reads the `orchestrationWorker` ranking) and read its JSON: `{"harness": ..., "providers": {"<provider>": [{"model": ..., "efforts": [...], "suggestedEffort": ...}]}}`. The script ranks the live model list against the priority file question 1 chose for that slot — pass `--recommended` when question 1 picked the Opinionated Set. Offer the models in the order it returns them and mark the first **(Recommended)** with its `suggestedEffort`. A model the priority file does not know still appears, below every ranked one — offer it too, never drop it.
   - **Which provider to use for this Agent Harness** — single-select over the report's `providers` keys, one question per Agent Harness. Ask it first: the model question's options come from the chosen provider alone.
   - **One model per Model Slot** — three single-selects (Orchestration Worker, Subagent, Subagent for simple tasks), options being that provider's `model` values from the run for that slot, plus a fourth for the Main Orchestrator on the Agent Harness that runs it.

   Antigravity bakes its Effort Level into the model id (`gemini-3.7-flash-high`); `list_models.py` strips the suffix and reports it under `efforts`, so the user picks a base model once and never sees two entries differing only by effort. Where a chosen `agy` model has a non-empty `efforts`, ask which one and write the slot as `{"model": ..., "effort": ...}` — that effort is what `agy --effort` receives.
5. **An effort for any slot that should not use the Workstream reasoning level** — per Agent Harness, multi-select over that Agent Harness's slots, `Use the workstream reasoning level` (Recommended) for each. Where the user picks an effort, ask which of `low`, `medium`, `high`, `xhigh`, `max`, and write that slot as `{"model": ..., "effort": ...}` instead of a plain string. Skip a slot whose effort question 2 or 4 already answered.
6. **An Agent Harness Tier for each selected Agent Harness** — `light` or `standard`, single-select, used later to route work items by size.
7. **Maximum concurrency** — free-text number, counting Orchestrator, Subagents, and Nested Subagents together.
8. **Reasoning level for Orchestrator and Subagents** — single-select: Default (medium) (Recommended), Low, Medium, High, X-High, Max.

**Offer to save these selections as Prompt Settings.** Ask once, after every Round 2 and Round 3 question is answered, and only where there were no stored settings or the user chose to override them: **save these selections as this repo's Prompt Settings?**, **Yes (Recommended)** or **No**. On yes, assemble the answers into a Prompt Settings object — `harnesses`, `mainOrchestratorHarness`, `targetBranch`, `maxConcurrency`, `reasoningLevel`, `priorityFile`, and nothing Workstream-specific — and pipe it in:

```
echo '<settings JSON>' | python3 orca-helpers/skills/orca-prompt-settings/scripts/write_settings.py
```

The script is the validator. On `ok: wrote <path>`, tell the user the path and what was stored; on `FAIL:` lines, show them verbatim, fix the object and re-run — nothing was written, and a failed save never blocks the Workstream.

### 4. Settle the scope

This step runs on `grill-with-docs`, which ships outside `orca-helpers`. Test for it by invoking it, not by looking for it: call `Skill(grill-with-docs)` (or the Agent Harness equivalent) and let the invocation decide. A project-local skill in `<cwd>/.claude/skills/` is invocable while being absent from your available-skills listing and from `~/.claude/plugins/`, so a listing check or a filesystem probe reports an installed skill as missing.

**When the invocation runs**, let it interview the user until the Scope of Work is fully settled: every work item named, sized (`light` or `standard`), and unambiguous, every skill it depends on has a decided name and behavior. `grill-with-docs` also produces or updates `CONTEXT.md` glossary entries and ADRs as domain terms and decisions surface — let it.

**When the invocation itself fails** — the skill is not found — stop here, tell the user this verbatim, and wait for them to install it and re-run `orca-prompt`:

> Step 4 needs `grill-with-docs`, one of Matt Pocock's skills. It is in Claude Code's official marketplace, so there is no marketplace to add first — install it with:
>
> ```
> /plugin install mattpocock-skills
> ```

`grill-with-docs` is the only thing that settles the scope. Waiting for the install is the whole behavior of this branch — steps 5 onward stay unrun until the invocation succeeds.

### 5. Write `_plan.md`

Write `.orca/prompts/<workstream>/_plan.md`:

- The settled Scope of Work from step 4, in prose.
- An `## Orchestration Rules` section — leave its body to the scripts. `scripts/render_rules.py` renders the whole block from `_config.json` (Agent Harness model slots and tier, maximum concurrency, reasoning level) and holds the one copy of the **Global Rules** in its `GLOBAL_RULES` string; `scaffold.py` injects the rendered block into `_plan.md` and into every generated prompt at step 8. Changing a Global Rule means editing that string.
- A `## Work Items` section, one subsection per work item, in the shape `scripts/scaffold.py` reads:

  ```markdown
  ### <id>: <title>

  <prose — the specific work>

  **Skills**: skill-one, skill-two
  **Closes**: #12
  **Phase**: 1
  ```

  `<id>` matches a `workItems[].id` in `_config.json`. `**Skills**`, `**Closes**`, and `**Phase**` are each optional (empty, unlinked, and phase 1 when omitted).

### 6. Write `_config.json`

Write `.orca/prompts/<workstream>/_config.json` against the schema below, filled from Rounds 1–3's answers. Every key must be present — `null` or `[]` only where a round genuinely left it unanswered (e.g. `models.subagentSimple` for an Agent Harness with no simple-task slot) — since every downstream script treats a missing key as an error, not a default to fill in.

### 7. Propose sizes, then confirm

Propose a size (`light` or `standard`) for every work item in `_config.json`'s `workItems[]`, based on its scope in `_plan.md`. Ask the user to confirm or correct each one with the Agent Harness question tool, the proposed size marked **(Recommended)**. Write any corrections back into `_config.json` before scaffolding.

### 8. Scaffold the workstream

Run `scripts/render_rules.py` and `scripts/scaffold.py` (see their module docstrings) against the workstream's `_config.json` and `_plan.md`. This writes one `<id>.prompt.md` per work item, `_run-order.md`, and `_orchestration.prompt.md` into `.orca/prompts/<workstream>/`.

### 9. Validate

Run `scripts/validate.py <workstream-dir>` (see its module docstring) and show the user the result verbatim. A clean run prints `ok: workstream meets the Definition of Done`; a failing run prints one `FAIL:` line per missing piece and exits non-zero — fix `_config.json` or `_plan.md` and re-run step 8 before reporting the workstream ready.

**Then ask whether to run this Workstream now or schedule it.** Only after a clean validate — a Workstream that fails validation is never scheduled. Single-select with the Agent Harness question tool: **Run it now** **(Recommended)** or **Schedule it for later**. On "run it now", stop here and report the Workstream ready.

On "schedule it for later", invoke `orca-prompt-scheduler` — `Skill(orca-prompt-scheduler)` or the Agent Harness equivalent — and hand it `.orca/prompts/<workstream>/_orchestration.prompt.md` as the prompt to schedule. That skill owns the time interview, the conflict check and the `orca automations` call; do not resolve times or touch the CLI here.

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

- `harnesses` may hold more than one entry; a work item's Agent Harness is chosen by matching its `workItems[].size` against a `harnesses[].tier`.
- A **Model Slot** is either a plain string — `"claude-sonnet-5"`, meaning "use the Workstream `reasoningLevel`" — or an object `{"model": "gpt-5.6-sol", "effort": "high"}` overriding the level for that slot alone. Valid efforts are `low`, `medium`, `high`, `xhigh`, `max`. Scripts read a slot through `render_rules.normalize_model_slot`, which turns either shape into `(model, effort_or_none)`; any third shape is a `FAIL:` from `validate.py`.
- `models.mainOrchestrator` is `null` on every Agent Harness but the one `mainOrchestratorHarness` names, and the key is still required there — `validate.py` reports a missing key as a `FAIL:`, the same as any other slot.
- `models.subagentSimple` may be `null` even when the Agent Harness is fully configured — not every Agent Harness distinguishes a simple-task model (see the Pi rules in any generated `_plan.md`'s Orchestration Rules section, which has no simple-task slot).
- Every key in this schema must exist in a written `_config.json`, even where the value is `null` or `[]`. A script encountering a missing key means the file was hand-edited or written by something older than this schema — treat that as an error, not a default to silently fill in.
