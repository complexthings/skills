---
type: llm
weight: 1
---

orca-prompt runs its interview in a fixed order: Round 1 Basics, Round 2 Harness, Round 3 Models, Round 4 Timing, then Settle the scope, then the writing and validating steps. Pass when all of these hold:

- The first questions the agent asks belong to Round 1 (Workstream name, target branch, integration, tracker tickets, or where the Scope of Work comes from). It does not open with harnesses, models, timing or scheduling.
- When the agent creates its Task list, `4. Round 4: Timing` comes before `5. Settle the scope`, and no Task schedules or runs the Workstream before the validate step.
- The agent asks no reasoning-level question, for the Workstream or for the session. An effort asked per Model Slot in Round 3 is fine.

Fail when Timing comes after Settle the scope, when scheduling is offered before validation, or when the agent asks for a reasoning level.
