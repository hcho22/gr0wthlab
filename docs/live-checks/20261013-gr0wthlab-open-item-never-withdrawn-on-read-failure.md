# An open item is never taken back because something could not be read (US-ME07, US-ME08)

The launcher withdraws, closes, or supersedes an open Review Queue item only on what a record it could read says.
Where a failed read would otherwise have taken an open item back or asked it again, the item stands under its identifier, its workflow's output reads incomplete with the real reason, and the run's notice names the item (`queue.stands`).
Those places judge an open item: the check of an open post, message, reply, or recruiting item against its Draft and what that check reads, an open invitation or Waitlist ask while a report of the Founder's cannot be read, an open follow-up whose record of the first message cannot be read, the open filming plan while the kit cannot be read, a Dispatch request's open item whose item file cannot be read, and an item in `incoming/` that supersedes an open item whose item file cannot be read.
Where a whole step did not run because its source could not be read, no item was judged: the output always reads incomplete in the run report with the real reason, and no item of that step is touched or listed.
Those are recruiting while the Waitlist view or the Beta Build record cannot be used, a Dispatch request whose reviewed text cannot be read, the post Drafts while the calendar cannot be read, outreach while the channel plan or the kit cannot be read, replies while the kit cannot be read, and the video of a day whose copy the Founder approved while its Draft cannot be read.
The run's notice names such a source only where its read failed as a source (a package file the snapshot could not read, the Waitlist view, the Beta Build record) or was recorded as a launcher problem (a reviewed Dispatch text, a kit that could not be prepared), and in the line that says no video was cut for an approved day.
A calendar or channel plan that was read but could not be parsed or decoded is told in the run report, and the notice has no line of its own for it; while the window's filming plan is open, though, that plan stands on a calendar that fails this way, as on any kit file, so the notice's list of open items not checked again names the plan with the kit file as its reason.
This file holds every round of that change's live checks.

## Re-check after the change and its merge with main

This work changes launcher code in every workflow that takes an open item back: `queue.py`, `posts.py`, `drafts.py`, `codebase.py`, `filming.py`, `footage.py`, `messages.py`, `beta.py`, `beta_drafts.py`, `dispatch.py`, `cycle.py`, and `report.py`.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.
The branch was brought up to `main` at `eb1bbbd` with one merge commit, `dca38dc`, whose two conflicts, in `filming.py` and `report.py`, were resolved by keeping both sides.
One more commit, `e25eb75`, changes four lines of the US-ME02 spike note and no code.
On `e25eb7521b8576e376a73e4c3a54482e363bbd32` the full unit suite passed under `/usr/bin/python3`, 1045 tests, as did ruff 0.15.20.

Every check below ran on 2026-10-12, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.
A run identifier carries its time in UTC, so each begins `20261013`.

### The boundary

Both checks ran from this work's linked worktree at `e25eb7521b8576e376a73e4c3a54482e363bbd32`, whose `src/` is tree `777368390cb275610d4dcb2a683ef7d43ae25c1d` and whose `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, with `git status` empty before the preflight and after the check, against Mandu and the Product checkouts as they are.
The configuration fingerprint `show-config` prints there is `32d7295b6d2f3613c44353b79ec3940bd15d2ed461ed26d29314a20584d8ed43`.
Their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.

- `src/bin/gr0wthlab preflight`, started at 21:38, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 21:38, passed at its first attempt, as `20261013T043825Z-on-demand-3c24`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the first on-demand run below and after the boundary check; the on-demand runs read none of them.

### The change itself, through the launcher on demand

Before those two checks, from 21:20 to 21:26, the change was seen live in three runs one after another, each started with `src/bin/gr0wthlab run` from a throwaway clone of `e25eb7521b8576e376a73e4c3a54482e363bbd32` in the Mac's temporary folder, network off for the agent as always.
Its inputs were throwaway ones, set with the `GR0WTHLAB_MANDU_DIR`, `GR0WTHLAB_REPTODAY_DIR`, `GR0WTHLAB_IMMERSE_DIR`, `GR0WTHLAB_EXCHANGE_DIR`, and `GR0WTHLAB_LOG_DIR` overrides: the post-Draft example set's synthetic package as Mandu, its synthetic Product code as a git checkout, an empty folder for the other Product, and an empty exchange folder.
In the clone's configuration no network source was listed, no outreach message was due, and no Product filmed; nothing else differed from the commit.
Its configuration fingerprint, `31649dfb29419ac84dfb653693efedb6efe278d65f73ca0bbb02452c725fe0ef`, differs from the one above because its locations do.
The first run used the real task definition.
The other two used a throwaway task definition that only re-runs the checks, so the agent changed no file; what changed between runs was changed by hand.

