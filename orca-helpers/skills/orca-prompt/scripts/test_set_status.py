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



def test_progress_writes_done_total_note_and_at():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        run(str(d), "01-a", "in_progress")
        assert run(str(d), "01-a", "progress", "2/5", "Writing tests").returncode == 0
        p = status(d)["items"][0]["progress"]
        assert (p["done"], p["total"], p["note"]) == (2, 5, "Writing tests") and p["at"].endswith("+00:00")
        # A worker that re-plans may change its total.
        assert run(str(d), "01-a", "progress", "3/7", "Re-planned").returncode == 0
        assert (status(d)["items"][0]["progress"]["total"]) == 7
        # A resumed run keeps the step.
        run(str(d), "--start")
        assert status(d)["items"][0]["progress"]["done"] == 3


def test_progress_refuses_bad_input_and_leaves_file_untouched():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        before = (d / "_status.json").read_bytes()
        for args in (("99-x", "progress", "1/2", "n"), ("01-a", "progress", "3/2", "n"), ("01-a", "progress", "1/0", "n"),
                     ("01-a", "progress", "a/2", "n"), ("01-a", "progress", "-1/2", "n"), ("01-a", "progress", "1/2")):
            r = run(str(d), *args)
            assert r.returncode == 1, args
            assert r.stdout.startswith("FAIL:") and r.stdout.count("\n") == 1, (args, r.stdout)
        assert (d / "_status.json").read_bytes() == before


def test_leaving_in_progress_clears_progress():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        for state, reason in (("complete", None), ("failed", "tests red"), ("todo", None)):
            run(str(d), "01-a", "in_progress")
            run(str(d), "01-a", "progress", "1/2", "Half")
            run(str(d), "01-a", state, *([reason] if reason else []))
            assert status(d)["items"][0]["progress"] is None, state
        run(str(d), "01-a", "in_progress")
        run(str(d), "01-a", "progress", "1/2", "Half")
        run(str(d), "01-a", "in_progress")
        assert status(d)["items"][0]["progress"]["done"] == 1


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


def test_entered_at_moves_only_when_the_state_changes():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        first = status(d)["items"][0]["enteredAt"]
        assert first and all(i["enteredAt"] for i in status(d)["items"])
        time.sleep(1.1)
        run(str(d), "01-a", "todo")
        run(str(d), "--start")
        assert status(d)["items"][0]["enteredAt"] == first
        run(str(d), "01-a", "in_progress")
        moved = status(d)["items"][0]["enteredAt"]
        assert moved > first
        old = status(d)
        del old["items"][1]["enteredAt"]
        (d / "_status.json").write_text(json.dumps(old))
        run(str(d), "--start")
        assert status(d)["items"][0]["enteredAt"] == moved and status(d)["items"][1]["enteredAt"] is None


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


def test_start_upserts_the_run_registry_under_a_repo_only():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        env = {**os.environ, "CLAUDE_PLUGIN_DATA": data}
        prompts = Path(root) / "my-repo" / ".orca" / "prompts"
        prompts.mkdir(parents=True)
        d = make_workstream(prompts)
        start = lambda: subprocess.run([sys.executable, SCRIPT, str(d), "--start"], env=env).returncode
        assert start() == 0
        first = json.loads((Path(data) / "runs.json").read_text())["runs"]
        assert [(r["repoPath"], r["repoName"], r["workstream"]) for r in first] == [
            (str((Path(root) / "my-repo").resolve()), "my-repo", "demo")
        ]
        time.sleep(1.1)
        assert start() == 0
        second = json.loads((Path(data) / "runs.json").read_text())["runs"]
        assert len(second) == 1 and second[0]["startedAt"] > first[0]["startedAt"]
        # A Workstream outside .orca/prompts/ is no run to list.
        other = make_workstream(root, "loose")
        assert subprocess.run([sys.executable, SCRIPT, str(other), "--start"], env=env).returncode == 0
        assert len(json.loads((Path(data) / "runs.json").read_text())["runs"]) == 1


