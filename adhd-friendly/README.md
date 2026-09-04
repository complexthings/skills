# adhd-friendly

A Claude Code plugin that keeps replies short, actionable, and consistently shaped.

Three hooks and one output style:

- `UserPromptSubmit` prints a Reply Card beside every prompt, sized to the prompt.
- `Stop` meters the reply that just finished, silently, and logs the score.
- `SessionStart` prints at most three lines saying where the last session left off.

The long rules ship as a bundled output style, loaded once per session. The card carries only the per-turn reminder, so a one-line prompt costs a one-line card.

## Install

```
/plugin marketplace add complexthings/skills
/plugin install adhd-friendly@complexthings
```

## Configuration

Three knobs, all optional. The defaults reproduce the plugin's behavior with no configuration.

| Knob | Default | What it does |
| --- | --- | --- |
| `cardTiers` | `6,12` | Reply Card tier thresholds as `oneLine,full` word counts. A prompt of 6 words or fewer gets the one-line card. A question, or a prompt longer than 12 words, gets the whole card. Anything else gets the shape half. |
| `meter` | `true` | Score each finished reply and log it. `false` means the `Stop` hook logs nothing and the next card carries no violation line. |
| `strictness` | `normal` | How hard the meter scores. `lenient` counts only the shape rules, `normal` counts the full STE set, `strict` adds the house spelling and dash counts. |

## State

Logs live in `${CLAUDE_PLUGIN_DATA}`, falling back to `~/.claude/adhd-friendly/`. `scripts/store.py` is the only file that knows this; every hook script goes through it.

- `card.log` — one JSON line per card fired: time, tier, violation prefix, first 80 characters of the prompt.
- `meter.log` — one JSON line per finished reply: session id, violation counts, reply shape counters.

Check the store on its own:

```
python3 scripts/store.py --self-test
```

## Hook safety

No hook blocks a turn. Every hook script exits 0, including when it raises, when a log is missing, and when the reply is empty.
