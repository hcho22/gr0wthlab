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
   It reads the fixed list of network sources in `config/sources.json` itself, outside the sandbox: the three subreddits' newest threads and rules, and App Store reviews of the competitors the research names.
   Every request is a credential-free GET to a host listed in `config/guardrails/fetch.json`; it reads each host's `robots.txt` first and never requests a path that file disallows.
   No read waits forever: each wait on a host ends after `timeout_seconds` and each whole read after `read_deadline_seconds`, both in that file, so a host that answers a byte at a time is cut off and reported as a source not read.
   The Founder decided on 2026-10-11 that each host's `robots.txt` is binding for now, while the owners' terms are read first-hand.
   Today each named host's `robots.txt` disallows the path a credential-free reader needs, so every source is reported as not read and Listening is marked incomplete while that decision stands.
   What it read goes into one snapshot (`ledger/working/`), which is working data for that run alone (see "What is kept of what a run fetches" below), and every request it was asked to make, sent or not, into the run's request log (`ledger/run-reports/<run id>.requests.json`).
   A source that is disallowed, refused, or failing is reported with its reason, queued in a notice, and marks its workflow incomplete; the run goes on.
   The first time it reads a subreddit's rules, it queues one notice that quotes and links them; no reply Draft for that subreddit is offered until the Founder acknowledges it, and the Founder's answer stands whatever the rules say later.
   It reads the Founder's outreach records from Mandu's exchange folder and works out which messages may be offered: the personal-network ask, one message for each creator in `config/run.json` that the channel plan names, and one follow-up only for a creator who was written to, has not replied, and whose waiting period has passed.
   It writes the agent's brief and runs the agent in the sandbox with the task definition `src/instructions/weekly-run.md`.
   The agent has no network, and every run proves it before the agent starts: the preflight tries each listed host from inside the sandbox and stops the run if one is reachable.
   The agent writes only in the six `workspace/` areas; it can read `ledger/`, where the launcher keeps its records, and never write there.
   The agent has a time limit; one still running at it is stopped, and the run goes on without it ([When a run times out](#when-a-run-times-out)).
7. Once the agent finishes, it restores its owner's read and write access to anything under `workspace/` the agent left without it, and the run report names every entry it fixed, before or after the agent.
   It queues the items the agent wrote to `workspace/review-queue/incoming/` that pass the format, sets the rest aside, each copied whole to `ledger/review-queue/set-aside/<run id>/`, and turns every problem into one notice.
   A post or a message written there is always set aside: the launcher queues those two kinds only from a Draft that passes its checks.
   Every package-change proposal there declares whether it adds or changes an Angle or Hook (`new_angle`), and the Founder sees the declaration on the item.
   One that declares it does is set aside, with what to add, unless its Evidence names the record of a Listening quote the launcher already keeps; one that declares it does not is queued whatever it touches or says.
   The launcher never checks a declaration against a proposal's wording: the Founder is the check on a wrong declaration, at the sitting.
   The package review counts as complete only when the agent's summary ends with the line `Review: complete`; otherwise the run report marks it incomplete and the notice says so.
   It checks each post Draft the agent wrote in `workspace/drafts/posts/` and queues a post only for one that passes; a blocked Draft is named in the run report and the notice with every failing rule or checklist line, and every check is kept in `ledger/evidence/post-drafts/`.
   It files each reviewed proposal in `src/proposals/` once, and never again whatever the Founder decides: the brand lint's word lists, and, in a run with outreach messages to offer, the loss-framing and sponsorship-ask lists.
   It checks each recruiting Draft the brief asked for in `workspace/drafts/beta-recruiting/`, and queues the invitation, with its batch attached, or the Waitlist ask only from a Draft that passes; a blocked Draft is named in the run report and the notice with every failing rule.
   A recruiting Draft that holds anything that looks like an email address is removed from `workspace/`, so the records step never saves it.
   It withdraws an open recruiting item whose Draft stopped passing, or that outlived the end of recruiting, at the Founder's stop or once the Founder reports the cohort full, and keeps the run's recruiting Evidence in `ledger/evidence/beta-recruiting/`.
   It replaces an open invitation that holds a sign-up who left the Waitlist with the batch made again without them, and withdraws it when that batch cannot be made.
   It replaces an open Waitlist ask whose stated gap changed with one that states the current gap, and withdraws it once the cohort can reach its minimum.
   It puts back any change the run made in `workspace/instructions/`, and names it in the run report.
   An entry there that it could not read before the agent started is not guarded: it is left exactly as it is, and the run report names it.
   It keeps each quote record whose words stand in the text it fetched from that record's link (`ledger/evidence/listening/quotes/`), and refuses every other: a refused record is removed, and only its file name and the reasons are kept.
   Once the agent's work is taken in and the run ends, it removes the snapshot.
   It queues a proposed Angle or Hook only when every source it cites is a kept quote, with the confidence it counts itself, and discards an unsourced one with a note: the discarded file is removed, and only its name and the reasons are kept.
   It checks each message Draft in `workspace/drafts/messages/` and queues a message only for one that passes; an open message that may no longer be offered, such as a follow-up to a creator who has since replied, is withdrawn.
   Only a record that was read withdraws a follow-up: when Mandu's `outreach/` folder cannot be read, or the record of a creator's first message is missing after a follow-up was queued from it, cannot be read, or is not valid, that follow-up is neither offered nor withdrawn, an open one stays as it is, and the run report names Mandu's outreach records as failed and the Outreach output as incomplete, with the reason.
   For a message Draft, a source it is checked against that cannot be read withdraws nothing either: an open message or reply stands, not checked again, and the Outreach or Listening output is incomplete and names the source.
   Those sources are the Angle bank, the checklist, and the brand rules; the Product's code, or git's read of one file a claim names when that read times out or cannot start; and the kept quote record a reply answers (`ledger/evidence/listening/quotes/`).
   A claim that names a file that is not there, and a reply whose quote record is absent altogether, are checks the launcher could make: the Draft is blocked and an open item withdrawn.
   It takes in the code the agent proposed for each rejection reason, writes it beside the Founder's words in that decision's Evidence, and rebuilds the learning ledger (`ledger/evidence/learning/ledger.json`), whose counts read "3 of 7".
   A proposed code that fails its check is set aside: its file is removed, and the run report and notice name it with the reasons.
   The `Rejection reasons coded` output is complete only when every reason the brief listed has an accepted code, or there was none to code; a reason left without one, or a reason that could not be read, marks it incomplete, and the reason is asked for again at the next run.
8. It writes `ledger/review-queue/queue.json`, each workflow's run state (`ledger/run-reports/state/`), and the run report (`ledger/run-reports/<run id>.md`), whose first line is `checked=N acted=N note=...` even when nothing happened.
9. In the production clone only, it commits the changed `workspace/` and `ledger/` paths and pushes them to `main`, never anything else and never by force; a change to a README in either is put back, since only a reviewed pull request changes documentation.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run, and the run log says why the replay failed.

The schedule, the agent's time limit, the production clone's path, and the records step are in [`config/run.json`](../config/run.json).
Launcher logs, Codex's event stream, and each run's record go to `~/Library/Logs/gr0wthlab/`.

## What is kept of what a run fetches

The snapshot of what a run fetched over the network is working data for that run alone.
It lives in `ledger/working/`, where the agent can read it while the run is in progress and can never write it.
Git ignores that folder, so the records step never saves it, and the launcher removes it when the run ends, however the run ends.
Anything a killed run left there is removed before the next run reads its sources, so no agent ever reads an earlier run's snapshot.
As Evidence of what was fetched, only what the agent actually quoted and the launcher validated is committed: each kept quote with its link, the date read, and a hash of the document it came from (`ledger/evidence/listening/quotes/`).
Besides the kept quotes, the launcher's own records of the reading say where it read and what became of each source: the request log holds addresses and outcomes, and a subreddit's rules notice quotes that subreddit's rules for the Founder.
The request log also holds the `robots.txt` rule lines of the group that applied to each host, each Allow and Disallow with its path as fetched.
`check-work --run <run id>` checks quotes against the snapshot, so it answers only while that run is in progress.

Nothing else the agent writes is checked against what was fetched, so text of its own that repeats a source's words is committed today in each of these places.
They are known gaps, not yet decided by the Founder:

- A file the launcher sets aside from `workspace/review-queue/incoming/` is copied whole to `ledger/review-queue/set-aside/<run id>/`: a package-change proposal that declares `new_angle: yes` and names no kept quote, a file that fails the item format, and a post or a message written there.
- A Draft the agent wrote, a reply that failed its checks included, stays in `workspace/` and is committed as written until it passes or is rewritten, as is any other file the agent leaves in `workspace/` that the launcher neither takes in nor puts back.
- The reasons in a run report or a notice can repeat pieces of a file's text: a front matter line, up to 80 characters of an Evidence line, the headings found.
  The reasons a Draft's checks give, kept with the Evidence of those checks, can quote the Draft.
- The run report quotes the agent's own summary, up to 4,000 characters.
- What the launcher accepts keeps the agent's own words: the text of a queued item, the context of a kept quote, and the line that says why a rejection code fits.

Only three things leave their file name and the launcher's reasons and nothing else: a quote record the launcher refuses, a proposed Angle or Hook it discards from `workspace/review-queue/angles/`, and a rejection code it sets aside.
Each is removed from `workspace/` and copied nowhere.

## Set up the production clone (once, after merge)

```sh
git clone https://github.com/hcho22/gr0wthlab.git ~/gr0wthlab
cd ~/gr0wthlab
src/bin/gr0wthlab preflight        # proves the write boundary and the closed network with no model
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

## When a run times out

Every run ends with its report, so the agent has a time limit: `agent.time_limit_seconds` in [`config/run.json`](../config/run.json), 1800 seconds (30 minutes) today.
The limit counts wall-clock time from the moment the agent starts, the Mac's sleep included.
Nothing keeps the Mac awake for a run, and a sleeping Mac runs nothing, so the stop of an agent the Mac slept past its limit starts within about a second of the Mac waking, not at the time of day the limit fell.
Awake time is counted as well, and the agent is stopped at whichever count reaches the limit first, so a wall clock set back cannot extend a run; one set forward can end a run early.
The 46 weekly runs recorded with the real agent took 18 to 218 seconds, so a healthy run on a Mac that stays awake ends long before the limit and is never touched by it.
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

A change to `src/bin/gr0wthlab` or the launcher's package, `config/guardrails/runtime.json`, `config/guardrails/fetch.json`, or `config/products.json` needs a fresh check on the Founder's Mac, which CI cannot run:

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
