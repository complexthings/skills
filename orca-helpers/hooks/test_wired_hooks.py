#!/usr/bin/env python3
"""Self-check for recall_hook.py, prompt_gate.py's tick, scaffold_hook.py and workstream_hook.py. Run: python3 test_wired_hooks.py"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompt_gate  # noqa: E402
import recall_hook  # noqa: E402
import scaffold_hook  # noqa: E402
import workstream_hook  # noqa: E402

KB = HERE.parent / "skills" / "orca-kb" / "scripts" / "kb.py"
EXTRACTION = {
    "nodes": [{"name": "Wave Band", "type": "SYSTEM", "description": "Draws each Work Item's progress"},
              {"name": "Status File", "type": "DOCUMENT", "description": "_status.json"}],
    "edges": [{"source": "Wave Band", "predicate": "depends_on", "target": "Status File"}],
    "aliases": [{"entity": "Wave Band", "alias": "band"}],
}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def hook(home, event):
    r = subprocess.run([sys.executable, str(HERE / "recall_hook.py")], input=json.dumps(event),
                       capture_output=True, text=True, env=dict(os.environ, HOME=str(home)))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout else None


def prompt(repo, text):
    return {"hook_event_name": "UserPromptSubmit", "cwd": str(repo), "prompt": text}


def subagent(repo):
    return {"hook_event_name": "SubagentStart", "cwd": str(repo), "agent_type": "general-purpose"}


def status(repo, ws, active):
    d = repo / ".orca" / "prompts" / ws
    d.mkdir(parents=True, exist_ok=True)
    (d / "_status.json").write_text(json.dumps({"workstream": ws, "active": active}))


def band(repo, ended, minutes_ago):
    d = repo / ".orca" / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    at = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    (d / "_prompt-band.json").write_text(json.dumps({"ended": ended, "updatedAt": at}))


def test_recall():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = Path(tmp) / "home", Path(tmp) / "repo"
        repo.mkdir()
        # A real repo with an origin, so a worktree keys the same store (kb.repo_key).
        git(repo, "init", "-q")
        git(repo, "remote", "add", "origin", "git@github.com:o/r.git")
        git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
        subprocess.run([sys.executable, str(KB), "--repo", str(repo), "update", "wave-band",
                        "--page", "# Wave Band", "--extraction", json.dumps(EXTRACTION)],
                       check=True, capture_output=True, env=dict(os.environ, HOME=str(home)))

        # Outside orca work: silent, whatever the prompt names.
        for text in ("fix the Wave Band", "", "/orcas band", "orca-prompt band"):
            assert hook(home, prompt(repo, text)) is None, text
        assert hook(home, subagent(repo)) is None

        # An orca skill prompt recalls; the smallest one with no match still injects the block.
        out = hook(home, prompt(repo, "/orca-prompt fix the band"))
        assert out.startswith("Orca Knowledge Graph recall") and "Wave Band --[depends_on]--> Status File" in out, out
        assert "no memory matches" in hook(home, prompt(repo, "/orca-kb"))
        assert "Wave Band" in hook(home, prompt(repo, "/orca-helpers:orca-execute band"))
        assert "Wave Band" in hook(home, prompt(repo, "Execute .orca/prompts/x/01-band.prompt.md"))
        # The review loop's tick is prompt_gate.py's: no recall.
        assert hook(home, prompt(repo, "/orca-pr-review tick")) is None

        # An open Prompt Band interview counts; an ended or stale one does not.
        band(repo, ended=False, minutes_ago=1)
        assert "Wave Band" in hook(home, prompt(repo, "the band"))
        band(repo, ended=True, minutes_ago=1)
        assert hook(home, prompt(repo, "the band")) is None
        band(repo, ended=False, minutes_ago=31)
        assert hook(home, prompt(repo, "the band")) is None

        # An inactive or malformed _status.json is not orca work; an active one is, and a
        # SubagentStart, which carries no prompt, seeds on the Workstream name.
        status(repo, "wave-band", active=False)
        (repo / ".orca" / "prompts" / "broken").mkdir()
        (repo / ".orca" / "prompts" / "broken" / "_status.json").write_text("[1")
        assert hook(home, prompt(repo, "the band")) is None
        status(repo, "wave-band", active=True)
        assert "Wave Band" in hook(home, prompt(repo, "hello"))
        assert "Wave Band" in hook(home, subagent(repo))
        (repo / "sub").mkdir()
        assert "Wave Band" in hook(home, subagent(repo / "sub"))

        # A worktree sees the main checkout's active Workstream.
        git(repo, "worktree", "add", "-q", str(Path(tmp) / "wt"))
        assert "Wave Band" in hook(home, subagent(Path(tmp) / "wt"))

        # No store yet: the block still arrives, with no matches.
        assert "no memory matches" in hook(Path(tmp) / "empty-home", prompt(repo, "/orca-prompt band"))

        # A corrupt graph.db: no matches, no crash.
        for db in home.rglob("graph.db"):
            db.write_bytes(b"")
        assert "no memory matches" in hook(home, prompt(repo, "/orca-prompt band"))


def test_tick():
    assert prompt_gate.gate("/orca-pr-review tick", tick=lambda: "") == {"decision": "block", "reason": "orca-pr-review: nothing new."}
    assert prompt_gate.gate(" /orca-helpers:orca-pr-review   tick\n", tick=lambda: "")["decision"] == "block"
    reply = prompt_gate.gate("/orca-pr-review tick", tick=lambda: "Review Draft ready: a/b#1")
    assert reply["hookSpecificOutput"]["additionalContext"].endswith("\nReview Draft ready: a/b#1"), reply
    for text in ("/orca-pr-review tick now", "/orca-pr-review status", "orca-pr-review tick", ""):
        assert prompt_gate.gate(text, tick=lambda: (_ for _ in ()).throw(AssertionError(text))) is None, text


def test_scaffold():
    calls = []
    scaffold_hook.run = lambda *a: calls.append([str(x) for x in a]) or "ok: workstream meets the Definition of Done"
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        ws = repo / ".orca" / "prompts" / "my ws"
        ws.mkdir(parents=True)
        (ws / "_config.json").write_text("{}")

        def event(command, stdout="Scaffolded 2 wave(s) into x"):
            return {"cwd": str(repo), "tool_input": {"command": command}, "tool_response": {"stdout": stdout, "stderr": ""}}

        # No open band: validate runs, the band is left alone.
        out = scaffold_hook.context(event("python3 /p/orca-prompt/scripts/scaffold.py '.orca/prompts/my ws/'"))
        assert out.endswith("\nok: workstream meets the Definition of Done") and len(calls) == 1, (out, calls)
        assert calls[0][1] == str(ws), calls

        band(repo, ended=False, minutes_ago=0)
        calls.clear()
        assert scaffold_hook.context(event(f'cd /x && python3 scaffold.py "{ws}" && echo done'))
        assert [c[0].rsplit("/", 1)[1] for c in calls] == ["validate.py", "set_prompt_band.py"], calls
        assert calls[1][1:] == [str(ws.parent), "tick", "scaffold"], calls

        calls.clear()
        for e in (event("python3 scaffold.py '.orca/prompts/my ws'", stdout="Traceback ..."),
                  event("python3 test_scaffold.py '.orca/prompts/my ws'"),
                  event("python3 scaffold.py .orca/prompts/missing"),
                  event("python3 scaffold.py"),
                  event("python3 scaffold.py $'my ws'"),
                  event("python3 scaffold.py '.orca/prompts/my ws"),
                  event("python3 scaffold.py \\"),
                  event("python3 scaffold.py <<'EOF'\n.orca/prompts/my ws\nEOF"),
                  {"cwd": str(repo), "tool_input": {}, "tool_response": None}):
            assert scaffold_hook.context(e) is None, e
        assert calls == [], calls


def test_workstream():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = Path(tmp) / "home", Path(tmp) / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "remote", "add", "origin", "git@github.com:o/r.git")
        ws = repo / ".orca" / "prompts" / "ws"
        ws.mkdir(parents=True)
        items = [{"id": "a", "wave": 1, "state": "complete"}, {"id": "b", "wave": 2, "state": "complete"}]
        (ws / "_status.json").write_text(json.dumps({"workstream": "ws", "active": True, "runId": "run_1", "items": items}))
        (ws / "_status.json.owner").write_text("S1\n")
        rows, prepared = [[{"dispatchId": "d1"}]], []
        workstream_hook.worker_list = lambda run_id: rows[0]
        workstream_hook.prepare = lambda d, text: prepared.append((d, text))
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)

        def run(name, session="S1", **extra):
            err, out = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = workstream_hook.main({"hook_event_name": name, "session_id": session, "cwd": str(repo), **extra})
            return code, err.getvalue(), out.getvalue()

        try:
            # Finished but not wrapped up: one line per missing piece, then the next stop passes.
            code, err, _ = run("Stop")
            assert code == 2 and len(err.strip().split("\n")) == 4, err
            assert "Wave 1 retro" in err and "Wave 2 retro" in err and "ws-lessons" in err and "1 reclaimable" in err, err
            assert run("Stop", stop_hook_active=True)[0] == 0
            # Another session, an unfinished Workstream, or an inactive one: no block.
            assert run("Stop", session="S2")[0] == 0
            (ws / "_status.json").write_text(json.dumps({"workstream": "ws", "active": True, "runId": "run_1",
                                                         "items": [*items, {"id": "c", "wave": 2, "state": "in_progress"}]}))
            assert run("Stop")[0] == 0
            (ws / "_status.json").write_text(json.dumps({"workstream": "ws", "active": False, "runId": "run_1", "items": items}))
            assert run("Stop")[0] == 0

            # Every piece present: the stop passes.
            (ws / "_status.json").write_text(json.dumps({"workstream": "ws", "active": True, "runId": "run_1", "items": items}))
            (ws / "_decisions.md").write_text("# Decision Log\n\n### 2026-10-29 · Wave 1 retro\n\n- x\n\n### 2026-10-29 · Wave 2 retro\n\n- y\n")
            pages = home / ".claude" / "orca-helpers" / "kb" / "o__r" / "pages"
            pages.mkdir(parents=True)
            (pages / "ws-lessons.md").write_text("# ws lessons")
            rows[0] = []
            assert run("Stop") == (0, "", "")
            # No runId, or a worker-list that fails, is a missing piece.
            rows[0] = None
            assert "worker-list --run run_1" in run("Stop")[1]
            (ws / "_status.json").write_text(json.dumps({"workstream": "ws", "active": True, "items": items}))
            code, err, _ = run("Stop")
            assert code == 2 and "no runId" in err, err

            # SessionStart: the Owning Session gets the paths that exist; another session nothing.
            out = json.loads(run("SessionStart", source="compact")[2])["hookSpecificOutput"]
            assert out["hookEventName"] == "SessionStart", out
            assert str(ws / "_status.json") in out["additionalContext"] and str(ws / "_decisions.md") in out["additionalContext"], out
            assert "_resume.md" not in out["additionalContext"], out
            assert run("SessionStart", session="S2")[2] == ""

            # PreCompact: prepare.py runs for the owned Workstream only.
            (ws / "_status.json").write_text(json.dumps({"workstream": "ws", "active": True, "items": [
                {"id": "a", "wave": 1, "state": "complete"}, {"id": "b", "wave": 2, "state": "in_progress"},
                {"id": "c", "wave": 2, "state": "reviewing"}, {"id": "d", "wave": 3, "state": "todo"}]}))
            run("PreCompact", session="S2")
            assert prepared == []
            run("PreCompact")
            assert prepared == [(ws.resolve(), "Wave 2 of 3: 1 of 4 complete; in progress: b, c")], prepared
            assert workstream_hook.summary({"items": items}) == "Wave 2 of 2: 2 of 2 complete"
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


def test_hostile_stdin():
    """Each hook runs on every prompt or Bash call: any stdin exits 0, and outside orca work prints nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        for script in ("prompt_gate.py", "recall_hook.py", "scaffold_hook.py", "workstream_hook.py"):
            for stdin in ("", "not json", "[1]", "null", "{", '{"prompt": 5, "cwd": 7}', '{"tool_input": "x", "tool_response": 3}',
                          json.dumps({"cwd": tmp, "prompt": "hi", "tool_input": {"command": "python3 scaffold.py $'my ws'"},
                                      "tool_response": {"stdout": "Scaffolded 1 wave(s) into my"}}),
                          "\udcff\x00"):
                r = subprocess.run([sys.executable, str(HERE / script)], input=stdin.encode("utf-8", "surrogateescape"),
                                   capture_output=True, cwd=tmp, env=dict(os.environ, HOME=tmp))
                assert (r.returncode, r.stdout) == (0, b""), (script, stdin, r)


