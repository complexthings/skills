#!/usr/bin/env python3
"""PostToolUse (Bash) hook: after a clean `scaffold.py <workstream-dir>`, run `validate.py` on it and
tick `scaffold` on the Prompt Band while its interview runs, then hand the validate result to the model as context, so
orca-prompt shows it and skips its own validate step. Any other command passes untouched.
"""
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "orca-prompt" / "scripts"
SCAFFOLD_RE = re.compile(r"(?:^|[\s/\"'])scaffold\.py[\"']?\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")
HEADER = "The orca-helpers hook already ran validate.py on the scaffolded Workstream. Show this result verbatim and skip the validate step:"


def run(*args):
    r = subprocess.run([sys.executable, *map(str, args)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def context(event):
    """The additionalContext for one PostToolUse event, or None when it is not a clean scaffold."""
    command = (event.get("tool_input") or {}).get("command") or ""
    m = SCAFFOLD_RE.search(command)
    response = event.get("tool_response")
    stdout = response.get("stdout", "") if isinstance(response, dict) else str(response or "")
    if not m or "Scaffolded " not in stdout:
        return None
    try:
        workstream = Path(event.get("cwd") or ".") / shlex.split(m.group(1))[0]
    except (ValueError, IndexError):  # an odd token such as `$'my`: not a scaffold this hook can follow
        return None
    if not (workstream / "_config.json").is_file():
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from recall_hook import band_open  # after the cheap checks: this runs on every Bash call
    result = run(SCRIPTS / "validate.py", workstream)
    if band_open(workstream.parent.parent.parent):  # a re-scaffold from orca-execute has no interview to tick
        run(SCRIPTS / "set_prompt_band.py", workstream.parent, "tick", "scaffold")
    return f"{HEADER}\n{result}"


def main():
    text = context(json.load(sys.stdin))
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # this runs on every Bash call: fail open, never break the session
        pass
