#!/usr/bin/env python3
"""Self-check for finish_work_item.py. Run: python3 test_finish_work_item.py"""
import json
import shlex
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_integrate import BRANCH, PR, Fixture

FILES = {"match": "diff -z --name-only origin/main...HEAD", "out": "a.py\0b c.py\0"}


def inbox(count, delivery=None, messages=()):
    return json.dumps({"result": {"dispatchId": "ctx_9", "count": count, "deliveryId": delivery, "messages": list(messages)}})


EMPTY = {"match": "check --terminal term_1 --json", "out": inbox(0)}


def finish(f, *extra):
    (f.ws / "01-a.prompt.md").exists() or (f.ws / "_completed").exists() or (f.ws / "01-a.prompt.md").write_text("x")
    return f.run("finish_work_item.py", str(f.ws), "01-a", "--terminal", "term_1", *extra)


def worker_done(r):
    # The command is last; a quoted file name holding a newline spans lines.
    start = r.stdout.rfind("\n", 0, r.stdout.rindex(" orchestration send ")) + 1
    return shlex.split(r.stdout[start:])


def test_happy_path_moves_checks_pr_drains_inbox_and_prints_worker_done():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root)
        f.rules([
            {"match": "check --terminal term_1 --ack d1 --json", "out": inbox(0)},
            {"match": "check --terminal term_1 --json", "out": inbox(1, "d1", [{"subject": "redirect"}])},
            BRANCH, PR, FILES,
        ])
        r = finish(f, "--report-path", "/tmp/r.md")
        assert r.returncode == 0, r.stdout + r.stderr
        assert f"git -C {f.ws.resolve()} mv 01-a.prompt.md _completed/01-a.prompt.md" in f.log()
        assert any("--ack d1" in l for l in f.log()) and '"redirect"' in r.stdout
        cmd = worker_done(r)
        assert cmd[:2] == [str(f.stub / "orca"), "orchestration"] and cmd[cmd.index("--type") + 1] == "worker_done"
        assert cmd[cmd.index("--from") + 1] == "term_1" and cmd[cmd.index("--dispatch-id") + 1] == "ctx_9"
        assert cmd[cmd.index("--outcome") + 1] == "succeeded" and cmd[cmd.index("--report-path") + 1] == "/tmp/r.md"
        assert cmd[cmd.index("--files-modified") + 1] == "a.py,b c.py" and "PR #7" in cmd[cmd.index("--body") + 1]


def test_each_failing_step_stops_there_and_a_rerun_finishes():
    for step, rule in [
        ("move", {"match": " mv ", "code": 1}),
        ("pr", {"match": "pr list", "out": "[]"}),
        ("inbox", {"match": "check --terminal", "code": 1}),
        ("files", {"match": "diff -z --name-only", "code": 128}),
    ]:
        with tempfile.TemporaryDirectory() as root:
            f = Fixture(root)
            f.rules([rule, EMPTY, BRANCH, PR, FILES])
            r = finish(f)
            assert r.returncode == 1 and r.stdout.splitlines()[-1].startswith(f"FAIL: {step}"), (step, r.stdout)
            assert "worker_done" not in r.stdout, step
            if step != "move":  # the stub git mv moves nothing, so file it the way git would
                (f.ws / "_completed" / "01-a.prompt.md").write_text("x")
                (f.ws / "01-a.prompt.md").unlink()
            f.rules([EMPTY, BRANCH, PR, FILES])
            r = finish(f)
            assert r.returncode == 0 and "worker_done" in r.stdout, (step, r.stdout)
            assert step == "move" or not any(" mv " in l for l in f.log()), step  # a filed prompt is not moved again


def test_files_modified_keeps_every_file_name_form():
    # `git diff -z` prints raw names, NUL-terminated; without -z git quotes non-ASCII and newlines.
    for name in ["b c.py", "café.py", 'q"x\'.py', "new\nline.py", "tab\t.py", None]:
        with tempfile.TemporaryDirectory() as root:
            f = Fixture(root)
            f.rules([EMPTY, BRANCH, PR, {**FILES, "out": f"{name}\0" if name else ""}])
            r = finish(f)
            assert r.returncode == 0, (name, r.stdout + r.stderr)
            cmd = worker_done(r)
            files = cmd[cmd.index("--files-modified") + 1] if "--files-modified" in cmd else None
            assert files == name, (name, cmd)


def test_branch_integration_skips_the_pr_check_and_omits_empty_flags():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root, integration="branch")
        f.rules([EMPTY])
        r = finish(f)
        assert r.returncode == 0, r.stdout
        assert not any("pr list" in l for l in f.log())
        cmd = worker_done(r)
        assert "--files-modified" not in cmd and "--report-path" not in cmd


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
