"""The Board server: one local page for every Workstream an orca-execute run started (ADR 0013).

Usage:
    python3 board.py           # start the server or reuse the running one, open the system browser
    python3 board.py --orca    # the same, but open the Board in an Orca browser tab
    python3 board.py stop      # end the running server
    python3 board.py serve     # run the server in the foreground (what the commands above start)

The server binds to 127.0.0.1 only. It writes `{pid, port}` to `board-server.json`
in the Plugin Data Dir, so a second call finds it and reuses the same port. It
exits 30 minutes after the last `GET /api/board`.

`GET /api/board` reads the Run Registry (`runs.json`, written by
`set_status.py --start`) and each run's `_config.json` and `_status.json`:

    {"generatedAt": "...", "attention": [],
     "repos": [{"name", "path", "slug", "executeActive", "prReviewActive", "totals",
                "workstreams": [{"name", "state", "lastChange", "totals",
                                 "waves": [{"n", "title", "state", "totals", "items": [...]}]}]}],
     "reviews": {"repos": [...]}}

`repos` lists every repo in the Run Registry whose folder exists, plus every
Watched Repo (`watched: true` in `review-settings.json`) that no such repo's
GitHub `origin` names, with `path` null. A Run Registry path is a main checkout or
one of its Orca worktrees, so main_checkout() resolves it with `git rev-parse
--git-common-dir` and every worktree of one repo groups under its main checkout.
`name` is the Repo Name: that checkout's folder, unless `repo-names.json` in the
Plugin Data Dir maps its path to another name (`{"<path>": "<name>"}`). `slug` is
`owner/repo` from the `origin` remote, or null. `executeActive` is true when any of
its Workstreams is `active`. `prReviewActive` is true when `pr-review/loop.json`
has `active: true` and `slug` is a Watched Repo.

Each Workstream carries `path`, the run's own checkout, which holds its
`_config.json` and `_status.json`. It also carries `mainOrchestrator`,
`{harness, model, effort}` from its `_config.json`; `taskTime`, `medium` where the
key is missing or not a Task Time; `started`, whether its `_status.json` has a
`startedAt`; and `active`, whether that file has `active: true`.

Each Workstream also carries `budgetUsd` and `maxConcurrency` from its
`_config.json` (null where unset or not a positive number), `running`, the count
of its items in `in_progress` or `reviewing`, `config`, the `_config.json` keys a
Workstream may override (`write_workstream_config.py` KEYS) as stored, less any
value holding Infinity or NaN, and `series`.
Each repo also carries `settings`, its Prompt Settings as stored (less retired keys),
or null where it has no checkout or no valid `prompt-settings.json`. Each Wave carries
`startedAt`, the earliest session log entry of its items, or null before any.

Each item carries id, title, column, harness, mood, model, effort, pr, enteredAt,
reason, progress, review and usage. `review` is the item's `_status.json` review
record, `{round, verdict, reviewer}`, or null before its first review round. `mood` is the Avatar Mood the Wave Band picks
(hooks/waves.ts avatarMood). `pr` is `{number, url, state}`; url and state come
from `gh pr view` in a background thread, so they read null until it answers. A
value nothing records yet is null, never 0. A run whose repo or `_status.json` is
gone is left out. A run whose `_status.json` has no items keeps its lane with no
Waves. A finished or stopped Workstream stays, greyed by the page, for the Recent
Window after its last change: the `recentWindowHours` key of `settings.json` in
the Plugin Data Dir, 120 by default.

`usage` is `{cost, input, output, cacheRead, cacheWrite}`, read from the worker's
own session logs: Claude Code JSONL under `${CLAUDE_CONFIG_DIR:-~/.claude}/projects`
for `claude`, rollout files under `${CODEX_HOME:-~/.codex}/sessions` for `codex`.
A worker's logs are the ones whose working directory ends in
`<main checkout folder>/<Work Item id>`, the path Orca gives a worker's worktree. Cost is in
USD from `prices.json` beside this script. Another Agent Harness, a model that
table lacks, or no log yet gives null, which the page draws as a dash. Each Wave,
Workstream and repo `totals` sums its items' usage, skipping nulls, with `missing`
counting the started items that have none; it is null when no item has usage.

`series` is the Workstream's usage over time, from the same session log entries,
or null when none has a timestamp:

    {"bucketSeconds": 600, "start": "...", "buckets": 34,
     "models": [{"model", "cost": [...], "tokens": [...], "seconds": [...]}]}

Bucket `k` starts at `start + k * bucketSeconds`; the bucket size is the smallest
of BUCKETS, then of 2, 3, 4 ... days, that keeps the run at MAX_BUCKETS buckets or fewer. Each model's three lists
hold one value per bucket: cost in USD (every value null for a model `prices.json`
lacks), tokens of every kind, and agent seconds, the time since the session's
previous response, capped at ACTIVE_GAP so a pause counts as idle. Models are
ordered by total cost, then tokens, highest first.

`GET /avatars/<file>` serves the Harness Avatar frames the bands draw, from
hooks/assets/avatars, with `manifest.json` giving each strip's frame count.

`reviews` is the Reviews Tab, read from the orca-pr-review ledgers
(`pr-review/<owner>__<repo>.json` in the Plugin Data Dir):

    {"repos": [{"name": "owner/repo", "prs": [{"number", "url", "title", "author", "assignees",
               "head", "base", "checks": {"passed", "total"}, "status", "round", "harness", "column",
               "claimedAt", "finishedAt", "held", "draft": {"event", "body"} | null, "mine"}]}]}

`column` comes from the ledger entry: `approved` for an APPROVED verdict,
`changes_requested` for CHANGES_REQUESTED or COMMENTED, `draft_ready` with a Review
Draft and no verdict, `reviewing` with a review worker, else `new`. The ledger gives
number, round and harness. `gh pr view` gives assignees, branches and status (OPEN,
DRAFT, MERGED or CLOSED), and `gh pr checks` gives `checks`, skipped checks left out.
Both run in a background thread, so their fields read null until gh answers, and
title, url and author fall back to the ledger. A ledger entry with `finishedAt`
is a merged or closed PR: its card comes from the ledger alone, with no gh call,
`status` from its `state`, and `column` `approved` for APPROVED, `changes_requested`
for CHANGES_REQUESTED, else `reviewing`. It shows for `recentWindowHours` after
`finishedAt`. Any other merged or closed PR leaves the tab, and gh is not asked
about it again. `held` is true when the PR's current round
holds a Review Draft nothing has posted yet: its `round-<r>.json`, whose `event`
and `body` fill `draft`. Otherwise `draft` is null. Loop cards carry `mine: false`.

A Watched Repo also lists the PRs the user reviewed by hand (`gh search prs
--reviewed-by @me`), updated inside `recentWindowHours` and absent from its ledger:
`mine: true`, `column: "approved"`, `claimedAt` from the PR's `createdAt`,
`finishedAt` from its `closedAt`, gh fields null. A background thread refreshes them
every 5 minutes.

`attention` lists every open Attention Item, questions and Decision Gates first:

    [{"kind": "question | gate | review_draft | failed", "repo", "repoPath", "workstream",
      "question", "options", "askedAt", "item": {"id", "title"} | null, "reason", "canJump",
      "verdict": "APPROVE | REQUEST_CHANGES | COMMENT | null", "url": "string | null"}]

A question is the `attention` entry the hooks module keeps in `_status.json`
(ADR 0014); one asked between two Waves, after a Wave finished and before the
next one started, is a Decision Gate. Each failed Work Item is one more. Each
ledger PR in Draft Ready is a Review Draft: `item.id` is `owner/repo#n`, `verdict`
is the draft's event, and its repoPath and workstream name the orca-pr-review loop.
Posting sets the PR's verdict, so it leaves Draft Ready and the section.

`POST /api/jump` with `{"repoPath", "workstream"}` runs `orca terminal switch` for
the terminal `set_status.py --start` recorded, the Owning Session's. For the
orca-pr-review loop it is the terminal `pr_review.py start` recorded in
`pr-review/loop.json`, the loop's session. It answers
`{"ok": true}`, or `{"ok": false, "error"}` with 404 for an unknown run, 409 with no
terminal recorded and 502 when Orca is unreachable. It takes only a JSON body, so
another site's page cannot post to it without a CORS preflight the server never answers.

Every request whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>` gets 403,
so a DNS-rebinding page cannot read the page. The server makes a token at start and
serves it only in the page's `<meta name="orca-board-token">`. Every POST without it in
`X-Orca-Board-Token` gets 403 and changes nothing. `board_write.py` holds the write
endpoints (ADR 0017).
"""
import itertools
import json
import math
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import board_write

