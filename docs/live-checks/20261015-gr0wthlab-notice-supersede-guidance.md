# Live checks: the agent is told no item supersedes the notice of a kept Instructions change (US-ME16)

This file records what was run on the Founder's Mac for the change that tells the agent, in `src/instructions/weekly-run/items.md` and in the brief's Review Queue section (`report.item_lines`), that the notice of a change to the Instructions cannot be superseded by any item and that only the Founder's decision closes it.
From round 4 on, the change also tells it the same of a Weekly Read decision, which changes only through the Weekly Read memo.
The launcher's rule in `Ledger` (`src/gr0wthlab/queue.py`) is unchanged.
No configuration and no permission profile changed; rounds 1 to 3 ran no `preflight` or `boundary-check`, and round 4, which changed `report.py` again, ran both.

## Round 1: the gap on main, the unit suite, and the example sets on both sides

Run on 2026-10-15 from 05:05 to 06:56 PDT, Codex CLI `codex-cli 0.160.0`, at the model and reasoning effort in `config/guardrails/runtime.json` (high).
Two clones of this repository sat in the Mac's own temporary folder: one at `main`, commit `dc4fb88fdd54bf83e5aaab59779bfd1ff441482b`, and one at the change, commit `f197899af56a1415229cb010c9af0a57046f51c6` (`src` tree `4be1b04e0bbcdd79e80950ad62d6b62e2c16e824`, `config` tree `578d1984f76e95cc63e37cdd6f720a68a8872f92`).
The two clones differ in `src/instructions/` only by the one line added to `items.md`.
`git status` was empty in the worktree before the checks and after them, apart from this file.

### The gap on main

`LoopTest.test_no_item_of_the_agent_s_can_supersede_a_kept_change_s_notice` in `src/tests/test_instructions.py` keeps a change to the Post Drafts Instructions, has the stand-in agent write an item with `supersedes:` naming its notice, and reads the run report's set-aside line.
With its new assertions on the Package review session's brief, run against `main`'s `report.py`, it failed, and the brief it printed showed:

- the header: "An item filed by the launcher changes only through a reviewed change to its source text, and a post or a message only through its Draft, so an item that supersedes any of them is refused."
- the notice's line: "- `20261018-instructions-post-drafts` (notice): Notice: the Post Drafts Instructions changed"

The run report of the same run held "Set aside, not queued: `replace-notice.md`: supersedes 20261018-instructions-post-drafts, the notice of a change to the Instructions, which only the Founder's decision closes".
The new `ItemLinesTest` in `src/tests/test_report.py` failed on `main` the same way.
Both pass on the change.

### The unit suite and lint

| Command | Where | What the records showed |
| --- | --- | --- |
| `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` (ruff 0.15.20) | the worktree at the change | all checks passed; 101 files already formatted |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | the `main` clone | 1,388 tests OK in 3,654 seconds |
| the same | the change's clone | 1,389 tests OK in 3,647 seconds |

The two suites ran at the same time, from 05:55 to 06:56, on a Mac under load from other work.

### The example sets, with the real agent

`items.md` is a shared part of the Package review, Post Drafts, and Rejection reasons task definitions (`sessions.WORKFLOWS`); only the first two have example sets.
A scratch script outside the repository called each clone's own `examples.run_example`, the function the gate calls, once for each example of both sets that carries `run`, with the Instructions in force from that clone's `ledger/instructions/`, each example's limit at `learning.example_time_limit_seconds`, and read each session's counts from the run's record in its log folder (`sessions[].work`, which the run report's Sessions section shows) and its closing line from the session's last message.
The four streams (two sides, two sets) ran at the same time, from 05:17 to 05:49.
Every lab run's identifier starts `20261011T230000Z-on-demand-`, the lab's fixed clock; the tables give the four characters after it.

Package review, ten examples on each side:

| Example | `main` run | `main` checks held | change run | change checks held |
| --- | --- | --- | --- | --- |
| 1 | `b429` | 2 of 2 | `c624` | 2 of 2 |
| 2 | `4a22` | 2 of 2 | `3320` | 2 of 2 |
| 3 | `b897` | 1 of 2 | `7abb` | 1 of 2 |
| 4 | `836f` | 2 of 2 | `2c78` | 1 of 2 |
| 5 | `2fa8` | 2 of 2 | `7e42` | 2 of 2 |
| 6 | `ad33` | 2 of 2 | `7dbd` | 2 of 2 |
| 7 | `6438` | 2 of 2 | `3dda` | 2 of 2 |
| 8 | `5175` | 2 of 2 | `3aad` | 1 of 2 |
| 9 | `af99` | 2 of 2 | `ea04` | 2 of 2 |
| 10 | `346f` | 3 of 3 | `a84f` | 2 of 3 |

