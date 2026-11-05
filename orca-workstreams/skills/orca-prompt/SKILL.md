---
name: orca-prompt
description: Plan an Orca Workstream, divide work into waves and generate worker and orchestration prompts. Use for a new Orca Workstream or planning parallel Orca workers.
---

# orca-prompt

Create a Workstream under `.orca/prompts/<name>/`. Resolve this skill's installed directory from the location of this file; call it `<skill-dir>` below. Python 3 and the Orca CLI are required. The scripts and data live inside this skill and do not require a Claude plugin or other skills.

1. Establish the objective, measurable Definition of Done, target branch, integration (`commit`, `branch`, `pr`, or `pr-merge`), and whether tracker tickets are requested. Ask only for decisions that cannot be inferred or safely made. Do not file tickets unless the user explicitly requests it.
2. Run `python3 <skill-dir>/scripts/detect_harnesses.py` and select installed harnesses with the user where necessary. Choose the main orchestrator harness, model slots and efforts, and concurrency limit. `scripts/list_models.py <harness> <slot>` lists available models for supported harnesses; `data/model-priority.json` and `data/recommended-priority.json` provide rankings. Set a tier (`light` or `standard`) per harness. Do not invent unavailable harnesses or models.
3. Split the work into independently actionable Work Items, assign each an id, size and numbered Wave, and establish dependencies by putting dependent work in later Waves. Set review and plan gate options if requested; otherwise use `false` for each. Record any decisions needed to run the work without the conversation.
4. Write `_plan.md` with `## Definition of Done`, `## Orchestration Rules`, and `## Work Items`. Each item must use `### <id>: <title>`, describe the work, and include `**Definition of Done**: ...` and `**Wave**: <number>`. Optional `**Skills**` and `**Closes**` fields name only skills or tickets actually available. The orchestration rules section is filled by the scaffold.
5. Write `_config.json` following [config-schema.md](references/config-schema.md). Include every required key; each harness has all four model slots, using `null` where no slot is selected. Work item ids and sizes must match the plan. Set `tickets` to `false` unless explicitly requested.
6. Run `python3 <skill-dir>/scripts/scaffold.py .orca/prompts/<name>/`, then `python3 <skill-dir>/scripts/validate.py .orca/prompts/<name>/`. Fix reported failures in the plan or config, re-scaffold, and validate again. Scaffolding rewrites generated prompts and the rules section; preserve any manual changes before re-running it.
7. Report the Workstream directory and validation result. Run it only when the user asks, using `orca-execute`.
