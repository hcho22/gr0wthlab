# The Waitlist is live, and window 1 has its dates (US-ME05, US-ME06, FR-8, FR-9)

RepToday's Waitlist went live on `reptoday.app` on 2026-10-21, and US-ME05's Validation Test passed there, as RepToday's go-live record shows ([`artifacts/reports/US-WL12/validation.md`](https://github.com/hcho22/RepToday/blob/main/artifacts/reports/US-WL12/validation.md), merged in https://github.com/hcho22/RepToday/pull/211).
This change names the anonymous view RepToday's own job writes in `config/products.json`, sets `waitlist.live_since` to 2026-10-21 in `config/run.json`, and sets window 1's first sitting to Sunday 2026-10-25 and its slot to 10:00, the Founder's choices of 2026-10-21.
It changes no launcher code, the permission profile, the Codex command, or the fetch policy; it changes the Product registry, so the boundary was checked again below.

Every check below ran on 2026-10-21, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran.
A run identifier carries its time in UTC.

| Commit | Full hash | `src` tree | `config` tree |
| --- | --- | --- | --- |
| `main` before this change | `df34b86a0237df8b353cba1c776fdb08ed8742ad` | | |
| This change | `84be180c21c7cd2cf33288e0218fa1b22136623d` | `5e7f8e2a75d203a181ef96e3c2e7300e9e7e2255` | `4cf438e622559bd9446bd809a1bf0458038a09fc` |

## First round

### The view RepToday writes, through gr0wthlab's reader

- The view is the one file `~/Library/Application Support/RepToday/waitlist/waitlist-view.json`, owner-only (`0600`), which RepToday's job `app.reptoday.waitlist-daily` writes.
  Nothing in gr0wthlab wrote, moved, or started anything there or in RepToday's job, its Keychain item, Kit, or Convex.
- A scratch script loaded this branch's configuration through `settings.waitlist`, which raised no error, so the path lies outside every location the sandbox reads, and read the file once with `waitlist.read`, the launcher's own reader, which runs its address check over the whole file before anything else.
  At 15:21 the file's modification time was 22:14:53 UTC, and at 16:33 it was 23:14:55 UTC; each read gave status `read`, "sign-ups 0, good-Fit opt-ins 0 of about 50", generated at the file's own modification time.
  The script printed no entry identifier; the view had none to print.
- The format agrees on both sides, read from RepToday's `main` at `6249e4a`, read-only: `tools/waitlist/contract.json` lists the same Source tags, Fit answers, top keys, entry keys, entry pattern, view version 1, and byte limit as the Waitlist Dispatch request (`src/dispatches/reptoday-waitlist.md`) and `src/gr0wthlab/waitlist.py`, and `build_view` in `tools/waitlist/wl_core.py` writes exactly those five fields per entry, `fit` as null for an answer outside the list, and `signed_up_on` as the UTC date.
  The view holds a sign-up only once its email is confirmed, which the request leaves to RepToday.

### US-ME05's Validation Test

The Founder's two sign-ups were made on the morning of 2026-10-21 and are recorded in RepToday's go-live record, under "The rehearsal".
That record, not this change, is where the steps were observed:

- The Founder signed up once through `reptoday.app/tiktok` and once through plain `reptoday.app`, and confirmed both.
- RepToday's job produced the view, and gr0wthlab's reader, run read-only from the production clone, read it with status `read`: one entry with Source `tiktok`, one with Source `unknown`, each with the Fit answer the Founder chose, and no address in the file.
- Neither entry holds a beta opt-in, though the Founder remembered ticking the box for the TikTok sign-up.
  The record explains it: the page's two sign-up forms each have their own box, and a box ticked in one form is not sent with the other form's Join.
- RepToday's production events counted `landing_page_view` and `waitlist_signup` by `referrer_source`, one per page load and per accepted sign-up.
- Those sign-ups were removed afterwards, which is why the view above has no entries.

What this change observed itself:

- `https://reptoday.app/privacy`, fetched once with `curl` at 23:03:28 UTC, answered `200`, "Last updated: October 21, 2026", with section 11, "The waitlist": what is collected, why, how long it is kept, how to be removed, and who sees the address.
- The Founder's approval of the Dispatch request: `ledger/founder/decisions/20261016-reptoday-waitlist.json` records `approve` at the sitting of 2026-10-18, and its Evidence in `ledger/evidence/decisions/` was taken in by run `20261019T133323Z-on-demand-c2e0`.

### A run once the Waitlist is live and the window is set

