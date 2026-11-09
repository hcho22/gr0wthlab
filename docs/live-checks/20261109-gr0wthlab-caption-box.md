# On-screen text in Bone on a Night box

This change draws every video's on-screen text and captions in Bone (`#F1EEE8`) on a solid Night (`#14181C`) box behind each line, in place of white text with a black outline and no box (`video.subtitles`, `config/platforms.json` `video.text`).
The Founder found the white text hard to read over the app's own white text, chose the boxed style from a preview of day 2 on 2026-11-09, and the colours are the dark palette for video in RepToday's brand guidelines (`projects/RepToday/gtm/02-brand/brand-guidelines.md`, section 4).
It serves US-ME09.

## Round 1: a run on the real records

**What was run:** `caffeinate -i ./src/bin/gr0wthlab run`, typed in a linked worktree of the production clone on branch `fm/gr0wthlab-caption-box`, Monday 2026-11-09 11:26 PST, with Codex CLI `codex-cli 0.160.0`.
The worktree held `origin/main` at `2ae8eaf18b13c984efbce2d9cc05a73b5adffa0b`, the records the production clone pushed after run `20261109T175145Z-on-demand-7f18`, with this change applied and uncommitted.
It read the real Mandu package, the real RepToday checkout at `58f6dd4`, and the real footage place.
A checkout that is not the production clone neither syncs nor saves records.

**On which commit:** base `2ae8eaf18b13c984efbce2d9cc05a73b5adffa0b` (`src` tree `febbb5868fbba52f2981ec4559139a5a2c0e7e70`, `config` tree `99379828dec3738b54ce0839e53f3b66b980f35e`) plus this change's working-tree edits to `src/gr0wthlab/video.py`, `src/tests/test_video.py`, and `config/platforms.json`.
`git status` before the run showed only those edits; the run's records were removed from the worktree afterwards and are not part of this change.
Configuration fingerprint: `3f380bec216908fe7e59276a72f1676345a94f4aba9a3cc92eb1838403f331ae`.

**Each run's identifier:** `20261109T192643Z-on-demand-1bca`, the one run.

**What the records showed:**

- Filming: the videos of days 2, 3, 5, 6, 7, 8, 9, 10, 12, and 13 were rendered again this run, since the canvas each is cut with changed, and each measured 1080x1920 at 30 fps for its edit record's length.
- Post Drafts: each of those days was queued again with its new video, replacing the item that showed the white-text video; day 4 has no edit record, and day 11 is still blocked by its own unsupported claim.
- A frame of each new video, read by eye, shows its text in Bone on a Night box, one box to a line, readable over the app's own text; day 6's four-line caption covers the top of the card beneath it.

**What was not exercised:**

- A caption of a spoken line on real footage: no Draft in window 1 has a spoken line, so only on-screen text was drawn; the caption style is held by `ComposeTest.test_text_is_drawn_inside_the_safe_zone_in_bone_on_a_night_box`.
- `boundary-check`: this change touches no boundary, runtime, fetch, or registry file.
