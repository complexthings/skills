# `orca automations` reference

**Verified:** 2026-08-31

## Schedule

`--trigger <schedule>` accepts `hourly`, `daily`, `weekdays`, `weekly`, a 5-field cron expression, or an RRULE string. There is no one-shot `--trigger` form.

Use `--time <HH:MM>` with the `daily`, `weekdays`, or `weekly` presets, and `--timezone <tz>` for an IANA timezone.

_Source: `orca automations create --help`; `orca automations edit --help`._

## Create and edit

```sh
orca automations create --name <name> --trigger <schedule> --prompt <text> --provider <agent> --json
orca automations edit <id> [flags] --json
```

`create` requires `--name`, `--trigger`, `--prompt`, and `--provider`. `create --json` returns the automation id; pass that id to `edit`, `remove`, or `runs --id`.

| Flag | Use |
| --- | --- |
| `--trigger <schedule>` | Set the schedule. Required by `create`. |
| `--time <HH:MM>` | Time for daily, weekdays, or weekly presets. |
| `--timezone <tz>` | IANA timezone. |
| `--prompt <text>` | Prompt text. Required by `create`. |
| `--provider <agent>` | Agent provider. Required by `create`. |
| `--repo <selector>` | Repository selector, such as `id:<id>`, `name:<name>`, or `path:<path>`. |
| `--precheck <command>` | Run before scheduled runs; exit 0 continues and a non-zero exit records a skipped run. |
| `--precheck-timeout` | Available on both commands. |
| `--enabled` / `--disabled` | Enable or disable the automation. |
| `--workspace-mode <mode>` | `existing` or `new-per-run`. |
| `--base-branch <ref>` | Base branch/ref for the created worktree. |
| `--json` | Emit machine-readable JSON. |

_Source: `orca automations create --help`; `orca automations edit --help`._

## Remove

```sh
orca automations remove <id> --json
```

`remove` takes the automation id returned by `create --json` and removes that automation and its run history.

_Source: `orca automations remove --help`._

## List and run history

```sh
orca automations list --json
orca automations runs --id <automation-id> --json
```

`list` returns scheduled automations. `runs` returns automation run history and can filter it with `--id`; both support `--json`.

_Source: `orca automations list --help`; `orca automations runs --help`._

Re-verify this reference in [#50](https://github.com/complexthings/skills-build/issues/50).
