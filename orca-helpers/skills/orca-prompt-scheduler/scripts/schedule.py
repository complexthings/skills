#!/usr/bin/env python3
"""Create a Workstream's one-shot Scheduled Prompt: create, id parse, Once-Guard wrapper, edit.

The automation id does not exist until `create` returns it, so the run creates
the automation with the `Execute` line alone, writes the precheck wrapper, then
`edit`s in the wrapper and the self-removing prompt. When any step after
`create` fails, it removes the automation again: an automation left without
its Once-Guard would fire every year.

Usage:
    python3 schedule.py <workstream-dir> --utc <ISO time> --tz <IANA> [--disabled] [--precondition <text>]

`--utc` is the `utc` field `resolve_schedule.py` printed and `--tz` its timezone.
Prints the created schedule as JSON, or `FAIL:` lines and exits 1.
"""
import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt" / "scripts"))
from orca_cli import orca_cli
from render_rules import normalize_model_slot
from scaffold import orca_agent

import once_guard
from check_conflicts import _automations

# The agent ids `--extra-agent-args` accepts, per `orca skills get orca-cli --reference references/automations.md`.
EXTRA_ARGS_AGENTS = ("claude", "codex", "codebuddy", "cursor", "grok", "omp")


class Failed(Exception):
    pass


def run(argv):
    """Run `argv`; return stdout, or raise `Failed` naming the step and its output."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise Failed(f"`{shlex.join(argv[:3])}` could not start: {e}")
    if done.returncode:
        raise Failed(f"`{shlex.join(argv[:3])}` exited {done.returncode}: {(done.stderr or done.stdout).strip()}")
    return done.stdout


def automation_id(output):
    """The new automation's id from `create --json`; the envelope's own top-level `id` is the request id."""
    try:
        result = json.loads(output).get("result") or {}
    except (json.JSONDecodeError, AttributeError):
        raise Failed(f"`automations create` printed no JSON: {output.strip()}")
    found = (result.get("automation") or {}).get("id") or result.get("id")
    if not found:
        raise Failed(f"`automations create` printed no automation id: {output.strip()}")
    return found


def extra_agent_args(harness, agent):
    """`--extra-agent-args=--model <m> [--effort <e>]` from the mainOrchestrator slot, or None."""
    model, effort = normalize_model_slot(harness.get("models", {}).get("mainOrchestrator"))
    if not model or agent not in EXTRA_ARGS_AGENTS:
        return None
    if "--extra-agent-args" not in run([*orca_cli(), "automations", "create", "--help"]):
        return None
    return "--extra-agent-args=" + shlex.join(["--model", model, *(["--effort", effort] if effort else [])])


def schedule(workstream, fire_utc, tz_name, disabled=False, precondition=""):
    workstream = Path(workstream).resolve()
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise Failed(f"{tz_name!r} is not an IANA timezone")
    try:
        utc = datetime.fromisoformat(fire_utc).astimezone(timezone.utc)
    except ValueError:
        raise Failed(f"{fire_utc!r} is not an ISO 8601 time")
    local = utc.astimezone(tz)
    cron = f"{local.minute} {local.hour} {local.day} {local.month} *"
    try:
        config = json.loads((workstream / "_config.json").read_text())
        harness = next(h for h in config["harnesses"] if h["name"] == config["mainOrchestratorHarness"])
    except (OSError, json.JSONDecodeError, KeyError, StopIteration) as e:
        raise Failed(f"{workstream}/_config.json names no mainOrchestratorHarness entry: {e}")
    agent = orca_agent(harness)
    repo = run(["git", "-C", str(workstream), "rev-parse", "--show-toplevel"]).strip()
    execute = f"Execute {workstream}/_orchestration.prompt.md"

    create = [
        *orca_cli(), "automations", "create",
        "--name", f"{workstream.name} orchestration",
        "--trigger", cron,
        "--timezone", tz_name,
        "--prompt", execute,
        "--provider", agent,
        "--repo", f"path:{repo}",
        "--base-branch", config["targetBranch"],
    ]
    extra = extra_agent_args(harness, agent)
    create += [extra] if extra else []
    create += ["--disabled"] if disabled else []
    # A failed create made nothing; a create that exits 0 but prints no id made one we must find and remove.
    output = run([*create, "--json"])
    try:
        new_id = automation_id(output)
    except Failed as e:
        remove_unread(e, workstream.name + " orchestration", cron)

    wrapper = workstream / ".scheduled" / f"{new_id}-precheck.sh"
    try:
        once_guard.write_wrapper(
            wrapper, new_id, workstream / ".scheduled" / f"{new_id}.marker", utc.isoformat(), precondition
        )
        run([
            *orca_cli(), "automations", "edit", new_id,
            "--precheck", str(wrapper),
            "--prompt", f"Before beginning, remove this automation: `{remove_cmd(new_id)}`.\n\n{execute}",
            "--json",
        ])
    except (Failed, OSError) as e:
        wrapper.unlink(missing_ok=True)
        try:
            run([*orca_cli(), "automations", "remove", new_id, "--json"])
        except Failed as gone:
            raise Failed(f"{e}; the rollback failed too, so run `{remove_cmd(new_id)}` by hand: {gone}")
        raise Failed(f"{e}; automation {new_id} was removed again, so nothing is scheduled")
    return {
        "id": new_id,
        "cron": cron,
        "timezone": tz_name,
        "local": local.isoformat(),
        "utc": utc.isoformat(),
        "enabled": not disabled,
        "precheck": str(wrapper),
        "cancel": remove_cmd(new_id),
    }


def remove_unread(error, name, cron):
    """Remove the automation a `create` made without printing its id, found by name and cron; always raises."""
    try:
        listed = _automations(json.loads(run([*orca_cli(), "automations", "list", "--json"])))
    except (Failed, json.JSONDecodeError) as gone:
        raise Failed(f"{error}; could not list automations to roll back, so remove `{name}` by hand: {gone}")
    found = [a.get("id") for a in listed
             if a.get("name") == name and (a.get("trigger") or a.get("schedule")) == cron]
    if len(found) != 1 or not found[0]:
        raise Failed(f"{error}; found {len(found)} automations named `{name}` on `{cron}`, so remove the new one by hand")
    try:
        run([*orca_cli(), "automations", "remove", found[0], "--json"])
    except Failed as gone:
        raise Failed(f"{error}; the rollback failed too, so run `{remove_cmd(found[0])}` by hand: {gone}")
    raise Failed(f"{error}; automation {found[0]} was removed again, so nothing is scheduled")


def remove_cmd(new_id):
    return shlex.join([*orca_cli(), "automations", "remove", new_id])


def main(argv):
    parser = argparse.ArgumentParser(prog="schedule.py")
    parser.add_argument("workstream")
    parser.add_argument("--utc", required=True)
    parser.add_argument("--tz", required=True)
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--precondition", default="")
    args = parser.parse_args(argv)
    try:
        result = schedule(args.workstream, args.utc, args.tz, args.disabled, args.precondition)
    except Failed as e:
        print(f"FAIL: {e}")
        return 1
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
