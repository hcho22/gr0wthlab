# An open item is never taken back because something could not be read (US-ME07, US-ME08)

The launcher withdraws, closes, or supersedes an open Review Queue item only on what a record it could read says: when a read fails, the item stands under its identifier, its workflow's output reads incomplete with the real reason, and the run's notice names the item (`queue.stands`).
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
