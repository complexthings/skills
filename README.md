# complexthings/skills

Two Claude Code plugins from [Complex Things](https://github.com/complexthings):
**`orca-helpers`**, which turns a rough idea into a planned, orchestratable
workstream, and **`adhd-friendly`**, which keeps Claude's replies short and
actionable.

This repository is generated. It is the install target only — source, issues, and
pull requests live in the private build repo. Every publish replaces the entire
history with a single commit, so clone it fresh rather than pulling.

## Install

From your shell:

```bash
claude plugin marketplace add complexthings/skills
claude plugin install orca-helpers@complexthings
claude plugin install adhd-friendly@complexthings
```

Or from inside a Claude Code session:

```
/plugin marketplace add complexthings/skills
/plugin install orca-helpers@complexthings
/plugin install adhd-friendly@complexthings
```

Install only the one you want — the two plugins are independent.

Standalone skills are not part of either plugin and install separately. See
[Standalone skills](#standalone-skills).

---

## `orca-helpers`

Plans, runs and tracks [Orca](https://orca.computer) Workstreams from inside
Claude Code. A **Workstream** is a named body of work: one plan, one set of Work
Items grouped into Waves, one target branch.

Starting one by hand is the tedious part. You decide how the work splits, which
Agent Harness runs which piece and which model each slot uses. Then you write
all of it down in a shape another agent can execute. orca-helpers does that
part, runs the result, and shows the progress in a band above the prompt.

![The Wave Band during a run](images/wave-band.gif)

It needs Claude Code v2.1.287 or later (v2.1.286 in the Desktop app), Python 3
and the `orca` CLI.

### Using it

1. Run `/orca-prompt-settings` once per repo to store your defaults. This step is optional.
2. Run `/orca-prompt` and answer the interview.
3. Run `/orca-execute <workstream>` to run it now, or `/orca-prompt-scheduler` to run it later.
4. Watch the Wave Band until its Done tab opens.

### Skills

- **`orca-prompt`** interviews you (Basics, Harness, Models, Timing, then the scope) and writes `.orca/prompts/<workstream>/`: `_config.json`, `_plan.md`, one prompt per Work Item and `_orchestration.prompt.md`.
- **`orca-execute`** runs a Workstream Wave by Wave as its Main Orchestrator. You start it by typing the command.
- **`orca-prompt-settings`** stores repo-level defaults: Agent Harnesses, Model Slots, concurrency and Priority File.
- **`orca-prompt-scheduler`** schedules a Workstream as a one-shot Orca automation that fires exactly once.

`orca-prompt` settles the scope with `grill-with-docs` from Matt Pocock's
[`mattpocock-skills`](https://github.com/mattpocock/skills) when it is
installed, and with its own built-in grilling otherwise.

### The bands

The **Prompt Band** follows the `orca-prompt` interview. It walks the five
steps, keeps every answer in view under one Harness Avatar per Agent Harness,
and draws a one-row step strip above each question. At the end its **Ready**
tab shows the Work Items per Wave and the next command to run.

![The Prompt Band on the Models step](images/prompt-band.png)

![The step strip above a question dialog](images/step-strip.png)

![The Ready tab after the interview](images/prompt-band-ready.png)

The **Wave Band** follows a run. It shows up to 4 Wave slots and lists the
current Wave's Work Items under TODO, In Progress and Complete. Once every Work
Item is merged, its **Done** tab shows the run time and the PRs merged. Press
`o` on a focused band, or click its caret, to collapse it.

![The Done tab after a run](images/wave-band-done.png)

### Ambient signals

During a run, a toast reports each Wave complete, each failed Work Item and the
final merge. A status line entry and a Spinner word show the current Wave and
its count. Bands and signals draw only in the Owning Session, the session that
started the interview or the run.

### Pictures in an Orca terminal

Claude Code draws the band pictures in an Orca terminal only when
`CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1` is set. Orca sets it only for agents it
launches. In a plain Orca terminal the bands fall back to half-block text art,
and a toast names the fix.

Run **`/orca-images`** once. It adds this line to `~/.zshrc` or `~/.bashrc`,
then you restart Claude:

```bash
[[ $TERM_PROGRAM == Orca ]] && export CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1
```

![The pictures-off toast and the half-block fallback](images/orca-images.png)

The plugin's own [`README.md`](orca-helpers/README.md) covers every detail.

---

## `adhd-friendly`

Keeps Claude's replies short, actionable, and consistently shaped.

Long, meandering replies are hard to act on — the next step gets buried three
paragraphs down, and by the time you have found it you have lost the thread. This
plugin fixes the shape of the reply rather than asking you to re-read it.

Three hooks and one output style:

- A **Reply Card** prints beside every prompt, sized to that prompt. A one-line
  question gets a one-line card.
- A **Reply Meter** silently scores each finished reply and logs the result, so
  the next card can call out what slipped.
- A **session card** prints at most three lines saying where the last session
  left off.

The long rules ship as a bundled output style, loaded once per session, so the
per-turn cost stays small.

It also ships one skill:

- **`/adhd-stats`** — the scoreboard: violation trend, reply length, card tier
  distribution, and the modelled token saving.

Three optional knobs (card tier thresholds, meter on/off, strictness) are
documented in the plugin's own `README.md`. The defaults need no configuration.

---

## Standalone skills

Skills that belong to no plugin. They live under `skills/` and are not declared
in the marketplace manifest, so `claude plugin install` does not reach them.
Install one directly:

```bash
npx skills@latest add complexthings/skills --skill pi-init --agent claude-code -y
```

That installs into `./.claude/skills/pi-init/`. In an open Claude Code session,
run `/reload-skills` afterwards to pick it up.

- **`/pi-init`** — writes or updates a concise, evidence-backed root `AGENTS.md`
  for the current project. Manually invoked only.

## Layout

```
.claude-plugin/marketplace.json          plugin manifest
orca-helpers/skills/<skill>/SKILL.md     orca-helpers skill entry points
adhd-friendly/skills/<skill>/SKILL.md    adhd-friendly skill entry points
skills/<skill>/SKILL.md                  standalone skills, not in the manifest
```

## License

See the repository owner for licensing.