| Run | What was done by hand before it | What it showed |
| --- | --- | --- |
| `20261013T042050Z-on-demand-b6f1` | Nothing | The real task definition: the agent wrote the seven post Drafts in 2 min 57 s; three passed and were queued, `20261012-post-w1-day-01`, `-day-03`, and `-day-04`, and four were blocked; Post Drafts read complete |
| `20261013T042401Z-on-demand-f829` | In the synthetic Product checkout, the git object of `Engine/ConsistencyScore.swift`, the one file day 3's claim cites, moved out of `.git/objects`, so that `git cat-file` on it exits non-zero while the branch still resolves to its commit | Day 3's row read `kept`, with "not checked again, since git could not read `Engine/ConsistencyScore.swift` in RepToday's code; the open item stands"; the three posts' queue entries were the same as after the first run, and no item was closed; Post Drafts read incomplete with that reason; the run's notice, `20261012-notice-run-problems-2`, listed `20261012-post-w1-day-03` among the open items left exactly as they are, with the same reason; days 1 and 4, whose claims cite other files, read "its Draft is unchanged and passes"; the Product's repository still read as read |
| `20261013T042454Z-on-demand-29e1` | The object put back | All three rows read "its Draft is unchanged and passes"; the three posts' queue entries were still the same as after the first run, nothing was closed, and no post was queued under a new identifier; Post Drafts read complete |

On `main` the second run's state withdraws the open post as "there is no file" with Post Drafts complete, and the third queues it again under a new identifier; a unit test holds that shape (`test_an_open_post_stands_under_its_id_while_git_cannot_read_the_file_its_claim_cites`).
The three runs' reports give their cost as about $0.026, $0.005, and $0.004 at API prices.

### What this re-check did not exercise

Only one of the fixed sites was run live: git's read of one file a post's claim cites.
The others stand on the unit tests, each a whole run with a stand-in agent: a Draft that cannot be read (a post, a message, a reply, a recruiting Draft), the Draft of an A/B pair's other leg, an edit record, a footage file an edit record names, the ledger's record of a video, a package file a recruiting Draft cites, the Founder's Beta Cohort reports, a Dispatch request's item file, an item that supersedes an open one whose file cannot be read, and the filming plan while the kit cannot be read.
Where this rule meets the video-file check, a post whose finished file is gone while its Draft cannot be read, was not run live and stands on a unit test.
No real withdrawal was made live; each stands on a unit test.
The failed read was made in a synthetic Product checkout, never in Mandu or a real Product checkout, which no check here may change.
No weekly run was made on a schedule, and Mandu's side was not shown the notice.

## Re-check after review

The review of this change asked for three fixes, and this round is the re-check of the code that holds them.
`beta.take_draft` reads a recruiting Draft the brief asked for, and removes one that holds what looks like an email address, before it weighs a report of the Founder's that could not be read.
`beta.decide` judges an open batch by the Waitlist's view before it holds a full count back for a report that could not be read: a batch the view shows has lost a sign-up is withdrawn with that reason, and no batch is made in its place on that count.
`dispatch.file` does not file a request again while the file of an item of it the Founder rejected cannot be read: the fingerprint the run state holds of that item settles it, and with neither record the request is held and the run reports the file.
`Ledger.check_incoming` sets aside an item in `incoming/` that has the kind and ask of a queued item whose file cannot be read and whose fingerprint no run state holds.
None of the four changes anything in a run where every file can be read.
The same repeat check for a proposed Angle (`listening.take_proposals`) and for a reviewed proposal (`proposals.file_once`) was left as it is, for the Founder to decide; `AGENTS.md` names it as a known gap.
The round changes launcher code in `beta.py`, `dispatch.py`, `queue.py`, `cycle.py`, and `report.py`.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.

