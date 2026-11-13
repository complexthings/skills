---
name: orca-prompt
description: Start a new Orca Workstream — interviews for its name, target branch, integration, Scope of Work and Definition of Done, then writes _config.json, _plan.md and one prompt per Work Item under .orca/prompts/<workstream>/. Use for "orca-prompt", "new workstream", "plan this as a workstream", or splitting a feature into parallel agent tasks for Orca. To schedule one use orca-prompt-scheduler; for stored defaults, orca-prompt-settings.
---

# orca-prompt

Starts a new Orca Workstream. A **Workstream** is a named body of work that one plan file scopes and one set of generated prompt files delivers, living under `.orca/prompts/<workstream>/`. A full run writes `_config.json` and `_plan.md`, then scaffolds every generated file from them: one prompt file per Work Item and `_orchestration.prompt.md`.

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment.

## Track every step

Before Round 1, create one Task per step below with `TaskCreate` (or the Agent Harness todo tool), eleven in all, titled by step: `1. Round 1: Basics`, `2. Round 2: Harness`, `3. Round 3: Models`, `4. Round 4: Timing`, `5. Settle the scope`, and so on. Mark each Task `in_progress` with `TaskUpdate` when its step starts and `completed` when it ends. The interview is long, and the list shows the user where it stands. A step that does not apply, such as Rounds 2 and 3 when stored settings are kept, is marked `completed` with a one-line note saying why.

## Drive the Prompt Band

Before Round 1, read `${CLAUDE_SKILL_DIR}/references/prompt-band.md` and run `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts begin`. That file holds the band's commands, each step's answer keys and the `_prompt-band.json` schema. Each step below names its band calls, written as the command after `.orca/prompts`.

## Recall earlier Workstreams

When the context holds an `Orca Knowledge Graph recall` block, the orca-helpers hook already ran recall: use its facts. Otherwise, before Round 1, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-kb/scripts/kb.py review <words>`, with the system, file and Workstream names from the invoking message. Use the facts it prints when you propose answers, so a lesson an earlier Workstream learned shapes the plan. `(no memory matches for this prompt)` is a real answer.

## The interview always runs

Rounds 1-4 and step 5 run in order, before any file is written, even when the Scope of Work looks small, obvious, or already described earlier in the conversation. The interview exists to surface the gaps and trade-offs the user has not stated, and a scope that reads as complete is not evidence that it is.

The one exception is the invoking message itself saying to skip: "skip the interview", "use the scope I already wrote, no questions". Prior context, an earlier message in the session, an existing scope document, a light-looking workload, and your own read of the scope all leave the interview running. On a valid opt-out, take the **(Recommended)** answer for every unasked question, write them into `_plan.md` under an `Assumed, not asked` heading, and list them in your reply so the user can correct them.

Ask every question with the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent), one answer per question marked **(Recommended)**, so the user can accept a sensible default in one click and only stops to think where the default is wrong.

## Steps

### 1. Round 1: Basics

Band: `start basics`, then `answer basics <key> <value>` after each answer, then `done basics` after question 5. Answers that land together go in one `answers basics '<JSON object>'` call.

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

Band: `start harness`, an `answer harness <key> <value>` per answer, and `done harness` when the round ends.

**Stored Prompt Settings.** Before asking anything in this round, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_settings.py --read --check`. `FAIL: no Prompt Settings at ...` means no settings are stored yet — the ordinary first run, not an error to report — so ask Rounds 2 and 3 in full. Any `FAIL: invalid Prompt Settings` line means the stored file is corrupt: show the lines verbatim and offer to rebuild it.

`--read` ignores a `reasoningLevel` key left from older settings, and gives each plain-string Model Slot the Priority File's suggested effort, so every slot it returns carries an effort where the file names one.

Where it returns settings, `--check` has already checked each value, because a setting valid when written can go stale. After the settings JSON it prints one `STALE: <setting>: <what is wrong>` line per broken setting: an Agent Harness no longer on PATH, a missing Priority File, or a Model Slot naming a model the Priority File does not rank (`claude`, `codex`) or the harness CLI no longer lists (`pi`, `opencode`, `copilot`, `agy`). No `STALE:` line means every setting holds.

