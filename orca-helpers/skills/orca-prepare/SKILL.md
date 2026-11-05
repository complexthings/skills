---
name: orca-prepare
description: Ready a running Orca Workstream for compaction or handover. Files the durable facts held only in this session to the Decision Log, writes Resume State to _resume.md beside _status.json, and prints a paste-ready `/orca-execute <workstream>` line with a one-line summary. `/orca-prepare [workstream]`.
argument-hint: "[workstream]"
disable-model-invocation: true
---

# orca-prepare

A compaction or a new session drops everything the Main Orchestrator holds only in context. This skill moves that knowledge to disk, so `/orca-execute <workstream>` in any session picks the run back up. It changes no Work Item state and dispatches nothing.

The argument is `$ARGUMENTS`.

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment.

## Steps

1. **Pick the Workstream.** Use the one named. With no argument, use the one whose `.orca/prompts/*/_status.json` has `"active": true`. When none is active and none is named, ask with the Agent Harness question tool, one option per directory under `.orca/prompts/` that holds a `_status.json`. Done when `<dir>/_status.json` exists, where `<dir>` is `.orca/prompts/<workstream>/`.

2. **Read what is already on disk.** Read `<dir>/_decisions.md` and run:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/set_status.py <dir> --show
   ```

   A fact already in the Decision Log, or a state already in the table, needs no new entry.

3. **File each durable fact.** A durable fact is one that a resumed orchestrator needs and that lives only in this session: a decision and its reason, a rejected approach, a user answer, a workaround, or a failure and its cause. Append one entry per fact:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/set_status.py <dir> log "<title>" "<body>" [--commit <repo>@<sha>] [--supersedes "<old title>"]
   ```

   Pass `--commit` when the fact is about code that a commit holds. Pass `--supersedes` when the fact changes an earlier entry, so the old entry is marked instead of edited. Leave out work in progress, Work Item states and anything already in `_plan.md` or a prompt file, because `_status.json` and the Resume State carry those and a duplicate goes stale. Write each body so it stands alone for a reader with no session context. A `FAIL:` line means nothing was written: fix the input it names and run it again.

4. **Write the Resume State.** Write one summary line of at most 25 words that says where the run stands, for example `Wave 2 of 3 running: 05-api in review, 06-ui building.` Then run:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prepare/scripts/prepare.py <dir> "<summary>" --next "<in flight>"
   ```

   `--next` names each worker still running, with its terminal handle, and each open question or Decision Gate. Leave `--next` out when nothing is in flight. The script writes `<dir>/_resume.md` and prints two lines: the resume line, then the summary.

5. **Reply.** Lead with the resume line in a code block, so the user pastes it in one move. Then give the summary line and the count of Decision Log entries filed in step 3. End with one next step: run `/compact`, or paste the resume line into the new session.

## Resuming

`/orca-execute <workstream>` reads `_resume.md` when it exists. `set_status.py --start` keeps every Work Item state, so the resumed run skips complete items and binds the workers still listed under In flight.
