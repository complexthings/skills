#!/usr/bin/env python3
"""Self-check for orca_cli.py. Run: python3 test_orca_cli.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from orca_cli import orca_cli

IN_ORCA = {"ORCA_TERMINAL_HANDLE": "term_1"}

# ORCA_CLI_COMMAND wins over everything and is split like a shell would.
assert orca_cli({"ORCA_CLI_COMMAND": "wsl.exe -- '/opt/my orca'", "ORCA_DEV_REPO_ROOT": "/x"}, "linux") == ["wsl.exe", "--", "/opt/my orca"]
# A dev checkout uses orca-dev, on any platform.
assert orca_cli({"ORCA_DEV_REPO_ROOT": "/x"}, "linux") == ["orca-dev"]
assert orca_cli({"ORCA_DEV_REPO_ROOT": "/x", **IN_ORCA}, "darwin") == ["orca-dev"]
# Linux outside an Orca terminal must not run the GNOME screen reader.
assert orca_cli({}, "linux") == ["orca-ide"]
# Linux inside an Orca terminal, and every other platform, use orca.
assert orca_cli(IN_ORCA, "linux") == "orca".split()
assert orca_cli({}, "darwin") == "orca".split()
assert orca_cli({}, "win32") == "orca".split()
# An unbalanced quote falls back to a whitespace split instead of raising.
assert orca_cli({"ORCA_CLI_COMMAND": "wsl.exe 'orca"}, "linux") == ["wsl.exe", "'orca"]
# An empty ORCA_CLI_COMMAND counts as unset.
assert orca_cli({"ORCA_CLI_COMMAND": ""}, "darwin") == "orca".split()
# So does a whitespace-only one, and the next rule still applies.
assert orca_cli({"ORCA_CLI_COMMAND": "  "}, "darwin") == ["orca"]
assert orca_cli({"ORCA_CLI_COMMAND": " \t", "ORCA_DEV_REPO_ROOT": "/x"}, "linux") == ["orca-dev"]
assert orca_cli({"ORCA_CLI_COMMAND": "''"}, "darwin") == ["orca"]
print("ok")
