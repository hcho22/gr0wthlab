# A claim citation that followed moved code keeps an approved copy

This change lets a day whose copy the Founder approved before its video existed get its video when its Draft differs from the approved file only in its claims' `Code:` lines (`drafts.same_copy`, `posts.cited`, `posts.approved_copy`).
It serves US-ME08 and US-ME09.

## Round 1: a run on the real records

**Why:** in the production clone, RepToday PR #220 moved `generate` in `ReadyViewModel.swift` from lines 415-439 to 472-500.
Day 1's approved copy (`20261101-post-w1-day-01`) then failed its claim check at `58f6dd4` (run `20261109T002710Z-on-demand-4b97`).
With only its `Code:` line moved to `472-500`, it was no longer that copy, so no video was cut (run `20261109T045521Z-on-demand-cb9a`).

**What was run:** `./src/bin/gr0wthlab run`, typed in a linked worktree of the production clone on branch `fm/gr0wthlab-approved-copy-citation`, Sunday 2026-11-08 21:18 PST, with Codex CLI `codex-cli 0.160.0`.
The worktree held `origin/main` at `b2c2513a8cb9474a27d8982679ec205aaedefaec`, the records the production clone pushed after run `cb9a`, with this change applied and uncommitted.
It read the real Mandu package, the real RepToday checkout at `58f6dd4`, and the real footage place.
A checkout that is not the production clone neither syncs nor saves records.

**On which commit:** base `b2c2513a8cb9474a27d8982679ec205aaedefaec` (`src` tree `487ca39fc49320757cac967694140943f6264956`, `config` tree `99379828dec3738b54ce0839e53f3b66b980f35e`) plus this change's working-tree edits to `src/gr0wthlab/drafts.py`, `posts.py`, and `cli.py`.
`git status` before the run showed only this change's edits; the run's records were removed from the worktree afterwards and are not part of this change.
Configuration fingerprint: `b4f7ddb438a726eef5bda082e5fe6b63e80050d35bebd22bbdda412a3e490113`.

**Each run's identifier:** `20261109T051847Z-on-demand-1a63`, the one run.

**What the records showed:**

- Post Drafts, day 1: `queued` as `20261108-post-w1-day-01`, "with its finished video, its copy was approved as `20261101-post-w1-day-01`".
- The item says "You approved this day's copy as `20261101-post-w1-day-01` before its video existed; this item adds the video." and lists the claim at `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:472-500`.
- Filming, day 1: `finished`, `assets/window-1/day-01-c4935f1a55ef.mp4`, 9.00s, 1080x1920, 30 fps; ffprobe reads it as `yuv420p`, limited range.
- Days 2, 3, 5, 6, and 7: `kept`, each "its Draft is unchanged and passes, and so is its video"; day 4: approved earlier.

**What was not exercised:**

- A Draft with a moved citation and any other change: `SameCopyTest` in `src/tests/test_drafts.py` and `test_a_claim_citation_that_followed_moved_code_is_still_the_approved_copy` in `src/tests/test_filming.py`, which also drives `check-edits`.
- An approved item file that cannot be read: nothing beyond the code path that then compares the very file, as before this change.
- `boundary-check`: this change touches no boundary, runtime, fetch, or registry file.
