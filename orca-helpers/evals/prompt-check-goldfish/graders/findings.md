---
type: llm
weight: 1
---

The reply is a Goldfish Reader's findings on the `csv-export` Workstream. Pass when all of these hold:

- Every finding line has the shape `<file>:<line> | <severity> | <sentence>`, with severity `blocker`, `gap` or `nit`.
- One finding flags the Definition of Done "it works" in `_plan.md` (line 16) or `01-export-api.prompt.md` (line 7) as something a worker cannot check.
- One finding flags the open choice between streaming and a buffered response (`_plan.md` line 14 or `01-export-api.prompt.md` line 3).
- One finding flags that `02-export-button` depends on `01-export-api` yet both sit in Wave 1 (`_plan.md` line 21 or 24, or `_orchestration.prompt.md` line 3).

Fail when any of the three gaps is missing, when the reply holds prose beyond the finding lines, or when it reports a style or wording issue as a finding.
