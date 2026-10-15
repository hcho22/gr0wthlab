# Live checks: a Hook no code supports goes to the Founder as a proposal (US-ME08, FR-7)

This file records what was run on the Founder's Mac for the change to the Post Drafts task definition, `src/instructions/weekly-run/post-drafts.md`, that has the session put a frozen Hook no code supports to the Founder as one package-change proposal, which words no new Hook and so needs no quote record.
The Founder decided on 2026-10-14 to fix it, after the learning loop's live checks found Post Drafts example 16 failing on every live run ([its record](20261014-gr0wthlab-learning-loop.md#round-6-examples-that-could-never-do-worse)).
CI cannot run any of it: it needs the Mac and the Codex login.

How to read the paths:

- `<tmp>` is the Mac's per-user temporary folder, the one `getconf DARWIN_USER_TEMP_DIR` prints.
- `<lab>` is the throwaway folder `<tmp>/gr0wthlab-hook-lab`, which held two clones of this repository: `<lab>/main` at `main` and `<lab>/branch` at this change.

All times are Mac local time (PDT, UTC-7) on 2026-10-15.
Every lab run's identifier starts `20261011T230000Z`, since each lab runs at the fixed time an example's lab uses (`examples.DEFAULT_AT`), not at the Mac's clock.
Codex CLI 0.160.0 with `gpt-6-luna` at `high` reasoning effort throughout, as each session's own record names them.

## What nothing here touched

Up to round 5 the change is text the agent reads and nothing else: no launcher code, no `config/`, no permission profile, no example set.
Round 6 adds launcher code that writes what a session's brief says of the Review Queue (`report.item_lines`), and nothing that starts, bounds, or grants a session anything.
So neither `src/bin/gr0wthlab preflight` nor `src/bin/gr0wthlab boundary-check` was run on its own for it; in round 6, the preflight a run makes before each session printed that it refused 21 paths and allowed 6 areas before all 64 sessions.
Every live run here was a lab run: its own synthetic Mandu, RepToday, and Immerse, built by `examples.build` from the Post Drafts example set's kit and code, and pointed to by the lab's `GR0WTHLAB_*` settings, so no run read or wrote the real checkouts.
`git status` in both clones was empty after the last run.

## The commits

| Side | Commit | `src` tree | `config` tree |
| --- | --- | --- | --- |
| Before, `main` | `dc4fb88fdd54bf83e5aaab59779bfd1ff441482b` | `0a725c861a31a32c9253124e38c8164dbf00e515` | `578d1984f76e95cc63e37cdd6f720a68a8872f92` |
| With the change | `48e52f89ae7fec7480f04514162fe5a0a2b8657b`, the fix before its message was reworded | `654a3452ef56c2532a54b1d7419ae2951fc33a56` | `578d1984f76e95cc63e37cdd6f720a68a8872f92` |

Both sides ran with the same Instructions in force, `ledger/instructions/post-drafts.md` as `main` holds it.

## How each example was run

A scratch script called the clone's own `examples.run_example`, the function the learning loop's gate calls, with that clone as the repository, the Instructions in force as the text, a 600-second limit, and the clone's own task definitions, so the only difference between the sides was the task definition.
Each call built one lab under `<lab>`, ran one Post Drafts session in it through the launcher, read the example's deterministic assertions off what the lab's launcher took in, and kept the lab's `workspace/` and `ledger/` for reading before removing it.

## Round 1: example 16 on `main`

Run from 05:11 to 05:14, three at a time.

| Run | Assertions held | The one that failed | Agent time | Cost |
| --- | --- | --- | --- | --- |
| `20261011T230000Z-on-demand-2c79` | 2 of 3 | `queued: 1 package-change-proposal`: 0 queued | 163 s | about $0.017 |
| `20261011T230000Z-on-demand-3dd8` | 2 of 3 | the same | 94 s | about $0.009 |
| `20261011T230000Z-on-demand-bda8` | 2 of 3 | the same | 97 s | about $0.010 |

In each, `check-drafts` blocked day 2 by `claim-unsupported` with the Hook unchanged, and the session wrote nothing to `incoming/`.
Each session's closing summary gave the same reason, in its own words:

