#!/usr/bin/env python3
"""Self-check for prompt_gate.py. Run: python3 test_prompt_gate.py"""
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_gate.py")


def run(prompt):
    r = subprocess.run([sys.executable, SCRIPT], input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_check_prompt_blocks():
    assert json.loads(run(" orca-hooks-check\n")) == {"decision": "block", "reason": "orca-helpers classic hooks are live."}


def test_other_prompts_pass():
    assert run("orca-hooks-check please") == ""
    assert run("hello") == ""


if __name__ == "__main__":
    test_check_prompt_blocks()
    test_other_prompts_pass()
    print("ok")
