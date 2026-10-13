# The kept-video file check: a post is said to keep a video only while its finished file is there (US-ME09)

The launcher says a post shows or keeps a video only when the finished file is on disk and is the file the video's record and the post's entry name, and an open post whose file is lost gives way to the same post without a video.
This file holds every round of that change's live checks.
The first two rounds were written into [the US-ME02 spike note](../spikes/us-me02-runtime-boundary.md) and were moved here word for word in the merge with `main` that brought in this folder, with no new run.

## Re-check after the kept-video file check (US-ME09)

This work changes launcher code in filming: before it says a post shows or keeps a video it is not cutting, the launcher now checks that the finished file is on disk and is the file the video's record and the post's entry name (`filming.on_disk`).
It changes nothing in the permission profile, the Codex command, the fetch policy, or the Product registry.
The branch was brought up to `main` at `c08df9e` with one merge commit, `3763129`, which had no conflict; the full unit suite, 1019 tests, and ruff pass on it.

Both checks ran on 2026-10-12, Mac local time, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, from this work's linked worktree at `3763129`, its `git status` empty before and after, against Mandu and the Product checkouts as they are; the configuration fingerprint there is `1a8995e778d9b5a45bbaf2e59a5fc4f32c48069bfb8155ea43b08d8bf5ad56f8`.

- `src/bin/gr0wthlab preflight` passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check` passed at its first attempt, as `20261012T233034Z-on-demand-959b`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, git status, and a digest over every file outside `.git` were the same before the preflight and after the check.

The change itself was then seen live through the launcher on demand, network off, with ffmpeg 7.1.1, in five runs one after another from a throwaway checkout of `3763129` in the Mac's temporary folder; its fingerprint, `bf18aa81a7074fc303b1795303681917c27d6d3f3bf7c7d4931ca52ffb94166b`, differs because its locations do.
Its inputs were throwaway ones made as for the filming proofs in [the US-ME02 spike note](../spikes/us-me02-runtime-boundary.md#re-check-after-filming-us-me09): the filming example set's synthetic kit cut down to days 1 and 8, the synthetic Product checkout, one stand-in clip of ffmpeg's test pattern in a footage place set with `GR0WTHLAB_FOOTAGE_DIR`, a simulated approval of the filming plan in a throwaway exchange folder, and no network source listed.
The last three runs used a throwaway task definition that only re-runs the checks, so the agent changed no file; what changed between runs was changed by hand.

| Run | What was done by hand before it | What it showed |
| --- | --- | --- |
| `20261012T231145Z-on-demand-c7b4` | Nothing | The real task definition: the filming plan filed, day 1's post queued with no video yet |
| `20261012T232217Z-on-demand-e4c1` | The plan approved | The agent wrote day 1's edit record; the launcher rendered `assets/window-1/day-01-791d5f47aca2.mp4`, and `20261012-post-w1-day-01-2` shows it |
| `20261012T232335Z-on-demand-8277` | The clip moved out of the footage place, and the finished file's mode set to no access | The open post stood as it was; its row, the Filming row, the notice, and `check-edits` as the agent ran it all said the finished file could not be read, with `Permission denied`, and that nothing is said of whether the post keeps its video; the filming output read incomplete with that reason |
| `20261012T232411Z-on-demand-5eb4` | The mode put back, then the finished file deleted | `20261012-post-w1-day-01-3` took the open post's place with no `asset`, saying `Video file: none yet` with both reasons, no footage for shot `d01-s1` and the finished file gone; both report rows and the notice gave the same reasons, the notice saying which post gave way to which; nothing said the post keeps a video, and the filming output read complete |
| `20261012T232445Z-on-demand-ce83` | The clip put back | The video was cut again to the same path with the SHA-256 the first render had, and `20261012-post-w1-day-01-4` took the bare post's place showing it |

Each run cost one or two cents at API prices at most.

What this re-check did not exercise: a finished file changed in place, an approved day, an A/B pair, a slot change, and missing video tooling were not run live and stand on the unit tests, one of which makes a whole run with the real ffmpeg; no weekly run was made on a schedule; the Founder's real footage does not exist yet; and Mandu's side was not shown the notice.

## Re-check after the review of the kept-video file check

The review of that change took two parts of it out and corrected two more, all in `filming.py`, so the unit suite and both checks were run again on the launcher as it now is.

- The launcher reads the finished file of a video only for an open post (`Filming.look`).
  It no longer reads the file of a post the Founder approved, and no line of the run report or the notice, and no reason for an incomplete filming output, comes from one.
- `rebuild-asset` prints what it prints on `main`: the line that told what stands at the asset's path after a rebuild that put nothing there is gone.
- A run whose post Drafts could not be taken in ends with its report when a day's open post had been settled to give way to one without a video (`Filming.settle`).
  Before, such a run ended in a `KeyError` with no run report.
- Of an open post whose day is not due in the run, the run report and the notice say that the day is not due, that nothing is cut for it, and that the post stands as it is (`Shown.account`).
  Before, they said the video is cut again once it can be, which no run does for a day that is not due.
- `codex.py`, `boundary.py`, `launcher.py`, the probe, `runtime.json`, `fetch.json`, and `config/products.json` are unchanged, and the footage place is still not set.

On these files the full unit suite passed under `/usr/bin/python3`, 1019 tests with none skipped, as did ruff 0.15.20.

Both checks ran on 2026-10-12, Mac local time, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, from the linked worktree this review ran in, on its files before the commit that records them here was made, with `src/` at tree `9c517a53dcc3dee3f67289390ea54828d908d9df` and `config/` at tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the tree `config/` has at `8b2ef8a`.
The worktree's `git status` listed the same three changed files, `docs/operations.md`, `src/gr0wthlab/filming.py`, and `src/tests/test_filming.py`, before the preflight and after the check, `src/` was at the same tree after it, and this section was written after both.
Their configuration fingerprint was `f693ecd1d90e450aa578030d385a8d56052aceeb961b503dfbf322d5e1b07f9d`, which differs from the one above: the fingerprint covers the sandbox policy, and that policy names the path of the worktree a check runs from.
Their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.

- `src/bin/gr0wthlab preflight` passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check` passed at its first attempt, as `20261013T002112Z-on-demand-94f5`, whose identifier carries the time in UTC: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.
  It replaces `20261012T233034Z-on-demand-959b` above, which passed on the launcher as it then was.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the check.

