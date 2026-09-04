---
name: orca-prompt-settings
description: Record the repo-level Prompt Settings a Workstream would otherwise be asked for every time — Agent Harnesses and their Model Slots, the Main Orchestrator harness, target branch, maximum concurrency, reasoning level, and the Priority File — into .orca/prompts/prompt-settings.json. Use when the user says "orca-prompt-settings", "prompt settings", "set the default harnesses or models", or when orca-prompt hands over a settings object to store.
---

# orca-prompt-settings

Stores the defaults `orca-prompt` would otherwise ask for on every Workstream. They live in **Prompt Settings**, one repo-level file at `.orca/prompts/prompt-settings.json`.

Prompt Settings hold only what is reusable across Workstreams. Anything specific to one Workstream — its name, its work items, their phases and sizes — belongs in that Workstream's `_config.json` and is a validation failure here.

## Two ways in

**A settings object was handed to you** — the invoking message carries a complete Prompt Settings object (`orca-prompt` passing its Round 2 and 3 answers over, or the user pasting one). Skip the interview entirely: pipe it into `write_settings.py`, and report what was written or every `FAIL:` line verbatim. See "Non-interview path" below.

**Anything else** — run the interview. Every question goes through the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent) with its recommended answer marked **(Recommended)**. Never ask in prose.

Settings already stored are the starting point, not a reason to skip: run `write_settings.py --read` first, and where it returns a file, offer each stored value as that question's **(Recommended)** answer instead of the default below. A `FAIL:` from `--read` means there are no settings yet — that is the normal first run, not an error to report.

## Steps

### 1. Which Agent Harnesses

Run `orca-helpers/skills/orca-prompt/scripts/detect_harnesses.py` (stdlib Python, no args) and read its JSON report of which of the seven known Agent Harnesses (`claude`, `opencode`, `copilot`, `codex`, `pi`, `prime-agent`, `agy`) are on PATH. The report already comes back in the priority order `data/model-priority.json` sets — offer the options in that order, do not re-sort them.

Ask two questions:

1. **Which Agent Harnesses these settings cover** — multi-select over every Agent Harness the probe found installed, plus a free-text path where the user names an Agent Harness the probe missed and the CLI command that invokes it. Recommend all detected Agent Harnesses.
2. **Which Agent Harness runs the Main Orchestrator** — single-select over the same option set, asked independently of question 1. If the answer is not in question 1's selection, add it to the list; the orchestrator's Agent Harness always needs a `harnesses[]` entry. `Leave it to the Workstream` is a valid answer and writes `mainOrchestratorHarness: null`.

### 2. Which Priority File

Ask before any model question, because every model question in step 3 reads the file this one picks. Single-select over the two that ship in `orca-helpers/skills/orca-prompt/data/`, plus free text for a path to another file:

- **Opinionated Set (Recommended)** — `recommended-priority.json`, ranked by hand from day-to-day use. This is what `list_models.py --recommended` reads.
- **Seeded Set** — `model-priority.json`, ranked on capability per dollar from DeepSWE v1.1 and Artificial Analysis figures. This is what `list_models.py` reads by default.

The answer is written verbatim into `priorityFile`.

### 3. Per Agent Harness: provider, Model Slots, Effort Levels, tier

Repeat this step once per Agent Harness step 1 selected, in the order the probe reported them.

**Where the models come from.** Claude Code (`anthropic`), GitHub Copilot (`github-copilot`) and OpenAI Codex (`openai-codex`) have small known sets: read the Priority File step 2 chose, keyed by provider and then by Model Slot (`orchestrationWorker`, `subagent`, `subagentSimple`; `mainOrchestrator` reads the `orchestrationWorker` ranking), and offer each slot's entries in file order with the top one **(Recommended)** carrying the `effort` the file names. The file is the source of truth; this prose only says where to look. Its `cautions` array holds effort-level traps worth repeating to the user. Copilot's list is the file's entries plus free-form text for anything else the user has access to.

For `pi`, `prime-agent`, `opencode` and `agy`, discover the models instead — they publish what they can run and the list is too long and too changeable to hard-code. Run `orca-helpers/skills/orca-prompt/scripts/list_models.py [--recommended] <harness> <slot>` (pass `--recommended` when step 2 picked the Opinionated Set) and read its JSON: `{"harness": ..., "providers": {"<provider>": [{"model": ..., "efforts": [...], "suggestedEffort": ...}]}}`. Offer the models in the order it returns them, first one **(Recommended)** with its `suggestedEffort`. A model the Priority File does not rank still appears, below every ranked one — offer it too, never drop it.

Then ask, in this order:

1. **Which provider** — single-select over the report's `providers` keys, only for the four discovered Agent Harnesses. Ask it first: the model questions' options come from the chosen provider alone.
2. **One model per Model Slot** — four single-selects: Main Orchestrator, Orchestration Worker, Subagent, Subagent for simple tasks. `Not used by this harness` is a valid answer on any slot and writes `null`. Ask the Main Orchestrator slot only on the Agent Harness step 1 named as `mainOrchestratorHarness`; every other Agent Harness gets `"mainOrchestrator": null` without being asked. The Main Orchestrator runs for the whole Workstream and mostly decides, so it stays a separate pick from the Orchestration Worker, which runs one work item and mostly writes.
3. **Which slots override the reasoning level** — multi-select over that Agent Harness's filled slots, `Use the reasoning level` **(Recommended)** for each. Where the user picks an override, ask which of `low`, `medium`, `high`, `xhigh`, `max`, and write that slot as `{"model": ..., "effort": ...}` instead of a plain string. Skip a slot whose effort question 2 already settled.
4. **Agent Harness Tier** — `light` or `standard`, single-select, used later to route work items by size.