A lab of `src/tests/`'s own harness (`CycleTestCase` in `src/tests/test_cycle.py`): a throwaway checkout in the Mac's temporary folder with this branch's `waitlist` and `window` values from `config/run.json`, the synthetic kit and code of `src/examples/post-drafts/`, the no-model stand-in for Codex (`tests.fakes.install_codex`) writing the synthetic Drafts, and no network.
Nothing in it posts or sends, and it is not the production clone.

| Run at (Mac local) | What the records showed |
| --- | --- |
| Sunday 2026-10-25 16:00 PDT | The brief and the report: "Window 1 begins on Monday 2026-10-26, the day after its first sitting; this run prepares days 1 to 7: the week after the sitting on Sunday 2026-10-25 (2026-10-26 to 2026-11-01)." 6 post items queued, each slot day N at 10:00 from Monday 2026-10-26 to Sunday 2026-11-01, each item reading "The Waitlist is live."; no "Nothing can be published" in the report and no "not live" in the brief. Weekly Read: "window 1's first Weekly Read is due on day 7, Sunday 2026-11-01". |
| Sunday 2026-11-01 15:00 PST | "this run prepares days 8 to 14: the week after the sitting on Sunday 2026-11-01 (2026-11-02 to 2026-11-08)"; days 8 to 13 queued at 10:00 from Monday 2026-11-02 to Saturday 2026-11-07, each "The Waitlist is live."; the day-7 Weekly Read due from Sunday 2026-11-01, covering days 1 to 5, with the notice to give its numbers on the sitting page. |
| Sunday 2026-11-08 15:00 PST | No calendar day left to prepare; the day-14 Weekly Read due from Sunday 2026-11-08, covering days 1 to 13. |

Day 5 was blocked by one failing check of the stand-in's Draft in the first run, and the synthetic kit has no Draft for day 14, so neither was queued; each is the synthetic kit's, and the real calendar's days are below.

The launcher's own date rules on the real calendar, `projects/RepToday/gtm/05-social-pmf/cadence-14-day.md` in `~/Mandu`, read-only, with this branch's configuration: `kit.parse_calendar` read days 1 to 14, `results.day_date` put day 1 on Monday 2026-10-26 and day 14 on Sunday 2026-11-08, each at 10:00 local, and the offset went from `-0700` to `-0800` on day 7, Sunday 2026-11-01, when the Mac's clock leaves daylight time, with the slot still 10:00.
`posts.target_days` prepares days 1 to 7 on 2026-10-21 and 2026-10-25, days 8 to 14 on 2026-11-01, and none on 2026-11-08; `results.due` gives the day-7 read on Sunday 2026-11-01, the evening the calendar names for its midpoint review, and the day-14 read on Sunday 2026-11-08.
No gr0wthlab code or check asks for an evening slot: `settings.load_window` takes any `HH:MM`.

### The boundary

From this work's linked worktree at `84be180c21c7cd2cf33288e0218fa1b22136623d`, against Mandu and the Product checkouts as they are, with `git status` empty before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `65c0362d7e73a1bc164001414c11a4aa2d3153d5c3658a53128ae58b4f09bb45`.

- `src/bin/gr0wthlab preflight`, at 16:32:07, passed: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 16:32:16 to 16:33:17, passed at its first attempt as `20261021T233218Z-on-demand-c93f`: 49 steps to prove, 33 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials and no shell target without one, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- The whole unit suite ran under `/usr/bin/python3`, Python 3.9.6, in this worktree on the path change alone: 1508 tests, 2 failed, the two that held the committed registry's view to null.
- After those two were changed to hold the reviewed path, and the tests' throwaway checkouts were given no view and no live date unless a test sets one, the whole suite ran again on the `src` and `config` trees of `84be180c21c7cd2cf33288e0218fa1b22136623d`: 1508 tests, none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab` passed, with ruff 0.15.20.
- CI's run on Linux with the latest Python was not part of this round.

### What this round did not exercise

- The Founder's two sign-ups, their Sources, Fit answers, and opt-ins, and the web event counts were observed in RepToday's record, not by this change: gr0wthlab reads nothing of RepToday's database, Kit, or the page, and the view now holds no entries, so this change read only an empty view.
  The reader's handling of entries in RepToday's format stands on `src/tests/test_waitlist.py` and on the rehearsal's read with status `read`.
- A real weekly run on the production clone, which first reads the view and writes Waitlist Evidence at the run after this change merges.
- A real agent writing real Drafts for the real calendar: the lab's Drafts were the stand-in's, on the synthetic kit.
