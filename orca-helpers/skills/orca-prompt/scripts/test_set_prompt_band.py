#!/usr/bin/env python3
"""Self-check for set_prompt_band.py. Run: python3 test_set_prompt_band.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "set_prompt_band.py")
STEP_KEYS = {"id", "title", "state", "answers"}


def run(d, *args):
    return subprocess.run([sys.executable, SCRIPT, str(d), *args], capture_output=True, text=True)


def ok(d, *args):
    r = run(d, *args)
    assert r.returncode == 0, (args, r.stdout)
    band = json.loads((Path(d) / "_prompt-band.json").read_text())
    assert set(band) == {"step", "ended", "updatedAt", "steps", "checklist"}, band
    assert [s["id"] for s in band["steps"]] == ["basics", "harness", "models", "timing", "write-validate"]
    assert all(set(s) == STEP_KEYS for s in band["steps"])
    assert sum(s["state"] == "active" for s in band["steps"]) <= 1
    assert [p.name for p in Path(d).iterdir() if p.name.endswith(".tmp")] == []
    return band


def states(band):
    return [s["state"] for s in band["steps"]]


def test_full_interview_in_order():
    with tempfile.TemporaryDirectory() as root:
        d = Path(root) / ".orca" / "prompts"
        band = ok(d, "begin")
        assert band["step"] is None and band["ended"] is False
        assert states(band) == ["upcoming"] * 5

        ok(d, "start", "basics")
        ok(d, "answer", "basics", "workstream", "demo")
        ok(d, "answer", "basics", "tickets", "false")
        band = ok(d, "done", "basics")
        assert band["step"] == "basics" and states(band)[0] == "complete"
        assert band["steps"][0]["answers"] == {"workstream": "demo", "tickets": False}

        ok(d, "start", "harness")
        ok(d, "answer", "harness", "harnesses", '[{"name": "claude", "tier": "standard"}]')
        ok(d, "done", "harness")
        ok(d, "start", "models")
        ok(d, "answer", "models", "maxConcurrency", "16")
        ok(d, "done", "models")
        ok(d, "start", "timing")
        ok(d, "answer", "timing", "taskTime", "medium")
        ok(d, "answer", "timing", "mode", "now")
        ok(d, "done", "timing")

        band = ok(d, "start", "write-validate")
        assert band["step"] == "write-validate"
        assert states(band) == ["complete"] * 4 + ["active"]
        for item in ("scope", "plan-config", "sizes", "scaffold", "validate"):
            band = ok(d, "tick", item)
        assert all(i["done"] for i in band["checklist"])
        ok(d, "done", "write-validate")
        band = ok(d, "end")
        assert band["ended"] is True and states(band) == ["complete"] * 5
        assert band["steps"][2]["answers"] == {"maxConcurrency": 16}
        assert band["steps"][3]["answers"] == {"taskTime": "medium", "mode": "now"}


def test_stored_settings_kept_fills_and_ticks_both_steps():
    with tempfile.TemporaryDirectory() as d:
        ok(d, "begin")
        ok(d, "start", "harness")
        ok(d, "answer", "models", "modelSet", "opinionated")
        ok(d, "done", "harness")
        band = ok(d, "done", "models")
        assert states(band)[1:3] == ["complete", "complete"]
        assert band["steps"][2]["answers"] == {"modelSet": "opinionated"}


def test_answers_records_several_at_once():
    with tempfile.TemporaryDirectory() as d:
        ok(d, "begin")
        ok(d, "answer", "basics", "workstream", "demo")
        band = ok(d, "answers", "basics", '{"targetBranch": "main", "tickets": false, "integration": "pr-merge"}')
        assert band["steps"][0]["answers"] == {"workstream": "demo", "targetBranch": "main", "tickets": False, "integration": "pr-merge"}
        before = (Path(d) / "_prompt-band.json").read_bytes()
        # One unknown key records none of them.
        for bad in ('{"targetBranch": "dev", "colour": "x"}', "{}", "[1]", "not json"):
            r = run(d, "answers", "basics", bad)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:"), (bad, r.stdout)
        assert (Path(d) / "_prompt-band.json").read_bytes() == before


def test_start_finishes_the_step_left_behind():
    with tempfile.TemporaryDirectory() as d:
        ok(d, "begin")
        ok(d, "start", "basics")
        band = ok(d, "start", "harness")
        assert states(band)[:2] == ["complete", "active"]


def test_bad_input_fails_and_leaves_file_untouched():
    with tempfile.TemporaryDirectory() as d:
        ok(d, "begin")
        before = (Path(d) / "_prompt-band.json").read_bytes()
        for args in (("start", "scope"), ("answer", "basics", "colour", "x"), ("answer", "basics", "workstream"),
                     ("tick", "deploy"), ("done",), ("bogus",)):
            r = run(d, *args)
            assert r.returncode != 0, args
            assert r.stdout.startswith("FAIL:"), (args, r.stdout)
        assert (Path(d) / "_prompt-band.json").read_bytes() == before


def test_calls_before_begin_fail():
    with tempfile.TemporaryDirectory() as d:
        r = run(d, "start", "basics")
        assert r.returncode != 0 and "run begin first" in r.stdout
        assert not (Path(d) / "_prompt-band.json").exists()


def test_begin_writes_the_owner_from_the_session_env():
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, "CLAUDE_CODE_SESSION_ID": "session-a"}
        assert subprocess.run([sys.executable, SCRIPT, d, "begin"], env=env).returncode == 0
        assert (Path(d) / "_prompt-band.json.owner").read_text() == "session-a"


if __name__ == "__main__":
    test_full_interview_in_order()
    test_stored_settings_kept_fills_and_ticks_both_steps()
    test_answers_records_several_at_once()
    test_start_finishes_the_step_left_behind()
    test_bad_input_fails_and_leaves_file_untouched()
    test_calls_before_begin_fail()
    test_begin_writes_the_owner_from_the_session_env()
    print("ok")
