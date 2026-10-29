"""The only writer of a Workstream's `_status.json`, the file the Wave band reads.

Usage:
    python3 set_status.py <workstream-dir> --start                  # build from _config.json, mark active
    python3 set_status.py <workstream-dir> <id> <state> [reason]    # move one Work Item
    python3 set_status.py <workstream-dir> <id> complete --pr <n>   # complete it and record its PR
    python3 set_status.py <workstream-dir> <id> progress <done>/<total> <note>  # record a worker's step
    python3 set_status.py <workstream-dir> <id> <verb> [args...]    # run a registered item verb
    python3 set_status.py <workstream-dir> <id> review <round> <reviewer> [SHIP|NO-SHIP]  # Work Item Review
    python3 set_status.py <workstream-dir> <id> review <round> <reviewer> --report <path>  # verdict from the report
    python3 set_status.py <workstream-dir> run <runId>              # record the Orca Run
    python3 set_status.py <workstream-dir> <id> task <taskId>       # record the item's Orca Task
    python3 set_status.py <workstream-dir> --stop                   # clear active
    python3 set_status.py <workstream-dir> --attention <kind> <question> [option...]  # open an Attention Item
    python3 set_status.py <workstream-dir> --attention --clear      # clear it
    python3 set_status.py <workstream-dir> --show                   # print the Wave-by-Wave table
    python3 set_status.py <workstream-dir> log <title> <body> [--commit <repo>@<sha>] [--supersedes <title>]

`<state>` is one of `todo`, `in_progress`, `reviewing`, `complete`, `failed`; `failed`
requires a reason. `--pr` goes only with `complete`.

Two transitions are refused, so the prose rules in orca-execute hold:

- `complete` fails when `_config.json` has `review: true` and the item's last
  review verdict is not `SHIP`, and fails without `--pr` when `integration` is
  `pr` or `pr-merge`.
- `in_progress` for a Wave N+1 item fails until every Wave N item is `complete`
  and `_decisions.md` holds a `Wave N retro` entry. N is the nearest lower Wave.
  An item already `in_progress` is not checked again.

The write that makes every
item `complete` stamps `finishedAt`. Any bad input prints one `FAIL:` line, exits 1 and leaves
the file untouched. Every write goes to a temp file in the same directory and
is renamed over `_status.json`, so a reader never sees a half-written file. Every verb but
`--show` and `log` holds an exclusive `flock` on `_status.json.lock` from its read to its
write, so parallel writers never lose an update.

`--start` reads `workItems[]` from `_config.json`; each item needs `wave` and
`title`. Each item's `harness` is routed from its `size` and `harnesses[]` by
the same tier rule dispatch uses (`scaffold.route_harness`). Re-running `--start` keeps the state of items already in the file,
so a resumed Workstream does not lose progress, and keeps `startedAt` and each item's `pr`.
Re-running a finished Workstream stamps a fresh `startedAt` and drops `finishedAt`. It also clears `active` on
every sibling Workstream, so at most one is active. `--start` records the Orca terminal it ran in
(`orca terminal show --json`), or null outside Orca, so the Board can jump to the Owning Session.

`--attention` records the one open Main Orchestrator question, `kind` `question`
or `gate`, with its options and the time it was asked. The orca-helpers hooks
module runs it when the question tool opens in the Owning Session and runs
`--attention --clear` when the tool returns (ADR 0014). When the Workstream sits under
`<repo>/.orca/prompts/`, `--start` also upserts it into the Run Registry, `runs.json` in
the Plugin Data Dir, which the Board reads.

Run Registry schema (`runs.json`), one entry per repo path and Workstream:

    {"runs": [{"repoPath": "string", "repoName": "string", "workstream": "string", "startedAt": "string: ISO 8601 UTC time of the last --start"}]}

An item verb is a function in `VERBS`, keyed by its name, called as
`fn(workstream_dir, item_id, args)`. It reports bad input by raising
`StatusError` and writes through `_write`. A verb name never shadows a state.

`progress` stores `{done, total, note, at}` on the item
and refuses an unknown id, a malformed count and done greater than total. A total
may change between calls. Any move to a state other than `in_progress` clears it.

The `review` verb records one Work Item Review round. Without a verdict it opens
the round and sets `reviewing`. `SHIP` keeps `reviewing` until the Main
Orchestrator integrates and sets `complete`. `NO-SHIP` sends the item back to
`in_progress` for the author, and the third NO-SHIP sets `failed` with the
reason `review: 3 NO-SHIP rounds`. `<round>` is 1 to 3; `<reviewer>` is the
reviewer's Agent Harness name, which the Wave Band draws beside the author's.
`--report <path>` reads the verdict from the report's last non-blank line,
`VERDICT: SHIP` or `VERDICT: NO-SHIP`. A report without that line counts as NO-SHIP.

`run <runId>` stores the Orca Run id at the top level, and `<id> task <taskId>`
stores the item's Orca Task id. Both stay null until set, and `--start` keeps them.

`log` appends a dated entry to the Decision Log, `_decisions.md`, creating it
with its header when absent:

    ### <YYYY-MM-DD> · <title>

    <body>

    Commit: <repo>@<sha>
    Supersedes: <old title>

`Commit:` and `Supersedes:` appear only when passed. `--supersedes` names an
earlier entry's title; that entry gains one `Superseded by: <title>` line and
is otherwise left as written. It fails when no live entry has that title.

`_status.json` schema:

    {
      "workstream": "string: the workstream name from _config.json",
      "active": "boolean: true while the Wave band should draw this Workstream",
      "updatedAt": "string: ISO 8601 UTC time of the last write",
      "startedAt": "string | null: ISO 8601 UTC time of the first --start",
      "finishedAt": "string | null: ISO 8601 UTC time of the write that made every item complete",
      "terminal": "string | null: the Orca terminal handle --start ran in",
      "attention": "{kind: question | gate, question: string, options: [string], askedAt: string} | null",
      "runId": "string | null: the Orca Run id recorded by `run <runId>`",
      "items": [
        {
          "id": "string: matches workItems[].id in _config.json",
          "title": "string: the Work Item title shown in the band",
          "wave": "number: the Wave the item belongs to, starting at 1",
          "state": "todo | in_progress | reviewing | complete | failed",
          "reason": "string | null: why it failed; null in every other state",
          "harness": "string | null: the Agent Harness name dispatch routes the item to; null without size or harnesses",
          "pr": "number | null: the PR number recorded by `<id> complete --pr <n>`",
          "enteredAt": "string | null: ISO 8601 UTC time the item entered its current state",
          "progress": "{done: number, total: number, note: string, at: string} | null: the worker's latest step; null outside in_progress",
          "review": "{round: number, verdict: 'SHIP' | 'NO-SHIP' | null, reviewer: string} | absent before the first review round",
          "taskId": "string | null: the Orca Task id recorded by `<id> task <taskId>`"
        }
      ]
    }

`items` keeps the `_config.json` order. `startedAt`, `finishedAt`, `terminal`, `attention`, `runId`, `pr`, `enteredAt`, `progress`, `review` and `taskId` are
optional: a file written before them reads as if each were null.
"""
import fcntl
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from orca_cli import orca_cli
from scaffold import DECISION_LOG, DECISION_LOG_HEADER, claim, route_harness, write_json_atomic, write_text_atomic