The fix to `Filming.settle` was reproduced and then seen live through `src/bin/gr0wthlab run` on demand, network off, with ffmpeg 7.1.1 and the repository's no-model stand-in for the agent, which wrote the filming example set's Draft and edit record for day 1.
Each checkout was a throwaway one in the Mac's temporary folder, with the inputs of the proofs above: the synthetic kit cut down to days 1 and 8, the synthetic Product checkout, one stand-in clip of ffmpeg's test pattern in a footage place set with `GR0WTHLAB_FOOTAGE_DIR`, a simulated approval of the filming plan, and no network source listed.
The first checkout held `8b2ef8a`, the code before this review, and the other three held this review's files.
In each, day 1's post `20261012-post-w1-day-01` was first queued with its finished video, and what the table lists was then done by hand.

| Run | Code | What was done by hand before it | What it showed |
| --- | --- | --- | --- |
| `20261013T000009Z-on-demand-35b4` | `8b2ef8a` | The clip moved out of the footage place, the finished file deleted, and a folder put at the path the next post's item is written to, so that the write fails | The launcher ended with exit code 1 and a traceback, `KeyError: 1` in `Filming.settle`, and wrote no run report |
| `20261013T000039Z-on-demand-dd99` | This review's | The same, in a second checkout | Exit code 0 and a run report: `Post Drafts: not taken in` with the write's error, `Is a directory`, the open post as it was, and the report and the notice naming it and its finished file as gone |
| `20261013T000047Z-on-demand-3b14` | This review's | The folder removed | `20261012-post-w1-day-01-2` took the open post's place with no video, and the report and the notice said which post gave way to which and why |
| `20261013T000114Z-on-demand-5fe5` | This review's | In a third checkout: the finished file deleted, and the window's first sitting set to 2026-10-11, so that the run prepared day 8 only | The open post stood; the one line of the report and the one line of the notice that name it say that day 1 is not due this run, so nothing is cut for it and the post stands as it is |
| `20261013T000133Z-on-demand-3b16` | This review's | In a fourth checkout: the post approved by a simulated decision that a run took in, then the finished file deleted | The run queued nothing, its report holds no line about a finished file, and its `Filming plan and edits` output reads complete |