def test_log_appends_dated_entries_and_supersedes_without_rewriting():
    from datetime import date
    today = date.today().isoformat()
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        log = d / "_decisions.md"
        log.write_text("# Decision Log\n\nHeader text.\n")
        assert run(str(d), "log", "Use uv", "Pin the toolchain with uv.").returncode == 0
        assert run(str(d), "log", "Skip Pi", "Pi lacks --model.", "--commit", "skills-build@abc1234").returncode == 0
        old_entry = f"### {today} · Use uv\n\nPin the toolchain with uv.\n"
        assert log.read_text() == (
            "# Decision Log\n\nHeader text.\n\n" + old_entry
            + f"\n### {today} · Skip Pi\n\nPi lacks --model.\n\nCommit: skills-build@abc1234\n"
        )
        r = run(str(d), "log", "Use pip", "uv broke on CI.", "--supersedes", "Use uv")
        assert r.returncode == 0 and r.stdout == "", r.stdout
        text = log.read_text()
        # The old entry keeps its body and gains only the Superseded by line.
        assert old_entry + "\nSuperseded by: Use pip\n\n### " in text
        assert text.endswith(f"### {today} · Use pip\n\nuv broke on CI.\n\nSupersedes: Use uv\n")
        assert [p.name for p in d.iterdir() if p.name.endswith(".tmp")] == []
        # A superseded or unknown title, or bad input, fails once and leaves the log as it was.
        for args in (("--supersedes", "Use uv"), ("--supersedes", "Nope"), ("--bogus",)):
            r = run(str(d), "log", "T", "B", *args)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:") and r.stdout.count("\n") == 1, (args, r.stdout)
        for args in (("only-title",), ("T", "### heading"), ("", "B")):
            assert run(str(d), "log", *args).returncode == 1, args
        assert log.read_text() == text


def test_log_creates_a_missing_decision_log_with_its_header():
    import scaffold
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        assert run(str(d), "log", "First", "Body.").returncode == 0
        assert (d / "_decisions.md").read_text().startswith(scaffold.DECISION_LOG_HEADER + "\n### ")

def test_review_rounds_record_verdicts_and_the_third_no_ship_fails():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        item = lambda: {i["id"]: i for i in status(d)["items"]}["02-b"]
        assert run(str(d), "02-b", "review", "1", "codex").returncode == 0
        assert (item()["state"], item()["review"]) == ("reviewing", {"round": 1, "verdict": None, "reviewer": "codex"})
        # NO-SHIP sends the item back to its author.
        assert run(str(d), "02-b", "review", "1", "codex", "NO-SHIP").returncode == 0
        assert (item()["state"], item()["review"]["verdict"]) == ("in_progress", "NO-SHIP")
        run(str(d), "02-b", "review", "2", "codex", "NO-SHIP")
        assert item()["state"] == "in_progress" and item()["reason"] is None
        assert run(str(d), "02-b", "review", "3", "codex", "NO-SHIP").returncode == 0
        assert (item()["state"], item()["reason"]) == ("failed", "review: 3 NO-SHIP rounds")
        assert item()["review"] == {"round": 3, "verdict": "NO-SHIP", "reviewer": "codex"}
        # A resumed --start keeps the review.
        run(str(d), "--start")
        assert item()["review"]["round"] == 3
        # SHIP keeps reviewing until the Main Orchestrator completes the item.
        run(str(d), "01-a", "review", "1", "claude", "SHIP")
        a = status(d)["items"][0]
        assert (a["state"], a["review"]["verdict"]) == ("reviewing", "SHIP")
        assert "review" not in status(d)["items"][2]


def test_bad_review_input_fails_once_and_leaves_file_untouched():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        before = (d / "_status.json").read_bytes()
        for args in (("01-a", "review"), ("01-a", "review", "x", "codex"), ("01-a", "review", "0", "codex"),
                     ("01-a", "review", "4", "codex"), ("01-a", "review", "1", "codex", "MAYBE"), ("zz", "review", "1", "codex")):
            r = run(str(d), *args)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:") and r.stdout.count("\n") == 1, (args, r.stdout)
        assert (d / "_status.json").read_bytes() == before


def test_attention_sets_and_clears_one_open_question():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        assert status(d)["attention"] is None
        assert run(str(d), "--attention", "question", "Ship it?", "Yes", "No").returncode == 0
        a = status(d)["attention"]
        assert (a["kind"], a["question"], a["options"]) == ("question", "Ship it?", ["Yes", "No"]) and a["askedAt"]
        assert run(str(d), "--attention", "gate", "Pick a design").returncode == 0
        assert status(d)["attention"]["options"] == []
        # A move keeps the open question; only --clear drops it.
        run(str(d), "01-a", "complete")
        assert status(d)["attention"]["kind"] == "gate"
        assert run(str(d), "--attention", "--clear").returncode == 0
        assert status(d)["attention"] is None


def test_attention_bad_input_fails_and_leaves_file_untouched():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        before = (d / "_status.json").read_text()
        for args in (["--attention"], ["--attention", "alert", "Q?"], ["--attention", "question"], ["--attention", "question", ""], ["--attention", "--clear", "x"]):
            r = run(str(d), *args)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:"), args
        assert (d / "_status.json").read_text() == before


