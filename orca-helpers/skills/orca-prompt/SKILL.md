---
name: orca-prompt
description: Start a new Orca Workstream — interviews for its name, target branch, integration, Scope of Work and Definition of Done, then writes _config.json, _plan.md and one prompt per Work Item under .orca/prompts/<workstream>/. Use for "orca-prompt", "new workstream", "plan this as a workstream", or splitting a feature into parallel agent tasks for Orca. To schedule one use orca-prompt-scheduler; for stored defaults, orca-prompt-settings.
---

# orca-prompt

Starts a new Orca Workstream. A **Workstream** is a named body of work that one plan file scopes and one set of generated prompt files delivers, living under `.orca/prompts/<workstream>/`. A full run writes `_config.json` and `_plan.md`, then scaffolds every generated file from them: one prompt file per Work Item and `_orchestration.prompt.md`.

## Track every step

Before Round 1, create one Task per step below with `TaskCreate` (or the Agent Harness todo tool), ten in all, titled by step: `1. Round 1: Basics`, `2. Round 2: Harness`, `3. Round 3: Models`, `4. Round 4: Timing`, `5. Settle the scope`, and so on. Mark each Task `in_progress` with `TaskUpdate` when its step starts and `completed` when it ends. The interview is long, and the list shows the user where it stands. A step that does not apply, such as Rounds 2 and 3 when stored settings are kept, is marked `completed` with a one-line note saying why.

## Drive the Prompt Band

The orca-helpers Prompt Band follows the interview above the prompt, reading `.orca/prompts/_prompt-band.json`. `scripts/set_prompt_band.py` is that file's only writer, and a guard denies a direct Edit or Write of it. Run it at every step start, every answer and every step end, as each step below says; the calls are written `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts <command>`.

- Before Round 1, run `begin` to reset the file, every step upcoming.
- `start <step>` at a step's start, `answer <step> <key> <value>` as each answer lands, `done <step>` at its end. Pass a JSON value for a list, object, number or boolean, and a plain string otherwise.
- `tick <item>` as each Write / Validate checklist item finishes, and `end` once the skill's last step is done.

The band's five steps are `basics` (Round 1), `harness` (Round 2), `models` (Round 3), `timing` (Round 4) and `write-validate` (steps 5-10). A `FAIL:` line from the script never blocks the Workstream: fix the call if you can, and carry on.

The band stays up while a question shows, and stays up after `end` with its finished state. It hides only at a fresh startup or a `/clear`, and comes back with the next write to the file; a resume or a compact keeps it. The `o` hotkey, or the band's caret, collapses it to its top bar, and collapses or expands the Wave band with it.

## The interview always runs

Rounds 1-4 and step 5 run in order, before any file is written, even when the Scope of Work looks small, obvious, or already described earlier in the conversation. The interview exists to surface the gaps and trade-offs the user has not stated, and a scope that reads as complete is not evidence that it is.

The one exception is the invoking message itself saying to skip: "skip the interview", "use the scope I already wrote, no questions". Prior context, an earlier message in the session, an existing scope document, a light-looking workload, and your own read of the scope all leave the interview running. On a valid opt-out, take the **(Recommended)** answer for every unasked question, write them into `_plan.md` under an `Assumed, not asked` heading, and list them in your reply so the user can correct them.

Ask every question with the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent), one answer per question marked **(Recommended)**, so the user can accept a sensible default in one click and only stops to think where the default is wrong.

## Steps

