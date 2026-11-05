---
name: orca-pr-review
description: Run a loop in this session that reviews other people's GitHub PRs in my Watched Repos. It finds PRs that request my review or are assigned to me, claims each unclaimed one by assigning me, reviews it with an Orca review worker and posts the Review Draft. Use when the user wants to start, stop or check a PR review loop, watch or unwatch a repo for reviews, post a held review, or send feedback that has the reviewer rewrite a held review, such as "start reviewing my PRs", "watch acme/api for reviews", "stop watching this repo", "approve the draft for acme/api#12" or "tell the reviewer to drop the naming nit on acme/api#12". Its subcommands are start, stop, status, tick, watch <owner/repo>, unwatch <owner/repo>, approve <owner/repo#n>, feedback <owner/repo#n> <text>. Not for reviewing one PR by hand, which needs no loop.
argument-hint: "start | stop | status | tick | watch <owner/repo> | unwatch <owner/repo> | approve <owner/repo#n> | feedback <owner/repo#n> <text>"
disable-model-invocation: true
---

# orca-pr-review

The loop scans GitHub on a session cron, in Watched Repos only. A Watched Repo is a repo the user named at `start` or with `watch`. Each scan lists the open PRs in those repos where review is requested from the user or their team, or that are assigned to the user, plus every PR the ledger already tracks there. A PR in any other repo is never touched. `pr_review.py` classifies each PR as NEW, CLAIMED, FOLLOWUP, INFLIGHT, UNSUPPORTED or IDLE. It claims each NEW PR by assigning the user, but only when nobody is assigned.

Each claimed PR then moves one step per tick. The script dispatches a review worker in its own Orca worktree, on the Orchestration Worker Model Slot from Prompt Settings. The worker's brief carries the repo's mandatory skills, recommended skills and special instructions. The worker writes a report and a Review Draft. In auto mode the next tick posts the draft. In manual mode the draft waits until the user approves it or sends Review Feedback. Before posting, the script re-reads the assignees and drops the draft when someone else took the PR.

After the user requests changes, new commits on the PR start round 2. Its worker gets only the diff since the head the earlier round reviewed, plus that round's findings. After a post, a drop, a merge or a close, the script stops the review worker, releases it with `worker-release` and removes its worktree. A review worker whose start fails is never started again: the tick prints the failed stage and what it left behind. A review worker that stopped or sat idle at its prompt without writing its draft is cleaned up and started again, at most twice a round. The loop stops itself at its Loop End.

The script holds every decision, so the loop behaves the same in every session. Assign, comment on or review a PR only through the script, because every GitHub write lands in the user's name.

## Writing to the user

Every message to the user follows the Communication Standard, because the reader scans fast and keeps little in working memory. The rules, in short:
- Lead with the next action. Write short, plain sentences in present tense and active voice, at most 25 words each, with no hedges or pleasantries.
- Use flat lists of at most 5 items. Bold only the action or the one changed value, with no italics, capitals or emoji.
- Restate what is done and what is next. End with exactly one next step the reader can take in under 2 minutes, or say the work is done when nothing is left.
- Copy every path, command, flag, id and `FAIL:` line byte for byte. On an error, give the cause, then the fix. The full file, `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`, adds the PR comment format: read it before writing a PR comment. The lines the script prints already follow it, so relay them as they are.

## Run

The argument is `$ARGUMENTS`. `SCRIPT` below is `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-pr-review/scripts/pr_review.py`.

The script prints the final text for the user. Relay every line it prints word for word. Add text of your own only where a step below asks for it, because a reworded line can drop the exact command the user needs. A line that starts with `CHOOSE`, `SAVED`, `NEW`, `RUNNING`, `CRON` or `NO CRON` is an instruction for you instead: act on it as the steps below say, and leave it out of the reply. When `tick` prints nothing, reply with nothing, because a quiet scan is not news. When a line ends with a bold command, end the reply with that command as the one next step.

### start

1. Run `SCRIPT start`. It prints `CHOOSE current=<owner/repo> before=<a,b>`, where `none` means there is none.
2. Ask with the question tool which repo or repos to watch. Offer the current repo first, marked **(Recommended)**, then each repo in `before`. Allow several answers.
3. For each chosen repo, run `SCRIPT show <owner/repo>`, then settle its Review Settings:
   - On `SAVED`, show the lines after it and ask one question: **Use these (Recommended)** or **Change**. On Use these, the repo is done.
   - On `NEW` or Change, ask for the Loop End in hours, the cadence in minutes, the mandatory skills, the recommended skills and the special instructions. Recommend the saved value when one exists, else 8 hours, 5 minutes and none. Ask the Loop End and the cadence once, for the first repo, and reuse both answers for the other repos. The cadence divides 60 minutes, such as 5, 15 or 30, or is whole hours that divide 24, such as 120. The script refuses any other cadence, such as 45 or 90.
   - Save the answers with `SCRIPT watch <owner/repo> loopEndHours=<h> cadenceMinutes=<m> "mandatorySkills=<a,b>" "recommendedSkills=<a,b>" "instructions=<text>"`. Leave a value empty for none. Quote each pair, because instructions hold spaces.
