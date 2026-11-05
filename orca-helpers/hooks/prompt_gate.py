#!/usr/bin/env python3
"""UserPromptSubmit hook that answers prompts a script can settle, so they cost no model turn (ADR 0016).

- `orca-hooks-check` answers that orca-helpers' classic hooks are live, and blocks.
- `/orca-pr-review tick`, the review loop's cron prompt, runs `pr_review.py tick` here. A quiet
  tick prints nothing, so the prompt is blocked. A tick with lines passes them to the model as
  context, so the skill relays them without running the tick a second time.

Every other prompt passes untouched.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

CHECK = "orca-hooks-check"
TICK_RE = re.compile(r"^/(orca-helpers:)?orca-pr-review\s+tick$")
TICK_HEADER = "orca-pr-review tick already ran in the orca-helpers hook. Do not run `SCRIPT tick` again. Its lines:"
PR_REVIEW = Path(__file__).resolve().parent.parent / "skills" / "orca-pr-review" / "scripts" / "pr_review.py"


def run_tick():
    r = subprocess.run([sys.executable, str(PR_REVIEW), "tick"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def gate(prompt, tick=run_tick):
    """The hook's JSON reply for `prompt`, or None to let it pass."""
    prompt = prompt.strip()
    if prompt == CHECK:
        return {"decision": "block", "reason": "orca-helpers classic hooks are live."}
    if TICK_RE.match(prompt):
        lines = tick()
        if not lines:
            return {"decision": "block", "reason": "orca-pr-review: nothing new."}
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": f"{TICK_HEADER}\n{lines}"}}
    return None


def main():
    reply = gate(json.load(sys.stdin).get("prompt") or "")
    if reply:
        print(json.dumps(reply))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # this runs on every prompt: fail open, never break the session
        pass
