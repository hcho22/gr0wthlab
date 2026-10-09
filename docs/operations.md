# Operating the weekly run

How the Marketing Engineer runs on the Founder's Mac: the production clone, the first run, the weekly schedule, and how to stop it.
Why the launcher works the way it does: [the US-ME02 spike note](spikes/us-me02-runtime-boundary.md).
What Mandu reads and writes: [the Mandu exchange](mandu-exchange.md).

## What one run does

`src/bin/gr0wthlab run` does the whole run, scheduled or on demand:

1. In the production clone only, it fetches `origin` and fast-forwards `main`, then restarts itself on the new code.
   It refuses to start if the clone is not on `main`, has changes outside `workspace/`, or has local commits outside `workspace/`.
   If the fetch fails, for example offline, it runs the current code and says so in the run report.
2. It snapshots RepToday's Go-To-Market Package in Mandu (`workspace/evidence/package-snapshots/`).
3. It takes in the Founder's decisions from Mandu's exchange folder and keeps each one as Evidence (`workspace/evidence/decisions/`).
4. It writes the agent's brief and runs the agent in the sandbox with the task definition `src/instructions/weekly-run.md`.
5. It undoes any change the agent made to records only the launcher writes, queues the items the agent wrote that pass the format, and turns every problem into one notice.
6. It writes `workspace/review-queue/queue.json`, each workflow's run state (`workspace/run-reports/state/`), and the run report (`workspace/run-reports/<run id>.md`), whose first line is `checked=N acted=N note=...` even when nothing happened.
7. In the production clone only, it commits the changed `workspace/` paths and pushes them to `main`, never anything else and never by force.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run.

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

The first run should end with `records: pushed`; check that `main` on GitHub gained one `chore(records): outputs of run …` commit touching only `workspace/`.
The push uses the Mac's git credentials for `https://github.com` (the `gh auth git-credential` helper); if it fails, the commit stays local and the next run pushes it.

## Install the weekly schedule

The default is Sunday at 16:00 in the Mac's local time zone, a few hours before the Founder's Sunday evening sitting.

```sh
cd ~/gr0wthlab
src/bin/gr0wthlab launch-agent > ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
launchctl print gui/$(id -u)/gr0wthlab.weekly-run | grep -E 'state|path'
```

For another time, pass it explicitly, for example `launch-agent --weekly sunday 15:00`.
The LaunchAgent runs `src/bin/gr0wthlab run --trigger scheduled --weekly <day> <time>`, so each run knows when it was due.
If the Mac is asleep at that time, launchd starts the run when it wakes, and the run report says how late it started.

## Run on demand

```sh
~/gr0wthlab/src/bin/gr0wthlab run
```

Only one run works at a time: a run started while another is in progress, scheduled or on demand, refuses to start with exit code 5, and the next run's report says it was refused.

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
