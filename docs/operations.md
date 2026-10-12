# Operating the weekly run

How the Marketing Engineer runs on the Founder's Mac: the production clone, the first run, the weekly schedule, and how to stop it.
Why the launcher works the way it does: [the US-ME02 spike note](spikes/us-me02-runtime-boundary.md).
What Mandu reads and writes: [the Mandu exchange](mandu-exchange.md).

## What one run does

`src/bin/gr0wthlab run` does the whole run, scheduled or on demand.
A run on demand always does it, and so does a one-off scheduled start (`--once`); a start of the weekly schedule does it only while the week's run is still owed and the Mac is fully awake, and otherwise ends at once ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).

1. In the production clone only, it fetches `origin` and fast-forwards `main`, then restarts itself on the new code.
   Before that, it restores its owner's read and write access to anything under `workspace/` left without it.
   It refuses to start if the clone is not on `main`, has changes outside `workspace/` and `ledger/`, or has local commits outside them.
   If the fetch fails, for example offline, it runs the current code and says so in the run report.
2. It snapshots RepToday's Go-To-Market Package in Mandu (`ledger/evidence/package-snapshots/`).
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
6. It reads the 14-day kit from Mandu, works out which calendar days need post Drafts this run, now that the Founder's decisions are in, and fixes RepToday's `main` to one commit for claim checks.
   It reads the Founder's Beta Build record in Mandu's exchange folder (`beta-builds/RepToday.json`), which is the only thing it takes as an approval.
   Until that record exists it does nothing more about the Beta Cohort, and the run report lists the approval as not recorded.
   Once it exists, it takes in the Founder's Beta Cohort reports (`ledger/evidence/beta-recruiting/reports/`) and fixes the run's next invitation batch: the next sign-ups that asked for a beta invitation and that no batch holds, good Fit first, then by sign-up date, at most the batch size in `config/run.json`.
   It offers at most one batch at a time, and the next only after the Founder has decided the last.
   It writes the agent's brief and runs the agent in the sandbox with the task definition `src/instructions/weekly-run.md`.
   The agent writes only in the six `workspace/` areas; it can read `ledger/`, where the launcher keeps its records, and never write there.
   The agent has a time limit; one still running at it is stopped, and the run goes on without it ([When a run times out](#when-a-run-times-out)).
7. Once the agent finishes, it restores its owner's read and write access to anything under `workspace/` the agent left without it, and the run report names every entry it fixed, before or after the agent.
   It queues the items the agent wrote to `workspace/review-queue/incoming/` that pass the format, sets the rest aside, and turns every problem into one notice.
   A post or a message written there is always set aside: the launcher queues those two kinds only from a Draft that passes its checks.
   The package review counts as complete only when the agent's summary ends with the line `Review: complete`; otherwise the run report marks it incomplete and the notice says so.
   It checks each post Draft the agent wrote in `workspace/drafts/posts/` and queues a post only for one that passes; a blocked Draft is named in the run report and the notice with every failing rule or checklist line, and every check is kept in `ledger/evidence/post-drafts/`.
   It files the brand lint's word-list proposal once, and never again whatever the Founder decides.
   It checks each recruiting Draft the brief asked for in `workspace/drafts/beta-recruiting/`, and queues the invitation, with its batch attached, or the Waitlist ask only from a Draft that passes; a blocked Draft is named in the run report and the notice with every failing rule.
   A recruiting Draft that holds anything that looks like an email address is removed from `workspace/`, so the records step never saves it.
   It withdraws an open recruiting item whose Draft stopped passing, or that outlived the end of recruiting, at the Founder's stop or once the Founder reports the cohort full, and keeps the run's recruiting Evidence in `ledger/evidence/beta-recruiting/`.
   It replaces an open invitation that holds a sign-up who left the Waitlist with the batch made again without them, and withdraws it when that batch cannot be made.
   It replaces an open Waitlist ask whose stated gap changed with one that states the current gap, and withdraws it once the cohort can reach its minimum.
8. It writes `ledger/review-queue/queue.json`, each workflow's run state (`ledger/run-reports/state/`), and the run report (`ledger/run-reports/<run id>.md`), whose first line is `checked=N acted=N note=...` even when nothing happened.
   It notes how the run ended in the record of the week's run (`ledger/run-reports/attempts/`), which the next start of the weekly schedule reads.
9. In the production clone only, it commits the changed `workspace/` and `ledger/` paths and pushes them to `main`, never anything else and never by force; a change to a README in either is put back, since only a reviewed pull request changes documentation.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run, and the run log says why the replay failed.

The schedule, how often a start of the weekly schedule checks whether the week's run is owed, how many attempts it may take, the agent's time limit, the production clone's path, and the records step are in [`config/run.json`](../config/run.json).
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

Each week's run falls due on Sunday at 16:00 in the Mac's local time zone, ahead of the Founder's Sunday evening sitting.
Nothing holds the Mac awake for it, so the run happens when the Mac is awake, Sunday night or Monday morning alike ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).

```sh
cd ~/gr0wthlab
src/bin/gr0wthlab launch-agent > ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
launchctl print gui/$(id -u)/gr0wthlab.weekly-run | grep -E 'state|path|run interval'
```

The LaunchAgent starts the launcher at the weekly time and again every two minutes that the Mac is running, with the same command both times; `launchctl print` shows the second as `run interval = 120 seconds`.
Once it is installed, the first start begins that week's run unless a run has completed since the last weekly time, so make the first run on demand, as above, before installing it.
The schedule lives only in `config/run.json`: the LaunchAgent takes its time and its interval from there, and each run reads the same entry to tell whether it started late and when the next run is due (`next_run` in the Review Queue).
To change the sitting day or time, how often the launcher is started, or how many attempts a week's run may take, change `schedule` in `config/run.json` through a reviewed pull request.
After a change of day, time, or interval, once it has reached the production clone, remove the LaunchAgent as under [Stop or remove the schedule](#stop-or-remove-the-schedule) and install it again as above, since a LaunchAgent keeps what it was rendered with; the number of attempts is read at every start and needs no reinstall.
After a change of day or time, the launcher's records hold no run for the new weekly time that has just passed, so the next start begins one.
A window's `first_sitting`, once set, must fall on the sitting's day, so a change of day changes it in the same pull request; a run refuses to start otherwise.

## A run happens when the Mac is awake

Nothing in gr0wthlab holds the Mac awake, wakes it, or schedules a wake, and a sleeping Mac runs nothing.
So each week's run happens when the Mac is awake: at the weekly time if the Mac is fully awake then, and otherwise once it next is, Sunday night or Monday morning alike.

Every start of the weekly schedule is first a check, and most of them begin nothing.
The LaunchAgent starts the launcher at the weekly time and again every `schedule.check_every_minutes` minutes that the Mac is running, 2 today.
Each start reads the launcher's own record of the week's run, `ledger/run-reports/attempts/<due>.json`, and begins a run only while all of this holds:

- No run has completed since the weekly time; a run on demand that completed counts.
- Every scheduled attempt so far was cut short by the Mac's sleep.
- Fewer than `schedule.attempts_per_week` attempts were made, 3 today.
- The Mac is fully awake.

Otherwise the start ends at once with exit code 0, having taken no lock and written nothing.
It prints nothing either, so the LaunchAgent's log does not grow by a line every two minutes.
Started by hand in a terminal, `src/bin/gr0wthlab run --trigger scheduled` says why it began nothing, and begins the run if one is owed.

Fully awake means awake as when someone has woken the Mac, not in a dark wake.
A sleeping Mac wakes by itself with its display off, every few minutes to an hour and usually for under a minute, and launchd starts jobs then as at any other time.
A run takes minutes, far longer than a dark wake usually lasts, so one begun in a dark wake would as a rule be frozen again before it could finish, and would use up an attempt.
The launcher asks the Mac for its power state (`pmset -g systemstate`), which only reads it; if the Mac does not answer, the run starts anyway and its report says so.

What a week looks like:

- The Mac is in use on Sunday at 16:00: the run starts then, and its report says it started on time.
- The Mac is asleep or off at 16:00: the run starts within about two minutes of the Mac next being fully awake, and its report says when it was due and when it started.
  A start more than `schedule.late_after_minutes` minutes after its time, 15 today, reads as started late, with how long after its time that was.
- The Mac goes to sleep in the middle of a run: the run is frozen while the Mac sleeps and goes on whenever the Mac is running, a dark wake included.
  If it finishes that way, it is the week's run.
  If it does not, whatever ended it and wherever in the run the Mac slept, the run does not count as the week's run: its report, where it has one, says that the Mac's sleep cut it short and for about how long the Mac slept, and a fresh, whole run starts by itself once the Mac is fully awake.
  The fresh run's report says when the run was due, when it started, which attempt it is, and when each attempt before it started.

A fresh run is a whole run under the same rules as any other: it queues nothing an earlier attempt already queued, asks again nothing the Founder decided, and keeps what was carried over.
An attempt that a fresh run is to follow queues no notice for being cut short, since nothing is needed from the Founder.
While a fresh run is owed, `next_run` in the Review Queue stays at the time the week's run was due, so Mandu says at a sitting that the week's run has not finished.
After the last attempt a week's run may take, a notice asks the Founder to start a run on demand while the Mac stays awake, and no further run starts by itself until the next weekly time.

Which endings earn another attempt:

- An attempt that completed is the week's run, whether or not the Mac slept during it, and nothing follows it.
- An attempt that did not complete and during which the Mac slept was cut short by sleep, and earns another.
  The sleep counts wherever it fell: during the pre-run fetch in the production clone, while the launcher asked git for the checkout's boundary, during Codex's version probe or the boundary preflight, or while the agent ran.
  It counts however the attempt then ended: refused before it started, stopped by an error, with its agent never started, stopped at its time limit, or ended with an error.
  Such an attempt does not block the week.
  A fresh, whole run follows by itself, within `schedule.attempts_per_week`, and that run's report names it as it names any earlier attempt.
- An attempt that did not complete with the Mac awake throughout earns none and waits for the Founder.
  That covers a run that timed out, whose agent stopped early or never started, that was refused before it started, or that an error stopped.
  Its report, where it has one, says that no run starts by itself after it.
- An attempt that left no ending, as when the Mac was restarted in the middle of it, earns none either, whether or not the Mac slept; the next run's report names it.

The launcher tells sleep the same way for a whole attempt as for the agent's own time.
It reads the Mac's two clocks as a start begins: the wall clock, which goes on while the Mac sleeps, and awake time, which does not.
It reads them again once the agent has ended, or when a start ends before it has a report.
A difference of 5 seconds or more between the two is the Mac asleep; anything less is the clocks' own difference.
A start that restarts itself on newly fetched code carries its reading across the restart, so the fetch counts.
An attempt that ended before its report has no report of its own to say that the Mac slept.
The record of the week's run says so (`cut-short-by-sleep`, with `asleep_seconds`), and the fresh run's report names the attempt.

After an attempt that earns none, start a run on demand once the cause is dealt with; the next scheduled run is otherwise the next week's.

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

## Mark the Waitlist live

No public post may go out before the Waitlist is live.
That is a fact only the Founder sets, in `waitlist` in [`config/run.json`](../config/run.json), through a reviewed pull request once US-ME05's Validation Test has passed on reptoday.app:

```json
"waitlist": {"live_since": "2026-10-20"}
```

It is never inferred from whether a source is connected or what a source is called.
While `live_since` is `null`, or a date still ahead, every post item, the run brief, and the run report say that nothing can be published until the Waitlist is live.
A post queued from that date on says the Waitlist is live; an open post keeps the line it was queued with until its Draft or slot changes and the launcher replaces it.

## Run on demand

```sh
~/gr0wthlab/src/bin/gr0wthlab run
```

A run on demand is not checked against the record of the week's run and does not ask whether the Mac is awake: it always runs.
One that completes counts as that week's run, so no scheduled run follows it that week.

The launcher treats a one-off scheduled run the same way.
`src/bin/gr0wthlab run --trigger scheduled --once <time>` starts one, by hand or from a one-off LaunchAgent (`launch-agent --once <time>`), which launchd starts once, at its time or at the next wake after it, a dark wake included.
It always runs and is never an attempt at the week's run; the launcher notes it in the record of the week's run as it notes a run on demand.
Its report gives its own due time and says whether it started late, never that a fresh run follows.
Its notice is queued as any run's is, and `next_run` in the Review Queue stays the weekly time.
One that completes counts as that week's run, exactly as a completed run on demand does.
One that the Mac's sleep cut short is not run again by itself, and leaves the week's run as owed as it was.

Only one run works at a time in each checkout: a run started while another is in progress in the same checkout, scheduled or on demand, refuses to start with exit code 5, and that checkout's next run report says it was refused.
A start of the weekly schedule refused that way has made no attempt, so the next check starts the run once the other has ended, if it is still owed.
A run that cannot finish, for example because a file it must write cannot be written, stops with exit code 6 instead of a crash, and the next run report says so too, as it does when a run could not write its report.
A run whose agent was stopped at its time limit also ends with exit code 6, after it has written its own report, which says it timed out.
Each checkout keeps its run lock (`ledger/run.lock`, never committed) and these notes for its next report (`ledger/notes/`) in its own `ledger/`, so a run in a firstmate worktree never blocks or hides a production run.

## When a run times out

Every run ends with its report, so the agent has a time limit: `agent.time_limit_seconds` in [`config/run.json`](../config/run.json), 1800 seconds (30 minutes) today.
The limit counts wall-clock time from the moment the agent starts, the Mac's sleep included.
Nothing keeps the Mac awake for a run, and a sleeping Mac runs nothing, so the stop of an agent the Mac slept past its limit starts within about a second of the Mac waking, a dark wake included, not at the time of day the limit fell.
Awake time is counted as well, and the agent is stopped at whichever count reaches the limit first, so a wall clock set back cannot extend a run; one set forward can end a run early.
The 46 weekly runs recorded with the real agent took 18 to 218 seconds, so a healthy run on a Mac that stays awake ends long before the limit and is never touched by it.
An agent still running at the limit, for example because its model stream stalled, is stopped with every process the Mac's process table shows it started, which is its descendants and every process in a session one of them leads: each is asked to stop, and any still running after 10 seconds of awake time is forced.
The launcher then reads the process table again to confirm that none of them is left, and finishes the run as it finishes any run.
The stop does not find a process the agent detached earlier in the run: one in a session of its own whose parent has already ended, as a shell command that has finished can leave.
Nothing in the process table ties such a process to the agent, so it is not stopped and the report does not speak for it; it outlives a run that finishes in time as well, since the launcher stops nothing then.

What the Founder sees after a timed-out run:

- The run report's summary says `The run timed out`, and its Agent section says how long the agent ran by the wall clock, how many processes were asked to stop or forced, and whether any of them is still running.
- If the Mac slept while the agent ran, in this or any other run, the summary and the Agent section say for about how long.
  The summary of an attempt of the weekly schedule also says for about how long the Mac slept in the run outside the agent's time.
- Each output that needed the agent, such as the package review and the post Drafts of a run with a day due, is marked incomplete with the reason; what the launcher does alone is complete as usual.
- Whatever the agent had written is checked as always: an item or Draft that passes every check is queued, and one cut off mid-way fails its checks and is set aside or blocked, named in the report.
- One notice in the Review Queue leads with the timeout and lists what it left incomplete; a second timed-out run the same day adds no second notice while the first is open.
  A run of the weekly schedule that the Mac's sleep cut short queues no notice for the timeout alone while a fresh run is to follow.
- The cost line says the cost is not available, or gives the part Codex had reported before the stop as a floor; it never says zero.
- The run saves its records and releases the run lock, so the next run starts as usual and does the unfinished work again; the run itself ends with exit code 6.

A run of the weekly schedule that timed out on a Mac that slept during it needs nothing from the Founder: a fresh run starts by itself once the Mac is fully awake ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).
A run that timed out with the Mac awake, scheduled or on demand, is not run again by itself, and neither is a run on demand or a one-off scheduled run that the Mac slept through: start one on demand if the sitting needs the missing work.
If healthy runs come near the limit, or runs keep timing out though the agent was working, raise `agent.time_limit_seconds` through a reviewed pull request; the report's `Agent time` line shows how long each run's agent took.
A run that timed out because the Mac slept past the limit needs no higher limit.
The value must be above zero and at most 86400 (a day); a run refuses to start on any other value and says why.
If the report names a process that could not be stopped, end it by hand (`kill -9 <process id>`) before the next run.

There is one limit, on the agent's total time, and none on silence: Codex's event stream reports only whole steps, and the longest recorded run went 35 seconds without an event while it worked, so a long step and a stalled stream look the same from outside until the step ends.
Every other process the launcher starts (git, Codex's version and sandbox probes, the boundary check's kernel-log query) has a fixed time limit of its own, counted on the same two clocks; one that passes it is stopped the same way, and the step that needed it fails with the reason or, where it can do without the answer, goes on with what it has.

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
