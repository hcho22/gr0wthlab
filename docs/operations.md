# Operating the weekly run

How the Marketing Engineer runs on the Founder's Mac: the production clone, the first run, the weekly schedule, and how to stop it.
Why the launcher works the way it does: [the US-ME02 spike note](spikes/us-me02-runtime-boundary.md).
What Mandu reads and writes: [the Mandu exchange](mandu-exchange.md).

## What one run does

`src/bin/gr0wthlab run` does the whole run, scheduled or on demand:

1. In the production clone only, it fetches `origin` and fast-forwards `main`, then restarts itself on the new code.
   Before that, it restores its owner's read and write access to anything under `workspace/` left without it.
   It refuses to start if the clone is not on `main`, has changes outside `workspace/` and `ledger/`, or has local commits outside them.
   If the fetch fails, for example offline, it runs the current code and says so in the run report.
2. It snapshots RepToday's Go-To-Market Package in Mandu (`ledger/evidence/package-snapshots/`), reads the 14-day kit, works out which calendar days need post Drafts this run, and fixes RepToday's `main` to one commit for claim checks.
3. It takes in the Founder's decisions from Mandu's exchange folder and keeps each one as Evidence (`ledger/evidence/decisions/`).
4. It reads RepToday's anonymous Waitlist view, once its build has made one, and keeps the counts by Source, Fit answer, and opt-in, per week and cumulative, with the entry identifiers, as Evidence (`ledger/evidence/waitlist/`).
   It checks every value for anything that looks like an email address first; on a hit it discards the whole read, keeps nothing from it, and queues a Guardrail breach notice.
   A week runs Monday to Sunday, and the run report leads with the week the run is in on the Mac's clock, the one that ends at the Sunday sitting; it also says how old the view was when the run started.
5. It files each reviewed Dispatch request in `src/dispatches/` that needs filing, such as RepToday's Waitlist, under an identifier that never changes.
   A filed request stays open until the Founder decides it: any reviewed change to its text, the ask or any section, files the new text in its place, and no item the agent writes can replace it.
   A request is never filed again once the Founder approved it, and the same whole text is never asked again once the Founder rejected it.
   Two exceptions arise only after a reviewed change to the request's text while an item of it is open, which is firstmate's own reviewed act.
   A reviewed change that brings back a text the Founder rejected, while another text is open, files the rejected text again in that open item's place.
   An approval the Founder gave an item that a reviewed change had already replaced still counts as the request's approval, though Mandu hands no superseded item to firstmate: the replacement stays open for the Founder to decide, no reviewed change replaces it any more, nothing is filed after it, and the run report says so.
6. It writes the agent's brief and runs the agent in the sandbox with the task definition `src/instructions/weekly-run.md`.
   The agent writes only in the six `workspace/` areas; it can read `ledger/`, where the launcher keeps its records, and never write there.
7. Once the agent finishes, it restores its owner's read and write access to anything under `workspace/` the agent left without it, and the run report names every entry it fixed, before or after the agent.
   It queues the items the agent wrote to `workspace/review-queue/incoming/` that pass the format, sets the rest aside, and turns every problem into one notice.
   The package review counts as complete only when the agent's summary ends with the line `Review: complete`; otherwise the run report marks it incomplete and the notice says so.
   It checks each post Draft the agent wrote in `workspace/drafts/posts/` and queues a post only for one that passes; a blocked Draft is named in the run report and the notice with every failing rule or checklist line, and every check is kept in `ledger/evidence/post-drafts/`.
   It files the brand lint's word-list proposal once, and never again whatever the Founder decides.
8. It writes `ledger/review-queue/queue.json`, each workflow's run state (`ledger/run-reports/state/`), and the run report (`ledger/run-reports/<run id>.md`), whose first line is `checked=N acted=N note=...` even when nothing happened.
9. In the production clone only, it commits the changed `workspace/` and `ledger/` paths and pushes them to `main`, never anything else and never by force; a change to a README in either is put back, since only a reviewed pull request changes documentation.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run, and the run log says why the replay failed.

The schedule, the production clone's path, and the records step are in [`config/run.json`](../config/run.json).
Launcher logs, Codex's event stream, and each run's record go to `~/Library/Logs/gr0wthlab/`.

## Set up the production clone (once, after merge)

```sh
git clone https://github.com/hcho22/gr0wthlab.git ~/gr0wthlab
cd ~/gr0wthlab
src/bin/gr0wthlab preflight        # proves the write boundary with no model
src/bin/gr0wthlab boundary-check   # the US-ME02 check, from this clone
src/bin/gr0wthlab run              # the first run, on demand
```

The first run should end with `records: pushed`; check that `main` on GitHub gained one `chore(records): outputs of run …` commit touching only `workspace/` and `ledger/`.
The push uses the Mac's git credentials for `https://github.com` (the `gh auth git-credential` helper); if it fails, the commit stays local and the next run pushes it.

