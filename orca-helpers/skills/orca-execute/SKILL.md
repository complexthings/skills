---
name: orca-execute
description: Run an Orca Workstream Wave by Wave as its Main Orchestrator, keeping the Task list and _status.json in step so the Wave band shows live progress. `/orca-execute <workstream>` starts or resumes; `/orca-execute stop` hides the band.
argument-hint: <workstream> | stop
disable-model-invocation: true
---

# orca-execute

Runs one Workstream from `.orca/prompts/<workstream>/` as its **Main Orchestrator**. `_orchestration.prompt.md` says how to dispatch, wait and merge. This skill adds the bookkeeping around it: every Work Item state change lands in `_status.json`, which the Wave band reads, and in a Claude Task, which is your own checklist.

The argument is `$ARGUMENTS`.

`set_status.py` is the only writer of `_status.json`. Run it as:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/set_status.py <dir> <args>
```

`<dir>` is the Workstream directory, `.orca/prompts/<workstream>/`. A `FAIL:` line means nothing was written. Fix the input it names and run it again.

## `stop`

When the argument is `stop`, or `stop <workstream>`, clear the active flag and end:

1. Pick the Workstream: the one named, or the one whose `_status.json` has `"active": true`. `--start` keeps at most one active. When none is, tell the user the band is already off and end.
2. Run `set_status.py <dir> --stop`. It prints nothing on success, and the band disappears.

Stopping hides the band only. Running workers, Tasks and Work Item states stay as they are.

`--stop` is the only thing that hides the Wave band: it stays up while a question shows. The `o` hotkey, or the band's caret, collapses it to its top bar, and collapses or expands the Prompt Band with it.

## Start or resume

1. **Resolve the Workstream.** A name maps to `.orca/prompts/<name>/`. A path is used as given. With no argument, ask with the Agent Harness question tool, one option per directory under `.orca/prompts/` holding a `_config.json`, the most recently modified marked **(Recommended)**. Done when `<dir>/_config.json` and `<dir>/_orchestration.prompt.md` both exist.

2. **Check for Wave data.** Read `_config.json`. Every `workItems[]` entry needs `wave` and `title`. Workstreams scaffolded before Waves existed have neither, and they still carry `_run-order.md`. If any entry lacks either key, the Workstream needs a re-scaffold:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-prompt/scripts/scaffold.py .orca/prompts/<workstream>/
   ```

   It reads `**Phase**: N` in `_plan.md` as a Wave and writes `wave` and `title` back into `_config.json`. It also rewrites every `*.prompt.md`, `_orchestration.prompt.md` and `_plan.md` in the directory, so hand edits to those files are lost. Ask with the question tool before running it, naming the files it rewrites: **Re-scaffold and continue (Recommended)** or **Stop**. On re-scaffold, first check `_config.json` for `integration` and `tickets`: Workstreams from before Waves lack them, and scaffold.py stops with "missing required keys". Ask for each one that is missing, then write the answers into `_config.json`. `integration` is `commit`, `branch`, `pr` or `pr-merge` (**PR + merge (Recommended)** is `pr-merge`), and `tickets` is `true` or `false` (**No (Recommended)** is `false`). Then run the command from the repo root, re-read `_config.json`, and continue to step 3. On stop, end without changing anything. Migrating by hand is out of scope.

3. **Light the band.** Run `set_status.py <dir> --start`. It marks this Workstream active and keeps the state of any Work Item already in `_status.json`, so a resumed run picks up where it stopped. Then run `set_status.py <dir> --show` and keep its table: it is the starting state for step 4.

4. **Create the Task list.** One Task per Work Item, in `_config.json` order, with the subject `Wave N · <title>`, for example `Wave 2 · Prompt Scaffolding`. Put the Work Item `id` in the description, since every later `set_status.py` call needs it. Then one final Task, subject `Definition of Done`, to verify the Workstream Definition of Done in `_plan.md`. Mirror the `--show` table: `todo` items start `pending`, `complete` items start `completed`, `in_progress` items start `in_progress`, and `failed` items stay `pending` with the reason in the description. Done when the Task count equals the Work Item count plus one.

5. **Follow `_orchestration.prompt.md`.** Read it in full and run it as written: its Run, its Task and worker commands, its wait loop and its per-worker steps. Its Waves run in order. Wave N starts only after every Work Item in Wave N-1 is `complete`, so items already `complete` in `_status.json` are skipped, never re-dispatched. Items left `failed` by an earlier run are dispatched again when their Wave comes up. On a resume, do not run its Task commands as written. Bind the existing Run instead of creating one. Create Tasks only for Work Items that are not `complete`, meaning their prompt is not in `_completed/` and `_status.json` does not say `complete`. Drop `--deps` on any Task whose previous Wave is already complete, since a `--deps` on a finished Task holds nothing back and a Task you skipped has no id to list. Otherwise it re-creates and re-dispatches finished items. Keep running until step 6 holds. Stop and ask with the question tool only when a failed Work Item needs a decision you cannot make from its prompt file, or before a step the orchestration prompt does not cover.

6. **Verify the Workstream Definition of Done.** After the last Wave completes, mark the `Definition of Done` Task `in_progress`, check every condition `_plan.md` lists under `## Definition of Done`, and mark it `completed` only when all of them hold. The band stays up until `/orca-execute stop` or the session ends.

## Every state change is two calls

A Work Item changes state at four moments. At each one, run `set_status.py` and TaskUpdate together, back to back, before anything else. When a whole Wave starts at once, make the pair of calls once per Work Item. The band and the Task list then never disagree.

| Moment | `set_status.py <dir> ...` | TaskUpdate |
|---|---|---|
| Its worker starts | `<id> in_progress` | `status: in_progress` |
| Its own Definition of Done holds | `<id> complete`, or `<id> complete --pr <n>` when `integration` is `pr` or `pr-merge` | `status: completed` |
| It fails or escalates past recovery | `<id> failed "<short reason>"` | keep the status, add `Failed: <reason>` to the description |
| A failed item is re-dispatched | `<id> in_progress` | `status: in_progress`, drop the failure note |

Whenever `_config.json` `integration` opens a PR (`pr` or `pr-merge`), pass `--pr <n>` with that PR's number, so `_status.json` records it on the item. The write that completes the last item stamps `finishedAt`, and `--start` stamps `startedAt` once.

Complete means the Work Item's own Definition of Done holds, from its prompt file. A `worker_done` alone is not the trigger when that Definition of Done also needs a merge or another step after the worker reports. Run those steps first, then mark it complete.

`_status.json` is written only through `set_status.py`. The orca-helpers mod blocks Edit and Write on it, because a hand edit can leave the band reading a half-written file.

## Stopping work you started

Use TaskStop only on background subagents this session started with the Agent tool. Orca workers belong to Orca: end them with the `worker-release` step in `_orchestration.prompt.md`.
