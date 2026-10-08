"""Report Orca automations on this repo that fire near a proposed Scheduled Prompt time.

Two agents starting on the same repo minutes apart fight over the same worktree
and the same branch, so before creating a Scheduled Prompt the scheduler asks
what else is already booked nearby. This reads `orca automations list --json`
and reports every automation on this repo whose schedule fires within 15
minutes of the proposed instant.

Matching is a scan: every minute in the window is tested against each
automation's schedule in that automation's own timezone. A trigger this script
cannot expand — an RRULE, or a preset with no time — is reported under
`unresolved` rather than guessed at, so nothing is silently declared clear.

Usage:
    python3 check_conflicts.py 2026-09-02T05:00:00+00:00 [--repo <path>] [--window-minutes 15]
    python3 check_conflicts.py --demo

The proposed time is an ISO 8601 datetime; a naive one is read as UTC. `--repo`
defaults to this git working tree. Output is JSON; the exit code is 0 whether
or not there are conflicts, because this is a report and not a gate.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WINDOW_MINUTES = 15
FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")

# The presets `orca automations create --trigger` accepts, as cron with `{m}`/`{h}`
# filled from `--time`. `weekly` has no day-of-week in the CLI, so it stays unresolved.
PRESETS = {"hourly": "0 * * * *", "daily": "{m} {h} * * *", "weekdays": "{m} {h} * * 1-5"}


def _field(spec, low, high):
    """Expand one cron field into the set of values it matches."""
    values = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, _, raw_step = part.partition("/")
            step = int(raw_step)
        if part in ("*", ""):
            start, end = low, high
        elif "-" in part.lstrip("-"):
            start, _, end = part.partition("-")
            start, end = int(start), int(end)
        else:
            start = end = int(part)
        if start < low or end > high or end < start or step < 1:
            raise ValueError(f"cron field {spec!r} is out of range {low}-{high}")
        values.update(range(start, end + 1, step))
    return values


def parse_cron(expression):
    """Expand a 5-field cron expression into a list of value sets. Raises `ValueError`."""
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"{expression!r} is not a 5-field cron expression")
    return [_field(spec, low, high) for spec, (low, high) in zip(fields, FIELD_RANGES)]


def cron_matches(sets, moment):
    """True when local `moment` matches the expanded cron `sets`."""
    minutes, hours, doms, months, dows = sets
    if moment.minute not in minutes or moment.hour not in hours or moment.month not in months:
        return False
    # Cron's own rule: with both day fields restricted, either one matching is a match.
    dom_restricted = doms != set(range(1, 32))
    dow_restricted = dows != set(range(0, 7))
    dom_hit = moment.day in doms
    dow_hit = (moment.weekday() + 1) % 7 in dows
    if dom_restricted and dow_restricted:
        return dom_hit or dow_hit
    return dom_hit and dow_hit


def trigger_to_cron(automation):
    """Return the cron expression for an automation, or None when it cannot be expanded."""
    trigger = str(automation.get("trigger") or automation.get("schedule") or "").strip()
    if not trigger:
        return None
    template = PRESETS.get(trigger.lower())
    if template is None:
        return trigger if len(trigger.split()) == 5 else None
    time_match = HHMM.match(str(automation.get("time") or "").strip())
    if "{h}" in template and not time_match:
        return None
    if not time_match:
        return template
    return template.format(h=int(time_match.group(1)), m=int(time_match.group(2)))


def _repo_text(automation):
    """Every string that might name the automation's repo, flattened."""
    parts = []
    for key in ("repo", "repository", "repoPath", "repoId", "repoName", "path"):
        value = automation.get(key)
        if isinstance(value, dict):
            parts.extend(str(v) for v in value.values() if isinstance(v, (str, int)))
        elif value is not None:
            parts.append(str(value))
    return parts


def on_repo(automation, repo):
    """True when the automation names `repo`. An automation naming no repo is kept, not dropped."""
    parts = _repo_text(automation)
    if not parts:
        return True
    repo = str(repo)
    name = Path(repo).name
    return any(repo in part or part == name or Path(part).name == name for part in parts)


def firing_times(automation, proposed, window_minutes=WINDOW_MINUTES):
    """Return the local ISO times this automation fires within the window around `proposed`."""
    expression = trigger_to_cron(automation)
    if expression is None:
        raise ValueError(f"trigger {automation.get('trigger')!r} cannot be expanded to cron")
    sets = parse_cron(expression)
    try:
        tz = ZoneInfo(str(automation.get("timezone") or "UTC"))
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"timezone {automation.get('timezone')!r} is not an IANA timezone")
    hits = []
    for offset in range(-window_minutes, window_minutes + 1):
        moment = (proposed + timedelta(minutes=offset)).astimezone(tz)
        if cron_matches(sets, moment):
            hits.append(moment.isoformat())
    return hits


