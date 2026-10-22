"""The only writer of a Workstream's `_status.json`, the file the Wave band reads.

Usage:
    python3 set_status.py <workstream-dir> --start                  # build from _config.json, mark active
    python3 set_status.py <workstream-dir> <id> <state> [reason]    # move one Work Item
    python3 set_status.py <workstream-dir> <id> complete --pr <n>   # complete it and record its PR
    python3 set_status.py <workstream-dir> --stop                   # clear active
    python3 set_status.py <workstream-dir> --show                   # print the Wave-by-Wave table

`<state>` is one of `todo`, `in_progress`, `complete`, `failed`; `failed`
requires a reason. `--pr` goes only with `complete`. The write that makes every
item `complete` stamps `finishedAt`. Any bad input prints one `FAIL:` line, exits 1 and leaves
the file untouched. Every write goes to a temp file in the same directory and
is renamed over `_status.json`, so a reader never sees a half-written file.

`--start` reads `workItems[]` from `_config.json`; each item needs `wave` and
`title`. Each item's `harness` is routed from its `size` and `harnesses[]` by
the same tier rule dispatch uses (`scaffold.route_harness`). Re-running `--start` keeps the state of items already in the file,
so a resumed Workstream does not lose progress, and keeps `startedAt` and each item's `pr`.
Re-running a finished Workstream stamps a fresh `startedAt` and drops `finishedAt`. It also clears `active` on
every sibling Workstream, so at most one is active.

`_status.json` schema:

    {
      "workstream": "string: the workstream name from _config.json",
      "active": "boolean: true while the Wave band should draw this Workstream",
      "updatedAt": "string: ISO 8601 UTC time of the last write",
      "startedAt": "string | null: ISO 8601 UTC time of the first --start",
      "finishedAt": "string | null: ISO 8601 UTC time of the write that made every item complete",
      "items": [
        {
          "id": "string: matches workItems[].id in _config.json",
          "title": "string: the Work Item title shown in the band",
          "wave": "number: the Wave the item belongs to, starting at 1",
          "state": "todo | in_progress | complete | failed",
          "reason": "string | null: why it failed; null in every other state",
          "harness": "string | null: the Agent Harness name dispatch routes the item to; null without size or harnesses",
          "pr": "number | null: the PR number recorded by `<id> complete --pr <n>`"
        }
      ]
    }

`items` keeps the `_config.json` order. `startedAt`, `finishedAt` and `pr` are
optional: a file written before them reads as if each were null.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scaffold import claim, route_harness, write_json_atomic

STATES = ("todo", "in_progress", "complete", "failed")
STATUS_FILE = "_status.json"


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
        "items": items,
    })
    claim(workstream_dir / STATUS_FILE)


def set_state(workstream_dir, item_id, state, reason=None, pr=None):
    if state not in STATES:
        raise StatusError(f"unknown state {state!r}; use one of {', '.join(STATES)}")
    if state == "failed" and not reason:
        raise StatusError("state failed needs a reason")
    if pr is not None and state != "complete":
        raise StatusError("--pr goes only with complete")
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    for item in status["items"]:
        if item["id"] == item_id:
            item["state"] = state
            item["reason"] = reason if state == "failed" else None
            if pr is not None:
                item["pr"] = pr
            status["startedAt"], status["finishedAt"] = _clock(status, status["items"])
            _write(workstream_dir, status)
            return
    raise StatusError(f"unknown Work Item id {item_id!r}")


def stop(workstream_dir):
    status = _read_json(Path(workstream_dir) / STATUS_FILE)
    status["active"] = False
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


def main(argv):
    if len(argv) < 2:
        raise StatusError("usage: set_status.py <workstream-dir> --start | --stop | --show | <id> <state> [reason]")
    workstream_dir, action, rest = argv[0], argv[1], argv[2:]
    if action == "--start":
        start(workstream_dir)
    elif action == "--stop":
        stop(workstream_dir)
    elif action == "--show":
        print(show(workstream_dir))
    elif action.startswith("--"):
        raise StatusError(f"unknown flag {action}")
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
