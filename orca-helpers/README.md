# orca-helpers

Helpers for planning and orchestrating [Orca](https://orca.computer) workstreams.
A **workstream** is a named body of work: one plan, one set of work items, one
target branch.

## Install

```bash
claude plugin marketplace add complexthings/skills
claude plugin install orca-helpers@complexthings
```

## Skills

- **`orca-prompt`** — interviews you and writes a whole `.orca/prompts/<workstream>/` directory: the plan, the config, and one prompt file per work item.
- **`orca-prompt-settings`** — stores the repo-level defaults (harnesses, models, concurrency, reasoning level, priority file) so `orca-prompt` stops asking for them.
- **`orca-prompt-scheduler`** — schedules a workstream's `_orchestration.prompt.md` as a one-shot Orca automation that fires exactly once.

## Prerequisites

`orca-prompt` settles the scope of work using `grill-with-docs`, from Matt
Pocock's [`mattpocock-skills`](https://github.com/mattpocock/skills). It is in
Claude Code's official marketplace:

```
/plugin install mattpocock-skills
```

Without it, `orca-prompt` stops after the interview and tells you to install it.
