#!/usr/bin/env python3
"""Checks the `taskTime` default and the `--read --check` stale checks of `write_settings.py`.

Run: python3 test_write_settings.py
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from write_settings import _valid_settings, read_settings, settings_problems, stale_settings

SCRIPT = Path(__file__).parent / "write_settings.py"


def write(settings, path):
    return subprocess.run([sys.executable, str(SCRIPT), str(path)], input=json.dumps(settings), capture_output=True, text=True)


def test_task_time():
    # Absent reads as the default, so settings written before the key stay valid.
    assert "taskTime" not in _valid_settings() and settings_problems(_valid_settings()) == []
    for task_time in ("low", "medium", "high", "xhigh", "ultra"):
        assert settings_problems(dict(_valid_settings(), taskTime=task_time)) == [], task_time

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "prompt-settings.json"
        r = write(dict(_valid_settings(), taskTime="xhigh"), path)
        assert (r.returncode, r.stdout) == (0, f"ok: wrote {path}\n"), r.stdout
        assert read_settings(path)["taskTime"] == "xhigh"

        # An invalid value prints one FAIL line, exits 1 and leaves the stored file alone.
        for bad in (None, "", "Medium", "max", 10, ["low"]):
            r = write(dict(_valid_settings(), taskTime=bad), path)
            assert r.returncode == 1, bad
            assert r.stdout == f"FAIL: taskTime must be one of low|medium|high|xhigh|ultra, got {bad!r}\n", r.stdout
            assert read_settings(path)["taskTime"] == "xhigh", bad


def harness(name, **models):
    slots = {"mainOrchestrator": None, "orchestrationWorker": None, "subagent": None, "subagentSimple": None}
    return {"name": name, "cli": name, "tier": "standard", "models": {**slots, **models}}


def test_stale_settings():
    installed = lambda cli: f"/bin/{cli}" if cli in ("claude", "opencode") else None
    discover = lambda name: {"gpt-6-luna"}
    settings = dict(_valid_settings(), harnesses=[
        harness("claude", mainOrchestrator="claude-opus-5.5", subagent={"model": "claude-opus-4-1", "effort": "low"}),
        harness("opencode", subagent="openai-codex/gpt-6-luna", subagentSimple="gone-model"),
        harness("pi", subagent="anything"),
    ])
    assert stale_settings(settings, installed, discover) == [
        "claude.subagent: claude-opus-4-1 is not in model-priority.json",
        "opencode.subagentSimple: gone-model is not in opencode's model list",
        "harnesses: pi is not installed",
    ], stale_settings(settings, installed, discover)
    # A CLI that cannot list its models reports nothing for its slots.
    assert stale_settings(dict(settings, harnesses=settings["harnesses"][1:2]), installed, lambda name: None) == []
    assert stale_settings(dict(_valid_settings(), priorityFile="missing.json"), installed, discover) == ["priorityFile: missing.json is not found"]


def test_read_check_cli():
    with tempfile.TemporaryDirectory() as tmp:
        # A stub `claude` on PATH stands in for the installed harness.
        stub = Path(tmp) / "claude"
        stub.write_text("#!/bin/sh\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = {**os.environ, "PATH": tmp}
        path = Path(tmp) / "prompt-settings.json"
        settings = _valid_settings()
        settings["harnesses"][0]["models"]["subagentSimple"] = "claude-opus-4-1"
        path.write_text(json.dumps(settings))
        r = subprocess.run([sys.executable, str(SCRIPT), "--read", "--check", str(path)], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stdout
        lines = [l for l in r.stdout.splitlines() if l.startswith("STALE:")]
        assert lines == ["STALE: claude.subagentSimple: claude-opus-4-1 is not in model-priority.json"], r.stdout
        # Without --check the output stays plain JSON.
        r = subprocess.run([sys.executable, str(SCRIPT), "--read", str(path)], capture_output=True, text=True, env=env)
        assert json.loads(r.stdout)["targetBranch"] == "main"


if __name__ == "__main__":
    test_task_time()
    test_stale_settings()
    test_read_check_cli()
    print("ok")
