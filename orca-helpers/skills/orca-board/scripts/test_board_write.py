#!/usr/bin/env python3
"""Self-check for board_write.py and the server's Host and token guards. Run: python3 test_board_write.py"""
import json
import sys
import tempfile
import threading
import urllib.request
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt-settings" / "scripts"))
import board
import board_write
from write_settings import _valid_settings


@contextmanager
def server():
    with tempfile.TemporaryDirectory() as data:
        s = board.make_server(data, idle_seconds=30)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        try:
            yield s, Path(data)
        finally:
            s.shutdown()


def call(s, path, body=None, token=True, host=None, kind="application/json", raw=None, size=None):
    """(code, parsed JSON or raw bytes) for one request; a POST when `body` or `raw` is given."""
    port = s.server_address[1]
    headers = {"Content-Type": kind}
    if token:
        headers[board_write.TOKEN_HEADER] = s.token if token is True else token
    if host:
        headers["Host"] = host
    if size is not None:
        headers["Content-Length"] = str(size)
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            code, out = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, out = e.code, e.read()
    try:
        return code, json.loads(out)
    except ValueError:
        return code, out


def fake(dir, name, script):
    """A stand-in script that logs its argv and stdin, then runs `script`."""
    path = Path(dir) / name
    path.write_text(f"import json, sys\nlog = {str(path) + '.log'!r}\n"
                    "open(log, 'a').write(json.dumps([sys.argv[1:], sys.stdin.read() if not sys.stdin.isatty() else None]) + '\\n')\n"
                    + script)
    return path


def repo_with_workstream(root, status=None):
    ws = Path(root) / ".orca" / "prompts" / "ws"
    ws.mkdir(parents=True)
    (ws / "_config.json").write_text(json.dumps({"workstream": "ws", **_valid_settings()}))
    if status is not None:
        (ws / "_status.json").write_text(json.dumps(status))
    return ws


def test_a_foreign_host_gets_403_on_get_and_post():
    with server() as (s, data), tempfile.TemporaryDirectory() as repo:
        port = s.server_address[1]
        for host in ("evil.example", f"evil.example:{port}", "127.0.0.1", f"127.0.0.1:{port + 1}", f"localhost.evil:{port}"):
            code, out = call(s, "/", host=host)
            assert code == 403 and s.token not in json.dumps(out), (host, code)
            assert call(s, "/api/board", host=host)[0] == 403
            code, out = call(s, "/api/repo-name", {"repo": repo, "name": "x"}, host=host)
            assert code == 403 and out["ok"] is False and out["fail"][0].startswith("FAIL:"), out
        assert not (data / "repo-names.json").exists()
        assert call(s, "/api/board", host=f"localhost:{port}")[0] == 200


def test_the_page_carries_the_token_and_every_post_needs_it():
    with server() as (s, data), tempfile.TemporaryDirectory() as repo:
        code, html = call(s, "/")
        assert code == 200 and f'<meta name="orca-board-token" content="{s.token}">'.encode() in html
        ws = repo_with_workstream(repo)
        before = (ws / "_config.json").read_text()
        writes = {"/api/settings": {"repo": repo, "settings": _valid_settings()},
                  "/api/workstream-config": {"repo": repo, "workstream": "ws", "overrides": {"maxConcurrency": 2}},
                  "/api/repo-name": {"repo": repo, "name": "x"},
                  "/api/review/approve": {"pr": "o/r#1"}, "/api/review/feedback": {"pr": "o/r#1", "text": "t"},
                  "/api/refresh": {}, "/api/jump": {"repoPath": repo, "workstream": "ws"}}
        for path, body in writes.items():
            for token in (False, "wrong", s.token[:-1], s.token + "x", ""):
                code, out = call(s, path, body, token=token)
                assert code == 403 and out["fail"][0].startswith("FAIL:"), (path, token, code, out)
        assert not (data / "repo-names.json").exists() and not (Path(repo) / ".orca" / "prompts" / "prompt-settings.json").exists()
        assert (ws / "_config.json").read_text() == before
        # A second server makes its own token, so an old page's token is refused.
        other = board.make_server(str(data), idle_seconds=30)
        assert other.token != s.token and len(s.token) >= 32
        other.server_close()


def test_settings_save_through_write_settings_or_return_its_fail_lines():
    with server() as (s, data), tempfile.TemporaryDirectory() as repo:
        assert call(s, "/api/settings", {"repo": repo, "settings": _valid_settings()}) == (200, {"ok": True})
        saved = Path(repo) / ".orca" / "prompts" / "prompt-settings.json"
        assert json.loads(saved.read_text())["maxConcurrency"] == 6
        code, out = call(s, "/api/settings", {"repo": repo, "settings": {**_valid_settings(), "maxConcurrency": 0, "workItems": []}})
        assert code == 400 and len(out["fail"]) == 2 and all(f.startswith("FAIL:") for f in out["fail"]), out
        assert json.loads(saved.read_text())["maxConcurrency"] == 6