STATES = ("todo", "in_progress", "reviewing", "complete", "failed")
ATTENTION_KINDS = ("question", "gate")
STATUS_FILE = "_status.json"
# Item verbs: name -> fn(workstream_dir, item_id, args). Each later verb registers here.
VERBS = {}
PROGRESS_USAGE = 'usage: set_status.py <workstream-dir> <id> progress <done>/<total> "<note>"'
REGISTRY_FILE = "runs.json"
REVIEW_ROUNDS = 3
VERDICTS = ("SHIP", "NO-SHIP")
PR_INTEGRATIONS = ("pr", "pr-merge")


def plugin_data_dir():
    """The Plugin Data Dir: ${CLAUDE_PLUGIN_DATA}, or ~/.claude/orca-helpers/ where it is unset."""
    return Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "orca-helpers")


def register_run(workstream_dir, workstream):
    """Upsert this run into the Run Registry, keyed by repo path plus Workstream."""
    d = Path(workstream_dir).resolve()
    if d.parent.name != "prompts" or d.parent.parent.name != ".orca":
        return
    repo = d.parent.parent.parent
    data = plugin_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    try:
        runs = json.loads((data / REGISTRY_FILE).read_text()).get("runs", [])
    except (OSError, json.JSONDecodeError):
        runs = []
    runs = [r for r in runs if (r.get("repoPath"), r.get("workstream")) != (str(repo), workstream)]
    runs.append({"repoPath": str(repo), "repoName": repo.name, "workstream": workstream, "startedAt": _now()})
    write_json_atomic(data, REGISTRY_FILE, {"runs": runs}, ".runs-")