### 1. Round 1: Basics

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts start basics`. After each answer below, run `answer basics <key> <value>` with its key: `workstream`, `targetBranch`, `integration` (the `_config.json` value), `tickets` (`true` or `false`), `scopeFrom` (`interview` or `written`). Run `done basics` after question 5.

1. **Workstream name** — the identifier used for `.orca/prompts/<workstream>/` and inside prompts as `<workstream>`. Recommend a kebab-case name derived from what the user has already said in this conversation; if nothing points to one, ask for free text with no recommendation.
2. **Target branch** — the branch every Work Item's result reaches. Recommend `main` unless the repo's default branch is something else (check `git remote show origin` or `git branch --show-current` on a clean checkout).
3. **Integration** — how each Work Item's result reaches the target branch. It becomes `_config.json` `integration`, and generated prompts name PRs and merges only when it asks for them:
   - **PR + merge (Recommended)** (`pr-merge`) — each worker opens a PR, and the Main Orchestrator merges it.
   - **PR per Work Item** (`pr`) — each worker opens a PR, left open for review.
   - **Branch per Work Item** (`branch`) — each worker pushes its branch, left for review. No PR.
   - **Commit to the target branch** (`commit`) — each worker commits on its branch, and the Main Orchestrator merges it into the target branch with plain `git`. No PR.
4. **Tracker tickets** — whether this Workstream files issues in the project tracker. It becomes `_config.json` `tickets`. **No (Recommended)** writes `false`. **Yes** writes `true` and lets step 6 use `to-spec` and `to-tickets`.
5. **Where the Scope of Work comes from**:
   - **Interview me now (Recommended)** — nothing is settled yet; step 5 interviews the user from scratch.
   - **I already have it written down** — the user points at a file or issue, or pastes it; step 5 sharpens what they gave you instead of starting blank.

### 2. Round 2: Harness

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts start harness`. Its answer keys are `detected` (the JSON list of installed Agent Harness names from `detect_harnesses.py`), `harnesses` (the JSON list of selected `{"name", "tier"}` objects, `tier` added once Round 3 asks it) and `mainOrchestratorHarness`. Run `done harness` when the round ends.

**Stored Prompt Settings.** Before asking anything in this round, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_settings.py --read`. `FAIL: no Prompt Settings at ...` means no settings are stored yet — the ordinary first run, not an error to report — so ask Rounds 2 and 3 in full. Any `FAIL: invalid Prompt Settings` line means the stored file is corrupt: show the lines verbatim and offer to rebuild it.

`--read` ignores a `reasoningLevel` key left from older settings, and gives each plain-string Model Slot the Priority File's suggested effort, so every slot it returns carries an effort where the file names one.

Where it returns settings, check each value before offering it, because a setting valid when written can go stale:

- An Agent Harness in `harnesses[]` that `detect_harnesses.py` (below) no longer reports as installed.
- A Model Slot naming a model the `priorityFile` Priority File does not carry — read that file for the fixed sets (`anthropic`, `openai-codex`); run `list_models.py` for the discovered Agent Harnesses (`pi`, `opencode`, `copilot`, `agy`).

Keep every still-valid setting. Name each broken one to the user with what is wrong, and re-ask that one question alone with the option set Round 2 or Round 3 would have used; the rest of the stored file stays in force.

Before the keep-or-override question, fill both panels from the stored values: `answer harness detected`, `answer harness harnesses`, `answer harness mainOrchestratorHarness`, then `answer models modelSet`, `answer models models` and `answer models maxConcurrency` (keys under Round 3). On keep, run `done harness` and `done models`, so both steps tick to done.

Then show the user what the settings hold — the Agent Harnesses and their tiers, each Model Slot with its effort, the Main Orchestrator Agent Harness, target branch, maximum concurrency, Priority File — and ask:

- **Use these settings for this Workstream (Recommended)** — every stored value becomes this Workstream's answer; skip Rounds 2 and 3 and go to Round 4.
- **Override them for this Workstream** — ask Rounds 2 and 3 in full, offering each stored value as that question's **(Recommended)** answer.

Round 1's target branch wins either way: it was asked for this Workstream, so a stored `targetBranch` never overrides it.

**The questions.** Run `python3 ${CLAUDE_SKILL_DIR}/scripts/detect_harnesses.py` (stdlib Python, no args). Its JSON reports which of the six known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `agy`) are on PATH, already in the priority order `data/model-priority.json` sets — offer them in exactly that order.

1. **Which Agent Harnesses to use for this Workstream** — multi-select over every installed Agent Harness, plus a free-text path where the user types the name and CLI command of an Agent Harness the probe missed. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select over the same option set, asked independently of question 1. This is a separate decision from being a worker Agent Harness: the Main Orchestrator drives dispatch, integrates each Work Item's result as `integration` says, and owns the worktree lifecycle. If the answer is not in question 1's selection, add it to the Agent Harness list — the Main Orchestrator's Agent Harness always needs an entry.

### 3. Round 3: Models

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts start models`. Its answer keys are `modelSet` (`opinionated` or `seeded`, after question 1), `models` (a JSON object of Agent Harness name to its `models` object, re-sent as each Model Slot and effort lands) and `maxConcurrency` (a number). After question 6, re-send `answer harness harnesses` with each tier. Run `done models` once the save offer below is settled.

