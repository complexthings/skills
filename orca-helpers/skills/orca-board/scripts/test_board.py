#!/usr/bin/env python3
"""Self-check for board.py. Run: python3 test_board.py"""
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import board

APP = Path(__file__).resolve().parents[3] / "board"
NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
# Usage reads harness logs from these homes; empty ones keep the real logs out of every test.
os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp()
os.environ["CODEX_HOME"] = tempfile.mkdtemp()
# Pin the resolver to the `orca` stubs these tests put on PATH; on Linux outside Orca it would pick `orca-ide`.
os.environ["ORCA_CLI_COMMAND"] = "orca"


def source_hash():
    """The same files, order and framing as sourceHash() in board/vite.config.js."""
    files = ["index.html", "package.json", "pnpm-lock.yaml", "tsconfig.json", "vite.config.js"]
    files += [p.relative_to(APP).as_posix() for p in (APP / "src").rglob("*") if p.is_file()]
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.encode() + b"\0" + (APP / f).read_bytes() + b"\0")
    return h.hexdigest()


def fake_repo(root, name, workstreams):
    repo = Path(root) / name
    for ws, items, extra in workstreams:
        extra = {"updatedAt": "2026-10-24T10:00:00+00:00", **extra}
        d = repo / ".orca" / "prompts" / ws
        d.mkdir(parents=True)
        (d / "_config.json").write_text(json.dumps({
            "workstream": ws,
            "harnesses": [{"name": "claude", "models": {"orchestrationWorker": {"model": "claude-opus-5-5", "effort": "medium"}}}],
        }))
        (d / "_status.json").write_text(json.dumps({"workstream": ws, "items": items, **extra}))
    return repo


PROGRESS = {"done": 2, "total": 5, "note": "Writing tests", "at": "2026-10-24T10:00:00+00:00"}
REVIEW = {"round": 2, "verdict": "NO-SHIP", "reviewer": "codex"}


def item(id, wave, state, **kw):
    return {"id": id, "title": id.title(), "wave": wave, "state": state, "reason": None, "harness": "claude", "pr": None, "enteredAt": None, **kw}


def registry(data, *runs):
    (Path(data) / "runs.json").write_text(json.dumps({"runs": [
        {"repoPath": str(repo), "repoName": repo.name, "workstream": ws, "startedAt": "2026-10-24T09:00:00+00:00"} for repo, ws in runs
    ]}))


def test_api_board_lists_repos_workstreams_waves_and_items():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        beta = fake_repo(root, "beta", [("ship", [item("a", 1, "complete", pr=12, enteredAt="2026-10-24T09:30:00+00:00"), item("b", 2, "failed", reason="tests red"), item("c", 3, "in_progress", progress=PROGRESS, review=REVIEW)], {"active": True})])
        alpha = fake_repo(root, "alpha", [
            ("one", [item("x", 1, "complete")], {"active": False, "finishedAt": "2026-10-24T11:00:00+00:00"}),
            ("two", [item("y", 1, "todo")], {"active": False}),
        ])
        registry(data, (beta, "ship"), (alpha, "one"), (alpha, "two"), (alpha, "gone"))
        b = board.build_board(data, now=NOW)
        assert [(a["kind"], a["workstream"], a["item"], a["reason"]) for a in b["attention"]] == [("failed", "ship", {"id": "b", "title": "B"}, "tests red")]
        assert b["generatedAt"] == "2026-10-24T12:00:00+00:00"
        assert [(r["name"], [w["name"] for w in r["workstreams"]]) for r in b["repos"]] == [("alpha", ["one", "two"]), ("beta", ["ship"])]
        alpha_lane, beta_lane = b["repos"]
        assert [w["state"] for w in alpha_lane["workstreams"]] == ["finished", "stopped"]
        ship = beta_lane["workstreams"][0]
        assert (ship["state"], ship["lastChange"], ship["totals"]) == ("active", "2026-10-24T10:00:00+00:00", None)
        assert [(w["n"], w["title"], w["state"]) for w in ship["waves"]] == [(1, "Wave 1", "complete"), (2, "Wave 2", "active"), (3, "Wave 3", "upcoming")]
        a, = ship["waves"][0]["items"]
        # The PR lookup runs in the background, so the first poll has no url or state yet.
        assert a == {"id": "a", "title": "A", "column": "complete", "harness": "claude", "mood": "red", "model": "claude-opus-5-5",
                     "effort": "medium", "pr": {"number": 12, "url": None, "state": None}, "enteredAt": "2026-10-24T09:30:00+00:00",
                     "reason": None, "progress": None, "review": None, "usage": None}
        assert ship["waves"][1]["items"][0]["reason"] == "tests red"
        assert ship["waves"][2]["items"][0]["pr"] is None and ship["waves"][2]["items"][0]["enteredAt"] is None
        assert ship["waves"][2]["items"][0]["progress"] == PROGRESS
        # The review record passes through beside progress, so the Board can draw the Reviewing column.
        assert ship["waves"][2]["items"][0]["review"] == REVIEW
        # No logs: no series, no Wave start; a config without budgetUsd or maxConcurrency reads them as null.
        assert (ship["series"], ship["budgetUsd"], ship["maxConcurrency"], ship["running"]) == (None, None, None, 1)
        assert [w["startedAt"] for w in ship["waves"]] == [None, None, None]


def test_moods_match_the_wave_band():
    # Expected values come from hooks/waves.ts avatarMood for the same inputs.
    ids = list("pqrstuvw")
    assert [board._mood("ship", 2, ids, i) for i in ids] == ["default", "red", "green", "blue", "yellow", "teal", "purple", "default"]


def test_pr_url_and_state_come_from_gh_and_a_merged_pr_is_cached():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "gamma", [("ws", [item("a", 1, "complete", pr=7), item("b", 1, "in_progress", pr=8)], {"active": True})])
        registry(data, (repo, "ws"))
        bin_dir = Path(root) / "bin"
        bin_dir.mkdir()
        calls = Path(root) / "calls"
        (bin_dir / "gh").write_text(f"""#!/bin/sh
echo "$3" >> {calls}
[ "$3" = 7 ] && echo '{{"url": "https://github.com/o/gamma/pull/7", "state": "MERGED"}}' && exit 0
exit 1
""")
        (bin_dir / "gh").chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        try:
            board.build_board(data)
            for _ in range(50):
                if not board._fetching:
                    break
                time.sleep(0.1)
            a, b = board.build_board(data)["repos"][0]["workstreams"][0]["waves"][0]["items"]
        finally:
            os.environ["PATH"] = old_path
        assert a["pr"] == {"number": 7, "url": "https://github.com/o/gamma/pull/7", "state": "MERGED"}
        assert b["pr"] == {"number": 8, "url": None, "state": None}
        # Merged is final, and a failed lookup waits out PR_TTL: one call each.
        assert sorted(calls.read_text().split()) == ["7", "8"]