Post Drafts, the ten examples that carry `run`, on each side:

| Example | `main` run | `main` checks held | change run | change checks held |
| --- | --- | --- | --- | --- |
| 1 | `3fed` | 4 of 4 | `df45` | 4 of 4 |
| 2 | `84b8` | 3 of 3 | `b5bd` | 3 of 3 |
| 8 | `097a` | 1 of 1 | `ee1a` | 1 of 1 |
| 16 | `279b` | 2 of 3 | `5036` | 2 of 3 |
| 17 | `1c83` | 5 of 5 | `afed` | 5 of 5 |
| 18 | `8548` | 4 of 4 | `400a` | 4 of 4 |
| 19 | `520d` | 4 of 4 | `1718` | 4 of 4 |
| 20 | `5202` | 5 of 5 | `6051` | 5 of 5 |
| 21 | `e4f2` | 3 of 3 | `891b` | 3 of 3 |
| 22 | `82cc` | 3 of 3 | `03de` | 3 of 3 |

Package review examples 4, 8, and 10 held on `main` and not with the change, so those three and example 3, which failed on both sides, ran four more times on each side, from 05:49 to 06:02:

| Example | `main` runs | `main` all checks held | change runs | change all checks held |
| --- | --- | --- | --- | --- |
| 3 | `d3da`, `5277`, `e28f`, `8081` | 0 of 4 | `2157`, `f1bc`, `51fa`, `813a` | 1 of 4 |
| 4 | `b3f8`, `151b`, `b6c0`, `16b0` | 3 of 4 | `b660`, `d72d`, `0796`, `dbc0` | 3 of 4 |
| 8 | `ea2c`, `13e9`, `3b9d`, `c6bc` | 2 of 4 | `3f86`, `23e2`, `00db`, `57c1` | 2 of 4 |
| 10 | `6b98`, `c2f2`, `2805`, `11c4` | 1 of 4 | `557f`, `a7b3`, `d7ef`, `16c6` | 0 of 4 |

Over all five runs of each, the four examples held every check 8 of 20 times on `main` and 6 of 20 times with the change; each of the four failed at least once on each side.
The failing checks were the same on both sides: in 3, 4, and 10 no queued proposal cited both files the check names, and in 8, a package whose files agree, a proposal was queued.
In each run of example 8 that failed, on either side, the session's last message names a proposal about the brand voice's rule against loss framing and P02's planned Hook; two of the change's runs queued a second proposal beside it.
No session's event record, on either side, holds a patch that adds a `supersedes:` line, and no session's brief listed the notice of an Instructions change, since no example's queue holds one.

The launcher's counts of each session, summed for each side:

| Set and runs | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Draft claims with a code location, without | Agent seconds | Cost (USD, API prices) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Package review, first run, `main` | 10 | 10 | 10 | 160 of 160 | 13 | none written | 994 | 0.107 |
| Package review, first run, change | 10 | 10 | 10 | 160 of 160 | 11 | none written | 1,017 | 0.110 |
| Package review, four more runs of 3, 4, 8, 10, `main` | 16 | 16 | 16 | 256 of 256 | 17 | none written | 1,496 | 0.159 |
| Package review, four more runs of 3, 4, 8, 10, change | 16 | 16 | 16 | 256 of 256 | 18 | none written | 1,547 | 0.166 |
| Post Drafts, `main` | 10 | 10 | 9 | 108 of 110 | 2 | 12, 1 | 1,126 | 0.113 |
| Post Drafts, change | 10 | 10 | 9 | 110 of 110 | 3 | 15, 1 | 1,294 | 0.120 |

On both sides the one Post Drafts session whose closing line was `Session: incomplete` was example 16's.
Altogether the check ran 72 sessions, 7,474 seconds of agent time, about 0.78 dollars at API prices.

