#!/usr/bin/env python3
"""Self-check for schedule.py with stub `orca` and `git`. Run: python3 test_schedule.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

STUB = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
if os.path.basename(sys.argv[0]) == "git":
    print(os.environ["STUB_REPO"])
elif sys.argv[1:4] == ["automations", "create", "--help"]:
    print("  --extra-agent-args=<args> Extra agent arguments for fresh runs")
elif sys.argv[1:3] == ["automations", "create"] and os.environ.get("STUB_NO_ID"):
    print(json.dumps({"id": "request-1", "ok": True, "result": {"created": True}}))
elif sys.argv[1:3] == ["automations", "create"]:
    print(json.dumps({"id": "request-1", "ok": True, "result": {"automation": {"id": "auto-1"}}}))
elif sys.argv[1:3] == ["automations", "list"]:
    print(json.dumps({"ok": True, "result": {"automations": [
        {"id": "old-1", "name": "ws orchestration", "trigger": "0 5 3 9 *"},
        {"id": "auto-2", "name": "ws orchestration", "trigger": "0 5 2 9 *"}]}}))
elif sys.argv[1:3] == ["automations", "edit"] and os.environ.get("STUB_FAIL_EDIT"):
    print("edit refused", file=sys.stderr)
    sys.exit(3)
"""

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    for name in ("orca", "git"):
        (bin_dir / name).write_text(STUB)
        (bin_dir / name).chmod(0o755)
    workstream = tmp / "repo" / ".orca" / "prompts" / "ws"
    workstream.mkdir(parents=True)
    (workstream / "_config.json").write_text(json.dumps({
        "targetBranch": "main",
        "mainOrchestratorHarness": "claude",
        "harnesses": [{"name": "claude", "cli": "claude", "models": {
            "mainOrchestrator": {"model": "claude-opus-5-5", "effort": "medium"}}}],
    }))
    log = tmp / "log"
    os.environ.update(
        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        ORCA_CLI_COMMAND=str(bin_dir / "orca"),
        STUB_LOG=str(log),
        STUB_REPO=str(tmp / "repo"),
    )
    import schedule

    def calls():
        lines = log.read_text().splitlines() if log.exists() else []
        log.write_text("")
        return [json.loads(line)[1:] for line in lines if "orca" in json.loads(line)[0]]

    # Success: create with the Execute line, then edit in the wrapper and the self-removing prompt.
    assert schedule.main([str(workstream), "--utc", "2026-09-02T05:00:00+00:00", "--tz", "America/New_York"]) == 0
    help_call, create, edit = calls()
    assert help_call == ["automations", "create", "--help"]
    assert create[create.index("--trigger") + 1] == "0 1 2 9 *"
    assert create[create.index("--provider") + 1] == "claude"
    assert create[create.index("--repo") + 1] == f"path:{tmp / 'repo'}"
    assert "--extra-agent-args=--model claude-opus-5-5 --effort medium" in create
    assert "--disabled" not in create and create[-1] == "--json"
    wrapper = workstream.resolve() / ".scheduled" / "auto-1-precheck.sh"
    assert edit[:5] == ["automations", "edit", "auto-1", "--precheck", str(wrapper)] and wrapper.exists()
    prompt = edit[edit.index("--prompt") + 1]
    assert prompt.startswith(f"Before beginning, remove this automation: `{bin_dir / 'orca'} automations remove auto-1`.")
    assert prompt.endswith(f"Execute {workstream.resolve()}/_orchestration.prompt.md")

    # --disabled reaches create; a Precondition lands in the wrapper.
    assert schedule.main([str(workstream), "--utc", "2026-09-02T05:00:00Z", "--tz", "UTC", "--disabled",
                          "--precondition", "gh pr view 1"]) == 0
    create = calls()[1]
    assert "--disabled" in create and create[create.index("--trigger") + 1] == "0 5 2 9 *"
    assert "gh pr view 1" in wrapper.read_text()

    # A failed edit removes the automation again, so no yearly automation stays behind.
    os.environ["STUB_FAIL_EDIT"] = "1"
    assert schedule.main([str(workstream), "--utc", "2026-09-02T05:00:00Z", "--tz", "UTC"]) == 1
    assert calls()[-1] == ["automations", "remove", "auto-1", "--json"]
    assert not wrapper.exists()
    del os.environ["STUB_FAIL_EDIT"]

    # A create that exits 0 without an id still made an automation: find it by name and cron, remove it.
    os.environ["STUB_NO_ID"] = "1"
    assert schedule.main([str(workstream), "--utc", "2026-09-02T05:00:00Z", "--tz", "UTC"]) == 1
    assert calls()[-2:] == [["automations", "list", "--json"], ["automations", "remove", "auto-2", "--json"]]
    del os.environ["STUB_NO_ID"]

    # A bad timezone fails before anything is created.
    assert schedule.main([str(workstream), "--utc", "2026-09-02T05:00:00Z", "--tz", "EDT/nope"]) == 1
    assert calls() == []

print("ok")
