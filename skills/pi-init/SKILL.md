---
name: pi-init
description: Create or update a concise, evidence-backed root AGENTS.md for the current project.
disable-model-invocation: true
---

# Pi Init

Produce one root `AGENTS.md` that a Claude 5 or GPT-6 agent can rely on: every line backed by repository evidence, nothing guessed, and no write the user has not authorized.

The bundled script handles every deterministic step. Run it from the project directory as `python3 <this-skill-dir>/scripts/pi_init.py <subcommand>` (Python 3.11+, standard library only). It prints JSON to stdout and exits 0 on success, 1 on a blocking finding or refusal, and 2 on a usage error. Your judgment covers what the script cannot decide: which evidence matters, what to ask, what to write, and whether each claim is true.

## Authority and boundary

These are hard rules because a wrong write lands in someone's repository:

- The only write target is `<root>/AGENTS.md`, and the only way to write it is the script's `write` subcommand. Do not create or edit companion AI instruction files, nested instructions, application code, environment configuration, dependencies, migrations, or project setup.
- A user focus is accepted only when preflight reports it in bounds. Omit an out-of-bound focus, report it, and do not inspect anything outside the root.
- A symlinked or non-regular target is never touched. Report it and the next safe action.
- Do not save a draft to disk. Pass drafts to the script on stdin.

## 1. Preflight

Run `preflight` (add `--focus <path>` when the user gave one). It resolves the root (Git root, else the current directory) and reports the target's kind, sha256, and Git status. Keep the reported `sha256` (or `absent`) for the write step. Exit 1 means a blocking condition: stop and report it.

For an existing target, read it now. Preserve its valid project-specific rules and any security, legal, or ownership requirements unless the user explicitly approves changing them.

## 2. Discover evidence

Run `inventory` for the candidate files that exist and are not gitignored, grouped as `manifests`, `readme`, `lockfiles`, `tooling`, `ci`, `hooks`, `scripts`, `agent_instructions`, and `nested_instructions`. Read the smallest subset that establishes commands, architecture, workflow, and constraints, preferring executable sources (manifests, scripts, configuration, CI) over prose. Sample source directories only when configuration and docs leave architecture or entrypoints unclear.

Keep discovery static: running tests, builds, formatters, generators, installs, or setup can mutate the tree or reach the network outside the one authorized write. Skip generated, vendored, and secret material, and do not infer facts from filenames alone. When prose and executable sources disagree, record the discrepancy instead of picking one silently.

Read a nested instruction file only as far as needed to avoid conflicting with it. A pointer to one in `AGENTS.md` names its exact relative path, the scope it governs, and the condition under which an agent should read it; it does not duplicate the nested contents.

Never ask the user for a fact the repository establishes. When important unknowns, safety ambiguities, or consequential conflicts remain, ask them in one batch with the question tool: number each question, give explicit choices, and put the recommended choice first, labeled **(Recommended)**. Wait for answers before drafting. If the batch goes unanswered, or a new material question appears after it, leave the target untouched and report the gap rather than opening a second batch.

**Done when:** each inventory category has been considered and every remaining unknown is either answered or recorded as a gap.

## 3. Draft

Draft a concise, portable `AGENTS.md` shared by Claude 5 and GPT-6 agents, in a stable order: exact runnable commands that were found, material architecture, workflow, constraints, and nested-instruction pointers. Keep simple repositories simple.

Write instructions the way both families follow them best: state the outcome and the reason, express tradeoffs as conditions rather than blanket bans, and keep hard rules only for high-stakes boundaries. Leave out generic advice, invented commands, duplicated docs, provider-specific sections, exhaustive file trees, and empty headings. Unknowns stay out of the file and go into the report.

Pipe the draft to `validate --stdin` and fix every finding (missing or out-of-root paths, empty headings, unclosed fences). Then check every remaining claim against the evidence you read; the script cannot judge truth.

## 4. Confirmation gate

**Target absent:** tell the user the intended contents in brief, then write it, provided no material question is unanswered and no ambiguity or safety issue needs their choice.

**Target exists:** pipe the draft to `diff`. If `changed` is false, make no change. Otherwise show the diff with a summary of material changes and instruction conflicts. If preflight reported `git_status` as `dirty` or `untracked`, warn about the target only, not unrelated repository changes. Wait for explicit confirmation of this diff before writing; approval of any other file or action does not count.

Decline, cancellation, unanswered conflicts, and unsafe ambiguity all end the same way: leave the target untouched, apply nothing partially, and report the next safe action.

## 5. Write and validate

Pipe the authorized content to `write --expect-sha <sha256-or-absent>` using the value from preflight. A refusal means the target changed or became unsafe since preflight: stop, report it, and do not retry with a new hash without re-running the confirmation gate.

After a successful write, run `validate` on the written file. Do not run project commands as validation.

## Report

End with a concise report:

- selected root and its source (`git` or `cwd`);
- target path and whether it changed;
- key decisions;
- validation performed and its result;
- evidence gaps and conflicts; and
- the next action, if blocked.

For a safe stop, say the target was left untouched and name the exact missing confirmation, answer, or safety condition.
