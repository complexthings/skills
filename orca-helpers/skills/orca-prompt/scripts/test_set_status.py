#!/usr/bin/env python3
"""Self-check for set_status.py. Run: python3 test_set_status.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "set_status.py")

CONFIG = {
    "workstream": "demo",
    "harnesses": [
        {"name": "claude", "tier": "standard"},
        {"name": "pi", "tier": "light"},
    ],
    "workItems": [
        {"id": "01-a", "size": "light", "wave": 1, "title": "Alpha"},
        {"id": "02-b", "size": "standard", "wave": 1, "title": "Bravo"},
        {"id": "03-c", "size": "standard", "wave": 2, "title": "Charlie"},
    ],
}


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def make_workstream(root, name="demo", config=CONFIG):
    d = Path(root) / name
    d.mkdir()
    (d / "_config.json").write_text(json.dumps(config))
    return d


def status(d):
    return json.loads((d / "_status.json").read_text())


def test_start_builds_every_item_todo_and_active():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        assert run(str(d), "--start").returncode == 0
        s = status(d)
        assert s["workstream"] == "demo" and s["active"] is True
        assert [(i["id"], i["wave"], i["title"], i["state"], i["reason"]) for i in s["items"]] == [
            ("01-a", 1, "Alpha", "todo", None),
            ("02-b", 1, "Bravo", "todo", None),
            ("03-c", 2, "Charlie", "todo", None),
        ]
        assert [p.name for p in d.iterdir() if p.name.endswith(".tmp")] == []


def test_moves_items_and_failed_keeps_reason():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        assert run(str(d), "01-a", "complete").returncode == 0
        assert run(str(d), "02-b", "failed", "tests red").returncode == 0
        items = {i["id"]: i for i in status(d)["items"]}
        assert items["01-a"]["state"] == "complete"
        assert (items["02-b"]["state"], items["02-b"]["reason"]) == ("failed", "tests red")
        run(str(d), "02-b", "in_progress")
        assert {i["id"]: i for i in status(d)["items"]}["02-b"]["reason"] is None


def test_bad_input_fails_and_leaves_file_untouched():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        before = (d / "_status.json").read_bytes()
        for args in (("99-x", "complete"), ("01-a", "done"), ("01-a", "failed"), ("--bogus",)):
            r = run(str(d), *args)
            assert r.returncode != 0, args
            assert r.stdout.startswith("FAIL:"), (args, r.stdout)
        assert (d / "_status.json").read_bytes() == before


def test_restart_keeps_progress_and_only_one_active():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        other = make_workstream(root, "other")
        run(str(other), "--start")
        run(str(d), "--start")
        run(str(d), "01-a", "complete")
        run(str(d), "--start")
        assert status(d)["items"][0]["state"] == "complete"
        assert status(other)["active"] is False


def test_stop_and_show():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        run(str(d), "03-c", "failed", "merge conflict")
        out = run(str(d), "--show").stdout
        assert "Wave 1 (0/2)" in out and "Wave 2 (0/1)" in out
        assert "! merge conflict" in out
        assert run(str(d), "--stop").returncode == 0
        assert status(d)["active"] is False


def test_start_routes_each_item_harness_by_size():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        assert [i["harness"] for i in status(d)["items"]] == ["pi", "claude", "claude"]
        one = {**CONFIG, "harnesses": [{"name": "claude", "tier": "standard"}]}
        e = make_workstream(root, "one", one)
        run(str(e), "--start")
        assert {i["harness"] for i in status(e)["items"]} == {"claude"}


def test_start_without_wave_data_fails():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root, config={"workstream": "old", "workItems": [{"id": "01-a", "size": "light"}]})
        r = run(str(d), "--start")
        assert r.returncode != 0 and r.stdout.startswith("FAIL:")
        assert not (d / "_status.json").exists()


def test_start_bad_tier_fails():
    with tempfile.TemporaryDirectory() as root:
        bad = dict(CONFIG, harnesses=[{"name": "claude", "tier": "heavy"}])
        r = run(str(make_workstream(root, config=bad)), "--start")
        assert r.returncode == 1 and r.stdout.startswith("FAIL:") and "Traceback" not in r.stderr, r
        assert not list(Path(root).glob("*/_status.json")), r  # nothing written


def test_start_stamps_started_at_once():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        s = status(d)
        assert s["startedAt"] and s["finishedAt"] is None
        assert all(i["pr"] is None for i in s["items"])
        s["startedAt"] = "2000-01-01T00:00:00Z"
        (d / "_status.json").write_text(json.dumps(s))
        run(str(d), "--start")
        assert status(d)["startedAt"] == "2000-01-01T00:00:00Z"


def _finish_stale(d):
    run(str(d), "--start")
    for i in ("01-a", "02-b", "03-c"):
        run(str(d), i, "complete")
    old = status(d)
    old.update(startedAt="2000-01-01T00:00:00Z", finishedAt="2000-01-01T01:00:00Z")
    (d / "_status.json").write_text(json.dumps(old))


def test_restart_of_finished_run_with_new_item_restamps_clock():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        _finish_stale(d)
        cfg = json.loads((d / "_config.json").read_text())
        cfg["workItems"].append({"id": "04-d", "title": "D", "wave": 2})
        (d / "_config.json").write_text(json.dumps(cfg))
        run(str(d), "--start")
        s = status(d)
        assert s["startedAt"] > "2000-01-01T00:00:00Z" and s["finishedAt"] is None


def test_restart_of_finished_run_all_complete_keeps_clock():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        _finish_stale(d)
        run(str(d), "--start")
        s = status(d)
        assert s["startedAt"] == "2000-01-01T00:00:00Z" and s["finishedAt"] == "2000-01-01T01:00:00Z"


def test_retry_of_finished_item_clears_then_restamps_finished_at():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        _finish_stale(d)
        run(str(d), "01-a", "in_progress")
        assert status(d)["finishedAt"] is None
        run(str(d), "01-a", "complete")
        assert status(d)["finishedAt"] > "2000-01-01T01:00:00Z"


def test_reopened_finished_run_restarts_clock_on_both_ends():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        _finish_stale(d)
        run(str(d), "01-a", "in_progress")
        s = status(d)
        assert s["startedAt"] > "2000-01-01T00:00:00Z" and s["finishedAt"] is None
        run(str(d), "01-a", "complete")
        s = status(d)
        assert s["startedAt"] > "2000-01-01T01:00:00Z" and s["finishedAt"] >= s["startedAt"]


def test_start_with_all_complete_and_no_finished_at_stamps_it():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        _finish_stale(d)
        s = status(d)
        s["finishedAt"] = None
        (d / "_status.json").write_text(json.dumps(s))
        run(str(d), "--start")
        s = status(d)
        assert s["startedAt"] == "2000-01-01T00:00:00Z" and s["finishedAt"] > "2000-01-01T01:00:00Z"


def test_complete_with_pr_stores_it_and_restart_keeps_it():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        assert run(str(d), "01-a", "complete", "--pr", "42").returncode == 0
        assert status(d)["items"][0]["pr"] == 42
        run(str(d), "--start")
        assert status(d)["items"][0]["pr"] == 42
        before = (d / "_status.json").read_bytes()
        for args in (("02-b", "in_progress", "--pr", "7"), ("02-b", "complete", "--pr", "x"), ("02-b", "complete", "--pr")):
            r = run(str(d), *args)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:"), (args, r.stdout)
        assert (d / "_status.json").read_bytes() == before


def test_last_complete_stamps_finished_at():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        run(str(d), "01-a", "complete")
        run(str(d), "02-b", "complete")
        assert status(d)["finishedAt"] is None
        run(str(d), "03-c", "complete", "--pr", "9")
        assert status(d)["finishedAt"]


def test_old_file_without_new_keys_still_works():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        old = status(d)
        for k in ("startedAt", "finishedAt"):
            del old[k]
        for i in old["items"]:
            del i["pr"]
        (d / "_status.json").write_text(json.dumps(old))
        assert "Wave 1 (0/2)" in run(str(d), "--show").stdout
        assert run(str(d), "01-a", "complete", "--pr", "5").returncode == 0
        run(str(d), "02-b", "complete")
        run(str(d), "03-c", "complete")
        s = status(d)
        assert s["finishedAt"] and s["items"][0]["pr"] == 5 and "pr" not in s["items"][1]
        assert s["startedAt"] is None
        assert run(str(d), "--start").returncode == 0
        s = status(d)
        assert s["startedAt"] is None and s["items"][1]["pr"] is None


def test_start_writes_the_owner_from_the_session_env():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "session-a"}
        assert subprocess.run([sys.executable, SCRIPT, str(d), "--start"], env=env).returncode == 0
        assert (d / "_status.json.owner").read_text() == "session-a"
        env.pop("CLAUDE_CODE_SESSION_ID")
        (d / "_status.json.owner").unlink()
        assert subprocess.run([sys.executable, SCRIPT, str(d), "--start"], env=env).returncode == 0
        assert not (d / "_status.json.owner").exists()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
