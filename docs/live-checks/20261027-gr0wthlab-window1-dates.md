# Window 1 moves back one week (FR-8)

No sitting took place on Sunday 2026-10-25 and no batch for days 1 to 7 was approved, because that day's scheduled run refused to start while the repository was public.
Under the dates [the Waitlist change](20261021-gr0wthlab-waitlist-live.md) set, day 1 was Monday 2026-10-26, and `posts.target_days` gives days 3 to 14 for a run on Tuesday 2026-10-27, days 4 to 14 on Wednesday 2026-10-28, days 7 to 14 on Saturday 2026-10-31, and days 8 to 14 on Sunday 2026-11-01, so no run from 2026-10-27 on would prepare days 1 and 2.
This change sets `window.first_sitting` in `config/run.json` to Sunday 2026-11-01, the Founder's choice of 2026-10-27, and leaves the slot, 10:00, and every other setting as they were.
It changes none of the launcher code, the permission profile, the Codex command, the fetch policy, or the Product registry, so no boundary check was run.
Of `src/` it changes only the two tests that hold the committed window's values.

| Commit | Full hash | `src` tree | `config` tree |
| --- | --- | --- | --- |
| `main` before this change | `6776dd0429ac383a15d0b68d95af0547f0fa52b8` | `1d6476aeaf4499339dda759e3158a181e99fbfb5` | `142866d3a94a2a9c9fbff96d6cb0d2e82468b565` |
| This change | the commit this record lands in | `8494d47ac2824780425730a0385cb88ce568516e` | `131e367e9a7588c58629053ef6d031e5346e913d` |

## First round

### What was run

On 2026-10-27, Mac local time (PDT), from this change's linked worktree with `config/run.json` changed and not yet committed, under `/usr/bin/python3`, Python 3.9.6.
That `config/run.json` held `window.first_sitting` 2026-11-01 under the old `window.why`; its `config` tree was `3604b1c2f7aac24979fd4223d59c4a5184978f1d`.
No Codex session ran; Codex CLI 0.160.0 is installed.
A scratch script outside the repository loaded this branch's `window` with `settings.load_window` against the schedule's day, `sunday`, read the real calendar `projects/RepToday/gtm/05-social-pmf/cadence-14-day.md` in `~/Mandu`, read-only, with `kit.parse_calendar`, and called `results.day_date`, `posts.target_days`, and `results.due`, the launcher's own date rules, for chosen dates.
Nothing ran in the production clone `~/gr0wthlab`, and the LaunchAgent was not touched.

### What the records showed

- `settings.load_window` raised no error: 2026-11-01 is a Sunday, and day 1 is Monday 2026-11-02.
- `kit.parse_calendar` read days 1 to 14; `results.day_date` put day 1 on Monday 2026-11-02 and day 14 on Sunday 2026-11-15, and each day's date at the slot, 10:00, in the Mac's time zone was `-0800` (PST) on every day.
- The Mac's clock leaves daylight time at 02:00 on Sunday 2026-11-01: 01:59 that day is `-0700` (PDT), and 10:00 and the schedule's 16:00 that day are `-0800` (PST), so the first sitting's day and every posting slot of the window fall after the change, at 10:00 local.
  A run due at 16:00 on 2026-10-27 is `-0700`.

| Run on | `posts.target_days` | `results.due` |
| --- | --- | --- |
| Tuesday 2026-10-27 | days 1 to 7: "the week after the sitting on Sunday 2026-11-01 (2026-11-02 to 2026-11-08), and the days from tomorrow, 2026-10-28, up to that week" | none: "window 1's first Weekly Read is due on day 7, Sunday 2026-11-08" |
| Saturday 2026-10-31 | days 1 to 7, the same week | none, the same |
| Sunday 2026-11-01 | days 1 to 7: "the week after the sitting on Sunday 2026-11-01 (2026-11-02 to 2026-11-08)" | none, the same |
| Monday 2026-11-02 | days 2 to 14: the week after the sitting on Sunday 2026-11-08, and the days from tomorrow up to that week | none, the same |
| Sunday 2026-11-08 | days 8 to 14: "the week after the sitting on Sunday 2026-11-08 (2026-11-09 to 2026-11-15)" | the day-7 read |
| Sunday 2026-11-15 | none: "no calendar day falls in the week after the sitting on Sunday 2026-11-15" | the day-14 read |
| Sunday 2026-11-22 | none | none: "window 1's Weekly Reads are behind it" |