def test_a_status_without_items_keeps_its_lane_with_no_waves():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "delta", [("new", [], {"active": True})])
        status = repo / ".orca" / "prompts" / "new" / "_status.json"
        status.write_text(json.dumps({"workstream": "new", "active": True}))
        registry(data, (repo, "new"))
        ws, = board.build_board(data)["repos"][0]["workstreams"]
        assert (ws["name"], ws["state"], ws["waves"]) == ("new", "active", [])


def ago(hours):
    return (NOW - timedelta(hours=hours)).isoformat()


def test_recent_window_keeps_active_and_recent_and_drops_old_and_missing():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "r", [
            ("live", [item("a", 1, "todo")], {"active": True, "updatedAt": ago(500)}),
            ("fresh", [item("b", 1, "complete")], {"active": False, "finishedAt": ago(119), "updatedAt": ago(119)}),
            ("halted", [item("c", 1, "todo")], {"active": False, "updatedAt": ago(100)}),
            ("old", [item("d", 1, "complete")], {"active": False, "finishedAt": ago(121), "updatedAt": ago(121)}),
            ("stale", [item("e", 1, "todo")], {"active": False, "updatedAt": ago(200)}),
        ])
        registry(data, *[(repo, ws) for ws in ("live", "fresh", "halted", "old", "stale")], (Path(root) / "deleted", "x"))
        names = lambda: [w["name"] for r in board.build_board(data, now=NOW)["repos"] for w in r["workstreams"]]
        assert names() == ["live", "fresh", "halted"]
        (Path(data) / "settings.json").write_text(json.dumps({"recentWindowHours": 300}))
        assert names() == ["live", "fresh", "halted", "old", "stale"]
        (Path(data) / "settings.json").write_text(json.dumps({"recentWindowHours": 50}))
        assert names() == ["live"]


def test_recent_window_hours_defaults_to_120():
    with tempfile.TemporaryDirectory() as data:
        assert board.recent_window_hours(data) == 120
        for bad in ("not json", '{"recentWindowHours": "48"}', '{"recentWindowHours": 0}', '{"recentWindowHours": true}', "[1]"):
            (Path(data) / "settings.json").write_text(bad)
            assert board.recent_window_hours(data) == 120, bad
        (Path(data) / "settings.json").write_text('{"recentWindowHours": 24, "reviews": {}}')
        assert board.recent_window_hours(data) == 24


def test_empty_or_missing_registry_is_an_empty_board():
    with tempfile.TemporaryDirectory() as data:
        assert board.build_board(data)["repos"] == []
        (Path(data) / "runs.json").write_text("not json")
        assert board.build_board(data)["repos"] == []


def test_server_binds_127_0_0_1_serves_page_and_exits_when_idle():
    with tempfile.TemporaryDirectory() as data:
        server = board.make_server(data, idle_seconds=1)
        host, port = server.server_address
        assert host == "127.0.0.1"
        t = threading.Thread(target=server.serve_forever)
        t.start()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board") as r:
            assert json.load(r)["repos"] == []
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
            assert b'id="root"' in r.read()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/avatars/manifest.json") as r:
            assert "claude_progress_red_24" in json.load(r) and r.headers["Cache-Control"] == "max-age=3600"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/avatars/claude_progress_red_24_0.svg") as r:
            assert r.headers["Content-Type"] == "image/svg+xml" and r.read().startswith(b"<svg")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/../board.py")
            raise AssertionError("served a file outside dist/")
        except urllib.error.HTTPError as e:
            assert e.code == 404
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/avatars/%2e%2e/%2e%2e/owner.ts")
            raise AssertionError("served a file outside avatars/")
        except urllib.error.HTTPError as e:
            assert e.code == 404
        # Polls hold it open; 1 second after the last one it stops.
        for _ in range(3):
            time.sleep(0.5)
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board").close()
        assert t.is_alive()
        t.join(timeout=4)
        assert not t.is_alive()


def test_start_reuses_the_running_server_and_stop_ends_it():
    with tempfile.TemporaryDirectory() as data:
        port, new = board.start(data)
        try:
            assert new is True
            assert board.start(data) == (port, False)
        finally:
            assert board.stop(data) is True
        for _ in range(30):
            if not (Path(data) / "board-server.json").exists():
                break
            time.sleep(0.1)
        assert board.running(data) is None and not (Path(data) / "board-server.json").exists()
        assert board.stop(data) is False



def test_attention_lists_questions_gates_and_failed_items_and_drops_cleared_ones():
    asked = lambda kind="question": {"kind": kind, "question": "Ship it?", "options": ["Yes", "No"], "askedAt": "2026-10-24T10:05:00+00:00"}
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "beta", [
            # Wave 1 in flight: a plain question.
            ("mid", [item("a", 1, "in_progress"), item("f", 1, "failed", reason="tests red")], {"active": True, "terminal": "term_1", "attention": asked()}),
            # Wave 1 done, Wave 2 not started: a question here is a Decision Gate.
            ("gap", [item("a", 1, "complete"), item("b", 2, "todo")], {"active": False, "attention": asked()}),
            ("told", [item("a", 1, "in_progress")], {"active": False, "attention": asked("gate")}),
            ("calm", [item("a", 1, "in_progress")], {"active": False, "attention": None}),
        ])
        registry(data, *[(repo, ws) for ws in ("mid", "gap", "told", "calm")])
        got = [(a["kind"], a["workstream"], a["canJump"]) for a in board.build_board(data, now=NOW)["attention"]]
        assert got == [("question", "mid", True), ("gate", "gap", False), ("gate", "told", False), ("failed", "mid", True)]
        q = board.build_board(data, now=NOW)["attention"][0]
        assert (q["repo"], q["repoPath"], q["question"], q["options"], q["askedAt"], q["item"]) == ("beta", str(repo), "Ship it?", ["Yes", "No"], "2026-10-24T10:05:00+00:00", None)
        # Cleared by `--attention --clear`, it leaves the Board.
        status = repo / ".orca" / "prompts" / "mid" / "_status.json"
        status.write_text(json.dumps({**json.loads(status.read_text()), "attention": None}))
        assert [a["kind"] for a in board.build_board(data, now=NOW)["attention"] if a["workstream"] == "mid"] == ["failed"]


