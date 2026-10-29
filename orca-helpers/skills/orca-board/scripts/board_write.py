"""The Board's write endpoints (ADR 0017).

Every write runs the plugin script that already owns the file or action, so
the Board adds no second writer and no second validator. `board.py`'s server
checks the `Host` header and the per-server token, then hands each POST here.
Every response is `{"ok": true, ...}` or `{"ok": false, "fail": ["FAIL: ..."]}`.
"""
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
WRITE_SETTINGS = SKILLS / "orca-prompt-settings" / "scripts" / "write_settings.py"
WRITE_WORKSTREAM_CONFIG = SKILLS / "orca-prompt-settings" / "scripts" / "write_workstream_config.py"
PR_REVIEW = SKILLS / "orca-pr-review" / "scripts" / "pr_review.py"
DETECT_HARNESSES = SKILLS / "orca-prompt" / "scripts" / "detect_harnesses.py"
LIST_MODELS = SKILLS / "orca-prompt" / "scripts" / "list_models.py"
REPO_NAMES = "repo-names.json"
TOKEN_HEADER = "X-Orca-Board-Token"
MAX_BODY = 1 << 20
SCRIPT_SECONDS = 120
PR = re.compile(r"[\w.-]+/[\w.-]+#[1-9]\d*")
WORKSTREAM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_names_lock = threading.Lock()


class Fail(Exception):
    """A request the endpoint refuses: `code` and its `FAIL:` lines."""

    def __init__(self, code, *lines):
        super().__init__(lines)
        self.code, self.lines = code, [line if line.startswith("FAIL:") else f"FAIL: {line}" for line in lines]


def host_ok(host, port):
    """True only for the server's own origin, so a DNS-rebinding page gets nothing."""
    return host in (f"127.0.0.1:{port}", f"localhost:{port}")


def token_ok(sent, token):
    return isinstance(sent, str) and hmac.compare_digest(sent.encode(), token.encode())


def page(html, token):
    """`index.html` with the token in a `<meta name="orca-board-token">`."""
    return html.replace(b"<head>", f'<head><meta name="orca-board-token" content="{token}">'.encode(), 1)


def _run(script, *args, stdin=None, data_dir=None):
    """(ok, stdout) of a plugin script; a crash or timeout is one `FAIL:` line."""
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data_dir)} if data_dir else None
    try:
        done = subprocess.run([sys.executable, str(script), *args], input=stdin, capture_output=True, text=True,
                              timeout=SCRIPT_SECONDS, env=env, stdin=None if stdin is not None else subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise Fail(504, f"{script.name} did not finish in {SCRIPT_SECONDS} seconds")
    if done.returncode == 0:
        return done.stdout
    fails = [line for line in done.stdout.splitlines() if line.startswith("FAIL:")]
    why = (done.stderr or done.stdout).strip().splitlines()
    raise Fail(400, *(fails or [f"{script.name} exited {done.returncode}: {why[-1] if why else 'no output'}"]))


def _str(body, key):
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise Fail(400, f"{key} must be a non-empty string, got {value!r}")
    return value


def _repo(body):
    repo = _str(body, "repo")
    path = Path(repo)
    if "\0" in repo or not path.is_absolute() or not path.is_dir():
        raise Fail(400, f"repo must be the absolute path of a repo folder, got {repo!r}")
    return path


def _pr(body):
    pr = _str(body, "pr")
    if not PR.fullmatch(pr):
        raise Fail(400, f"pr must read owner/repo#n, got {pr!r}")
    return pr


def settings(data_dir, body):
    if not isinstance(body.get("settings"), dict):
        raise Fail(400, f"settings must be a JSON object, got {body.get('settings')!r}")
    path = _repo(body) / ".orca" / "prompts" / "prompt-settings.json"
    _run(WRITE_SETTINGS, str(path), stdin=json.dumps(body["settings"]))
    return {"ok": True}


def workstream_config(data_dir, body):
    repo, workstream = _repo(body), _str(body, "workstream")
    if not WORKSTREAM.fullmatch(workstream) or ".." in workstream:
        raise Fail(400, f"workstream must be a Workstream folder name, got {workstream!r}")
    if not isinstance(body.get("overrides"), dict):
        raise Fail(400, f"overrides must be a JSON object, got {body.get('overrides')!r}")
    clear = body.get("clear", [])
    if not isinstance(clear, list) or not all(isinstance(k, str) for k in clear):
        raise Fail(400, f"clear must be a list of config keys, got {clear!r}")
    _run(WRITE_WORKSTREAM_CONFIG, str(repo / ".orca" / "prompts" / workstream), *clear, stdin=json.dumps(body["overrides"]))
    return {"ok": True}


def repo_name(data_dir, body):
    repo, name = str(_repo(body)), _str(body, "name").strip()
    if len(name) > 100 or any(ord(c) < 32 for c in name):
        raise Fail(400, "name must be at most 100 characters with no control characters")
    path = Path(data_dir) / REPO_NAMES
    with _names_lock:
        try:
            names = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            names = {}
        names = {**(names if isinstance(names, dict) else {}), repo: name}
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".repo-names-", suffix=".json", dir=path.parent)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(names, indent=2) + "\n")
        os.replace(tmp, path)
    return {"ok": True}


def approve(data_dir, body):
    _run(PR_REVIEW, "approve", _pr(body), data_dir=data_dir)
    return {"ok": True}


def feedback(data_dir, body):
    pr, text = _pr(body), _str(body, "text")
    if len(text) > 20000:
        raise Fail(400, "text must be at most 20000 characters")
    _run(PR_REVIEW, "feedback", pr, text, data_dir=data_dir)
    return {"ok": True}


def refresh(data_dir, body):
    """Rerun harness and model discovery; a harness list_models cannot list is left out."""
    harnesses = json.loads(_run(DETECT_HARNESSES))
    models = {}
    for h in harnesses:
        if not h.get("installed"):
            continue
        try:
            models[h["name"]] = json.loads(_run(LIST_MODELS, h["name"]))
        except Fail as e:
            # Exit 2 is list_models.py's usage line: it has no list command for this harness.
            if "exited 2" not in e.lines[0]:
                models[h["name"]] = {"fail": e.lines}
    return {"ok": True, "harnesses": harnesses, "models": models}


ROUTES = {
    "/api/settings": settings,
    "/api/workstream-config": workstream_config,
    "/api/repo-name": repo_name,
    "/api/review/approve": approve,
    "/api/review/feedback": feedback,
    "/api/refresh": refresh,
}


def handle(data_dir, path, body):
    """`(http code, response)` for one POST body already parsed from JSON."""
    try:
        if not isinstance(body, dict):
            raise Fail(400, f"{path} takes a JSON object body")
        return 200, ROUTES[path](data_dir, body)
    except Fail as e:
        return e.code, {"ok": False, "fail": e.lines}
    except Exception as e:
        return 500, {"ok": False, "fail": [f"FAIL: {path} crashed: {type(e).__name__}: {e}"]}
