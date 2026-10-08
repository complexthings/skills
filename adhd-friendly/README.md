# adhd-friendly

A Claude Code plugin that keeps replies short, actionable, and consistently shaped.

Three hooks, one output style, and one skill:

- `UserPromptSubmit` prints a Reply Card beside every prompt, sized to the prompt.
- `Stop` meters the reply that just finished, silently, and logs the score.
- `SessionStart` prints at most three lines saying where the last session left off.
- The `adhd-friendly` output style carries the long rules. Pick it with `/output-style`, as `adhd-friendly:adhd-friendly`.
- The `adhd-stats` skill prints a scoreboard from the logs. Run `/adhd-stats`, or ask for your adhd-friendly stats.

The card carries only the per-turn reminder, so a one-line prompt costs a one-line card.

## Install

```
/plugin marketplace add complexthings/skills
/plugin install adhd-friendly@complexthings
```

## Configuration

Three knobs, all optional, set in `/config` or when you enable the plugin. Hooks read them from `CLAUDE_PLUGIN_OPTION_<KEY>`.

| Knob | Default | What it does |
| --- | --- | --- |
| `cardTiers` | `6,12` | Reply Card tier thresholds as `oneLine,full` word counts. A prompt of 6 words or fewer gets the one-line card. A question, or a prompt longer than 12 words, gets the whole card. Anything else gets the shape half. |
| `meter` | `true` | Score each finished reply and log it. `false` means the `Stop` hook logs nothing and the next card carries no violation line. |
| `strictness` | `normal` | How hard the meter scores. `lenient` counts only the shape rules, `normal` counts the full STE set, `strict` adds the house spelling and dash counts. |

## State

Logs live in `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/<plugin-id>/`), which survives plugin updates and is deleted on uninstall. Outside Claude Code the scripts fall back to `~/.claude/adhd-friendly/`. `scripts/store.py` is the only file that knows this; every hook script goes through it.

- `card.log` — one JSON line per card fired: time, tier, violation prefix, first 80 characters of the prompt.
- `meter.log` — one JSON line per finished reply: session id, violation counts, reply shape counters.

Check the store on its own:

```
python3 scripts/store.py --self-test
```

## Hook safety

No hook blocks a turn. Every hook script exits 0, including when it raises, when a log is missing, and when the reply is empty.

## Changelog

- 0.2.0: Reply Card refresh for Claude 5. Plugin best-practices pass: config knobs read from `CLAUDE_PLUGIN_OPTION_<KEY>`, `adhd-stats` is model-invocable and reads the plugin data directory, an eval suite under `evals/`.
- 0.1.0: First release.
