#!/usr/bin/env python3
"""Self-check for prepare.py. Run: python3 test_prepare.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREPARE = HERE / "prepare.py"
SET_STATUS = HERE.parents[1] / "orca-prompt" / "scripts" / "set_status.py"

CONFIG = {
    "workstream": "demo",
    "workItems": [
        {"id": "01-a", "wave": 1, "title": "Alpha"},
        {"id": "02-b", "wave": 2, "title": "Bravo"},
    ],
}


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)


def started(root):
    d = Path(root) / "demo"
    d.mkdir()
    (d / "_config.json").write_text(json.dumps(CONFIG))
    assert run(SET_STATUS, d, "--start").returncode == 0
    return d


def test_prepare_then_resume():
    with tempfile.TemporaryDirectory() as root:
        d = started(root)
        run(SET_STATUS, d, "01-a", "complete")
        run(SET_STATUS, d, "log", "Wave 1 retro", "No failures.")
        assert run(SET_STATUS, d, "02-b", "in_progress").returncode == 0
        r = run(SET_STATUS, d, "log", "Bravo uses the v2 API", "v1 drops pagination.")
        assert r.returncode == 0, r.stdout
        r = run(PREPARE, d, "Wave 1 merged; Bravo is in review.", "--next", "02-b waits on its reviewer.")
        assert r.returncode == 0, r.stdout
        assert r.stdout == "/orca-execute demo\nWave 1 merged; Bravo is in review.\n"
        resume = (d / "_resume.md").read_text()
        for expected in ("Resume: `/orca-execute demo`", "Wave 1 merged; Bravo is in review.",
                         "02-b waits on its reviewer.", "complete     01-a  Alpha", "in_progress  02-b  Bravo",
                         "- `_decisions.md`", "- `_status.json`"):
            assert expected in resume, expected
        assert "### " in (d / "_decisions.md").read_text() and "Bravo uses the v2 API" in (d / "_decisions.md").read_text()
        # The resume: --start keeps every state prepare recorded.
        run(SET_STATUS, d, "--stop")
        assert run(SET_STATUS, d, "--start").returncode == 0
        states = {i["id"]: i["state"] for i in json.loads((d / "_status.json").read_text())["items"]}
        assert states == {"01-a": "complete", "02-b": "in_progress"}


def test_prepare_replaces_and_defaults_in_flight():
    with tempfile.TemporaryDirectory() as root:
        d = started(root)
        run(PREPARE, d, "first")
        assert run(PREPARE, d, "second").returncode == 0
        resume = (d / "_resume.md").read_text()
        assert "second" in resume and "first" not in resume and "Nothing in flight." in resume
        assert not list(d.glob(".resume-*"))


def test_bad_input_fails_and_writes_nothing():
    with tempfile.TemporaryDirectory() as root:
        d = started(root)
        for args in ([d], [d, ""], [d, "a\nb"], [d, "s", "--next"], [d, "s", "extra"], [d, "s", "--bogus"]):
            r = run(PREPARE, *args)
            assert r.returncode == 1 and r.stdout.startswith("FAIL:"), args
        unstarted = Path(root) / "fresh"
        unstarted.mkdir()
        r = run(PREPARE, unstarted, "s")
        assert r.returncode == 1 and r.stdout.startswith("FAIL:")
        assert not (d / "_resume.md").exists() and not (unstarted / "_resume.md").exists()


def test_eval_embeds_the_current_skill():
    # The eval sandbox cannot read the plugin, so its prompt carries a copy of SKILL.md that must not drift.
    body = (HERE.parent / "SKILL.md").read_text().split("---\n", 2)[2].strip()
    prompt = (HERE.parents[2] / "evals" / "orca-prepare-then-resume" / "prompt.md").read_text()
    assert f"<!-- SKILL START -->\n{body}\n<!-- SKILL END -->" in prompt


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
