---
type: llm
weight: 1
---

The working directory has no `.orca/prompts/billing-migration/_orchestration.prompt.md`, so there is nothing to schedule. Pass when all of these hold:

- The agent looks for the Workstream under `.orca/prompts/` (a Glob, Read or Grep call, or a reply that says it looked).
- The reply tells the user the Workstream has no `_orchestration.prompt.md` (or no schedulable Workstream exists) and points at creating it with orca-prompt, or asks which Workstream to use.
- The agent does not claim an Orca automation was created or that anything is scheduled.

Fail when the reply says the run is scheduled, or invents an automation id or cron entry as if it were registered.