1. **Which Priority File this Workstream ranks models against** — single-select, asked first because questions 2-4 all read the file it picks. Two ship in `${CLAUDE_SKILL_DIR}/data/`: the **Opinionated Set (Recommended)**, `recommended-priority.json`, ranked by hand from day-to-day use; and the **Seeded Set**, `model-priority.json`, ranked on capability per dollar from DeepSWE v1.1 and Artificial Analysis figures. `list_models.py` reads the Seeded Set by default and the Opinionated Set with `--recommended`.
2. **Which model the Main Orchestrator runs** — single-select, asked once, only for the `mainOrchestratorHarness` from Round 2, since that is the only Agent Harness with a `mainOrchestrator` slot to fill. The Main Orchestrator runs for the whole Workstream and mostly decides, so it is a separate pick from the Orchestration Worker, which runs one Work Item and mostly writes. No Priority File ranks this slot on its own: offer the file's `orchestrationWorker` entries for that Agent Harness's provider, in file order, top entry **(Recommended)** with the `effort` it names. Every other Agent Harness gets `"mainOrchestrator": null`.
3. **Per Agent Harness from Round 2, three Model Slots** — Orchestration Worker, Subagent, Subagent for simple tasks. The Priority File is the source of truth for every model ordering and suggested Effort Level, keyed by provider (`anthropic`, `github-copilot`, `openai-codex`) and then by Model Slot (`orchestrationWorker`, `subagent`, `subagentSimple`). Offer each slot's entries in file order, top entry **(Recommended)** with the `effort` it names, and repeat the file's `cautions` — the effort-level traps — to the user. Claude Code (`anthropic`) and OpenAI Codex (`openai-codex`) options come straight from the file; GitHub Copilot's come from question 4.
4. **For Pi, OpenCode, GitHub Copilot and Antigravity, discover the models** — these Agent Harnesses publish what they can run, and the list is too long and changeable to hard-code. Per Agent Harness and slot, run `python3 ${CLAUDE_SKILL_DIR}/scripts/list_models.py [--recommended] <name> <slot>` (`<name>` is `pi`, `opencode`, `copilot` or `agy`; `<slot>` is `mainOrchestrator`, `orchestrationWorker`, `subagent` or `subagentSimple`, and `mainOrchestrator` reads the `orchestrationWorker` ranking; pass `--recommended` when question 1 picked the Opinionated Set). It prints `{"harness": ..., "providers": {"<provider>": [{"model": ..., "efforts": [...], "suggestedEffort": ...}]}}`, ranked against the chosen Priority File. Offer models in the order returned, first one **(Recommended)** with its `suggestedEffort`. A model the Priority File does not rank still appears below every ranked one; offer it too, because the Priority File is never a whitelist.
   - **Which provider to use for this Agent Harness** — single-select over the report's `providers` keys, asked first because the model options come from the chosen provider alone.
   - **One model per Model Slot** — single-selects for Orchestration Worker, Subagent and Subagent for simple tasks, plus the Main Orchestrator on the Agent Harness that runs it, options being that provider's `model` values from the run for that slot.

   GitHub Copilot has no list command, so `list_models.py` reads the `model` choices from `copilot help config` and reports them under `github-copilot`. When that finds nothing, it returns the Priority File's `github-copilot` entries instead.

   Antigravity bakes its Effort Level into the model id (`gemini-3.8-flash-high`); `list_models.py` strips the suffix and reports it under `efforts`, so the user picks a base model once and never sees two entries differing only by effort.
