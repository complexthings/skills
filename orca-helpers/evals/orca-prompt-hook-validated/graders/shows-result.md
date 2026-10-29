---
type: llm
weight: 1
---

The orca-helpers hook already validated the Workstream. Pass when the reply shows `ok: workstream meets the Definition of Done` verbatim and treats the Workstream as validated. Fail when the reply says it still has to run validate.py, or reports a validation failure.
