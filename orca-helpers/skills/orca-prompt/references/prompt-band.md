# Prompt Band

## Driving the band

The orca-helpers Prompt Band follows the interview above the prompt, reading `.orca/prompts/_prompt-band.json`. `scripts/set_prompt_band.py` is that file's only writer, and a guard denies a direct Edit or Write of it. Run it at every step start, every answer and every step end, as each step in `../SKILL.md` says; the calls are written `python3 ${CLAUDE_SKILL_DIR}/scripts/set_prompt_band.py .orca/prompts <command>`.

- Before Round 1, run `begin` to reset the file, every step upcoming.
- `start <step>` at a step's start, `answer <step> <key> <value>` as each answer lands, `done <step>` at its end. Pass a JSON value for a list, object, number or boolean, and a plain string otherwise.
- `answers <step> '<JSON object>'` records several answers in one call, such as the stored settings that fill the `harness` and `models` panels. One unknown key records none of them.
- `tick <item>` as each Write / Validate checklist item finishes, and `end` once the skill's last step is done.

The band's five steps are `basics` (Round 1), `harness` (Round 2), `models` (Round 3), `timing` (Round 4) and `write-validate` (steps 5-11). A `FAIL:` line from the script never blocks the Workstream: fix the call if you can, and carry on.

The band stays up while a question shows, and stays up after `end` with its finished state. It hides only at a fresh startup or a `/clear`, and comes back with the next write to the file; a resume or a compact keeps it. The `o` hotkey, or the band's caret, collapses it to its top bar, and collapses or expands the Wave band with it.

## `_prompt-band.json` schema

`.orca/prompts/_prompt-band.json` holds the live state of the orca-prompt interview, and the orca-helpers Prompt Band reads it. `scripts/set_prompt_band.py` is its only writer (see Driving the band, above). `start` marks any other active step complete, so at most one step is active. `done` leaves `step` alone, so the band holds the finished step until the next `start`. A bad step, key, item or `answers` object prints a `FAIL:` line, exits non-zero and leaves the file as it was.

```json
{
  "step": "string | null — the active step id; null until the first start",
  "ended": "boolean — true once the skill finished its last step",
  "updatedAt": "string — ISO 8601 UTC time of the last write",
  "steps": [
    {
      "id": "basics | harness | models | timing | write-validate",
      "title": "string — Basics, Harness, Models, Timing, Write / Validate",
      "state": "upcoming | active | complete",
      "answers": "object — answer key -> value, filled as the user answers"
    }
  ],
  "checklist": [
    {
      "id": "scope | plan-config | sizes | scaffold | validate",
      "title": "string — Settle the Scope, Write the Plan & Config, Propose Sizes, Scaffold the Workstream, Validate",
      "done": "boolean"
    }
  ]
}
```

`steps` and `checklist` keep the order above. Answer keys per step: `basics` takes `workstream`, `targetBranch`, `integration`, `tickets`, `scopeFrom`; `harness` takes `detected`, `harnesses`, `mainOrchestratorHarness`; `models` takes `modelSet`, `models`, `maxConcurrency`; `timing` takes `taskTime`, `mode`, `localTime`, `timezone`, `utcTime`; `write-validate` takes none.
