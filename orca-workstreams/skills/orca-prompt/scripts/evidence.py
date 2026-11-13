"""Write the Evidence Record for one Work Item's reviewed commit.

Usage:
    python3 evidence.py <workstream-dir> <id> <worktree>

Reads the worktree's head SHA. When `<workstream-dir>/_reviews/<id>.<sha>.evidence.md`
already exists, prints `skip: <path> exists`. Otherwise runs `evidenceCommand` from
`_config.json` in the worktree and writes that file: a first line
`Evidence Record, commit <sha>, exit <code>`, then the full output. A non-zero exit
is evidence for the reviewer, so it still exits 0 and prints the path. A null or empty
`evidenceCommand` prints `skip: no evidenceCommand` and exits 0. Any bad input
prints one `FAIL:` line and exits 1.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scaffold import write_text_atomic


class EvidenceError(Exception):
    pass


def evidence(workstream_dir, item_id, worktree):
    """Return the line to print: the record's path, or why it was skipped."""
    workstream_dir = Path(workstream_dir)
    try:
        config = json.loads((workstream_dir / "_config.json").read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise EvidenceError(f"cannot read {workstream_dir / '_config.json'}: {e}")
    if not isinstance(config, dict):
        raise EvidenceError(f"{workstream_dir / '_config.json'} is not a JSON object")
    command = config.get("evidenceCommand")
    # scaffold.py treats an empty command as no command, so skip it here too.
    if not command:
        return "skip: no evidenceCommand"
    head = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0:
        raise EvidenceError(f"git rev-parse HEAD failed in {worktree}: {head.stderr.strip()}")
    sha = head.stdout.strip()
    path = workstream_dir / "_reviews" / f"{item_id}.{sha}.evidence.md"
    if path.exists():
        return f"skip: {path} exists"
    # evidenceCommand is a shell command line from the user's own _config.json.
    out = subprocess.run(command, shell=True, cwd=worktree, capture_output=True, text=True)
    path.parent.mkdir(exist_ok=True)
    write_text_atomic(path, f"Evidence Record, commit {sha}, exit {out.returncode}\n\n{out.stdout}{out.stderr}", ".evidence-")
    return str(path)


def main(argv):
    if len(argv) != 3:
        raise EvidenceError("usage: evidence.py <workstream-dir> <id> <worktree>")
    print(evidence(*argv))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except EvidenceError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