def test_jump_switches_to_the_owning_terminal_or_says_why_not():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as bin:
        repo = fake_repo(root, "beta", [("ws", [item("a", 1, "todo")], {"active": True, "terminal": "term_1"}),
                                        ("bare", [item("a", 1, "todo")], {"active": True})])
        registry(data, (repo, "ws"), (repo, "bare"))
        log = Path(bin) / "argv"
        orca = Path(bin) / "orca"
        orca.write_text(f'#!/bin/sh\necho "$@" > {log}\n')
        orca.chmod(0o755)
        server = board.make_server(data, idle_seconds=30)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

        def post(body, kind="application/json"):
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/jump", data=json.dumps(body).encode(), headers={"Content-Type": kind, "X-Orca-Board-Token": server.token})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                return e.code, json.load(e)

        path = os.environ["PATH"]
        try:
            os.environ["PATH"] = f"{bin}{os.pathsep}{path}"
            assert post({"repoPath": str(repo), "workstream": "ws"}) == (200, {"ok": True})
            assert log.read_text().split() == ["terminal", "switch", "--terminal", "term_1"]
            assert post({"repoPath": str(repo), "workstream": "bare"})[0] == 409
            assert post({"repoPath": str(repo), "workstream": "nope"})[0] == 404
            assert post({"repoPath": str(repo), "workstream": "ws"}, kind="text/plain")[0] == 400
            orca.write_text("#!/bin/sh\necho 'Orca is not running' >&2\nexit 1\n")
            code, out = post({"repoPath": str(repo), "workstream": "ws"})
            assert code == 502 and "Orca is not running" in out["error"]
            os.environ["PATH"] = str(Path(bin) / "empty")
            code, out = post({"repoPath": str(repo), "workstream": "ws"})
            assert code == 502 and "not installed" in out["error"]
        finally:
            os.environ["PATH"] = path
            server.shutdown()


def test_review_drafts_are_attention_items_that_jump_to_the_loop_and_clear_once_posted():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as bin:
        repo = Path(root) / "home"
        draft = Path(data) / "round-1.json"
        draft.write_text(json.dumps({"event": "REQUEST_CHANGES", "body": "", "comments": []}))
        entry = {"title": "Fix it", "url": "https://github.com/o/r/pull/3", "author": "ann", "headSha": "abc", "round": 1, "worker": "ctx_1"}
        prs = {"2": {**entry, "number": 2, "draft": None, "verdict": None},
               "3": {**entry, "number": 3, "draft": str(draft), "verdict": None}}
        led = Path(data) / "pr-review" / "o__r.json"
        led.parent.mkdir()
        led.write_text(json.dumps({"repo": "o/r", "prs": prs}))
        (Path(data) / "pr-review" / "loop.json").write_text(json.dumps({"active": True, "repoPath": str(repo), "terminal": "term_loop"}))
        (Path(data) / "runs.json").write_text(json.dumps({"runs": [
            {"repoPath": str(repo), "repoName": "home", "workstream": "orca-pr-review", "kind": "pr-review"}]}))
        a, = board.build_board(data)["attention"]
        assert a == {"kind": "review_draft", "repo": "o/r", "repoPath": str(repo), "workstream": "orca-pr-review",
                     "question": None, "options": [], "askedAt": None, "canJump": True,
                     "item": {"id": "o/r#3", "title": "Fix it"}, "reason": "Approve it in the session with /orca-pr-review approve o/r#3.",
                     "verdict": "REQUEST_CHANGES", "url": "https://github.com/o/r/pull/3"}
        # Jump focuses the terminal `pr_review.py start` recorded, the loop's session.
        log = Path(bin) / "argv"
        (Path(bin) / "orca").write_text(f'#!/bin/sh\necho "$@" > {log}\n')
        (Path(bin) / "orca").chmod(0o755)
        path = os.environ["PATH"]
        try:
            os.environ["PATH"] = f"{bin}{os.pathsep}{path}"
            assert board.jump(data, a["repoPath"], a["workstream"]) == (200, {"ok": True})
        finally:
            os.environ["PATH"] = path
        assert log.read_text().split() == ["terminal", "switch", "--terminal", "term_loop"]
        # Posting records the verdict, which clears the Attention Item.
        prs["3"]["verdict"] = "CHANGES_REQUESTED"
        led.write_text(json.dumps({"repo": "o/r", "prs": prs}))
        assert board.build_board(data)["attention"] == []


def test_reviews_come_from_the_ledger_with_ci_passed_over_total_from_gh():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        entry = {"title": "Ledger title", "url": "https://github.com/o/r/pull/0", "author": "ann", "claimedAt": "2026-10-24T09:00:00+00:00",
                 "headSha": None, "round": 0, "verdict": None, "worker": None, "draft": None}
        prs = {
            "1": {**entry, "number": 1},
            "2": {**entry, "number": 2, "worker": "term_a", "harness": "codex", "round": 1},
            "3": {**entry, "number": 3, "worker": "term_a", "draft": "/tmp/d.json", "round": 1},
            "4": {**entry, "number": 4, "verdict": "CHANGES_REQUESTED", "round": 1},
            "5": {**entry, "number": 5, "verdict": "APPROVED", "round": 2},
            "6": {**entry, "number": 6, "verdict": "APPROVED", "round": 1},
        }
        (Path(data) / "pr-review").mkdir()
        (Path(data) / "pr-review" / "o__r.json").write_text(json.dumps({"repo": "o/r", "scannedAt": None, "prs": prs}))
        (Path(data) / "pr-review" / "loop.json").write_text(json.dumps({"active": True}))
        bin_dir = Path(root) / "bin"
        bin_dir.mkdir()
        # PR 1: pass, fail, pending and skipped checks (gh exits 8 while any are pending). PR 6 is merged. Others: gh fails.
        (bin_dir / "gh").write_text("""#!/bin/sh
case "$2 $3" in
  "view 1") echo '{"url": "https://github.com/o/r/pull/1", "title": "Live title", "author": {"login": "bob"}, "assignees": [{"login": "me"}],
            "headRefName": "feat", "baseRefName": "main", "state": "OPEN", "isDraft": true}' ;;
  "checks 1") echo '[{"bucket": "pass"}, {"bucket": "pass"}, {"bucket": "fail"}, {"bucket": "pending"}, {"bucket": "skipping"}]'; exit 8 ;;
  "view 6") echo '{"state": "MERGED"}' ;;
  "checks 6") echo '[]' ;;
  *) exit 1 ;;
esac
""")
        (bin_dir / "gh").chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        try:
            first = board.build_board(data)["reviews"]
            for _ in range(50):
                if not board._review_fetching:
                    break
                time.sleep(0.1)
            reviews = board.build_board(data)["reviews"]
        finally:
            os.environ["PATH"] = old_path
        # Before gh answers, a card has the ledger's fields only.
        assert first["repos"][0]["prs"][0] == {"number": 1, "url": "https://github.com/o/r/pull/0", "title": "Ledger title", "author": "ann",
                                              "assignees": None, "head": None, "base": None, "checks": None, "status": None,
                                              "round": 0, "harness": None, "column": "new", "claimedAt": "2026-10-24T09:00:00+00:00", "finishedAt": None, "held": False, "draft": None, "mine": False}
        repo, = reviews["repos"]
        assert repo["name"] == "o/r"
        one = repo["prs"][0]
        assert one == {"number": 1, "url": "https://github.com/o/r/pull/1", "title": "Live title", "author": "bob", "assignees": ["me"],
                       "head": "feat", "base": "main", "checks": {"passed": 2, "total": 4}, "status": "DRAFT",
                       "round": 0, "harness": None, "column": "new", "claimedAt": "2026-10-24T09:00:00+00:00", "finishedAt": None, "held": False, "draft": None, "mine": False}
        assert [(p["number"], p["column"], p["harness"]) for p in repo["prs"]] == [
            (1, "new", None), (2, "reviewing", "codex"), (3, "draft_ready", None), (4, "changes_requested", None), (5, "approved", None)]


