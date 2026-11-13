# Orca Workstreams

Plan and run Orca Workstreams across coding agents. `orca-prompt` creates a plan and worker prompts; `orca-execute` runs their Waves and records progress.

## Requirements

- Python 3 and the Orca CLI on PATH.
- An installed agent harness supported by Orca. Git and, for PR integrations, `gh` are also required.

## Install

Install `orca-workstreams` from the Complexthings marketplace with your harness's plugin manager. In Codex, use `codex plugin add orca-workstreams@complexthings`. For a harness that loads skills directly, install both directories under `skills/` together, preserving their contents. Restart or reload the harness if needed.

## Use

1. Invoke `orca-prompt` to plan a Workstream. It writes `.orca/prompts/<name>/` in the project.
2. Invoke `orca-execute <name>` to start or resume it. The generated orchestration prompt directs dispatch, integration, and cleanup.

The scripts are bundled with `orca-prompt`. Generated prompts contain absolute paths to the installed scripts, so re-scaffold after moving or reinstalling the skill. Scaffolding rewrites generated prompts; preserve manual changes first. This package does not include the Claude plugin's visual bands, scheduler, board, or knowledge graph.

Run the portable runtime check with `python3 -m unittest discover -s orca-workstreams/tests` from the repository root.