Keep every still-valid setting. Name each broken one to the user with what is wrong, and re-ask that one question alone with the option set Round 2 or Round 3 would have used; the rest of the stored file stays in force.

Before the keep-or-override question, fill both panels from the stored values in two calls: `answers harness '{"detected": ..., "harnesses": ..., "mainOrchestratorHarness": ...}'`, then `answers models '{"modelSet": ..., "models": ..., "maxConcurrency": ...}'` (keys under Round 3). On keep, run `done harness` and `done models`, so both steps tick to done.

Then show the user what the settings hold — the Agent Harnesses and their tiers, each Model Slot with its effort, the Main Orchestrator Agent Harness, target branch, maximum concurrency, Priority File — and ask (Round 4 asks the review defaults on its own):

- **Use these settings for this Workstream (Recommended)** — every stored value becomes this Workstream's answer; skip Rounds 2 and 3 and go to Round 4.
- **Override them for this Workstream** — ask Rounds 2 and 3 in full, offering each stored value as that question's **(Recommended)** answer.

Round 1's target branch wins either way: it was asked for this Workstream, so a stored `targetBranch` never overrides it.

**The questions.** Run `python3 ${CLAUDE_SKILL_DIR}/scripts/detect_harnesses.py` (stdlib Python, no args). Its JSON reports which of the six known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `agy`) are on PATH, already in the priority order `data/model-priority.json` sets — offer them in exactly that order.

1. **Which Agent Harnesses to use for this Workstream** — multi-select over every installed Agent Harness, plus a free-text path where the user types the name and CLI command of an Agent Harness the probe missed. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select over the same option set, asked independently of question 1. This is a separate decision from being a worker Agent Harness: the Main Orchestrator drives dispatch, integrates each Work Item's result as `integration` says, and owns the worktree lifecycle. If the answer is not in question 1's selection, add it to the Agent Harness list — the Main Orchestrator's Agent Harness always needs an entry.

### 3. Round 3: Models

Band: `start models`, an `answer models <key> <value>` per answer, and `done models` once the save offer below is settled. After question 6, re-send `answer harness harnesses` with each tier.

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

**Offer to save these as Prompt Settings.** Only where there were no stored settings or the user chose to override them, ask once after every Round 2 and 3 question is answered: **save these selections as this repo's Prompt Settings?** — **Yes (Recommended)** or **No**. On yes, assemble a Prompt Settings object — `harnesses`, `mainOrchestratorHarness`, `targetBranch`, `maxConcurrency`, `priorityFile`, and nothing Workstream-specific — and pipe it in. Carry over any `review`, `planGate`, `evidenceCommand`, `budgetUsd` and `taskTime` the stored settings hold, so the save does not drop them:

```
echo '<settings JSON>' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_settings.py
```

The script is the validator. On `ok: wrote <path>`, tell the user the path and what was stored. On `FAIL:` lines, show them verbatim, fix the object and re-run — nothing was written. A failed save never blocks the Workstream.

### 4. Round 4: Timing

Band: `start timing`, an `answer timing <key> <value>` per answer, and `done timing` once the answer is recorded.

**Run defaults.** Ask these five first, on every Workstream, even when Round 2 kept the stored settings, because Prompt Settings hold only their defaults and each Workstream picks its own. Each one's Recommended option is the stored value from the `--read` in Round 2. With no stored value, it is the default named below. Step 7 writes the answers into `_config.json`. The Board reads `budgetUsd`. `scaffold.py` writes the Task Time into every generated prompt.

1. **Work Item Review**: whether a reviewer from another Agent Harness checks each Work Item's diff before it is integrated. **On** writes `review: true`, the default. **Off** writes `false`.
2. **Plan Gate**: whether a reviewer signs GO or NO-GO on `_plan.md` before Wave 1. **Off** writes `planGate: false`, the default. **On** writes `true`.
3. **Evidence command**: the command the Main Orchestrator runs once per reviewed commit, such as `pnpm test`. Free text. **None** writes `evidenceCommand: null`, the default.
4. **Budget**: the most the Workstream is meant to spend, in USD, which the Board draws its spend meter against. Nothing stops a run that passes it. Free text, a positive number such as `30`. **None** writes `budgetUsd: null`, the default.
5. **Task Time**: how long each Work Item is meant to take. Every Work Item prompt and `_orchestration.prompt.md` carry it, so each agent knows its time box. Single-select: **Low** (under 5 minutes per Task) writes `taskTime: "low"`, **Medium** (under 10) writes `"medium"`, the default, **High** (under 15) writes `"high"`, **Extra High** (under 30) writes `"xhigh"`, and **Ultra High** (30 or more) writes `"ultra"`. Band: `answer timing taskTime <value>`.

