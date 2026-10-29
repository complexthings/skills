---
max_turns: 6
timeout_seconds: 240
allowed_tools: []
---

You are the Main Orchestrator for the `auth-refactor` Workstream, and this session continues it after a compaction. Follow the Resume step between the RESUME markers below. Nothing is checked out here and no `orca` command runs, so each doc's contents follow the step, and reading a doc means reading its block below.

<!-- RESUME START -->
## Resume

This run is a resume when any Work Item in `.orca/prompts/auth-refactor/_status.json` has left `todo`, or when you continue this Workstream after a compaction or a handover. On a resume, read these four docs in full before any dispatch:

1. `.orca/prompts/auth-refactor/_plan.md`
2. `.orca/prompts/auth-refactor/_orchestration.prompt.md`
3. `.orca/prompts/auth-refactor/_decisions.md`
4. `.orca/prompts/auth-refactor/_status.json`

When any of the four is missing, stop the resume. Dispatch nothing, start no worker and create no Task. Report the missing path, then its fix, for example: `Resume stopped: .orca/prompts/auth-refactor/_decisions.md is missing. Restore it from git, then resume again.` Each doc holds state the run needs, so a resume without one re-dispatches finished work or repeats a rejected approach.

Your first report after a resume starts with one `Read:` line that names every doc you read, these four first: `Read: _plan.md, _orchestration.prompt.md, _decisions.md, _status.json`. Add any other doc you read after them. The user checks this line to confirm the resume picked up the current plan and state.
<!-- RESUME END -->

## `.orca/prompts/auth-refactor/_plan.md`

```markdown
# Plan: auth-refactor

## Goal

Move session auth from cookies to signed tokens.

## Work Items

### 01-token-signer: Token signer
**Wave**: 1

### 02-middleware: Token middleware
**Wave**: 2
```

## `.orca/prompts/auth-refactor/_orchestration.prompt.md`

```markdown
# Main Orchestrator: `auth-refactor`

Run the Waves in order: Wave 1, then Wave 2. Wave N starts only after every Work Item in Wave N-1 is complete.
```

## `.orca/prompts/auth-refactor/_decisions.md`

```markdown
# Decision Log

### 2026-10-20 · Tokens use Ed25519, not HMAC
The middleware verifies tokens without the signing key.
```

## `.orca/prompts/auth-refactor/_status.json`

```json
{"workstream": "auth-refactor", "active": true, "items": [{"id": "01-token-signer", "wave": 1, "state": "complete", "pr": 41}, {"id": "02-middleware", "wave": 2, "state": "todo"}]}
```

Write your first report to the user after this resume, as the Resume step and these docs set it. Stop before you dispatch anything.
