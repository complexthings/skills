#!/usr/bin/env python3
"""An Orchestration Worker's last step: file its prompt, check its PR, drain its inbox, print `worker_done`.

Usage:
    python3 finish_work_item.py <workstream-dir> <id> --terminal <handle> [--report-path <path>]

`--terminal` is the handle from the worker's injected preamble. In order:

    move     `git mv <id>.prompt.md _completed/`; skipped when it is already there
    pr       the branch has a PR, when `integration` is `pr` or `pr-merge`
    inbox    `orca orchestration check --terminal <handle> --json`, acking each batch
             until `count` is 0; each message is printed for the worker to act on
    print    the exact `worker_done` command, with `--report-path` when given and
             `--files-modified` from `git diff -z --name-only origin/<targetBranch>...HEAD`

The worker commits and pushes the move, then fills in the subject and body and runs
the printed command. Stops at the first failed step with one `FAIL:` line; a re-run
after the fix repeats only what is left.
"""
import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from integrate import StepError, find_pr, run
from orca_cli import orca_cli
from scaffold import PR_INTEGRATIONS, load_config


def drain_inbox(orca, handle):
    """Ack every batch until `count` is 0; return (dispatchId, the messages read)."""
    argv = [*orca, "orchestration", "check", "--terminal", handle, "--json"]
    seen, ack = [], []
    while True:
        try:
            result = json.loads(run("inbox", argv[:-1] + ack + ["--json"])).get("result") or {}
        except (ValueError, AttributeError):
            raise StepError("inbox: unreadable JSON from orca orchestration check")
        seen += result.get("messages") or []
        if not result.get("count"):
            return result.get("dispatchId"), seen
        if not result.get("deliveryId"):
            raise StepError("inbox: a batch with messages carried no deliveryId to ack")
        ack = ["--ack", result["deliveryId"]]


def finish(ws, item_id, handle, report_path=None):
    """Return the lines to print, the `worker_done` command last."""
    ws = Path(ws).resolve()
    try:
        config = load_config(ws)
    except (OSError, ValueError) as e:
        raise StepError(f"setup: {e}")
    lines = []
    prompt, filed = ws / f"{item_id}.prompt.md", ws / "_completed" / f"{item_id}.prompt.md"
    if prompt.exists():
        filed.parent.mkdir(exist_ok=True)
        run("move", ["git", "-C", str(ws), "mv", prompt.name, f"_completed/{prompt.name}"])
        lines.append(f"ok: moved {prompt.name} into _completed/; commit and push it")
    elif not filed.exists():
        raise StepError(f"move: neither {prompt} nor {filed} exists")
    pr = None
    if config["integration"] in PR_INTEGRATIONS:
        branch = run("pr", ["git", "-C", str(ws), "branch", "--show-current"]).strip()
        pr = find_pr(ws, branch) if branch else None
        if pr is None:
            raise StepError(f"pr: branch {branch or '(detached HEAD)'} has no PR; open one into {config['targetBranch']}")
    orca = orca_cli()
    dispatch_id, messages = drain_inbox(orca, handle)
    lines += [f"message: {json.dumps(m)}" for m in messages]
    # -z: without it git quotes names holding non-ASCII bytes, quotes or newlines.
    changed = [n for n in run("files", ["git", "-C", str(ws), "diff", "-z", "--name-only", f"origin/{config['targetBranch']}...HEAD"]).split("\0") if n]
    body = "<3-sentence summary: what you did, what you found, what's left>" + (f" PR #{pr}." if pr else "")
    command = [*orca, "orchestration", "send", "--from", handle, "--type", "worker_done",
               "--subject", "<short status>", "--body", body,
               # The worktree's _status.json predates the Task, so the task id comes from the preamble.
               "--task-id", "<taskId from your preamble>",
               "--dispatch-id", dispatch_id or "<dispatchId from your preamble>", "--outcome", "succeeded"]
    command += ["--report-path", str(report_path)] if report_path else []
    command += ["--files-modified", ",".join(changed)] if changed else []
    return lines + [shlex.join(command)]


def main(argv):
    p = argparse.ArgumentParser(prog="finish_work_item.py")
    p.add_argument("workstream_dir")
    p.add_argument("id")
    p.add_argument("--terminal", required=True)
    p.add_argument("--report-path")
    a = p.parse_args(argv)
    try:
        for line in finish(a.workstream_dir, a.id, a.terminal, a.report_path):
            print(line)
    except StepError as e:
        print(f"FAIL: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