def test_finished_reviews_show_inside_the_window_from_the_ledger_alone():
    with tempfile.TemporaryDirectory() as data:
        now = datetime.now(timezone.utc)
        (Path(data) / "settings.json").write_text(json.dumps({"recentWindowHours": 2}))
        draft = Path(data) / "round-1.json"
        draft.write_text(json.dumps({"event": "APPROVE", "body": "", "comments": []}))
        entry = {"title": "Done", "url": "https://github.com/o/r/pull/1", "author": "ann", "claimedAt": "2026-10-24T09:00:00+00:00",
                 "round": 1, "worker": None, "harness": "claude", "draft": str(draft)}
        ago = lambda hours: (now - timedelta(hours=hours)).isoformat(timespec="seconds")
        prs = {"1": {**entry, "number": 1, "verdict": "APPROVED", "state": "MERGED", "finishedAt": ago(1)},
               "2": {**entry, "number": 2, "verdict": "CHANGES_REQUESTED", "state": "CLOSED", "finishedAt": ago(1.9)},
               # A finished entry with a draft and no verdict: never a Review Draft to approve.
               "3": {**entry, "number": 3, "verdict": None, "state": "MERGED", "finishedAt": ago(1)},
               "4": {**entry, "number": 4, "verdict": "APPROVED", "state": "MERGED", "finishedAt": ago(3)}}
        (Path(data) / "pr-review").mkdir()
        (Path(data) / "pr-review" / "o__r.json").write_text(json.dumps({"repo": "o/r", "prs": prs}))
        live = board._live_review
        board._live_review = lambda *a: (_ for _ in ()).throw(AssertionError(f"gh asked about {a}"))
        try:
            got = board.build_board(data)
        finally:
            board._live_review = live
        assert got["attention"] == []
        one, two, three = got["reviews"]["repos"][0]["prs"]
        assert one == {"number": 1, "url": "https://github.com/o/r/pull/1", "title": "Done", "author": "ann", "assignees": None,
                       "head": None, "base": None, "checks": None, "status": "MERGED", "round": 1, "harness": "claude",
                       "column": "approved", "claimedAt": "2026-10-24T09:00:00+00:00", "finishedAt": prs["1"]["finishedAt"], "held": False, "draft": None, "mine": False}
        assert (two["status"], two["column"]) == ("CLOSED", "changes_requested")
        assert (three["number"], three["column"], three["held"], three["draft"]) == (3, "reviewing", False, None)
        # review_attention() alone also skips the finished entry with a draft.
        assert board.review_attention(data) == []


def test_no_ledgers_is_an_empty_reviews_section():
    with tempfile.TemporaryDirectory() as data:
        assert board.build_board(data)["reviews"] == {"repos": []}


def test_hand_reviews_on_watched_repos_show_as_mine_once_and_inside_the_window():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        board._own.clear()
        (Path(data) / "review-settings.json").write_text(json.dumps({"o/r": {"watched": True}, "o/new": {"watched": True}, "o/off": {"watched": False}}))
        (Path(data) / "pr-review").mkdir()
        entry = {"title": "T", "url": "u", "author": "ann", "round": 1, "verdict": "APPROVED", "worker": None, "draft": None}
        (Path(data) / "pr-review" / "O__R.json").write_text(json.dumps({"repo": "O/R", "prs": {"5": {**entry, "number": 5}}}))
        # build_reviews reads the real clock, so these sit 1 and 200 hours before it.
        recent, old = [(datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=h)).isoformat().replace("+00:00", "Z") for h in (1, 200)]
        pr = lambda n, state, **kw: {"number": n, "title": f"PR {n}", "url": f"https://github.com/o/r/pull/{n}", "state": state, "isDraft": False,
                                     "createdAt": old, "updatedAt": recent, "closedAt": "0001-01-01T00:00:00Z", "author": {"login": "bob"}, **kw}
        # 5 is the ledger's, 6 merged, 7 closed, 8 a draft, 9 open, 10 outside the window.
        found = [pr(5, "closed"), pr(6, "closed", closedAt=recent), pr(7, "closed", closedAt=recent), pr(8, "open", isDraft=True),
                 pr(9, "open"), pr(10, "open", updatedAt=old)]
        bin_dir, calls = Path(root) / "bin", Path(root) / "calls"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(f"""#!/bin/sh
echo "$*" >> {calls}
case "$*" in
  "search prs --reviewed-by @me --repo o/r "*--merged*) echo '[{{"number": 5}}, {{"number": 6}}]' ;;
  "search prs --reviewed-by @me --repo o/r "*) echo '{json.dumps(found)}' ;;
  "search "*) echo '[]' ;;
  "pr view "*) echo '{{"state": "OPEN"}}' ;;
  *) echo '[]' ;;
esac
""")
        (bin_dir / "gh").chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        settle = lambda: [time.sleep(0.1) for _ in range(50) if board._own_fetching or board._review_fetching]
        try:
            assert [r["name"] for r in board.build_reviews(data)["repos"]] == ["O/R"]  # nothing cached before gh answers
            settle()
            for _ in range(3):
                got = board.build_reviews(data)["repos"]
            settle()
        finally:
            os.environ["PATH"] = old_path
        repo, = got
        assert [(p["number"], p["mine"], p["status"], p["column"]) for p in repo["prs"]] == [
            (5, False, "OPEN", "approved"), (6, True, "MERGED", "approved"), (7, True, "CLOSED", "approved"), (8, True, "DRAFT", "approved"), (9, True, "OPEN", "approved")]
        assert repo["prs"][-1] == {"number": 9, "url": "https://github.com/o/r/pull/9", "title": "PR 9", "author": "bob", "assignees": None,
                                   "head": None, "base": None, "checks": None, "status": "OPEN", "round": None, "harness": None, "column": "approved",
                                   "claimedAt": old, "held": False, "draft": None, "mine": True, "finishedAt": None}
        assert repo["prs"][1]["finishedAt"] == recent
        searches = [c for c in calls.read_text().splitlines() if c.startswith("search")]
        # One plain and one merged search per Watched Repo, never for o/off, and none again inside OWN_TTL.
        assert len(searches) == 4 and not any("o/off" in c for c in searches), searches
        assert all(f"--updated >={(NOW.now(timezone.utc) - timedelta(hours=120)):%Y-%m-%d}" in c for c in searches), searches



