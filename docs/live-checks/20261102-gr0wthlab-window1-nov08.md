# Window 1 moves back one more week (FR-8)

No sitting took place on Sunday 2026-11-01.
That day's scheduled run, `20261102T000002Z-scheduled-0673`, queued post items for days 1 to 4, 6, and 7 with slots from 2026-11-02 to 2026-11-08 at 10:00, and day 1's slot on Monday 2026-11-02 passed with its video not cut.
Under those dates, a run from 2026-11-02 on would prepare days 2 to 14 only, as [the record of the last move](20261027-gr0wthlab-window1-dates.md) shows for a run the day after day 1, so day 1, which is AB-1's leg A, would be lost.
This change sets `window.first_sitting` in `config/run.json` to Sunday 2026-11-08, the Founder's choice of 2026-11-02, adds that move to `window.why`, and leaves the slot, 10:00, and every other setting as they were.
It changes none of the launcher code, the permission profile, the Codex command, the fetch policy, or the Product registry, so no boundary check was run.
Of `src/` it changes only the two tests that hold the committed window's values.

| Commit | Full hash | `src` tree | `config` tree |
| --- | --- | --- | --- |
| `main` before this change | `7178ef19780569a0c60b6d0517a2cce219704ab4` | `8494d47ac2824780425730a0385cb88ce568516e` | `131e367e9a7588c58629053ef6d031e5346e913d` |
| This change | the commit this record lands in | given by `git rev-parse <commit>:src` | given by `git rev-parse <commit>:config` |

## First round

### What was run

On 2026-11-02, Mac local time (PST), from this change's linked worktree with `config/run.json`, the PRD, and the two test files changed and not yet committed, under `/usr/bin/python3`, Python 3.9.6.
No Codex session ran; Codex CLI 0.160.0 is installed.
A scratch script outside the repository copied the worktree, without its `.git`, to a new folder in the Mac's temporary directory and made that copy a git checkout of its own with one commit, so `load_boundary` would accept it.
From that copy it loaded the `window` with `settings.load`, read the real calendar in `~/Mandu`, read-only, with `posts.context_plan`, and called `results.day_date`, `posts.slot_for`, `posts.target_days`, and `results.due`, the launcher's own date rules, for chosen dates.
It then took in the copy's records as a run on Monday 2026-11-02 at 16:00 would: `Ledger.load` read the copy's `ledger/review-queue/queue.json`, which is the queue run `20261102T000002Z-scheduled-0673` left, `posts.prepare` planned the days, and `posts.take` checked the copy's Drafts in `workspace/drafts/posts/window-1/` with no filming workflow, under the made-up run identifier `20261103T000000Z-on-demand-lab0`.
The copy was removed afterwards.
Nothing ran in the production clone `~/gr0wthlab`, no real records tree was written, and the LaunchAgent was not touched; `git status` in the worktree listed only the four changed files after the script ran.

### What the records showed

- `settings.load` raised no error: 2026-11-08 is a Sunday, and day 1 is Monday 2026-11-09.
- The calendar read days 1 to 14; `results.day_date` put day 1 on Monday 2026-11-09 and day 14 on Sunday 2026-11-22.
- `posts.slot_for` gave each of days 1 to 14 its date at 10:00 with offset `-08:00`, from `2026-11-09T10:00-08:00` to `2026-11-22T10:00-08:00`.
- The Mac's clock left daylight time at 02:00 on Sunday 2026-11-01: 01:59 that day is `-0700` (PDT) and 03:00 is `-0800` (PST), and the next change, on Sunday 2027-03-14, is after day 14, so no time change falls inside the window.

