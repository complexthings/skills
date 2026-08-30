---
name: adhd-stats
description: Print the adhd-friendly scoreboard — violation trend, reply length, card tier distribution, and the modelled token saving — from card.log and meter.log. Use when the user runs /adhd-stats.
disable-model-invocation: true
---

# adhd-stats

Run the script and print its output verbatim:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adhd-stats/scripts/stats.py"
```

Rules:

- Print what the script returns. Add no commentary, no interpretation of the trend, no advice.
- The token saving is arithmetic over fixed per-tier card costs. Say "modelled", never "measured", if the user asks where it comes from.
- Empty logs print one line saying there is nothing recorded yet. That is the whole answer.
