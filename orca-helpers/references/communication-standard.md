# Communication Standard

Every orca skill follows these rules whenever it writes to a person: a chat reply, a question, a report, a PR comment, a review report or a `/orca-board` message. The reader is a busy developer who scans fast, keeps little in working memory and needs to know the next move. Each rule below defends against one of those three failures.

The rules cover only the words a person reads. They do not cover file contents a script validates (`_config.json`, `_plan.md`, prompt files), command output a skill shows verbatim, or the question tool's mechanics, which each skill sets for itself.

## Rules for every message

1. Lead with the next action: the command, path or answer, before any explanation. A reader who stops after line 1 still knows what to do.
2. Write short, plain sentences in present tense and active voice: one idea per sentence and at most 25 words. Leave out idioms, hedges ("should", "might"), and preamble or closing pleasantries, because each one is text the reader decodes before reaching the point.
3. Use flat lists of at most 5 items, one level deep. Number steps that happen in order. Past 5 items, split the list into "do now" and "later", because a scanner loses the thread in a long list.
4. Bold only the action the reader takes or the one value that changed. Use no italics, capitals or emoji for emphasis. A second signal, or bold used everywhere, leaves the reader unsure which signal marks the action.
5. Restate state every turn: what is done and what is next, for example "Wave 1 of 3 merged. Next: dispatch Wave 2." The reader does not carry earlier turns in memory.
6. End with exactly one next step the reader can take in under 2 minutes. One step gets done. Three steps get skimmed. When nothing is left for the reader to do, say the work is done instead of inventing a step.

Copy every path, command, flag, id and `FAIL:` line byte for byte. Plain wording applies to prose only, never to a literal the reader pastes or searches for.

On an error, give the cause, then the fix: "`edit` failed, so the automation has no Once-Guard. Run `orca automations remove <id>`."

## PR comment format

orca-pr-review comments on a PR in this layout, top to bottom:

1. Line 1: the verdict and the count of blocking findings, for example `Changes requested: 2 blocking findings.` or `Approved: 0 blocking findings.`
2. Line 2: one encouragement line for the author that names a specific thing the change does well. Generic praise such as "Nice work!" reads as boilerplate, so the author learns nothing from it.
3. Blocking findings, numbered, at most 5. Each gives `path:line`, the Demonstrated Failure (the input or state and the wrong result it produces), and the fix.
4. Suggestions: a short flat list of at most 5 non-blocking items, one line each.
5. Optional last line: one safe-for-work GIF.

Leave out a section that has no items, except line 1, which every comment carries. When more than 5 blocking findings exist, list the 5 most severe and state how many remain on the last numbered line.

```markdown
Changes requested: 2 blocking findings.
The verb dispatch in `set_status.py` keeps every existing command untouched, which makes the next four tickets cheap.

1. `orca-helpers/skills/orca-prompt/scripts/set_status.py:88`: an unknown verb writes `_status.json` before it fails, so `set_status.py dir 01 bogus` leaves a half-written file. Fix: validate the verb before the write.
2. `orca-helpers/skills/orca-prompt/scripts/test_set_status.py:40`: no test covers an unknown verb. Fix: add one that asserts exit 1 and an unchanged file.

Suggestions:
- Name the `FAIL:` message after the verb, not the state.

![ship it](https://media.giphy.com/media/<id>/giphy.gif)
```
