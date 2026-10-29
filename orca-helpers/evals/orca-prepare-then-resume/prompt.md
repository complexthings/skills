---
max_turns: 4
timeout_seconds: 240
allowed_tools: []
---

You are the Main Orchestrator of the Orca Workstream `auth-refactor`. Nothing is checked out here, so you cannot run commands. Follow the orca-prepare skill between the SKILL markers below, and print each command you would run instead of running it. Treat `${CLAUDE_PLUGIN_ROOT}` as a literal.

<!-- SKILL START -->
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
<!-- SKILL END -->

## Part 1: prepare

The user typed `/orca-prepare auth-refactor`. What you know from this session:

- `set_status.py --show` prints:

  ```
  auth-refactor (active)

  Wave 1 (2/2)
    complete     01-schema  Session schema
    complete     02-tokens  Token rotation

  Wave 2 (0/2)
    in_progress  03-api  Login API
    todo         04-ui  Login page
  ```

- `_decisions.md` holds one entry, `### 2026-10-20 · Tokens rotate on every refresh`.
- The user told you this session to keep refresh tokens in an httpOnly cookie, not localStorage, because of XSS.
- 03-api's worker runs in terminal `term_77`. 04-ui waits on 03-api.
- The `jose` library was tried for 02-tokens and dropped at commit `skills-build@9f3c2ab`, because it lacks Ed25519 key import on Node 18.

Print the commands for steps 3 and 4, then the step 5 reply.

## Part 2: resume

The context is gone. A new session pastes the resume line from Part 1. `/orca-execute` reads this `_resume.md`:

```
# Resume State: auth-refactor

Prepared: 2026-10-24T18:02:11Z
Resume: `/orca-execute auth-refactor`

## Summary

Wave 2 of 2 running: 03-api building in term_77, 04-ui waits on it.

## In flight

03-api worker in terminal term_77.

## Status

auth-refactor (active)

Wave 1 (2/2)
  complete     01-schema  Session schema
  complete     02-tokens  Token rotation

Wave 2 (0/2)
  in_progress  03-api  Login API
  todo         04-ui  Login page

## Read on resume

- `_plan.md`
- `_orchestration.prompt.md`
- `_decisions.md`
- `_status.json`
- `_resume.md`
```

Print the resumed Main Orchestrator's first report: which docs it reads, which Work Items it dispatches now and which it leaves alone. End the reply with that report.
