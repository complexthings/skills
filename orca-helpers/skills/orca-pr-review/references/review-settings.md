# Review Settings

Review Settings live in `review-settings.json` in the Plugin Data Dir, outside every repo, keyed by `owner/repo`. Only `watch` and `start` write them:

```json
{"owner/repo": {"watched": true, "mode": "manual", "gifs": false, "cadenceMinutes": 5, "loopEndHours": 8,
                "mandatorySkills": ["sec-review"], "recommendedSkills": [], "instructions": "Check the migrations."}}
```

A missing repo or key reads as unwatched, manual mode, GIFs off, 5 minutes, a Loop End after 8 hours and no skills or instructions. `unwatch` sets `watched` to false and keeps the rest, so the repo returns as a recommendation at the next `start`. `mode` decides whether a Review Draft posts at once (`auto`) or waits for `approve` (`manual`). The cron runs at the shortest `cadenceMinutes` any Watched Repo sets. A repo with a longer cadence sits out the ticks in between. `cadenceMinutes` divides 60, or is whole hours that divide 24, so the cron fires at an even step. A change to the cadence takes effect after `stop` and then `start`.

`start` sets the Loop End to the longest `loopEndHours` among the repos it names, at most 168, because the session cron expires after 7 days. The first tick after the Loop End stops the loop.

`gifs` is off unless a repo sets it to `true`. When it is on, the script ends each posted review with one GIF from `references/gifs.json`, a hand-checked safe-for-work list. It skips the last 10 GIFs posted and any URL that does not return 200. When no GIF qualifies, the review posts without one. Add a GIF to that file only after watching it to the end, because every GIF posts in the user's name and the script never checks content.

`evidenceCommand` is optional, such as `"pnpm test"`. When it is set, each dispatch runs it once in a temporary detached checkout of the PR head, in the repo's Orca clone. The output, its exit code and the commit SHA go into the review brief as the Evidence Record. A non-zero exit is evidence, not a failure. Without it, the brief says `Evidence Record: none: no evidence command is set`, and the tick prints one `UNSUPPORTED-evidence owner/repo` line for that repo. A fork PR never runs it, because its head is code from outside the repo: its brief says `Evidence Record: none: fork PR`.
