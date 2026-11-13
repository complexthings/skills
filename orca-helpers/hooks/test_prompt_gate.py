#!/usr/bin/env python3
"""Self-check for prompt_gate.py. Run: python3 test_prompt_gate.py"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_gate.py")


def run(prompt, env=None):
    r = subprocess.run([sys.executable, SCRIPT], input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}), capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_check_prompt_blocks():
    assert json.loads(run(" orca-hooks-check\n")) == {"decision": "block", "reason": "orca-helpers classic hooks are live."}


def test_other_prompts_pass():
    assert run("orca-hooks-check please") == ""
    assert run("hello") == ""


def test_tick_ignores_claude_plugin_data_and_says_when_no_loop_runs():
    # Claude Code sets CLAUDE_PLUGIN_DATA for hooks only; the tick must read the dir `start` wrote.
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as hook_data:
        env = {k: v for k, v in os.environ.items() if k != "ORCA_HELPERS_DATA"}
        env.update(HOME=home, CLAUDE_PLUGIN_DATA=hook_data)
        context = json.loads(run("/orca-helpers:orca-pr-review tick", env))["hookSpecificOutput"]["additionalContext"]
        assert f"No active loop in {os.path.join(home, '.claude', 'orca-helpers')}." in context, context


if __name__ == "__main__":
    test_check_prompt_blocks()
    test_other_prompts_pass()
    test_tick_ignores_claude_plugin_data_and_says_when_no_loop_runs()
    print("ok")