What the numbers show: the counts the launcher keeps of each session are the same or within a session's variance on both sides, and Post Drafts held the same checks on both sides.
In the Package review set, the first run had three examples fail with the change that held on `main`; over five runs each, the four examples that failed held 8 of 20 times on `main` and 6 of 20 with the change, every one of them failing on both sides, which is no example that held on `main` every time and failed with the change.
The sample does not tell a difference of that size from the run-to-run variance the learning-loop check recorded (`docs/live-checks/20261014-gr0wthlab-learning-loop.md`).

### What was not exercised

- A session with the real agent whose brief lists the notice of a kept Instructions change: no example set holds one, so whether the new wording keeps the agent from writing such an item rests on the unit tests that hold the brief line and on the launcher's unchanged refusal, which the whole-run test above shows.
- The Rejection reasons session, which also carries `items.md`: it has no example set.
- A weekly run in the production clone.

## Round 2: the final guidance, with the exact-repeat sentence, on `main` as it moved

Commit `0fd4683` changes one more sentence of `items.md`: the launcher refuses only an exact repeat of an open or decided item, the same kind, `# ` title, and proposal text once case and spacing are ignored (`exchange.item_hash`), so a reworded repeat is the session's own to catch.
`main` had moved to `3789b3ffb769e64696af8cf7f0e95e414f047e43`, which changes the weekly-run Instructions too, so this round compared that commit with the same commit plus this branch's three commits, cherry-picked in a throwaway clone without conflict as `f87ee531379ce8d8b086a2be014ba7669ebcebce` (`src` tree `6d6ed98420229e2d0dcb67f9e5621a3b92ec3b2d`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657` on both sides).
The two clones' `src/` differ in `report.py`, `items.md`, and four test files, and `src/instructions/` differs only by the three lines this change adds to `items.md`.
Run on 2026-10-15 from 13:32 to 13:57 PDT for the example sets, with the same scratch script, Codex CLI and effort as round 1.

### The unit suite and lint

| Command | Where | What the records showed |
| --- | --- | --- |
| `ruff check` and `ruff format --check`, as CI runs them | the worktree at `0fd4683` | all checks passed; 101 files already formatted |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | the clone at `f87ee53` | 1,482 tests OK in 3,881 seconds, from 13:33 to 14:38, beside the example-set runs |

### The example sets, with the real agent

Each example of both sets once on each side, from 13:32 to 13:39 (lab run identifiers after `20261011T230000Z-on-demand-`):

| Set | Example | `main` run | `main` checks held | change run | change checks held |
| --- | --- | --- | --- | --- | --- |
| Package review | 1 | `c32a` | 2 of 2 | `f09f` | 2 of 2 |
| Package review | 2 | `7191` | 2 of 2 | `8b73` | 2 of 2 |
| Package review | 3 | `35b3` | 1 of 2 | `669a` | 2 of 2 |
| Package review | 4 | `1e8e` | 2 of 2 | `a940` | 1 of 2 |
| Package review | 5 | `9c6a` | 2 of 2 | `c0c1` | 2 of 2 |
| Package review | 6 | `f216` | 2 of 2 | `3399` | 2 of 2 |
| Package review | 7 | `11f7` | 2 of 2 | `ab8d` | 2 of 2 |
| Package review | 8 | `a373` | 1 of 2 | `def3` | 2 of 2 |
| Package review | 9 | `dc7b` | 1 of 2 | `9aa6` | 1 of 2 |
| Package review | 10 | `4fce` | 2 of 3 | `6007` | 2 of 3 |
| Post Drafts | 1 | `aecb` | 4 of 4 | `036e` | 4 of 4 |
| Post Drafts | 2 | `d03b` | 3 of 3 | `115b` | 3 of 3 |
| Post Drafts | 8 | `ab1b` | 1 of 1 | `1229` | 1 of 1 |
| Post Drafts | 16 | `435e` | 2 of 3 | `e5f5` | 2 of 3 |
| Post Drafts | 17 | `3cd4` | 5 of 5 | `c046` | 5 of 5 |
| Post Drafts | 18 | `ac0c` | 4 of 4 | `e26a` | 4 of 4 |
| Post Drafts | 19 | `f09a` | 4 of 4 | `1e42` | 4 of 4 |
| Post Drafts | 20 | `9b7a` | 5 of 5 | `1061` | 5 of 5 |
| Post Drafts | 21 | `b2bd` | 3 of 3 | `2548` | 2 of 3 |
| Post Drafts | 22 | `2ccc` | 3 of 3 | `cdf6` | 3 of 3 |

