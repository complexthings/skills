---
name: orca-prompt-settings
description: Store repo-level Orca Prompt Settings in .orca/prompts/prompt-settings.json — Agent Harnesses and Model Slots, Main Orchestrator harness, target branch, concurrency, Priority File, and the Work Item Review, Plan Gate, evidence command, budget and Task Time defaults. Use for "orca-prompt-settings", "prompt settings", "set the default harnesses or models", or when orca-prompt hands over settings to store. To start a Workstream use orca-prompt; to schedule one, orca-prompt-scheduler.
---

# orca-prompt-settings

Stores the defaults `orca-prompt` would otherwise ask for on every Workstream. They live in **Prompt Settings**, one repo-level file at `.orca/prompts/prompt-settings.json`.

Prompt Settings hold only what is reusable across Workstreams. Anything specific to one Workstream — its name, its Work Items, their Waves and sizes — belongs in that Workstream's `_config.json` and is a validation failure here.

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment.

## Two ways in

**A settings object was handed to you** — the invoking message carries a complete Prompt Settings object (`orca-prompt` passing its Round 2 and 3 answers over, or the user pasting one). Ask nothing: pipe it straight into `write_settings.py` and report the result the way step 6 does — the path and what was stored on success, every `FAIL:` line verbatim on failure. The script is the validator, so hand it the object as received: a missing key is a `FAIL:` to return to the caller, not a gap to fill with a guess or a reason to start the interview.

**Anything else** — run the interview. Ask every question with the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent), its recommended answer marked **(Recommended)**, so the user picks from options rather than composing a reply.

Settings already stored are the starting point, not a reason to skip: run `python3 ${CLAUDE_SKILL_DIR}/scripts/write_settings.py --read` first, and where it returns a file, offer each stored value as that question's **(Recommended)** answer instead of the default below. `--read` ignores a `reasoningLevel` key left from older settings and gives each plain-string Model Slot the Priority File's suggested effort. A `FAIL: no Prompt Settings at ...` from `--read` means there are no settings yet — the normal first run, not an error to report. Any other `FAIL:` (`invalid Prompt Settings`) means the stored file is corrupt or missing keys: show the lines verbatim and ask whether to rebuild it through the interview, which overwrites it.

## Steps