def test_start_records_the_orca_terminal_or_null():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as bin:
        d = make_workstream(root)
        orca = Path(bin) / "orca"
        orca.write_text('#!/bin/sh\necho \'{"ok": true, "result": {"terminal": {"handle": "term_abc"}}}\'\n')
        orca.chmod(0o755)
        # Pin the resolver to the `orca` stub; on Linux outside Orca it would pick `orca-ide`.
        env = {**os.environ, "ORCA_CLI_COMMAND": "orca", "PATH": f"{bin}{os.pathsep}{os.environ['PATH']}"}
        assert subprocess.run([sys.executable, SCRIPT, str(d), "--start"], env=env).returncode == 0
        assert status(d)["terminal"] == "term_abc"
        orca.write_text("#!/bin/sh\nexit 1\n")
        assert subprocess.run([sys.executable, SCRIPT, str(d), "--start"], env=env).returncode == 0
        assert status(d)["terminal"] is None


def test_twelve_parallel_writers_keep_every_update():
    config = {"workstream": "demo", "workItems": [{"id": f"{n:02}-x", "wave": 1, "title": f"T{n}"} for n in range(12)]}
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root, config=config)
        run(str(d), "--start")
        procs = [subprocess.Popen([sys.executable, SCRIPT, str(d), f"{n:02}-x", "progress", "1/2", f"n{n}"]) for n in range(12)]
        assert all(p.wait() == 0 for p in procs)
        assert [i["progress"]["note"] for i in status(d)["items"]] == [f"n{n}" for n in range(12)]


def test_complete_is_refused_without_ship_when_review_is_on():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root, config={**CONFIG, "review": True})
        run(str(d), "--start")
        before = (d / "_status.json").read_bytes()
        r = run(str(d), "01-a", "complete")
        assert r.returncode == 1 and r.stdout.startswith("FAIL:") and "SHIP" in r.stdout, r.stdout
        assert (d / "_status.json").read_bytes() == before
        run(str(d), "01-a", "review", "1", "codex", "NO-SHIP")
        assert run(str(d), "01-a", "complete").returncode == 1
        run(str(d), "01-a", "review", "2", "codex", "SHIP")
        assert run(str(d), "01-a", "complete").returncode == 0


def test_complete_is_refused_without_pr_under_pr_integration():
    for integration in ("pr", "pr-merge"):
        with tempfile.TemporaryDirectory() as root:
            d = make_workstream(root, config={**CONFIG, "integration": integration})
            run(str(d), "--start")
            before = (d / "_status.json").read_bytes()
            r = run(str(d), "01-a", "complete")
            assert r.returncode == 1 and "--pr" in r.stdout, r.stdout
            assert (d / "_status.json").read_bytes() == before
            assert run(str(d), "01-a", "complete", "--pr", "3").returncode == 0
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root, config={**CONFIG, "integration": "merge"})
        run(str(d), "--start")
        assert run(str(d), "01-a", "complete").returncode == 0


def test_next_wave_start_needs_the_wave_complete_and_its_retro():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        # Wave 1 items start freely.
        assert run(str(d), "01-a", "in_progress").returncode == 0
        run(str(d), "01-a", "complete")
        r = run(str(d), "03-c", "in_progress")
        assert r.returncode == 1 and "02-b" in r.stdout, r.stdout
        run(str(d), "02-b", "complete")
        before = (d / "_status.json").read_bytes()
        r = run(str(d), "03-c", "in_progress")
        assert r.returncode == 1 and "Wave 1 retro" in r.stdout, r.stdout
        assert (d / "_status.json").read_bytes() == before
        run(str(d), "log", "Wave 10 retro", "No failures.")
        assert run(str(d), "03-c", "in_progress").returncode == 1
        run(str(d), "log", "Wave 1 retro", "No failures.")
        assert run(str(d), "03-c", "in_progress").returncode == 0
        # Other moves of a later-Wave item are not gated.
        assert run(str(d), "03-c", "todo").returncode == 0


def test_run_and_task_ids_start_null_and_survive_restart():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        assert status(d)["runId"] is None and all(i["taskId"] is None for i in status(d)["items"])
        assert run(str(d), "run", "run_123").returncode == 0
        assert run(str(d), "02-b", "task", "task_9").returncode == 0
        run(str(d), "--start")
        s = status(d)
        assert s["runId"] == "run_123"
        assert [i["taskId"] for i in s["items"]] == [None, "task_9", None]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
