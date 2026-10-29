# `_config.json` schema

The contract every later script in this pattern codes against. Renaming or removing a key means updating every skill that reads it.

```json
{
  "workstream": "string — the workstream name, matches the .orca/prompts/<workstream>/ directory",
  "targetBranch": "string — branch every Work Item's result reaches, by the route `integration` names",
  "harnesses": [
    {
      "name": "string — Agent Harness identifier: claude | opencode | copilot | codex | pi | agy | <other>",
      "cli": "string — the CLI command to invoke this Agent Harness (only needed when name is not one of the six built-ins)",
      "tier": "light | standard — routes work items to this Agent Harness by size",
      "models": {
        "mainOrchestrator": "Model Slot | null — model for the Main Orchestrator session; null on every Agent Harness that does not run it",
        "orchestrationWorker": "Model Slot | null — model for the Orchestration Worker session",
        "subagent": "Model Slot | null — model for ordinary subagents",
        "subagentSimple": "Model Slot | null — model for subagents doing simple tasks"
      }
    }
  ],
  "mainOrchestratorHarness": "string | null — which harnesses[].name runs the Main Orchestrator",
  "maxConcurrency": "number | null — ceiling counting Orchestrator, Subagents, and Nested Subagents combined",
  "integration": "commit | branch | pr | pr-merge — how each Work Item's result reaches targetBranch",
  "tickets": "boolean — whether the Workstream files tracker tickets",
  "review": "boolean — whether each Work Item gets a Work Item Review, from Round 4",
  "planGate": "boolean — whether a Plan Gate runs before Wave 1, from Round 4",
  "evidenceCommand": "string | null — the evidence command, from Round 4; null for none",
  "budgetUsd": "positive number | null — the spend budget in USD, from Round 4; null for none",
  "taskTime": "low | medium | high | xhigh | ultra — the Task Time, from Round 4: under 5, 10, 15 or 30 minutes per Work Item, or 30 or more",
  "workItems": [
    {
      "id": "string — matches the work item prompt filename, e.g. 01-skill-skeleton",
      "size": "light | standard",
      "wave": "number — the Work Item's Wave, written by scaffold.py from _plan.md",
      "title": "string — the Work Item's title, written by scaffold.py from _plan.md"
    }
  ]
}
```

Notes for the scripts that read this file:

- `harnesses` may hold more than one entry; a Work Item's Agent Harness is chosen by matching its `workItems[].size` against a `harnesses[].tier`. With no exact match, the Agent Harness with the nearest tier takes it.
- `integration` sets each Work Item's Definition of Done and the Main Orchestrator's per-worker steps. `commit`: the worker commits on its branch and the Main Orchestrator merges that branch into `targetBranch`. `branch`: the worker pushes its branch, left for review. `pr`: the worker opens a PR, left for review. `pr-merge`: the worker opens a PR and the Main Orchestrator merges it. Generated prompts name PRs only for `pr` and `pr-merge`, and merges only for `commit` and `pr-merge`.
- `tickets` is `false` unless the user opts in. When `true`, step 6 may file Work Items with `to-spec` / `to-tickets`, and the Main Orchestrator may file new tickets with them from PR feedback. When `false`, nothing invokes either skill.
- `workItems[].wave` and `title` come from `_plan.md`; `scaffold.py` writes them, and `validate.py` reports a Work Item missing either. `dispatch.py` creates Wave N's Tasks with `task-create --deps` naming every open Task of Wave N-1, and gives a `failed` Work Item a new Task when its Wave comes up.
- A **Model Slot** is either an object `{"model": "gpt-6.1-sol", "effort": "high"}` or a plain string `"<model-id>"` for a model that takes no effort. Round 3 writes the object form wherever the model takes an effort. There is no Workstream-wide effort: an older `_config.json` that still holds `reasoningLevel` is read with the key ignored. Valid efforts are `low`, `medium`, `high`, `xhigh`, `max`. Scripts read a slot through `render_rules.normalize_model_slot`, which turns either shape into `(model, effort_or_none)`; any third shape is a `FAIL:` from `validate.py`.
- `models.mainOrchestrator` is `null` on every Agent Harness but the one `mainOrchestratorHarness` names, and the key is still required there — `validate.py` reports a missing key as a `FAIL:`, the same as any other slot.
- `models.subagentSimple` may be `null` even when the Agent Harness is fully configured — not every Agent Harness distinguishes a simple-task model (see the Pi rules in any generated `_plan.md`'s Orchestration Rules section, which has no simple-task slot).
- `review`, `planGate`, `evidenceCommand`, `budgetUsd` and `taskTime` record the Round 4 answers, so a run never re-reads Prompt Settings. `review: true` adds a `## Work Item Review` section to `_orchestration.prompt.md` and writes the reviewer brief `_review.prompt.md` beside it. `review: false`, or no `review` key, scaffolds exactly as before. `planGate: true` adds a Plan Gate step to `_orchestration.prompt.md` before the Wave Tasks: one reviewer reads `_plan.md`, writes `_plan-review.md` in the Workstream folder, and signs `VERDICT: GO` or `VERDICT: NO-GO`. NO-GO raises a Decision Gate with **Revise plan** and **Start anyway**. `planGate: false` leaves every generated file as it was before the key existed. `evidenceCommand` changes no generated file yet. `budgetUsd` changes no generated file: the Board reads it from `_config.json`. `taskTime` renders a `## Task Time` section into every Work Item prompt and `_orchestration.prompt.md`, and an absent key reads as `medium`. `scaffold.py` and `validate.py` check their types when present, and an older `_config.json` without them scaffolds as before.
- Every key in this schema except those five must exist in a written `_config.json`, even where the value is `null` or `[]`. Step 7 of `../SKILL.md` writes all five. A missing key means the file was hand-edited or written by something older than this schema — an error to report, not a default to fill in.