- 2c79: "I couldn't write the required package-change proposal: the run's Evidence contains only the package snapshot, and the required listening quote record is unavailable."
- 3dd8: "I couldn't write the package-change proposal: changing the Hook would be a new Angle, which requires a citation to a listening quote record."
- bda8: "The package instructions call for a new-Angle proposal in that case, but the required `ledger/evidence/listening/quotes/` directory is absent".

Each closed with `Session: incomplete`, naming the missing quote record.
The reading matches step 2 of the task definition on `main`, which follows the instruction to write a proposal citing both sides with "A proposal that would change a Hook, signal, or kill criterion is a proposal for a new Angle: it declares `new_angle: yes` and needs sourced pain."
The change keeps the proposal and says what it is: it puts the conflict to the Founder, words no new Hook, signal, or kill criterion, declares `new_angle: no`, and needs no quote record; only a proposal that words a new or changed one is a new Angle.

## Round 2: the example set, both sides

Run from 05:15 to 05:20.
Example 16 ran three times with the change; every other example the agent re-runs ran once on each side.
The script that ran this round started all its runs at once rather than six at a time as intended, so 21 sessions ran together beside two weekly lab runs (round 3).

| Example | `main` | With the change |
| --- | --- | --- |
| 1 | 4 of 4 (`1177`) | 4 of 4 (`a98e`) |
| 2 | 3 of 3 (`0b1b`) | 3 of 3 (`a693`) |
| 8 | 1 of 1 (`8aec`) | 1 of 1 (`bb15`) |
| 16 | 2 of 3, 2 of 3, 2 of 3 (round 1) | 3 of 3 (`2308`), 3 of 3 (`c175`), 3 of 3 (`e747`) |
| 17 | 5 of 5 (`a5e6`) | 5 of 5 (`577b`) |
| 18 | 4 of 4 (`82fc`) | 4 of 4 (`2d5a`) |
| 19 | 4 of 4 (`e642`) | 4 of 4 (`51e9`) |
| 20 | 5 of 5 (`a0d5`) | 5 of 5 (`42a1`) |
| 21 | 2 of 3 (`e21d`) | 3 of 3 (`c114`) |
| 22 | 3 of 3 (`3259`) | 3 of 3 (`93d2`) |

Each cell's run is `20261011T230000Z-on-demand-` and the four characters shown.
Example 21's failing assertion on `main` was `queued: 1 package-change-proposal citing brand-rules.json`, with 0 queued.
No assertion that held on `main` failed with the change.

Example 22 on `main` ran twice from one start of the scratch script, which was edited while it ran.
The first run, `20261011T230000Z-on-demand-7ba8`, ended with exit code 0, and its session's own record shows it wrote the day 1 Draft and one file in `incoming/`; its assertions were not read, since the second run's result replaced them.
The table counts the second run, `3259`.

Each of the three proposals queued for example 16 with the change declares `new_angle: no`, proposes no replacement Hook, cites the Hook at `projects/RepToday/gtm/05-social-pmf/angles.md` line 8 and lines of the RepToday code (`App/ReadyScreen.swift`, `Engine/ConsistencyScore.swift`), and says the Founder chooses between the Product doing what the Hook says and a later proposal that changes the Hook.
Their titles: "Resolve the unsupported five-day comeback Hook", "Resolve the P02 welcome-back Hook and code conflict", "Resolve the unsupported P02 welcome-back behavior".

What the sessions cost, as the lab runs' records give agent time and cost:

| Side | Sessions | Agent time | Cost | Per session |
| --- | --- | --- | --- | --- |
| `main` | 12 (example 16 three times, nine others once, the counted run of example 22) | 1,532 s | about $0.141 | 128 s, about $0.012 |
| With the change | 12 | 1,735 s | about $0.173 | 145 s, about $0.014 |

The first run of example 22 on `main` (`7ba8`) is not in these sums.

## Round 3: whole weekly runs in a lab

A second scratch script built a lab the same way, with no day filter or with the days named below, gave the run a bound of 7,200 seconds, and ran one whole weekly run in it (`cycle.Cycle` with every workflow), on each side.
In each, the Package review and Post Drafts sessions were due, and no other session was.

### Days 1, 2, 3, 6, and 7: one Hook no code supports