def test_a_failed_merged_search_keeps_the_last_merged_answer():
    board._own.clear()
    pr = {"number": 6, "state": "closed", "closedAt": "2026-10-24T09:00:00Z"}
    old_gh = board._gh_json
    board._gh_json = lambda *a: [{"number": 6}] if "--merged" in a else [pr]
    try:
        board._fetch_own("o/r", "2026-10-20")
        board._gh_json = lambda *a: None if "--merged" in a else [pr]
        board._own_fetching.add("o/r")
        board._fetch_own("o/r", "2026-10-20")
    finally:
        board._gh_json = old_gh
    assert [board._own_card(p)["status"] for p in board._own["o/r"][1]] == ["MERGED"]
    assert "o/r" not in board._own_fetching


def test_a_failed_merged_search_with_no_earlier_answer_caches_nothing():
    board._own.clear()
    pr = {"number": 6, "state": "closed", "closedAt": "2026-10-24T09:00:00Z"}
    old_gh = board._gh_json
    board._gh_json = lambda *a: None if "--merged" in a else [pr]
    try:
        board._own_fetching.add("o/r")
        board._fetch_own("o/r", "2026-10-20")
    finally:
        board._gh_json = old_gh
    assert "o/r" not in board._own
    assert "o/r" not in board._own_fetching


def test_a_failed_plain_search_keeps_the_last_good_answer():
    board._own.clear()
    pr = {"number": 9, "state": "open", "updatedAt": "2026-10-24T09:00:00Z"}
    old_gh = board._gh_json
    board._gh_json = lambda *a: [] if "--merged" in a else [pr]
    try:
        board._fetch_own("o/r", "2026-10-20")
        good = board._own["o/r"]
        board._gh_json = lambda *a: [] if "--merged" in a else None
        board._own_fetching.add("o/r")
        board._fetch_own("o/r", "2026-10-20")
    finally:
        board._gh_json = old_gh
    assert board._own["o/r"] == good
    assert [board._own_card(p)["status"] for p in board._own["o/r"][1]] == ["OPEN"]
    assert "o/r" not in board._own_fetching


def jsonl(path, *rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")


def reply(id, model, **usage):
    return {"type": "assistant", "requestId": f"req_{id}", "message": {"id": id, "model": model, "usage": usage}}


def rollout(path, cwd, model, *counts):
    jsonl(path, {"type": "session_meta", "payload": {"cwd": cwd}}, {"type": "turn_context", "payload": {"model": model}},
          *({"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": c}}} for c in counts))


def test_usage_comes_from_claude_and_codex_logs_and_rolls_up():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "gamma", [
            ("ws", [item("c1", 1, "complete"), item("x1", 1, "complete", harness="codex"), item("c2", 2, "in_progress"),
                    item("p1", 2, "complete", harness="pi"), item("t1", 2, "todo")], {"active": True}),
            ("ws2", [item("c3", 1, "complete")], {"active": True}),
        ])
        registry(data, (repo, "ws"), (repo, "ws2"))
        claude, codex = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects", Path(os.environ["CODEX_HOME"]) / "sessions"
        opus = reply("m1", "claude-opus-5-5", input_tokens=1000, output_tokens=2000, cache_read_input_tokens=1_000_000,
                     cache_creation_input_tokens=10_000, cache_creation={"ephemeral_1h_input_tokens": 4000})
        # Claude Code logs one response once per content block, so m1 appears twice and counts once.
        jsonl(claude / "-w-gamma-c1" / "s1.jsonl", opus, opus, reply("m0", "<synthetic>", input_tokens=0, output_tokens=0))
        jsonl(claude / "-w-gamma-c1" / "s1" / "subagents" / "agent-1.jsonl", reply("m2", "claude-haiku-5-5", input_tokens=1_000_000, output_tokens=1_000_000))
        jsonl(claude / "-w-gamma-c2" / "s2.jsonl", reply("m3", "claude-mystery-9", input_tokens=5, output_tokens=5))
        jsonl(claude / "-w-gamma-c3" / "s3.jsonl", reply("m4", "claude-sonnet-5-5", input_tokens=1_000_000, output_tokens=0))
        jsonl(claude / "-w-gamma-p1" / "s4.jsonl", reply("m5", "claude-opus-5-5", input_tokens=9, output_tokens=9))
        day = codex / "2026" / "10" / "24"
        rollout(day / "rollout-a.jsonl", "/w/gamma/x1", "gpt-5.6-terra",
                {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 1},
                {"input_tokens": 1_000_000, "cached_input_tokens": 400_000, "output_tokens": 100_000})
        rollout(day / "rollout-b.jsonl", "/w/xgamma/x1", "gpt-5.6-terra", {"input_tokens": 7, "output_tokens": 7})
        try:
            b = board.build_board(data, now=NOW)
        finally:
            for d in (claude, codex):
                for p in sorted(d.rglob("*"), reverse=True):
                    p.unlink() if p.is_file() else p.rmdir()
        lane, = b["repos"]
        ws, ws2 = lane["workstreams"]
        got = {i["id"]: i["usage"] for w in ws["waves"] for i in w["items"]}
        assert got["c1"] == {"cost": 0.906, "input": 1_001_000, "output": 1_002_000, "cacheRead": 1_000_000, "cacheWrite": 10_000}
        assert got["x1"] == {"cost": 2.48, "input": 600_000, "output": 100_000, "cacheRead": 400_000, "cacheWrite": 0}
        # An unknown model, a harness with no parser and a Work Item with no log all read null, never zero.
        assert (got["c2"], got["p1"], got["t1"]) == (None, None, None)
        one = {"cost": 3.386, "input": 1_601_000, "output": 1_102_000, "cacheRead": 1_400_000, "cacheWrite": 10_000}
        assert ws["waves"][0]["totals"] == {**one, "missing": 0}
        assert ws["waves"][1]["totals"] is None
        # c2 and p1 started and have no usage; t1 is still to do, so it is not missing.
        assert ws["totals"] == {**one, "missing": 2}
        assert ws2["totals"] == {"cost": 2.0, "input": 1_000_000, "output": 0, "cacheRead": 0, "cacheWrite": 0, "missing": 0}
        assert lane["totals"] == {"cost": 5.386, "input": 2_601_000, "output": 1_102_000, "cacheRead": 1_400_000, "cacheWrite": 10_000, "missing": 2}


