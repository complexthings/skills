#!/usr/bin/env python3
"""Stop, SessionStart (compact|resume) and PreCompact hook for the Owning Session of an active Workstream.

The Owning Session (ADR 0011) is the one whose id `_status.json.owner` holds. Every other session,
and every repo with no active Workstream, passes untouched.

- Stop: once every Work Item is `complete`, block the stop (exit 2, one stderr line per missing
  piece) until each Wave has a `Wave N retro` Decision Log entry, the Orca Knowledge Graph holds
  the `<workstream>-lessons` page, and `orca orchestration worker-list --run <runId>
  --terminal-state reclaimable --json` lists no worker. `stop_hook_active` lets the next stop
  through, so it blocks at most once.
- SessionStart after a compact or a resume: inject the paths of the files a resumed Main
  Orchestrator reads.
- PreCompact: run `prepare.py` so `_resume.md` is current before the compact.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent / "skills"
sys.path.insert(0, str(SKILLS / "orca-prompt" / "scripts"))
PREPARE = SKILLS / "orca-prepare" / "scripts" / "prepare.py"
READ_ON_RESUME = ("_resume.md", "_plan.md", "_status.json", "_decisions.md")


def owned(event):
    """(dir, status) for each active Workstream whose `_status.json.owner` holds this session's id."""
    session = event.get("session_id")
    if not session:
        return []
    sys.path.insert(0, str(HERE))
    from recall_hook import roots
    found = []
    for root in roots(event.get("cwd") or "."):
        for path in sorted(root.glob(".orca/prompts/*/_status.json")):
            try:
                status = json.loads(path.read_text(encoding="utf-8"))
                if status.get("active") is True and Path(f"{path}.owner").read_text(encoding="utf-8").strip() == session:
                    found.append((path.parent, status))
            except (OSError, ValueError, AttributeError):
                continue
    return found


def worker_list(run_id):
    """The reclaimable worker rows of `run_id`, or None when the list cannot be read."""
    from orca_cli import orca_cli
    try:
        r = subprocess.run([*orca_cli(), "orchestration", "worker-list", "--run", run_id, "--terminal-state", "reclaimable", "--json"],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        return (json.loads(r.stdout).get("result") or {}).get("workers") or [] if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return None


def missing(d, status):
    """One line per wrap-up piece the finished Workstream in `d` still lacks."""
    sys.path.insert(0, str(SKILLS / "orca-kb" / "scripts"))
    from kb import store
    ws = status.get("workstream") or d.name
    items = status.get("items") or []
    log_path = d / "_decisions.md"
    log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    lines = [f"{ws}: no `Wave {wave} retro` entry in {log_path}. Add it with set_status.py {d} log."
             for wave in sorted({i.get("wave") for i in items if isinstance(i.get("wave"), int)})
             if not re.search(rf"^### \S+ · Wave {wave} retro\s*$", log, re.MULTILINE)]
    if not (store(d.parents[2]) / "pages" / f"{ws}-lessons.md").is_file():
        lines.append(f"{ws}: no Orca Knowledge Graph page `{ws}-lessons`. Write it with orca-kb update {ws}-lessons.")
    run_id = status.get("runId")
    if not run_id:
        lines.append(f"{ws}: _status.json has no runId, so its reclaimable workers cannot be checked. Record it with set_status.py {d} run <runId>.")
    else:
        rows = worker_list(run_id)
        if rows is None:
            lines.append(f"{ws}: worker-list --run {run_id} --terminal-state reclaimable failed. Run it and release every worker it lists.")
        elif rows:
            lines.append(f"{ws}: {len(rows)} reclaimable worker(s) in run {run_id}. Release each one and remove its worktree.")
    return lines


def summary(status):
    """`Wave 2 of 5: 3 of 5 complete; in progress: a, b` for prepare.py."""
    items = status.get("items") or []
    waves = [i["wave"] for i in items if isinstance(i.get("wave"), int)]
    open_waves = [i["wave"] for i in items if isinstance(i.get("wave"), int) and i.get("state") != "complete"]
    done = sum(i.get("state") == "complete" for i in items)
    busy = [str(i.get("id")) for i in items if i.get("state") in ("in_progress", "reviewing")]
    text = f"Wave {min(open_waves, default=max(waves, default=0))} of {max(waves, default=0)}: {done} of {len(items)} complete"
    return text + (f"; in progress: {', '.join(busy)}" if busy else "")


def prepare(d, text):
    subprocess.run([sys.executable, str(PREPARE), str(d), text], stdin=subprocess.DEVNULL, capture_output=True, timeout=60)


def main(event):
    """The hook's exit code, printing its output."""
    if not isinstance(event, dict):
        return 0
    name = event.get("hook_event_name")
    if name == "Stop":
        if event.get("stop_hook_active"):
            return 0
        lines = [line for d, status in owned(event)
                 if (status.get("items") or []) and all(i.get("state") == "complete" for i in status["items"])
                 for line in missing(d, status)]
        if lines:
            print("\n".join(lines), file=sys.stderr)
            return 2
    elif name == "SessionStart":
        paths = [str(d / f) for d, _ in owned(event) for f in READ_ON_RESUME if (d / f).is_file()]
        if paths:
            text = "This session owns an active Orca Workstream. Read these before you continue:\n" + "\n".join(paths)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    elif name == "PreCompact":
        for d, status in owned(event):
            prepare(d, summary(status))
    return 0


if __name__ == "__main__":
    try:
        code = main(json.load(sys.stdin))
    except Exception:  # this runs on every stop and compact: fail open, never break the session
        code = 0
    sys.exit(code)