5. **An effort for every filled Model Slot** — single-select per slot, right after its model is picked. Offer only the Effort Levels (`max`, `xhigh`, `high`, `medium`, `low`) that the slot's Agent Harness and model support, because a level the model lacks is either rejected or ignored by its CLI. Take the supported set from `list_models.py`'s `efforts` where it is non-empty, and otherwise from the efforts the Priority File lists for that model. Mark the Priority File's suggested effort **(Recommended)**. Write the slot as `{"model": ..., "effort": ...}`. A model the Priority File lists with `"effort": null` takes no effort: skip the question and write the slot as a plain string. For `agy`, the chosen effort is what `agy --effort` receives.
6. **An Agent Harness Tier for each selected Agent Harness** — `light` or `standard`, single-select, used later to route Work Items by size.
7. **Maximum concurrency** — free-text number, counting Orchestrator, Subagents, and Nested Subagents together.

Ask no Workstream-wide reasoning or effort question. Effort lives only on the Model Slot, and question 5 has already set it per slot.

**Offer to save these as Prompt Settings.** Only where there were no stored settings or the user chose to override them, ask once after every Round 2 and 3 question is answered: **save these selections as this repo's Prompt Settings?** — **Yes (Recommended)** or **No**. On yes, assemble a Prompt Settings object — `harnesses`, `mainOrchestratorHarness`, `targetBranch`, `maxConcurrency`, `priorityFile`, and nothing Workstream-specific — and pipe it in:

```
echo '<settings JSON>' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_settings.py
```

The script is the validator. On `ok: wrote <path>`, tell the user the path and what was stored. On `FAIL:` lines, show them verbatim, fix the object and re-run — nothing was written. A failed save never blocks the Workstream.

### 4. Round 4: Timing

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts start timing`. Its answer keys are `mode` (`now` or `later`), and for `later` the confirmed `localTime`, `timezone` and `utcTime`. Run `done timing` once the answer is recorded.

Ask when the Workstream runs, now, so the answer is settled before the scope interview and the Prompt Band can show it:

- **Run it now (Recommended)** — go to step 5.
- **Schedule it for later** — resolve the time in this round. Ask for the Time Phrase as free text ("1AM on September 2nd", "tomorrow 09:30") and the IANA timezone, recommending the machine's own. Turn the phrase into a concrete local datetime and run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-scheduler/scripts/resolve_schedule.py '<YYYY-MM-DD HH:MM>' <IANA timezone>`. On `FAIL:` lines, show them verbatim and re-ask. Show the resolved local and UTC times and have the user confirm them.

Record the answer and the confirmed time. Nothing is scheduled here: step 10 creates the automation, and only after a clean validate.