| Run on | `posts.target_days` | `results.due` |
| --- | --- | --- |
| Monday 2026-11-02 | days 1 to 7: "the week after the sitting on Sunday 2026-11-08 (2026-11-09 to 2026-11-15), and the days from tomorrow, 2026-11-03, up to that week" | none: "window 1's first Weekly Read is due on day 7, Sunday 2026-11-15" |
| Saturday 2026-11-07 | days 1 to 7: the same week, and the days from tomorrow, 2026-11-08, up to that week | none, the same |
| Sunday 2026-11-08 | days 1 to 7: "the week after the sitting on Sunday 2026-11-08 (2026-11-09 to 2026-11-15)" | none, the same |
| Monday 2026-11-09 | days 2 to 14: the week after the sitting on Sunday 2026-11-15 (2026-11-16 to 2026-11-22), and the days from tomorrow, 2026-11-10, up to that week | none, the same |
| Sunday 2026-11-15 | days 8 to 14: "the week after the sitting on Sunday 2026-11-15 (2026-11-16 to 2026-11-22)" | the day-7 read |
| Sunday 2026-11-22 | none: "no calendar day falls in the week after the sitting on Sunday 2026-11-22 (2026-11-23 to 2026-11-29)" | the day-14 read |

#### The open post items, on the copy

`posts.prepare` planned days 1 to 7, each with its new slot, and found an open post item for every day but day 5:

| Day | Open item | Its slot | New slot | `posts.take` | Item queued |
| --- | --- | --- | --- | --- | --- |
| 1 | `20261101-post-w1-day-01` | 2026-11-02 10:00 | 2026-11-09 10:00 | queued, "replaces `20261101-post-w1-day-01`" | `20261102-post-w1-day-01` |
| 2 | `20261101-post-w1-day-02` | 2026-11-03 10:00 | 2026-11-10 10:00 | queued, "replaces `20261101-post-w1-day-02`" | `20261102-post-w1-day-02` |
| 3 | `20261101-post-w1-day-03` | 2026-11-04 10:00 | 2026-11-11 10:00 | queued, "replaces `20261101-post-w1-day-03`" | `20261102-post-w1-day-03` |
| 4 | `20261101-post-w1-day-04` | 2026-11-05 10:00 | 2026-11-12 10:00 | queued, "replaces `20261101-post-w1-day-04`" | `20261102-post-w1-day-04` |
| 5 | none | none | 2026-11-13 10:00 | blocked | none |
| 6 | `20261101-post-w1-day-06` | 2026-11-07 10:00 | 2026-11-14 10:00 | queued, "replaces `20261101-post-w1-day-06`" | `20261102-post-w1-day-06` |
| 7 | `20261101-post-w1-day-07` | 2026-11-08 10:00 | 2026-11-15 10:00 | queued, "replaces `20261101-post-w1-day-07`" | `20261102-post-w1-day-07` |

- In the ledger `posts.take` left, each of the six open items was `superseded` with `superseded_by` naming the item queued in its place, and each new item was `open` with its new slot and `supersedes` naming the old one.
- The new item files held the new slot: `20261102-post-w1-day-01.md` has `slot: 2026-11-09T10:00-08:00` and the line "Slot: Monday 2026-11-09 10:00 (-08:00).", and `20261102-post-w1-day-07.md` has `slot: 2026-11-15T10:00-08:00` and "Slot: Sunday 2026-11-15 10:00 (-08:00).".
- None of the six open items named a video, so no video was carried over or dropped.

### Tests

- The whole unit suite, `/usr/bin/python3 -m unittest discover -s src/tests -t src` from the worktree's root, ran with this change's four files changed: 1548 tests in 2330.505 seconds, none failed.
- `ruff check` and `ruff format --check` on the two changed test files passed, with ruff 0.15.20.

### What this round did not exercise

- A real weekly run in the production clone, with a real agent writing new Drafts and the filming workflow cutting videos for these dates: the copy's take-in checked the Drafts run `20261102T000002Z-scheduled-0673` left, with no filming workflow, and the queue it changed was never saved.
- Day 5's failing check: the script printed its result, blocked, and not its checks; run `20261102T000002Z-scheduled-0673`'s report shows day 5 blocked by one failing check of the same Draft.
- CI's run on Linux with the latest Python.