### 1. Which Agent Harnesses

Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/detect_harnesses.py` (stdlib Python, no args) and read its JSON report of which of the six known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `agy`) are on PATH. The report already comes back in the priority order `data/model-priority.json` sets — offer the options in exactly that order.

Ask two questions:

1. **Which Agent Harnesses these settings cover** — multi-select over every Agent Harness the probe found installed, plus a free-text path where the user names an Agent Harness the probe missed and the CLI command that invokes it. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select over the same option set, asked independently of question 1. If the answer is not in question 1's selection, add it to the list; the Main Orchestrator's Agent Harness always needs a `harnesses[]` entry. `Leave it to the Workstream` is a valid answer and writes `mainOrchestratorHarness: null`.

### 2. Which Priority File

Ask before any model question, because every model question in step 3 reads the file this one picks. Single-select over the two that ship in `${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/data/`, plus free text for a path to another file:

- **Opinionated Set (Recommended)** — `recommended-priority.json`, ranked by hand from day-to-day use. This is what `list_models.py --recommended` reads.
- **Seeded Set** — `model-priority.json`, ranked on capability per dollar from DeepSWE v1.1 and Artificial Analysis figures. This is what `list_models.py` reads by default.

The answer is written verbatim into `priorityFile`.

### 3. Per Agent Harness: provider, Model Slots, efforts, tier

Repeat this step once per Agent Harness step 1 selected, in the order the probe reported them.

**Where the models come from.** Claude Code (`anthropic`) and OpenAI Codex (`openai-codex`) have small known sets: read the Priority File step 2 chose, keyed by provider and then by Model Slot (`orchestrationWorker`, `subagent`, `subagentSimple`; `mainOrchestrator` reads the `orchestrationWorker` ranking), and offer each slot's entries in file order with the top one **(Recommended)** carrying the `effort` the file names. The file is the source of truth; this prose only says where to look. Its `cautions` array holds effort-level traps worth repeating to the user.

For `pi`, `opencode`, `copilot` and `agy`, discover the models instead — they publish what they can run and the list is too long and too changeable to hard-code. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/list_models.py [--recommended] <harness> <slot>` (pass `--recommended` when step 2 picked the Opinionated Set) and read its JSON: `{"harness": ..., "providers": {"<provider>": [{"model": ..., "efforts": [...], "suggestedEffort": ...}]}}`. Offer the models in the order it returns them, first one **(Recommended)** with its `suggestedEffort`. A model the Priority File does not rank still appears below every ranked one; offer it too, because the Priority File is never a whitelist.

Then ask, in this order:

1. **Which provider** — single-select over the report's `providers` keys, only for the discovered Agent Harnesses. Ask it first: the model questions' options come from the chosen provider alone.
2. **One model per Model Slot** — four single-selects: Main Orchestrator, Orchestration Worker, Subagent, Subagent for simple tasks. `Not used by this Agent Harness` is a valid answer on any slot and writes `null`. Ask the Main Orchestrator slot only on the Agent Harness step 1 named as `mainOrchestratorHarness`; every other Agent Harness gets `"mainOrchestrator": null` without being asked. The Main Orchestrator runs for the whole Workstream and mostly decides, so it stays a separate pick from the Orchestration Worker, which runs one work item and mostly writes.
3. **An effort for every filled Model Slot** — single-select per slot, right after its model is picked. Offer only the Effort Levels (`max`, `xhigh`, `high`, `medium`, `low`) that the slot's Agent Harness and model support, because a level the model lacks is either rejected or ignored by its CLI. Take the supported set from `list_models.py`'s `efforts` where it is non-empty, and otherwise from the efforts the Priority File lists for that model. Mark the Priority File's suggested effort **(Recommended)**, and write the slot as `{"model": ..., "effort": ...}`. A model the Priority File lists with `"effort": null` takes no effort: skip the question and write the slot as a plain string.
4. **Agent Harness Tier** — `light` or `standard`, single-select, used later to route work items by size.

Antigravity bakes its Effort Level into the model id (`gemini-3.8-flash-high`); `list_models.py` strips the suffix and reports it under `efforts`, so the user picks a base model once and never sees two entries differing only by effort. Question 3's effort for an `agy` slot is what `agy --effort` receives.

### 4. Target branch, concurrency

Two questions, asked once for the whole file:

1. **Target branch** — the default branch every Work Item's result reaches. Recommend `main` unless the repo's default is something else (`git remote show origin`, or `git branch --show-current` on a clean checkout).
2. **Maximum concurrency** — free-text positive whole number, counting Orchestrator, Subagents and Nested Subagents together. Recommend `6`.

Ask no file-wide reasoning or effort question. Effort lives only on the Model Slot, and step 3 has already set it per slot.

### 5. Run defaults

Five questions, asked once for the whole file. `orca-prompt` offers each answer as the Recommended option on every Workstream, so these are defaults, not fixed rules.

1. **Work Item Review**: whether a reviewer from another Agent Harness checks each Work Item's diff before it is integrated. **On (Recommended)** writes `review: true`. **Off** writes `false`.
2. **Plan Gate**: whether a reviewer signs GO or NO-GO on `_plan.md` before Wave 1. **Off (Recommended)** writes `planGate: false`. **On** writes `true`.
3. **Evidence command**: the command the Main Orchestrator runs once per reviewed commit, such as `pnpm test`. Free text, or **None**, which writes `evidenceCommand: null`. Mark the repo's test command **(Recommended)** when `package.json`, `Makefile` or `pyproject.toml` names one, and **None** otherwise.
4. **Budget**: the default spend budget in USD that the Board draws its spend meter against. Nothing stops a run that passes it. Free text, a positive number such as `30`. **None (Recommended)** writes `budgetUsd: null`.
5. **Task Time**: how long each Work Item is meant to take. Every generated prompt carries it. Single-select: **Low** (under 5 minutes per Task) writes `taskTime: "low"`, **Medium (Recommended)** (under 10) writes `"medium"`, **High** (under 15) writes `"high"`, **Extra High** (under 30) writes `"xhigh"`, and **Ultra High** (30 or more) writes `"ultra"`.

### 6. Write the settings

Assemble the answers into one settings object matching the schema below, and pipe it into `write_settings.py`:

```
echo '<settings JSON>' | python3 ${CLAUDE_SKILL_DIR}/scripts/write_settings.py
```

Every key is present, `null` only where a question genuinely left a slot unfilled. On `ok: wrote <path>`, tell the user the path and list what was stored — Agent Harnesses and their tiers, each Model Slot with its effort, the Main Orchestrator Agent Harness, target branch, concurrency, Priority File, Work Item Review, Plan Gate, evidence command, budget, Task Time. On `FAIL:` lines, show them verbatim, fix the object, and re-run; nothing was written.

## Reading and writing the file

`scripts/write_settings.py` is the only path in or out. Both `orca-prompt` and this skill go through it, so there is exactly one validator and one reader.

```
echo '<settings JSON>' | python3 ${CLAUDE_SKILL_DIR}/scripts/write_settings.py [path]
python3 ${CLAUDE_SKILL_DIR}/scripts/write_settings.py --read [path]
python3 ${CLAUDE_SKILL_DIR}/scripts/write_settings.py --demo
```

`path` defaults to `.orca/prompts/prompt-settings.json`. A write validates first and prints one `FAIL:` line per problem, exits 1, and leaves any stored file untouched; a clean write prints `ok: wrote <path>`. `--read` prints the stored settings as JSON, or a `FAIL: no Prompt Settings at ...` line and exit 1 when the file does not exist — that is how a caller learns there are no settings yet, not an error to report. A file that is not valid JSON or fails the validator prints `FAIL: invalid Prompt Settings at ...` lines and exits 1; that is a corrupt file, not a first run.

## Prompt Settings schema

The contract every later script in this pattern codes against. Renaming or removing a key means updating every skill that reads it.

```json
{
  "harnesses": [
    {
      "name": "string — Agent Harness identifier: claude | opencode | copilot | codex | pi | agy | <other>",
      "cli": "string or null — the CLI command that invokes this Agent Harness; null for a built-in name",
      "tier": "light | standard — routes work items to this Agent Harness by size",
      "models": {
        "mainOrchestrator": "Model Slot | null — model for the Main Orchestrator session",
        "orchestrationWorker": "Model Slot | null — model for the Orchestration Worker session",
        "subagent": "Model Slot | null — model for ordinary subagents",
        "subagentSimple": "Model Slot | null — model for subagents doing simple tasks"
      }
    }
  ],
  "mainOrchestratorHarness": "string | null — which harnesses[].name runs the Main Orchestrator",
  "targetBranch": "string — default branch every Work Item's result reaches",
  "maxConcurrency": "positive integer | null — ceiling counting Orchestrator, Subagents, and Nested Subagents combined",
  "priorityFile": "string — the Priority File models are ranked against: model-priority.json (Seeded Set) or recommended-priority.json (Opinionated Set), both in ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/data/, or a path to another file",
  "review": "boolean, optional — Work Item Review default; absent reads as true",
  "planGate": "boolean, optional — Plan Gate default; absent reads as false",
  "evidenceCommand": "string | null, optional — the evidence command default; absent reads as null",
  "budgetUsd": "positive number | null, optional — the spend budget default in USD; absent reads as null",
  "taskTime": "low | medium | high | xhigh | ultra, optional — the Task Time default; absent reads as medium"
}
```

Notes for the scripts that read this file:

- A **Model Slot** is either an object `{"model": "gpt-6.1-sol", "effort": "high"}` or a plain string `"<model-id>"` for a model that takes no effort. A plain string the Priority File ranks with an effort reads back from `--read` as the object form, with that suggested effort. Valid efforts are `low`, `medium`, `high`, `xhigh`, `max`. Slots are read through `orca-prompt`'s `render_rules.normalize_model_slot`, which is where the shape is defined; any third shape is a `FAIL:`.
- All four Model Slot keys must be present on every `harnesses[]` entry. `null` is how an Agent Harness says it does not fill that slot — `mainOrchestrator` is `null` on every Agent Harness that does not run the Main Orchestrator, and `subagentSimple` is `null` on one that does not distinguish a simple-task model.
- `mainOrchestratorHarness` must name one of the `harnesses[].name` values, or be `null` when the choice is left to the Workstream.
- Every key in this schema except `review`, `planGate`, `evidenceCommand`, `budgetUsd` and `taskTime` must exist in a written file, even where the value is `null`. Those five are optional so settings written before them still read; step 6 writes all five. A missing key means the file was hand-edited or written by something older than this schema — an error to report, not a default to fill in.
- `reasoningLevel` is retired. `--read` ignores it in older files, and a write drops it, so the next save removes it.
- Any other key this schema does not list is a `FAIL:`, so a Workstream-specific value (`workstream`, `workItems`) cannot leak in unnoticed.

## Relationship to `_config.json`

Prompt Settings are the defaults; a Workstream's `_config.json` is the record of what one Workstream actually used. The overlapping keys carry the same meaning and the same Model Slot shape in both files, so `orca-prompt` can offer stored settings as the answers to Rounds 2 and 3. `review`, `planGate`, `evidenceCommand`, `budgetUsd` and `taskTime` are defaults here and the Workstream's own answers in `_config.json`. `_config.json` additionally carries `workstream` and `workItems`, which never appear here.