def at(minute, hour=9, **usage):
    return usage | {"timestamp": f"2026-10-24T{hour:02d}:{minute:02d}:30.000Z"}


def clear_logs():
    for d in (Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects", Path(os.environ["CODEX_HOME"]) / "sessions"):
        for p in sorted(d.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()


def set_config(repo, ws, **keys):
    path = repo / ".orca" / "prompts" / ws / "_config.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), **keys}))


def test_series_buckets_usage_per_model_and_marks_wave_starts():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "delta", [("ws", [item("a1", 1, "complete"), item("b1", 2, "in_progress"), item("b2", 2, "reviewing"),
                                                 item("x1", 2, "complete", harness="codex"), item("t1", 3, "todo")], {"active": True})])
        set_config(repo, "ws", budgetUsd=30, maxConcurrency=12)
        registry(data, (repo, "ws"))
        claude = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects"
        # a1 runs 08:00 to 08:20: the 08:20 reply follows a 10 minute pause, so it counts ACTIVE_GAP, not 600 seconds.
        jsonl(claude / "-w-delta-a1" / "s.jsonl", at(0, 8, **reply("m1", "claude-opus-5-5", input_tokens=1_000_000, output_tokens=0)),
              at(10, 8, **reply("m2", "claude-opus-5-5", input_tokens=0, output_tokens=100_000)),
              at(20, 8, **reply("m3", "claude-opus-5-5", input_tokens=0, output_tokens=0, cache_read_input_tokens=10)))
        jsonl(claude / "-w-delta-b1" / "s.jsonl", at(41, **reply("m4", "claude-haiku-5-5", input_tokens=1_000_000, output_tokens=0)),
              at(42, **reply("m5", "claude-mystery-9", input_tokens=5, output_tokens=5)))
        rollout(Path(os.environ["CODEX_HOME"]) / "sessions" / "rollout-x.jsonl", "/w/delta/x1", "gpt-5.6-luna",
                {"input_tokens": 1_000_000, "output_tokens": 0})
        lines = (Path(os.environ["CODEX_HOME"]) / "sessions" / "rollout-x.jsonl").read_text().splitlines()
        stamped = [json.dumps({**json.loads(l), "timestamp": f"2026-10-24T09:{40 + k}:00Z"}) for k, l in enumerate(lines[:-1])]
        (Path(os.environ["CODEX_HOME"]) / "sessions" / "rollout-x.jsonl").write_text("\n".join(stamped) + "\n")
        try:
            ws = board.build_board(data, now=NOW)["repos"][0]["workstreams"][0]
        finally:
            clear_logs()
        assert (ws["budgetUsd"], ws["maxConcurrency"], ws["running"]) == (30, 12, 2)
        # Wave markers: each Wave's earliest log entry, the codex session's first event in Wave 2; Wave 3 has not started.
        assert [w["startedAt"] for w in ws["waves"]] == ["2026-10-24T08:00:30+00:00", "2026-10-24T09:40:00+00:00", None]
        s = ws["series"]
        # 08:00:30 to 09:42:30 is 102 minutes: 5-minute buckets are the smallest under MAX_BUCKETS, the start floors to 08:00.
        assert (s["bucketSeconds"], s["start"], s["buckets"]) == (300, "2026-10-24T08:00:00+00:00", 21)
        assert [m["model"] for m in s["models"]] == ["claude-opus-5-5", "gpt-5.6-luna", "claude-haiku-5-5", "claude-mystery-9"]
        assert all(len(m[k]) == 21 for m in s["models"] for k in ("cost", "tokens", "seconds"))
        opus, luna, haiku, mystery = s["models"]
        assert opus["cost"] == [4.0, 0, 2.0, 0, 0.000002] + [0] * 16
        assert opus["tokens"] == [1_000_000, 0, 100_000, 0, 10] + [0] * 16
        assert opus["seconds"] == [0, 0, 300, 0, 300] + [0] * 16
        # The codex session lands at its last event with its whole span as agent time.
        assert (luna["cost"][20], luna["tokens"][20], luna["seconds"][20]) == (0.2, 1_000_000, 120)
        assert (haiku["cost"][20], haiku["seconds"][20]) == (0.1, 0)
        # A model prices.json lacks keeps its tokens and time, with every cost null.
        assert mystery["cost"] == [None] * 21 and mystery["tokens"][20] == 10 and mystery["seconds"][20] == 60


def test_one_reply_is_a_one_bucket_series_and_odd_config_values_read_null():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "e", [("w", [item("a", 1, "in_progress")], {"active": True})])
        set_config(repo, "w", budgetUsd="30", maxConcurrency=True)
        registry(data, (repo, "w"))
        claude = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects"
        # A reply with no timestamp counts in usage but not in the series.
        jsonl(claude / "-w-e-a" / "s.jsonl", at(5, **reply("m1", "claude-opus-5-5", input_tokens=10, output_tokens=0)),
              reply("m2", "claude-opus-5-5", input_tokens=1, output_tokens=0))
        try:
            ws = board.build_board(data, now=NOW)["repos"][0]["workstreams"][0]
        finally:
            clear_logs()
        assert (ws["budgetUsd"], ws["maxConcurrency"]) == (None, None)
        assert ws["totals"]["input"] == 11
        assert ws["series"] == {"bucketSeconds": 60, "start": "2026-10-24T09:05:00+00:00", "buckets": 1,
                                "models": [{"model": "claude-opus-5-5", "cost": [0.00004], "tokens": [10], "seconds": [0]}]}


