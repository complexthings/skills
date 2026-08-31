# complexthings/skills

Agent skills and Claude Code plugins published by [Complex Things](https://github.com/complexthings).

Two plugins live here. **`orca-helpers`** turns a vague "we should build this" into
a complete, ready-to-run Orca workstream. **`adhd-friendly`** keeps Claude's replies
short, scannable, and consistently shaped so you can actually read them.

Both are free, both are stdlib-Python only, and neither phones home.

> This repository is generated. It is the install target only — source, issues, and
> pull requests live in the private build repo. Every publish replaces the entire
> history with a single commit, so clone it fresh rather than pulling.

## Install

Add the marketplace once, then install whichever plugins you want.

```bash
claude plugin marketplace add complexthings/skills
claude plugin install orca-helpers@complexthings
claude plugin install adhd-friendly@complexthings
```

The same three steps from inside a Claude Code session:

```
/plugin marketplace add complexthings/skills
/plugin install orca-helpers@complexthings
/plugin install adhd-friendly@complexthings
```

Prefer the `skills` CLI, or using these outside Claude Code?

```bash
npx skills@latest add complexthings/skills --agent claude-code -p -y
```

To update later, re-run `claude plugin marketplace update complexthings` and
reinstall. To remove a plugin, `claude plugin uninstall orca-helpers@complexthings`.

---

## `orca-helpers`

**Plan a whole multi-agent workstream in one conversation, then let Orca run it.**

Orchestrating several agents across several worktrees is mostly a planning problem.
Who does what, in what order, on which model, merging into which branch — get that
wrong and you spend the afternoon untangling half-finished branches. `orca-helpers`
does that planning with you, in a structured interview, and writes the whole thing
to disk as files Orca can execute.

### Why you'd want it

- **No blank page.** It interviews you instead of asking you to write a plan.
- **It knows what you have installed.** It probes your machine for Claude Code,
  Codex, Copilot, OpenCode, Pi, Prime Agent and Antigravity, and only offers the
  ones actually on your `PATH`.
- **Model picks that aren't guesses.** Every model and effort-level suggestion comes
  from a ranked dataset, with the known traps called out (some models genuinely get
  *worse* at higher effort — it will tell you which).
- **Cheap where cheap is fine.** Separate model slots for the orchestrator, ordinary
  subagents, and simple mechanical subagents, so you are not paying frontier prices
  to rename a file.
- **It checks its own work.** A validator runs at the end and tells you plainly
  whether the workstream is complete.

### How to use it

Just ask, in any Claude Code session:

```
/orca-prompt
```

or simply say *"start a new workstream"*, *"plan this as a workstream"*, or
*"orca-prompt"*. If you have already described what you want earlier in the
conversation, it uses that as the starting point.

It then asks you a handful of questions in three short rounds. Every question has a
recommended answer marked **(Recommended)**, so pressing through the defaults gets
you a sensible workstream.

**Round 1 — the basics**
1. Workstream name (it proposes one from what you have already said)
2. Target branch everything merges into
3. Whether to interview you from scratch or start from something you already wrote

**Round 2 — who does the work**
1. Which agent harnesses to use (only the ones you have installed)
2. Which harness runs the Main Orchestrator

**Round 3 — models and limits**
1. **Which model dataset to rank by** — *opinionated picks* (recommended) or
   *rankings seeded from DeepSWE / ArtificialAnalysis.ai data*
2. A model per slot, per harness: orchestrator, subagent, simple subagent
3. Effort-level overrides, harness tier, max concurrency, reasoning level

Then it grills you on the actual scope until every work item is named, sized, and
unambiguous — and finally scaffolds the files.

_Screenshot: the Round 1 questions in Orca_

<!-- ![orca-prompt Round 1](docs/images/orca-prompt-round-1.png) -->

_Screenshot: the model dataset and model-slot questions_

<!-- ![orca-prompt model questions](docs/images/orca-prompt-models.png) -->

### What you get

Everything lands under `.orca/prompts/<workstream>/`:

| File | What it is |
| --- | --- |
| `_plan.md` | The settled scope in prose, the orchestration rules, and one section per work item |
| `_config.json` | The machine-readable contract: harnesses, model slots, branch, concurrency, work item sizes |
| `<id>.prompt.md` | One ready-to-run prompt per work item |
| `_run-order.md` | What runs in which phase, and what blocks what |
| `_orchestration.prompt.md` | The prompt you hand the Main Orchestrator to kick the whole thing off |

Hand `_orchestration.prompt.md` to your orchestrator and the workstream runs: each
work item gets its own worktree, its own model, and its own PR back into your target
branch.

_Screenshot: the generated `.orca/prompts/<workstream>/` files_

<!-- ![generated workstream files](docs/images/orca-prompt-output.png) -->

_Screenshot: the workstream running in Orca_

<!-- ![workstream running](docs/images/orca-prompt-running.png) -->

### Skills in this plugin

- **`orca-prompt`** — the whole flow above: interview, scope, scaffold, validate.

---

## `adhd-friendly`

**Makes Claude answer the way you actually read.**

Long replies are a tax. You asked one question and got six paragraphs, three of which
restate your question back at you. `adhd-friendly` fixes that at the harness level,
not by nagging in a prompt you have to keep repeating.

### Why you'd want it

- **Replies get shorter and land the action first.** A command or a path, then the
  explanation — not the other way round.
- **Every reply has the same shape**, so you learn where to look instead of reading
  everything.
- **It costs you almost nothing per turn.** The long rules load once per session as
  an output style; each prompt only carries a small card sized to that prompt.
- **It keeps score, silently.** A meter grades each finished reply and logs it, so
  drift back to essays is visible instead of gradual.
- **It never blocks you.** Every hook exits cleanly, even when it fails.

### How to use it

Install it and it's on. Three hooks and one bundled output style do the work:

- `UserPromptSubmit` prints a Reply Card beside your prompt, sized to the prompt
- `Stop` quietly scores the reply that just finished
- `SessionStart` prints at most three lines on where you left off

Three optional knobs, configurable in the plugin settings: `cardTiers` (when you get
the short card vs. the whole card), `meter` (scoring on or off), and `strictness`
(`lenient`, `normal`, `strict`).

To see how it's going:

```
/adhd-stats
```

_Screenshot: the adhd-stats scoreboard_

<!-- ![adhd-stats scoreboard](docs/images/adhd-stats.png) -->

### Skills in this plugin

- **`adhd-stats`** — the scoreboard: violation trend, reply length, card tier
  distribution, and the modelled token saving.

---

## Layout

```
.claude-plugin/marketplace.json          plugin manifest
orca-helpers/<skill>/SKILL.md            orca-helpers skill entry points
adhd-friendly/skills/<skill>/SKILL.md    adhd-friendly skill entry points
```

## License

See the repository owner for licensing.
