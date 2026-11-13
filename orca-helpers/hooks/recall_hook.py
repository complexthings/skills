#!/usr/bin/env python3
"""UserPromptSubmit and SubagentStart hook: inject Orca Knowledge Graph recall during orca work only.

Orca work is any of: the prompt runs an orca skill (`/orca-...` or `/orca-helpers:...`), the
prompt names `.orca/prompts/` (an Orca Work Item or orchestration prompt), a Workstream's
`_status.json` is `active`, or the Prompt Band is mid-interview. Anywhere else it prints nothing.
During orca work it always injects a block, even with no matches, so a skill knows the hook ran
and skips its own `orca-kb review` step. A quiet orca-pr-review tick gets no recall: prompt_gate.py
answers it. ADR 0016: one user prompt can fire this more than once; recall is read-only, so a
repeat costs one query.
"""
import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

HEADER = "Orca Knowledge Graph recall (orca-helpers hook; skip the orca-kb review step):"
SKILL_RE = re.compile(r"^/(orca-helpers:)?orca-")
BAND_STALE_S = 30 * 60  # prompt-band.tsx STALE_MS


def roots(cwd):
    """The cwd, its repo root, and the main checkout when cwd is a worktree, since `_status.json` lives there."""
    found = [Path(cwd).resolve()]
    try:
        top, common = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"],
                                     capture_output=True, text=True, timeout=5).stdout.split("\n")[:2]
        for root in (Path(top), Path(common).parent):
            if root.resolve() not in found:
                found.append(root.resolve())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return found


def active_workstreams(found):
    names = []
    for root in found:
        for path in sorted(root.glob(".orca/prompts/*/_status.json")):
            try:
                if json.loads(path.read_text(encoding="utf-8")).get("active") is True:
                    names.append(path.parent.name)
            except (OSError, ValueError, AttributeError):
                continue
    return names


def band_open(root):
    """The orca-prompt interview is running: `_prompt-band.json` not ended and touched recently."""
    try:
        band = json.loads((Path(root) / ".orca" / "prompts" / "_prompt-band.json").read_text(encoding="utf-8"))
        if band.get("ended", True):
            return False
        updated = band.get("updatedAt")
        return not updated or time.time() - datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp() < BAND_STALE_S
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def context(event):
    """The additionalContext for one hook event, or None outside orca work."""
    # Imported here so an import failure lands in main's catch, not a crash at load.
    sys.path[:0] = [str(HERE), str(HERE.parent / "skills" / "orca-kb" / "scripts")]
    from kb import store
    from prompt_gate import TICK_RE
    from recall import NO_MATCH, recall
    prompt = event.get("prompt") or ""
    if TICK_RE.match(prompt.strip()):
        return None
    cwd = event.get("cwd") or "."
    found = roots(cwd)
    workstreams = active_workstreams(found)
    if not (SKILL_RE.match(prompt.strip()) or ".orca/prompts/" in prompt or workstreams or any(map(band_open, found))):
        return None
    # Seed on the prompt and the active Workstream names: a SubagentStart event carries no prompt.
    try:
        facts = recall(" ".join([prompt, *workstreams]), store(cwd) / "graph.db").as_text()
    except sqlite3.Error:  # a corrupt or foreign graph.db: no matches, no crash
        facts = NO_MATCH
    return HEADER + "\n" + facts


def main():
    event = json.load(sys.stdin)
    text = context(event)
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event.get("hook_event_name", "UserPromptSubmit"), "additionalContext": text}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # this runs on every prompt: fail open, never break the session
        pass
