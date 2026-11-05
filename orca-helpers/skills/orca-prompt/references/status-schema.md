# `_status.json` schema

`.orca/prompts/<workstream>/_status.json` holds the live state of each Work Item, and the orca-helpers Wave band reads it. `scripts/set_status.py` is its only writer: run it for every change, so each write is atomic and stays in schema. `--start` builds the file from `_config.json` and marks this Workstream active, `<id> <state> [reason]` moves one Work Item, `<id> complete --pr <n>` also records its PR, `--stop` clears `active`, and `--show` prints the Wave-by-Wave table. `log <title> <body> [--commit <repo>@<sha>] [--supersedes <title>]` appends a dated entry to the Decision Log, `_decisions.md`; the module docstring gives the entry shape. `run <runId>` records the Orca Run, and `<id> task <taskId>` records an item's Orca Task. `<id> review <round> <reviewer> [SHIP|NO-SHIP]` records a Work Item Review round, and `--report <path>` in place of the verdict reads it from the report's last line, where a report without a `VERDICT:` line counts as `NO-SHIP`. A bad id or state prints a `FAIL:` line, exits non-zero and leaves the file as it was.

```json
{
  "workstream": "string — the workstream name from _config.json",
  "active": "boolean — true while the Wave band draws this Workstream; --start sets it and clears it on every sibling Workstream",
  "updatedAt": "string — ISO 8601 UTC time of the last write",
  "startedAt": "string | null — ISO 8601 UTC time the run started; a resumed --start keeps it, a finished run that reopens gets a fresh one",
  "finishedAt": "string | null — ISO 8601 UTC time of the write that made every item complete, cleared when a finished run reopens",
  "runId": "string | null — the Orca Run id from `run <runId>`; null until set, kept by --start",
  "items": [
    {
      "id": "string — matches workItems[].id in _config.json",
      "title": "string — the Work Item title shown in the band",
      "wave": "number — the Wave the item belongs to, starting at 1",
      "state": "todo | in_progress | reviewing | complete | failed",
      "reason": "string | null — why it failed; null in every other state",
      "harness": "string | null — the Agent Harness name dispatch routes the item to, from its size by the same tier rule; null without size or harnesses",
      "pr": "number | null — the PR number from `<id> complete --pr <n>`; null until set",
      "taskId": "string | null — the Orca Task id from `<id> task <taskId>`; null until set, kept by --start"
    }
  ]
}
```

`items` keeps the `_config.json` order. `--start` needs `wave` and `title` on every `workItems[]` entry, and re-running it keeps the state of items already in the file and each `pr`. One rule sets the clock, for `--start` and for a state change alike. A finished run that has an item not complete gets a fresh `startedAt` and a cleared `finishedAt`. Otherwise `startedAt` is kept, and `finishedAt` is stamped once every item is complete. Those three keys are optional, so a `_status.json` written before them still reads, and it keeps `startedAt` null rather than inventing one.

`set_status.py` refuses two transitions, so the orca-execute rules hold without a reader checking them. `complete` fails when `_config.json` has `review: true` and the item's last review verdict is not `SHIP`, and fails without `--pr` when `integration` is `pr` or `pr-merge`. `in_progress` for a Wave N+1 item fails until every item in Wave N, the nearest lower Wave, is `complete` and `_decisions.md` holds a `Wave N retro` entry.

`scripts/evidence.py <workstream-dir> <id> <worktree>` writes the Evidence Record for a Work Item Review: `<workstream-dir>/_reviews/<id>.<sha>.evidence.md` for the worktree's head SHA, a first line `Evidence Record, commit <sha>, exit <code>`, then the output of `evidenceCommand`. It skips when that file exists, and prints `skip: no evidenceCommand` when the command is `null`.