# The Config tab and modal edit what the owning scripts read and accept, so the Board reuses their reader and key list.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt-settings" / "scripts"))
from write_settings import _drop_retired, settings_problems
from write_workstream_config import KEYS as OVERRIDE_KEYS
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt" / "scripts"))
from orca_cli import orca_cli

HOST = "127.0.0.1"
IDLE_SECONDS = 30 * 60
STATE_FILE = "board-server.json"
REGISTRY_FILE = "runs.json"
SETTINGS_FILE = "settings.json"
REPO_NAMES_FILE = "repo-names.json"
REVIEW_SETTINGS_FILE = "review-settings.json"
TASK_TIMES = ("low", "medium", "high", "xhigh", "ultra")
RECENT_WINDOW_HOURS = 120
DIST = Path(__file__).resolve().parents[3] / "board" / "dist"
AVATARS = Path(__file__).resolve().parents[3] / "hooks" / "assets" / "avatars"
MOODS = ("default", "red", "blue", "green", "yellow", "purple", "teal")
PR_TTL = 60
BUCKETS = (60, 300, 600, 1800, 3600, 3 * 3600, 6 * 3600, 86400)
MAX_BUCKETS = 48
ACTIVE_GAP = 300
REVIEW_VIEW = "url,title,author,assignees,headRefName,baseRefName,state,isDraft"
TYPES = {".json": "application/json", ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}


def plugin_data_dir():
    """The Plugin Data Dir: ${CLAUDE_PLUGIN_DATA}, or ~/.claude/orca-helpers/ where it is unset."""
    return Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "orca-helpers")


def _read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def recent_window_hours(data_dir):
    """`recentWindowHours` from the user-level settings file, or 120 where it is unset or not a positive number."""
    settings = _read(Path(data_dir) / SETTINGS_FILE)
    hours = settings.get("recentWindowHours") if isinstance(settings, dict) else None
    ok = isinstance(hours, (int, float)) and not isinstance(hours, bool) and hours > 0
    return hours if ok else RECENT_WINDOW_HOURS


def _last_change(status, path):
    """The status file's `updatedAt`, or its mtime where that is missing or unreadable."""
    t = _when(status.get("updatedAt"))
    if t:
        return t
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return datetime.min.replace(tzinfo=timezone.utc)  # gone since the read: outside any window


def _fnv(text):
    h = 0x811C9DC5
    for c in text:
        h = ((h ^ ord(c)) * 0x01000193) & 0xFFFFFFFF
    return h


def _mood(workstream, wave, ids, id):
    """The Avatar Mood hooks/waves.ts avatarMood picks: a per-Wave deck dealt in item order."""
    deck = sorted(MOODS, key=lambda m: _fnv(f"{workstream}\0{wave}\0{m}"))
    return deck[max(0, ids.index(id) if id in ids else 0) % len(deck)]


# (repo path, PR number) -> (fetched at, {"url", "state"}); a merged or closed PR is final.
_prs = {}
_fetching = set()


