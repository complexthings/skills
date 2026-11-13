---
name: orca-execute
description: Start or resume a planned Orca Workstream, dispatch its waves and integrate completed work. Use when asked to run or resume an Orca Workstream.
argument-hint: <workstream>
---

# orca-execute

Resolve the `orca-prompt` skill installed alongside this skill and call its directory `<prompt-skill>`. A name resolves to `.orca/prompts/<name>/`; a path is used as given. Require `_config.json`, `_plan.md`, and `_orchestration.prompt.md`. If no Workstream is specified and the intended one is unclear, ask the user.

Run `python3 <prompt-skill>/scripts/scaffold.py --check <dir>` and `python3 <prompt-skill>/scripts/validate.py <dir>`. Stop on errors and explain them. Re-scaffolding overwrites generated prompts and must not be done without preserving manual edits.

Run `python3 <prompt-skill>/scripts/set_status.py <dir> --start` and `python3 <prompt-skill>/scripts/set_status.py <dir> --show`. Read `_resume.md` and the documents it names if present. Read `_orchestration.prompt.md` in full and follow its Run, dispatch, wait, review, integration and cleanup steps. On resume, bind the recorded Run, use `dispatch.py <dir> --resume`, and never dispatch an already complete Work Item. Do not create a second worker for an in-flight item.

Use `set_status.py` for every status change. Mark an item complete only when its own Definition of Done and required integration or review have passed. A failed item gets a concise reason and may be retried when its Wave resumes. Wait for all items in a Wave before starting the next. Stop for a decision only when the plan cannot resolve it.

After the last Wave, check every condition in `_plan.md` under `## Definition of Done` and report the result. Use `python3 <prompt-skill>/scripts/set_status.py <dir> --stop` to clear the active flag when stopping; this does not stop workers. Release Orca workers through the orchestration workflow.