Every check below ran on 2026-10-12, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- `/usr/bin/python3 -m unittest tests.test_dispatch tests.test_queue tests.test_beta tests.test_beta_cycle tests.test_cycle.DispatchRunTest tests.test_cycle.TakeInTest`, started once from `src/`, ran 127 tests, and all passed.
- The six tests this round adds were also run on the code of `156dfcf0ad4ec337870fd1ee0281b1f3969313f5`, the commit before the fixes, in a throwaway copy in the Mac's temporary folder with this round's test files copied over it, and none passed.
  Five failed on an assertion: the Draft that held an address was still in `workspace/`, the batch read as not stale, the rejected request was in the queue a second time, and the repeated item was queued, in a whole run and in the ledger's own test.
  The sixth ended in `KeyError: 'withdrawn'` where it reads the open batch's queue entry.

### The boundary

Both checks ran from the review's linked worktree, on `156dfcf0ad4ec337870fd1ee0281b1f3969313f5` with this round's changes in place and not yet committed.
Its `src/` is tree `db268f4a17f19433945f5f4f13e24e555f33dd39` and its `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the `config/` tree of the round above; both were the same after the boundary check as before the preflight.
`git status` was not empty, since the round's commit comes after its checks: it listed the same twelve changed files, and nothing else, before the preflight and after the boundary check.
The checks ran against Mandu and the Product checkouts as they are, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` prints there is `1fd7a1300daef25aba4297d52d84ad86d0341312a75c395ab0192f8737bcda14`.
It differs from the one above because the worktree does: the fingerprint covers the Codex command, which holds the checkout's own path.

- `src/bin/gr0wthlab preflight`, started at 22:20, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 22:20, passed at its first attempt, as `20261013T052016Z-on-demand-5024`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this re-check did not exercise

No run was started with `src/bin/gr0wthlab run` in this round, so none of the four changes was seen live.
Each stands on the unit tests named above, which are whole runs with a stand-in agent beside the tests of `beta.decide`, `dispatch.file`, and `Ledger.take_incoming`: a report that cannot be read with a Draft that holds an address, with a batch that lost a sign-up, with a batch that lost none, with a view that cannot be used, and with no open batch; a rejected request whose item file cannot be read with and without the run state's fingerprint, and with a fingerprint of another text; and an item in `incoming/` with the kind and ask of a rejected item whose file and fingerprint are both lost, beside one with another ask.
The whole unit suite was not run in this round.
The boundary check was run once, not as a streak.
No file was made unreadable in Mandu, in a real Product checkout, or in a real `ledger/`.
No weekly run was made on a schedule, and Mandu's side was not shown a notice.

## Re-check after the second review

The second review found a fault in the check of `incoming/` that the round above added.
The list of items whose item file could not be read was built after the launcher had filed its own items for the run, from fingerprints read before it filed them, so it also named every item filed earlier in the same run.
A run that filed a Dispatch request and then took in an item with that request's kind and ask and another body set the item aside, gave a read that had not failed as the reason, and marked the Review Queue output incomplete.
The round above says none of its four changes anything in a run where every file can be read: for that check this was not so on the code that round ran on, and it is so from this round on.
`cycle.run` now builds the list where it reads the fingerprints, from the entries the queue holds then, so the list names only items whose read was tried and failed.
The round also corrects a function's name, `proposals.file_once`, in `AGENTS.md` and in the round above.
It changes launcher code in `cycle.py` alone.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.

Every check below ran on 2026-10-12, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- `/usr/bin/python3 -m unittest tests.test_queue tests.test_dispatch tests.test_cycle.DispatchRunTest tests.test_cycle.TakeInTest`, started once from `src/`, ran 53 tests, and all passed.
- The one test this round adds is a whole run with a stand-in agent, in which the launcher files the Waitlist request and the agent writes an item with that request's kind and ask and another body.
  It was also run on the code of `3498be220fd367cacd064484bcdb394ae8e053c8`, the commit before the fix, in a throwaway copy in the Mac's temporary folder with this round's test file copied over it, and it failed on its first assertion: the open items were the request and a notice of the run's problems, where the test expects the request and the item the agent wrote.

### The boundary

