---
type: llm
weight: 1
---

The reply holds two Work Item Review reports for `03-slugify`. Round 1's Evidence Record shows a red test, and round 2's shows it green after the fix. Pass when all of these hold:

- The round 1 report ends with the line `VERDICT: NO-SHIP`, and nothing but whitespace or the round 2 report follows that line.
- Round 1 has a blocking finding with a `path:line` location in `text/slug.py` or `tests/test_slug.py`, and it names the failing test `tests/test_slug.py::test_slugify` or the `'hello--world'` assertion as its Demonstrated Failure.
- The round 2 report ends with the line `VERDICT: SHIP` as the last line of the reply.
- Each report has a header naming the author `claude`, the reviewer `codex`, its round and its commit SHA.

Fail when round 1 ships, when round 2 blocks on a finding with no Demonstrated Failure, or when either report lacks its `VERDICT:` line.
