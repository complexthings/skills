"""Let a one-shot Scheduled Prompt run exactly once, then delete itself.

A one-shot Scheduled Prompt is the narrowest cron containing the wanted moment,
so it would fire again next year. Orca runs `--precheck` before each scheduled
run and records a skipped run on a non-zero exit, so the guard lives there: the
first invocation writes a marker and exits 0, and every later invocation runs
`orca automations remove <id>` and exits non-zero. Enforcement sits outside the
agent — see `docs/adr/0007-one-shot-schedules-use-cron-plus-a-once-guard.md`.

Orca accepts exactly one precheck command, so a user-supplied Precondition
cannot be passed separately. `--write-wrapper` emits the one wrapper script the
automation's `--precheck` points at: Once-Guard first, Precondition second, and
both must exit 0.

Usage:
    python3 once_guard.py <automation-id> <marker-path>
    python3 once_guard.py --write-wrapper <wrapper-path> <automation-id> <marker-path> [precondition]
    python3 once_guard.py --demo

The marker's parent directories are created as needed, and the marker is
created exclusively, so two runs racing the same marker cannot both pass.
"""
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WRAPPER_TEMPLATE = """#!/bin/sh
# Precheck for Orca automation {automation_id}. Both halves must exit 0.
set -e
{python} {guard} {automation_id} {marker}
{precondition}
"""


def guard(automation_id, marker_path, runner=subprocess.run):
    """Return True on the first call for `marker_path`; otherwise remove the automation and return False."""
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


def write_wrapper(wrapper_path, automation_id, marker_path, precondition=""):
    """Write the executable precheck wrapper composing the Once-Guard and the user's Precondition."""
    wrapper = Path(wrapper_path)
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        WRAPPER_TEMPLATE.format(
            automation_id=automation_id,
            python=sys.executable or "python3",
            guard=Path(__file__).resolve(),
            marker=Path(marker_path).resolve(),
            precondition=precondition.strip() or "# no Precondition configured",
        )
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return wrapper


def demo():
    import tempfile

    calls = []

    def fake_run(argv, check=False):
        calls.append(argv)

    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "nested" / "dir" / "once.marker"

        # First run passes and leaves the marker; nothing is removed.
        assert guard("auto-1", marker, fake_run) is True
        assert marker.exists()
        assert calls == []

        # Every later run fails and asks Orca to remove the automation.
        assert guard("auto-1", marker, fake_run) is False
        assert guard("auto-1", marker, fake_run) is False
        assert calls == [["orca", "automations", "remove", "auto-1"]] * 2

        # A different automation has its own marker, so it still gets its one run.
        other = Path(tmp) / "other.marker"
        assert guard("auto-2", other, fake_run) is True

        # The wrapper runs the guard first and the Precondition second, and is executable.
        wrapper = write_wrapper(Path(tmp) / "precheck.sh", "auto-1", marker, "test -f /etc/hosts")
        body = wrapper.read_text()
        assert body.startswith("#!/bin/sh")
        assert "set -e" in body
        assert body.index("once_guard.py") < body.index("test -f /etc/hosts")
        assert os.access(wrapper, os.X_OK)

        # No Precondition still produces a valid single-command wrapper.
        bare = write_wrapper(Path(tmp) / "bare.sh", "auto-2", other).read_text()
        assert "no Precondition configured" in bare

    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        demo()
    elif args and args[0] == "--write-wrapper":
        if len(args) not in (4, 5):
            print("FAIL: usage: once_guard.py --write-wrapper <wrapper-path> <automation-id> <marker-path> [precondition]")
            sys.exit(1)
        print(f"ok: wrote {write_wrapper(args[1], args[2], args[3], args[4] if len(args) == 5 else '')}")
    elif len(args) != 2:
        print("FAIL: usage: once_guard.py <automation-id> <marker-path>")
        sys.exit(1)
    elif guard(args[0], args[1]):
        print(f"ok: first run of {args[0]}")
    else:
        print(f"FAIL: {args[0]} has already run; removing the automation and skipping this run")
        sys.exit(1)