def test_codex_wave_starts_at_first_event_and_budget_infinity_reads_null():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "f", [("w", [item("x", 1, "in_progress", harness="codex")], {"active": True})])
        set_config(repo, "w", budgetUsd=float("inf"))
        registry(data, (repo, "w"))
        path = Path(os.environ["CODEX_HOME"]) / "sessions" / "rollout-f.jsonl"
        rollout(path, "/w/f/x", "gpt-5.6-luna", {"input_tokens": 10, "output_tokens": 0})
        stamps = ["2026-10-24T09:40:00Z", "2026-10-24T09:41:00Z", "2026-10-24T09:42:00Z"]
        path.write_text("".join(json.dumps({**json.loads(l), "timestamp": t}) + "\n" for l, t in zip(path.read_text().splitlines(), stamps)))
        try:
            board_ = board.build_board(data, now=NOW)
        finally:
            clear_logs()
        ws = board_["repos"][0]["workstreams"][0]
        assert ws["waves"][0]["startedAt"] == "2026-10-24T09:40:00+00:00"
        assert ws["budgetUsd"] is None
        json.dumps(board_, allow_nan=False)


def test_series_never_exceeds_max_buckets_for_any_span():
    # Property: every span from 1 second to 400 days, at any start offset, fits MAX_BUCKETS and every row lands in a bucket.
    rng = random.Random(262)
    spans = [1, 4 * 3600 - 241, 48 * 86400, 84 * 86400, 400 * 86400] + [round(10 ** rng.uniform(0, math.log10(400 * 86400))) for _ in range(3000)]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for span in spans:
        first = base + timedelta(seconds=rng.randrange(400 * 86400))
        when = (first, first + timedelta(seconds=rng.uniform(0, span)), first + timedelta(seconds=span))
        rows = [("claude-opus-5-5", 1, 0, 0, 0, 0, w, 0) for w in when]
        s = board.series(rows)
        assert 1 <= s["buckets"] <= board.MAX_BUCKETS, (span, first, s["bucketSeconds"], s["buckets"])
        assert sum(s["models"][0]["tokens"]) == len(rows), (span, first, s)


def test_prices_list_every_model_slot_default():
    for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1", "gpt-5.6-terra"):
        assert set(board.PRICES[model]) == {"input", "output", "cacheRead", "cacheWrite", "cacheWrite1h"}


def git(*args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def test_worktree_and_main_checkout_share_one_repo_name_and_the_worktree_logs():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        main = fake_repo(root, "kai-apps", [("done", [item("a", 1, "complete")], {"active": False, "updatedAt": ago(1)})])
        git("init", "-q", str(main))
        git("-C", str(main), "commit", "-q", "--allow-empty", "-m", "init")
        git("-C", str(main), "remote", "add", "origin", "git@github.com:Acme/Kai-Apps.git")
        wt = Path(root) / "workspaces" / "kai-apps" / "main-2"
        git("-C", str(main), "worktree", "add", "-q", str(wt))
        fake_repo(wt.parent, wt.name, [("live", [item("02-x", 1, "in_progress")], {"active": True, "startedAt": ago(2), "updatedAt": ago(1)})])
        registry(data, (main, "done"), (wt, "live"))
        # The worker's worktree sits beside main-2 under the main checkout's folder, not under main-2.
        jsonl(Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "-w-kai-apps-02-x" / "s.jsonl",
              reply("m1", "claude-opus-5-5", input_tokens=1_000_000, output_tokens=0) | {"timestamp": "2026-10-24T09:00:30Z"})
        try:
            b = board.build_board(data, now=NOW)
        finally:
            clear_logs()
        lane, = b["repos"]
        assert (lane["name"], lane["path"], lane["slug"]) == ("kai-apps", str(main.resolve()), "Acme/Kai-Apps")
        done, live = lane["workstreams"]
        # Each Workstream keeps its own checkout, where its _config.json and _status.json live.
        assert (done["path"], live["path"]) == (str(main), str(wt))
        x, = live["waves"][0]["items"]
        assert x["usage"]["cost"] == 4.0 and live["totals"]["cost"] == 4.0 and live["series"]["buckets"] == 1
        assert lane["totals"]["cost"] == 4.0
        assert b["attention"] == [] and board.main_checkout(wt) == board.main_checkout(main)
        # A Repo Name keyed by any checkout of the repo renames the whole repo.
        (Path(data) / "repo-names.json").write_text(json.dumps({str(wt): " Kai ", "/nowhere": 3}))
        assert [r["name"] for r in board.build_board(data, now=NOW)["repos"]] == ["Kai"]
        (Path(data) / "repo-names.json").write_text("not json")
        assert [r["name"] for r in board.build_board(data, now=NOW)["repos"]] == ["kai-apps"]


def test_loop_flags_and_watched_repos_without_a_checkout():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        main = fake_repo(root, "app", [("idle", [item("a", 1, "todo")], {"active": False, "updatedAt": ago(1)})])
        git("init", "-q", str(main))
        git("-C", str(main), "remote", "add", "origin", "https://github.com/acme/app.git")
        other = fake_repo(root, "tool", [("go", [item("b", 1, "in_progress")], {"active": True})])
        registry(data, (main, "idle"), (other, "go"))
        settings = {"ACME/app": {"watched": True}, "acme/remote": {"watched": True}, "acme/old": {"watched": False}, "bad": "x"}
        (Path(data) / "review-settings.json").write_text(json.dumps(settings))
        (Path(data) / "pr-review").mkdir()
        loop = Path(data) / "pr-review" / "loop.json"
        flags = lambda: [(r["name"], r["path"] is None, r["slug"], r["executeActive"], r["prReviewActive"]) for r in board.build_board(data, now=NOW)["repos"]]
        loop.write_text(json.dumps({"active": True}))
        assert flags() == [("app", False, "acme/app", False, True), ("remote", True, "acme/remote", False, True), ("tool", False, None, True, False)]
        loop.write_text(json.dumps({"active": False}))
        assert flags() == [("app", False, "acme/app", False, False), ("remote", True, "acme/remote", False, False), ("tool", False, None, True, False)]
        for bad in ("not json", "[1]"):
            (Path(data) / "review-settings.json").write_text(bad)
            assert [r["name"] for r in board.build_board(data, now=NOW)["repos"]] == ["app", "tool"]


def test_workstreams_carry_main_orchestrator_task_time_started_and_active():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "r", [("new", [], {"active": False}), ("run", [item("a", 1, "in_progress")], {"active": True, "startedAt": ago(1)}),
                                     ("odd", [], {"active": "yes"})])
        main = {"model": "claude-fable-5-1", "effort": "high"}
        set_config(repo, "run", taskTime="xhigh", mainOrchestratorHarness="claude",
                   harnesses=[{"name": "codex", "models": {"mainOrchestrator": None}}, {"name": "claude", "models": {"mainOrchestrator": main}}])
        set_config(repo, "odd", taskTime="forever", mainOrchestratorHarness="pi")
        registry(data, (repo, "new"), (repo, "run"), (repo, "odd"))
        got = {w["name"]: (w["mainOrchestrator"], w["taskTime"], w["started"], w["active"]) for w in board.build_board(data, now=NOW)["repos"][0]["workstreams"]}
        none = {"harness": None, "model": None, "effort": None}
        assert got == {"new": (none, "medium", False, False), "run": ({"harness": "claude", **main}, "xhigh", True, True),
                       "odd": ({**none, "harness": "pi"}, "medium", False, False)}


