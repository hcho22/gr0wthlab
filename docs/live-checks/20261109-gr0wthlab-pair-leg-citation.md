# An A/B leg compared with an approved leg whose citation alone followed moved code

This change lets an A/B leg pass its pair check against the other leg's approved post when that leg's Draft differs from the approved file only in its claims' `Code:` lines (`posts.standing_posts`, `posts.reference_leg`).
It follows [the approved-copy change](20261109-gr0wthlab-approved-copy-citation.md), which covered the approved day itself but not the pair check.
It serves US-ME08.

## Round 1: a run on the real records

**Why:** in the production clone, run `20261109T143518Z-on-demand-079b` blocked day 8 (AB-1 leg B) with "pair-legs: day 1's Draft is no longer the one `20261101-post-w1-day-01` was queued from, so this leg cannot be compared with it".
Day 1's Draft differs from that approved copy only in its `Code:` line, which followed RepToday PR #220 from `ReadyViewModel.swift:415-439` to `472-500`.

**What was run:** `caffeinate -i ./src/bin/gr0wthlab run`, typed in a linked worktree of the production clone on branch `fm/gr0wthlab-pair-leg-citation`, Monday 2026-11-09 09:10 PST, with Codex CLI `codex-cli 0.160.0`.
The worktree held `origin/main` at `4108f438695d048fbf9f35ba889f650d22eb7796`, the records the production clone pushed after run `079b`, with this change applied and uncommitted.
It read the real Mandu package, the real RepToday checkout at `58f6dd4`, and the real footage place.
A checkout that is not the production clone neither syncs nor saves records.

**On which commit:** base `4108f438695d048fbf9f35ba889f650d22eb7796` (`src` tree `1d307d664eaefe6dfaaefc2d7c80e8035c75ef64`, `config` tree `99379828dec3738b54ce0839e53f3b66b980f35e`) plus this change's working-tree edits to `src/gr0wthlab/posts.py` and `src/tests/test_posts.py`.
`git status` before the run showed only those edits; the run's records were removed from the worktree afterwards and are not part of this change.
Configuration fingerprint: `4cb59d08f488c55beafef43f9853d28c0d28c96e84c0923894588cb1de759ecd`.

**Each run's identifier:** `20261109T171010Z-on-demand-ed9c`, the one run.

**What the records showed:**

- Post Drafts, day 8: `queued` as `20261109-post-w1-day-08`, with its finished video.
- Filming, day 8: `finished`, `assets/window-1/day-08-6ffc2faca178.mp4`, 9.00s, 1080x1920, 30 fps.
- Days 2, 3, 5, 6, 7, 9, 10, 12, and 13: `kept`; day 4: approved earlier; day 11: still blocked by its own unsupported claim, which this change does not touch.

**What was not exercised:**

- A leg whose other leg's approved Draft changed beyond its citations: `test_a_newer_leg_cannot_pass_against_a_reference_draft_that_is_not_the_one_posted` in `src/tests/test_posts.py`.
- `check-drafts` reading the plan record's approved post with its claim locations: nothing beyond the unit tests, since the record carries the same entry the launcher used.
- `boundary-check`: this change touches no boundary, runtime, fetch, or registry file.
