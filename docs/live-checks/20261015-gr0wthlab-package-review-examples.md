# Live checks: the package review's examples check what their packages say (US-ME04, US-ME16)

This file records what was run on the Founder's Mac for the change to the Package review example set (`src/examples/package-review/`) and to the Package review task definition (`src/instructions/weekly-run/package-review.md`).
The Instructions in force (`ledger/instructions/package-review.md`), the shared task-definition parts (`common.md`, `items.md`), the launcher, the configuration, and the permission profile are unchanged, so no `preflight` or `boundary-check` was run and the Post Drafts set was not measured again.

## What was run, and where

Run on 2026-10-15 from 09:27 to 10:55 PDT, Codex CLI `codex-cli 0.160.0`, model `gpt-6-luna` at reasoning effort `high`, as each session's record in its log folder shows.
Five clones of this repository sat in the Mac's own temporary folder, each at one commit:

| Side | Commit | `src` tree |
| --- | --- | --- |
| `main` | `9ec7a364466421f499e05ac26d87ea646b0d2f41` | `c13378a8d77afdc284cd707a218a081be7c7281c` |
| Round A: the first fixture fix alone | `4d5fb979300f85801329e89825aac293f9d591fb` | `60be7f084903d381df658a9b25436b79571f8b8f` |
| Round B: with the first task-definition change | `b622a799295df67ae1f819396f913a86b422f76a` | `805cf65b0d32cd33c48a1355753b7689b7419031` |
| Round C: with the platform fixture and the omission line | `5a7f3dd9b22a931a3bf4844c6a0a91ad431efddc` | `53f635fd462562c7c64910c1ed3f8c85b1b8ffe4` |
| Round D: the change as it is committed | `ccb7c5972ec1c46f84e68531795eb215bd44b7f6` | `d8e55f867677c5aa8a71248b2d9dafbc67991c6b` |

Every side's `config` tree is `578d1984f76e95cc63e37cdd6f720a68a8872f92`.
Each clone was made fresh at its commit before its runs, and `git status` in each was empty after its last run.