def test_a_merged_ledger_pr_is_never_asked_about_again_and_a_held_draft_carries_its_body():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        reviews = Path(data) / "pr-review" / "reviews" / "o__m-2"
        reviews.mkdir(parents=True)
        (reviews / "round-1.json").write_text(json.dumps({"event": "COMMENT", "body": "old"}))
        (reviews / "round-2.json").write_text(json.dumps({"event": "REQUEST_CHANGES", "body": "Fix the cache.", "comments": []}))
        entry = {"title": "T", "url": "u", "author": "ann", "verdict": None, "worker": "w"}
        prs = {"1": {**entry, "number": 1, "round": 1, "draft": None},
               "2": {**entry, "number": 2, "round": 2, "draft": str(reviews / "round-2.json")},
               "3": {**entry, "number": 3, "round": 2, "draft": str(reviews / "round-1.json")},
               "x": {"number": "4"}}
        (Path(data) / "pr-review" / "o__m.json").write_text(json.dumps({"repo": "o/m", "prs": prs}))
        bin_dir, calls = Path(root) / "bin", Path(root) / "calls"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(f"""#!/bin/sh
echo "$2 $3" >> {calls}
case "$2 $3" in
  "view 1") echo '{{"state": "MERGED"}}' ;;
  "view "*) echo '{{"state": "OPEN"}}' ;;
  *) echo '[]' ;;
esac
""")
        (bin_dir / "gh").chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        try:
            for _ in range(2):
                board.build_reviews(data)
                for _ in range(50):
                    if not board._review_fetching:
                        break
                    time.sleep(0.1)
                # Age every cached answer past PR_TTL, so only the final check holds a refresh back.
                for key, (at, found) in list(board._reviews.items()):
                    board._reviews[key] = (at - board.PR_TTL - 1, found)
            got = board.build_reviews(data)["repos"][0]["prs"]
            # The last call refreshes in the background too: let it finish before the temp dirs go.
            for _ in range(50):
                if not board._review_fetching:
                    break
                time.sleep(0.1)
        finally:
            os.environ["PATH"] = old_path
        assert calls.read_text().split("\n").count("view 1") == 1
        assert [(p["number"], p["held"], p["draft"]) for p in got] == [(2, True, {"event": "REQUEST_CHANGES", "body": "Fix the cache."}), (3, False, None)]


def test_when_parses_a_trailing_z_on_the_system_python():
    assert board._when("2026-10-24T09:00:30.000Z") == datetime(2026, 10, 24, 9, 0, 30, tzinfo=timezone.utc)
    assert (board._when(None), board._when(3), board._when("soon")) == (None, None, None)
    if Path("/usr/bin/python3").exists():
        out = subprocess.run(["/usr/bin/python3", "-c", "import board; print(board._when('2026-10-24T09:00:30.000Z'))"],
                             cwd=Path(__file__).parent, capture_output=True, text=True, check=True).stdout
        assert out.strip() == "2026-10-24 09:00:30+00:00", out


def test_a_codex_rollout_for_another_worktree_is_read_only_to_its_first_line():
    with tempfile.TemporaryDirectory() as root:
        day = Path(os.environ["CODEX_HOME"]) / "sessions" / "2026"
        rollout(day / "rollout-mine.jsonl", "/w/r/a", "gpt-5.6-terra", {"input_tokens": 10, "output_tokens": 1})
        rollout(day / "rollout-other.jsonl", "/w/r/b", "gpt-5.6-terra", {"input_tokens": 99, "output_tokens": 9})
        read, full = board._codex_file, []
        board._codex_file = lambda f: full.append(Path(f.name).name) or read(f)
        try:
            rows = board.log_rows("codex", "r", "a")
        finally:
            board._codex_file = read
            clear_logs()
        assert full == ["rollout-mine.jsonl"] and [r[1] for r in rows] == [10]


def test_repo_settings_and_workstream_config_feed_the_config_tab():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt-settings" / "scripts"))
    from write_settings import _valid_settings
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as data:
        repo = fake_repo(root, "cfg", [("ws", [item("a", 1, "todo")], {"active": False})])
        set_config(repo, "ws", maxConcurrency=4, taskTime="high", budgetUsd=float("inf"), workItems=[{"id": "a"}])
        registry(data, (repo, "ws"))
        settings = repo / ".orca" / "prompts" / "prompt-settings.json"
        # No file, a corrupt file, a non-object and an invalid object all read as no Prompt Settings.
        for text in (None, "{not json", "[]", json.dumps({"targetBranch": "main"})):
            if text is not None:
                settings.write_text(text)
            lane, = board.build_board(data, now=NOW)["repos"]
            assert lane["settings"] is None, text
        settings.write_text(json.dumps(_valid_settings()))
        lane, = board.build_board(data, now=NOW)["repos"]
        assert lane["settings"]["targetBranch"] == _valid_settings()["targetBranch"]
        # Only the keys a Workstream may override pass through, as stored, less the Infinity budget JSON cannot carry.
        ws, = lane["workstreams"]
        assert ws["config"] == {"harnesses": json.loads((repo / ".orca/prompts/ws/_config.json").read_text())["harnesses"],
                                "maxConcurrency": 4, "taskTime": "high"}
        # A Watched Repo with no checkout has no Prompt Settings to edit.
        assert board._settings(None) is None


def test_committed_bundle_matches_its_source():
    built = (APP / "dist" / "source-hash.txt").read_text().strip()
    assert built == source_hash(), "board/dist is older than board/src: run `pnpm build` in orca-helpers/board"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