In the second checkout, `rebuild-asset` on that video's record, run while the clip was away, printed one line, that the record cannot be rebuilt, with `No such file or directory`, and ended with exit code 1; in the first, on `8b2ef8a`, it printed a second line saying the finished file is gone.

What this re-check did not exercise: the stand-in wrote every file of the five runs, so no model was called outside the boundary check; a finished file changed in place or one that cannot be read, an A/B pair, a slot change, and missing video tooling were not run live on this review's files and stand on the unit tests; no weekly run was made on a schedule; the Founder's real footage does not exist yet; and Mandu's side was not shown the notices.

A second review round then changed one heading of the run report, in `filming.py`, so both checks were run once more on the launcher as it now is.
The first round's files are commit `e790c0f`, whose `src` tree is the one named above.

- The heading over the run report's list of open posts whose finished file is gone, changed, could not be read, or has no record that can be read is now `Posts whose video's finished file was not confirmed as the file they name:`.
  The heading before said the file is not the file they name, which was untrue of the last two of those four.
  No line under the heading changed, the notice has no such heading, and the launcher does nothing it did not do before.
- `codex.py`, `boundary.py`, `launcher.py`, the probe, `runtime.json`, `fetch.json`, and `config/products.json` are unchanged.

On these files ruff 0.15.20 passed, and so did the `tests.test_filming` module under `/usr/bin/python3`, 94 tests with none skipped; the full unit suite was not run again.

Both checks ran on 2026-10-12, Mac local time, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, from the same worktree, on its files before the commit that records them here was made, with `src/` at tree `be3ed576ac5ce40af50cb706f243a406451d6a03` and `config/` at the tree named above.
The worktree's `git status` listed the same two changed files, `src/gr0wthlab/filming.py` and `src/tests/test_filming.py`, before the preflight and after the check, `src/` was at the same tree after it, and these paragraphs were written after both.
Their configuration fingerprint was again `f693ecd1d90e450aa578030d385a8d56052aceeb961b503dfbf322d5e1b07f9d`, and their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.

- `src/bin/gr0wthlab preflight` passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check` passed at its first attempt, as `20261013T004925Z-on-demand-270b`, whose identifier carries the time in UTC: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.
  It replaces `20261013T002112Z-on-demand-94f5` above, which passed on the launcher as it then was.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the check.

The heading was then seen in two run reports, through `src/bin/gr0wthlab run` on demand with the stand-in for the agent, in one more throwaway checkout made as the four above and holding this round's files, where day 1's post was first queued with its finished video.
In `20261013T005123Z-on-demand-0a46`, with the clip moved out of the footage place and the finished file's mode set to no access, the heading stood over the one line saying the file could not be read, with `Permission denied`, and that nothing is said of whether the post keeps the video; the open post stood, and the filming output read incomplete with that reason.
In `20261013T005124Z-on-demand-3ba1`, with the mode put back, the finished file deleted, and the first sitting set to 2026-10-11, it stood over the one line saying the file is gone and day 1 is not due this run.
Neither report holds the heading as it was before.

## Re-check after the guidance wording and the merge that moved this record

The validation run that held the two rounds above ended when its document step ran out of time, with its three commits kept (`e790c0f`, `9f06ec5`, `b2aecdf`).
After it, `main` at `c107a54` was merged in as `7fdfec5`, which moved this record here, and one commit, `e44f5ce`, reworded four sentences of the agent's guidance and one docstring.
The four sentences are in `src/instructions/weekly-run.md` and `workspace/instructions/filming.md`: where they said without condition that a day whose edit record is left as it is has a post that shows its video, they now say the day's open post names a video that cannot be cut again this run and that the table, or the KEPT line of `check-edits`, says whether the post keeps it.
No instruction changed, and no code.