4. Run `SCRIPT start <owner/repo> [<owner/repo> ...]` with every chosen repo. The repos it names become the only Watched Repos.
5. On `RUNNING cron=<id>`, a cron already runs in this session. Create no second one, because two crons scan twice. Skip to step 7.
6. Otherwise, call the CronCreate tool with `cron` set to the expression after `CRON `, `prompt` set to `/orca-pr-review tick`, and `recurring` set to true. Then run `SCRIPT set-cron <id>` with the job id CronCreate returned.
7. Run one tick at once, as in the tick section below, and relay the lines from steps 3 to 7.

### tick

When the context holds `orca-pr-review tick already ran in the orca-helpers hook`, the hook ran the tick: relay the lines under it and do not run the tick again. A quiet tick never reaches you, because the hook blocks its prompt.

Otherwise the classic hooks are off. Start one subagent with the Agent tool, `model` set to `haiku` (Claude Haiku 5.5), asking it to run `SCRIPT tick` and return its stdout verbatim, then relay those lines. A Haiku turn costs less than this session's model, and the cron fires every few minutes. Leave the tick to the subagent even when it fails: relay its failure line, because a second scan from this session doubles the GitHub calls. A `Review Draft ready` line names a report: read it and show its findings before the approve command. On `CRON <id>`, the Loop End passed: call the CronDelete tool with that id. The script prints each held draft and each repeated error only once.

### watch

The argument is `watch <owner/repo>`. Settle the repo's Review Settings as in start step 3. On Use these, still run `SCRIPT watch <owner/repo>` with no pairs, because only `watch` or `start` marks the repo watched. Then relay the `Watching` lines. A running loop picks the repo up on its next tick.

### stop

Run `SCRIPT stop`. On `CRON <id>`, call the CronDelete tool with that id. On `NO CRON`, delete nothing. Relay the line after it.

### approve

Run `SCRIPT approve <owner/repo#n>` only when the user asked to post that draft, because the review lands in the user's name. When the PR head moved since the review started, the script posts nothing and starts a new round on the new head. When a tick is running, `approve` and `feedback` print `FAIL: a tick, approve or feedback is running`: run the same command again after a minute.

### feedback

The argument is `feedback <owner/repo#n> <text>`, where the text is the user's Review Feedback on a held Review Draft. Pass the text on stdin through a quoted heredoc, which passes every `"`, `$` and backtick unchanged, and relay the script's line:

```
SCRIPT feedback <owner/repo#n> <<'FEEDBACK'
<text>
FEEDBACK
```

When the text itself holds a line that reads `FEEDBACK`, pick another delimiter. Pass the user's words as they wrote them, because the review worker rewrites the draft from them. Run `approve` only when the user asks to post, even when the feedback sounds final, because a review posts in the user's name.

The script sends the feedback to the PR's review worker. When that worker is gone, it starts a fresh one on the same worktree. The next tick holds the rewritten draft for `approve`, even in auto mode, and prints `Review Draft ready` once.

### unwatch

Run `SCRIPT unwatch <owner/repo>` and relay its lines. The repo leaves the Watched Repos, and its Review Settings stay saved. The script cleans up the repo's review workers. A cleanup that fails prints once, and each later tick retries it.

### Any other argument

Run `SCRIPT $ARGUMENTS` and relay its lines. `status` needs no other step. For an unknown argument, the script prints a usage line.

## Errors

A `FAIL:` line means the command stopped and changed nothing more. Give its cause, then the fix. For a timeout, the fix is to wait for the next tick. For a gh error, the fix is `gh auth status`. During a cron tick, report a `FAIL:` line once. Stay silent when the next tick prints the same line, because a repeat every few minutes buries the session.

## Review Settings

Each Watched Repo keeps its Review Settings in `review-settings.json` in the Plugin Data Dir, outside every repo. Read `references/review-settings.md` when the user asks what a setting does, or before you recommend a value in start step 3. It lists every key, its default, the Loop End cap, the GIF rules and the evidence command.