Both checks ran from the review's linked worktree, on `3498be220fd367cacd064484bcdb394ae8e053c8` with this round's changes in place and not yet committed.
Its `src/` is tree `792df29422cd983f4d88709c38a1bbc9e8ae9978` and its `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the `config/` tree of both rounds above; both were the same after the boundary check as before the preflight.
`git status` was not empty, since the round's commit comes after its checks: it listed the same four changed files, and nothing else, before the preflight and after the boundary check.
The checks ran against Mandu and the Product checkouts as they are, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` prints there is `1fd7a1300daef25aba4297d52d84ad86d0341312a75c395ab0192f8737bcda14`, the one of the round above.

- `src/bin/gr0wthlab preflight`, started at 22:34, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 22:34, passed at its first attempt, as `20261013T053428Z-on-demand-bccf`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this re-check did not exercise

No run was started with `src/bin/gr0wthlab run` in this round, so the fix was not seen live.
It stands on the whole-run test named above, beside the tests of the round above in which an item file cannot be read, which still pass.
That test files a Dispatch request; a filming plan filed in the same run goes through the same list and has no test of its own here.
The whole unit suite was not run in this round.
The boundary check was run once, not as a streak.
No file was made unreadable in Mandu, in a real Product checkout, or in a real `ledger/`.
No weekly run was made on a schedule, and Mandu's side was not shown a notice.

## Re-check after the fourth review

The third review's one change was a sentence in `AGENTS.md`, with no launcher code, so it has no round here.
The fourth review asked for three changes, and this round is the re-check of the code that holds them.
An open follow-up whose record of the first message could not be read stayed open, but it was not weighed through `queue.stands`, so the run's notice did not name it among the open items not checked again.
`outreach.follow_up` now weighs it there and keeps it on the run's plan, and `cycle.left_standing` gathers it, so the notice names it as it names every other workflow's.
The follow-up still stays open under its identifier, and the Outreach Drafts output still reads incomplete with the same reason.
One thing the Founder sees changes with it: the notice of a run whose only problem was that failed read now holds two sections, so its title counts two problems where it named the one source before.
The reason given to an item in `incoming/` that supersedes an open item whose file cannot be read now states only what the records show: the file could not be read, so the open item stands and nothing replaces it in this run.
What happens to both items is as before: the new one is set aside and the open one stands.
The module docstring of `codebase.py` now names `ls-tree` among the git reads.
The round changes launcher code in `outreach.py`, `cycle.py`, and `queue.py`, and that docstring.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.

Every check below ran on 2026-10-12, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- `/usr/bin/python3 -m unittest tests.test_messages tests.test_queue tests.test_cycle tests.test_work_cycle.OutreachCycleTest`, started once from `src/`, ran 151 tests, and all passed; `tests.test_messages` holds the outreach unit tests.
- The five tests this round changes were also run on the code of `64b1c839d72e7852f480655b0ca585cf3645e86c`, the commit before the fixes, in a throwaway copy in the Mac's temporary folder with this round's test files copied over it, and none passed.
  The three follow-up tests failed where they look for the follow-up among the notice's open items not checked again, and the two take-in tests failed on the wording of the reason.

### The boundary

Both checks ran from the review's linked worktree, on `64b1c839d72e7852f480655b0ca585cf3645e86c` with this round's changes in place and not yet committed.
Its `src/` is tree `3a56be4bdacff5a1f70dc4da7c9a3e73ae4800ea` and its `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the `config/` tree of every round above; both were the same after the boundary check as before the preflight.
`git status` was not empty, since the round's commit comes after its checks: it listed the same eight changed files, and nothing else, before the preflight and after the boundary check.
The checks ran against Mandu and the Product checkouts as they are, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` prints there is `1fd7a1300daef25aba4297d52d84ad86d0341312a75c395ab0192f8737bcda14`, the one of the two rounds above.

- `src/bin/gr0wthlab preflight`, started at 23:03, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 23:03, passed at its first attempt, as `20261013T060325Z-on-demand-a90a`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this re-check did not exercise

No run was started with `src/bin/gr0wthlab run` in this round, so no change of it was seen live.
The follow-up change stands on three whole-run tests with a stand-in agent, one for each read a follow-up rests on: Mandu's `outreach/` folder that cannot be read, the record of the first message that is missing, and that record not in its format.
A fourth, which this round did not change, holds that a reply that was read still takes an open follow-up back.
The reason's wording stands on the ledger's own test and on one whole-run test.
The whole unit suite was not run in this round.
The boundary check was run once, not as a streak.
No file was made unreadable in Mandu, in a real Product checkout, or in a real `ledger/`.
No weekly run was made on a schedule, and Mandu's side was not shown a notice.

