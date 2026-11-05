#!/usr/bin/env python3
"""Create a Workstream's Orca Run and Tasks, then print the `worker-start` line for each ready Work Item.

Usage:
    python3 dispatch.py <workstream-dir> [--resume]

Reads `runId` from `_status.json`, or runs `orca orchestration run-create` and records it
with `set_status.py <dir> run <runId>`. Runs `orca orchestration task-create` once per Work
Item not yet `complete`, Wave by Wave, with `--deps` naming every Task of the previous Wave
still open, and records each id with `set_status.py <dir> <id> task <taskId>`. `--resume`
skips items that already have a `taskId`, so a re-run after a failure creates only the
missing Tasks. A `failed` item gets a new Task and goes back to `todo`: Orca reopens a failed
Task only with `--retry-of` its dispatchId, which `_status.json` does not keep. Last, prints one `worker-start --task` line per ready item: state `todo`
with every earlier Wave complete. The line is `scaffold.worker_start_command` for the
item's `harness`, so the Model Slot flags come from `_config.json`.

Needs `_status.json`, so run `set_status.py <dir> --start` first. Stops at the first
failed step with one `FAIL:` line.
"""
import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from integrate import StepError, run
from orca_cli import orca_cli
from scaffold import load_config, worker_start_command

SET_STATUS = Path(__file__).parent / "set_status.py"


def created_id(step, out, kind):
    """The id in an Orca `--json` receipt: `result.<kind>.id`, `result.<kind>Id` or `result.id`."""
    try:
        result = json.loads(out).get("result") or {}
    except (ValueError, AttributeError):
        raise StepError(f"{step}: unreadable JSON from orca")
    found = (result.get(kind) or {}).get("id") or result.get(f"{kind}Id") or result.get("id")
    if not found:
        raise StepError(f"{step}: orca returned no {kind} id")
    return found


def set_status(step, ws, *args):
    run(step, [sys.executable, str(SET_STATUS), str(ws), *args])


def dispatch(ws, resume=False):
    """Create what is missing; return the `worker-start` lines for the ready items."""
    ws = Path(ws).resolve()
    try:
        config = load_config(ws)
        status = json.loads((ws / "_status.json").read_text())
    except (OSError, ValueError) as e:
        raise StepError(f"setup: {e}; run set_status.py {ws} --start first")
    orca, workstream = orca_cli(), config["workstream"]
    run_id = status.get("runId")
    if not run_id:
        run_id = created_id("run-create", run("run-create", [*orca, "orchestration", "run-create", "--objective", workstream, "--json"]), "run")
        set_status("record run", ws, "run", run_id)
    items = status["items"]
    task_ids = {i["id"]: i.get("taskId") for i in items}
    waves = sorted({i["wave"] for i in items})
    for n, wave in enumerate(waves):
        previous = [i for i in items if n and i["wave"] == waves[n - 1] and i["state"] != "complete"]
        deps = [task_ids[i["id"]] for i in previous if task_ids[i["id"]]]
        for item in (i for i in items if i["wave"] == wave and i["state"] != "complete"):
            # A failed Task reopens only with --retry-of its dispatchId, which _status.json does not keep, so it gets a new Task.
            if resume and task_ids[item["id"]] and item["state"] != "failed":
                continue
            argv = [*orca, "orchestration", "task-create",
                    "--spec", f"Execute .orca/prompts/{workstream}/{item['id']}.prompt.md",
                    "--task-title", f"Wave {wave} · {item['title']}", "--run", run_id]
            out = run(f"task-create {item['id']}", argv + (["--deps", json.dumps(deps)] if deps else []) + ["--json"])
            task_ids[item["id"]] = created_id(f"task-create {item['id']}", out, "task")
            set_status(f"record task {item['id']}", ws, item["id"], "task", task_ids[item["id"]])
            if item["state"] == "failed":
                set_status(f"reopen {item['id']}", ws, item["id"], "todo")
                item["state"] = "todo"
    harnesses = {h["name"]: h for h in config["harnesses"]}
    lines = []
    for item in items:
        earlier_done = all(i["state"] == "complete" for i in items if i["wave"] < item["wave"])
        if item["state"] != "todo" or not earlier_done:
            continue
        harness = harnesses.get(item.get("harness"))
        if not harness:
            raise StepError(f"worker-start {item['id']}: harness {item.get('harness')!r} is not in _config.json; re-run set_status.py {ws} --start")
        line = worker_start_command(harness, name=item["id"]).replace("<taskId>", task_ids[item["id"]] or "<taskId>")
        lines.append(shlex.join(orca) + line.removeprefix("orca"))
    return lines


def main(argv):
    p = argparse.ArgumentParser(prog="dispatch.py")
    p.add_argument("workstream_dir")
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)
    try:
        for line in dispatch(a.workstream_dir, a.resume):
            print(line)
    except StepError as e:
        print(f"FAIL: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
