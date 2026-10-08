"""Resolve a concrete local time into the cron expression a Scheduled Prompt fires on.

`orca automations create --trigger` has no one-shot form, so a one-shot Scheduled
Prompt is the narrowest cron containing the wanted moment plus a precheck
Once-Guard (see `docs/adr/0007-one-shot-schedules-use-cron-plus-a-once-guard.md`).
This script owns the time half: local wall clock in an IANA timezone -> the
5-field cron expression, plus the resolved local and UTC instants.

The interview turns a Time Phrase into a concrete local datetime; this script
takes it from there and refuses to guess across a DST transition:

- A local time inside the spring-forward gap does not exist. It is a `FAIL`.
- A local time inside the fall-back overlap happens twice. It is a `FAIL` that
  names both UTC instants, so the interview can ask which one was meant.

Usage:
    python3 resolve_schedule.py "2026-09-02 01:00" America/New_York
    python3 resolve_schedule.py --demo

Accepted datetime forms: `YYYY-MM-DD HH:MM` (or `T` separator, optional
seconds) and `YYYY-MM-DD h:MM am|pm`. Every problem prints as its own `FAIL:`
line and the exit code is 1 when there is any.
"""
import json
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

AMPM = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?$", re.I)


def parse_local(phrase):
    """Return a naive `datetime` for `phrase`. Raises `ValueError` when it is not a concrete time."""
    text = " ".join(phrase.split())
    match = AMPM.match(text)
    if match:
        date, hour, minute, half = match.groups()
        hour = int(hour)
        if not 1 <= hour <= 12:
            raise ValueError(f"{phrase!r} has a 12-hour clock hour outside 1-12")
        hour = hour % 12 + (12 if half.lower() == "p" else 0)
        text = f"{date}T{hour:02d}:{minute or '00'}"
    if ":" not in text:
        # A bare date is a day, not a moment; the interview has to settle the clock time.
        raise ValueError(f"{phrase!r} names a date but no time of day")
    try:
        return datetime.fromisoformat(text.replace(" ", "T"))
    except ValueError:
        raise ValueError(
            f"{phrase!r} is not a concrete local time; use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD h:MM am|pm'"
        )


def _nonexistent(naive, tz):
    """True when `naive` falls in a spring-forward gap: the zone maps it to a different wall clock."""
    local = naive.replace(tzinfo=tz)
    return local.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != naive


def _ambiguous(naive, tz):
    """True when `naive` falls in a fall-back overlap: the two folds have different offsets."""
    return naive.replace(tzinfo=tz, fold=0).utcoffset() != naive.replace(tzinfo=tz, fold=1).utcoffset()


def resolve(phrase, tz_name):
    """Return the schedule dict for `phrase` in `tz_name`. Raises `ValueError` listing every problem."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError([f"{tz_name!r} is not an IANA timezone"])

    naive = parse_local(phrase)

    if _nonexistent(naive, tz):
        raise ValueError([
            f"{naive.isoformat()} does not exist in {tz_name}: it is inside the DST spring-forward gap. "
            "Pick a time before or after the gap."
        ])
    if _ambiguous(naive, tz):
        first = naive.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
        second = naive.replace(tzinfo=tz, fold=1).astimezone(timezone.utc)
        raise ValueError([
            f"{naive.isoformat()} happens twice in {tz_name}: it is inside the DST fall-back overlap. "
            f"It is either {first.isoformat()} or {second.isoformat()} UTC. Say which one."
        ])

    local = naive.replace(tzinfo=tz)
    return {
        "cron": f"{naive.minute} {naive.hour} {naive.day} {naive.month} *",
        "timezone": tz_name,
        "local": local.isoformat(),
        "utc": local.astimezone(timezone.utc).isoformat(),
    }


def demo():
    ny = "America/New_York"

    assert resolve("2026-09-02 01:00", ny) == {
        "cron": "0 1 2 9 *",
        "timezone": ny,
        "local": "2026-09-02T01:00:00-04:00",
        "utc": "2026-09-02T05:00:00+00:00",
    }

    # The same instant, written every accepted way.
    for phrase in ("2026-09-02T01:00", "2026-09-02 01:00:00", "2026-09-02 1:00 AM", "2026-09-02 1am"):
        assert resolve(phrase, ny)["utc"] == "2026-09-02T05:00:00+00:00", phrase

    # UTC is a real offset conversion, not a copy of the local clock.
    assert resolve("2026-01-15 23:30", ny)["utc"] == "2026-01-16T04:30:00+00:00"
    assert resolve("2026-01-15 23:30", "UTC")["cron"] == "30 23 15 1 *"

    # 2026-03-08 02:30 New York is skipped by spring forward.
    try:
        resolve("2026-03-08 02:30", ny)
        raise AssertionError("the spring-forward gap was accepted")
    except ValueError as e:
        assert "does not exist" in e.args[0][0]

    # 2026-11-01 01:30 New York happens twice; both instants are named.
    try:
        resolve("2026-11-01 01:30", ny)
        raise AssertionError("the fall-back overlap was accepted")
    except ValueError as e:
        assert "happens twice" in e.args[0][0]
        assert "2026-11-01T05:30:00+00:00" in e.args[0][0]
        assert "2026-11-01T06:30:00+00:00" in e.args[0][0]

    # An hour either side of that overlap is unambiguous and still resolves.
    assert resolve("2026-11-01 00:30", ny)["utc"] == "2026-11-01T04:30:00+00:00"
    assert resolve("2026-11-01 02:30", ny)["utc"] == "2026-11-01T07:30:00+00:00"

    for bad in ("next tuesday", "2026-09-02", "2026-09-02 13:00 pm"):
        try:
            resolve(bad, ny)
            raise AssertionError(f"{bad!r} was accepted as a concrete time")
        except ValueError:
            pass

    try:
        resolve("2026-09-02 01:00", "EST5EDT/nope")
        raise AssertionError("a bogus timezone was accepted")
    except ValueError as e:
        assert "IANA timezone" in e.args[0][0]

    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        demo()
    elif len(args) != 2:
        print("FAIL: usage: resolve_schedule.py '<local datetime>' <IANA timezone>")
        sys.exit(1)
    else:
        try:
            schedule = resolve(args[0], args[1])
        except ValueError as e:
            problems = e.args[0] if isinstance(e.args[0], list) else [str(e)]
            for problem in problems:
                print(f"FAIL: {problem}")
            sys.exit(1)
        json.dump(schedule, sys.stdout, indent=2)
        print()
