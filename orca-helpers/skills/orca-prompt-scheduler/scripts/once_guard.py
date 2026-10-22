"""Let a one-shot Scheduled Prompt run exactly once, then delete itself.

A one-shot Scheduled Prompt is the narrowest cron containing the wanted moment,
so it would fire again next year. Orca runs `--precheck` before each scheduled
run and records a skipped run on a non-zero exit, so the guard lives there: the
first invocation writes a marker and exits 0, and every later invocation runs
`orca automations remove <id>` and exits non-zero. So does a run more than a
day past `<utc>` (the resolved fire instant): a run missed while the machine slept
would otherwise fire a year later. A run more than a day before `<utc>` fails
without removing the automation or writing the marker: a time over a year out
makes the yearly cron fire early, and it must fire again on the right date. Enforcement sits outside the
agent — see `docs/adr/0007-one-shot-schedules-use-cron-plus-a-once-guard.md`.

Orca accepts exactly one precheck command, so a user-supplied Precondition
cannot be passed separately. `--write-wrapper` emits the one wrapper script the
automation's `--precheck` points at: Once-Guard first, Precondition second, and
both must exit 0.

Usage:
    python3 once_guard.py <automation-id> <marker-path> <utc>
    python3 once_guard.py --write-wrapper <wrapper-path> <automation-id> <marker-path> <utc> [precondition]
    python3 once_guard.py --demo

The marker's parent directories are created as needed, and the marker is
created exclusively, so two runs racing the same marker cannot both pass.
"""
import os
import stat
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WRAPPER_TEMPLATE = """#!/bin/sh
# Precheck for Orca automation {automation_id}. Both halves must exit 0.
set -e
{python} {guard} {automation_id} {marker} {fire_utc}
{precondition}
"""


def guard(automation_id, marker_path, fire_utc, runner=subprocess.run, now=None):
    """Return True on the first call for `marker_path`; otherwise remove the automation and return False.

    A run more than a day before `fire_utc` is a yearly cron firing early: return False, keeping the automation and writing no marker.

    A run more than a day past `fire_utc` (ISO 8601) is a yearly re-fire of a missed run: stale, so removed too.
    """
    late = (now or datetime.now(timezone.utc)) - datetime.fromisoformat(fire_utc)
    if late < -timedelta(days=1):
        return False
    if late > timedelta(days=1):
        runner(["orca", "automations", "remove", automation_id], check=False)
        return False
    marker = Path(marker_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(marker, "x") as handle:
            handle.write(f"{automation_id} ran at {datetime.now(timezone.utc).isoformat()}\n")
    except FileExistsError:
        # Best effort: a failed removal still blocks this run, and the next run tries again.
        runner(["orca", "automations", "remove", automation_id], check=False)
        return False
    return True


def write_wrapper(wrapper_path, automation_id, marker_path, fire_utc, precondition=""):
    """Write the executable precheck wrapper composing the Once-Guard and the user's Precondition."""
    wrapper = Path(wrapper_path)
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        WRAPPER_TEMPLATE.format(
            automation_id=shlex.quote(automation_id),
            python="python3",
            guard=shlex.quote(str(Path(__file__).resolve())),
            marker=shlex.quote(str(Path(marker_path).resolve())),
            fire_utc=shlex.quote(fire_utc),
            precondition=precondition.strip() or "# no Precondition configured",
        )
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return wrapper


def demo():
    import tempfile

    calls = []
    FIRE = "2026-09-02T05:00:00+00:00"
    NOW = datetime(2026, 9, 2, 5, 1, tzinfo=timezone.utc)

    def fake_run(argv, check=False):
        calls.append(argv)

    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "nested" / "dir" / "once.marker"

        # First run passes and leaves the marker; nothing is removed.
        assert guard("auto-1", marker, FIRE, fake_run, NOW) is True
        assert marker.exists()
        assert calls == []

        # Every later run fails and asks Orca to remove the automation.
        assert guard("auto-1", marker, FIRE, fake_run, NOW) is False
        assert guard("auto-1", marker, FIRE, fake_run, NOW) is False
        assert calls == [["orca", "automations", "remove", "auto-1"]] * 2

        # A different automation has its own marker, so it still gets its one run.
        other = Path(tmp) / "other.marker"
        assert guard("auto-2", other, FIRE, fake_run, NOW) is True

        # A run a year late is stale: the automation is removed, the run fails, no marker is left.
        calls.clear()
        late = Path(tmp) / "late.marker"
        assert guard("auto-3", late, FIRE, fake_run, datetime(2027, 9, 2, 5, 0, tzinfo=timezone.utc)) is False
        assert calls == [["orca", "automations", "remove", "auto-3"]] and not late.exists()

        # A run over a day early (a yearly cron firing a year ahead) fails but keeps the automation and writes no marker.
        calls.clear()
        early = Path(tmp) / "early.marker"
        assert guard("auto-4", early, FIRE, fake_run, datetime(2025, 9, 2, 5, 0, tzinfo=timezone.utc)) is False
        assert calls == [] and not early.exists()

        # The wrapper runs the guard first and the Precondition second, and is executable.
        wrapper = write_wrapper(Path(tmp) / "precheck.sh", "auto-1", marker, FIRE, "test -f /etc/hosts")
        body = wrapper.read_text()
        assert body.startswith("#!/bin/sh")
        assert "set -e" in body
        assert body.index("once_guard.py") < body.index("test -f /etc/hosts")
        assert os.access(wrapper, os.X_OK)
        assert "python3 " in body and sys.executable not in body

        # A path with a space is quoted so the shell sees one argument.
        spaced = write_wrapper(Path(tmp) / "p.sh", "auto-1", Path(tmp) / "a dir" / "m", FIRE)
        assert shlex.quote(str(Path(tmp, "a dir", "m").resolve())) in spaced.read_text()

        # No Precondition still produces a valid single-command wrapper.
        bare = write_wrapper(Path(tmp) / "bare.sh", "auto-2", other, FIRE).read_text()
        assert "no Precondition configured" in bare

    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        demo()
    elif args and args[0] == "--write-wrapper":
        if len(args) not in (5, 6):
            print("FAIL: usage: once_guard.py --write-wrapper <wrapper-path> <automation-id> <marker-path> <utc> [precondition]")
            sys.exit(1)
        print(f"ok: wrote {write_wrapper(args[1], args[2], args[3], args[4], args[5] if len(args) == 6 else '')}")
    elif len(args) != 3:
        print("FAIL: usage: once_guard.py <automation-id> <marker-path> <utc>")
        sys.exit(1)
    elif guard(args[0], args[1], args[2]):
        print(f"ok: first run of {args[0]}")
    else:
        print(f"FAIL: {args[0]} has already run or is stale; removing the automation and skipping this run")
        sys.exit(1)
