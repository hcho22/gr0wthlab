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
   It writes the agent's brief and runs the agent in the sandbox with the task definition `src/instructions/weekly-run.md`, at the reasoning effort [`config/guardrails/runtime.json`](../config/guardrails/runtime.json) sets, which is high.
   The agent writes only in the six `workspace/` areas; it can read `ledger/`, where the launcher keeps its records, and never write there.
   The agent has a time limit; one still running at it is stopped, and the run goes on without it ([When a run times out](#when-a-run-times-out)).
7. Once the agent finishes, it restores its owner's read and write access to anything under `workspace/` the agent left without it, and the run report names every entry it fixed, before or after the agent.
   It queues the items the agent wrote to `workspace/review-queue/incoming/` that pass the format, sets the rest aside, and turns every problem into one notice.
   A post or a message written there is always set aside: the launcher queues those two kinds only from a Draft that passes its checks.
   The package review counts as complete only when the agent's summary ends with the line `Review: complete`; otherwise the run report marks it incomplete and the notice says so.
   That line is the agent's own word, so the run report also shows what the launcher itself counted of the session ([Reading the agent's work](#reading-the-agents-work)).
   It checks each post Draft the agent wrote in `workspace/drafts/posts/` and queues a post only for one that passes; a blocked Draft is named in the run report and the notice with every failing rule or checklist line, and every check is kept in `ledger/evidence/post-drafts/`.
   It files the brand lint's word-list proposal once, and never again whatever the Founder decides.
   It checks each recruiting Draft the brief asked for in `workspace/drafts/beta-recruiting/`, and queues the invitation, with its batch attached, or the Waitlist ask only from a Draft that passes; a blocked Draft is named in the run report and the notice with every failing rule.
   A recruiting Draft that holds anything that looks like an email address is removed from `workspace/`, so the records step never saves it.
   It withdraws an open recruiting item whose Draft stopped passing, or that outlived the end of recruiting, at the Founder's stop or once the Founder reports the cohort full, and keeps the run's recruiting Evidence in `ledger/evidence/beta-recruiting/`.
   It replaces an open invitation that holds a sign-up who left the Waitlist with the batch made again without them, and withdraws it when that batch cannot be made.
   It replaces an open Waitlist ask whose stated gap changed with one that states the current gap, and withdraws it once the cohort can reach its minimum.
8. It writes `ledger/review-queue/queue.json`, each workflow's run state (`ledger/run-reports/state/`), and the run report (`ledger/run-reports/<run id>.md`), whose first line is `checked=N acted=N note=...` even when nothing happened.
9. In the production clone only, it commits the changed `workspace/` and `ledger/` paths and pushes them to `main`, never anything else and never by force; a change to a README in either is put back, since only a reviewed pull request changes documentation.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run, and the run log says why the replay failed.

The schedule, the agent's time limit, the production clone's path, and the records step are in [`config/run.json`](../config/run.json).
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

Only one run works at a time in each checkout: a run started while another is in progress in the same checkout, scheduled or on demand, refuses to start with exit code 5, and that checkout's next run report says it was refused.
A run that cannot finish, for example because a file it must write cannot be written, stops with exit code 6 instead of a crash, and the next run report says so too, as it does when a run could not write its report.
A run whose agent was stopped at its time limit also ends with exit code 6, after it has written its own report, which says it timed out.
Each checkout keeps its run lock (`ledger/run.lock`, never committed) and these notes for its next report (`ledger/notes/`) in its own `ledger/`, so a run in a firstmate worktree never blocks or hides a production run.

## Reading the agent's work

A run is one agent session, and it ends when the agent writes its final message.
The launcher checks everything the agent wrote, but whether the agent did all its work is something only the agent says, in the `Review:` line that ends its summary.
That line has read `Review: complete` after sessions that did the least, so no run should be judged by it alone.

Each run report therefore has an `Agent's work` section, and a line in its summary, that set two things side by side and name each for what it is:

- What the launcher counted, from Codex's record of the session, the Draft files the run left, and the Review Queue.
  None of it comes from what the agent says of itself.
- The agent's own word: its closing `Review:` line, quoted.

The counts:

- `Agent time`, against the limit, with the model and reasoning effort the agent ran at.
- `Commands run`: the shell commands that ran to their end; how many read the Product's code, how many ran one of the launcher's checks (`check-incoming`, `check-drafts`, `check-beta-drafts`), and how many returned more output than Codex shows the model.
- `Package files read`: how many of the package files the brief listed came back to the model.
  Codex shows the model at most about 40,000 characters of one command's output, the first and last halves of that, and cuts the middle.
  A session that prints every package file in one command is shown the first and last few, so naming a file in a command is not reading it.
  The launcher counts a file as read when at least half of its lines are in the part of some command's output the model was shown; the figure is `work_counts` in [`config/run.json`](../config/run.json), a fact about Codex that needs measuring again after a Codex upgrade or a change of model.
- `File edits`: the edits the agent made with its file-editing tool.
- `Post Drafts`: how many of the days due have a Draft, and how many of those this run wrote or changed.
- `Draft claims`: how many claims the Drafts list, how many name a code location, for how many of those the launcher found the quoted code at that location, and how many name none.
- `Review Queue items the agent wrote`: how many were queued, how many of those are package-change proposals, and how many were set aside.

The counts inform the Founder and gate nothing: nothing is queued, blocked, or marked incomplete because of one, and every check of an item or a Draft is what it was.
The run's log record in `~/Library/Logs/gr0wthlab/` holds the same counts under `work`, with the name of every package file not read.

What the counts looked like when they were introduced, on 2026-10-11, against Mandu and RepToday as they were.
Each run was on demand in a fresh clone, so each was a first week: a package review and the first batch's seven post Drafts.

| Reasoning effort | Runs | Ended with the words `Review: complete` | Package files read, of 24 | Draft claims naming code | Proposals queued | Agent time | Cost a run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| medium, Codex's default, on `main` before the change | 3 | 0 | 6, 11, and 24 | 4 of 25 | 0 to 1 | 59 s to 2 min 38 s | $0.012 to $0.028 |
| high | 10 | 10 | 11 to 24, all 24 in four runs | 78 of 97 | 2 to 13 | 4 min 43 s to 18 min 42 s | $0.056 to $0.158 |

Read a report against these counts.
A run that says `Review: complete` after few commands, few package files read, or with most claims naming no code did less than the runs at high effort did, whatever its closing line says.
High effort does not make every session thorough: two of the ten read 11 and 17 of the 24 files and still said the review was complete.
[The US-ME02 spike note](spikes/us-me02-runtime-boundary.md#re-check-after-the-agents-reasoning-effort-and-the-work-counts-us-me17) lists every run and says what the sample does not show.

## When a run times out

Every run ends with its report, so the agent has a time limit: `agent.time_limit_seconds` in [`config/run.json`](../config/run.json), 1800 seconds (30 minutes) today.
The limit counts wall-clock time from the moment the agent starts, the Mac's sleep included.
Nothing keeps the Mac awake for a run, and a sleeping Mac runs nothing, so the stop of an agent the Mac slept past its limit starts within about a second of the Mac waking, not at the time of day the limit fell.
Awake time is counted as well, and the agent is stopped at whichever count reaches the limit first, so a wall clock set back cannot extend a run; one set forward can end a run early.
At high reasoning effort the agent took 283 to 1,122 seconds, median 646, in the ten runs measured on 2026-10-11, each a package review and one batch of post Drafts, most with four or five sessions running at once on the Mac.
A healthy run on a Mac that stays awake therefore ends inside the limit, the longest measured at 62 percent of it; at Codex's default medium effort the 46 runs recorded before took 18 to 218 seconds.
An agent still running at the limit, for example because its model stream stalled, is stopped with every process the Mac's process table shows it started, which is its descendants and every process in a session one of them leads: each is asked to stop, and any still running after 10 seconds of awake time is forced.
The launcher then reads the process table again to confirm that none of them is left, and finishes the run as it finishes any run.
The stop does not find a process the agent detached earlier in the run: one in a session of its own whose parent has already ended, as a shell command that has finished can leave.
Nothing in the process table ties such a process to the agent, so it is not stopped and the report does not speak for it; it outlives a run that finishes in time as well, since the launcher stops nothing then.

What the Founder sees after a timed-out run:

- The run report's summary says `The run timed out`, and its Agent section says how long the agent ran by the wall clock, how many processes were asked to stop or forced, and whether any of them is still running.
- If the Mac slept while the agent ran, in this or any other run, the summary and the Agent section say for about how long.
- Each output that needed the agent, such as the package review and the post Drafts of a run with a day due, is marked incomplete with the reason; what the launcher does alone is complete as usual.
- Whatever the agent had written is checked as always: an item or Draft that passes every check is queued, and one cut off mid-way fails its checks and is set aside or blocked, named in the report.
- One notice in the Review Queue leads with the timeout and lists what it left incomplete; a second timed-out run the same day adds no second notice while the first is open.
- The cost line says the cost is not available, or gives the part Codex had reported before the stop as a floor; it never says zero.
- The run saves its records and releases the run lock, so the next run starts as usual and does the unfinished work again; the run itself ends with exit code 6.

One timed-out run needs nothing from the Founder beyond a re-run on demand if the sitting needs the missing work.
If healthy runs come near the limit, or runs keep timing out though the agent was working, raise `agent.time_limit_seconds` through a reviewed pull request; the report's `Agent time` line shows how long each run's agent took.
A run that timed out because the Mac slept past the limit needs no higher limit, only a Mac that is awake for the re-run.
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
