---
type: llm
weight: 1
---

Part 1 of the reply prepares `auth-refactor` for handover. Pass when all of these hold:

- It prints at least two `set_status.py <dir> log` commands: one for the httpOnly cookie decision and one for dropping `jose`.
- The `jose` entry passes `--commit skills-build@9f3c2ab`.
- No command logs a Work Item state, such as 03-api being in progress, as a Decision Log entry.
- It prints one `prepare.py` command with a one-line summary and a `--next` that names `term_77`.
- The step 5 reply shows `/orca-execute auth-refactor` in a code block before any other content.

Fail when the reply claims it ran a command, when it edits `_decisions.md` or `_status.json` directly, or when the resume line is missing.
