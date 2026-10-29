---
name: orca-kb
description: Recall, record and health-check the Orca Knowledge Graph, the user-level store of what this repo's Orca Workstreams decided and learned, kept at ~/.claude/orca-helpers/kb/<owner__repo>/ outside the repo. `review <task>` recalls facts for a task, `update <slug>` writes a page with its extraction and aliases, `lint` runs a read-only health check. Use for "orca-kb", "what did earlier Workstreams decide about X", "record this Workstream's lessons", or the Main Orchestrator's last step. It holds only Orca Workstream memory, so a request for the project knowledge base, its context for a task, or .agents/project-knowledge/ belongs to the rex-kb skills, even when no rex skill is installed. To create the store, use orca-bootstrap.
argument-hint: "review <task> | update <slug> | lint"
---

# orca-kb

The Orca Knowledge Graph keeps what a repo's Workstreams learned, so the next one does not relearn it (ADR 0015). It lives outside the repo, at `~/.claude/orca-helpers/kb/<owner__repo>/`: `pages/<slug>.md`, `extraction/<slug>.json` and `graph.db`. Nothing here writes inside the repo.

The argument is `$ARGUMENTS`. Run every command from the repo root. When the store is missing, `review` prints no matches and `lint` says to run `/orca-bootstrap`. Run orca-bootstrap then, because it is safe to rerun, and retry the verb.

## Writing to the user

Every message to the user follows the Communication Standard in `${CLAUDE_PLUGIN_ROOT}/references/communication-standard.md`. Read it before your first message.

## review

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-kb/scripts/kb.py review <task words>
```

Recall seeds only on an entity name or alias that appears as a whole word in the task. Pass the task's own nouns: system names, file names, Workstream names. Report the facts it prints. `(no memory matches for this prompt)` is a real answer, not an error.

## update

One call writes the page, writes its extraction, and rebuilds the graph:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-kb/scripts/kb.py update <slug> --page "<markdown>" --extraction '<json>'
```

- `<slug>` is lowercase letters, digits, `.`, `_` or `-`. The same slug overwrites its page. Reuse it to correct that page's fact, and pick a new slug for a new fact so no other page is lost.
- The extraction is `{"nodes": [...], "edges": [...], "aliases": [...]}`. Read `${CLAUDE_SKILL_DIR}/references/extraction.md` for the node types, predicates and alias rules before you write one.

A `FAIL:` line means nothing was written: fix what it names and run it again. Any other problem line under the counts means the page and extraction landed, and only the named edge or alias was skipped. Fix it with a second `update` on the same slug.

## lint

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/orca-kb/scripts/kb.py lint
```

It reports pages without an extraction, extractions without a page, edges or aliases naming no node, types outside the vocabulary, and non-`CONCEPT` nodes without an alias. It changes nothing. Fix each problem with `update`.