Package review examples 3, 4, 8, and 10, the four round 1 re-ran, ran four more times on each side, and Post Drafts examples 16 and 21 four more times on each side, from 13:34 to 13:57; a run marked `*` did not hold every check:

| Example | `main` runs | `main` all checks held, of five | change runs | change all checks held, of five |
| --- | --- | --- | --- | --- |
| Package review 3 | `83fd*`, `a6b6*`, `eeb7*`, `66d8*` | 0 | `3863*`, `9005`, `6d05*`, `2189` | 3 |
| Package review 4 | `8e2b`, `1f58*`, `40cc`, `bf0e` | 4 | `d460`, `a2e9`, `e257*`, `a2b5*` | 2 |
| Package review 8 | `4131*`, `ba40`, `3e5e*`, `d061*` | 1 | `9a14`, `22bf`, `dcbc*`, `8f69*` | 3 |
| Package review 10 | `459b*`, `8a9b*`, `ac07*`, `9749*` | 0 | `98aa*`, `991b*`, `d603*`, `4073*` | 0 |
| Post Drafts 16 | `0102*`, `63d5*`, `4ae1*`, `7dd4*` | 0 | `9e8d*`, `2969*`, `f2c8*`, `e19e*` | 0 |
| Post Drafts 21 | `c859*`, `16f6`, `4234`, `02d4*` | 3 | `0405`, `83ae`, `5d63`, `0adc*` | 3 |

Over five runs each, the four Package review examples held every check 5 of 20 times on `main` and 8 of 20 with the change.
Post Drafts example 21 held every check 3 of 5 times on each side; in each run of it that did not, on either side, the session's closing line says it wrote no package-change proposal because the quote record it took a Hook change to need was absent.
Example 16 held 0 of 5 on each side, as in round 1.
No session's event record, on either side, holds a patch that adds a `supersedes:` line.

The launcher's counts of each session, summed for each side over every run of this round:

| Set and side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Draft claims with a code location, without | Agent seconds | Cost (USD, API prices) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Package review, `main` | 26 | 26 | 25 | 416 of 416 | 34 | none written | 2,316 | 0.257 |
| Package review, change | 26 | 26 | 26 | 416 of 416 | 28 | none written | 2,016 | 0.225 |
| Post Drafts, `main` | 18 | 18 | 11 | 198 of 198 | 5 | 22, 5 | 1,879 | 0.198 |
| Post Drafts, change | 18 | 18 | 11 | 198 of 198 | 5 | 24, 5 | 1,820 | 0.189 |

The one Package review session on `main` whose closing line was `Session: incomplete` was example 10's first run.
Altogether this round ran 88 sessions, 8,031 seconds of agent time, about 0.87 dollars at API prices.

What the numbers show: with the final guidance, the counts the launcher keeps of each session are the same or within a session's variance on both sides.
Every example run once held every check on both sides or failed on both, except Package review 3, 4, and 8 and Post Drafts 21, which were run five times each; each of those failed on both sides, and Package review 3, 4, and 8 together held every check 5 of 15 times on `main` and 8 of 15 with the change.
The difference between the sides in the four noisy Package review examples went toward `main` in round 1 (8 to 6 of 20) and toward the change in this round (5 to 8 of 20).

### What was not exercised

- A session with the real agent whose brief lists the notice of a kept Instructions change, or whose queue holds an item a reworded proposal would repeat: no example set holds either, so the wording's effect where it applies was not measured; the brief line rests on the unit tests that hold it, and both refusals on the launcher's unchanged rules.
- The Rejection reasons session, which also carries `items.md`: it has no example set.
- A weekly run in the production clone.

## Round 3: on the merged head