### 5. Settle the scope

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts start write-validate`; it stays the active band step through step 10. Run `tick scope` once the user confirms the settled scope.

Step 5 interviews the user until the Scope of Work and the Workstream Definition of Done are settled. Settled means every Work Item is named, sized (`light` or `standard`), placed in a Wave and unambiguous, every skill it depends on has a decided name and behavior, and the **Workstream Definition of Done** is a short list of checks someone can run or observe.

**Try `grill-with-docs` first.** Invoke it with `Skill(grill-with-docs)` or the Agent Harness equivalent, and let the invocation decide whether it runs. A listing or filesystem check gives false negatives: a project-local skill in `<cwd>/.claude/skills/` is invocable while absent from your available-skills listing. When it runs, let it interview the user and write `CONTEXT.md` glossary entries and ADRs as terms and decisions surface. When it ends, ask any Definition of Done question it left open, with a **(Recommended)** answer.

**On any refusal, run the built-in procedure.** Read `${CLAUDE_SKILL_DIR}/references/grilling.md` and follow it from the top. A refusal is any invocation that does not start the skill: not found, `disable-model-invocation: true`, a permission denial, or any other error. Tell the user in one line which refusal happened and that the built-in grilling procedure is running instead. Do not ask the user to install anything, and do not stop.

Either path ends the same way: the user confirms the settled scope and the Workstream Definition of Done before step 6 starts.

### 6. Write `_plan.md`

Write `.orca/prompts/<workstream>/_plan.md`:

- The settled Scope of Work from step 5, in prose.
- A `## Definition of Done` section holding the Workstream Definition of Done from step 5, followed by an `**Integration**:` line that says in words what Round 1's `integration` answer means for this Workstream. `scaffold.py` copies this section into `_orchestration.prompt.md`, so the Main Orchestrator checks it before it reports the Workstream done.
- An `## Orchestration Rules` section with its body left to the scripts. `scripts/render_rules.py` renders the whole block from `_config.json` (Agent Harness Model Slots with their efforts and tier, maximum concurrency, integration) and holds the one copy of the **Global Rules** in its `GLOBAL_RULES` string; `scaffold.py` replaces that section's body in `_plan.md` with the rendered block, appending the section when it is absent, and copies the block into every generated prompt at step 9. Changing a Global Rule means editing that string.
- A `## Work Items` section, one subsection per Work Item, in the shape `scripts/scaffold.py` reads:

  ```markdown
  ### <id>: <title>

  <prose — the specific work>

  **Definition of Done**: what must hold for this Work Item to be complete
  **Skills**: skill-one, skill-two
  **Closes**: #12
  **Wave**: 1
  ```

  `<id>` matches a `workItems[].id` in `_config.json`. Write a `**Definition of Done**` for every Work Item yourself: derive it from the Workstream Definition of Done, naming the checks this Work Item's share of the work must pass. Add the integration step to it only when `integration` asks for one, for example "a PR into `main` is open" for `pr` or `pr-merge`; for `commit` and `branch` it names no PR. The other field lines are optional: `**Skills**` falls back to none, `**Closes**` to no linked issue, and `**Wave**` to Wave 1. scaffold.py still writes a generic Definition of Done when the line is missing, and still reads `**Phase**: N` as `**Wave**: N`, so older plans scaffold.

**Tracker tickets are opt-in.** When `tickets` is `false`, do not invoke `to-spec` or `to-tickets`. Fill `**Closes**` only with issues the user already named. When `tickets` is `true`, offer once to file the Work Items: **File one ticket per Work Item (Recommended)** or **Skip**. On yes, invoke `to-spec` and then `to-tickets`, or the Agent Harness equivalents, and write each returned issue into its Work Item's `**Closes**` line. If either skill refuses to run, tell the user in one line and continue without tickets. A missing ticket skill never blocks the Workstream.

### 7. Write `_config.json`

Write `.orca/prompts/<workstream>/_config.json` against the schema below, filled from Rounds 1-3. `integration` and `tickets` come from Round 1. Every key is present, with `null` or `[]` only where a round genuinely left it unanswered (see the schema notes). Then run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts tick plan-config`.

### 8. Propose sizes, then confirm

Propose a size (`light` or `standard`) for every Work Item in `_config.json`'s `workItems[]`, based on its scope in `_plan.md`. Skip this step when the user already confirmed every size in step 5. Otherwise ask the user to confirm or correct each, the proposed size marked **(Recommended)**, and write corrections back into `_config.json` before scaffolding. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts tick sizes` when sizes are settled, skipped or not.

### 9. Scaffold the Workstream

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold.py .orca/prompts/<workstream>/`. It reads the Workstream's `_config.json` and `_plan.md`, calls `render_rules.py` itself for the Orchestration Rules block, and writes one `<id>.prompt.md` per Work Item and `_orchestration.prompt.md` into that directory. It writes each Work Item's `wave` and `title` back into `_config.json` and the rendered Orchestration Rules into `_plan.md`. To preview the rules block alone, run `python3 ${CLAUDE_SKILL_DIR}/scripts/render_rules.py <path-to-_config.json>`; module docstrings cover the rest. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts tick scaffold` once it succeeds.

### 10. Validate, then run or schedule

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/validate.py .orca/prompts/<workstream>/` and show the user the result verbatim. A clean run prints `ok: workstream meets the Definition of Done`; a failing run prints one `FAIL:` line per missing piece and exits non-zero. On failure, fix `_config.json` or `_plan.md` and re-run step 9; the Workstream is ready only after a clean validate. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts tick validate` on the clean run.