Antigravity bakes its Effort Level into the model id (`gemini-3.7-flash-high`); `list_models.py` strips the suffix and reports it under `efforts`, so the user picks a base model once and never sees two entries differing only by effort. Where a chosen `agy` model has a non-empty `efforts`, ask which one and write the slot as `{"model": ..., "effort": ...}` — that effort is what `agy --effort` receives.

### 4. Target branch, concurrency, reasoning level

Three questions, asked once for the whole file:

1. **Target branch** — the default branch a Main Orchestrator merges work item PRs into. Recommend `main` unless the repo's default is something else (`git remote show origin`, or `git branch --show-current` on a clean checkout).
2. **Maximum concurrency** — free-text number, counting Orchestrator, Subagents and Nested Subagents together. Recommend `6`.
3. **Reasoning level** — single-select: Default (medium) **(Recommended)**, Low, Medium, High, X-High, Max. Written as `default`, `low`, `medium`, `high`, `xhigh` or `max`.

### 5. Write the settings

Assemble the answers into one settings object matching the schema below, and pipe it into `write_settings.py`:

```
echo '<settings JSON>' | python3 orca-helpers/skills/orca-prompt-settings/scripts/write_settings.py
```

Every key must be present, `null` only where a question genuinely left a slot unfilled. On `ok: wrote <path>`, tell the user the path and list what was stored — Agent Harnesses and their tiers, the Main Orchestrator Agent Harness, target branch, concurrency, reasoning level, Priority File. On `FAIL:` lines, show them verbatim, fix the object, and re-run; nothing was written.

## Non-interview path

When the invoking message carries a complete settings object, ask nothing. Pipe it straight into `write_settings.py` and report the result the same way step 5 does: the path and what was stored on success, every `FAIL:` line verbatim on failure. The script is the validator — do not pre-check the object yourself, and do not fill a missing key with a guess. An object missing keys is a `FAIL:` to hand back to the caller, not an interview to start.

## Reading and writing the file

`scripts/write_settings.py` is the only path in or out. Both `orca-prompt` and this skill go through it, so there is exactly one validator and one reader.

```
echo '<settings JSON>' | python3 orca-helpers/skills/orca-prompt-settings/scripts/write_settings.py [path]
python3 orca-helpers/skills/orca-prompt-settings/scripts/write_settings.py --read [path]
python3 orca-helpers/skills/orca-prompt-settings/scripts/write_settings.py --demo
```

`path` defaults to `.orca/prompts/prompt-settings.json`. A write validates first and prints one `FAIL:` line per problem, exits 1, and leaves any stored file untouched; a clean write prints `ok: wrote <path>`. `--read` prints the stored settings as JSON, or a `FAIL:` line and exit 1 when the file does not exist — that exit is how a caller learns there are no settings yet, not an error to report to the user.

## Prompt Settings schema

The contract every later script in this pattern codes against. Do not rename or remove a key without updating every skill that reads it.

```json
{
  "harnesses": [
    {
      "name": "string — Agent Harness identifier: claude | opencode | copilot | codex | pi | prime-agent | agy | <other>",
      "cli": "string — the CLI command that invokes this Agent Harness",
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
  "targetBranch": "string — default branch the Main Orchestrator merges work item PRs into",
  "maxConcurrency": "number | null — ceiling counting Orchestrator, Subagents, and Nested Subagents combined",
  "reasoningLevel": "default | low | medium | high | xhigh | max",
  "priorityFile": "string — the Priority File models are ranked against: model-priority.json (Seeded Set) or recommended-priority.json (Opinionated Set), both in orca-helpers/skills/orca-prompt/data/, or a path to another file"
}
```

Notes for the scripts that read this file:

- A **Model Slot** is either a plain string — `"claude-opus-5"`, meaning "use the `reasoningLevel`" — or an object `{"model": "gpt-5.6-sol", "effort": "high"}` overriding the level for that slot alone. Valid efforts are `low`, `medium`, `high`, `xhigh`, `max`. Slots are read through `orca-prompt`'s `render_rules.normalize_model_slot`, which is where the shape is defined; any third shape is a `FAIL:`.
- All four Model Slot keys must be present on every harness entry. `null` is how a harness says it does not fill that slot — `mainOrchestrator` is `null` on every harness that does not run the Main Orchestrator, and `subagentSimple` is `null` on a harness that does not distinguish a simple-task model.
- `mainOrchestratorHarness` must name one of the `harnesses[].name` values, or be `null` when the choice is left to the Workstream.
- Every key in this schema must exist in a written file, even where the value is `null`. A missing key means the file was hand-edited or written by something older than this schema — that is an error, not a default to silently fill in.
- A key this schema does not list is a `FAIL:`, so a Workstream-specific value (`workstream`, `workItems`) cannot leak in unnoticed.

## Relationship to `_config.json`

Prompt Settings are the defaults; a Workstream's `_config.json` is the record of what one Workstream actually used. The overlapping keys carry the same meaning and the same Model Slot shape in both files, so `orca-prompt` can offer stored settings as the answers to Rounds 2 and 3. `_config.json` additionally carries `workstream` and `workItems`, which never appear here.
