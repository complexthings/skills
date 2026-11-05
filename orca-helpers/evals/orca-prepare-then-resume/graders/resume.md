---
type: llm
weight: 1
---

Part 2 of the reply is the resumed Main Orchestrator's first report. Pass when all of these hold:

- It names `_plan.md`, `_orchestration.prompt.md`, `_decisions.md` and `_status.json` as docs it reads.
- It leaves 01-schema and 02-tokens alone, because they are complete.
- It does not dispatch a new worker for 03-api, because the worker in `term_77` is already in flight.
- It does not dispatch 04-ui before 03-api completes.

Fail when the report re-dispatches a complete Work Item or starts a second worker for 03-api.
