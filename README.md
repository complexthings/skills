# complexthings/skills

Agent skills published by [Complex Things](https://github.com/complexthings).

This repository is generated. It is the install target only — source, issues, and
pull requests live in the private build repo. Every publish replaces the entire
history with a single commit, so clone it fresh rather than pulling.

## Install

With the `skills` CLI:

```bash
npx skills@latest add complexthings/skills --agent claude-code -p -y
```

As a Claude Code plugin marketplace:

```
/plugin marketplace add complexthings/skills
/plugin install orca@complexthings-skills
/plugin install adhd-friendly@complexthings-skills
```

## Plugins

### `orca`

Orca workstream orchestration skills.

- **`orca-prompt`** — Start a new Orca workstream: interviews for the workstream
  name, target branch, and scope of work, then writes `_config.json` and
  `_plan.md` under `.orca/prompts/<workstream>/`.

### `adhd-friendly`

Keeps replies short, actionable and consistently shaped: a per-prompt Reply Card,
a silent Reply Meter, and a bundled ADHD output style.

```
/plugin install adhd-friendly@complexthings-skills
```

- **`adhd-stats`** — Print the adhd-friendly scoreboard: violation trend, reply
  length, card tier distribution, and the modelled token saving.

## Layout

```
.claude-plugin/marketplace.json   plugin manifest
orca/<skill>/SKILL.md             skill entry points
adhd-friendly/skills/<skill>/SKILL.md
```

## License

See the repository owner for licensing.
