#!/usr/bin/env python3
"""The only writer of `.orca/prompts/_prompt-band.json`, the file the Prompt Band reads.

Usage:
    python3 set_prompt_band.py <prompts-dir> begin                       # fresh file, every step upcoming
    python3 set_prompt_band.py <prompts-dir> start <step>                # step start: make it the active step
    python3 set_prompt_band.py <prompts-dir> answer <step> <key> <value> # one answer as it lands
    python3 set_prompt_band.py <prompts-dir> done <step>                 # step end: mark it complete
    python3 set_prompt_band.py <prompts-dir> tick <item>                 # tick one Write / Validate checklist item
    python3 set_prompt_band.py <prompts-dir> end                         # end marker: the skill finished
    python3 set_prompt_band.py <prompts-dir> show                        # print the file

`<prompts-dir>` is `.orca/prompts`. `<step>` is one of `basics`, `harness`,
`models`, `timing`, `write-validate`; `<item>` is one of `scope`,
`plan-config`, `sizes`, `scaffold`, `validate`. `<key>` must be one of the
step's answer keys below. `<value>` is parsed as JSON when it parses, and
kept as a plain string otherwise, so `true`, `16` and `'["claude"]'` arrive
typed while `main` stays a string.

`start` marks every other active step complete, so at most one step is active
and moving on finishes the step left behind. `done` leaves `step` alone: the
band holds the finished step until the next `start`. Any bad input prints one
`FAIL:` line, exits 1 and leaves the file untouched. Every write goes to a temp
file in the same directory and is renamed over `_prompt-band.json`, so a reader
never sees a half-written file.

`_prompt-band.json` schema:

    {
      "step": "string | null: the active step id; null until the first start",
      "ended": "boolean: true once the skill finished its last step",
      "updatedAt": "string: ISO 8601 UTC time of the last write",
      "steps": [
        {
          "id": "basics | harness | models | timing | write-validate",
          "title": "string: the name the band shows",
          "state": "upcoming | active | complete",
          "answers": "object: answer key -> value, filled as the user answers"
        }
      ],
      "checklist": [
        {
          "id": "scope | plan-config | sizes | scaffold | validate",
          "title": "string: the name the band shows",
          "done": "boolean"
        }
      ]
    }

`steps` and `checklist` keep the order above.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scaffold import claim, write_json_atomic

BAND_FILE = "_prompt-band.json"
STEPS = {
    "basics": "Basics",
    "harness": "Harness",
    "models": "Models",
    "timing": "Timing",
    "write-validate": "Write / Validate",
}
ANSWER_KEYS = {
    "basics": ("workstream", "targetBranch", "integration", "tickets", "scopeFrom"),
    "harness": ("detected", "harnesses", "mainOrchestratorHarness"),
    "models": ("modelSet", "models", "maxConcurrency"),
    "timing": ("mode", "localTime", "timezone", "utcTime"),
    "write-validate": (),
}
CHECKLIST = {
    "scope": "Settle the Scope",
    "plan-config": "Write the Plan & Config",
    "sizes": "Propose Sizes",
    "scaffold": "Scaffold the Workstream",
    "validate": "Validate",
}


class BandError(Exception):
    pass


def _read(prompts_dir):
    path = Path(prompts_dir) / BAND_FILE
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise BandError(f"{path} does not exist; run begin first")
    except json.JSONDecodeError as e:
        raise BandError(f"{path} is not valid JSON: {e}")


def _write(prompts_dir, band):
    """Write `_prompt-band.json` atomically: temp file in the same dir, then rename."""
    write_json_atomic(prompts_dir, BAND_FILE, band, ".prompt-band-")


def _step(band, step_id):
    if step_id not in STEPS:
        raise BandError(f"unknown step {step_id!r}; use one of {', '.join(STEPS)}")
    return next(s for s in band["steps"] if s["id"] == step_id)


def _parse(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def begin(prompts_dir):
    Path(prompts_dir).mkdir(parents=True, exist_ok=True)
    _write(prompts_dir, {
        "step": None,
        "ended": False,
        "steps": [{"id": i, "title": t, "state": "upcoming", "answers": {}} for i, t in STEPS.items()],
        "checklist": [{"id": i, "title": t, "done": False} for i, t in CHECKLIST.items()],
    })
    claim(Path(prompts_dir) / BAND_FILE)


def start(prompts_dir, step_id):
    band = _read(prompts_dir)
    step = _step(band, step_id)
    for other in band["steps"]:
        if other["state"] == "active":
            other["state"] = "complete"
    step["state"] = "active"
    band["step"] = step_id
    _write(prompts_dir, band)


def answer(prompts_dir, step_id, key, value):
    band = _read(prompts_dir)
    step = _step(band, step_id)
    if key not in ANSWER_KEYS[step_id]:
        allowed = ", ".join(ANSWER_KEYS[step_id]) or "none"
        raise BandError(f"unknown answer key {key!r} for {step_id}; use one of {allowed}")
    step["answers"][key] = _parse(value)
    _write(prompts_dir, band)


def done(prompts_dir, step_id):
    band = _read(prompts_dir)
    _step(band, step_id)["state"] = "complete"
    _write(prompts_dir, band)


def tick(prompts_dir, item_id):
    if item_id not in CHECKLIST:
        raise BandError(f"unknown checklist item {item_id!r}; use one of {', '.join(CHECKLIST)}")
    band = _read(prompts_dir)
    next(i for i in band["checklist"] if i["id"] == item_id)["done"] = True
    _write(prompts_dir, band)


def end(prompts_dir):
    band = _read(prompts_dir)
    band["ended"] = True
    _write(prompts_dir, band)


COMMANDS = {
    "begin": (begin, 0),
    "start": (start, 1),
    "answer": (answer, 3),
    "done": (done, 1),
    "tick": (tick, 1),
    "end": (end, 0),
    "show": (lambda d: print(json.dumps(_read(d), indent=2)), 0),
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        raise BandError(f"usage: set_prompt_band.py <prompts-dir> {' | '.join(COMMANDS)} [args]")
    prompts_dir, command, rest = argv[0], argv[1], argv[2:]
    fn, arity = COMMANDS[command]
    if len(rest) != arity:
        raise BandError(f"{command} takes {arity} argument(s), got {len(rest)}")
    fn(prompts_dir, *rest)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BandError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
