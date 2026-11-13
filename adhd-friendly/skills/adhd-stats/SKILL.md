---
name: adhd-stats
description: Print the adhd-friendly plugin's scoreboard from its own logs — Reply Meter violation trend, reply length, Reply Card tier counts, and the modelled token saving. Use when the user runs /adhd-stats or asks for adhd-friendly stats, meter scores, or card usage. Not for general ADHD or focus advice.
allowed-tools: Bash(python3 *)
---

# adhd-stats

Run the script and print its output verbatim:

```
python3 "${CLAUDE_SKILL_DIR}/scripts/stats.py" "${CLAUDE_PLUGIN_DATA}"
```

Rules:

- Print what the script returns. Add no commentary, no interpretation of the trend, no advice.
- The token saving is arithmetic over fixed per-tier card costs. Say "modelled", never "measured", if the user asks where it comes from.
- Empty logs print one line saying there is nothing recorded yet. That is the whole answer.
