#!/usr/bin/env python3
"""Self-check for dispatch.py. Run: python3 test_dispatch.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_integrate import Fixture

RUN = {"match": "run-create", "out": json.dumps({"result": {"run": {"id": "run_1"}}})}


def task(item_id, task_id):
    return {"match": f"{item_id}.prompt.md", "out": json.dumps({"result": {"task": {"id": task_id}}})}


TASKS = [task("01-a", "task_a"), task("02-b", "task_b"), task("03-c", "task_c")]


def dispatch(f, *args):
    return f.run("dispatch.py", str(f.ws), *args)


def test_creates_run_and_tasks_and_prints_ready_lines():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root)
        f.rules([RUN, *TASKS])
        r = dispatch(f)
        assert r.returncode == 0, r.stdout + r.stderr
        stub = f.stub / "orca"
        assert r.stdout.splitlines() == [
            f"{stub} orchestration worker-start --task {t} --worktree new-child --name {i} --agent claude --model claude-opus-5-5 --effort medium --setup run --json"
            for i, t in (("01-a", "task_a"), ("02-b", "task_b"))
        ], r.stdout
        creates = [l for l in f.log() if "task-create" in l]
        assert len(creates) == 3 and "--run run_1" in creates[0] and "--deps" not in creates[1], creates
        assert '--deps ["task_a", "task_b"]' in creates[2], creates[2]
        assert json.loads((f.ws / "_status.json").read_text())["runId"] == "run_1"
        assert {i: s["taskId"] for i, s in f.status().items()} == {"01-a": "task_a", "02-b": "task_b", "03-c": "task_c"}


def test_reuses_run_skips_complete_and_deps_name_only_open_tasks():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root)
        assert f.set_status("run", "run_9").returncode == 0
        assert f.set_status("01-a", "complete").returncode == 1  # pr-merge needs --pr
        assert f.set_status("01-a", "complete", "--pr", "4").returncode == 0
        f.rules(TASKS)
        r = dispatch(f)
        assert r.returncode == 0, r.stdout
        assert not any("run-create" in l or "01-a.prompt.md" in l for l in f.log()), f.log()
        assert '--deps ["task_b"]' in [l for l in f.log() if "03-c" in l][0]
        assert len(r.stdout.splitlines()) == 1 and "--task task_b" in r.stdout  # 03-c waits on 02-b


def test_each_failing_step_stops_there_and_resume_creates_only_what_is_missing():
    for step, rules in [
        ("run-create", [{"match": "run-create", "code": 1}]),
        ("task-create 02-b", [RUN, TASKS[0], {"match": "02-b.prompt.md", "code": 1}]),
        ("task-create 03-c", [RUN, TASKS[0], TASKS[1], {"match": "03-c.prompt.md", "out": "{}"}]),
    ]:
        with tempfile.TemporaryDirectory() as root:
            f = Fixture(root)
            f.rules(rules)
            r = dispatch(f, "--resume")
            assert r.returncode == 1 and r.stdout.startswith(f"FAIL: {step}") and r.stdout.count("\n") == 1, (step, r.stdout)
            assert "worker-start" not in r.stdout
            f.rules([RUN, *TASKS])
            r = dispatch(f, "--resume")
            assert r.returncode == 0, (step, r.stdout)
            created = [l for l in f.log() if "task-create" in l or "run-create" in l]
            expected = {"run-create": 4, "task-create 02-b": 2, "task-create 03-c": 1}[step]
            assert len(created) == expected, (step, created)
            assert {i: s["taskId"] for i, s in f.status().items()} == {"01-a": "task_a", "02-b": "task_b", "03-c": "task_c"}


def test_failed_item_in_a_reached_wave_gets_a_new_task_and_a_line_once():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root)
        f.rules([RUN, *TASKS])
        assert dispatch(f).returncode == 0
        assert f.set_status("02-b", "failed", "tests red").returncode == 0
        f.rules([task("02-b", "task_b2")])
        r = dispatch(f, "--resume")
        assert r.returncode == 0, r.stdout
        assert "--task task_b2" in r.stdout and "--task task_a" in r.stdout, r.stdout
        assert f.status()["02-b"]["state"] == "todo" and f.status()["02-b"]["taskId"] == "task_b2"
        assert [l for l in f.log() if "task-create" in l] == [l for l in f.log() if "02-b.prompt.md" in l], f.log()
        assert len([l for l in f.log() if "task-create" in l]) == 1, f.log()
        f.rules([])
        assert "--task task_b2" in dispatch(f, "--resume").stdout
        assert not any("task-create" in l for l in f.log()), f.log()  # no second new Task


def test_unreadable_status_fails_before_any_orca_call():
    with tempfile.TemporaryDirectory() as root:
        f = Fixture(root)
        (f.ws / "_status.json").write_text("{not json")
        r = dispatch(f)
        assert r.returncode == 1 and r.stdout.startswith("FAIL: setup") and "--start" in r.stdout, r.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
