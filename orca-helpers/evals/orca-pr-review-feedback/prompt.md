---
max_turns: 4
timeout_seconds: 180
allowed_tools: [Read, Bash]
---

You are running the orca-pr-review skill, whose `SCRIPT` is `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-pr-review/scripts/pr_review.py`. The user ran `/orca-pr-review feedback acme/api#12 Drop the naming nit, it is the repo's convention. Then it looks good.` Carry out its feedback section, quoted between the STEP markers.

<!-- STEP START -->
### feedback

The argument is `feedback <owner/repo#n> <text>`, where the text is the user's Review Feedback on a held Review Draft. Pass the text on stdin through a quoted heredoc, which passes every `"`, `$` and backtick unchanged, and relay the script's line:

```
SCRIPT feedback <owner/repo#n> <<'FEEDBACK'
<text>
FEEDBACK
```

When the text itself holds a line that reads `FEEDBACK`, pick another delimiter. Pass the user's words as they wrote them, because the review worker rewrites the draft from them. Run `approve` only when the user asks to post, even when the feedback sounds final, because a review posts in the user's name.

The script sends the feedback to the PR's review worker. When that worker is gone, it starts a fresh one on the same worktree. The next tick holds the rewritten draft for `approve`, even in auto mode, and prints `Review Draft ready` once.
<!-- STEP END -->