All of this round ran on 2026-10-12, Mac local time, 19:00 to 19:30 PDT, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, on commit `e44f5ce11417f6bbb13de6e74224be4f474746d0`, whose `src` tree is `fff1145291f46ffc143559fa170340a8c30a4308` and whose `config` tree is `bfa79f76f468035578efd8d2c901b92c40c3adf9`.
The full unit suite, 1019 tests under `/usr/bin/python3`, and ruff pass on it.

### Both checks

From this work's linked worktree at `e44f5ce`, its `git status` empty before and after, against Mandu and the Product checkouts as they are; `show-config` printed the fingerprint `1a8995e778d9b5a45bbaf2e59a5fc4f32c48069bfb8155ea43b08d8bf5ad56f8`.

- `src/bin/gr0wthlab preflight` passed: six areas writable, 14 paths refused, no breach, and neither of the two listed hosts reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check` passed at its first attempt, as `20261013T022115Z-on-demand-b323`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, three sandbox network targets refused after the control reached its listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and no change since the snapshot.

Mandu's, RepToday's, and Immerse's HEAD, git status, and a digest over every file outside `.git` were the same before the preflight and after the check.

### The reworded guidance in live sessions

A change to the task definition is judged by what the launcher counts of a live session; the counts inform and do not gate.
Six runs were made one after another through `src/bin/gr0wthlab run` on demand, network off, with ffmpeg 7.1.1, from a throwaway checkout of `e44f5ce` in the Mac's temporary folder, with the inputs of the first round: the synthetic kit cut down to days 1 and 8, the synthetic Product checkout, one stand-in clip in a footage place set with `GR0WTHLAB_FOOTAGE_DIR`, a simulated approval of the filming plan, and no network source listed.
Its fingerprint was `2f931fe0b008843a20897025902bf420f0e5f64667f31993ffca437fba9f490e`.
The first four runs only brought day 1's post to show a finished video; the last two are the sessions judged, both under the real task definition.

| Run | Task definition | What was done by hand before it | What it showed |
| --- | --- | --- | --- |
| `20261013T020336Z-on-demand-faf9` | Real | Nothing | The filming plan filed, day 1's post queued with no video yet |
| `20261013T020519Z-on-demand-0c13` | Real | The plan approved | The agent wrote day 1's edit record, one unbroken range from 2 to 12 seconds, and rewrote its Draft with the Hook listed as a claim with no code; the claim check blocked the Draft, so no video was cut and the open post was withdrawn |
| `20261013T020730Z-on-demand-36f0` | Real | Nothing | The same Draft, blocked by the same claim |
| `20261013T020919Z-on-demand-abec` | Throwaway, checks only | The filming example set's day 1 Draft put in place of the agent's | The launcher rendered `assets/window-1/day-01-84af9c001ff9.mp4` from the agent's edit record, and `20261012-post-w1-day-01-2` shows it |
| `20261013T020952Z-on-demand-fe7d` | Real | The clip moved out of the footage place | The agent left day 1's Draft and edit record byte for byte as they were; the post stood, and the Filming row says its post keeps the video it shows. Counted: agent time 1 min 10 s, 16 of 16 package files read, no Draft written or changed, no proposal written |
| `20261013T021109Z-on-demand-97a6` | Real | The finished file deleted | The agent again left the Draft and the edit record byte for byte as they were; `20261012-post-w1-day-01-3` took the open post's place with no video, with both reasons in its item, both report rows, and the notice. Counted: agent time 1 min 20 s, 16 of 16 package files read, no Draft written or changed, no proposal written |

In the last run the agent's own summary, which the report quotes, says that `check-edits` reported day 1's edit as kept, that the footage is absent and the named video file is gone, and that it left the edit record unchanged; it does not say the post keeps or shows a video.
In the run before it, with the finished file in place, its summary says `check-edits` said to keep the record because its footage is unavailable.
The same summary of the last run says `check-drafts` could not read the Product checkout or find day 1 in the calendar; the record does not show why, and the launcher's own check of that Draft passed in the same run.
Each run cost one or two cents at API prices.

### What this round did not exercise

A finished file changed in place or one that cannot be read, an approved day, an A/B pair, a slot change, and missing video tooling were not run live on this commit and stand on the unit tests and on the rounds above.
The agent's first Draft of day 1 passed and its rewrite in the second run did not, so the post that shows the video came from the example set's Draft, put in place by hand.
No weekly run was made on a schedule, the Founder's real footage does not exist yet, and Mandu's side was not shown the notices.

## Re-check after the line for a post that left the queue with nothing queued in its place

A review of the change found one line of the run report and the notice that said more than a record shows, and one fix in `filming.py` corrects it (`Filming.settle`).

- An open post whose video's finished file is lost is settled to give way to the same post without a video, and that post is checked against the item format once more as it is queued, with the reason it gives for having no video.
  When it fails there, the open post is withdrawn and nothing is queued for the day.
  The line that names such a post under `Posts that lost the video they named:`, and in the notice, ended by saying that nothing is asked in its place since the Founder already decided this day's copy, which no record shows.
  It now ends `Nothing is asked in its place, since its Draft no longer passes.`, the reason the post section's own line gives.
- The line names a decision of the Founder's only for the two results that come from one: a day's copy the Founder approved, and a Draft the Founder rejected.
  Those two lines read word for word as before.
- Nothing about when a post is replaced, stands, or leaves the queue changed, and `codex.py`, `boundary.py`, `launcher.py`, the probe, `runtime.json`, `fetch.json`, and `config/products.json` are unchanged.

On these files ruff 0.15.20 passed, and so did the `tests.test_filming` module under `/usr/bin/python3`, 95 tests with none skipped; the full unit suite was not run again.
The module holds one new test of that case, which failed on `filming.py` as it is at `045b1a1` and passes on it as it now is.

All of this round ran on 2026-10-12, Mac local time, 19:39 to 19:49 PDT, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, on the files of the linked worktree this review ran in, before the commit that records them here was made.
That worktree's HEAD was `045b1a1b2e75303ff57dc29da20459e5eab0b07d`, with `src/` at tree `d60c7d6a50d99f77cc6f04a3e1d8d760f314cebc` and `config/` at tree `bfa79f76f468035578efd8d2c901b92c40c3adf9`, the tree `config/` has at `045b1a1`.

### Both checks

From that worktree, against Mandu and the Product checkouts as they are, each started under `caffeinate -i -s -m`, with their logs sent to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.
The worktree's `git status` listed the same two changed files, `src/gr0wthlab/filming.py` and `src/tests/test_filming.py`, before the preflight and after the check, `src/` was at the same tree after it, and this section was written after both.
`show-config` printed the fingerprint `b6d21e615aa50e7efec9686364db55291ae821b6aab1548c8dbd5d5cc0f3f3f9`, which differs from the ones above: the fingerprint covers the sandbox policy, and that policy names the path of the worktree a check runs from.

- `src/bin/gr0wthlab preflight` passed: six areas writable, 14 paths refused, no breach, and neither of the two listed hosts reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check` passed at its first attempt, as `20261013T024040Z-on-demand-9da9`, whose identifier carries the time in UTC: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, three sandbox network targets refused after the control reached its listener, two requests from the launcher's client, both a GET, to the two listed hosts, whose `robots.txt` it read, an unlisted address refused, and no change since the snapshot.
  It replaces `20261013T022115Z-on-demand-b323` above, which passed on the launcher as it then was.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the check.