class StatusError(Exception):
    pass


def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise StatusError(f"{path} does not exist")
    except json.JSONDecodeError as e:
        raise StatusError(f"{path} is not valid JSON: {e}")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clock(old, items):
    """The run's (startedAt, finishedAt): a finished run that reopens restarts its clock."""
    done = all(i["state"] == "complete" for i in items)
    # A legacy status (items, no startedAt) keeps None: a start time invented now would read "Done · 0m".
    started = old.get("startedAt") or (None if old else _now())
    if old.get("finishedAt"):
        return (started, old["finishedAt"]) if done else (_now(), None)
    return started, _now() if done else None


def _write(workstream_dir, status):
    """Write `_status.json` atomically: temp file in the same dir, then rename."""
    write_json_atomic(workstream_dir, STATUS_FILE, status, ".status-")


@contextmanager
def _locked(workstream_dir):
    """Hold an exclusive flock on `_status.json.lock` from a verb's read to its write, so parallel writers keep every update."""
    path = Path(workstream_dir) / f"{STATUS_FILE}.lock"
    try:
        f = open(path, "a")
    except FileNotFoundError:
        raise StatusError(f"{Path(workstream_dir) / STATUS_FILE} does not exist")
    with f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def _terminal():
    """The Orca terminal handle this process runs in, or None outside Orca."""
    try:
        out = subprocess.run([*orca_cli(), "terminal", "show", "--json"], capture_output=True, text=True, timeout=5)
        return json.loads(out.stdout)["result"]["terminal"]["handle"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


def start(workstream_dir):
    workstream_dir = Path(workstream_dir)
    config = _read_json(workstream_dir / "_config.json")
    status_path = workstream_dir / STATUS_FILE
    old_status = _read_json(status_path) if status_path.exists() else {}
    previous = {i["id"]: i for i in old_status.get("items", [])}

    harnesses = config.get("harnesses") or []
    items = []
    for item in config.get("workItems", []):
        missing = [k for k in ("id", "wave", "title") if k not in item]
        if missing:
            raise StatusError(
                f"workItems entry {item.get('id', '?')} lacks {', '.join(missing)}; "
                "re-scaffold the Workstream with orca-prompt"
            )
        old = previous.get(item["id"], {})
        try:
            routed = route_harness(item["size"], harnesses)["name"] if harnesses and "size" in item else None
        except ValueError as e:
            raise StatusError(str(e))
        items.append({
            "id": item["id"],
            "title": item["title"],
            "wave": item["wave"],
            "state": old.get("state", "todo"),
            "reason": old.get("reason"),
            "harness": routed,
            "pr": old.get("pr"),
            # A legacy item (no enteredAt) keeps None rather than a time invented now.
            "enteredAt": old.get("enteredAt") if old else _now(),
            "progress": old.get("progress"),
            **({"review": old["review"]} if old.get("review") else {}),
            "taskId": old.get("taskId"),
        })
    if not items:
        raise StatusError("_config.json has no workItems")

    for sibling in workstream_dir.parent.glob(f"*/{STATUS_FILE}"):
        if sibling.parent.resolve() == workstream_dir.resolve():
            continue
        try:
            other = json.loads(sibling.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if other.get("active"):
            other["active"] = False
            _write(sibling.parent, other)

    started, finished = _clock(old_status, items)
    _write(workstream_dir, {
        "workstream": config.get("workstream"),
        "active": True,
        "startedAt": started,
        "finishedAt": finished,
        "terminal": _terminal(),
        "attention": None,
        "runId": old_status.get("runId"),
        "items": items,
    })
    claim(workstream_dir / STATUS_FILE)
    register_run(workstream_dir, config.get("workstream") or workstream_dir.name)


def _config(workstream_dir):
    """`_config.json`, or {} when absent, so a bare `_status.json` keeps working."""
    path = Path(workstream_dir) / "_config.json"
    return _read_json(path) if path.exists() else {}


def _guard(workstream_dir, status, item, state, pr):
    """Refuse a move orca-execute forbids: an unreviewed or PR-less complete, or a Wave started early."""
    if state == "complete":
        config = _config(workstream_dir)
        verdict = (item.get("review") or {}).get("verdict")
        if config.get("review") is True and verdict != "SHIP":
            raise StatusError(f"{item['id']} cannot complete: review is on and its last verdict is {verdict or 'missing'}, not SHIP")
        if config.get("integration") in PR_INTEGRATIONS and pr is None:
            raise StatusError(f"{item['id']} cannot complete without --pr: integration is {config['integration']}")
    if state == "in_progress" and item["state"] != "in_progress":
        earlier = [i["wave"] for i in status["items"] if i["wave"] < item["wave"]]
        if not earlier:
            return
        wave = max(earlier)
        open_ = [i["id"] for i in status["items"] if i["wave"] == wave and i["state"] != "complete"]
        if open_:
            raise StatusError(f"{item['id']} cannot start: Wave {wave} has items not complete: {', '.join(open_)}")
        log = Path(workstream_dir) / DECISION_LOG
        text = log.read_text() if log.exists() else ""
        if not re.search(rf"^### \S+ · Wave {wave} retro$", text, re.MULTILINE):
            raise StatusError(f"{item['id']} cannot start: {DECISION_LOG} has no 'Wave {wave} retro' entry")


def set_state(workstream_dir, item_id, state, reason=None, pr=None):
    if state not in STATES:
        raise StatusError(f"unknown state {state!r}; use one of {', '.join(STATES + tuple(VERBS))}")
    if state == "failed" and not reason:
        raise StatusError("state failed needs a reason")
    if pr is not None and state != "complete":
        raise StatusError("--pr goes only with complete")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    for item in status["items"]:
        if item["id"] == item_id:
            _guard(workstream_dir, status, item, state, pr)
            if item["state"] != state:
                item["enteredAt"] = _now()
            item["state"] = state
            item["reason"] = reason if state == "failed" else None
            if state != "in_progress":
                item["progress"] = None
            if pr is not None:
                item["pr"] = pr
            status["startedAt"], status["finishedAt"] = _clock(status, status["items"])
            _write(workstream_dir, status)
            return
    raise StatusError(f"unknown Work Item id {item_id!r}")


def progress(workstream_dir, item_id, args):
    """`<id> progress <done>/<total> <note>`: the worker's latest step on its item."""
    if len(args) != 2:
        raise StatusError(PROGRESS_USAGE)
    done, _, total = args[0].partition("/")
    if not (done.isdigit() and total.isdigit()) or int(total) == 0:
        raise StatusError(f"progress {args[0]!r} is not <done>/<total> with a total above 0; {PROGRESS_USAGE}")
    if int(done) > int(total):
        raise StatusError(f"progress {args[0]!r} has done greater than total")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    for item in status["items"]:
        if item["id"] == item_id:
            item["progress"] = {"done": int(done), "total": int(total), "note": args[1], "at": _now()}
            _write(workstream_dir, status)
            return
    raise StatusError(f"unknown Work Item id {item_id!r}")


VERBS["progress"] = progress


def report_verdict(path):
    """The verdict on a review report's last non-blank line; an unsigned report is NO-SHIP."""
    try:
        lines = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    except OSError as e:
        raise StatusError(f"cannot read review report {path}: {e}")
    m = re.fullmatch(r"VERDICT:\s*(SHIP|NO-SHIP)", lines[-1]) if lines else None
    return m[1] if m else "NO-SHIP"


def review(workstream_dir, item_id, args):
    """`<id> review <round> <reviewer> [SHIP|NO-SHIP]`: open a review round, or sign it."""
    usage = "usage: set_status.py <workstream-dir> <id> review <round> <reviewer> [SHIP|NO-SHIP | --report <path>]"
    if len(args) == 4 and args[2] == "--report":
        args = [args[0], args[1], report_verdict(args[3])]
    if len(args) not in (2, 3) or not args[0].isdigit() or not args[1]:
        raise StatusError(usage)
    rnd, reviewer, verdict = int(args[0]), args[1], args[2] if len(args) == 3 else None
    if not 1 <= rnd <= REVIEW_ROUNDS:
        raise StatusError(f"review round must be 1 to {REVIEW_ROUNDS}, got {rnd}")
    if verdict is not None and verdict not in VERDICTS:
        raise StatusError(f"verdict must be SHIP or NO-SHIP, got {verdict!r}")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    item = next((i for i in status["items"] if i["id"] == item_id), None)
    if item is None:
        raise StatusError(f"unknown Work Item id {item_id!r}")
    item["review"] = {"round": rnd, "verdict": verdict, "reviewer": reviewer}
    old_state = item["state"]
    if verdict == "NO-SHIP" and rnd == REVIEW_ROUNDS:
        item["state"], item["reason"] = "failed", f"review: {REVIEW_ROUNDS} NO-SHIP rounds"
    else:
        item["state"], item["reason"] = ("in_progress" if verdict == "NO-SHIP" else "reviewing"), None
    # The same enteredAt and progress rules as set_state.
    if item["state"] != old_state:
        item["enteredAt"] = _now()
    if item["state"] != "in_progress":
        item["progress"] = None
    _write(workstream_dir, status)


VERBS["review"] = review


def task(workstream_dir, item_id, args):
    """`<id> task <taskId>`: the Orca Task id dispatch made for the item."""
    if len(args) != 1 or not args[0]:
        raise StatusError("usage: set_status.py <workstream-dir> <id> task <taskId>")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    item = next((i for i in status["items"] if i["id"] == item_id), None)
    if item is None:
        raise StatusError(f"unknown Work Item id {item_id!r}")
    item["taskId"] = args[0]
    _write(workstream_dir, status)


VERBS["task"] = task


def set_run(workstream_dir, args):
    """`run <runId>`: the Orca Run this Workstream executes in."""
    if len(args) != 1 or not args[0]:
        raise StatusError("usage: set_status.py <workstream-dir> run <runId>")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    status["runId"] = args[0]
    _write(workstream_dir, status)


def stop(workstream_dir):
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    status["active"] = False
    _write(workstream_dir, status)


def attention(workstream_dir, args):
    """Open the Attention Item `[kind, question, *options]`, or clear it with `["--clear"]`."""
    if args == ["--clear"]:
        entry = None
    elif len(args) >= 2 and args[0] in ATTENTION_KINDS and args[1]:
        entry = {"kind": args[0], "question": args[1], "options": args[2:], "askedAt": _now()}
    else:
        raise StatusError(f"usage: set_status.py <workstream-dir> --attention <{' | '.join(ATTENTION_KINDS)}> <question> [option...] | --attention --clear")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    status["attention"] = entry
    _write(workstream_dir, status)


def show(workstream_dir):
    """Return the Wave-by-Wave table as text."""
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    lines = [f"{status['workstream']} ({'active' if status['active'] else 'inactive'})"]
    for wave in sorted({i["wave"] for i in status["items"]}):
        items = [i for i in status["items"] if i["wave"] == wave]
        done = sum(i["state"] == "complete" for i in items)
        lines.append(f"\nWave {wave} ({done}/{len(items)})")
        for i in items:
            reason = f"  ! {i['reason']}" if i["reason"] else ""
            lines.append(f"  {i['state']:<11}  {i['id']}  {i['title']}{reason}")
    return "\n".join(lines)


def log(workstream_dir, title, body, commit=None, supersedes=None):
    """Append one Decision Log entry; mark the entry it supersedes with a `Superseded by` line."""
    if not title.strip() or "\n" in title:
        raise StatusError("log needs a one-line title")
    if not body.strip():
        raise StatusError("log needs a body")
    if re.search(r"^### ", body, re.MULTILINE):
        raise StatusError("a log body cannot hold a `### ` heading line")
    path = Path(workstream_dir) / DECISION_LOG
    if not Path(workstream_dir).is_dir():
        raise StatusError(f"{workstream_dir} does not exist")
    text = path.read_text() if path.exists() else DECISION_LOG_HEADER
    # Each entry runs from its heading to the next heading or the end of the file.
    entries = list(re.finditer(r"^### \S+ · (?P<title>[^\n]+)\n(?P<body>.*?)(?=^### |\Z)", text, re.DOTALL | re.MULTILINE))
    if supersedes is not None:
        live = [m for m in entries if m["title"] == supersedes and not re.search(r"^Superseded by: ", m["body"], re.MULTILINE)]
        if not live:
            raise StatusError(f"no live Decision Log entry titled {supersedes!r} to supersede")
        old = live[-1]
        marked = old.group(0).rstrip("\n") + f"\n\nSuperseded by: {title}\n" + ("\n" if old.end() < len(text) else "")
        text = text[:old.start()] + marked + text[old.end():]
    entry = [f"### {datetime.now().date().isoformat()} · {title}", "", body.strip()]
    trailer = ([f"Commit: {commit}"] if commit else []) + ([f"Supersedes: {supersedes}"] if supersedes else [])
    if trailer:
        entry += [""] + trailer
    text = text.rstrip("\n") + "\n\n" + "\n".join(entry) + "\n"
    write_text_atomic(path, text, ".decisions-")


def log_cli(workstream_dir, args):
    """`log <title> <body> [--commit <repo>@<sha>] [--supersedes <title>]`."""
    usage = "usage: set_status.py <workstream-dir> log <title> <body> [--commit <repo>@<sha>] [--supersedes <title>]"
    positional, flags = [], {}
    it = iter(args)
    for a in it:
        if a in ("--commit", "--supersedes"):
            value = next(it, None)
            if value is None or a in flags:
                raise StatusError(usage)
            flags[a] = value
        elif a.startswith("--"):
            raise StatusError(f"unknown flag {a}; {usage}")
        else:
            positional.append(a)
    if len(positional) != 2:
        raise StatusError(usage)
    log(workstream_dir, *positional, commit=flags.get("--commit"), supersedes=flags.get("--supersedes"))


def main(argv):
    if len(argv) < 2:
        raise StatusError("usage: set_status.py <workstream-dir> --start | --stop | --show | log <title> <body> | <id> <state> [reason]")
    workstream_dir, action, rest = argv[0], argv[1], argv[2:]
    if action in ("--show", "log"):
        dispatch(workstream_dir, action, rest)
    else:
        with _locked(workstream_dir):
            dispatch(workstream_dir, action, rest)


def dispatch(workstream_dir, action, rest):
    if action == "--start":
        start(workstream_dir)
    elif action == "--stop":
        stop(workstream_dir)
    elif action == "--show":
        print(show(workstream_dir))
    elif action == "log":
        log_cli(workstream_dir, rest)
    elif action == "--attention":
        attention(workstream_dir, rest)
    elif action == "run":
        set_run(workstream_dir, rest)
    elif action.startswith("--"):
        raise StatusError(f"unknown flag {action}")
    elif rest and rest[0] in VERBS and rest[0] not in STATES:
        VERBS[rest[0]](workstream_dir, action, rest[1:])
    elif "--pr" in rest:
        if len(rest) != 3 or rest[1] != "--pr" or not rest[2].isdigit():
            raise StatusError("usage: set_status.py <workstream-dir> <id> complete --pr <number>")
        set_state(workstream_dir, action, rest[0], pr=int(rest[2]))
    elif not rest or len(rest) > 2:
        raise StatusError("usage: set_status.py <workstream-dir> <id> <state> [reason | --pr <n>]")
    else:
        set_state(workstream_dir, action, rest[0], rest[1] if len(rest) == 2 else None)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except StatusError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