## Re-check after the fifth review

The fifth review asked for three changes, and this round is the re-check of the code that holds them.
Two items in `incoming/` that superseded the same open item, whose item file could not be read, put that open item in the run's notice twice, counted as two open items not checked again.
`Ledger.check_incoming` now adds an open item to the ones left standing once, however many items would have replaced it.
A day whose copy the Founder approved, with an edit record waiting and a Draft that could not be read, got no video and gave no gap: Post Drafts read complete.
`posts.read_day` now records that Draft as unread, so Post Drafts reads incomplete with the real reason.
The day's outcome is otherwise as before: no video is cut for it, its row and the notice say its Draft could not be read, and its open post is not touched.
The opening of this file, `AGENTS.md`, `docs/operations.md`, and the docstring of `queue.stands` said that every workflow weighs a failed read through `queue.stands` and that the notice names each item left standing.
That holds only where a failed read would otherwise have taken an open item back or asked it again.
Each of the four now says so, names those places, and says what a step that did not run because its source could not be read does instead; those steps, and what the notice says of them, are as they were.
The round changes launcher code in `queue.py` and `posts.py`.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.

Every check below ran on 2026-10-12, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- `/usr/bin/python3 -m unittest tests.test_posts tests.test_queue tests.test_filming tests.test_cycle.PostDraftsTest tests.test_cycle.TakeInTest`, started once from `src/`, ran 187 tests, and all passed.
  The test of the approved day is in `tests.test_filming`, and no test module reads `AGENTS.md`, `docs/operations.md`, or this file.
- The one test this round adds and the one it extends were also run on the code of `c6a5936310a2a822713a270c294cb028a3fbc14b`, the commit before the fixes, in a throwaway copy in the Mac's temporary folder with this round's test files copied over it, and both failed.
  The test of the approved day failed where it looks for the Draft in the Post Drafts row, and the ledger's test failed where it counts the open item once.

### The boundary

Both checks ran from the review's linked worktree, on `c6a5936310a2a822713a270c294cb028a3fbc14b` with this round's changes in place and not yet committed.
Its `src/` is tree `ab98ddd81f55a77836ecf0484e273cbfc4ff0c66` and its `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the `config/` tree of every round above; both were the same after the boundary check as before the preflight.
`git status` was not empty, since the round's commit comes after its checks: it listed the same seven changed files, and nothing else, before the preflight and after the boundary check.
The checks ran against Mandu and the Product checkouts as they are, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` prints there is `1fd7a1300daef25aba4297d52d84ad86d0341312a75c395ab0192f8737bcda14`, the one of the three rounds above.

- `src/bin/gr0wthlab preflight`, started at 23:38, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 23:38, passed at its first attempt, as `20261013T063836Z-on-demand-7056`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this re-check did not exercise

No run was started with `src/bin/gr0wthlab run` in this round, so no change of it was seen live.
The approved day stands on one whole-run test with a stand-in agent and stand-in video tooling, and the item left standing once stands on the ledger's own test.
The steps the four texts name as not run for want of their source were not changed in this round, and no check here ran them with their source unreadable.
The whole unit suite was not run in this round.
The boundary check was run once, not as a streak.
No file was made unreadable in Mandu, in a real Product checkout, or in a real `ledger/`.
No weekly run was made on a schedule, and Mandu's side was not shown a notice.

## Re-check after the sixth review

The sixth review found one sentence of the round above saying more than the launcher does.
It said, in the opening of this file, `AGENTS.md`, `docs/operations.md`, and the docstring of `queue.stands`, that where a whole step did not run because its source could not be read, the run's notice names the source.
That holds only where the read failed as a source or was recorded as a launcher problem, and for the video of an approved day, whose notice line says its Draft could not be read.
A calendar or channel plan that was read but could not be parsed or decoded is told in the run report, and the notice has no line of its own for it; while the window's filming plan is open, though, that plan stands on a calendar that fails this way, as on any kit file, so the notice's list of open items not checked again names the plan with the kit file as its reason.
Each of the four now says so; the rest of the sentence stood: the output always reads incomplete in the run report with the real reason, and no item of that step is touched or listed.
The round changes no behavior, no notice, and no test: its one change under `src/` is that docstring in `queue.py`.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.

