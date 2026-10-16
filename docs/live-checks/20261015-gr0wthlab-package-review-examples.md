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
Every session of round 1 and rounds A to D ran to its end, and every closing line was `Session: complete`; no session ended early with a provider's refusal.

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

## Round E: after the merge with `main`

The branch took in `main` at `2af81a45181bc0ddb297cf604cecf73ed7d07fee` with one merge commit, `4a300176fe548556b6e29edbb27c5eb82e59ad81`, which brought the Hook claim fix and the Instructions-notice guidance fix: `items.md` now says what an item may not supersede and the exact rule by which the launcher refuses a repeat, and the brief's lines on open items changed with it.
Both reach the Package review session, whose task definition carries `common.md` and `items.md`.
`items.md` now also says when a proposal declares `new_angle: yes` and that a fix bringing stale text in line is `no`, so commit `42a505b` rewords the task definition's step 2 to say only what `items.md` does not: a proposal that leaves the choice to the Founder is `no` as well, and no contradiction is left unwritten for want of a quote record.

Run on 2026-10-15 from 18:59 to 19:12 PDT, as in the rounds above, from a fresh clone at `42a505b72acb73aba379775ecee6a7e845e3e8af` (`src` tree `bae03e6a8519a7dca6f9a248f1085225097aad2b`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`), with the same Codex CLI, model, and effort; `git status` in the clone was empty after its last run.

| Example | Runs | All checks held | Round D, for comparison |
| --- | --- | --- | --- |
| 1 | `a14c`, `36b1` (failed), `3632`, `20a5`, `118d` | 4 of 5 | 2 of 2 |
| 2 | `2654`, `1b0c` | 2 of 2 | 2 of 2 |
| 3 | `77c5`, `9305`, `1cc6`, `b8d7`, `442f` | 5 of 5 | 5 of 5 |
| 4 | `11de`, `a8f1`, `a913`, `b46a`, `c0ed` | 5 of 5 | 5 of 5 |
| 5 | `d187`, `c342` | 2 of 2 | 2 of 2 |
| 6 | `5845`, `d887` | 2 of 2 | 2 of 2 |
| 7 | `985c`, `215c` | 2 of 2 | 2 of 2 |
| 8 | `0422`, `e04c`, `477f`, `84f4`, `77ab` | 5 of 5 | 10 of 10 |
| 9 | `d61a`, `4a47`, `40dc`, `d189`, `ce5f` | 5 of 5 | 10 of 10 |
| 10 | `c98a`, `d3ac`, `fd89`, `549a`, `3d2c` | 5 of 5 | 5 of 5 |

No session queued a proposal beyond the one its example plants.
Example 1's `36b1` read none of its 16 listed files, by the launcher's count, and closes `Session: incomplete`, saying the package files and the snapshot were not at their paths.
Its event record shows its first command failed to start and every package path it then tried named the lab's folder with one `/` left out (`…0000gnT/gr0wthlab-prx/…` for `…0000gn/T/gr0wthlab-prx/…`), while its reads by relative path succeeded; example 1 then ran three more times, `3632`, `20a5`, and `118d`, and held each time.
Two other sessions read fewer than all their listed files: `477f` (example 8) 11 of 16 and `5845` (example 6) 15 of 16; both held every check.

| Side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Agent seconds | Cost (USD, API prices) | Per session |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Round E, the merged head | 38 | 38 | 37 | 586 of 608 | 32 | 2,413 | 0.335 | 64 s, 0.0088 |

| Command | Where | What the records showed |
| --- | --- | --- |
| `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` (ruff 0.15.20) | the worktree at `42a505b` | all checks passed; 107 files already formatted |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | a clone at `42a505b` | 1,484 tests OK in 2,319 seconds |

What this round did not exercise: the Post Drafts set, since this branch changes no file it reads and the merged changes to `items.md` were measured on it in their own records; `main`'s side again, since round 1 above is that side for the package review set; and anything round 1 to D left out.

## Round F: example 6 again, on `main` and on this branch

Review asked for more runs of example 6.
Its planted conflict, a brand rule that bans a word in P01's frozen Hook, is the case step 2 of the task definition covers, and it failed once in two runs in round A, which ran the first fixture fix with `main`'s task definition.

Run on 2026-10-15 from 19:47 to 19:50 PDT, three at a time with the sides taken in turn, with the same scratch script, Codex CLI, model, and effort as the rounds above, from two fresh clones:

| Side | Commit | `src` tree | `config` tree |
| --- | --- | --- | --- |
| `main` | `2af81a45181bc0ddb297cf604cecf73ed7d07fee` | `74308c217117f51d883415ee0cb0028d7403e98e` | `e3b97b510841032f95c57c5f8f61285f8906e657` |
| This branch | `05be1889246c04cb094efd5e0b6671e3aa382679` | `bae03e6a8519a7dca6f9a248f1085225097aad2b` | `e3b97b510841032f95c57c5f8f61285f8906e657` |

`main` here is the commit round E merged in, not round 1's `main`.
This branch's trees are round E's.
After these runs the change took back the line it had added to `AGENTS.md`, a file a lab does not copy (`examples.COPIED`).
`git status` in each clone was empty before its first run and after its last.

| Example | `main` runs | `main` held | Branch runs | Branch held |
| --- | --- | --- | --- | --- |
| 6 | `78b0`, `eead`, `8254` | 3 of 3 | `6325`, `9bf0`, `f981` | 3 of 3 |

Every session ran to its end, read all 16 of its listed package files, and closes `Session: complete`.
In each of the six runs one queued proposal cites `brand-rules.json` and `angles.md` and declares `new_angle: no`, and nothing was set aside.
On `main`, `78b0` also queued two proposals beyond the planted one, one titled "clarify the loss-framing rule" and one titled "limit posts to their primary platform"; no session on this branch queued one.

| Side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Agent seconds | Cost (USD, API prices) | Per session |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `main` | 3 | 3 | 3 | 48 of 48 | 5 | 252 | 0.031 | 84 s, 0.0104 |
| This branch | 3 | 3 | 3 | 48 of 48 | 3 | 202 | 0.029 | 67 s, 0.0097 |

Example 6 holds no worse with the change.
With this branch's task definition it held every check 5 of 5 times (round E 2, this round 3), and with round D's, before commit `42a505b` reworded step 2, 2 of 2.
On `main` it held 5 of 5 (round 1 2, this round 3).
Its one failing run in any round is round A's `6abc`.

What this round did not exercise: more runs of examples 1, 2, 5, and 7, which stay as rounds 1, D, and E left them; the Post Drafts set, as in round E.

## Round G: step 2 states its declaration as a condition

Review found that step 2 said a proposal leaving the choice to the Founder is `new_angle: no` "since" it words no new Hook, signal, or kill criterion, which reads as covering one that offers a newly worded Hook; `items.md` and the guidance in force declare that one `yes`.
Step 2 now says a proposal that leaves the choice to the Founder, offering no newly worded Hook, signal, or kill criterion (a changed Hook enters only as a new Angle), is `new_angle: no`.
Examples 3, 6, and 10, whose planted contradictions are about a Hook, ran again on this branch; `main` has not moved since round F, so its side is the counts above.

Run on 2026-10-15 from 20:15 to 20:22 PDT, with the same scratch script, Codex CLI, model, and effort as the rounds above, the first nine runs four at a time and the last three three at a time, from a fresh clone of this branch with this round's change: `src` tree `dcb43ea4c735cbcf855bb9c5e2c305da156e4e11`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
`git status` in the clone was empty before its first run and after its last.

| Example | Runs | All checks held | Held under round H's declaration rule | This branch before: rounds D, E, F | `main`: rounds 1, F |
| --- | --- | --- | --- | --- | --- |
| 3 | `da21`, `ba50`, `9a53` | 3 of 3 | 3 of 3 | 5 of 5, 5 of 5, not run | 0 of 5, not run |
| 6 | `d936` (failed), `8529`, `6b6a`, `1dd7`, `e1bf`, `6ce0` | 5 of 6 | 0 of 6 | 2 of 2, 2 of 2, 3 of 3 | 2 of 2, 3 of 3 |
| 10 | `7bd3`, `4bf9` (does not hold under round H's rule), `9402` | 3 of 3 | 2 of 3 | 5 of 5, 5 of 5, not run | 0 of 5, not run |

`d936` read none of its 16 listed files, by the launcher's count, queued nothing, and closes `Session: incomplete`, saying the package files could not be opened at their listed paths.
Its event record shows one listing of the package folder by its full path, and after it every package path it tried named the lab's folder with one `/` left out (`…0000gnT/gr0wthlab-pr-g/…` for `…0000gn/T/gr0wthlab-pr-g/…`), and four of its commands failed to start, as round E's `36b1` shows.
Example 6 then ran three more times, `1dd7`, `e1bf`, and `6ce0`, and held each time.
Every other session read all 16 of its listed files and closes `Session: complete`.
No session queued a proposal beyond the one its example plants, and every queued proposal declares `new_angle: no`.
Each of example 6's five proposals asks the Founder to choose between the brand rule and P01's Hook and says it proposes no replacement Hook.
Each of example 3's three proposals, and two of example 10's three pair proposals, replace leg A's Hook in the A/B pairs file with P01's Hook from the Angle bank; example 10's `4bf9` asks the Founder to choose which of the two existing wordings stays, either leg A's or P01's in the Angle bank, and to make the other file match.
Approving any of example 6's five proposals or `4bf9` could change P01's frozen Hook, so under the rule round H's step 2 states each should have declared `new_angle: yes`, and none of the six holds; the column for that rule counts them so.

| Side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Agent seconds | Cost (USD, API prices) | Per session |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Round G | 12 | 12 | 11 | 176 of 192 | 14 | 703 | 0.115 | 59 s, 0.0096 |

By the examples' checks none of the three does worse with this round's step 2: in every session that read the package each held every check, and example 6's one failing run read no package file.

What this round did not exercise: examples 1, 2, 4, 5, 7, 8, and 9 with this round's step 2, which stand on round E's runs of the line before it; a proposal that offers a newly worded Hook and declares `yes`, which no session here wrote and no example's lab holds the quote record for; the Post Drafts set, as in round E.

## Round H: step 2 declares from what approving a proposal could change

Review found that round G's step 2, which made a proposal leaving the choice to the Founder `new_angle: no` when it offered no newly worded Hook, let a `no` proposal rewrite a frozen Hook to another file's existing wording, as round G's `4bf9` offered.
Step 2 now says a proposal is `new_angle: yes` whenever approving it could change a frozen Hook, signal, or kill criterion, including by choosing another file's existing wording, since such a change enters only as a new Angle.
It says a proposal that only brings a stale copy in line with its source is `no`, and that for the A/B pairs the Angle bank is the source and leg A the copy.
Where no kept quote record supports changing a frozen Hook, signal, or kill criterion, it has the `no` proposal propose the change on the other side and say that changing the frozen one instead enters only as a new Angle.
Example 3's expected output now asks only for leg A brought in line with its source, and example 6's expected output and judged statement ask for a proposal whose approval changes no frozen Hook; no deterministic assertion changed.
Under this rule round G's `4bf9` and example 6's five proposals do not hold, as round G's table now shows.

Run on 2026-10-15 from 20:34 to 20:37 PDT, with the same scratch script, Codex CLI, model, and effort as the rounds above, four at a time, from a fresh clone of this branch with this round's change: `src` tree `d23070983634e7652e6220d0809e9ff1495912bb`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
`git status` in the clone was empty before its first run and after its last.

| Example | Runs | All checks held | Held under this round's declaration rule | Round G: checks, this rule | `main`: rounds 1, F |
| --- | --- | --- | --- | --- | --- |
| 3 | `d89f`, `7cc2`, `fb0d` | 3 of 3 | 3 of 3 | 3 of 3, 3 of 3 | 0 of 5, not run |
| 6 | `93a0`, `f530`, `9dd9` | 3 of 3 | 3 of 3 | 5 of 6, 0 of 6 | 2 of 2, 3 of 3 |
| 10 | `12a9`, `b71b`, `aa87` | 3 of 3 | 3 of 3 | 3 of 3, 2 of 3 | 0 of 5, not run |

Every session read all 16 of its listed files and closes `Session: complete`.
No session queued a proposal beyond the one its example plants, every queued proposal declares `new_angle: no`, and nothing was set aside.
Each of example 6's three proposals proposes removing the banned word from the brand rules' list of words banned in a Hook, leaving P01's Hook as it is, and says that changing the Hook instead enters only as a new Angle.
Each of example 3's three proposals and example 10's three pair proposals replaces leg A's Hook in the A/B pairs file with P01's Hook from the Angle bank.
Read one by one, none of these nine proposals could change a frozen Hook if approved, so each holds under this round's rule.

| Side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Agent seconds | Cost (USD, API prices) | Per session |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Round H | 9 | 9 | 9 | 144 of 144 | 12 | 530 | 0.083 | 59 s, 0.0093 |

None of the three examples does worse with this round's step 2: each held every check in every run, against 0 of 5 for examples 3 and 10 and 5 of 5 for example 6 on `main`.

What this round did not exercise: examples 1, 2, 4, 5, 7, 8, and 9 with this round's step 2, which stand on round E's runs; a proposal that declares `yes` with a kept quote record, which no example's lab holds; whether the proposals of rounds before G, on either side, hold under this round's rule, since this record keeps none of their wording; the Post Drafts set, as in round E.

## Round I: step 2 puts a conflict with a frozen Hook to the Founder

Review found two things in round H's step 2.
It said for every package that the Angle bank is the source and leg A the copy, which only a pairs file that says so makes true.
It also had a proposal about a frozen Hook, signal, or kill criterion with no kept quote record propose the change on the other side, which in example 6 meant unbanning the word for every Hook.
Step 2 now keeps round H's rule that a proposal whose approval could change a frozen Hook, signal, or kill criterion declares `new_angle: yes`, and makes the Angle bank leg A's source only where the A/B pairs file says leg A opens on its Angle's Hook.
Where a frozen Hook, signal, or kill criterion conflicts with another file and no kept quote record supports changing it, the proposal puts the conflict to the Founder and changes nothing frozen: it says what each file says and what would change on each side, leaves the choice to the Founder, says that changing the frozen one would enter through the next run as a new Angle, and declares `new_angle: no`.
Example 6's expected output asks again for a proposal that puts the conflict to the Founder and changes nothing frozen, and its judged statement now reads "The proposal neither unbans the word nor rewords the Hook, and leaves the choice to the Founder."
Round H's three example 6 proposals each removed the word from the brand rules' list, which that expected output and judged statement now rule out.

Run on 2026-10-16 from 05:57 to 06:01 PDT, with the same scratch script, Codex CLI, model, and effort as the rounds above, four at a time, from a fresh clone of this branch with this round's change: `src` tree `9781524a4e7becf1fae7c59e2516be80891dc03f`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
`git status` in the clone was empty before its first run and after its last.

| Example | Runs | All checks held | This branch before: rounds D, E, G, H | `main`: rounds 1, F |
| --- | --- | --- | --- | --- |
| 3 | `bb78`, `ad2a`, `6cd9` | 3 of 3 | 5 of 5, 5 of 5, 3 of 3, 3 of 3 | 0 of 5, not run |
| 6 | `e4cc`, `b245`, `0be9` | 3 of 3 | 2 of 2, 2 of 2, 5 of 6, 3 of 3 | 2 of 2, 3 of 3 |
| 10 | `fc28`, `cb9a`, `3fe7` (failed) | 2 of 3 | 5 of 5, 5 of 5, 3 of 3, 3 of 3 | 0 of 5, not run |

Every session closes `Session: complete`, and every one read all 16 of its listed files except `6cd9`, which read 15, leaving `BUILD-SPEC.md`.
Nothing was set aside, and every queued proposal declares `new_angle: no`.
Each of example 6's three proposals sets out both sides, leaves the choice to the Founder, changes neither the brand rule nor the Hook itself, and says that changing the Hook would enter through the next run, or in `0be9` a later run, as a new Angle.
Each of example 3's three proposals and example 10's three pair proposals replaces leg A's Hook in the A/B pairs file with P01's Hook from the Angle bank.
Read one by one, none of these nine proposals could change a frozen Hook if approved.

`3fe7` failed the check that a queued proposal cites `brand-guidelines.md` and `02-marketing-launch-checklist_260807.md`.
Its name-status proposal cites the brand guidelines' line 8 as the stale side and the pre-publication checklist's line 9 as the dated outcome, a line that records the trademark search cleared on 2026-08-07, and does not cite the launch checklist.
Its pair proposal held.

| Side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Agent seconds | Cost (USD, API prices) | Per session |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Round I | 9 | 9 | 9 | 143 of 144 | 12 | 633 | 0.086 | 70 s, 0.0096 |

Against `main` none of the three examples does worse: 3 of 3 for example 3 and 2 of 3 for example 10 against 0 of 5 each, and 3 of 3 for example 6 against 5 of 5.
Example 10's `3fe7` is its first failing run on this branch in 19, in rounds D, E, G, H, and this one, and it fails on the name-status proposal, which no line of this round's step 2 is about.
Three runs cannot show whether that is run-to-run variance, so it is left here for firstmate rather than worded around: the name-status check asks for the launch checklist alone, while the pre-publication checklist the session cited records the same dated outcome.

What this round did not exercise: examples 1, 2, 4, 5, 7, 8, and 9 with this round's step 2, which stand on round E's runs; a proposal that declares `yes` with a kept quote record, which no example's lab holds; the Post Drafts set, as in round E.
