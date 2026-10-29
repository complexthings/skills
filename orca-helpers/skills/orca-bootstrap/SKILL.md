---
name: orca-bootstrap
description: Create the Orca Knowledge Graph store for this repo at ~/.claude/orca-helpers/kb/<owner__repo>/ and backfill it from every .orca/prompts/*/_decisions.md Decision Log. Safe to rerun, and it writes nothing inside the repo. Use for "orca-bootstrap", "set up the Orca knowledge graph", or when orca-kb reports no store. To build or reset the Rex project knowledge base in .agents/project-knowledge/, use rex-create-kb or rex-reset-kb. To read or write the graph afterwards, use orca-kb.
---

# orca-bootstrap

Creates the repo's Orca Knowledge Graph store (ADR 0015) and fills it from the Decision Logs already on disk. It writes nothing inside the repo, so `git status` stays clean.

## Writing to the user

Every message to the user follows the Communication Standard in `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`. Read it before your first message.

## Steps

1. **Run the bootstrap** from the repo root:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-kb/scripts/kb.py bootstrap
   ```

   Each Decision Log becomes one page, `decisions__<workstream>`, with each entry a `CONCEPT` that is `part_of` its Workstream. A rerun rewrites the same pages, so it never duplicates.

2. **Report** the store path, the Workstreams it backfilled, and the graph counts it printed. Any indented line under the counts is an extraction problem: name it, and suggest `/orca-kb lint`.