Run from 05:20 to 05:30.
Of these days only day 2's Hook, P02's, has no code behind it in the example set's code.

| | `main`, `20261011T230000Z-on-demand-f1e7` | With the change, `20261011T230000Z-on-demand-58dc` |
| --- | --- | --- |
| Days 1, 3, 6, 7 | queued | queued |
| Day 2 | blocked by `claim-unsupported` | blocked by `claim-unsupported` |
| Post Drafts proposals queued | 0 | 1, `20261011-p02-welcome-back-hook-unsupported` |
| Package review proposals queued | 1, on P03's primary platform | 1, on P03's primary platform |
| Post Drafts agent time and cost | 240 s, about $0.019 | 554 s, about $0.049 |
| Post Drafts closing line | `Session: incomplete: P02 package-change proposal; no sourced listening quote record exists to support its required new-angle evidence.` | `Session: complete` |

Both runs also queued the filming plan, the RepToday Waitlist Dispatch request, and the run-problems notice.
The change's proposal declares `new_angle: no`, cites P02's Hook at `angles.md` line 8 and `App/ReadyScreen.swift` lines 8-10 and `Engine/ConsistencyScore.swift` lines 5-7, and ends "This proposal supplies no replacement Hook; the Founder decides which side to change."
The change's Post Drafts session record shows six changes to the day 6 and day 7 Drafts after its first `check-drafts`, three before it wrote the proposal and three after.

### Days 1 to 7, the first batch of the whole calendar

Run from 05:16 to 05:20.
Of these days, day 2's Hook has no code behind it, and day 5's Angle depends on the claim the open checklist line 12 holds.

| | `main`, `20261011T230000Z-on-demand-c023` | With the change, `20261011T230000Z-on-demand-cf66` |
| --- | --- | --- |
| Days 1, 3, 6, 7 | queued | queued |
| Day 2 | blocked by `claim-unsupported` | blocked by `claim-unsupported` |
| Day 4 | blocked by `claim-unsupported`, its claim listed with `Code: none` | queued, its claim citing `Engine/SessionBuilder.swift:3-5` |
| Day 5 | blocked: `claim-unsupported` for its Hook, and checklist line 12 | the same |
| Post Drafts proposals queued | 0 | 2: `20261011-founder-comeback-claim` (day 2) and `20261011-speed-benchmark-conflict` (day 5, citing checklist line 12) |
| Package review proposals queued | 1, on the calendar's primary platforms | 0 |
| Post Drafts closing line | `Session: incomplete: no sourced listening quote record was available to support the required new-Angle package-change proposal for the blocked Hooks.` | `Session: complete` |

Both of the change's proposals declare `new_angle: no` and propose no replacement Hook, signal, or kill criterion.

## Round 4: the unit tests

Each ran in a clone of its own under `<lab>`, while other work also ran on the Mac.

| Command | Where | What it printed |
| --- | --- | --- |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | a clone of `main` at `dc4fb88`, from 05:07 | 1,388 tests OK in 4,124 seconds |
| `/usr/bin/python3 -m unittest tests.test_sessions tests.test_examples tests.test_example_runs`, from `src/` | `<lab>/branch` | 48 tests OK in 726 seconds |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | a clone of this change with the record, whose tree is `805546b6ce2bdc270cc45a559d40609963cdf944` | 1,388 tests OK in 3,777 seconds |
| `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab`, ruff 0.15.20 as CI installs it | this change's worktree | all checks passed; 101 files already formatted |

## Round 5: example 16 on the merged head

