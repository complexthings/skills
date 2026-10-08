#!/usr/bin/env python3
"""Self-check for detect_harnesses.py. Run: python3 test_detect_harnesses.py"""
import os
import stat
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from detect_harnesses import detect_harnesses, harness_order, KNOWN_HARNESSES


def test_detects_only_harnesses_on_path():
    with tempfile.TemporaryDirectory() as bin_dir:
        fake = os.path.join(bin_dir, "claude")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)

        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = bin_dir
        try:
            report = detect_harnesses()
        finally:
            os.environ["PATH"] = old_path

    by_name = {entry["name"]: entry for entry in report}
    assert len(report) == len(KNOWN_HARNESSES)
    assert by_name["claude"]["installed"] is True
    assert by_name["claude"]["path"] == fake
    assert by_name["opencode"]["installed"] is False
    assert by_name["opencode"]["path"] is None
    # Antigravity (`agy`) replaced the deprecated `gemini` CLI.
    assert "agy" in by_name
    assert "prime-agent" in by_name
    assert "gemini" not in by_name


def test_report_follows_the_priority_order():
    order = harness_order()
    assert [entry["name"] for entry in detect_harnesses()] == order
    assert sorted(order) == sorted(KNOWN_HARNESSES)
    # An Agent Harness the priority file forgot is still probed, listed last.
    names = [entry["name"] for entry in detect_harnesses(["agy", "pi"])]
    assert names[:2] == ["agy", "pi"]
    assert sorted(names) == sorted(KNOWN_HARNESSES)


if __name__ == "__main__":
    test_detects_only_harnesses_on_path()
    test_report_follows_the_priority_order()
    print("ok")
