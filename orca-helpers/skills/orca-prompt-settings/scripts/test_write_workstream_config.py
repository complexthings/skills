#!/usr/bin/env python3
"""Self-check for write_workstream_config.py. Run: python3 test_write_workstream_config.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).with_name("write_workstream_config.py"))


def test_overrides_save_validate_and_never_touch_a_running_workstream():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        base = {"workstream": "ws", "targetBranch": "main", "mainOrchestratorHarness": "claude", "workItems": [{"id": "01"}],
                "harnesses": [{"name": "claude", "cli": "claude", "tier": "standard",
                               "models": {s: "claude-opus-5-5" for s in ("mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple")}}]}
        (ws / "_config.json").write_text(json.dumps(base))

        def run(overrides):
            r = subprocess.run([sys.executable, SCRIPT, str(ws)], input=json.dumps(overrides), capture_output=True, text=True)
            return r.returncode, r.stdout

        code, out = run({"maxConcurrency": 4, "taskTime": "high", "budgetUsd": 12.5, "review": False})
        assert code == 0, out
        saved = json.loads((ws / "_config.json").read_text())
        assert saved["maxConcurrency"] == 4 and saved["taskTime"] == "high" and saved["workItems"] == [{"id": "01"}], saved
        # Each bad value and each key outside KEYS is its own FAIL line, and nothing is written.
        code, out = run({"workItems": [], "taskTime": "slow", "maxConcurrency": 0, "budgetUsd": float("inf"),
                         "planGate": "yes", "targetBranch": "", "mainOrchestratorHarness": "codex"})
        assert code == 1 and out.count("FAIL:") == 7, out
        assert json.loads((ws / "_config.json").read_text()) == saved
        code, out = run({"harnesses": [{"name": "codex"}]})
        assert code == 1 and "harnesses[0].tier" in out and "'claude' is not one of" in out, out
        for hostile in ([], "x", None, 3):
            code, out = run(hostile)
            assert code == 1 and "overrides must be a JSON object" in out, out
        r = subprocess.run([sys.executable, SCRIPT, str(ws)], input="{not json", capture_output=True, text=True)
        assert r.returncode == 1 and r.stdout.startswith("FAIL: stdin is not valid JSON"), r.stdout
        # A running Workstream keeps its config.
        (ws / "_status.json").write_text(json.dumps({"active": True}))
        code, out = run({"maxConcurrency": 2})
        assert code == 1 and "is running" in out and json.loads((ws / "_config.json").read_text()) == saved, out
        (ws / "_status.json").write_text(json.dumps({"active": False}))
        assert run({"maxConcurrency": 2})[0] == 0
        r = subprocess.run([sys.executable, SCRIPT, str(ws / "missing")], input="{}", capture_output=True, text=True)
        assert r.returncode == 1 and "FAIL: no Workstream config" in r.stdout, r.stdout
        # Deeply nested JSON is a FAIL line, not a traceback.
        r = subprocess.run([sys.executable, SCRIPT, str(ws)], input="[" * 100000, capture_output=True, text=True)
        assert r.returncode == 1 and r.stdout.startswith("FAIL:"), (r.stdout, r.stderr[-200:])


def test_cleared_keys_are_dropped_so_the_workstream_follows_the_repo_default():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "_config.json").write_text(json.dumps({"workstream": "ws", "taskTime": "medium", "maxConcurrency": 2, "workItems": []}))

        def run(overrides, *clear):
            r = subprocess.run([sys.executable, SCRIPT, str(ws), *clear], input=json.dumps(overrides), capture_output=True, text=True)
            return r.returncode, r.stdout

        code, out = run({"maxConcurrency": 4}, "taskTime", "budgetUsd")
        assert code == 0, out
        assert json.loads((ws / "_config.json").read_text()) == {"workstream": "ws", "maxConcurrency": 4, "workItems": []}
        # A key outside KEYS, or one both set and cleared, is a FAIL and nothing is written.
        for overrides, clear in (({}, "workItems"), ({"maxConcurrency": 3}, "maxConcurrency")):
            code, out = run(overrides, clear)
            assert code == 1 and out.startswith("FAIL:"), out
        assert json.loads((ws / "_config.json").read_text())["maxConcurrency"] == 4


def test_new_writes_every_schema_key():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "demo"
        answers = {"workstream": "demo", "targetBranch": "main", "mainOrchestratorHarness": "claude", "maxConcurrency": 6,
                   "integration": "pr-merge", "tickets": False, "workItems": [{"id": "01-a", "size": "light"}],
                   "harnesses": [{"name": "claude", "cli": "claude", "tier": "standard",
                                  "models": {"mainOrchestrator": {"model": "claude-opus-5-5", "effort": "medium"},
                                             "orchestrationWorker": "claude-opus-5-5", "subagent": "claude-opus-5-5", "subagentSimple": None}}]}

        def new(answers):
            r = subprocess.run([sys.executable, SCRIPT, "--new", str(ws)], input=json.dumps(answers), capture_output=True, text=True)
            return r.returncode, r.stdout

        code, out = new(dict(answers, budgetUsd=30))
        assert (code, out) == (0, f"ok: wrote {ws / '_config.json'}\n"), out
        written = json.loads((ws / "_config.json").read_text())
        # Every key the schema names, in schema order, the Round 4 keys defaulted.
        assert list(written) == ["workstream", "targetBranch", "harnesses", "mainOrchestratorHarness", "maxConcurrency",
                                 "integration", "tickets", "review", "planGate", "evidenceCommand", "budgetUsd", "taskTime", "workItems"]
        assert {k: written[k] for k in ("review", "planGate", "evidenceCommand", "budgetUsd", "taskTime")} == \
            {"review": True, "planGate": False, "evidenceCommand": None, "budgetUsd": 30, "taskTime": "medium"}

        # Each bad answer is a FAIL line, and the written config stays as it was.
        for bad, needle in ((dict(answers, workstream="other"), "must match the directory name"),
                            ({k: v for k, v in answers.items() if k != "tickets"}, "missing required keys: ['tickets']"),
                            (dict(answers, colour="red"), "does not hold: ['colour']"),
                            (dict(answers, integration="push"), "integration must be one of"),
                            (dict(answers, workItems=[]), "workItems is empty"),
                            (dict(answers, taskTime="slow"), "taskTime must be one of"),
                            ([], "answers must be a JSON object")):
            code, out = new(bad)
            assert code == 1 and out.startswith("FAIL:") and needle in out, (needle, out)
        assert json.loads((ws / "_config.json").read_text()) == written
        # A running Workstream keeps its config.
        (ws / "_status.json").write_text(json.dumps({"active": True}))
        code, out = new(dict(answers, maxConcurrency=2))
        assert code == 1 and "is running" in out, out
        r = subprocess.run([sys.executable, SCRIPT, "--new"], input="{}", capture_output=True, text=True)
        assert r.returncode == 1 and "usage" in r.stdout, r.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