## Install the weekly schedule

The default is Sunday at 16:00 in the Mac's local time zone, a few hours before the Founder's Sunday evening sitting.

```sh
cd ~/gr0wthlab
src/bin/gr0wthlab launch-agent > ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
launchctl print gui/$(id -u)/gr0wthlab.weekly-run | grep -E 'state|path'
```

The schedule lives only in `config/run.json`: the LaunchAgent takes its time from there, and each run reads the same entry to tell whether it started late and when the next run is due (`next_run` in the Review Queue).
To change the sitting day or time, change `schedule` in `config/run.json` through a reviewed pull request, then reinstall the LaunchAgent as above once the change has reached the production clone.
A window's `first_sitting`, once set, must fall on the sitting's day, so a change of day changes it in the same pull request; a run refuses to start otherwise.
If the Mac is asleep at that time, launchd starts the run when it wakes, and the run report says how late it started.

## Set the 14-day window

Day 1 of the window follows from the Founder's sitting: it is the day after the sitting that approves the window's first batch.
Which sitting that is, and the window's one fixed posting slot, are the Founder's call, set in `window` in [`config/run.json`](../config/run.json) through a reviewed pull request and never inferred, since nothing posts before the Waitlist is live:

```json
"window": {"number": 1, "first_sitting": "2026-10-18", "slot": "19:00"}
```

`first_sitting` is that sitting's date, which must fall on the schedule's day (a Sunday today); day 1 is then Monday 2026-10-19, and every calendar day follows from it.
`slot` is the Mac's local time; the kit's posting-slot rule in the calendar names no time, so it is set here.
Until `first_sitting` is set, every run prepares calendar days 1 to 7 as the first batch, with no slot on the posts.
Once it is set, each run prepares the calendar days from the next day through the end of the week after the coming sitting (on the sitting's own day, exactly that week), skipping any day already approved, and each post's slot is its date at `slot`.
A changed slot reaches an open post at the next run, which replaces the post with one that carries it.

## Run on demand

```sh
~/gr0wthlab/src/bin/gr0wthlab run
```

Only one run works at a time in each checkout: a run started while another is in progress in the same checkout, scheduled or on demand, refuses to start with exit code 5, and that checkout's next run report says it was refused.
A run that cannot finish, for example because a file it must write cannot be written, stops with exit code 6 instead of a crash, and the next run report says so too, as it does when a run could not write its report.
Each checkout keeps its run lock (`ledger/run.lock`, never committed) and these notes for its next report (`ledger/notes/`) in its own `ledger/`, so a run in a firstmate worktree never blocks or hides a production run.

## When RepToday's Waitlist build lands

The Founder approves the Waitlist Dispatch request in Mandu, and firstmate builds it in RepToday; until then every run reports the Waitlist view as skipped.
Once the build writes its anonymous view, a reviewed gr0wthlab pull request sets `waitlist.view.local_path` for RepToday in [`config/products.json`](../config/products.json) to the file's path, and the next run reads it.
The path must lie outside this clone, Mandu, and every Product checkout, all of which the sandbox reads; the launcher refuses to start otherwise, so the agent can never open the view.
`GR0WTHLAB_WAITLIST_VIEW` overrides the path on one machine, for example to try the run against a test copy of the view.
The change touches `config/products.json`, so it needs the boundary check below.

## Stop or remove the schedule

```sh
launchctl bootout gui/$(id -u)/gr0wthlab.weekly-run
rm ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
```

To keep running but stop saving records to GitHub, set `records.save_after_run` (or `records.sync_before_run`) to `false` in `config/run.json` through a reviewed pull request; the next run picks it up when it fast-forwards.
To stop immediately without a pull request, remove the schedule as above.

## After a change to the launcher or configuration

A change to `src/bin/gr0wthlab` or the launcher's package, `config/guardrails/runtime.json`, or `config/products.json` needs a fresh check on the Founder's Mac, which CI cannot run:

```sh
cd ~/gr0wthlab && src/bin/gr0wthlab preflight && src/bin/gr0wthlab boundary-check
```

To repeat the check on the scheduled path, generate a one-off LaunchAgent a few minutes ahead, then remove it once it has run:

```sh
src/bin/gr0wthlab launch-agent --boundary-check --once 2026-10-12T09:05 --label gr0wthlab.boundary-check \
  > ~/Library/LaunchAgents/gr0wthlab.boundary-check.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/gr0wthlab.boundary-check.plist
# after it fires: read ~/Library/Logs/gr0wthlab/gr0wthlab.boundary-check.out.log
launchctl bootout gui/$(id -u)/gr0wthlab.boundary-check
rm ~/Library/LaunchAgents/gr0wthlab.boundary-check.plist
```
