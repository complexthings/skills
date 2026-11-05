---
type: llm
weight: 1
---

The scope in the prompt looks complete, but orca-prompt's interview must still run. Pass when all of these hold:

- The agent starts Round 1 by asking for at least one of: the Workstream name, the target branch, or how results integrate (PR + merge, PR, branch, commit).
- At least one question offers an answer marked (Recommended), in a question tool call or in the reply text.
- The agent does not claim to have written `_config.json`, `_plan.md` or any prompt file, and does not present a finished plan.

Fail when the agent skips straight to writing or summarising a plan.