`main` moved to `b7575956cdff0a0223ac4ad802c57fda15002181`, the Hook claim fix, which changed `post-drafts.md` and the brief's Review Queue lines (each package-change proposal listed with its item file, and a line asking the session to read each before writing one).
Merge commit `662a3906b460d6179a53947ab3aae6d2483c1a27` brought it in (`src` tree `3176d06863f3f313189d5db08377d27697efbce7`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`).
`report.item_lines` was the one conflict: the merged head keeps this change's header and its mark on an Instructions notice, and `main`'s item file on each proposal's line.
The `items.md` sentences of this change say nothing the brief's new line says: the brief tells the session to read each proposal's file, and `items.md` that the launcher refuses only an exact repeat.
The text sessions of both example sets read changed with the merge, so both sets ran again, `main` at `b757595` on one side and the merged head on the other, whose `src/instructions/` differ only by this change's three lines in `items.md`.
Run on 2026-10-15 from 15:37 to 16:23 PDT, with the same scratch script, Codex CLI and effort as round 1; `git status` was empty in the worktree before and after.

### The unit suite and lint

| Command | Where | What the records showed |
| --- | --- | --- |
| `ruff check` and `ruff format --check`, as CI runs them | the worktree at `662a390` | all checks passed; 107 files already formatted |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | a clone at `662a390` | 1,483 tests OK in 2,719 seconds, from 15:37 to 16:23, beside the example-set runs |

### The example sets, with the real agent

Each example of both sets once on each side, from 15:37 to 15:43 (lab run identifiers after `20261011T230000Z-on-demand-`):

| Set | Example | `main` run | `main` checks held | merged head run | merged head checks held |
| --- | --- | --- | --- | --- | --- |
| Package review | 1 | `ec7a` | 2 of 2 | `d9aa` | 2 of 2 |
| Package review | 2 | `2b2a` | 2 of 2 | `173c` | 2 of 2 |
| Package review | 3 | `1e05` | 1 of 2 | `a6bf` | 1 of 2 |
| Package review | 4 | `a3a2` | 2 of 2 | `251c` | 2 of 2 |
| Package review | 5 | `c0b4` | 2 of 2 | `2ecf` | 2 of 2 |
| Package review | 6 | `da1d` | 2 of 2 | `c174` | 2 of 2 |
| Package review | 7 | `0e21` | 2 of 2 | `129f` | 2 of 2 |
| Package review | 8 | `be31` | 2 of 2 | `b182` | 1 of 2 |
| Package review | 9 | `5962` | 2 of 2 | `c0fa` | 1 of 2 |
| Package review | 10 | `4b02` | 2 of 3 | `b0dd` | 2 of 3 |
| Post Drafts | 1 | `3e53` | 4 of 4 | `adfb` | 4 of 4 |
| Post Drafts | 2 | `e385` | 3 of 3 | `51e6` | 3 of 3 |
| Post Drafts | 8 | `30b9` | 1 of 1 | `693c` | 1 of 1 |
| Post Drafts | 16 | `f6c7` | 3 of 3 | `b3a8` | 3 of 3 |
| Post Drafts | 17 | `1da4` | 5 of 5 | `a5c5` | 5 of 5 |
| Post Drafts | 18 | `4646` | 4 of 4 | `3a62` | 4 of 4 |
| Post Drafts | 19 | `e586` | 4 of 4 | `ba9a` | 4 of 4 |
| Post Drafts | 20 | `05de` | 5 of 5 | `9846` | 5 of 5 |
| Post Drafts | 21 | `7013` | 3 of 3 | `44e0` | 3 of 3 |
| Post Drafts | 22 | `3233` | 3 of 3 | `b5a0` | 3 of 3 |

Package review examples 3, 4, 8, and 10 and Post Drafts examples 16 and 21, the ones earlier rounds re-ran, ran twice more on each side; a run marked `*` did not hold every check:

| Example | `main` runs | `main` all checks held, of three | merged head runs | merged head all checks held, of three |
| --- | --- | --- | --- | --- |
| Package review 3 | `76ee*`, `eb4b*` | 0 | `c6ba`, `0852*` | 1 |
| Package review 4 | `7c69`, `a48e*` | 2 | `930f`, `e03e*` | 2 |
| Package review 8 | `6e9e*`, `dab1` | 2 | `e108`, `5646*` | 1 |
| Package review 10 | `0f7a*`, `8567*` | 0 | `f2f9*`, `26f7` | 1 |
| Post Drafts 16 | `34e6`, `c35f` | 3 | `eb88`, `b8f7` | 3 |
| Post Drafts 21 | `56d8`, `e3c9` | 3 | `c89a`, `3c85` | 3 |

The four Package review examples held every check 4 of 12 times on `main` and 5 of 12 on the merged head.
Package review example 9 failed once on the merged head, by queuing one proposal where none is expected; that session's last message names a proposal about the brand voice's rule against loss framing and P02's Hook, the proposal that each failed run of example 8 queued on both sides in round 1, and example 9 failed the same check on both sides in round 2.
Every Post Drafts run on both sides held every check, examples 16 and 21 included.
No session's event record, on either side, holds a patch that adds a `supersedes:` line.

The launcher's counts of each session, summed for each side over every run of this round:

| Set and side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Draft claims with a code location, without | Agent seconds | Cost (USD, API prices) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Package review, `main` | 18 | 18 | 17 | 288 of 288 | 20 | none written | 1,338 | 0.174 |
| Package review, merged head | 18 | 18 | 18 | 288 of 288 | 20 | none written | 1,351 | 0.163 |
| Post Drafts, `main` | 14 | 14 | 14 | 152 of 154 | 8 | 18, 3 | 1,374 | 0.167 |
| Post Drafts, merged head | 14 | 14 | 14 | 154 of 154 | 8 | 19, 3 | 1,379 | 0.160 |

The one session whose closing line was `Session: incomplete` was `main`'s example 10 run `0f7a`.
Altogether this round ran 64 sessions, 5,443 seconds of agent time, about 0.66 dollars at API prices.

What the numbers show: on the merged head the counts the launcher keeps of each session are the same or within a session's variance as on `main`, both sets held the same number of examples in full (10 of 18 Package review runs and 14 of 14 Post Drafts runs on each side), and the examples that failed did so on both sides across the three rounds.
What round 2 says was not exercised holds for this round too.

## Round 4: the Weekly Read decision named, and the repeat rule in the launcher's terms

The review of the merged head found two places where the agent was not told exactly what the launcher refuses, and this round's change closes both:

- `Ledger.check_incoming` refuses any item that supersedes an open Weekly Read decision, since `queue.FROM_DRAFT` holds that kind, and neither `items.md` nor the brief said so.
  `items.md` now says a Weekly Read decision cannot be superseded and changes only through the Weekly Read memo; the brief's header names it beside the others, and its line in the brief's list of open items carries the mark "which changes only through the Weekly Read memo".
- `items.md` said the launcher refuses only an exact repeat.
  It now says an item is refused as a repeat when its kind, `# ` title, and text match an open or decided item's once case and spacing are ignored, the text being a proposal's `## Proposal` section and a Dispatch request's `## Request` section (`exchange.item_hash`), and also when it has the kind and title of a queued item whose file the launcher could not read (`queue.may_repeat`); any other repeat is the session's own to catch.

This round's code is not committed yet: it is commit `c368c0e5ecf73d887868b18822bfaaa21808ce82` with the change on top, `src` tree `e591ea8c80317cbc9acd00a9eb56d498a6696c88` and `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
The other side is `main` at `05006936783d2e2cb6f08d91fa675182f0f6de24` (`src` tree `fb1d365d5c58b6b74a35a0c1bf1b13c777abab32`, the same as `b757595`'s, and the same `config` tree).
The two sides' `src/instructions/` differ only in `items.md`: the change's lines that name a Weekly Read decision and the notice of an Instructions change, and its three lines of the repeat rule in place of `main`'s one.
Run on 2026-10-15 from 16:45 to 17:34 PDT, Codex CLI `codex-cli 0.160.0`, at the model and reasoning effort in `config/guardrails/runtime.json` (`gpt-6-luna`, high).

### The gap before this round

`ItemLinesTest` in `src/tests/test_report.py` now lists an open Weekly Read decision among the open items, and `WeeklyReadRunTest.test_no_item_of_the_agent_s_supersedes_a_weekly_read_decision_and_the_brief_says_so` in `src/tests/test_weekly_read_cycle.py` queues a read's decision items, has the stand-in agent write a proposal whose `supersedes:` names one of them, and reads the Package review session's brief and the run report.
Run against round 3's `report.py` in a throwaway copy, both failed; both pass on the change.

### The unit suite and lint

| Command | Where | What the records showed |
| --- | --- | --- |
| `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` (ruff 0.15.20) | the worktree with the change | all checks passed; 107 files already formatted |
| `/usr/bin/python3 -m unittest discover -s src/tests -t src` | a clone of the worktree's files, `src` tree `e591ea8` | 1,484 tests OK in 2,841 seconds, from 16:46 to 17:34, beside the example-set runs |

### The preflight and the boundary check

From this work's linked worktree, against Mandu and the Product checkouts as they are, with logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`.
`git status --porcelain` printed the same 6 changed files, with the same SHA-256, before the preflight and after the check.
`show-config` printed the configuration fingerprint `258ebc6a8aa74a5c2da1c4986bd50032dc364581194246fe1984e3208a7f8480`; its output names this worktree's own path.

- `src/bin/gr0wthlab preflight`, run twice at 16:45, passed both times: six areas writable, 22 paths refused, among them the six folders of the Founder's records, the Instructions in force, and the example sets; no breach; a listing of the footage place `~/Mandu/projects/RepToday` refused; and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 16:46:03 to 16:46:57, passed at its first attempt as `20261015T234605Z-on-demand-9a45`, with `gpt-6-luna` at `high` reasoning effort and 42.5 s of agent time: 49 steps to prove, 28 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials naming the run's sentinels or the check's listeners, the footage place's read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, no local connection through, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and no change since the snapshot from before the check.

### The example sets, with the real agent

A scratch script outside the repository called each side's own `examples.run_example`, as in round 1, with up to ten sessions at a time.
Each lab's brief listed two open items, the Waitlist Dispatch request and the filming plan, each marked as filed by the launcher, under the header of its side: all 48 change-side briefs carried the change's header, which names a Weekly Read decision and the notice of an Instructions change, and all 48 `main` briefs carried `main`'s.
No brief listed a Weekly Read decision or the notice of an Instructions change, since no example's queue holds one.

Each example of both sets once on each side, from 16:47 to 16:54 (lab run identifiers after `20261011T230000Z-on-demand-`):

| Set | Example | `main` run | `main` checks held | change run | change checks held |
| --- | --- | --- | --- | --- | --- |
| Package review | 1 | `064a` | 2 of 2 | `c6eb` | 2 of 2 |
| Package review | 2 | `2306` | 2 of 2 | `c235` | 2 of 2 |
| Package review | 3 | `464a` | 1 of 2 | `25d9` | 1 of 2 |
| Package review | 4 | `4d3e` | 2 of 2 | `1fec` | 2 of 2 |
| Package review | 5 | `c0e9` | 2 of 2 | `a254` | 2 of 2 |
| Package review | 6 | `a732` | 2 of 2 | `6e06` | 2 of 2 |
| Package review | 7 | `68ec` | 2 of 2 | `f5ce` | 2 of 2 |
| Package review | 8 | `9351` | 2 of 2 | `6069` | 1 of 2 |
| Package review | 9 | `220a` | 2 of 2 | `868a` | 1 of 2 |
| Package review | 10 | `8707` | 2 of 3 | `ac91` | 2 of 3 |
| Post Drafts | 1 | `cd9f` | 4 of 4 | `cff6` | 4 of 4 |
| Post Drafts | 2 | `cc92` | 3 of 3 | `e23a` | 3 of 3 |
| Post Drafts | 8 | `cf2a` | 1 of 1 | `aa60` | 1 of 1 |
| Post Drafts | 16 | `9253` | 3 of 3 | `6e14` | 3 of 3 |
| Post Drafts | 17 | `0385` | 5 of 5 | `231e` | 5 of 5 |
| Post Drafts | 18 | `670c` | 4 of 4 | `83b0` | 4 of 4 |
| Post Drafts | 19 | `3ac8` | 4 of 4 | `8a6d` | 4 of 4 |
| Post Drafts | 20 | `ce0e` | 5 of 5 | `ec45` | 5 of 5 |
| Post Drafts | 21 | `9f9e` | 3 of 3 | `ae5f` | 3 of 3 |
| Post Drafts | 22 | `9c94` | 3 of 3 | `1e4b` | 3 of 3 |

Package review examples 3, 4, 8, and 10 and Post Drafts examples 16 and 21, the ones earlier rounds re-ran, and Package review example 9, which held on `main` and not with the change, ran four more times on each side, from 16:54 to 17:04; a run marked `*` did not hold every check:

| Example | `main` runs | `main` all checks held, of five | change runs | change all checks held, of five |
| --- | --- | --- | --- | --- |
| Package review 3 | `4537*`, `63aa*`, `e27e*`, `8804*` | 0 | `a4de*`, `9e76*`, `2d71`, `ed15*` | 1 |
| Package review 4 | `75a1`, `4769`, `2460`, `c13a` | 5 | `7b4a*`, `3b44`, `10d6`, `d7ec` | 4 |
| Package review 8 | `cc76*`, `5ff7*`, `61df*`, `5199*` | 1 | `c8e1*`, `62e8*`, `9bf5*`, `a971*` | 0 |
| Package review 9 | `8ca1*`, `ac9a`, `9449*`, `6f7b` | 3 | `11ea*`, `1b1b*`, `c7bb`, `7f72` | 2 |
| Package review 10 | `8c48*`, `f52c*`, `09dd*`, `65a9` | 1 | `af61*`, `af25*`, `9f4c*`, `f5cd*` | 0 |
| Post Drafts 16 | `719c`, `d948`, `7646`, `99db` | 5 | `0796`, `38af`, `278a`, `7c2f` | 5 |
| Post Drafts 21 | `3584`, `7552`, `026b`, `269a` | 5 | `82dc`, `565d`, `ff7c`, `e4b6` | 5 |

Over five runs each, the five Package review examples held every check 10 of 25 times on `main` and 7 of 25 with the change; without example 9, which earlier rounds did not re-run, 7 of 20 and 5 of 20.
Examples 3, 8, 9, and 10 failed at least once on each side.
Example 4 held 5 of 5 on `main` and 4 of 5 with the change; on `main` it failed once in each of rounds 1, 2, and 3.
In its one failed run, `7b4a`, the session queued one proposal, to remove the cleared trademark blocker, and none citing both `cadence-14-day.md` and `angles.md`.
The failing checks were otherwise the ones earlier rounds saw: in 3 and 10 no queued proposal cited both `ab-pairs.md` and `angles.md`, and a proposal was queued in 8, a package whose files agree, and in 9, one that differs only in text it marks as history.
In 11 of the 14 runs of 8 and 9 that failed, on both sides, a queued proposal's title names the loss-framing rule or the score's factual behavior, and in the other three it names the trademark.
Every Post Drafts run on both sides held every check.
No item any session wrote named `supersedes`: no queued entry in any lab carries it, and no set-aside reason names it.

The launcher's counts of each session, summed for each side over every run of this round:

| Set and side | Sessions | Ran to their end | Closing line `Session: complete` | Package files read of those listed | Proposals queued | Draft claims with a code location, without | Agent seconds | Cost (USD, API prices) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Package review, `main` | 30 | 30 | 29 | 480 of 480 | 28 | none written | 2,269 | 0.292 |
| Package review, change | 30 | 30 | 28 | 479 of 480 | 31 | none written | 2,404 | 0.319 |
| Post Drafts, `main` | 18 | 18 | 18 | 195 of 198 | 12 | 22, 6 | 1,694 | 0.223 |
| Post Drafts, change | 18 | 18 | 18 | 195 of 198 | 12 | 23, 5 | 1,930 | 0.225 |

The three sessions whose closing line was `Session: incomplete` were `main`'s example 3 run `464a` and the change's example 3 run `ed15` and example 8 run `a971`; each names a Hook proposal it did not write, for want of a kept Listening quote record.
Altogether this round ran 96 example sessions, 8,297 seconds of agent time, about 1.06 dollars at API prices, beside the boundary check's one.

What the numbers show: with the change, the counts the launcher keeps of each session are the same or within a session's variance as on `main`, and every Post Drafts run held every check on both sides.
In the Package review set, the difference between the sides in the examples re-run went toward `main` in round 1 (8 to 6 of 20), toward the change in round 2 (5 to 8 of 20) and round 3 (4 to 5 of 12), and toward `main` in this round (7 to 5 of 20 for the same four examples).
The sample does not tell a difference of that size from the run-to-run variance those rounds recorded.

### What was not exercised

- A session with the real agent whose brief lists an open Weekly Read decision or the notice of a kept Instructions change, or whose queue holds an item a reworded proposal would repeat: no example set holds one, so the wording's effect where it applies was not measured; the brief's header and marks rest on the unit tests that hold them, and the refusals on the launcher's unchanged rules.
- The Rejection reasons session, which also carries `items.md`: it has no example set.
- A weekly run in the production clone.
