# Built-in grilling

orca-prompt's own procedure for settling the Scope of Work. Step 5 of `SKILL.md` runs it whenever `grill-with-docs` refuses to run, so a Workstream never depends on a skill outside `orca-helpers`. It does the same two jobs: it interviews the user until the scope is settled, and it writes domain terms and decisions into `CONTEXT.md` and ADRs as they surface.

## What "settled" means

The session ends when all of these hold and the user confirms them:

- Every Work Item has an id, a title and a size (`light` or `standard`), and its work is unambiguous.
- Every Work Item has a Wave, and a Work Item depends only on Work Items in earlier Waves.
- Every skill a Work Item depends on has a decided name and behavior.
- The **Workstream Definition of Done** is a short list of checks someone can run or observe. "Works well" is not a check. "`pytest` passes and the login page renders the OAuth button" is one.
- The `integration` and `tickets` answers from Round 1 still fit the scope. Re-ask one only when the scope contradicts it.

## The design tree

Map the scope as a **design tree**: each decision branches into the decisions that depend on it. The root holds the Workstream goal. Its children hold the Work Items. Each Work Item's children hold its open questions: inputs, outputs, edge cases, the files it touches, how its result is checked.

Find facts yourself. When a question needs a fact from the repo, the filesystem or a tool, look it up, or dispatch a subagent to look it up. Ask the user only for decisions. A running lookup blocks only the questions that depend on it.

## Rounds

Work the tree in rounds. The **frontier** is every decision whose prerequisites are already settled. Ask the whole frontier in one round, then wait for the answers.

1. Ask each frontier question with the Agent Harness question tool. Put the recommended answer first and mark it **(Recommended)**. Give a recommendation even when the choice is close, so the user can accept it in one click.
2. Where the question tool has no working multi-select, list the options as `A`, `B`, `C` in the question body and take comma-separated letters.
3. Leave a question whose answer depends on another open question in the same round for a later round.
4. After each round, record the answers, update the tree and recompute the frontier.
5. Repeat until the frontier is empty.

Settle the Workstream Definition of Done in the last round, after the Work Items. Recommend one check per Work Item outcome, plus the repo's own test command. Find that command in the repo's manifests, CI config or README. When the repo has none, recommend no test check and say so. When `integration` is `pr-merge` or `commit`, recommend a check that the target branch holds the merged work.

Then show the user the whole settled tree in one message: Work Items by Wave with sizes, and the Workstream Definition of Done. Ask them to confirm it with one **(Recommended)** "Yes, this is the scope" answer. Do not start step 6 until they confirm.

## Domain docs as you go

Write these when a term or decision settles, not in a batch at the end:

- **`CONTEXT.md`** at the repo root holds the glossary. When the user settles a domain term, add or update its entry: the term in bold, a one-paragraph definition, and an `_Avoid_:` line naming the synonyms to drop. Keep implementation detail out of it. Create the file when the first term settles.
- When the user uses a term that conflicts with an existing `CONTEXT.md` entry, name the conflict and ask which meaning is right.
- **`docs/adr/NNNN-<slug>.md`** records a decision. Offer one only when the decision is hard to reverse, surprising without context and the result of a real trade-off. Number it one past the highest existing ADR. Write the decision as the title, one paragraph of context and choice, a `## Considered Options` list, and a `## Consequences` paragraph.

Name every file you wrote or changed when you hand the settled scope back to the end of step 5 in `SKILL.md`.
