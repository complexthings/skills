#!/usr/bin/env python3
"""Self-check for integrate.py, plus the fixture test_dispatch.py and test_finish_work_item.py share.
Run: python3 test_integrate.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SET_STATUS = HERE / "set_status.py"
SLOTS = {s: {"model": "claude-opus-5-5", "effort": "medium"} for s in ("mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple")}

# A stub for orca, gh and git: logs argv, then answers with the first rule whose `match` is
# a substring of the command line. Rules live in rules.json beside the log, so a test can
# make one step fail, fix it, and re-run.
STUB = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["STUB_DIR"]
line = " ".join([os.path.basename(sys.argv[0])] + sys.argv[1:])
open(os.path.join(d, "log"), "a").write(line + "\\n")
for rule in json.load(open(os.path.join(d, "rules.json"))):
    if rule["match"] in line:
        sys.stdout.write(rule.get("out", ""))
        sys.exit(rule.get("code", 0))
"""


class Fixture:
    def __init__(self, root, integration="pr-merge", review=False):
        root = Path(root)
        self.ws, self.wt, self.stub = root / "ws", root / "wt", root / "stub"
        for d in (self.ws, self.wt, self.stub):
            d.mkdir()
        for name in ("orca", "gh", "git"):
            (self.stub / name).write_text(STUB)
            (self.stub / name).chmod(0o755)
        self.rules([])
        (self.ws / "_config.json").write_text(json.dumps({
            "workstream": "demo", "targetBranch": "main", "mainOrchestratorHarness": "claude", "maxConcurrency": 4,
            "integration": integration, "tickets": False, "review": review,
            "harnesses": [{"name": "claude", "cli": "claude", "tier": "standard", "models": SLOTS}],
            "workItems": [
                {"id": "01-a", "size": "standard", "wave": 1, "title": "Alpha"},
                {"id": "02-b", "size": "standard", "wave": 1, "title": "Bravo"},
                {"id": "03-c", "size": "standard", "wave": 2, "title": "Charlie"},
            ],
        }))
        (self.ws / "_plan.md").write_text(
            "# demo\n\n## Work Items\n\n"
            "### 01-a: Alpha\n\nDo a.\n\n**Closes**: #11, #12\n**Wave**: 1\n\n"
            "### 02-b: Bravo\n\nDo b.\n\n**Wave**: 1\n\n"
            "### 03-c: Charlie\n\nDo c.\n\n**Wave**: 2\n"
        )
        self.env = {**os.environ, "PATH": f"{self.stub}{os.pathsep}{os.environ['PATH']}",
                    "STUB_DIR": str(self.stub), "ORCA_CLI_COMMAND": str(self.stub / "orca")}
        assert self.set_status("--start").returncode == 0

    def rules(self, rules):
        """Replace the stub answers, and clear the log."""
        (self.stub / "rules.json").write_text(json.dumps(rules))
        (self.stub / "log").write_text("")

    def log(self):
        return (self.stub / "log").read_text().splitlines()

    def status(self):
        return {i["id"]: i for i in json.loads((self.ws / "_status.json").read_text())["items"]}

    def set_status(self, *args):
        return subprocess.run([sys.executable, str(SET_STATUS), str(self.ws), *args], capture_output=True, text=True, env=self.env)

    def run(self, script, *args):
        return subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, env=self.env)


BRANCH = {"match": "branch --show-current", "out": "feat-a\n"}
PR = {"match": "pr list --head feat-a", "out": json.dumps([{"number": 7}])}


def integrate(f, item="01-a"):
    return f.run("integrate.py", str(f.ws), item, "--dispatch", "ctx_1", "--worktree", str(f.wt))


def test_pr_merge_runs_every_step_in_order():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root)
        f.rules([BRANCH, PR])
        r = integrate(f)
        assert r.returncode == 0, r.stdout + r.stderr
        log = [l for l in f.log() if not l.startswith("orca terminal")]
        assert log == [
            f"git -C {f.wt.resolve()} branch --show-current",
            "gh pr list --head feat-a --state all --json number",
            f"git -C {f.wt.resolve()} status --porcelain",
            f"git -C {f.wt.resolve()} log --oneline @{{upstream}}..HEAD",
            "gh pr merge 7 --merge",
            "orca orchestration worker-release --dispatch ctx_1 --json",
            f"orca worktree rm --worktree path:{f.wt.resolve()} --json",
            "gh issue close 11",
            "gh issue close 12",
        ], log
        assert f.status()["01-a"]["state"] == "complete" and f.status()["01-a"]["pr"] == 7
        assert not (f.ws / ".integrate-01-a.json").exists()


