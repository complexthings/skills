---
name: orca-prompt-scheduler
description: Schedule an Orca Workstream's _orchestration.prompt.md to run later as a one-shot Orca automation — resolves the time to cron, warns about nearby automations, and adds a Once-Guard so it fires exactly once. Use for "orca-prompt-scheduler", "schedule this workstream", "run this prompt later", "kick this Workstream off overnight". To create a Workstream use orca-prompt; for recurring automations, orca-cli.
---

# orca-prompt-scheduler

Turns a Workstream into a **Scheduled Prompt**: its `_orchestration.prompt.md` registered with Orca to run at a future time rather than now, backed by one Orca automation and identified by that automation's id.

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment.

## Ground rules

`scripts/schedule.py` runs every `orca automations` call that creates or edits the Scheduled Prompt. To read or change an automation by hand, take the flags from `orca skills get orca-cli --reference references/automations.md` rather than from memory.

Ask each choice with the Agent Harness question tool (`askUserQuestion` / `askQuestions` / `ask_user_question` / the Agent Harness equivalent), the recommended answer marked **(Recommended)**, so the user picks from options rather than composing a reply. The Time Phrase and a Precondition command are the free-text exceptions — there is no sensible option list for either.

Orca has no one-shot trigger. A one-shot Scheduled Prompt is the narrowest cron containing the wanted moment plus a **Once-Guard** precheck that removes the automation after its first run (see `docs/adr/0007-one-shot-schedules-use-cron-plus-a-once-guard.md`). The trigger carries only the cron; the Once-Guard is what makes it fire once.

## Steps

### 1. Which Workstream

Single-select over every directory under `.orca/prompts/` that holds an `_orchestration.prompt.md`, most recently modified first and that one **(Recommended)**. A directory without that file is not schedulable, so it is not an option. When `orca-prompt` handed over a Workstream path, use it as the answer and do not ask afresh.

`schedule.py` reads the chosen Workstream's `_config.json` itself: the `mainOrchestratorHarness` entry gives the Orca agent id (through `scaffold.orca_agent()`) and its `mainOrchestrator` Model Slot, and `targetBranch` gives the base branch.

### 2. When

Ask for the **Time Phrase** as free text — "1AM on September 2nd", "tomorrow 09:30" — and for the timezone, recommending the machine's own IANA name (from `$TZ` or the target of `readlink /etc/localtime`; an abbreviation such as `EDT` is not an IANA name).

You turn the Time Phrase into a concrete local datetime; `resolve_schedule.py` takes it from there and refuses anything vague:

```
python3 ${CLAUDE_SKILL_DIR}/scripts/resolve_schedule.py '<YYYY-MM-DD HH:MM>' <IANA timezone>
```

It prints `{"cron": ..., "timezone": ..., "local": ..., "utc": ...}`. On `FAIL:` lines, show them verbatim and re-ask — a time inside the DST spring-forward gap does not exist, and one inside the fall-back overlap names both UTC instants so the user picks which was meant.

When `orca-prompt` handed over a time and timezone, use them as the answer: skip the Time Phrase question, still run `resolve_schedule.py` on them, and do not ask afresh.

Then show the resolved **local** and **UTC** times and the cron expression, and have the user confirm (a handed-over time is confirmed here, not asked) before anything is created — a wrong time is only cheap to fix before creation.

### 3. Enabled, and any Precondition

Two questions:

1. **Starts enabled or disabled** — `Enabled` **(Recommended)**. Disabled writes `--disabled` and the automation sits there until the user enables it.
2. **Any Precondition** — a user-supplied shell command the run must pass, such as a check that a PR is open. `No Precondition` **(Recommended)**; otherwise take the command as free text. It is composed behind the Once-Guard in step 6, because Orca accepts exactly one precheck command.

### 4. Conflict check

```
python3 ${CLAUDE_SKILL_DIR}/scripts/check_conflicts.py <utc from step 2> --repo <repo path>
```

`--repo` defaults to this git working tree. The JSON carries `conflicts` (automations on this repo firing within 15 minutes) and `unresolved` (schedules the script would not guess at, such as an RRULE).

This is a report, not a gate — it exits 0 either way. Where either list is non-empty, show each entry's name, trigger and firing times as a **warning**, say plainly that two agents starting minutes apart on the same repo fight over the same worktree and branch, and ask whether to continue or pick a different time. Continue only on an explicit yes; a different time sends you back to step 2.

### 5. Schedule it

```
python3 ${CLAUDE_SKILL_DIR}/scripts/schedule.py <workstream path> \
  --utc '<utc from step 2>' --tz '<timezone from step 2>' \
  [--disabled] [--precondition '<precondition from step 3>']
```

The script creates the automation with the `Execute <workstream path>/_orchestration.prompt.md` line alone, because the id does not exist until `create` returns it. It then writes the precheck wrapper (Once-Guard first, Precondition second, both must exit 0) under `<workstream path>/.scheduled/`, and edits the automation to carry the wrapper and the full prompt. That prompt opens with the self-removal instruction, spelled with the resolved Orca executable. When the Main Orchestrator's Agent Harness takes `--extra-agent-args`, its Model Slot rides along.

Both layers are deliberate: the prompt instruction usually removes the automation the moment it runs, and the Once-Guard is what still stops a second run when the agent crashes before removing it, and removes the automation when a run missed while the machine slept fires more than a day late. A run more than a day early (a time over a year out makes the yearly cron fire early) is skipped without removing the automation or writing the marker, so the cron fires again on the right date.

On `FAIL:` lines, show them verbatim and report the schedule as failed, not created. When a step after `create` fails, the script has already removed the automation again, so nothing fires every year. When `create` prints no id, the script finds the new automation by its name and cron and removes it. A `FAIL:` line that says to remove an automation by hand names it, or the `remove` command to run.

### 6. Report

The script prints JSON with `id`, `cron`, `timezone`, `local`, `utc`, `enabled`, `precheck` and `cancel`. Tell the user, in this order: the automation id, the resolved local and UTC times, the trigger, enabled or disabled, the precheck wrapper's path, and the `cancel` command as the way to cancel it. Mention that the automation list shows a recurring cron rather than a one-shot until the guard fires: that is expected, not a mistake.

## Scripts

All are stdlib Python. `schedule.py` has `test_schedule.py` beside it; the other three take `--demo` to self-check.

| Script | Does |
| --- | --- |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/schedule.py <workstream> --utc <ISO> --tz <IANA> [--disabled] [--precondition <text>]` | Creates the automation, writes the precheck wrapper and edits in the self-removing prompt. Removes the automation again when a later step fails. |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/resolve_schedule.py '<local datetime>' <tz>` | Local wall clock -> `{cron, timezone, local, utc}`. Fails on a DST gap or overlap rather than guessing. |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/check_conflicts.py <ISO datetime> [--repo <path>] [--window-minutes 15]` | Reports automations on this repo firing near the proposed instant. Always exits 0. |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/once_guard.py --write-wrapper <wrapper> <id> <marker> <utc> [precondition]` | Writes the executable precheck wrapper: Once-Guard first, Precondition second. |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/once_guard.py <id> <marker> <utc>` | The guard itself, run by the wrapper. First call exits 0; every later call, or one over a day past `<utc>`, removes the automation and exits non-zero; one over a day before `<utc>` exits non-zero and keeps the automation and marker untouched. |
