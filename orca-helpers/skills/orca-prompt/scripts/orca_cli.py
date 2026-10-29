#!/usr/bin/env python3
"""Resolve the Orca executable once, following the stub rule in the orca-cli skill.

`ORCA_CLI_COMMAND` when set (Orca exports it for managed WSL sessions), else
`orca-dev` in a dev checkout that exposes `ORCA_DEV_REPO_ROOT`, else `orca-ide` on
Linux outside an Orca-managed terminal, else `orca`. On Linux a bare `orca`
outside Orca's terminals is usually the GNOME screen reader.

Usage:
    python3 orca_cli.py    # prints the resolved command, shell-quoted
"""
import os
import shlex
import sys


def orca_cli(env=None, platform=None):
    """The Orca executable as a list of argv words, for example `["orca"]`."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    command = env.get("ORCA_CLI_COMMAND", "")
    if command.strip():
        try:
            words = shlex.split(command)
        except ValueError:  # an unbalanced quote; split on whitespace rather than crash every caller
            words = command.split()
        if words and words[0]:  # an empty argv or an empty first word is no executable, so fall through to the next rule
            return words
    if env.get("ORCA_DEV_REPO_ROOT"):
        return ["orca-dev"]
    # Orca exports ORCA_TERMINAL_HANDLE into every terminal it manages, so its absence means outside Orca.
    if platform.startswith("linux") and not env.get("ORCA_TERMINAL_HANDLE"):
        return ["orca-ide"]
    return ["orca"]


def main(argv):
    if argv:
        print("FAIL: orca_cli.py takes no arguments")
        return 2
    print(shlex.join(orca_cli()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
