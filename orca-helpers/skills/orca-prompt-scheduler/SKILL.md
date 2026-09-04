---
name: orca-prompt-scheduler
description: Register a Workstream's _orchestration.prompt.md as a Scheduled Prompt — interviews for the workstream, the time, enabled or disabled, and an optional Precondition, resolves the time to a cron expression, warns about nearby automations, and creates the Orca automation with a Once-Guard precheck so a one-shot fires exactly once. Use when the user says "orca-prompt-scheduler", "schedule this workstream", "run this prompt later", "schedule an orchestration", or when orca-prompt asks to schedule a Workstream instead of running it now.
---

# orca-prompt-scheduler

Turns a Workstream into a **Scheduled Prompt**: its `_orchestration.prompt.md` registered with Orca to run at a future time rather than now, backed by one Orca automation and identified by that automation's id.

## Non-negotiable

Read `resources/orca-automations.md` before you touch the `orca automations` CLI. It is the verified flag reference — the source of truth for what `create`, `edit`, `remove`, `list` and `runs` accept — so take every flag you pass from it, rather than from `--help` or from memory.

Every question goes through the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent) with the recommended answer marked **(Recommended)**. Never ask in prose.

Orca has no one-shot trigger. A one-shot Scheduled Prompt is the narrowest cron containing the wanted moment plus a **Once-Guard** precheck that removes the automation after its first run — see `docs/adr/0007-one-shot-schedules-use-cron-plus-a-once-guard.md`. Do not try to express "once" in the trigger.

## Steps

### 1. Which Workstream

Single-select over every directory under `.orca/prompts/` that holds an `_orchestration.prompt.md`, most recently modified first and that one **(Recommended)**. A directory without that file is not schedulable — do not offer it.

Read the chosen Workstream's `_config.json`. `mainOrchestratorHarness` and its `harnesses[].cli` give the recommended `--provider`; `targetBranch` gives the recommended `--base-branch`.

### 2. When

Ask for the **Time Phrase** as free text — "1AM on September 2nd", "tomorrow 09:30" — and ask for the timezone, recommending the machine's own (`python3 -c "import datetime; print(datetime.datetime.now().astimezone().tzname())"` only tells you the abbreviation; prefer the IANA name from `readlink /etc/localtime` or `TZ`).

You turn the Time Phrase into a concrete local datetime. `resolve_schedule.py` takes it from there and refuses anything vague:

```
python3 orca-helpers/skills/orca-prompt-scheduler/scripts/resolve_schedule.py '<YYYY-MM-DD HH:MM>' <IANA timezone>
```

It prints `{"cron": ..., "timezone": ..., "local": ..., "utc": ...}`. On `FAIL:` lines, show them verbatim and re-ask — a time inside the DST spring-forward gap does not exist, and one inside the fall-back overlap names both UTC instants so the user picks which was meant.

Then confirm: show the resolved **local** and **UTC** times and the cron expression, and ask the user to confirm before anything is created. A wrong time is only cheap to fix before creation.

### 3. Enabled, and any Precondition

Two questions:

1. **Starts enabled or disabled** — `Enabled` **(Recommended)**. Disabled writes `--disabled` and the automation sits there until the user enables it.
2. **Any Precondition** — a user-supplied shell command the run must pass, such as a check that a PR is open. `No Precondition` **(Recommended)**; otherwise take the command as free text. It is composed behind the Once-Guard in step 6, because Orca accepts exactly one precheck command.

### 4. Conflict check

```
python3 orca-helpers/skills/orca-prompt-scheduler/scripts/check_conflicts.py <utc from step 2> --repo <repo path>
```

`--repo` defaults to this git working tree. The JSON carries `conflicts` (automations on this repo firing within 15 minutes) and `unresolved` (schedules the script would not guess at, such as an RRULE).

This is a report, not a gate — it exits 0 either way. Where either list is non-empty, show each entry's name, trigger and firing times as a **warning**, say plainly that two agents starting minutes apart on the same repo fight over the same worktree and branch, and ask whether to continue or pick a different time. Continue only on an explicit yes; a different time sends you back to step 2.

### 5. Create the automation

The prompt text has a fixed shape — the self-removal instruction first, then the execution instruction:

```
Before beginning, remove this automation: `orca automations remove <id>`.

Execute <workstream path>/_orchestration.prompt.md
```

The id does not exist yet, so create first with a placeholder-free first line — write only the `Execute` line now — and install the full text in step 6:

```
orca automations create \
  --name '<workstream> orchestration' \
  --trigger '<cron from step 2>' \
  --timezone '<timezone from step 2>' \
  --prompt 'Execute <workstream path>/_orchestration.prompt.md' \
  --provider <cli from step 1> \
  --repo path:<repo path> \
  --base-branch <targetBranch from step 1> \
  [--disabled] \
  --json
```

Read the automation id out of the JSON. Every later step needs it. If `create` fails, report its output verbatim and stop — there is nothing to clean up.

### 6. Install the precheck and the id-carrying prompt

Write the precheck wrapper. It is one script composing the Once-Guard and the Precondition, and both halves must exit 0:

```
python3 orca-helpers/skills/orca-prompt-scheduler/scripts/once_guard.py --write-wrapper \
  '<workstream path>/.scheduled/<id>-precheck.sh' \
  '<id>' \
  '<workstream path>/.scheduled/<id>.marker' \
  ['<precondition from step 3>']
```

Then `edit` the automation to carry both the wrapper and the full prompt text:

```
orca automations edit <id> \
  --precheck '<workstream path>/.scheduled/<id>-precheck.sh' \
  --prompt 'Before beginning, remove this automation: `orca automations remove <id>`.

Execute <workstream path>/_orchestration.prompt.md' \
  --json
```

Both layers are deliberate: the prompt instruction usually removes the automation the moment it runs, and the Once-Guard is what still stops a second run when the agent crashes before removing it.

If `edit` fails, the automation exists without its guard and would fire every year. Say so, and offer `orca automations remove <id>` — do not leave a half-configured automation reported as success.

### 7. Report

Tell the user, in this order: the automation id, the resolved local and UTC times, the trigger, enabled or disabled, the precheck wrapper's path, and `orca automations remove <id>` as the way to cancel it. Mention that `orca automations list` shows a recurring cron rather than a one-shot until the guard fires — that is expected, not a mistake.

## Scripts

All three are stdlib Python and all three take `--demo` to self-check.

| Script | Does |
| --- | --- |
| `scripts/resolve_schedule.py '<local datetime>' <tz>` | Local wall clock -> `{cron, timezone, local, utc}`. Fails on a DST gap or overlap rather than guessing. |
| `scripts/check_conflicts.py <ISO datetime> [--repo <path>] [--window-minutes 15]` | Reports automations on this repo firing near the proposed instant. Always exits 0. |
| `scripts/once_guard.py --write-wrapper <wrapper> <id> <marker> [precondition]` | Writes the executable precheck wrapper: Once-Guard first, Precondition second. |
| `scripts/once_guard.py <id> <marker>` | The guard itself, run by the wrapper. First call exits 0; every later call removes the automation and exits non-zero. |
