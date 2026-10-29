---
type: llm
weight: 1
---

The Resume step says a resumed Main Orchestrator's first report starts with a `Read:` line naming every doc it read, `_plan.md`, `_orchestration.prompt.md`, `_decisions.md` and `_status.json` first. Pass when all of these hold:

- The reply's first non-empty line starts with `Read:`.
- That line names `_plan.md`, `_orchestration.prompt.md`, `_decisions.md` and `_status.json`, with or without the `.orca/prompts/auth-refactor/` prefix.

Fail when anything other than whitespace comes before the `Read:` line, when the line misses any of the four docs, or when the reply has no `Read:` line.