### Tests

- The whole unit suite ran under `/usr/bin/python3` with only `config/run.json` changed: 1548 tests, 2 failed, `test_window_1_starts_after_the_sitting_the_founder_set_at_the_slot_the_founder_set` in `src/tests/test_config_files.py` and `test_day_1_follows_the_window_s_first_sitting_which_only_the_founder_sets` in `src/tests/test_settings.py`, the two that hold the committed first sitting and day 1.
- After those two were changed to hold 2026-11-01 and 2026-11-02, `tests.test_config_files` and `tests.test_settings` ran again: 34 tests, none failed.
  The whole suite was not run again.
- `ruff check` and `ruff format --check` on the two changed test files passed, with ruff 0.15.20.

### What this round did not exercise

- A real weekly run in the production clone, with a real agent writing real Drafts for these dates: the Founder starts this week's run after this change merges.
- A lab run of the whole cycle on the new dates: the date rules above are the ones a run calls, and a whole run on set dates stands on the Waitlist change's lab round and on `src/tests/`.
- CI's run on Linux with the latest Python.

## After review

### What was run

On 2026-10-27, Mac local time (PDT), from this change's linked worktree, under `/usr/bin/python3`, Python 3.9.6.
Review found that `window.why` in `config/run.json` still said only that the first sitting was Sunday 2026-10-25.
It gained one sentence: on 2026-10-27 the Founder moved the first sitting back one week to Sunday 2026-11-01, so day 1 is Monday 2026-11-02 and day 14 Sunday 2026-11-15, with the slot still 10:00.
This round changed no value in `config/run.json` and nothing in `src/`.
The command, run from `src/`, was `/usr/bin/python3 -m unittest tests.test_config_files tests.test_settings`.
No Codex session ran.

### What the records showed

- 34 tests ran, none failed.

### What this round did not exercise

- The date rules of the first round, which read the window's values and not `window.why`: they stand on the first round.
- The whole unit suite and CI's run on Linux with the latest Python.

## After the second review

### What was run

On 2026-10-27 at 16:47 PDT, from this change's linked worktree, under `/usr/bin/python3`, Python 3.9.6, with `git status` empty before the run.
Review found that the opening said a run before 2026-11-01 under the old dates would prepare days 8 to 14, and that the first round credited `results.day_date`, which gives a date, with each day's time and offset.
A script given to `/usr/bin/python3` on its standard input, run from `src/`, read the real calendar in `~/Mandu`, read-only, with `kit.parse_calendar`.
It loaded this change's `window`, and the same `window` with `first_sitting` 2026-10-25, with `settings.load_window` against `sunday`, and called `posts.target_days`, `results.due`, `results.day_date`, and `posts.slot_for`.
No Codex session ran, nothing ran in the production clone `~/gr0wthlab`, and the LaunchAgent was not touched.
This round then changed only this record.

### What the records showed

- `kit.parse_calendar` read days 1 to 14.
- With `first_sitting` 2026-10-25, `settings.load_window` put day 1 on Monday 2026-10-26, and `posts.target_days` gave:

| Run on | `posts.target_days` |
| --- | --- |
| Tuesday 2026-10-27 | days 3 to 14: "the week after the sitting on Sunday 2026-11-01 (2026-11-02 to 2026-11-08), and the days from tomorrow, 2026-10-28, up to that week" |
| Wednesday 2026-10-28 | days 4 to 14: the same week, and the days from tomorrow, 2026-10-29, up to that week |
| Saturday 2026-10-31 | days 7 to 14: the same week, and the days from tomorrow, 2026-11-01, up to that week |
| Sunday 2026-11-01 | days 8 to 14: "the week after the sitting on Sunday 2026-11-01 (2026-11-02 to 2026-11-08)" |

- With this change's `window`, `posts.target_days` and `results.due` gave, for each date in the first round's table, the days and the quoted words its row shows.
- `results.day_date` gave Monday 2026-11-02 for day 1 and Sunday 2026-11-15 for day 14, and `posts.slot_for` gave each of days 1 to 14 its date at 10:00 with offset `-08:00`, from `2026-11-02T10:00-08:00` to `2026-11-15T10:00-08:00`.

### What this round did not exercise

- The unit tests: this round changed only this record, and they stand on the round after review.
- Everything the first round did not exercise.
