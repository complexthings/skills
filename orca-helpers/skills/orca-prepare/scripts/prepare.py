"""Write a Workstream's Resume State, `_resume.md`, beside `_status.json`, and print the resume line.

Usage:
    python3 prepare.py <workstream-dir> <summary> [--next <what is in flight>]

`_resume.md` holds the time it was written, the one-line summary, what is in
flight, the Wave-by-Wave table from `set_status.py --show`, and the docs a
resumed Main Orchestrator reads. Each run replaces the previous file through a
temp file and a rename. On success it prints two lines:

    /orca-execute <workstream>
    <summary>

Bad input prints one `FAIL:` line, exits 1 and writes nothing. The Workstream
must have a `_status.json`, so `set_status.py --start` has run at least once.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt" / "scripts"))
from scaffold import DECISION_LOG, write_text_atomic
from set_status import STATUS_FILE, StatusError, _read_json, show

RESUME_FILE = "_resume.md"
USAGE = "usage: prepare.py <workstream-dir> <summary> [--next <what is in flight>]"
READ_ON_RESUME = ("_plan.md", "_orchestration.prompt.md", DECISION_LOG, STATUS_FILE, RESUME_FILE)


def prepare(workstream_dir, summary, next_up=None):
    """Write `_resume.md` and return the two-line resume text."""
    if not summary.strip() or "\n" in summary:
        raise StatusError("prepare needs a one-line summary")
    d = Path(workstream_dir)
    if not (d / STATUS_FILE).exists():
        raise StatusError(f"{d / STATUS_FILE} does not exist; run set_status.py {workstream_dir} --start first")
    workstream = _read_json(d / STATUS_FILE)["workstream"]
    resume_line = f"/orca-execute {workstream}"
    text = "\n".join([
        f"# Resume State: {workstream}",
        "",
        f"Prepared: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"Resume: `{resume_line}`",
        "",
        "## Summary",
        "",
        summary.strip(),
        "",
        "## In flight",
        "",
        (next_up or "Nothing in flight.").strip(),
        "",
        "## Status",
        "",
        "```",
        show(d),
        "```",
        "",
        "## Read on resume",
        "",
        *[f"- `{name}`" for name in READ_ON_RESUME],
        "",
    ])
    write_text_atomic(d / RESUME_FILE, text, ".resume-")
    return f"{resume_line}\n{summary.strip()}"


def main(argv):
    args = list(argv)
    next_up = None
    if "--next" in args:
        i = args.index("--next")
        if i + 1 >= len(args):
            raise StatusError(USAGE)
        next_up = args.pop(i + 1)
        args.pop(i)
    if len(args) != 2 or any(a.startswith("--") for a in args):
        raise StatusError(USAGE)
    print(prepare(*args, next_up=next_up))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except StatusError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
