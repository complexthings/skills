#!/usr/bin/env python3
"""Integrate one finished Work Item: the Main Orchestrator's per-worker steps after `worker_done`.

Usage:
    python3 integrate.py <workstream-dir> <id> --dispatch <dispatch-id> --worktree <path>

Reads the branch (`git -C <path> branch --show-current`), its PR (`gh pr list --head
<branch> --state all`) and the issues on the Work Item's `**Closes**` line in `_plan.md`.
Then runs, in the order the orchestration prompt lists them:

    drain check     `git status --porcelain` and the unpushed log both print nothing
    integrate       `gh pr merge` for pr-merge, `git merge` + push for commit (before the
                    drain check), nothing for pr and branch
    release         `orca orchestration worker-release --dispatch <id>`
    remove          `orca worktree rm` when release left the worktree
    close           `gh issue close` for each `**Closes**` issue, merged integrations only
    complete        `set_status.py <dir> <id> complete [--pr <n>]`

It stops at the first failed step with that step's `FAIL:` line and never falls back
from `gh` to plain `git`. Finished steps, the branch and the PR are kept in
`<workstream-dir>/.integrate-<id>.json`, so a re-run after the fix starts at the failed
step; the file is removed once `complete` succeeds.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from orca_cli import orca_cli
from scaffold import MERGE_INTEGRATIONS, load_config, parse_plan

SET_STATUS = Path(__file__).parent / "set_status.py"


class StepError(Exception):
    pass


def run(step, argv, cwd=None):
    """`argv`'s stdout; a non-zero exit or a missing command raises StepError naming `step`."""
    try:
        out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    except OSError as e:
        raise StepError(f"{step}: {e}")
    if out.returncode != 0:
        detail = (out.stderr.strip() or out.stdout.strip()).splitlines()
        raise StepError(f"{step}: `{' '.join(map(str, argv))}` exited {out.returncode}" + (f": {detail[-1]}" if detail else ""))
    return out.stdout


def find_pr(ws, branch):
    """The PR number for `branch`, or None when it has none."""
    prs = json.loads(run("pr lookup", ["gh", "pr", "list", "--head", branch, "--state", "all", "--json", "number"], cwd=ws) or "[]")
    return prs[0]["number"] if prs else None


def steps(ws, item_id, dispatch, worktree, config, closes, memo):
    """(name, action) pairs in run order; each action takes no arguments."""
    integration, target = config["integration"], config["targetBranch"]
    wt = str(worktree)
    pr = memo["pr"]
    # A squash merge rewrites SHAs, so PR integrations check the pushed branch before merging.
    unpushed = f"origin/{target}..HEAD" if integration == "commit" else "@{upstream}..HEAD"

    def drain():
        if run("drain check", ["git", "-C", wt, "status", "--porcelain"]).strip():
            raise StepError(f"drain check: {wt} has uncommitted changes")
        if run("drain check", ["git", "-C", wt, "log", "--oneline", unpushed]).strip():
            raise StepError(f"drain check: {wt} has commits not pushed ({unpushed})")

    def merge():
        if integration == "pr-merge":
            if pr is None:
                raise StepError(f"merge: branch {memo['branch']} has no PR")
            run("merge", ["gh", "pr", "merge", str(pr), "--merge"], cwd=ws)
        elif integration == "commit":
            on = run("merge", ["git", "-C", str(ws), "branch", "--show-current"]).strip()
            if on != target:
                raise StepError(f"merge: the checkout holding {ws} is on {on or 'a detached HEAD'}, not {target}")
            run("merge", ["git", "-C", str(ws), "merge", "--no-edit", memo["branch"]])
            run("merge", ["git", "-C", str(ws), "push", "origin", target])

    def remove():
        if worktree.exists():
            run("remove", [*orca_cli(), "worktree", "rm", "--worktree", f"path:{wt}", "--json"])

    def complete():
        run("complete", [sys.executable, str(SET_STATUS), str(ws), item_id, "complete", *(["--pr", str(pr)] if pr is not None else [])])

    order = [("merge", merge), ("drain", drain)] if integration == "commit" else [("drain", drain), ("merge", merge)]
    order += [
        ("release", lambda: run("release", [*orca_cli(), "orchestration", "worker-release", "--dispatch", dispatch, "--json"])),
        ("remove", remove),
    ]
    if integration in MERGE_INTEGRATIONS:
        order += [(f"close {ref}", lambda ref=ref: run(f"close {ref}", ["gh", "issue", "close", ref.lstrip("#")], cwd=ws)) for ref in closes]
    return order + [("complete", complete)]


def integrate(ws, item_id, dispatch, worktree):
    """Run every step not yet done; return the lines to print."""
    ws, worktree = Path(ws).resolve(), Path(worktree).resolve()
    try:
        config = load_config(ws)
        plan = parse_plan(ws)
    except (OSError, ValueError) as e:
        raise StepError(f"setup: {e}")
    if item_id not in plan:
        raise StepError(f"setup: {item_id} is not a Work Item in {ws / '_plan.md'}")
    memo_file = ws / f".integrate-{item_id}.json"
    memo = json.loads(memo_file.read_text()) if memo_file.exists() else {"done": []}
    if "branch" not in memo:
        branch = run("branch", ["git", "-C", str(worktree), "branch", "--show-current"]).strip()
        if not branch:
            raise StepError(f"branch: {worktree} is on a detached HEAD")
        memo["branch"] = branch
    if memo.get("pr") is None:  # the PR may have been opened since the last run
        memo["pr"] = find_pr(ws, memo["branch"])
        memo_file.write_text(json.dumps(memo))
    lines = []
    for name, action in steps(ws, item_id, dispatch, worktree, config, plan[item_id]["closes"], memo):
        if name in memo["done"]:
            lines.append(f"skip: {name} (done)")
            continue
        action()
        lines.append(f"ok: {name}")
        memo["done"].append(name)
        memo_file.write_text(json.dumps(memo))
    memo_file.unlink()
    return lines


def main(argv):
    p = argparse.ArgumentParser(prog="integrate.py")
    p.add_argument("workstream_dir")
    p.add_argument("id")
    p.add_argument("--dispatch", required=True)
    p.add_argument("--worktree", required=True)
    a = p.parse_args(argv)
    try:
        for line in integrate(a.workstream_dir, a.id, a.dispatch, a.worktree):
            print(line)
    except StepError as e:
        print(f"FAIL: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