def test_eval_copies():
    """Evals quote the hook markers and a SKILL.md step; keep them in step with the source."""
    root = HERE.parent
    for case, skill in (("orca-prompt-hook-validated", "orca-prompt"), ("orca-pr-review-tick-hook-ran", "orca-pr-review"),
                        ("orca-pr-review-tick-haiku-fallback", "orca-pr-review"),
                        ("orca-pr-review-feedback", "orca-pr-review")):
        step = (root / "evals" / case / "prompt.md").read_text().split("<!-- STEP START -->\n")[1].split("<!-- STEP END -->")[0]
        assert step.strip() in (root / "skills" / skill / "SKILL.md").read_text(), case
    assert scaffold_hook.HEADER in (root / "evals" / "orca-prompt-hook-validated" / "prompt.md").read_text()
    assert prompt_gate.TICK_HEADER in (root / "evals" / "orca-pr-review-tick-hook-ran" / "prompt.md").read_text()
    for skill, marker in (("orca-pr-review", prompt_gate.TICK_HEADER.split(".")[0]), ("orca-prompt", "The orca-helpers hook already ran validate.py"),
                          ("orca-prompt", "Orca Knowledge Graph recall"), ("orca-execute", "Orca Knowledge Graph recall")):
        assert marker in (root / "skills" / skill / "SKILL.md").read_text(), (skill, marker)
    assert "Orca Knowledge Graph recall" in recall_hook.HEADER


if __name__ == "__main__":
    test_recall()
    test_tick()
    test_scaffold()
    test_workstream()
    test_hostile_stdin()
    test_eval_copies()
    print("ok")