def test_workstream_overrides_save_and_a_running_workstream_refuses():
    with server() as (s, data), tempfile.TemporaryDirectory() as repo:
        ws = repo_with_workstream(repo, {"active": False})
        body = {"repo": repo, "workstream": "ws", "overrides": {"maxConcurrency": 3, "taskTime": "xhigh"}}
        assert call(s, "/api/workstream-config", body) == (200, {"ok": True})
        assert json.loads((ws / "_config.json").read_text())["taskTime"] == "xhigh"
        code, out = call(s, "/api/workstream-config", {**body, "overrides": {"workItems": []}})
        assert code == 400 and "cannot override" in out["fail"][0], out
        (ws / "_status.json").write_text(json.dumps({"active": True}))
        code, out = call(s, "/api/workstream-config", {**body, "overrides": {"maxConcurrency": 9}})
        assert code == 400 and "is running" in out["fail"][0], out
        assert json.loads((ws / "_config.json").read_text())["maxConcurrency"] == 3
        for name in ("../ws", "ws/../../x", ".hidden", "", "a/b"):
            code, out = call(s, "/api/workstream-config", {**body, "workstream": name})
            assert code == 400 and out["fail"][0].startswith("FAIL: workstream must"), (name, out)
        assert call(s, "/api/workstream-config", {**body, "workstream": "missing"})[1]["fail"][0].startswith("FAIL: no Workstream config")


def test_the_modal_body_writes_only_switched_on_keys_and_clears_the_rest():
    # The modal's body: Override on for maxConcurrency only, every other key switched off.
    keys = ("harnesses", "mainOrchestratorHarness", "maxConcurrency", "targetBranch", "review", "planGate",
            "evidenceCommand", "budgetUsd", "taskTime")
    with server() as (s, data), tempfile.TemporaryDirectory() as repo:
        ws = repo_with_workstream(repo, {"active": False})
        config = json.loads((ws / "_config.json").read_text())
        (ws / "_config.json").write_text(json.dumps({**config, "taskTime": "medium", "budgetUsd": 5}))
        body = {"repo": repo, "workstream": "ws", "overrides": {"maxConcurrency": 4}, "clear": [k for k in keys if k != "maxConcurrency"]}
        assert call(s, "/api/workstream-config", body) == (200, {"ok": True})
        saved = json.loads((ws / "_config.json").read_text())
        assert saved["maxConcurrency"] == 4 and not set(saved) & (set(keys) - {"maxConcurrency"}), saved
        assert saved["workstream"] == "ws", saved
        for clear in ("taskTime", [1], ["workItems"]):
            code, out = call(s, "/api/workstream-config", {**body, "clear": clear})
            assert code == 400 and out["fail"][0].startswith("FAIL:"), (clear, out)


def test_repo_names_save_and_bad_names_or_repos_fail():
    with server() as (s, data), tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as other:
        (data / "repo-names.json").write_text(json.dumps({other: "kept"}))
        assert call(s, "/api/repo-name", {"repo": repo, "name": "  Kai Apps "}) == (200, {"ok": True})
        assert json.loads((data / "repo-names.json").read_text()) == {other: "kept", repo: "Kai Apps"}
        for body in ({"repo": repo, "name": ""}, {"repo": repo, "name": "a\nb"}, {"repo": repo, "name": "x" * 101},
                     {"repo": "relative/path", "name": "x"}, {"repo": repo + "/missing", "name": "x"}, {"repo": 3, "name": "x"},
                     {"repo": repo + "\0", "name": "x"}, {"repo": repo}):
            code, out = call(s, "/api/repo-name", body)
            assert code == 400 and out["fail"][0].startswith("FAIL:"), (body, out)
        assert json.loads((data / "repo-names.json").read_text()) == {other: "kept", repo: "Kai Apps"}
        # A corrupt file is replaced, not a crash.
        (data / "repo-names.json").write_text("[not json")
        assert call(s, "/api/repo-name", {"repo": repo, "name": "y"}) == (200, {"ok": True})