The `tests.test_filming` module and the runs below were going on the same Mac while the boundary check ran, the module from the same worktree.

### The line before and after the fix

The line was reproduced and then seen live through `src/bin/gr0wthlab run` on demand, network off, with ffmpeg 7.1.1 and the repository's no-model stand-in for the agent, which wrote the filming example set's Draft and edit record for day 1.
Each checkout was a throwaway one in the Mac's temporary folder, with the inputs of the rounds above: the synthetic kit cut down to days 1 and 8, the synthetic Product checkout, one stand-in clip of ffmpeg's test pattern in a footage place set with `GR0WTHLAB_FOOTAGE_DIR`, a simulated approval of the filming plan, and no network source listed.
No checkout held a decision on any post.

- Checkout A held `045b1a1`, the code before this fix, with `src/` at tree `fff1145291f46ffc143559fa170340a8c30a4308`; its fingerprint was `e192599823c2c4408d19a945e9d3006f10917995bfdcf66785d7e49824cface4`.
- Checkout B held this round's two changed files over `045b1a1`, and also eight files the boundary check had written under the worktree's `workspace/` by then, copied from there while that check was running; its fingerprint was `881f5a2f371b365dd938ffbd618fa58ce35827e31191b2a8f69b287782c0087d`.
  It was not what this round's files are, so it was made again as checkout C.
