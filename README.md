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

Helpers for planning and orchestrating [Orca](https://orca.computer) workstreams.

On Claude and Codex, the Main Orchestrator passes each worker's Model Slot to `worker-start --model/--effort`.

A **workstream** is a named body of work: one plan, one set of work items, one
target branch. Getting one started by hand is the tedious part — deciding how the
work splits, which agent harness runs which piece, which model each slot uses,
and then writing all of that down in a shape another agent can execute.

`orca-prompt` does that part for you. It interviews you, settles the scope, and
writes the whole `.orca/prompts/<workstream>/` directory. What you get back is a
directory an orchestrator can pick up and run: every work item has its own prompt
file, with its own model rules and its own definition of done.

### Prerequisites

`orca-prompt` settles the scope of work using `grill-with-docs`, from Matt
Pocock's [`mattpocock-skills`](https://github.com/mattpocock/skills). It is in
Claude Code's official marketplace, so there is no marketplace to add first:

```
/plugin install mattpocock-skills
```

Without it, `orca-prompt` stops after the interview and tells you to install it.

### Using it

Ask for a new workstream in plain language, or invoke the skill by name:

```
/orca-prompt
```

<!-- ![Round 1: workstream name, target branch, scope source](images/round-1-questions.png) -->

It then asks you three rounds of questions.

**Round 1 — what you are building.** The workstream name, the branch every work
item's PR merges into, and whether the scope of work already exists somewhere or
should be interviewed out of you from scratch.

**Round 2 — who does the work.** It probes your PATH for known agent harnesses
(Claude Code, Codex, Copilot, OpenCode, Pi, Prime Agent, Antigravity) and asks
which ones this workstream uses, and which one runs the main orchestrator.

**Round 3 — what they run on.** Which priority file ranks the models, then a
model and reasoning effort for each of the three slots — orchestration worker,
subagent, and subagent for simple tasks — per harness. Plus each harness's tier,
the maximum concurrency, and the workstream's reasoning level.

<!-- ![Round 3: picking a model for each slot](images/model-questions.png) -->

Then it settles the scope with `grill-with-docs`, proposes a size for every work
item for you to confirm, writes the files, and validates them.

### What it writes

Five kinds of file land in `.orca/prompts/<workstream>/`:

| File | What it is |
| --- | --- |
| `_plan.md` | The settled scope of work in prose, the orchestration rules, and one section per work item. |
| `_config.json` | The machine-readable contract: harnesses, model slots, concurrency, work item sizes. |
| `<id>.prompt.md` | One per work item — the actual brief a worker agent executes, with its own rules and completion steps. |
| `_run-order.md` | Which work items run in which phase, and what blocks what. |
| `_orchestration.prompt.md` | The brief for the main orchestrator that dispatches all of the above. |

<!-- ![The generated .orca/prompts/<workstream>/ directory](images/generated-files.png) -->

Everything after that is ordinary Orca: dispatch the work items, watch them land.

<!-- ![A workstream running across several worktrees](images/workstream-running.png) -->

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