A scratch script outside the repository called each clone's own `examples.run_example`, the function the gate calls, once for each example run, with the Instructions in force from that clone's `ledger/instructions/` and each example's limit of 600 seconds, four at a time.
It read each check from the run, each session's counts from the run's record in its log folder (`sessions[].work`, which the run report's Sessions section shows), each session's closing message from its `.last-message.md`, and each queued proposal from the lab's `ledger/review-queue/items/` before the lab was removed.
Every lab run's identifier starts `20261011T230000Z-on-demand-`, the lab's fixed clock; the tables give the four characters after it, with each run whose checks did not all hold marked as failed.
Every session of every round ran to its end, and every closing line was `Session: complete`; no session ended early with a provider's refusal.

## Round 1: the gap on `main`

Package review examples 3, 4, 8, and 10 ran five times each and every other example twice; examples 8 and 9 ran ten times each, five of them during round D.

| Example | `main` runs | All checks held |
| --- | --- | --- |
| 1 | `ca48`, `c58e` | 2 of 2 |
| 2 | `f53f`, `a1d6` | 2 of 2 |
| 3 | `4fc4` (failed), `5e41` (failed), `aaa2` (failed), `b03d` (failed), `8e39` (failed) | 0 of 5 |
| 4 | `0685`, `2cfd`, `397c`, `2a22` (failed), `8136` | 4 of 5 |
| 5 | `7960`, `58b2` | 2 of 2 |
| 6 | `803a`, `a106` | 2 of 2 |
| 7 | `c3f1`, `95f4` | 2 of 2 |
| 8 | `41b9` (failed), `7352`, `5dd4`, `7932`, `6fad`, `c7fc` (failed), `45c5` (failed), `df4f`, `26c5` (failed), `6bee` | 6 of 10 |
| 9 | `811a`, `e710`, `f15f` (failed), `186e`, `1513` (failed), `f279`, `4646`, `8fc0`, `7315`, `3f18` (failed) | 7 of 10 |
| 10 | `abf4` (failed), `3e1a` (failed), `0464` (failed), `1c97` (failed), `d6cb` (failed) | 0 of 5 |

The first five runs of 3, 4, 8, and 10 held every check 8 of 20 times, the count the Instructions-notice guidance work recorded.
Example 9, whose package keeps an earlier version marked as history and which also checks that nothing is queued, failed three times in ten, each time with a proposal about P02's Hook.

### What each failing session said, and what its files say

**Examples 3 and 10.**
In each failed run the failing check was that no queued proposal cited both `ab-pairs.md` and `angles.md`.
Nine of the ten failing sessions' closing messages do not name the A/B pair or its leg A Hook at all.
The tenth, `4fc4`, says: "P01's Angle hook wording differs from AB-1 leg A. Correcting either hook requires a Listening quote record, and none is present, so I could not propose that change."
The planted fact is there: the overlay gives AB-1 leg A "Open it and today's session is waiting." where the Angle bank gives P01 "Open it and the session is already waiting."
Nothing in the package said that leg A carries its Angle's Hook, though.
`CONTEXT.md` says one Angle can be tested with several Hooks, leg B already opens on a Hook of its own, and the launcher takes each pair leg's own Hook as the frozen text for its day (`kit.frozen_hook`), so by the package's own files a leg A with its own Hook was not a contradiction.
Example 3's expected output also said the proposal "declares new_angle: yes only if it changes a Hook"; a `yes` proposal needs a kept quote record, which the lab holds none of, so the launcher would set it aside and the example's `nothing_set_aside` check would fail.
What the Founder should see is one proposal that brings leg A in line with the Angle's Hook, or asks which wording stands, declared `new_angle: no`.

**Example 4.**
The planted fact is there: the calendar's day 2 names Angle P03, and the Angle bank holds only P01 and P02.
The one failing session, `2a22`, read all 16 listed files and closes with a list of the recorded outcomes alone and "No proposals were needed"; its one search of the package was for status words such as trademark, cleared, held, and waitlist.
Its assertion matches what the Founder should see, so the example was right and the session's pass over facts that should agree was the gap.

**Examples 8 and 9.**
Both check that nothing is queued, and every failed run queued a proposal.
Of all 45 `main` sessions, 14, in examples 3, 4, 6, 8, 9, and 10, queued a proposal setting the brand voice's rule against P02's Hook.
The brand guidelines' line 13 says "Identity-framed, never loss-framed", and P02's Hook in the Angle bank was "Skip a day and the score dips.", a line that states what the viewer loses by skipping a day.
The two do contradict, so the package these examples call consistent was not.
Two other `main` sessions, both of example 8 (`41b9`, `c7fc`), proposed removing "(blocking: everything public)" from the checked trademark item of the pre-publication checklist, and one proposed completing a calendar that lists three of its fourteen days.

## The change

Six commits, each measured in the round named here.

- Round A: P02's Hook is now "Your score keeps every day you moved.", and the A/B pairs file, in the base package and in the overlay, says "Leg A of each pair opens on its Angle's Hook in the Angle bank, word for word; leg B is the Hook tested against it."
  Example 3's prompt and expected output now say what the Founder should see; no assertion changed.
- Round B: the task definition's step 1 asks the pass over facts that should agree to check that each name one file uses for something another file defines is defined there; step 2 says a contradiction about a Hook, signal, or kill criterion is written like any other, and that a proposal which only makes one file's copy match another's words, or leaves the choice to the Founder, declares `new_angle: no` and needs no quote record; the summary says what each pass checked.
  This round's and round C's text also asked for a word-for-word comparison of each wording two files give for the same thing, which round D's text no longer does.
- Round C: the Angle bank's Platform column is now named "Primary platform", and the platform file says each Angle names its primary platform in the bank; step 1 also says a file that only says less than another does not contradict it.
- Round D: the pre-publication checklist says "An item marked (blocking: X) holds back X until it is checked."; the word-for-word clause is gone.

The real package states the relations rounds C and D add in its own files, in its own words; the synthetic package had left them out.
`src/tests/test_example_runs.py` cites the two lines the fixtures moved.

## Rounds A, B, and C: what each step did

| Example | Round A runs | Held | Round B runs | Held | Round C runs | Held |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `697d`, `9724` | 2 of 2 | `6fb2`, `05de` | 2 of 2 | `5ac5`, `bde2` | 2 of 2 |
| 2 | `6cde`, `e08b` | 2 of 2 | `2a1b`, `1680` | 2 of 2 | `1bef`, `d9d2` | 2 of 2 |
| 3 | `5bd8`, `5616`, `7cad`, `9fd5`, `d2e3` | 5 of 5 | `c662`, `3ff9`, `a8a8`, `eada`, `d22a` | 5 of 5 | `7297`, `5728`, `e677`, `8148`, `57ea` | 5 of 5 |
| 4 | `b0f2`, `0a68`, `281d`, `70a9` (failed), `9671` | 4 of 5 | `8336`, `a5d9`, `9d50`, `2e38`, `8e7d` | 5 of 5 | `d5c4`, `4951`, `5692`, `7ef2`, `a6b1` | 5 of 5 |
| 5 | `3289`, `4a69` | 2 of 2 | `1f3e`, `5d97` | 2 of 2 | `5a8f`, `d46b` | 2 of 2 |
| 6 | `77c6`, `6abc` (failed) | 1 of 2 | `35d3`, `c63a` | 2 of 2 | `6330`, `f4a0` | 2 of 2 |
| 7 | `c329`, `8dcc` | 2 of 2 | `fc59`, `e30f` | 2 of 2 | `ebc3`, `4b19` | 2 of 2 |
| 8 | `d63d`, `4667`, `fd53`, `066c`, `a082` | 5 of 5 | `92f2` (failed), `a829`, `c0ec`, `1164`, `90c1` | 4 of 5 | `1e14`, `bc6f` (failed), `b7ad`, `62d1`, `2043` | 4 of 5 |
| 9 | `0642` (failed), `8a24` | 1 of 2 | `810e`, `91df` (failed) | 1 of 2 | `4c51` (failed), `8100`, `aeb8` (failed), `fad0`, `06e0` (failed) | 2 of 5 |
| 10 | `7d63`, `9314`, `6165`, `c27c`, `7146` | 5 of 5 | `6081`, `b92c`, `11d0`, `9495`, `e2aa` | 5 of 5 | `c925`, `384c`, `5670`, `cb46`, `b491` | 5 of 5 |

- Round A: with the fixtures alone, 3 and 10 held 10 of 10, every session's pair proposal declared `new_angle: no`, and no session queued a proposal about P02's Hook.
  Example 4 failed once as on `main`: `70a9` lists only the recorded outcomes and queued a proposal about the pre-publication checklist instead.
  Example 6's `6abc` cited the Hook's line in `ab-pairs.md` and the brand rule, and not `angles.md`.
- Round B: example 4 held 5 of 5.
  Example 8's `92f2` proposed aligning each Angle's single Platform with the platform file's cross-posting, as round A's `9fd5` and `0642` had; example 9's `91df` proposed adding the Beta Build gate to the thesis, as example 2's `2a1b` did beside its planted proposal, and completing the three-day calendar.
- Round C: four sessions of examples 8 and 9, and one of example 3, queued a proposal beyond the planted one: four removed the checked trademark item's "(blocking: everything public)" (`bc6f`, `aeb8`, `06e0`, and `57ea` in example 3), and `4c51` proposed aligning the brand guidelines' status line with the differently worded required disclosure, under the round's text that asked for word-for-word comparisons.
  `4c51`'s summary also says "The three listed calendar days do not specify all 14 days, but that omission is not a contradiction."

## Round D: the change as committed, against `main`

| Example | `main` runs | `main` held | Change runs | Change held |
| --- | --- | --- | --- | --- |
| 1 | `ca48`, `c58e` | 2 of 2 | `dd7e`, `4f82` | 2 of 2 |
| 2 | `f53f`, `a1d6` | 2 of 2 | `4784`, `da87` | 2 of 2 |
| 3 | `4fc4` (failed), `5e41` (failed), `aaa2` (failed), `b03d` (failed), `8e39` (failed) | 0 of 5 | `d1dc`, `090b`, `6c42`, `a14e`, `df27` | 5 of 5 |
| 4 | `0685`, `2cfd`, `397c`, `2a22` (failed), `8136` | 4 of 5 | `b000`, `bdc3`, `9ede`, `d5b1`, `329d` | 5 of 5 |
| 5 | `7960`, `58b2` | 2 of 2 | `4d66`, `8967` | 2 of 2 |
| 6 | `803a`, `a106` | 2 of 2 | `f1f6`, `8d45` | 2 of 2 |
| 7 | `c3f1`, `95f4` | 2 of 2 | `962a`, `d729` | 2 of 2 |
| 8 | `41b9` (failed), `7352`, `5dd4`, `7932`, `6fad`, `c7fc` (failed), `45c5` (failed), `df4f`, `26c5` (failed), `6bee` | 6 of 10 | `41eb`, `38a0`, `0a69`, `6d0c`, `6a84`, `c72e`, `446f`, `413a`, `25e8`, `92e0` | 10 of 10 |
| 9 | `811a`, `e710`, `f15f` (failed), `186e`, `1513` (failed), `f279`, `4646`, `8fc0`, `7315`, `3f18` (failed) | 7 of 10 | `8abf`, `859b`, `09d4`, `71c5`, `ab1d`, `8932`, `810c`, `7f28`, `461a`, `cebb` | 10 of 10 |
| 10 | `abf4` (failed), `3e1a` (failed), `0464` (failed), `1c97` (failed), `d6cb` (failed) | 0 of 5 | `2498`, `31ef`, `4494`, `9afd`, `088a` | 5 of 5 |

With the change every example held every check in every run, and no session queued a proposal beyond the one its example plants; on `main`, 16 of 45 sessions did.

The launcher's counts of each session, summed for each side:

| Side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Agent seconds | Cost (USD, API prices) | Per session |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `main`, every run above | 45 | 45 | 45 | 720 of 720 | 36 | 3,226 | 0.379 | 72 s, 0.0084 |
| Round A | 32 | 32 | 32 | 512 of 512 | 33 | 2,359 | 0.279 | 74 s, 0.0087 |
| Round B | 32 | 32 | 32 | 510 of 512 | 34 | 2,463 | 0.277 | 77 s, 0.0087 |
| Round C | 35 | 35 | 35 | 560 of 560 | 35 | 2,574 | 0.317 | 74 s, 0.0091 |
| Round D, the change | 45 | 45 | 45 | 720 of 720 | 30 | 3,320 | 0.377 | 74 s, 0.0084 |

Round B's two files not read were `02-marketing-launch-checklist_260807.md` in `3ff9` and `BUILD-SPEC.md` in `1680`.
Altogether the checks ran 189 sessions, 13,941 seconds of agent time, about 1.63 dollars at API prices.

## The unit suite and lint

| Command | Where | What the records showed |
| --- | --- | --- |
| `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` (ruff 0.15.20) | the worktree at the change | all checks passed; 101 files already formatted |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | the `main` clone | 1,388 tests OK in 2,796 seconds |
| the same | a clone at `ccb7c59` | 1,388 tests OK in 2,918 seconds |

## What was not exercised

- The Post Drafts example set: no file it reads changed, since `common.md` and `items.md` did not.
- The gate itself (`examples.gate`) deciding a proposed Instructions change against this set: the runs above call the function it calls for each example, and no change was proposed through the learning loop.
- A weekly run on a real package: whether the new step 1 and step 2 lines change what a review of RepToday's or Immerse's own package finds rests on these synthetic examples alone.
- More runs of examples 1, 2, 5, 6, and 7, which ran twice on each side.