def _fetch_pr(repo, number):
    try:
        r = subprocess.run(["gh", "pr", "view", str(number), "--json", "url,state"], cwd=repo, capture_output=True, text=True, timeout=15)
        found = json.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        found = {}
    _prs[(repo, number)] = (time.monotonic(), {"url": found.get("url"), "state": found.get("state")})
    _fetching.discard((repo, number))


def _pr(repo, number):
    """`{number, url, state}` from the cache; a missing or stale entry refreshes in the background."""
    key = (repo, number)
    at, found = _prs.get(key, (None, {"url": None, "state": None}))
    final = found["state"] in ("MERGED", "CLOSED")
    if not final and (at is None or time.monotonic() - at > PR_TTL) and key not in _fetching:
        _fetching.add(key)
        threading.Thread(target=_fetch_pr, args=key, daemon=True).start()
    return {"number": number, **found}


def _dash(text):
    """A path as Claude Code names its project folder: every character not a letter or digit becomes `-`."""
    return re.sub(r"[^A-Za-z0-9]", "-", text)


# Repo path -> (main checkout, owner/repo or None); a checkout never moves while the server runs.
_checkouts = {}


def _git(path, *args):
    try:
        r = subprocess.run(["git", "-C", str(path), *args], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _checkout(path):
    """`(main checkout, owner/repo)` for any checkout of a repo: its main one or an Orca worktree."""
    path = str(path)
    if path not in _checkouts:
        common = _git(path, "rev-parse", "--git-common-dir")
        # The main checkout gets `.git` back, a worktree the main checkout's absolute `.git`.
        git = (Path(path) / common).resolve() if common else None  # resolved, so /var and /private/var agree on macOS
        main = str(git.parent if git and git.name == ".git" else git or path)
        m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", _git(main, "remote", "get-url", "origin") or "")
        _checkouts[path] = (main, m.group(1) if m else None)
    return _checkouts[path]


def main_checkout(path):
    """The one key for a repo path from any source: the Run Registry, `repo-names.json` or a request."""
    return _checkout(path)[0]


def repo_names(data_dir):
    """`repo-names.json` as {main checkout: Repo Name}, keeping only non-empty string names."""
    found = _read(Path(data_dir) / REPO_NAMES_FILE)
    items = found.items() if isinstance(found, dict) else ()
    return {main_checkout(p): n.strip() for p, n in items if isinstance(n, str) and n.strip()}


def watched_repos(data_dir):
    """The Watched Repos, `owner/repo`, from the Review Settings orca-pr-review keeps."""
    found = _read(Path(data_dir) / REVIEW_SETTINGS_FILE)
    return sorted(r for r, e in found.items() if isinstance(e, dict) and e.get("watched") is True) if isinstance(found, dict) else []


# (session log path, parser) -> ((mtime, size), parsed); a log only grows, so a changed stat means re-read.
_logs = {}


def _parsed(path, parse):
    try:
        st = path.stat()
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = _logs.get((path, parse))
    if hit and hit[0] == key:
        return hit[1]
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            found = parse(f)
    except OSError:
        return None
    _logs[(path, parse)] = (key, found)
    return found


def _when(text):
    """An ISO 8601 log timestamp as an aware datetime, or None."""
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))  # Python 3.9 rejects a trailing Z
    except (AttributeError, TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _gaps(found):
    """`found` with each row's agent seconds appended: the gap since the previous timed row, capped at ACTIVE_GAP."""
    out, last = {}, None
    for key, r in sorted(found.items(), key=lambda kv: (kv[1][6] is None, kv[1][6] or datetime.min.replace(tzinfo=timezone.utc))):
        out[key] = (*r, min((r[6] - last).total_seconds(), ACTIVE_GAP) if r[6] and last else 0)
        last = r[6] or last
    return out


def _lines(f):
    for line in f:
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _claude_file(f):
    """One (model, input, output, cacheRead, cacheWrite5m, cacheWrite1h, at, seconds) per billed response in one Claude Code JSONL."""
    found = {}
    for e in _lines(f):
        m = e.get("message") if isinstance(e, dict) else None
        u = m.get("usage") if isinstance(m, dict) else None
        if not isinstance(u, dict) or m.get("model") == "<synthetic>":
            continue
        write = u.get("cache_creation_input_tokens") or 0
        hour = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
        # One API response is logged once per content block, each with the same usage; the first block's time counts.
        key = (m.get("id"), e.get("requestId"))
        at = found[key][6] if key in found else _when(e.get("timestamp"))
        found[key] = (m.get("model"), u.get("input_tokens") or 0, u.get("output_tokens") or 0,
                      u.get("cache_read_input_tokens") or 0, write - hour, hour, at)
    return _gaps(found)


def _claude(worktree):
    """Every billed response the claude worker in `worktree` logged, its subagents' included."""
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    tail = "-" + _dash(worktree)
    try:
        dirs = [d for d in root.iterdir() if d.name.endswith(tail)]
    except OSError:
        return []
    found = {}
    for d in dirs:
        for p in d.rglob("*.jsonl"):
            found.update(_parsed(p, _claude_file) or {})
    return list(found.values())


def _codex_file(f):
    """(cwd, model, total token usage, first time, last time) for one codex rollout file."""
    cwd = model = total = first = last = None
    for e in _lines(f):
        p = e.get("payload") if isinstance(e, dict) else None
        if not isinstance(p, dict):
            continue
        at = _when(e.get("timestamp"))
        first, last = first or at, at or last
        if e.get("type") == "session_meta":
            cwd = p.get("cwd")
        elif e.get("type") == "turn_context":
            model = p.get("model") or model
        elif p.get("type") == "token_count" and isinstance(p.get("info"), dict):
            total = p["info"].get("total_token_usage") or total
    return cwd, model, total, first, last


def _codex_cwd(f):
    """The cwd a codex rollout's first line, its session_meta, records, or None."""
    e = next(_lines([f.readline()]), None)
    p = e.get("payload") if isinstance(e, dict) and e.get("type") == "session_meta" else None
    return p.get("cwd") if isinstance(p, dict) else None


def _codex(worktree):
    """One row per codex session whose cwd is `worktree`, from its last cumulative token count."""
    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
    rows = []
    for p in root.rglob("rollout-*.jsonl"):
        # Every worker's rollouts share this folder, so only a matching first line earns a full parse.
        cwd = _parsed(p, _codex_cwd)
        if not isinstance(cwd, str) or not cwd.endswith(worktree) or cwd[: -len(worktree)][-1:] not in ("/", ""):
            continue
        cwd, model, t, first, last = _parsed(p, _codex_file) or (None,) * 5
        if not t:
            continue
        cached = t.get("cached_input_tokens") or 0
        # shortcut: a session that switches model mid-way is priced at its last model; split per turn_context if that matters.
        # shortcut: a session lands in one series bucket at its last event, its whole span as agent time; split per token_count if the chart needs it.
        # OpenAI counts cached tokens inside input_tokens, so the uncached input is the difference.
        rows.append((model, max(0, (t.get("input_tokens") or 0) - cached), t.get("output_tokens") or 0, cached,
                     t.get("cache_write_input_tokens") or 0, 0, last, (last - first).total_seconds() if first and last else 0))
    return rows


PARSERS = {"claude": _claude, "codex": _codex}
PRICES = (_read(Path(__file__).with_name("prices.json")) or {}).get("models") or {}


def log_rows(harness, repo_name, item_id):
    """Every billed response the worker logged, as (model, input, output, cacheRead, cacheWrite5m, cacheWrite1h, at, seconds).

    An Orca worker runs in `<...>/<repo name>/<Work Item id>`, so that path suffix finds its logs.
    A harness with no parser gives none.
    """
    parse = PARSERS.get(harness)
    return parse(f"{repo_name}/{item_id}") if parse else []


def _cost(model, inp, outp, read, write, hour, *_):
    p = PRICES[model]
    return (inp * p["input"] + outp * p["output"] + read * p["cacheRead"] + write * p["cacheWrite"] + hour * p["cacheWrite1h"]) / 1e6


def usage(rows):
    """`{cost, input, output, cacheRead, cacheWrite}` summed over `rows`, or None.

    None, never zeros, for no rows or a model PRICES does not list.
    """
    if not rows or any(r[0] not in PRICES for r in rows):
        return None
    out = {"cost": 0.0, "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    for row in rows:
        model, inp, outp, read, write, hour = row[:6]
        out["cost"] += _cost(*row)
        out["input"] += inp
        out["output"] += outp
        out["cacheRead"] += read
        out["cacheWrite"] += write + hour
    out["cost"] = round(out["cost"], 6)
    return out


def series(rows):
    """The `series` usage over time for `rows`, or None when no row has a timestamp."""
    timed = [r for r in rows if r[6]]
    if not timed:
        return None
    first, last = min(r[6] for r in timed), max(r[6] for r in timed)
    # Each size is tested against the start floored to it, since flooring can add a bucket.
    # Past BUCKETS come whole days without end, so some size always passes: one over the span gives at most 2 buckets.
    sizes = itertools.chain(BUCKETS, (d * 86400 for d in itertools.count(2)))
    size = next(b for b in sizes if (last.timestamp() - first.timestamp() // b * b) // b < MAX_BUCKETS)
    start = datetime.fromtimestamp(first.timestamp() // size * size, timezone.utc)
    n = int((last - start).total_seconds() // size) + 1
    found = {}
    for row in timed:
        model = row[0]
        s = found.setdefault(model, {"model": model, "cost": [0.0 if model in PRICES else None] * n, "tokens": [0] * n, "seconds": [0.0] * n})
        k = int((row[6] - start).total_seconds() // size)
        s["tokens"][k] += sum(row[1:6])
        s["seconds"][k] += row[7]
        if model in PRICES:
            s["cost"][k] += _cost(*row)
    for s in found.values():
        s["cost"] = [None if c is None else round(c, 6) for c in s["cost"]]
        s["seconds"] = [round(x) for x in s["seconds"]]
    models = sorted(found.values(), key=lambda s: (-sum(c or 0 for c in s["cost"]), -sum(s["tokens"]), s["model"] or ""))
    return {"bucketSeconds": size, "start": start.isoformat(timespec="seconds"), "buckets": n, "models": models}


def _positive(value):
    # Infinity and NaN would make /api/board invalid JSON.
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 else None


def totals(items):
    """Summed usage of `items`, skipping nulls; `missing` counts started items with no usage. None when none has any."""
    known = [i["usage"] for i in items if i["usage"]]
    if not known:
        return None
    out = {k: sum(u[k] for u in known) for k in ("cost", "input", "output", "cacheRead", "cacheWrite")}
    out["cost"] = round(out["cost"], 6)
    # A Work Item still to do has run nothing, so its dash is not a gap in the sum.
    out["missing"] = sum(1 for i in items if not i["usage"] and i["column"] != "todo")
    return out


def _item(item, slots, repo, rows, mood):
    model = slots.get(item.get("harness")) or {}
    pr = item.get("pr")
    return {
        "id": item["id"],
        "title": item["title"],
        "column": item["state"],
        "harness": item.get("harness"),
        "mood": mood,
        "model": model.get("model"),
        "effort": model.get("effort"),
        "pr": _pr(repo, pr) if pr is not None else None,
        "enteredAt": item.get("enteredAt"),
        "reason": item.get("reason"),
        "progress": item.get("progress"),
        "review": item.get("review"),
        "usage": usage(rows),
    }


def _status(run):
    d = Path(run["repoPath"]) / ".orca" / "prompts" / run["workstream"]
    status = _read(d / "_status.json")
    if not isinstance(status, dict):
        return None
    if not isinstance(status.get("items"), list):
        status["items"] = []
    return status


def _attention(run, status, waves, name):
    base = {"repo": name, "repoPath": run["repoPath"], "workstream": run["workstream"], "canJump": bool(status.get("terminal"))}
    found = []
    asked = status.get("attention")
    if asked:
        # Between Waves: one finished, the next not started, so the run waits on this answer.
        current = next((w for w in waves if w["state"] == "active"), None)
        between = current is not None and current["n"] != waves[0]["n"] and all(i["column"] == "todo" for i in current["items"])
        kind = "gate" if asked.get("kind") == "gate" or between else "question"
        found.append({**base, "kind": kind, "question": asked.get("question"), "options": asked.get("options") or [],
                      "askedAt": asked.get("askedAt"), "item": None, "reason": None, "verdict": None, "url": None})
    for i in status["items"]:
        if i["state"] == "failed":
            found.append({**base, "kind": "failed", "question": None, "options": [], "askedAt": None,
                          "item": {"id": i["id"], "title": i["title"]}, "reason": i.get("reason"), "verdict": None, "url": None})
    return found


def review_attention(data_dir):
    """One Review Draft Attention Item per ledger PR in Draft Ready, jumping to the loop's session."""
    loop = _read(Path(data_dir) / "pr-review" / "loop.json") or {}
    found = []
    for repo, entries in _ledger_entries(data_dir):
        for e in entries:
            if e.get("finishedAt") or _review_column(e) != "draft_ready":
                continue
            draft = _read(e["draft"])
            found.append({"kind": "review_draft", "repo": repo, "repoPath": loop.get("repoPath"), "workstream": "orca-pr-review",
                          "question": None, "options": [], "askedAt": None, "canJump": bool(loop.get("terminal")),
                          "item": {"id": f"{repo}#{e['number']}", "title": e.get("title")},
                          "reason": f"Approve it in the session with /orca-pr-review approve {repo}#{e['number']}.",
                          "verdict": draft.get("event") if isinstance(draft, dict) else None, "url": e.get("url")})
    return found


def _workstream(run, status, now, window_hours, folder):
    d = Path(run["repoPath"]) / ".orca" / "prompts" / run["workstream"]
    state = "active" if status.get("active") else "finished" if status.get("finishedAt") else "stopped"
    if state != "active" and (now - _last_change(status, d / "_status.json")).total_seconds() > window_hours * 3600:
        return None
    config = _read(d / "_config.json") or {}
    # Work Items run on the orchestrationWorker Model Slot of their Agent Harness.
    slots = {h.get("name"): (h.get("models") or {}).get("orchestrationWorker") for h in config.get("harnesses") or []}
    # Orca names a worker's worktree after the main checkout's folder, whatever the run's own checkout is called.
    logs = {i["id"]: log_rows(i.get("harness"), folder, i["id"]) for i in status["items"]}
    waves, active = [], False
    for n in sorted({i["wave"] for i in status["items"]}):
        items = [i for i in status["items"] if i["wave"] == n]
        # Waves run in order, so only the first unfinished one is in flight.
        wave_state = "complete" if all(i["state"] == "complete" for i in items) else "upcoming" if active else "active"
        active = active or wave_state == "active"
        ids = [i["id"] for i in items]
        made = [_item(i, slots, run["repoPath"], logs[i["id"]], _mood(run["workstream"], n, ids, i["id"])) for i in items]
        # A row's agent seconds end at its timestamp, so this is a codex session's first event and a Claude reply's own time.
        began = [r[6] - timedelta(seconds=r[7]) for i in ids for r in logs[i] if r[6]]
        waves.append({"n": n, "title": f"Wave {n}", "state": wave_state, "startedAt": min(began).isoformat(timespec="seconds") if began else None,
                      "totals": totals(made), "items": made})
    every = [i for w in waves for i in w["items"]]
    main = config.get("mainOrchestratorHarness")
    slot = next(((h.get("models") or {}).get("mainOrchestrator") or {} for h in config.get("harnesses") or [] if h.get("name") == main), {})
    return {"name": run["workstream"], "path": run["repoPath"], "state": state,
            "mainOrchestrator": {"harness": main, "model": slot.get("model"), "effort": slot.get("effort")},
            "taskTime": config.get("taskTime") if config.get("taskTime") in TASK_TIMES else "medium",
            "started": bool(status.get("startedAt")), "active": status.get("active") is True, "lastChange": status.get("updatedAt"), "totals": totals(every),
            "budgetUsd": _positive(config.get("budgetUsd")), "maxConcurrency": _positive(config.get("maxConcurrency")),
            "running": sum(i["column"] in ("in_progress", "reviewing") for i in every),
            "config": {k: config[k] for k in OVERRIDE_KEYS if k in config and _json_safe(config[k])},
            "series": series([r for rows in logs.values() for r in rows]), "waves": waves}


# (owner/repo, PR number) -> (fetched at, (gh pr view JSON or None, gh pr checks JSON or None)).
_reviews = {}
_review_fetching = set()


def _gh_json(*args):
    try:
        r = subprocess.run(["gh", *args], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout)  # `gh pr checks` exits 8 while checks are pending, with valid JSON
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def _fetch_review(repo, number):
    view = _gh_json("pr", "view", str(number), "-R", repo, "--json", REVIEW_VIEW)
    checks = _gh_json("pr", "checks", str(number), "-R", repo, "--json", "bucket")
    _reviews[(repo, number)] = (time.monotonic(), (view, checks))
    _review_fetching.discard((repo, number))


def _live_review(repo, number):
    """The cached `(view, checks)` gh JSON for a PR; a missing or stale entry refreshes in the background."""
    key = (repo, number)
    at, found = _reviews.get(key, (None, (None, None)))
    final = isinstance(found[0], dict) and found[0].get("state") in ("MERGED", "CLOSED")
    if not final and (at is None or time.monotonic() - at > PR_TTL) and key not in _review_fetching:
        _review_fetching.add(key)
        threading.Thread(target=_fetch_review, args=key, daemon=True).start()
    return found


def _ledger_entries(data_dir):
    """`(owner/repo, its PR entries by number)` for each orca-pr-review ledger in `data_dir`."""
    for path in sorted((Path(data_dir) / "pr-review").glob("*__*.json")):
        led = _read(path)
        if not isinstance(led, dict) or not led.get("repo"):
            continue
        prs = led.get("prs") if isinstance(led.get("prs"), dict) else {}
        yield led["repo"], sorted((e for e in prs.values() if isinstance(e, dict) and isinstance(e.get("number"), int)), key=lambda e: e["number"])


def _review_column(entry):
    verdict = entry.get("verdict")
    if verdict == "APPROVED":
        return "approved"
    if verdict in ("CHANGES_REQUESTED", "COMMENTED"):  # posted feedback waits on the author either way
        return "changes_requested"
    if entry.get("draft"):
        return "draft_ready"
    return "reviewing" if entry.get("worker") else "new"


def _review_card(repo, entry):
    finished = entry.get("finishedAt")
    # A finished entry is final: its card comes from the ledger alone, with no gh call.
    view, checks = (None, None) if finished else _live_review(repo, entry["number"])
    view = view if isinstance(view, dict) else {}
    counted = [c for c in checks if c.get("bucket") != "skipping"] if isinstance(checks, list) else None
    state = entry.get("state") if finished else view.get("state")
    verdict = entry.get("verdict")
    column = ({"APPROVED": "approved", "CHANGES_REQUESTED": "changes_requested"}.get(verdict, "reviewing")
              if finished else _review_column(entry))
    # A draft from an earlier round is never the one waiting: each round writes round-<r>.json.
    draft = _read(entry["draft"]) if column == "draft_ready" and Path(entry["draft"]).name == f"round-{entry.get('round')}.json" else None
    held = isinstance(draft, dict)
    return {
        "number": entry["number"],
        "url": view.get("url") or entry.get("url"),
        "title": view.get("title") or entry.get("title"),
        "author": (view.get("author") or {}).get("login") or entry.get("author"),
        "assignees": [a["login"] for a in view["assignees"]] if "assignees" in view else None,
        "head": view.get("headRefName"),
        "base": view.get("baseRefName"),
        "checks": {"passed": sum(c.get("bucket") == "pass" for c in counted), "total": len(counted)} if counted is not None else None,
        "status": "DRAFT" if state == "OPEN" and view.get("isDraft") else state,
        "round": entry.get("round"),
        "harness": entry.get("harness"),
        "column": column,
        "claimedAt": entry.get("claimedAt"),
        "finishedAt": finished,
        "held": held,
        "draft": {"event": draft.get("event"), "body": draft.get("body")} if held else None,
        "mine": False,
    }


OWN_TTL = 300
OWN_FIELDS = "number,title,url,state,isDraft,createdAt,updatedAt,closedAt,author"
# Watched Repo `owner/repo` -> (fetched at, [gh search JSON plus "merged"]): the PRs the user reviewed by hand.
_own = {}
_own_fetching = set()


def _fetch_own(repo, since):
    """Search gh for the PRs the user reviewed by hand on `repo`, at most 100 per search."""
    try:
        search = ("search", "prs", "--reviewed-by", "@me", "--repo", repo, "--updated", f">={since}", "--limit", "100")
        found = _gh_json(*search, "--json", OWN_FIELDS)
        # gh search reports only open or closed, so a second search learns which closed PRs merged.
        merged = _gh_json(*search, "--merged", "--json", "number")
        # Either search failing leaves the cache as it was, so the next poll retries and a merged PR never reads CLOSED.
        if isinstance(found, list) and isinstance(merged, list):
            numbers = {m.get("number") for m in merged if isinstance(m, dict)}
            _own[repo] = (time.monotonic(), [{**f, "merged": f["number"] in numbers} for f in found
                                             if isinstance(f, dict) and isinstance(f.get("number"), int)])
    finally:
        _own_fetching.discard(repo)


def _own_card(pr):
    open_ = str(pr.get("state")).lower() == "open"
    status = ("DRAFT" if pr.get("isDraft") else "OPEN") if open_ else "MERGED" if pr["merged"] else "CLOSED"
    return {"number": pr["number"], "url": pr.get("url"), "title": pr.get("title"), "author": (pr.get("author") or {}).get("login"),
            "assignees": None, "head": None, "base": None, "checks": None, "status": status, "round": None, "harness": None,
            "column": "approved", "claimedAt": pr.get("createdAt"), "held": False, "draft": None, "mine": True,
            "finishedAt": None if open_ else pr.get("closedAt")}  # gh gives an open PR a zero-time closedAt


def _add_own_reviews(data_dir, repos):
    """Add to `repos` the PRs the user reviewed by hand on each Watched Repo inside the window that no ledger holds."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=recent_window_hours(data_dir))
    ledger = {}
    for repo, entries in _ledger_entries(data_dir):
        ledger.setdefault(repo.lower(), set()).update(e["number"] for e in entries)
    for repo in watched_repos(data_dir):
        at, prs = _own.get(repo, (None, []))
        if (at is None or time.monotonic() - at > OWN_TTL) and repo not in _own_fetching:
            _own_fetching.add(repo)
            threading.Thread(target=_fetch_own, args=(repo, f"{cutoff:%Y-%m-%d}"), daemon=True).start()
        cards = [_own_card(p) for p in prs if p["number"] not in ledger.get(repo.lower(), ()) and (_when(p.get("updatedAt")) or cutoff) > cutoff]
        if cards:
            found = next((r for r in repos if r["name"].lower() == repo.lower()), None)
            if found is None:
                repos.append(found := {"name": repo, "prs": []})
            found["prs"].extend(sorted(cards, key=lambda c: c["number"]))


def build_reviews(data_dir):
    """The `reviews` section: one repo per orca-pr-review ledger, one card per PR in flight or finished inside the window."""
    now, window = datetime.now(timezone.utc), timedelta(hours=recent_window_hours(data_dir))
    repos = []
    for repo, entries in _ledger_entries(data_dir):
        # An unreadable finishedAt counts as old, so a broken entry never pins a card.
        fresh = [e for e in entries if not e.get("finishedAt") or now - (_when(e["finishedAt"]) or datetime.min.replace(tzinfo=timezone.utc)) <= window]
        cards = [c for c in (_review_card(repo, e) for e in fresh) if c["finishedAt"] or c["status"] not in ("MERGED", "CLOSED")]
        repos.append({"name": repo, "prs": cards})
    _add_own_reviews(data_dir, repos)
    return {"repos": repos}


def _runs(data_dir):
    return (_read(Path(data_dir) / REGISTRY_FILE) or {}).get("runs") or []


def jump(data_dir, repo_path, workstream):
    """Focus the Owning Session's Orca terminal: `(http code, body)`."""
    run = next((r for r in _runs(data_dir) if (r.get("repoPath"), r.get("workstream")) == (repo_path, workstream)), None)
    if run and run.get("kind") == "pr-review":
        status = _read(Path(data_dir) / "pr-review" / "loop.json") or {}
    else:
        status = _status(run) if run else None
    if status is None:
        return 404, {"ok": False, "error": f"No run of {workstream} in {repo_path} is on the Board."}
    if not status.get("terminal"):
        return 409, {"ok": False, "error": "This run recorded no Orca terminal. It started outside Orca, so there is no session to jump to."}
    try:
        done = subprocess.run([*orca_cli(), "terminal", "switch", "--terminal", status["terminal"]], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return 502, {"ok": False, "error": "Orca is unreachable: the orca command is not installed. Open Orca and try again."}
    except subprocess.TimeoutExpired:
        return 502, {"ok": False, "error": "Orca is unreachable: orca terminal switch did not answer in 10 seconds. Open Orca and try again."}
    if done.returncode != 0:
        why = (done.stderr or done.stdout).strip().splitlines()
        return 502, {"ok": False, "error": f"Orca is unreachable: {why[-1] if why else 'orca terminal switch failed'}. Open Orca and try again."}
    return 200, {"ok": True}


def _json_safe(value):
    """False for Infinity or NaN anywhere inside, which the page's JSON.parse rejects."""
    try:
        json.dumps(value, allow_nan=False)
        return True
    except ValueError:
        return False


def _settings(path):
    """The repo's Prompt Settings as stored, so they compare with the `_config.json` copies scaffold.py made from them.

    Null with no checkout or no file `write_settings.py` would accept.
    """
    try:
        found = _drop_retired(json.loads((Path(path) / ".orca" / "prompts" / "prompt-settings.json").read_text())) if path else None
        return found if isinstance(found, dict) and not settings_problems(found) else None
    except Exception:
        return None  # the form edits only a file the writer would accept; /orca-prompt-settings repairs the rest


def build_board(data_dir, now=None):
    """The `GET /api/board` payload, built from the Run Registry in `data_dir`."""
    now = now or datetime.now(timezone.utc)
    window = recent_window_hours(data_dir)
    names, watched = repo_names(data_dir), watched_repos(data_dir)
    loop_on = (_read(Path(data_dir) / "pr-review" / "loop.json") or {}).get("active") is True
    repos, attention = {}, []

    def repo(path, slug):
        return repos.setdefault(path or slug, {"name": names.get(path) or Path(path or slug).name, "path": path, "slug": slug,
                                               "executeActive": False, "prReviewActive": False, "totals": None, "workstreams": []})

    for run in _runs(data_dir):
        if not isinstance(run, dict) or not isinstance(run.get("repoPath"), str) or not Path(run["repoPath"]).is_dir():
            continue  # a repo that is gone leaves the Board
        lane = repo(*_checkout(run["repoPath"]))
        status = _status(run) if run.get("kind") != "pr-review" else None
        ws = _workstream(run, status, now, window, Path(lane["path"]).name) if status is not None else None
        if ws is None:
            continue
        attention += _attention(run, status, ws["waves"], lane["name"])
        lane["workstreams"].append(ws)
    # GitHub names are case-insensitive, so a Watched Repo matches its checkout's origin in any case.
    local = {r["slug"].lower() for r in repos.values() if r["slug"]}
    for slug in watched:
        if slug.lower() not in local:
            repo(None, slug)
    on = {s.lower() for s in watched} if loop_on else set()
    for lane in repos.values():
        lane["executeActive"] = any(ws["active"] for ws in lane["workstreams"])
        lane["prReviewActive"] = bool(lane["slug"]) and lane["slug"].lower() in on
        lane["totals"] = totals([i for ws in lane["workstreams"] for w in ws["waves"] for i in w["items"]])
        lane["settings"] = _settings(lane["path"])
    return {
        "generatedAt": now.isoformat(timespec="seconds"),
        "attention": sorted(attention + review_attention(data_dir), key=lambda a: a["kind"] == "failed"),
        "repos": sorted(repos.values(), key=lambda r: (r["name"], r["path"] or "")),
        "reviews": build_reviews(data_dir),
    }


def make_server(data_dir, port=0, idle_seconds=IDLE_SECONDS, dist=DIST):
    """A server on 127.0.0.1 that shuts itself down `idle_seconds` after the last /api/board."""
    last_poll = [time.monotonic()]

    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, kind, cache="no-store"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, out):
            self._send(code, json.dumps(out).encode(), "application/json")

        def _refused(self):
            """403 for a foreign Host, before anything is read or served."""
            if board_write.host_ok(self.headers.get("Host"), self.server.server_address[1]):
                return False
            self._json(403, {"ok": False, "fail": ["FAIL: this Board answers only on 127.0.0.1 or localhost"]})
            return True

        def do_GET(self):
            try:
                if not self._refused():
                    self._get()
            except Exception as e:
                self._json(500, {"ok": False, "fail": [f"FAIL: {type(e).__name__}: {e}"]})

        def _get(self):
            path = self.path.split("?")[0]
            if path == "/api/board":
                last_poll[0] = time.monotonic()
                return self._send(200, json.dumps(build_board(data_dir)).encode(), "application/json")
            if path == "/api/ping":
                return self._send(200, json.dumps({"pid": os.getpid()}).encode(), "application/json")
            # Avatar frames never change while the server runs, so the page's animation reads them from cache.
            root, cache = (AVATARS, "max-age=3600") if path.startswith("/avatars/") else (dist, "no-store")
            file = (root / (path.removeprefix("/avatars/").lstrip("/") or "index.html")).resolve()
            if not file.is_relative_to(root.resolve()) or not file.is_file():
                return self._send(404, b"not found", "text/plain")
            body = file.read_bytes()
            if file == (Path(dist) / "index.html").resolve():
                body = board_write.page(body, token)
            self._send(200, body, TYPES.get(file.suffix, "application/octet-stream"), cache)

        def do_POST(self):
            try:
                if not self._refused():
                    self._post()
            except Exception as e:
                self._json(500, {"ok": False, "fail": [f"FAIL: {type(e).__name__}: {e}"]})

        def _post(self):
            path = self.path.split("?")[0]
            if path != "/api/jump" and path not in board_write.ROUTES:
                return self._send(404, b"not found", "text/plain")
            if not board_write.token_ok(self.headers.get(board_write.TOKEN_HEADER), token):
                return self._json(403, {"ok": False, "fail": [f"FAIL: {path} needs the Board's {board_write.TOKEN_HEADER} header"]})
            try:
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    raise ValueError
                size = int(self.headers.get("Content-Length") or 0)
                if not 0 <= size <= board_write.MAX_BODY:
                    raise ValueError
                body = json.loads(self.rfile.read(size))
            except (ValueError, RecursionError):
                if path != "/api/jump":
                    return self._json(400, {"ok": False, "fail": [f"FAIL: {path} takes a JSON body of at most {board_write.MAX_BODY} bytes"]})
                body = None
            if path != "/api/jump":
                return self._json(*board_write.handle(data_dir, path, body))
            try:
                code, out = jump(data_dir, body["repoPath"], body["workstream"])
            except (KeyError, TypeError):
                code, out = 400, {"ok": False, "error": 'POST /api/jump takes a JSON body {"repoPath", "workstream"}.'}
            self._json(code, out)

    server = ThreadingHTTPServer((HOST, port), Handler)
    server.token = token

    def watch():
        while time.monotonic() - last_poll[0] < idle_seconds:
            time.sleep(min(1, idle_seconds / 4))
        server.shutdown()

    threading.Thread(target=watch, daemon=True).start()
    return server


def serve(data_dir):
    server = make_server(data_dir)
    state = Path(data_dir) / STATE_FILE
    state.write_text(json.dumps({"pid": os.getpid(), "port": server.server_address[1]}))
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    try:
        server.serve_forever()
    finally:
        if (_read(state) or {}).get("pid") == os.getpid():
            state.unlink(missing_ok=True)


def running(data_dir):
    """The `{pid, port}` of a live Board server, or None."""
    state = _read(Path(data_dir) / STATE_FILE)
    if not state:
        return None
    try:
        with urllib.request.urlopen(f"http://{HOST}:{state['port']}/api/ping", timeout=1) as r:
            return state if json.load(r).get("pid") == state["pid"] else None
    except (OSError, ValueError, KeyError):
        return None


def start(data_dir):
    """Reuse the running server or start one in the background; return its port."""
    found = running(data_dir)
    if found:
        return found["port"], False
    subprocess.Popen([sys.executable, __file__, "serve"], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env={**os.environ, "CLAUDE_PLUGIN_DATA": str(data_dir)})
    for _ in range(50):
        time.sleep(0.1)
        found = running(data_dir)
        if found:
            return found["port"], True
    raise RuntimeError("the Board server did not start within 5 seconds")


def stop(data_dir):
    """End the running server; return whether one was running."""
    found = running(data_dir)
    if not found:
        (Path(data_dir) / STATE_FILE).unlink(missing_ok=True)
        return False
    os.kill(found["pid"], signal.SIGTERM)
    return True


def main(argv):
    data = plugin_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    if argv == ["serve"]:
        return serve(data)
    if argv == ["stop"]:
        print("Board server stopped." if stop(data) else "No Board server is running.")
        return
    if argv not in ([], ["--orca"]):
        print("FAIL: usage: board.py [--orca] | stop")
        sys.exit(1)
    port, new = start(data)
    url = f"http://{HOST}:{port}/"
    if argv == ["--orca"]:
        try:
            opened = subprocess.run([*orca_cli(), "tab", "create", "--url", url], capture_output=True).returncode == 0
        except FileNotFoundError:
            opened = False
    else:
        opened = webbrowser.open(url)
    print(f"Open {url}" if not opened else f"Board open at {url}")
    print("Started a new server." if new else "Reused the running server.")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, RuntimeError) as e:
        print(f"FAIL: {e}")
        sys.exit(1)
