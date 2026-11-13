---
max_turns: 4
timeout_seconds: 180
allowed_tools: [Read, Bash, Agent]
---

You are running the orca-pr-review skill, whose `SCRIPT` is `python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-pr-review/scripts/pr_review.py`. The user ran `/orca-pr-review tick`. Carry out its tick section, quoted between the STEP markers.

<!-- STEP START -->
### tick

When the context holds `orca-pr-review tick already ran in the orca-helpers hook`, the hook ran the tick: relay the lines under it and do not run the tick again. A quiet tick never reaches you, because the hook blocks its prompt.

Otherwise the classic hooks are off. Start one subagent with the Agent tool, `model` set to `haiku` (Claude Haiku 5.5), asking it to run `SCRIPT tick` and return its stdout verbatim, then relay those lines. A Haiku turn costs less than this session's model, and the cron fires every few minutes. Leave the tick to the subagent even when it fails: relay its failure line, because a second scan from this session doubles the GitHub calls. A `Review Draft ready` line names a report: read it and show its findings before the approve command. On `CRON <id>`, the Loop End passed: call the CronDelete tool with that id. The script prints each held draft and each repeated error only once.
<!-- STEP END -->

Context from the hook:

orca-pr-review tick already ran in the orca-helpers hook. Do not run `SCRIPT tick` again. Its lines:
Review Draft ready: acme/api#12. Approve with **/orca-pr-review approve acme/api#12**
