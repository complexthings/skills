# orca-helpers

Run **`/orca-prompt`** to plan an [Orca](https://orca.computer) Workstream,
then **`/orca-execute <workstream>`** to run it.

A Workstream is a named body of work: one plan, one set of Work Items
grouped into Waves, and one target branch. Every file for it lives under
`.orca/prompts/<workstream>/`.

orca-helpers is a Claude Code mod. It ships nine skills, a hooks module and a
set of classic Claude Code hooks. The skills plan, run, review, schedule and
remember each Workstream. The hooks draw two bands above the prompt and guard
the files those bands read.

![The Wave Band during a run](../images/wave-band.gif)

## Requirements

- Claude Code v2.1.287 or later in the terminal, or v2.1.286 in the Desktop app. Older versions load the skills but not the bands or the hooks.
- Python 3 on `PATH`, for the skill scripts.
- The `orca` CLI, for dispatch and scheduling.

## Install

```bash
claude plugin marketplace add complexthings/skills
claude plugin install orca-helpers@complexthings
```

Run **`/reload-plugins`** in every session that was already open. Inside an
Orca terminal, also run `/orca-images` once. See
[Pictures in an Orca terminal](#pictures-in-an-orca-terminal).

## Use it

1. Run `/orca-prompt-settings` once per repo to store your Agent Harnesses, models and concurrency. This step is optional.
2. Run `/orca-prompt` and answer the interview. It writes `.orca/prompts/<workstream>/`.
3. Run `/orca-execute <workstream>` to run it now, or `/orca-prompt-scheduler` to run it later.
4. Watch the Wave Band. It ends on the Done tab once every Work Item is merged.
5. Run `/orca-board` to see every Workstream across repos in a browser.

## Skills

Plan and run:

- **`orca-prompt`** interviews you and writes the Workstream. See [orca-prompt](#orca-prompt).
- **`orca-execute`** runs a Workstream Wave by Wave as its Main Orchestrator. See [orca-execute](#orca-execute).
- **`orca-prepare`** readies a running Workstream for compaction or handover, and prints the `/orca-execute <workstream>` line that resumes it.
- **`orca-prompt-settings`** stores repo defaults in `.orca/prompts/prompt-settings.json`, so `orca-prompt` stops asking for them.
- **`orca-prompt-scheduler`** schedules a Workstream's `_orchestration.prompt.md` as a one-shot Orca automation. A Once-Guard makes it fire exactly once.

Watch and remember:

- **`orca-board`** opens the Board, a local page for every Workstream across repos. See [The Board](#the-board).
- **`orca-pr-review`** runs a loop in your session that reviews other people's PRs in the repos you watch. See [orca-pr-review](#orca-pr-review).
- **`orca-bootstrap`** creates the repo's Orca Knowledge Graph under `~/.claude/orca-helpers/kb/<owner__repo>/`. It writes nothing inside the repo.
- **`orca-kb`** reads and writes that graph: `/orca-kb review <task>`, `/orca-kb update <slug>` and `/orca-kb lint`.

Every skill writes to you by one Communication Standard. It puts the next
action first, keeps sentences short and plain, and ends with one next step. The
full rules live in `references/communication-standard.md`.

## orca-prompt

Run **`/orca-prompt`** and answer each question. Each question marks one
answer (Recommended), so you accept a good default in one click.

### What it writes

`orca-prompt` writes these files under `.orca/prompts/<workstream>/`:

- `_config.json`: the answers, the Work Items and their Waves. The schema is `skills/orca-prompt/references/config-schema.md`.
- `_plan.md`: the Scope of Work, the Definition of Done, the Orchestration Rules and one section per Work Item.
- `<id>.prompt.md`: one prompt per Work Item, which one Orchestration Worker runs.
- `_orchestration.prompt.md`: the Main Orchestrator's brief. `_rules.md` holds the Global Rules once for every prompt.
- `_decisions.md`: an empty Decision Log. With `planGate` on, it also writes `_plan-gate.prompt.md`.

`scaffold.py` writes every file except `_config.json` and `_plan.md`. A
re-scaffold rewrites the prompts, so a hand edit to a `*.prompt.md` file is
lost. Edit `_plan.md` or `_config.json` instead, then scaffold again.

### The interview

The interview always runs, even when the scope looks obvious. Say "skip the
interview" in the invoking message to skip it. The skipped answers then land
in `_plan.md` under `Assumed, not asked`.

1. Basics: the Workstream name, the target branch, the integration (`commit`, `branch`, `pr` or `pr-merge`), tracker tickets, and where the Scope of Work comes from.
2. Harness: which Agent Harnesses do the work, and which one runs the Main Orchestrator. Stored Prompt Settings fill this round, and you keep them or override them.
3. Models: the Priority File and the Main Orchestrator model. Then three Model Slots per Agent Harness, one effort each, a tier per Agent Harness, and the maximum concurrency.
4. Timing: Work Item Review, the Plan Gate, the evidence command, the budget in USD, the Task Time, and whether to run now or schedule it.
5. Scope: `grill-with-docs` interviews you until every Work Item is named, sized and placed in a Wave. Without it, the built-in grilling procedure runs instead.

### The Prompt Check

After scaffold, `orca-prompt` reads the new Workstream the way each worker
does: cold, with no memory of the interview. It runs once and never loops.

1. `check_paths.py` prints one `FAIL:` line per path, script or command that the files name but that does not exist.
2. Three Goldfish Readers run in parallel, on Sonnet 5.5 medium, Haiku 5.5 high and Opus 5.5 low. Each reads `_plan.md`, `_orchestration.prompt.md` and every Work Item prompt once.
3. Their findings merge into one list sorted by severity. `orca-prompt` fixes the small gaps itself and asks you about each decision.
4. `validate.py` runs last. A clean run prints `ok: workstream meets the Definition of Done`, and only then can a Workstream run or be scheduled.

### Use it well

- Write a sharp Scope of Work. Name each file, script or page a Work Item changes, so the worker reads the right code first.
- Write a Definition of Done someone can check: a test that passes, a command that prints `ok`, a page that shows a value. "Works well" is not checkable.
- Size Waves by shared files. Work Items that edit the same file go in separate Waves, or they spend a round on merge conflicts.
- Pick a Task Time that fits the work. `low` is under 5 minutes per Task, `medium` under 10 and `high` under 15. `xhigh` is under 30, and `ultra` 30 or more.
- Fill every Model Slot. Each Orchestration Worker can start subagents on its Subagent Model, and on its Simple Tasks model for lookups and mechanical edits.

Run **`/orca-prompt-settings`** first when you start many Workstreams in one
repo. Rounds 2 and 3 then turn into one keep-or-change question.

## orca-execute

Run **`/orca-execute <workstream>`** to start or resume a run. Claude never
starts it on its own: you type the command.

### What the Main Orchestrator does

The session that runs `/orca-execute` becomes the Main Orchestrator. It
follows `_orchestration.prompt.md` and records every state change with
`set_status.py`.

1. It creates one Orca Run and one Task per Work Item, and starts one Orchestration Worker per ready Task in its own worktree.
2. Each worker runs its `<id>.prompt.md`, opens its PR and sends `worker_done`.
3. With Work Item Review on, a reviewer signs SHIP or NO-SHIP on the diff before anything merges.
4. On SHIP, the Main Orchestrator merges the PR, releases the worker and removes its worktree.
5. After the last Wave, it checks the Definition of Done in `_plan.md` and writes the lessons to the Orca Knowledge Graph.

### Waves and the Wave Band

Waves run in order. Wave N starts only after every Work Item in Wave N-1 is
merged. After each Wave, the Main Orchestrator writes a Wave Retro to
`_decisions.md`: the rule, test or doc that prevents each failure next time.

The Wave Band above the prompt shows the run. It reads
`.orca/prompts/<workstream>/_status.json` every 2 seconds, so it comes back
after `/resume` or in a new session.

- The top bar shows an animated orca, the Workstream name, up to 4 Wave slots with `(complete/total)` counts, and a `+N More Waves` slot.
- The body lists the current Wave's Work Items under TODO, In Progress and Complete, each with its Harness Avatar. A failed item stays in In Progress in red, with its reason.
- An In Progress card draws a progress bar, `done/total` and the worker's latest note. With review on, a Reviewing column shows the reviewer's Harness Avatar.
- Click a Wave slot to pin it. Press **`o`** in the focused band, or click the caret, to collapse it. Focus the band with Ctrl+X then Tab.
- Press **`b`** to open the Board, or **`c`** to copy the run as Markdown. Each key also has a button.

Once every Work Item is complete, the Done tab opens. Its card shows the run
time, every Harness Avatar, the PRs merged and the path to `_decisions.md`.

![The Done tab after a run](../images/wave-band-done.png)

### Work Item Review and fix rounds

Before a Work Item merges, one reviewer signs SHIP or NO-SHIP on its diff. The
reviewer comes from a different Agent Harness than the author. Review is on
unless the Workstream sets `review: false`.

- Only a finding with a Demonstrated Failure blocks: a test, input or command that goes red on the reviewed commit. Every other finding is a suggestion.
- On NO-SHIP, a fresh worker starts in the author's worktree and fixes the findings. The reviewer never fixes. Then the next round starts.
- The third NO-SHIP fails the Work Item. The Main Orchestrator then asks you how to go on.
- With `evidenceCommand` set, such as `pnpm test`, the Main Orchestrator runs it once per reviewed commit. Reviewers read that Evidence Record and never run tests themselves.
- With `planGate: true`, a reviewer signs GO or NO-GO on `_plan.md` before Wave 1. A NO-GO asks you to revise the plan or start anyway.

### Resume and `/orca-prepare`

Run **`/orca-prepare`** before a compaction or a handover. It files the facts
held only in the session to `_decisions.md` and writes Resume State to
`_resume.md`. Then it prints the paste-ready `/orca-execute <workstream>` line.

Run that line in any session to resume. The resume reads `_plan.md`,
`_orchestration.prompt.md`, `_decisions.md` and `_status.json` first. It skips
every Work Item already complete and binds the workers still in flight. Its
first report starts with a `Read:` line that names every doc it read.

### `stop` and `copy`

- **`/orca-execute stop`** hides the Wave Band. Running workers and Work Item states stay as they are.
- **`/orca-execute copy`** copies the run as Markdown: each Wave, its Work Items with state and PR, and its progress. A toast confirms.

### What to watch while it runs

- A question from the Main Orchestrator. The run waits until you answer it.
- A red item in In Progress. Its reason names what failed.
- A third NO-SHIP. The Work Item fails, and the Main Orchestrator asks you how to go on.
- Spend on the Board. Nothing stops a run that passes its `budgetUsd`.
- The Done tab. It opens once every Work Item is merged.

## The Prompt Band

While `orca-prompt` interviews you, a band above the prompt follows along.
`set_prompt_band.py` records every step and answer in
`.orca/prompts/_prompt-band.json`. The band reads that file every 2 seconds.

![The Prompt Band on the Models step](../images/prompt-band.png)

- The left column walks the five steps: Basics, Harness, Models, Timing, and Write / Validate. Done steps show a checkmark, and the current one an animated wave.
- The right side keeps every answer in view, under one Harness Avatar per Agent Harness. A crown marks the harness that runs the Main Orchestrator.
- Click a done step to pin it. While an interview is live, the Prompt Band takes the Wave Band's place.
- A one-row step strip draws above each question dialog, so the interview stays in view while you answer.
- At the end, a Ready tab shows the Work Items per Wave, how the work lands, and the next command to run.

![The step strip above a question dialog](../images/step-strip.png)

![The Ready tab after the interview](../images/prompt-band-ready.png)

## The Decision Log

Each Workstream keeps a Decision Log in `_decisions.md`: the dated record of
what its Main Orchestrator decided and learned. Add an entry with
`set_status.py <workstream-dir> log <title> <body>`. A changed fact gets a new
entry with `--supersedes <title>`, and the old entry stays.

## The Board

Run **`/orca-board`** to open the Board in your browser, or
`/orca-board --orca` to open it in an Orca browser tab. Run `/orca-board stop`
to end its server.

The server binds to 127.0.0.1 and exits 30 minutes after the page last polled
it. The Status Page opens first and covers every repo. Click a repo in the
sidebar to open its Repo Status Page.

![The Board's Waves tab](../images/board-waves.png)

### The pages

- The sidebar lists each repo with a Wave progress bar, its spend against its budget with a thin meter, and an attention count, and a Needs you list below. On a phone it turns into a repo dropdown, with the active Workstreams in a strip that scrolls sideways.
- The top bar shows the poll state on the left and a Light and Dark switch on the right.
- The Status Page opens with a Needs you list: gates, Review Drafts, PRs awaiting changes, NO-SHIP reviews and failed Work Items. Each row clicks, with an action word on the right: Approve, Open or Jump. Merged and closed PRs never appear there. The usage chart and the Spend panel sit below it.
- The usage chart stacks cost, tokens or time per model over wall-clock time, with numbered Wave flags. The Spend panel meters each Workstream against its `budgetUsd`.
- The Repo Status Page has three tabs: Waves, Reviews and Config.

![The Board's Usage tab](../images/board-usage.png)

### The Repo Status Page tabs

- Waves shows one swimlane per Workstream, with a Wave timeline and a Kanban per Wave. Finished and Planned Workstreams sit under their own dividers.
- A Work Item card shows its state, id, title, Harness Avatar, PR, progress and cost. A Reviewing card is amber with a gold beam.
- Reviews lists the repo's `orca-pr-review` PRs with CI pills and an age bar. A held draft has a **Review draft** button. Its modal has Publish Review and Adjust Review.
- Config edits the repo's Prompt Settings, its Repo Name and its Task Time. A Workstream's own overrides open in a modal with one Override switch per section.
- A repo with PR review off shows a **Turn on** action with the `/orca-pr-review watch <owner/repo>` and `/orca-pr-review start` commands.

### How the Board saves

The Board saves only through the plugin scripts that own each file (ADR
0017). Every POST carries the server's token, and a request without it gets
403. A request from any host other than `127.0.0.1:<port>` or
`localhost:<port>` also gets 403.

- Settings go through `write_settings.py`, and Workstream overrides through `write_workstream_config.py`. A running Workstream refuses overrides.
- Publish Review runs `pr_review.py approve`. Adjust Review runs `pr_review.py feedback`, and the rewritten draft stays held.
- A run in an Orca worktree groups under its repo's main checkout. Rename a repo in the Config tab, which writes `repo-names.json` in the Plugin Data Dir.
- Finished Workstreams stay for the Recent Window: set `recentWindowHours` in `settings.json` in the Plugin Data Dir, 120 by default.

## orca-pr-review

Run **`/orca-pr-review start`** to begin the loop. It asks which repos to
watch, the Loop End in hours and the cadence. Then it asks each repo's
mandatory skills, recommended skills and special instructions.

Each tick lists the open PRs in Watched Repos that request your review or are
assigned to you. The loop claims a PR only when nobody is assigned. It starts
a review worker in its own Orca worktree, which writes a report and a Review
Draft.

- In manual mode a draft waits until you run `/orca-pr-review approve <owner/repo#n>`. In auto mode it posts on the next tick.
- Run `/orca-pr-review feedback <owner/repo#n> <text>` to have the worker rewrite a held draft. The new draft stays held, even in auto mode.
- Before it posts, the loop re-reads the assignees. A PR someone else took drops its draft, and a PR whose head moved is skipped.
- New commits after you request changes start round 2, which reviews only the diff since the last reviewed head.
- `status` prints the ledger, `tick` runs one scan, `watch` and `unwatch <owner/repo>` change the Watched Repos, and `stop` ends the loop.

The loop stops itself at its Loop End, and the session cron expires after 7
days. After a post, a drop, a merge or a close, the loop removes the worker and
its worktree.

Review Settings live in `review-settings.json` in the Plugin Data Dir, outside
every repo, keyed by `owner/repo`:

```json
{"owner/repo": {"watched": true, "mode": "manual", "gifs": false, "cadenceMinutes": 5, "loopEndHours": 8,
                "mandatorySkills": [], "recommendedSkills": [], "instructions": "", "evidenceCommand": "pnpm test"}}
```

A missing key reads as unwatched, manual mode, GIFs off, 5 minutes, and a Loop
End after 8 hours. It also means no skills, instructions or evidence command. With
`gifs: true`, each posted review ends with one GIF from
`skills/orca-pr-review/references/gifs.json`.

## Ambient signals

While a Workstream runs, three signals report progress outside the band:

- A toast on each Wave complete (`Wave 2 complete: 3 PRs merged`), on each failed Work Item with its reason, and once all Waves are merged.
- A status line entry such as `orca my-workstream W2 2/4 · 1 failed`. It clears once `set_status.py --stop` ends the run.
- A Spinner word such as `Wave 2 · 2/4 merged`, shown while Claude works.

Bands and signals draw only in the Owning Session: the session that last ran
`set_prompt_band.py begin` or `set_status.py --start`. Other sessions on the
same repo stay quiet.

## Pictures in an Orca terminal

Run **`/orca-images`** once, then restart Claude. It appends this line to
`~/.zshrc` for zsh or `~/.bashrc` for bash:

```bash
[[ $TERM_PROGRAM == Orca ]] && export CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1
```

Claude Code draws pictures in an Orca terminal only with
`CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1` set. Orca sets it only for agents it
launches, so a plain Orca terminal lacks it. Without it, the bands draw each
icon as half-block text art, and a toast names the fix.

`/orca-images` skips the write when the line is already there. For any other
shell it prints the line for you to add. The Desktop app needs none of this.

![The pictures-off toast and the half-block fallback](../images/orca-images.png)

## The Orca Knowledge Graph

Run **`/orca-bootstrap`** once per repo. It creates the store under
`~/.claude/orca-helpers/kb/<owner__repo>/` and backfills it from every
`.orca/prompts/*/_decisions.md`. It is safe to run twice.

- `/orca-kb review <task>` recalls facts for a task. During orca work, a hook does this for you.
- The Main Orchestrator's last step writes each Workstream's lessons with `/orca-kb update`, so the next Workstream recalls them.
- `/orca-kb lint` runs a read-only health check.

## Hooks

The mod module (`hooks/register.tsx`) and the classic hooks in
`hooks/hooks.json` load side by side (ADR 0016). Run `/reload-plugins` after an
update to load both.

Guards:

- State file guard denies Edit, Write and Bash writes on `_status.json`, `_prompt-band.json`, `prompt-settings.json` and a Workstream's `_config.json`. It names the script that owns each file.
- PR write guard denies `gh pr review`, `gh pr comment`, `gh pr edit --add-assignee` and `gh api` PR review or comment calls, so `pr_review.py` posts them. Comments and review replies on a PR the signed-in `gh` user authored pass.
- Attention capture records an open question in `_status.json` during a run, so the Board lists it. Only Claude Code has this capture today (ADR 0014).

Context and checks:

- Recall injects Orca Knowledge Graph facts while an orca skill runs or a Workstream is active. Anywhere else it prints nothing.
- Quiet review tick runs `/orca-pr-review tick` as a script. A tick with nothing to report spends no model turn.
- Scaffold check runs `validate.py` and ticks the Prompt Band after a clean `scaffold.py`.
- Hooks check answers the prompt `orca-hooks-check` with "orca-helpers classic hooks are live." and spends no model turn.
- Stale settings warning prints one line at session start when `prompt-settings.json` names a model its Priority File does not rank.

The Harness Avatars cover Claude Code, GitHub Copilot, OpenCode, Codex, Pi and
Antigravity.

## Changes in 0.10.0

0.10.0 closes the orca-helpers-mod-11 Workstream. It syncs orca-helpers with Orca CLI 1.4.243 and moves fixed steps out of prose into scripts, hooks and guards.

- CLI sync: every script resolves the Orca executable through `orca_cli.py` (`ORCA_CLI_COMMAND` overrides it). Generated prompts match Orca 1.4.243 and load no guide with `--full` (#326, #333).
- New orchestrator scripts: `integrate.py`, `dispatch.py` and `finish_work_item.py` merge, dispatch and close Work Items. `evidence.py` runs the evidence command. `schedule.py` schedules a Workstream (#330, #331, #329).
- `set_status.py` refuses bad transitions and stores `runId` and `taskId`. `pr_review.py` follows the recovery and release rules (#329, #328).
- Interview helpers: `set_prompt_band.py answers`, `write_settings.py --read --check` and `write_workstream_config.py --new` (#332).
- New hooks in `workstream_hook.py`: Stop blocks once until every Wave retro, the lessons page and worker cleanup exist. Resume and PreCompact keep `_resume.md` current (#327).
- New guards: `_decisions.md` is written only by `set_status.py log`, `_resume.md` only by `prepare.py`. `orca worktree rm` on a worktree with unsaved work denies (#327).
- The Board tab shows the orca-helpers icon (#337). `scaffold.py` imports on Python 3.9 again.

## Changes in 0.9.3

- The Reviews tab keeps merged and closed loop reviews for `recentWindowHours`, and lists the PRs you reviewed by hand on Watched Repos with a quiet "You" marker (#308, #309, #314).
- Rows show the PR, its state and its age. Merged rows are grey. A draft-ready row gets a soft cyan tint.
- The Board uses a cyan accent, thin separators, soft shadows and calm motion. No card has a colored left rail (#310).
- The Spend card shows one number. A Running agents card counts the agents at work, and its amber "waiting on you" link scrolls to the Needs you panel (#311).
- Today's pace chart draws spend against the day and the budget (#312). Work Item cards, the sidebar and Needs you take the new look (#313).

## Changes in 0.9.2

- The owner hook no longer creates `$D/` or `$W/` directories. A script dir the shell expands, such as `$D`, `~` or a glob, claims nothing in the hook. The script still writes its own `.owner` file.
- The hook writes a `.owner` file only beside the state file the script wrote, so it never creates a directory.

## Changes in 0.9.1

- The PR write guard lets you comment on your own PRs and reply to their reviewers (#304). It asks `gh` who you are and who authored the PR.
- Reviews, assignments and comments on other people's PRs still deny. So does a comment whose PR number the guard cannot read, and any `gh` error.
- A body or heredoc that only mentions a blocked command no longer trips the guard.

## Changes in 0.9.0

0.9.0 closes the orca-helpers-mod-9 Workstream. Patch releases 0.8.1 to 0.8.3
shipped each Wave. In sum:

- The Board is rebuilt around a repo sidebar, a Status Page and a Repo Status Page. It adds a usage chart, a Spend panel, swimlanes, a Reviews tab and a Config tab.
- The Board saves settings, Repo Names and Workstream overrides, and publishes or adjusts held Review Drafts. Every write needs the server's token.
- `orca-pr-review` takes Review Feedback on a held draft and posts more safely.
- `orca-prompt` asks a Task Time, tells workers they can use their subagent Model Slots, and starts fix rounds in a fresh worker.
- The scripts share one atomic writer and one origin parser, and this README follows the Communication Standard.

## Upgrading to 0.8.0

- Run **`/orca-pr-review start`** again. `orca-pr-review` now reviews only Watched Repos, so no repo is watched until you do.
- The plugin now ships classic Claude Code hooks (ADR 0016) beside its mod module. Run `/reload-plugins` in open sessions to load them.
- Agents can start `/orca-bootstrap` on their own. It writes only under `~/.claude`.

## Changes in 0.8.3

- The Board has a usage chart and a Spend panel. Set a budget opens the budget field in the Config tab.
- Swimlanes fold per Workstream, with Wave dots and a Wave timeline. Work Item cards show a gold beam while in review.
- The Reviews tab lists held Review Drafts. Its draft modal has Publish Review and Adjust Review buttons.
- The Config tab and the Workstream config modal edit Prompt Settings and Workstream overrides. A switched-off override follows the repo default.
- One atomic file writer and one origin parser, `repo_slug`, serve `scaffold.py`, `set_status.py`, `prepare.py`, `pr_review.py` and `kb.py`.

## Changes in 0.8.2

- The Board has a sidebar, a top bar, a Status Page and a Repo Status Page. Click the logo or All to open the Status Page.
- `orca-pr-review` posts more safely. It skips a PR whose head moved, runs no evidence for fork PRs, drops merged PRs from the ledger, and holds one lock across tick, approve and feedback.
- The PR review guard splits each Bash command into shell words. Quoted and attached `gh api` write flags are denied, and reads still pass.
- `set_status.py` takes a lock for each write. `scaffold.py` quotes Task titles and rejects an empty or repeated `workItems` list.
- `check_conflicts.py` follows the cron rule for day fields, and the Wave Band shows the reviewing state.

## Changes in 0.8.1

- The Board groups every run under its main checkout, so a run in a worktree such as `main-2` shows under its repo. Live usage and spend now count for those runs.
- The Board server accepts writes only with its token and its own Host. Six write endpoints call the owning scripts: Prompt Settings, Workstream config, Repo Names, approve, feedback and refresh.
- `pr_review.py feedback <owner/repo#n>` sends the Review Feedback it reads on stdin on a held draft. The rewritten draft stays held, even in auto mode.
- `orca-prompt` asks for a Task Time, from `low` to `ultra`, and writes it into every Work Item prompt. Fix rounds start a fresh worker in the author worktree.
- The Orca Knowledge Graph names each Decision Log entry after its Workstream, so two Workstreams with a `Wave 1 retro` no longer share a node. Rebuilds write through a temp file.

## Changes in 0.8.0

- Added the Orca Knowledge Graph: `/orca-bootstrap` creates and backfills a per-repo store under `~/.claude`, and `/orca-kb` reviews, updates and lints it.
- Added the Prompt Check: `check_paths.py` and three Goldfish Readers read a new Workstream cold before validate.
- `orca-pr-review` reviews only Watched Repos. `start` asks the repos, Loop End and cadence, then per-repo skills and instructions, saved in Review Settings. New `watch` and `unwatch` verbs, and the loop stops itself at its Loop End.
- Classic hooks: Orca Knowledge Graph recall during orca work, a quiet review tick that costs no model turn, and validate after scaffold.
- New guards: Bash writes into the state files and PR review writes outside `pr_review.py` are denied.
- The Board is rebuilt: Waves Kanban with a Reviewing column, a Usage chart, budget and concurrency meters, a header toast stack, and A/B layouts. `_config.json` gains an optional `budgetUsd`.
- Shorter prompts: Work Item prompts point at one `_rules.md`, and each skill carries a five-line Communication Standard digest.

## Changes in 0.7.0

- Added the Board: `/orca-board` opens a local page with every Workstream across repos, an Attention section with Jump to session buttons, per-item cost and tokens, and the Reviews Tab.
- Added Work Item Review: a reviewer from another Agent Harness signs SHIP or NO-SHIP before integrate, with an Evidence Record per reviewed commit and an optional Plan Gate before Wave 1.
- Added `orca-pr-review`: a session loop that claims, reviews and posts reviews of PRs that request your review, in manual or auto mode.
- Added `orca-prepare` and the Decision Log: `_decisions.md` with a Wave Retro after each Wave, Resume State in `_resume.md`, and a `Read:` attestation on resume.
- Workers report progress with `set_status.py ... progress`, and the Wave Band draws it as a bar. The Wave Band also gains a Reviewing column and Board and Copy buttons.
- Every skill follows one Communication Standard when it writes to you.

## Changes in 0.6.3

- A failed Work Item stays in the In Progress lane, drawn red with its reason, instead of a row above the columns.

## Changes in 0.6.2

- The Wave Band shows however the `set_status.py --start` command reads, shell variables included. The scripts now record the Owning Session themselves.
- Work Items in one Wave never share an avatar color, up to seven per Wave. The colors still change from Wave to Wave.

## Changes in 0.6.1

- Bands draw in a plain Orca terminal. With pictures off, the Prompt Band, the step strip and the Wave Band draw half-block Raster art instead of alt text.
- A toast shows once per session when pictures are off, and `/orca-images` adds the `CLAUDE_CODE_FORCE_TERMINAL_IMAGES` export to `~/.zshrc` or `~/.bashrc`.
- A chained `set_prompt_band.py begin` or `set_status.py --start` command now claims the band.
- The Prompt Band shows no gap above the Harness Avatars, and each Model Slot sits on its own untruncated line.
- The Wave Band header draws on one row.
- READMEs for the plugin, the skills-build repo and the published skills repo, with screenshots.

## Changes in 0.6.0

- The Wave Band takes the refined-columns layout, with a header rule that draws as one line on Desktop and Harness Avatars large enough to read in the TUI.
- The Prompt Band is a stepper, and a one-row step strip inside the question dialog keeps the interview in view.
- The Prompt Band ends on a Ready tab and the Wave Band ends on a Done tab, each with a summary card.
- A toast on Wave complete, item failed and all merged, plus a status line entry and a Spinner word.
- Bands and ambient signals draw only in the Owning Session, the session that last ran `set_prompt_band.py begin` or `set_status.py --start`.
- `_status.json` records each Work Item's `pr`, `startedAt` and `finishedAt`.
- Fixes from five code-review rounds over the whole plugin.

## Changes in 0.5.1

- Codex Harness Avatars are the logo cloud with two feet, in all 48 strips and states.
- Pi Complete strips keep the `i` at its Todo and In Progress height.
- The Prompt Band shows during an orca-prompt interview while a Workstream is active, and the Wave Band returns at `end`.
- Band pictures draw in the Orca terminal again, and each Wave Band Work Item shows its Harness Avatar.
- Fixes from five code-review rounds over the whole plugin.

## Changes in 0.5.0

- Added the Wave Band Harness Avatars: Todo, In Progress and Complete for all six Agent Harnesses, in seven Avatar Moods, at 18x18 and 24x24.
- The Wave Band uses the Mod Part 2 icons and shows each Work Item's Harness Avatar. Only one band draws at a time, and both share one collapse toggle.
- orca-prompt ranks the new model set and discovers Copilot models.
- Final review fixes: Copilot is the helmet head from its logo, every Complete keeps its harness's body proportions, Codex is back to its original design, and Antigravity carries its logo gradient.

## Changes in 0.4.0

- Added the Prompt Band, the picked step icons, the animated orca and the six Harness Avatars.
- Removed the separate prime harness role. The Main Orchestrator settings cover it.
- Removed the reasoning-level question and `reasoningLevel`. Each Model Slot now carries its own effort, and old Prompt Settings still read: `reasoningLevel` is ignored.
- Timing moved to Round 4, before the scope interview.
