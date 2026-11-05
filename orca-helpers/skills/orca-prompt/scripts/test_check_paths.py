#!/usr/bin/env python3
"""Self-check for check_paths.py. Run: python3 test_check_paths.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_paths
from check_paths import main, missing

HERE = Path(__file__).resolve().parent


def workstream(root, plan, **prompts):
    """A git repo at root holding one tracked skill file and a Workstream with the given files."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "skills" / "demo").mkdir(parents=True)
    (root / "skills" / "demo" / "SKILL.md").write_text("x")
    d = root / ".orca" / "prompts" / "ws"
    (d / "_completed").mkdir(parents=True)
    (d / "_plan.md").write_text(plan)
    for name, text in prompts.items():
        (d / f"{name}.prompt.md").write_text(text)
    return d


def test_missing_path_is_reported_with_file_and_line():
    with tempfile.TemporaryDirectory() as root:
        d = workstream(Path(root), "# Plan\n\nEdit `skills/demo/SKILL.md`.\nRun `python3 skills/demo/gone.py --flag`.\n")
        assert missing(d) == ["FAIL: _plan.md:4: path skills/demo/gone.py does not exist"]


def test_missing_command_and_prompt_files():
    with tempfile.TemporaryDirectory() as root:
        d = workstream(Path(root), "", **{"01-a": "```\nnosuchprogram-xyz run\npnpm-not-real\n```\nthen `orca-helpers/nope.md`\n"})
        # A fenced line runs a program only when PROGRAMS lists it, so neither fenced line is checked.
        assert missing(d) == ["FAIL: 01-a.prompt.md:5: path orca-helpers/nope.md does not exist"]
        (d / "02-b.prompt.md").write_text("Run `uv sync` first.\n")
        real = check_paths.shutil.which
        check_paths.shutil.which = lambda name: None if name == "uv" else real(name)
        try:
            assert missing(d)[-1] == "FAIL: 02-b.prompt.md:1: command uv is not on PATH"
        finally:
            check_paths.shutil.which = real


def test_names_that_exist_or_name_no_file_pass():
    plan = "\n".join([
        "`SKILL.md` and `demo/SKILL.md:42` and `skills/demo/`",  # bare name, tail with a line number, directory
        "`.orca/prompts/<workstream>/` `${CLAUDE_SKILL_DIR}/x.py` `test_*.py`",  # placeholders
        "`https://example.com/a.md` `path:/abs/x` `/clear` `/api/board` `owner/repo`",  # schemes, routes, pairs
        "`_status.json` `_rules.md` `01-a.prompt.md` `main` `pr-merge` `--worktree new-child`",
        "`git status`",
        "",
    ])
    with tempfile.TemporaryDirectory() as root:
        d = workstream(Path(root), plan)
        (d / "_completed" / "01-a.prompt.md").write_text("done")  # a finished Work Item moved out
        assert missing(d) == []


def test_smallest_inputs():
    with tempfile.TemporaryDirectory() as root:
        d = workstream(Path(root), "")
        assert missing(d) == []
        (d / "_plan.md").unlink()
        assert missing(d) == []  # no plan yet: nothing to check
        (d / "_plan.md").write_text("``\n` `\n```\n\n```\n")  # empty spans and an empty fence
        assert missing(d) == []
    assert main(["check_paths.py"]) == 2
    assert main(["check_paths.py", "/no/such/dir"]) == 2


def test_cli_exit_codes():
    with tempfile.TemporaryDirectory() as root:
        d = workstream(Path(root), "`skills/demo/nope.py`\n")
        r = subprocess.run([sys.executable, str(HERE / "check_paths.py"), str(d)], capture_output=True, text=True)
        assert r.returncode == 1 and r.stdout.startswith("FAIL: _plan.md:1: path skills/demo/nope.py"), r.stdout
        (d / "_plan.md").write_text("`skills/demo/SKILL.md`\n")
        r = subprocess.run([sys.executable, str(HERE / "check_paths.py"), str(d)], capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout.strip() == "ok: every named path and command exists", r.stdout


def test_eval_embeds_the_reviewer_brief():
    # The Prompt Check eval embeds the brief, since its sandbox cannot read the plugin directory.
    brief = (HERE.parent / "references" / "prompt-check.md").read_text()
    eval_prompt = HERE.parents[2] / "evals" / "prompt-check-goldfish" / "prompt.md"
    assert f"<!-- BRIEF START -->\n{brief}<!-- BRIEF END -->" in eval_prompt.read_text()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
