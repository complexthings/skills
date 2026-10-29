---
name: orca-execute
description: Run an Orca Workstream Wave by Wave as its Main Orchestrator, keeping _status.json in step so the Wave band shows live progress. `/orca-execute <workstream>` starts or resumes; `/orca-execute copy` copies the run as Markdown; `/orca-execute stop` hides the band.
argument-hint: <workstream> | copy | stop
disable-model-invocation: true
---

# orca-execute

Runs one Workstream from `.orca/prompts/<workstream>/` as its **Main Orchestrator**. `_orchestration.prompt.md` says how to dispatch, wait and merge. This skill adds the bookkeeping around it: every Work Item state change lands in `_status.json`, which the Wave band reads. The band is the checklist, so keep no separate Task list.

The argument is `$ARGUMENTS`.

`set_status.py` is the only writer of `_status.json`. Run it as:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/set_status.py <dir> <args>
```

`<dir>` is the Workstream directory, `.orca/prompts/<workstream>/`. A `FAIL:` line means nothing was written. Fix the input it names and run it again.

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment.

## `stop`

When the argument is `stop`, or `stop <workstream>`, clear the active flag and end:

1. Pick the Workstream: the one named, or the one whose `_status.json` has `"active": true`. `--start` keeps at most one active. When none is, tell the user the band is already off and end.
2. Run `set_status.py <dir> --stop`. It prints nothing on success, and the band disappears.

Stopping hides the band only. Running workers, Tasks and Work Item states stay as they are.

`--stop` is the only thing that hides the Wave band: it stays up while a question shows. The `o` hotkey, or the band's caret, collapses it to its top bar, and collapses or expands the Prompt Band with it.

## `copy`

The orca-helpers hooks module answers `/orca-execute copy` before this skill loads. It copies the active run as Markdown and confirms with a toast. When this skill receives `copy` anyway, the hooks module is not loaded. Copy nothing yourself: the toast and the surface clipboard belong to the hooks module. Tell the user to restart Claude Code so the hooks module loads, and end.

## Start or resume

1. **Resolve the Workstream.** A name maps to `.orca/prompts/<name>/`. A path is used as given. With no argument, ask with the Agent Harness question tool, one option per directory under `.orca/prompts/` holding a `_config.json`, the most recently modified marked **(Recommended)**. Done when `<dir>/_config.json` and `<dir>/_orchestration.prompt.md` both exist.

2. **Check for Wave data.** Run the check from the repo root:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/scaffold.py --check .orca/prompts/<workstream>/
   ```

   It prints nothing and exits 0 when `_config.json` has every key a Wave run needs. Otherwise it prints one `FAIL:` line per missing `wave`, `title`, `integration` or `tickets` key: Workstreams scaffolded before Waves lack them, and they still carry `_run-order.md`. Then the Workstream needs a re-scaffold with `scaffold.py .orca/prompts/<workstream>/`. It reads `**Phase**: N` in `_plan.md` as a Wave and writes `wave` and `title` back into `_config.json`. It also rewrites every `*.prompt.md`, `_orchestration.prompt.md` and `_plan.md` in the directory, so hand edits to those files are lost. Ask with the question tool before running it, naming the files it rewrites: **Re-scaffold and continue (Recommended)** or **Stop**. On re-scaffold, first ask for each missing `integration` or `tickets` key the check named, then write the answers into `_config.json`. `integration` is `commit`, `branch`, `pr` or `pr-merge` (**PR + merge (Recommended)** is `pr-merge`), and `tickets` is `true` or `false` (**No (Recommended)** is `false`). Then run the re-scaffold from the repo root, run the check again until it prints nothing, and continue to step 3. On stop, end without changing anything. Migrating by hand is out of scope.

3. **Light the band.** Run `set_status.py <dir> --start`. It marks this Workstream active and keeps the state of any Work Item already in `_status.json`, so a resumed run picks up where it stopped. It also records the run in the Run Registry, so `/orca-board` lists it. Then run `set_status.py <dir> --show` and keep its table: it is the starting state for step 4. When `<dir>/_resume.md` exists, `/orca-prepare` wrote it before a compaction or handover. Read it and every doc it lists under Read on resume, and treat its In flight section as work already dispatched, so the resume binds those workers instead of starting a second one. Last, recall what earlier Workstreams learned: when the context holds no `Orca Knowledge Graph recall` block, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-kb/scripts/kb.py review <workstream> <Work Item titles>`. Use its facts when a Work Item fails or needs a decision.

4. **Follow `_orchestration.prompt.md`.** Read it in full and run it as written: its Run, its Task and worker commands, its wait loop and its per-worker steps. Its Waves run in order. Wave N starts only after every Work Item in Wave N-1 is `complete`, so items already `complete` in `_status.json` are skipped, never re-dispatched. Items left `failed` by an earlier run are dispatched again when their Wave comes up. On a resume, run its `## Resume` step first: it stops the resume when a required doc is missing, and your first report starts with its `Read:` line. Bind the Run `_status.json` already records instead of creating one, and run `dispatch.py` with `--resume`, so it creates only the missing Tasks. Skip its Plan Gate step when `_plan-review.md` already ends `VERDICT: GO` or any Work Item in `_status.json` has left `todo`, because the first run already passed the gate. `dispatch.py` skips Work Items `_status.json` marks `complete` and lists only open Tasks in `--deps`. Keep running until step 5 holds. Stop and ask with the question tool only when a failed Work Item needs a decision you cannot make from its prompt file, or before a step the orchestration prompt does not cover.

5. **Verify the Workstream Definition of Done.** After the last Wave completes, check every condition `_plan.md` lists under `## Definition of Done`, and report each one's result. The band stays up until `/orca-execute stop` or the session ends.

## Every state change is one call

A Work Item changes state at four moments, plus the review moments when `_config.json` has `review: true`. At each one, run `set_status.py` before anything else. When a whole Wave starts at once, make the call once per Work Item. The scripts `_orchestration.prompt.md` names make some of these calls themselves.

| Moment | `set_status.py <dir> ...` |
|---|---|
| Its worker starts | `<id> in_progress` |
| Its own Definition of Done holds | `integrate.py` runs `<id> complete`, with `--pr <n>` when `integration` is `pr` or `pr-merge` |
| It fails or escalates past recovery | `<id> failed "<short reason>"` |
| A failed item is re-dispatched | `<id> in_progress` |
| Its review round `<n>` starts | `<id> review <n> <reviewer>` |
| Its reviewer signs | `<id> review <n> <reviewer> --report <report path>` |

Whenever `_config.json` `integration` opens a PR (`pr` or `pr-merge`), pass `--pr <n>` with that PR's number, so `_status.json` records it on the item. The write that completes the last item stamps `finishedAt`, and `--start` stamps `startedAt` once.

With review on, `_orchestration.prompt.md` carries a `## Work Item Review` section that runs the rounds. `NO-SHIP` moves the item back to `in_progress`, and the third one sets it `failed`, which needs the user's decision. Never mark an item complete before its last round signs `VERDICT: SHIP`.

Complete means the Work Item's own Definition of Done holds, from its prompt file. A `worker_done` alone is not the trigger when that Definition of Done also needs a merge or another step after the worker reports. Run those steps first, then mark it complete.

`_status.json` is written only through `set_status.py`. The orca-helpers mod blocks Edit and Write on it, because a hand edit can leave the band reading a half-written file.

## Stopping work you started

Use TaskStop only on background subagents this session started with the Agent tool. Orca workers belong to Orca: end them with the `worker-release` step in `_orchestration.prompt.md`.
