---
max_turns: 4
timeout_seconds: 180
allowed_tools: [Read, Bash, Glob]
---

You are running orca-prompt for the Workstream `oauth-login`. Step 9 just finished: `scaffold.py .orca/prompts/oauth-login/` printed `Scaffolded 2 wave(s) into .orca/prompts/oauth-login/`. Carry out step 10, quoted between the STEP markers, up to the point where it acts on the Round 4 answer, then stop.

<!-- STEP START -->
### 11. Validate, then run or schedule

When the context after step 9 holds `The orca-helpers hook already ran validate.py`, the hook already validated the Workstream: show the result under that line verbatim and skip the command. Otherwise run `python3 ${CLAUDE_SKILL_DIR}/scripts/validate.py .orca/prompts/<workstream>/` and show the user the result verbatim. A clean run prints `ok: workstream meets the Definition of Done`; a failing run prints one `FAIL:` line per missing piece and exits non-zero. On failure, fix `_config.json` or `_plan.md` and re-run step 9; the Workstream is ready only after a clean validate. Band: `tick validate` on the clean run.
<!-- STEP END -->

Context after step 9:

The orca-helpers hook already ran validate.py on the scaffolded Workstream. Show this result verbatim and skip the validate step:
ok: workstream meets the Definition of Done
