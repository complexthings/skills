---
name: pi-init
description: Create or update a concise, evidence-backed root AGENTS.md for the current project.
disable-model-invocation: true
---

# Pi Init

This skill is **manually invoked only**. Never auto-invoke or evaluate it.

## Authority and boundary

- Resolve the project root as the Git root (`git rev-parse --show-toplevel`); if that does not yield a root, use the current working directory. State the selected root in the final report.
- The only write target is `<root>/AGENTS.md`. Create or update that file and no other. Never create or edit companion AI instruction files, application code, environment configuration, dependencies, migrations, or project setup.
- Accept an optional user focus only when it is within the selected root. Reject or omit an out-of-bound focus and report it; do not inspect or change anything outside the root.
- Treat a missing target as creatable only when the target path is absent. If it is a symlink or non-regular path, leave it untouched and report the next safe action.

## 1. Resolve and preflight

Resolve the root and target before discovery. Check the target's existence, regular-file status, symlink status, and working-tree state without changing it. For an existing target, preserve valid project-specific rules and high-stakes security, legal, and ownership requirements unless the user explicitly approves a change.

**Complete this stage when:** the root, in-bound focus, target state, and edit authority are explicit.

## 2. Discover bounded evidence

Review only the smallest high-signal set needed to produce useful instructions, in this order:

1. root `README*`, manifests, workspace configuration, and lockfiles;
2. build, test, lint, formatter, typecheck, code-generation, and task-runner configuration;
3. CI workflows, pre-commit configuration, and relevant scripts;
4. existing `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`, and repo-local agent configuration;
5. relevant Git metadata, including ignore rules and target status; and
6. a small representative sample of relevant source directories only when configuration and docs do not establish architecture or entrypoints.

Prefer executable sources (scripts, manifests, configuration, and CI) to prose. Report material discrepancies instead of silently choosing a prose claim. Read nested instruction files only as needed to prevent conflicts; every pointer to nested instructions must name its exact relative path from `<root>`, state the material or scope it governs, and give a distinct condition that requires an agent to read it. Avoid generic pointers and do not duplicate nested contents in `AGENTS.md`; never edit nested instructions. Honor the bounded focus while selecting evidence.

Keep this review static and bounded: do not exhaustively scan, run tests, builds, formatters, generators, installs, or project setup. Do not read ignored, generated, vendored/dependency-tree, or secret material. Do not infer facts from filenames alone. During preflight discovery, resolve repository-established facts from evidence and gather every simultaneously answerable important unknown, safety ambiguity, and consequential conflict that remains; never ask for a repository-established fact. If material questions are necessary, use the available question tool for one short batch at most: number each question, state explicit choices for each ambiguity or conflict, and give one recommended answer labeled **(Recommended)** for each question, first when choices are listed; wait for answers before writing. If the batch is unanswered, report the gap and leave the target untouched. If a new material question is discovered after that batch, leave the target untouched, report it, and do not silently write or open another batch.

**Complete this stage when:** each applicable high-signal category has been considered, relevant architecture/workflow evidence is sufficient, and material discrepancies and evidence gaps are recorded without guesses.

## 3. Draft the shared core

Draft a concise, adaptive, portable root `AGENTS.md` for a shared Claude 5 + GPT-5.6 core. Use only verified facts and a stable useful order. Include exact runnable commands when found, material architecture, workflow, constraints, and nested-instruction pointers satisfying the pointer rule above. Keep simple repositories simple.

Follow the current rule-rewriter guidance for both model families: state clear outcomes and boundaries, use conditional tradeoffs where context changes the right action, and keep direct instructions lean. Retain high-stakes requirements. Avoid brittle routine mandates, generic advice, invented commands, duplicate documentation, unnecessary provider/model sections, empty headings, exhaustive file trees, and uncertainty. Omit unknowns from `AGENTS.md`; report the gaps instead.

**Complete this stage when:** every proposed line has evidence or is a necessary scope/safety boundary, and the draft contains no empty, generic, duplicated, invented, or unresolved material.

## 4. Apply the confirmation gate

### Missing `AGENTS.md`

State the intended concise contents to the user, then create `<root>/AGENTS.md` directly only when preflight has no unanswered material question and no ambiguity or safety issue requiring an explicit choice. Do not create a saved draft. If the discovery question batch is unanswered, leave the target absent and report the gap.

### Existing `AGENTS.md`

If it is already current, make no change. Otherwise, inspect whether **that target file** is dirty and warn only about that target; do not turn unrelated repository changes into warnings. Generate a focused unified diff against its current contents, plus a summary of material changes and instruction conflicts. Wait for explicit user confirmation of that proposed target-file change before writing, even when the target is clean. A confirmation for another file or action does not authorize this write.

Preserve valid project-specific rules. Compact or remove only stale, duplicated, or generic content. Consequential or ambiguous instruction conflicts require an explicit user choice. Decline, cancellation, unanswered conflicts, non-regular or symlinked targets, and unsafe ambiguity all mean: leave the target untouched, do not partially apply edits or save a draft, and report the next safe action.

**Complete this stage when:** the missing-file write was authorized by the direct-create rule, the existing-file change was explicitly confirmed, or a safe stop was reported with no target mutation.

## 5. Write and validate

Write only the authorized root `AGENTS.md`. After a write, re-read it and statically verify its Markdown structure, every factual claim, every command and path, the root-only scope, and every nested-instruction pointer against the reviewed evidence. Do not run project commands as validation.

**Complete this stage when:** the written file matches the authorized content, all claims and pointers are evidence-backed, scope is confined to the root target, and static checks pass.

## Report

End with a concise actionable report containing:

- selected root;
- changed or unchanged target path;
- key decisions;
- static validation performed;
- evidence gaps and conflicts; and
- the next action if blocked.

For a safe stop, say that the target was left untouched and identify the exact missing confirmation, answer, or safety condition.