Then ask when the Workstream runs, now, so the answer is settled before the scope interview and the Prompt Band can show it:

- **Run it now (Recommended)** — go to step 5.
- **Schedule it for later** — resolve the time in this round. Ask for the Time Phrase as free text ("1AM on September 2nd", "tomorrow 09:30") and the IANA timezone, recommending the machine's own. Turn the phrase into a concrete local datetime and run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-scheduler/scripts/resolve_schedule.py '<YYYY-MM-DD HH:MM>' <IANA timezone>`. On `FAIL:` lines, show them verbatim and re-ask. Show the resolved local and UTC times and have the user confirm them.

Record the answer and the confirmed time. Nothing is scheduled here: step 11 creates the automation, and only after a clean validate.

### 5. Settle the scope

Band: `start write-validate`, which stays active through step 11, and `tick scope` once the user confirms the settled scope.

Step 5 interviews the user until the Scope of Work and the Workstream Definition of Done are settled. Settled means every Work Item is named, sized (`light` or `standard`), placed in a Wave and unambiguous, every skill it depends on has a decided name and behavior, and the **Workstream Definition of Done** is a short list of checks someone can run or observe.

**Try `grill-with-docs` first.** Invoke it with `Skill(grill-with-docs)` or the Agent Harness equivalent, and let the invocation decide whether it runs. A listing or filesystem check gives false negatives: a project-local skill in `<cwd>/.claude/skills/` is invocable while absent from your available-skills listing. When it runs, let it interview the user and write `CONTEXT.md` glossary entries and ADRs as terms and decisions surface. When it ends, ask any Definition of Done question it left open, with a **(Recommended)** answer.

**On any refusal, run the built-in procedure.** Read `${CLAUDE_SKILL_DIR}/references/grilling.md` and follow it from the top. A refusal is any invocation that does not start the skill: not found, `disable-model-invocation: true`, a permission denial, or any other error. Tell the user in one line which refusal happened and that the built-in grilling procedure is running instead. Do not ask the user to install anything, and do not stop.

Either path ends the same way: the user confirms the settled scope and the Workstream Definition of Done before step 6 starts.

### 6. Write `_plan.md`

Write `.orca/prompts/<workstream>/_plan.md`:

- The settled Scope of Work from step 5, in prose.
- A `## Definition of Done` section holding the Workstream Definition of Done from step 5, followed by an `**Integration**:` line that says in words what Round 1's `integration` answer means for this Workstream. `scaffold.py` copies this section into `_orchestration.prompt.md`, so the Main Orchestrator checks it before it reports the Workstream done.
- An `## Orchestration Rules` section with its body left to the scripts. `scripts/render_rules.py` renders it from `_config.json` and holds the one copy of the **Global Rules** in its `GLOBAL_RULES` string, so changing a Global Rule means editing that string.
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

Assemble the answers as one JSON object keyed like `${CLAUDE_SKILL_DIR}/references/config-schema.md`: `workstream`, `targetBranch`, `integration` and `tickets` from Round 1, `harnesses`, `mainOrchestratorHarness` and `maxConcurrency` from Rounds 2-3, `review`, `planGate`, `evidenceCommand`, `budgetUsd` and `taskTime` from Round 4, and `workItems` (`id` and `size` per Work Item) from `_plan.md`. Pipe it into the writer:

```
echo '<answers JSON>' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt-settings/scripts/write_workstream_config.py --new .orca/prompts/<workstream>
```

The script writes every schema key, fills an absent Round 4 key with its Round 4 default, and runs the checks `scaffold.py` runs. On `ok: wrote <path>`, go on. On `FAIL:` lines, fix the answers and re-run: nothing was written. Band: `tick plan-config`.

### 8. Propose sizes, then confirm

