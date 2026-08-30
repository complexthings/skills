#!/usr/bin/env python3
"""Probe PATH for the seven known Agent Harness CLIs and report which are installed.

Prints a JSON array to stdout, one object per known Agent Harness:
    {"name": "claude", "cli": "claude", "installed": true, "path": "/usr/bin/claude"}

The report comes back in the priority order `data/model-priority.json` sets, so
the skill can offer the options in that order without re-sorting.

The `orca-prompt` skill's Agent Harness question offers only entries where
`installed` is true, plus a free-text path for an Agent Harness this probe missed
(see CONTEXT.md's "Agent Harness" entry for the closed set of seven).
"""
import json
import os
import shutil
import sys

# name -> cli command, matching CONTEXT.md's Agent Harness vocabulary and the
# _config.json schema in orca/orca-prompt/SKILL.md.
KNOWN_HARNESSES = {
    "claude": "claude",
    "opencode": "opencode",
    "copilot": "copilot",
    "codex": "codex",
    "pi": "pi",
    "prime-agent": "prime-agent",
    "agy": "agy",
}

PRIORITY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "model-priority.json")


def harness_order(path=PRIORITY_PATH):
    """The Agent Harness priority order from `data/model-priority.json`."""
    with open(path) as handle:
        return json.load(handle)["harnessOrder"]


def detect_harnesses(order=None):
    """Return {name, cli, installed, path} per known Agent Harness, in priority order."""
    order = harness_order() if order is None else order
    # An Agent Harness the priority file forgot still gets probed, listed last.
    names = sorted(KNOWN_HARNESSES, key=lambda name: (order.index(name) if name in order else len(order), name))
    report = []
    for name in names:
        cli = KNOWN_HARNESSES[name]
        path = shutil.which(cli)
        report.append({"name": name, "cli": cli, "installed": path is not None, "path": path})
    return report


if __name__ == "__main__":
    json.dump(detect_harnesses(), sys.stdout, indent=2)
    print()
