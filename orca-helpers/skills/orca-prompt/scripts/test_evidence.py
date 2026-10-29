#!/usr/bin/env python3
"""Self-check for evidence.py. Run: python3 test_evidence.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence.py")
SHA = "abc123"


def setup(root, command):
    """A workstream with `command` as evidenceCommand, a worktree dir, and a `git` stub on PATH."""
    root = Path(root)
    ws, worktree, bin = root / "ws", root / "wt", root / "bin"
    for d in (ws, worktree, bin):
        d.mkdir()
    (ws / "_config.json").write_text(json.dumps({"evidenceCommand": command}))
    git = bin / "git"
    git.write_text(f'#!/bin/sh\n[ -f "{root}/git-fails" ] && {{ echo "not a repo" >&2; exit 128; }}\necho {SHA}\n')
    git.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin}{os.pathsep}{os.environ['PATH']}"}
    return ws, worktree, lambda *a: subprocess.run([sys.executable, SCRIPT, *a], capture_output=True, text=True, env=env)


def test_runs_the_command_in_the_worktree_and_writes_the_record():
    with tempfile.TemporaryDirectory() as root:
        ws, wt, run = setup(root, "pwd; echo boom >&2; exit 3")
        r = run(str(ws), "01-a", str(wt))
        record = ws / "_reviews" / f"01-a.{SHA}.evidence.md"
        assert r.returncode == 0 and r.stdout.strip() == str(record), r.stdout
        text = record.read_text()
        assert text.startswith(f"Evidence Record, commit {SHA}, exit 3\n"), text
        assert str(wt.resolve()) in text and "boom" in text, text


def test_skips_when_the_record_for_this_sha_exists():
    with tempfile.TemporaryDirectory() as root:
        ws, wt, run = setup(root, "touch ran")
        run(str(ws), "01-a", str(wt))
        (wt / "ran").unlink()
        r = run(str(ws), "01-a", str(wt))
        assert r.returncode == 0 and r.stdout.startswith("skip:") and "exists" in r.stdout, r.stdout
        assert not (wt / "ran").exists()


def test_null_command_skips():
    for command in (None, ""):
        with tempfile.TemporaryDirectory() as root:
            ws, wt, run = setup(root, command)
            r = run(str(ws), "01-a", str(wt))
            assert (r.returncode, r.stdout) == (0, "skip: no evidenceCommand\n"), (command, r.stdout)
            assert not (ws / "_reviews").exists()


def test_bad_input_fails_once():
    with tempfile.TemporaryDirectory() as root:
        ws, wt, run = setup(root, "true")
        (Path(root) / "git-fails").write_text("")
        for args in ((str(ws), "01-a", str(wt)), (str(ws), "01-a"), (str(Path(root) / "nope"), "01-a", str(wt))):
            r = run(*args)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:") and r.stdout.count("\n") == 1, (args, r.stdout)
        assert not (ws / "_reviews").exists()


def test_non_object_config_fails_once():
    with tempfile.TemporaryDirectory() as root:
        ws, wt, run = setup(root, "true")
        (ws / "_config.json").write_text("[]")
        r = run(str(ws), "01-a", str(wt))
        assert r.returncode == 1 and r.stdout.startswith("FAIL:") and r.stdout.count("\n") == 1, r.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