def test_each_failing_step_stops_there_and_a_rerun_resumes():
    failing = [
        ("drain check", {"match": "status --porcelain", "out": " M x\n"}),
        ("drain check", {"match": "log --oneline", "out": "abc unpushed\n"}),
        ("merge", {"match": "pr merge", "code": 1, "out": "conflict"}),
        ("release", {"match": "worker-release", "code": 1}),
        ("remove", {"match": "worktree rm", "code": 1}),
        ("close #12", {"match": "issue close 12", "code": 1}),
    ]
    for step, rule in failing:
        with tempfile.TemporaryDirectory() as root:
            f = Fixture(root)
            f.rules([rule, BRANCH, PR])
            r = integrate(f)
            assert r.returncode == 1 and r.stdout.splitlines()[-1].startswith(f"FAIL: {step}"), (step, r.stdout)
            assert f.status()["01-a"]["state"] == "todo", step
            assert not any("git merge" in l or l.startswith("git push") for l in f.log()), step  # no fallback to git
            before = f.log()
            f.rules([BRANCH, PR])
            r = integrate(f)
            assert r.returncode == 0 and f.status()["01-a"]["state"] == "complete", (step, r.stdout)
            redone = [l for l in f.log() if "branch --show-current" in l or "pr list" in l]
            assert redone == [], (step, redone)  # branch and PR come from the resume file
            # every step that succeeded before is skipped
            for line in before:
                if rule["match"] not in line and ("issue close" in line or "worker-release" in line or "pr merge" in line):
                    assert line not in f.log(), (step, line)


def test_complete_refused_by_set_status_stops_and_reruns_after_the_fix():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root, review=True)
        f.rules([BRANCH, PR])
        r = integrate(f)
        assert r.returncode == 1 and "FAIL: complete" in r.stdout and "not SHIP" in r.stdout, r.stdout
        assert f.set_status("01-a", "review", "1", "claude", "SHIP").returncode == 0
        f.rules([BRANCH, PR])
        r = integrate(f)
        assert r.returncode == 0 and f.status()["01-a"]["state"] == "complete", r.stdout
        assert all(l.startswith("orca terminal") for l in f.log()), f.log()  # only set_status ran


def test_pr_without_a_pr_is_refused_and_branch_completes_without_pr():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root, integration="pr")
        f.rules([BRANCH])
        r = integrate(f)
        assert r.returncode == 1 and "without --pr" in r.stdout, r.stdout
        assert not any("pr merge" in l or "issue close" in l for l in f.log())
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root, integration="branch")
        f.rules([BRANCH])
        r = integrate(f)
        assert r.returncode == 0, r.stdout
        assert f.status()["01-a"]["state"] == "complete" and f.status()["01-a"].get("pr") is None


def test_a_pr_opened_after_the_first_fail_is_found_on_the_rerun():
    for integration, fail in (("pr-merge", "FAIL: merge"), ("pr", "FAIL: complete")):
        with tempfile.TemporaryDirectory() as root:
            f = Fixture(root, integration=integration)
            f.rules([BRANCH])
            r = integrate(f)
            assert r.returncode == 1 and fail in r.stdout, (integration, r.stdout)
            f.rules([BRANCH, PR])
            r = integrate(f)
            assert r.returncode == 0, (integration, r.stdout)
            assert f.status()["01-a"]["state"] == "complete" and f.status()["01-a"]["pr"] == 7, integration


def test_commit_merges_first_and_refuses_the_wrong_checkout_branch():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root, integration="commit")
        f.rules([{"match": f"-C {f.ws.resolve()} branch --show-current", "out": "dev\n"}, BRANCH])
        r = integrate(f)
        assert r.returncode == 1 and "not main" in r.stdout, r.stdout
        f.rules([{"match": f"-C {f.ws.resolve()} branch --show-current", "out": "main\n"}, BRANCH])
        r = integrate(f)
        assert r.returncode == 0, r.stdout
        log = f.log()
        merge = log.index(f"git -C {f.ws.resolve()} merge --no-edit feat-a")
        assert log[merge + 1] == f"git -C {f.ws.resolve()} push origin main"
        assert log[merge + 2] == f"git -C {f.wt.resolve()} status --porcelain"
        assert f"git -C {f.wt.resolve()} log --oneline origin/main..HEAD" in log


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