Every check below ran on 2026-10-12, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- No test module reads `AGENTS.md`, `docs/operations.md`, or this file, so there was none of those to run.
  `/usr/bin/python3 -m unittest tests.test_queue`, the tests of the one file under `src/` this round touches, started once from `src/`, ran 23 tests, and all passed.

### The boundary

Both checks ran from the review's linked worktree, on `e2b30e0a100e76cee89ecc767ce34e664e4f92da` with this round's changes in place and not yet committed.
Its `src/` is tree `c94c758e23e48e5b662f763e270c90adac9a9abf` and its `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the `config/` tree of every round above; both were the same after the boundary check as before the preflight.
`git status` was not empty, since the round's commit comes after its checks: it listed the same four changed files, and nothing else, before the preflight and after the boundary check.
The checks ran against Mandu and the Product checkouts as they are, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` prints there is `1fd7a1300daef25aba4297d52d84ad86d0341312a75c395ab0192f8737bcda14`, the one of the four rounds above.

- `src/bin/gr0wthlab preflight`, started at 23:56, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 23:56, passed at its first attempt, as `20261013T065654Z-on-demand-bd14`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this re-check did not exercise

No run was started with `src/bin/gr0wthlab run` in this round.
The narrowed sentence describes code this round did not change, and no check here ran a step with its source unreadable or unparsed: what it says of the notice rests on the review's reading of that code.
The whole unit suite was not run in this round.
The boundary check was run once, not as a streak.
No file was made unreadable in Mandu, in a real Product checkout, or in a real `ledger/`.
No weekly run was made on a schedule, and Mandu's side was not shown a notice.

## Re-check after the seventh review

The seventh review found the round above had dropped an exception its own finding named.
That round wrote, in the opening of this file and in its own section, in `AGENTS.md`, in `docs/operations.md`, and in the docstring of `queue.stands`, that a calendar or channel plan that was read but could not be parsed or decoded is told in the run report alone, with no notice.
That is not so for the calendar while the window's filming plan is open: the plan then stands on the kit file, and the notice's list of open items not checked again names the plan with that file as its reason.
Each place now says that the notice has no line of its own for such a file, and says what it holds while the filming plan is open; the two sentences in this file, in its opening and in the round above, were corrected where they stand.
The round changes no behavior, no notice, and no test: its one change under `src/` is that docstring in `queue.py`.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 6.

Every check below ran on 2026-10-13, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- `/usr/bin/python3 -m unittest tests.test_queue`, started once from `src/`, ran 23 tests, and all passed.

### The boundary

Both checks ran from the review's linked worktree, on `de5fd4e22618db538dfeb4c82e7e91a3587c0c51` with this round's changes in place and not yet committed.
Its `src/` is tree `0e6ea0ca3ea4b60848aa1d9f220bf268cfbbe204` and its `config/` is tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the `config/` tree of every round above; both were the same after the boundary check as before the preflight.
`git status` was not empty, since the round's commit comes after its checks: it listed the same four changed files, and nothing else, before the preflight and after the boundary check.
The checks ran against Mandu and the Product checkouts as they are, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` prints there is `1fd7a1300daef25aba4297d52d84ad86d0341312a75c395ab0192f8737bcda14`, the one of the five rounds above.

- `src/bin/gr0wthlab preflight`, started at 00:09, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 00:09, passed at its first attempt, as `20261013T070911Z-on-demand-ec7b`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this re-check did not exercise

No run was started with `src/bin/gr0wthlab run` in this round.
The corrected sentence describes code this round did not change, and no check here ran a step with a calendar that could not be parsed.
What it says of the open filming plan stands on the unit test in which an open plan stands while a kit file that was read has lost its table; that test uses the Angle bank, and the calendar goes through the same code.
The whole unit suite was not run in this round.
The boundary check was run once, not as a streak.
No file was made unreadable in Mandu, in a real Product checkout, or in a real `ledger/`.
No weekly run was made on a schedule, and Mandu's side was not shown a notice.