def test_approve_and_feedback_run_pr_review_and_return_its_fail_lines():
    with server() as (s, data), tempfile.TemporaryDirectory() as bin:
        script = fake(bin, "pr_review.py", "if sys.argv[2] == 'o/r#9':\n    print('FAIL: no held Review Draft for o/r#9')\n    sys.exit(1)\n")
        real = board_write.PR_REVIEW
        board_write.PR_REVIEW = script
        try:
            assert call(s, "/api/review/approve", {"pr": "o/r#1"}) == (200, {"ok": True})
            assert call(s, "/api/review/feedback", {"pr": "o/r#1", "text": "--tone softer; $(rm -rf /)"}) == (200, {"ok": True})
            assert call(s, "/api/review/approve", {"pr": "o/r#9"}) == (400, {"ok": False, "fail": ["FAIL: no held Review Draft for o/r#9"]})
            assert call(s, "/api/review/feedback", {"pr": "o/r#9", "text": "x"})[0] == 400
            for body in ({"pr": "o/r"}, {"pr": "o/r#0"}, {"pr": "-x/r#1"[1:] + " #1"}, {"pr": ["o/r#1"]}, {"pr": "o/r#1;ls"}):
                assert call(s, "/api/review/approve", body)[0] == 400, body
            for text in ("", "   ", None, 7, "x" * 20001):
                assert call(s, "/api/review/feedback", {"pr": "o/r#1", "text": text})[0] == 400, text
        finally:
            board_write.PR_REVIEW = real
        log = [json.loads(line)[0] for line in Path(f"{script}.log").read_text().splitlines()]
        assert log == [["approve", "o/r#1"], ["feedback", "o/r#1", "--tone softer; $(rm -rf /)"], ["approve", "o/r#9"], ["feedback", "o/r#9", "x"]], log


def test_refresh_reruns_discovery_and_lists_models_per_installed_harness():
    with server() as (s, data), tempfile.TemporaryDirectory() as bin:
        detect = fake(bin, "detect.py", "print(json.dumps([{'name': 'pi', 'installed': True}, {'name': 'claude', 'installed': True},"
                                        " {'name': 'agy', 'installed': True}, {'name': 'codex', 'installed': False}]))\n")
        models = fake(bin, "models.py", "h = sys.argv[1]\n"
                                        "if h == 'claude':\n    sys.exit(2)\n"
                                        "if h == 'agy':\n    sys.stderr.write('error: agy output did not parse\\n'); sys.exit(1)\n"
                                        "print(json.dumps({'harness': h, 'providers': {}}))\n")
        real = board_write.DETECT_HARNESSES, board_write.LIST_MODELS
        board_write.DETECT_HARNESSES, board_write.LIST_MODELS = detect, models
        try:
            code, out = call(s, "/api/refresh", {})
            assert code == 200 and out["ok"] and len(out["harnesses"]) == 4, out
            assert out["models"] == {"pi": {"harness": "pi", "providers": {}},
                                     "agy": {"fail": ["FAIL: models.py exited 1: error: agy output did not parse"]}}, out
            assert not Path(f"{detect}.log").read_text().count("\n") > 1
            fake(bin, "detect.py", "sys.exit(3)\n")
            code, out = call(s, "/api/refresh", {})
            assert code == 400 and out["fail"] == ["FAIL: detect.py exited 3: no output"], out
        finally:
            board_write.DETECT_HARNESSES, board_write.LIST_MODELS = real


def test_hostile_bodies_get_a_fail_line_never_a_crash():
    with server() as (s, data), tempfile.TemporaryDirectory() as repo:
        for path in board_write.ROUTES:
            # /api/refresh reads no field, so only the non-object bodies apply to it.
            objects = () if path == "/api/refresh" else (b"{\"repo\": NaN}", "{\"repo\": \"\\ud800\"}".encode())
            for raw in (b"not json", b"[]", b'"x"', b"null", b"3", b"[" * 100000, b"\xff\xfe", *objects):
                code, out = call(s, path, raw=raw)
                assert code == 400 and out["ok"] is False and out["fail"][0].startswith("FAIL:"), (path, raw[:20], code, out)
            assert call(s, path, {"repo": repo}, kind="text/plain")[0] == 400
            assert call(s, path, raw=b"{}", size=board_write.MAX_BODY + 1)[0] == 400
            assert call(s, path, raw=b"{}", size=-1)[0] == 400
        # Wrong types inside an object are refused per field.
        for body in ({"repo": {"a": 1}, "settings": {}}, {"repo": repo, "settings": []}, {"repo": repo, "settings": "x"}):
            code, out = call(s, "/api/settings", body)
            assert code == 400 and out["fail"][0].startswith("FAIL:"), (body, out)
        assert call(s, "/api/workstream-config", {"repo": repo, "workstream": "ws", "overrides": [1]})[0] == 400
        assert call(s, "/api/nope", {})[0] == 404
        # A crash inside an endpoint is caught at top level and the server keeps answering.
        real = board_write.ROUTES["/api/refresh"]
        board_write.ROUTES["/api/refresh"] = lambda data_dir, body: 1 / 0
        try:
            code, out = call(s, "/api/refresh", {})
            assert code == 500 and out["fail"][0].startswith("FAIL: /api/refresh crashed: ZeroDivisionError"), out
        finally:
            board_write.ROUTES["/api/refresh"] = real
        assert call(s, "/api/board")[0] == 200


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