Act on the Round 4 answer only after a clean validate, because a Workstream that fails validation must never be scheduled. Ask nothing new about timing.

- **Run it now**: stop and report the Workstream ready.
- **Schedule it for later**: invoke `orca-prompt-scheduler` — `Skill(orca-prompt-scheduler)` or the Agent Harness equivalent. Hand it `.orca/prompts/<workstream>/_orchestration.prompt.md` as the prompt to schedule, plus the time and timezone the user confirmed in Round 4, so its time step confirms that time instead of asking afresh. That skill owns the conflict check and the `orca automations` call, so leave the CLI to it.

This is the skill's last step. When it is done, run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts done write-validate` and then `end`, which stops the band's checkered flag.

## `_config.json` schema

The contract every later script in this pattern codes against. Renaming or removing a key means updating every skill that reads it.

```json
{
  "workstream": "string — the workstream name, matches the .orca/prompts/<workstream>/ directory",
  "targetBranch": "string — branch every Work Item's result reaches, by the route `integration` names",
  "harnesses": [
    {
      "name": "string — Agent Harness identifier: claude | opencode | copilot | codex | pi | agy | <other>",
      "cli": "string — the CLI command to invoke this Agent Harness (only needed when name is not one of the six built-ins)",
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
  "maxConcurrency": "number | null — ceiling counting Orchestrator, Subagents, and Nested Subagents combined",
  "integration": "commit | branch | pr | pr-merge — how each Work Item's result reaches targetBranch",
  "tickets": "boolean — whether the Workstream files tracker tickets",
  "workItems": [
    {
      "id": "string — matches the work item prompt filename, e.g. 01-skill-skeleton",
      "size": "light | standard",
      "wave": "number — the Work Item's Wave, written by scaffold.py from _plan.md",
      "title": "string — the Work Item's title, written by scaffold.py from _plan.md"
    }
  ]
}
```

Notes for the scripts that read this file:

- `harnesses` may hold more than one entry; a Work Item's Agent Harness is chosen by matching its `workItems[].size` against a `harnesses[].tier`. With no exact match, the Agent Harness with the nearest tier takes it.
- `integration` sets each Work Item's Definition of Done and the Main Orchestrator's per-worker steps. `commit`: the worker commits on its branch and the Main Orchestrator merges that branch into `targetBranch`. `branch`: the worker pushes its branch, left for review. `pr`: the worker opens a PR, left for review. `pr-merge`: the worker opens a PR and the Main Orchestrator merges it. Generated prompts name PRs only for `pr` and `pr-merge`, and merges only for `commit` and `pr-merge`.
- `tickets` is `false` unless the user opts in. When `true`, step 6 may file Work Items with `to-spec` / `to-tickets`, and the Main Orchestrator may file new tickets with them from PR feedback. When `false`, nothing invokes either skill.
- `workItems[].wave` and `title` come from `_plan.md`; `scaffold.py` writes them, and `validate.py` reports a Work Item missing either. Wave N's Tasks are created with `task-create --deps` naming every Task of Wave N-1.
- A **Model Slot** is either an object `{"model": "gpt-6.1-sol", "effort": "high"}` or a plain string `"<model-id>"` for a model that takes no effort. Round 3 writes the object form wherever the model takes an effort. There is no Workstream-wide effort: an older `_config.json` that still holds `reasoningLevel` is read with the key ignored. Valid efforts are `low`, `medium`, `high`, `xhigh`, `max`. Scripts read a slot through `render_rules.normalize_model_slot`, which turns either shape into `(model, effort_or_none)`; any third shape is a `FAIL:` from `validate.py`.
- `models.mainOrchestrator` is `null` on every Agent Harness but the one `mainOrchestratorHarness` names, and the key is still required there — `validate.py` reports a missing key as a `FAIL:`, the same as any other slot.
- `models.subagentSimple` may be `null` even when the Agent Harness is fully configured — not every Agent Harness distinguishes a simple-task model (see the Pi rules in any generated `_plan.md`'s Orchestration Rules section, which has no simple-task slot).
- Every key in this schema must exist in a written `_config.json`, even where the value is `null` or `[]`. A missing key means the file was hand-edited or written by something older than this schema — an error to report, not a default to fill in.

## `_status.json` schema

`.orca/prompts/<workstream>/_status.json` holds the live state of each Work Item, and the orca-helpers Wave band reads it. `scripts/set_status.py` is its only writer: run it for every change, so each write is atomic and stays in schema. `--start` builds the file from `_config.json` and marks this Workstream active, `<id> <state> [reason]` moves one Work Item, `<id> complete --pr <n>` also records its PR, `--stop` clears `active`, and `--show` prints the Wave-by-Wave table. A bad id or state prints a `FAIL:` line, exits non-zero and leaves the file as it was.

```json
{
  "workstream": "string — the workstream name from _config.json",
  "active": "boolean — true while the Wave band draws this Workstream; --start sets it and clears it on every sibling Workstream",
  "updatedAt": "string — ISO 8601 UTC time of the last write",
  "startedAt": "string | null — ISO 8601 UTC time the run started; a resumed --start keeps it, a finished run that reopens gets a fresh one",
  "finishedAt": "string | null — ISO 8601 UTC time of the write that made every item complete, cleared when a finished run reopens",
  "items": [
    {
      "id": "string — matches workItems[].id in _config.json",
      "title": "string — the Work Item title shown in the band",
      "wave": "number — the Wave the item belongs to, starting at 1",
      "state": "todo | in_progress | complete | failed",
      "reason": "string | null — why it failed; null in every other state",
      "harness": "string | null — the Agent Harness name dispatch routes the item to, from its size by the same tier rule; null without size or harnesses",
      "pr": "number | null — the PR number from `<id> complete --pr <n>`; null until set"
    }
  ]
}
```

`items` keeps the `_config.json` order. `--start` needs `wave` and `title` on every `workItems[]` entry, and re-running it keeps the state of items already in the file and each `pr`. One rule sets the clock, for `--start` and for a state change alike. A finished run that has an item not complete gets a fresh `startedAt` and a cleared `finishedAt`. Otherwise `startedAt` is kept, and `finishedAt` is stamped once every item is complete. Those three keys are optional, so a `_status.json` written before them still reads, and it keeps `startedAt` null rather than inventing one.

## `_prompt-band.json` schema

`.orca/prompts/_prompt-band.json` holds the live state of the orca-prompt interview, and the orca-helpers Prompt Band reads it. `scripts/set_prompt_band.py` is its only writer (see Drive the Prompt Band). `start` marks any other active step complete, so at most one step is active. `done` leaves `step` alone, so the band holds the finished step until the next `start`. A bad step, key or item prints a `FAIL:` line, exits non-zero and leaves the file as it was.

```json
{
  "step": "string | null — the active step id; null until the first start",
  "ended": "boolean — true once the skill finished its last step",
  "updatedAt": "string — ISO 8601 UTC time of the last write",
  "steps": [
    {
      "id": "basics | harness | models | timing | write-validate",
      "title": "string — Basics, Harness, Models, Timing, Write / Validate",
      "state": "upcoming | active | complete",
      "answers": "object — answer key -> value, filled as the user answers"
    }
  ],
  "checklist": [
    {
      "id": "scope | plan-config | sizes | scaffold | validate",
      "title": "string — Settle the Scope, Write the Plan & Config, Propose Sizes, Scaffold the Workstream, Validate",
      "done": "boolean"
    }
  ]
}
```

`steps` and `checklist` keep the order above. Answer keys per step: `basics` takes `workstream`, `targetBranch`, `integration`, `tickets`, `scopeFrom`; `harness` takes `detected`, `harnesses`, `mainOrchestratorHarness`; `models` takes `modelSet`, `models`, `maxConcurrency`; `timing` takes `mode`, `localTime`, `timezone`, `utcTime`; `write-validate` takes none.
