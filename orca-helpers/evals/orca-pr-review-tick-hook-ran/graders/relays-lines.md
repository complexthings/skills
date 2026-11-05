---
type: llm
weight: 1
---

The prompt carries a tick the orca-helpers hook already ran. Pass when the reply relays the `Review Draft ready: acme/api#12` line and includes the command `/orca-pr-review approve acme/api#12`. Reading the review report first is fine. Fail when the reply says it ran a new scan, invents other PRs, or drops the approve command.