- Checkout C held this round's two changed files over `045b1a1` and nothing else, with `src/` at the tree the checks above ran on; its fingerprint was `c4bbb0300ab8e7e79513efbb0723459458bed49a6f356278a4c1dcc5fafcc976`.

The same five runs were made in each, every one ending with exit code 0.

| What was done by hand before the run | Run in A | Run in B | Run in C | What it showed in all three |
| --- | --- | --- | --- | --- |
| Nothing | `20261013T024123Z-on-demand-9544` | `20261013T024124Z-on-demand-6ee0` | `20261013T024236Z-on-demand-6064` | The filming plan filed |
| The plan approved | `20261013T024126Z-on-demand-fa8a` | `20261013T024126Z-on-demand-91a3` | `20261013T024239Z-on-demand-646c` | The launcher rendered `assets/window-1/day-01-84af9c001ff9.mp4`, and `20261012-post-w1-day-01` shows it |
| The clip moved out of the footage place, and the finished file deleted | `20261013T024134Z-on-demand-1d1a` | `20261013T024134Z-on-demand-8536` | `20261013T024244Z-on-demand-a0ee` | `20261012-post-w1-day-01-2` took the open post's place with no video; its item is 3949 characters as the item format counts them |
| The clip put back | `20261013T024136Z-on-demand-c040` | `20261013T024136Z-on-demand-1f01` | `20261013T024246Z-on-demand-6444` | The video was cut again to the same path, and `20261012-post-w1-day-01-3` shows it |
| 61 lines, 8059 characters in the item, added to the checklist of the throwaway Mandu's synthetic calendar, which every post item lists; the clip moved out, and the finished file deleted | `20261013T024142Z-on-demand-0f04` | `20261013T024142Z-on-demand-5a2a` | `20261013T024250Z-on-demand-5410` | Day 1's row of the post table read blocked, with one failing check, `the item is 12010 characters; keep it under 12000`, and `20261012-post-w1-day-01-3` withdrawn; no post was open for day 1 |

What the last run of each said of the withdrawn post, in one line of its report and one line of its notice, the same line in both:

- In A, the line ended `Nothing is asked in its place, since the Founder already decided this day's copy, and the video comes back for approval once it is cut again.`
- In B and in C, the line read `Day 1's post 20261012-post-w1-day-01-3 left the queue: no footage yet for shot d01-s1, and the finished file assets/window-1/day-01-84af9c001ff9.mp4 of the video 20261012-post-w1-day-01-3 named is gone. Nothing is asked in its place, since its Draft no longer passes.`, with the launcher's backticks around the post and the file left out here, and neither the report nor the notice held the words `already decided this day's copy`.
- In all three, the notice's line from the post section read that the open post `20261012-post-w1-day-01-3` for day 1 is withdrawn, since its Draft no longer passes.

### What this round did not exercise

The stand-in wrote every file of the fifteen runs, so no model was called outside the boundary check.
The two lines that name a decision, for a copy the Founder approved and for a Draft the Founder rejected, were not run live on these files and stand on the two unit tests of them, which are unchanged.
The item grew past the limit through lines added by hand to a synthetic calendar; no Product's package was read.
A finished file changed in place or one that cannot be read, an A/B pair, a slot change, and missing video tooling were not run live on these files and stand on the unit tests and on the rounds above.
The full unit suite was not run in this round, no weekly run was made on a schedule, the Founder's real footage does not exist yet, and Mandu's side was not shown the notices.