def _automations(payload):
    """Pull the automation list out of the `orca automations list --json` envelope."""
    if isinstance(payload, list):
        return payload
    result = payload.get("result", payload) if isinstance(payload, dict) else {}
    for key in ("automations", "items"):
        if isinstance(result.get(key), list) and result[key]:
            return result[key]
    return []


def check(proposed, repo, automations, window_minutes=WINDOW_MINUTES):
    """Return the conflict report for `proposed` against `automations` on `repo`."""
    conflicts, unresolved = [], []
    for automation in automations:
        if not on_repo(automation, repo):
            continue
        entry = {
            "id": automation.get("id"),
            "name": automation.get("name"),
            "trigger": automation.get("trigger") or automation.get("schedule"),
            "timezone": automation.get("timezone") or "UTC",
        }
        try:
            hits = firing_times(automation, proposed, window_minutes)
        except ValueError as e:
            unresolved.append(dict(entry, reason=str(e)))
            continue
        if hits:
            conflicts.append(dict(entry, firesAt=hits))
    return {
        "proposed": proposed.isoformat(),
        "repo": str(repo),
        "windowMinutes": window_minutes,
        "conflicts": conflicts,
        "unresolved": unresolved,
    }


def _list_automations():
    output = subprocess.run(
        ["orca", "automations", "list", "--json"], capture_output=True, text=True, check=True
    ).stdout
    return _automations(json.loads(output))


def _git_root():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return str(Path.cwd())


def demo():
    utc = timezone.utc
    proposed = datetime(2026, 9, 2, 5, 0, tzinfo=utc)
    repo = "/repos/skills-build"

    yearly = {"id": "a", "name": "yearly", "trigger": "0 1 2 9 *", "timezone": "America/New_York", "repo": repo}
    # 01:00 New York on Sep 2 is exactly the proposed 05:00 UTC.
    assert firing_times(yearly, proposed) == ["2026-09-02T01:00:00-04:00"]

    # Ten minutes out is a conflict; twenty is not.
    near = dict(yearly, id="b", trigger="10 1 2 9 *")
    far = dict(yearly, id="c", trigger="25 1 2 9 *")
    assert firing_times(near, proposed) and not firing_times(far, proposed)

    # A daily preset needs its `--time`, and resolves in its own timezone.
    daily = {"id": "d", "name": "daily", "trigger": "daily", "time": "1:05", "timezone": "America/New_York", "repo": repo}
    assert firing_times(daily, proposed) == ["2026-09-02T01:05:00-04:00"]
    assert trigger_to_cron(dict(daily, time=None)) is None
    assert trigger_to_cron({"trigger": "hourly"}) == "0 * * * *"

    # Sep 2 2026 is a Wednesday, so `weekdays` fires and a Sunday-only cron does not.
    assert firing_times(dict(daily, id="e", trigger="weekdays"), proposed)
    assert not firing_times(dict(yearly, id="f", trigger="5 1 * * 0"), proposed)

    # Both day fields restricted means either may match.
    assert cron_matches(parse_cron("0 1 2 9 0"), datetime(2026, 9, 2, 1, 0))
    assert parse_cron("*/30 * * * *")[0] == {0, 30}
    assert parse_cron("0 9-17 * * *")[1] == set(range(9, 18))

    # Another repo's automation is out of scope; one naming no repo is kept.
    assert not on_repo(dict(yearly, repo="/repos/other"), repo)
    assert on_repo({"trigger": "hourly"}, repo)
    assert on_repo({"repo": {"path": repo, "name": "skills-build"}}, repo)

    # An RRULE is reported, never assumed clear.
    report = check(proposed, repo, [yearly, far, {"id": "g", "trigger": "FREQ=DAILY;COUNT=1", "repo": repo}])
    assert [c["id"] for c in report["conflicts"]] == ["a"]
    assert [u["id"] for u in report["unresolved"]] == ["g"]
    assert report["windowMinutes"] == 15

    # The list envelope is unwrapped, empty or not.
    assert _automations({"ok": True, "result": {"automations": [yearly], "items": []}}) == [yearly]
    assert _automations({"ok": True, "result": {"automations": [], "items": []}}) == []

    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        demo()
        sys.exit(0)
    if not args:
        print("FAIL: usage: check_conflicts.py <ISO datetime> [--repo <path>] [--window-minutes 15]")
        sys.exit(1)
    try:
        proposed = datetime.fromisoformat(args[0])
    except ValueError:
        print(f"FAIL: {args[0]!r} is not an ISO 8601 datetime")
        sys.exit(1)
    if proposed.tzinfo is None:
        proposed = proposed.replace(tzinfo=timezone.utc)
    rest = args[1:]
    repo = rest[rest.index("--repo") + 1] if "--repo" in rest else _git_root()
    window = int(rest[rest.index("--window-minutes") + 1]) if "--window-minutes" in rest else WINDOW_MINUTES
    try:
        automations = _list_automations()
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"FAIL: could not read `orca automations list --json`: {e}")
        sys.exit(1)
    json.dump(check(proposed, repo, automations, window), sys.stdout, indent=2)
    print()