`main` moved two changes while this branch waited, the Dispatch wording fix (#24) and the Weekly Read (#25).
Merge commit `6155b45e8ba3dc8ea19db71ad3bd2ce7c385d77b` (`src` tree `15b9406344669caa785e24ac58ba678cbed46501`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`) brought in `main` at `3789b3f`.
The merge changed three things a Post Drafts session reads: `src/instructions/weekly-run/common.md` and `items.md` now name the Weekly Read decision item and a Dispatch request where a session says so, and the example set's kit gained `projects/RepToday/gtm/05-social-pmf/read-the-results.md`.
`post-drafts.md`, `ledger/instructions/post-drafts.md`, and example 16's own entry and Draft file did not change.

Example 16 ran three more times on that commit, from a clone under `<lab>`, the same way as round 2, from 12:12 to 12:13.

| Run | Assertions held | Agent time | Cost |
| --- | --- | --- | --- |
| `20261011T230000Z-on-demand-c74e` | 3 of 3 | 76 s | about $0.010 |
| `20261011T230000Z-on-demand-b6dd` | 3 of 3 | 71 s | about $0.008 |
| `20261011T230000Z-on-demand-6df7` | 3 of 3 | 78 s | about $0.011 |

Each queued proposal declares `new_angle: no` and cites the Hook at `projects/RepToday/gtm/05-social-pmf/angles.md` line 8 and lines of the RepToday code (`Engine/ConsistencyScore.swift` in two, `App/ReadyScreen.swift` in one).
The rest of the example set and the weekly lab runs were not run again on this commit; they stand on rounds 2 and 3.

## Round 6: a second weekly run while the proposal is open

The gate's test of `c951a73` ran two weekly runs one after the other in 8 fresh labs, leaving the first run's Hook proposal open, and in 1 of the 8 the second run queued a reworded copy of it beside the open one.
In that lab the first session had given the proposal the identifier `20261015-score-dip-hook-code-conflict` and the title "Resolve the score-dip Hook and shipped behavior conflict", which name P03's subject, though its text is about P02's Hook.
The brief listed each open item by identifier and title alone, and the launcher refuses an item only when its kind, title, and text match a queued one's (`exchange.item_hash`), so nothing caught the copy.
This record had said, under "What was not exercised", that the launcher's refusal would; it covers only a copy that keeps the wording.

The fix is in the brief: each open and decided package-change proposal is listed with its item file, and a session that may write items is told that a title may not name all a proposal asks, and to read each one's file before it writes a proposal (`report.item_lines`).
`test_a_session_is_told_the_file_of_each_proposal_whatever_its_title_names` in `src/tests/test_cycle.py` holds that the brief names each file, and fails on the brief before the fix.

Each lab was built like round 3's, from the Post Drafts example set by `examples.build`, with calendar days 1 to 3, and ran two on-demand runs through `src/bin/gr0wthlab run` at the Mac's clock.
Between the two runs, a script put the failed lab's proposal in place of the P02 proposal the first run had queued, word for word: its title, Proposal, Touches, and Evidence, under the first run's front matter.
In batch 2 it also gave it the failed lab's identifier.
Each side ran from a clone of its own under `<tmp>`: `c951a73` (`src` tree `15b9406344669caa785e24ac58ba678cbed46501`), and `c951a73` with the fix (`src` tree `df6767a1b871cca1d946fb82b3d6e227bce12856`); both have `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
Batch 1 ran from 12:48 to 12:57, and batch 2 from 12:58 to 13:04, its eight labs side by side.

| Batch | Lab | Side | First run | Second run | Second run's Post Drafts session opened the proposal's file | P02 Hook proposals the second run queued |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | h1 | `c951a73` | `0bc6` | `0711` | no | 0 |
| 1 | h2 | `c951a73` | `5f42` | `b7cf` | yes | 0 |
| 1 | h3 | `c951a73` | `45e1` | `098e` | no | 1, `20261015-founder-comeback-hook-code-mismatch` |
| 1 | h4 | `c951a73` | `a470` | `1862` | no | 0 |
| 1 | f1 | with the fix | `0ffc` | `2278` | yes | 0 |
| 1 | f2 | with the fix | `19fb` | `4e28` | yes | 0 |
| 1 | f3 | with the fix | `a569` | `5e56` | yes | 0 |
| 1 | f4 | with the fix | `b559` | `ebc0` | yes | 0 |
| 2 | h5 | `c951a73` | `9350` | `0f63` | no | 1, `20261015-founder-comeback-hook-code-conflict` |
| 2 | h6 | `c951a73` | `2655` | `85d2` | yes | 0 |
| 2 | h7 | `c951a73` | `6439` | `634f` | no | 1, `20261015-founder-comeback-hook-code-conflict` |
| 2 | h8 | `c951a73` | `054d` | `e544` | no | 1, `20261015-p02-welcome-back-code-conflict` |
| 2 | f5 | with the fix | `abb6` | `31a1` | yes | 0 |
| 2 | f6 | with the fix | `5c7e` | `02bb` | yes | 0 |
| 2 | f7 | with the fix | `afec` | `77f5` | yes | 0 |
| 2 | f8 | with the fix | `32b5` | `186d` | yes | 0 |

Each run is the run identifier ending in the four characters shown.
With the failed lab's title alone, `c951a73` asked again in 1 of 4 labs and the fix in none; with its identifier as well, `c951a73` asked again in 3 of 4 and the fix in none.
With the fix, every second run's Post Drafts session opened the proposal's file before it decided, and each said the open proposal covered day 2's Hook; on `c951a73`, 2 of 8 did, and neither of those asked again.
Each repeat declared `new_angle: no` and cited P02's Hook at `angles.md` line 8, as the open proposal did.
Every session of the 32 runs ended with exit code 0 and closed `Session: complete`.

From `src/`, `tests.test_sessions` and `tests.test_work` (68 tests) and the `DecisionRoundTripTest`, `CarryOverTest`, and `TakeInTest` classes of `tests.test_cycle` (19 tests) passed with the fix; the whole suite and ruff were not run for this round.

## What was not exercised

- Immerse: the example set and the labs are RepToday's; the task definition is shared, so the change applies to Immerse's weekly runs alike, and nothing here ran one.
- A production run: nothing here ran in the production clone or read the real Mandu or RepToday.
- The learning loop's gate itself: no rejection reason was given, so no lab run tried an Instructions change; round 2 calls the function the gate calls, once per side, without the gate's repeat rule.
- A decided proposal under a title that names another subject: round 6 left each proposal open, and the brief names a decided one's file the same way.
- Example 16's judged statements are judged by nothing; what the proposals say is quoted above.

## Round 7: preflight and boundary check on `main` after the merge

The pipeline's own runs of both checks on `1a80815`, the launcher change this change's pull request carried, are stated only in the pull request.
This round was run after the merge, on `main`, to put them in this record.
Nothing was changed for it: no launcher code, `config/`, permission profile, or example set.

What was run, as typed, from a linked worktree of this repository on the Founder's Mac, on 2026-10-15 (PDT, UTC-7), with Codex CLI 0.160.0:

- `src/bin/gr0wthlab preflight`, at 15:37:16, ending at 15:37:17.
- `src/bin/gr0wthlab boundary-check`, from 15:37:20 to 15:38:14.

On which commit: `b7575956cdff0a0223ac4ad802c57fda15002181`, `main` after #26, with `src` tree `fb1d365d5c58b6b74a35a0c1bf1b13c777abab32` and `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
`git status` was empty before and after both.
The configuration fingerprint `show-config` prints, and the boundary check printed, is `65c0362d7e73a1bc164001414c11a4aa2d3153d5c3658a53128ae58b4f09bb45`.

| Check | Run identifier | Exit code |
| --- | --- | --- |
| `preflight` | none printed | 0 |
| `boundary-check` | `20261015T223723Z-on-demand-05fc` | 0 |

What the records showed:

- The preflight printed `"ok": true` with no breaches and no failures.
  It listed 6 writable areas and 22 refused paths.
  Its footage probe refused a listing of the footage place (`~/Mandu/projects/RepToday`), with no listing and nothing untried.
  Its network probe found `www.reddit.com:443` and `itunes.apple.com:443` unreachable, none reached, nothing untried.
- The boundary check printed `PASSED`: 49 steps this run had to prove, 0 sentinels escaped, 12 of 12 permitted sentinels written, 17 of 17 file-tool targets Codex refused each in a patch of its own, 19 kernel Seatbelt denials naming this run's sentinels or the check's listeners, and 1 of 1 forbidden reads of the footage place the runtime refused.
  No local connection got through.
  The sandbox network refused 3 targets and reached none, and the control outside the sandbox reached its listener.
  The launcher sent 2 requests, both `GET`, to `itunes.apple.com` and `www.reddit.com`, read both `robots.txt` files, and refused an unlisted address.
  It found no change since the snapshot from before the check.
- The run was the first attempt; no run was repeated, and none ended before a tool call.

What was not exercised: nothing beyond what these two commands cover; the commands were not run in the production clone, and the pipeline's runs on `1a80815` are not repeated here.