Propose a size (`light` or `standard`) for every Work Item in `_config.json`'s `workItems[]`, based on its scope in `_plan.md`. Skip this step when the user already confirmed every size in step 5. Otherwise ask the user to confirm or correct each, the proposed size marked **(Recommended)**, and write corrections back into `_config.json` before scaffolding. Band: `tick sizes` when sizes are settled, skipped or not.

### 9. Scaffold the Workstream

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/scaffold.py .orca/prompts/<workstream>/`. It writes one `<id>.prompt.md` per Work Item, `_orchestration.prompt.md` with the full Orchestration Rules, and `_rules.md` with the Global Rules once; each Work Item prompt points at `_rules.md` instead of carrying them. With `planGate` on, it also writes `_plan-gate.prompt.md`. It creates an empty Decision Log, `_decisions.md`, when none exists, and writes each Work Item's `wave` and `title` back into `_config.json` and the rendered rules into `_plan.md`. The Wave band reads `_status.json`, whose schema is in `${CLAUDE_SKILL_DIR}/references/status-schema.md`. Band: `tick scaffold` once it succeeds.

### 10. Prompt Check

The Prompt Check reads the scaffolded files the way each worker will: cold, with no memory of this conversation. It runs once, between scaffold and validate, and never loops.

1. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/check_paths.py .orca/prompts/<workstream>/`. It prints one `FAIL: <file>:<line>: ...` line per path, script or command that `_plan.md` and the generated prompts name but that does not exist, or `ok: every named path and command exists`.
2. In parallel, start three Goldfish Readers, one per Prompt Check Model Slot: **Sonnet 5.5 at medium effort**, **Haiku 5.5 at high effort** and **Opus 5.5 at low effort**. In Claude Code, that is three Agent tool calls in one message with `model` set to `sonnet`, `haiku` and `opus` and `effort` set to `medium`, `high` and `low`. Use the Agent Harness equivalent elsewhere, and where it cannot pick a model per subagent, run all three on its default model and say so in one line. Give each reader the same prompt: the full text of `${CLAUDE_SKILL_DIR}/references/prompt-check.md`, then the absolute Workstream directory. Pass no other context, because a reader that knows the conversation fills the gaps a worker cannot.
3. Merge the `check_paths.py` lines and the three readers' findings into one list. Drop a finding that another reader already reported for the same file and line, or for the Work Item prompt line that copies the same `_plan.md` line, keeping the higher severity. Sort it by severity.
4. Fix each small gap yourself in `_plan.md` or `_config.json`: a wrong path, a missing file name, an undefined term the conversation already settled. A missing path that a Work Item creates is not a gap. Ask the user about each finding that needs a decision, one question per finding, with a **(Recommended)** answer.
5. Re-run step 9 when you changed `_plan.md` or `_config.json`, then go on to step 11. Do not run the Prompt Check again.

Show the user the merged list and what you fixed, in at most 5 lines.

### 11. Validate, then run or schedule

When the context after step 9 holds `The orca-helpers hook already ran validate.py`, the hook already validated the Workstream: show the result under that line verbatim and skip the command. Otherwise run `python3 ${CLAUDE_SKILL_DIR}/scripts/validate.py .orca/prompts/<workstream>/` and show the user the result verbatim. A clean run prints `ok: workstream meets the Definition of Done`; a failing run prints one `FAIL:` line per missing piece and exits non-zero. On failure, fix `_config.json` or `_plan.md` and re-run step 9; the Workstream is ready only after a clean validate. Band: `tick validate` on the clean run.

Act on the Round 4 answer only after a clean validate, because a Workstream that fails validation must never be scheduled. Ask nothing new about timing.

- **Run it now**: stop and report the Workstream ready.
- **Schedule it for later**: invoke `orca-prompt-scheduler` — `Skill(orca-prompt-scheduler)` or the Agent Harness equivalent. Hand it `.orca/prompts/<workstream>/_orchestration.prompt.md` as the prompt to schedule, plus the time and timezone the user confirmed in Round 4, so its time step confirms that time instead of asking afresh. That skill owns the conflict check and the `orca automations` call, so leave the CLI to it.

This is the skill's last step. When it is done, run band `done write-validate` and then `end`, which stops the band's checkered flag.

