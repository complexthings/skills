---
name: orca-board
description: Open the Board, a local browser page listing every Workstream an orca-execute run started, across repos. `/orca-board` opens it in the system browser, `/orca-board --orca` in an Orca browser tab, and `/orca-board stop` ends its server.
argument-hint: "[--orca | stop]"
disable-model-invocation: true
---

# orca-board

The Board shows one swimlane per repo and one sub-swimlane per Workstream. The active Wave opens with To do, In progress and Complete columns and a Failed row above them. Other Waves stay collapsed until clicked. Each Work Item card shows its animated Harness Avatar, PR, time in column, model and Effort Level, and the failure reason when failed. Above the swimlanes, an Attention section lists every open Main Orchestrator question, Decision Gate and failed Work Item, each with a Jump to session button that focuses the Owning Session's Orca terminal. It also lists each Review Draft the orca-pr-review loop holds in manual mode, with its verdict, and its Jump to session button focuses the loop's session. Approving the draft there posts it and clears the item. It reads the Run Registry, which `set_status.py --start` fills on every orca-execute start and resume. The user answers questions and Decision Gates in the Owning Session, never on the page. The server's write endpoints save settings and act on held Review Drafts through the plugin scripts that own them, behind a per-server token (ADR 0017).

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment.

## Run

The argument is `$ARGUMENTS`. Run the one command it maps to:

| Argument | Command |
|---|---|
| none | `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-board/scripts/board.py` |
| `--orca` | `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-board/scripts/board.py --orca` |
| `stop` | `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-board/scripts/board.py stop` |

For any other argument, run nothing and reply with the three accepted forms, because `board.py` accepts only these.

The script starts a server on 127.0.0.1, or reuses the one already running, and opens the page. The server exits by itself 30 minutes after the page last polled it.

## Reply

Write the reply by the Communication Standard. Lead with the URL the script printed, then say whether it started a new server or reused the running one. When the script printed `Open <url>`, the page did not open by itself: tell the user to open that URL. A `FAIL:` line means nothing started: give its cause, then the fix. End with one next step.
