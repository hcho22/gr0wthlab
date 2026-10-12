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
   From the same kit it reads each asset's shot list and files the filming plan, one item per window, unless one is open or decided and the kit has not changed what must be filmed.
   It lists the footage place, read-only, and measures every file there with `ffprobe`; the agent never opens the footage, and learns each file's name and measured facts from the brief.
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
   For a Draft that passes, it checks the day's edit record in `workspace/drafts/edits/`, if the agent wrote one, against the shot list and the footage, renders it with `ffmpeg` into `ledger/assets/` with the Draft's text drawn over it, and measures the result; the day's post then shows the finished video.
   An edit record that fails a check renders nothing and blocks the day's post, naming the rule; missing video tooling is reported as a skipped edit, never as a failed run; every check is kept in `ledger/evidence/filming/`.
   A cut that fails for a reason outside the edit record (a tooling error, footage that changed while the run worked, a record that could not be written) holds the video as missing tooling does: nothing is blocked, an open post stands, and the run's notice names the failure.
   Where the day's post shows a video when the run ends, the notice and the run report say that the video could not be cut again and that the post keeps the video it shows; they say a day has no video only when its post shows none.
   The brief and `check-edits` tell the agent the same beforehand: the edit record of a day whose open post shows a video stays as it is while the video cannot be cut again, and is never reported as a problem to fix.
   Before it queues any post, it compares the two videos each A/B pair's posts are about to show, reading each from its own record in `ledger/evidence/filming/assets/`, which knows every footage file by its fingerprint and not by its name: when they show different footage outside their openings, nothing the run changed for the pair is offered, the posts that stood stay, and the run report and the notice name the pair.
   A day whose copy the Founder approved before its video existed gets its video only while its Draft is still that copy; otherwise no video is cut and the notice says so.
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
   It notes how the run ended in the record of the week's run (`ledger/run-reports/attempts/`), which the next start of the weekly schedule reads.
9. In the production clone only, it commits the changed `workspace/` and `ledger/` paths and pushes them to `main`, never anything else and never by force; a change to a README in either is put back, since only a reviewed pull request changes documentation.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run, and the run log says why the replay failed.

The schedule, how often a start of the weekly schedule checks whether the week's run is owed, how many attempts it may take, the agent's time limit, the production clone's path, and the records step are in [`config/run.json`](../config/run.json).
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

- A file the launcher sets aside from `workspace/review-queue/incoming/` is copied whole to `ledger/review-queue/set-aside/<run id>/`: a package-change proposal that declares `new_angle: yes` and names no kept quote, a file that fails the item format, and a post, a message, or a filming plan written there.
- A Draft the agent wrote, a reply that failed its checks included, stays in `workspace/` and is committed as written until it passes or is rewritten, as is any other file the agent leaves in `workspace/` that the launcher neither takes in nor puts back.
- The reasons in a run report or a notice can repeat pieces of a file's text: a front matter line, up to 80 characters of an Evidence line, the headings found.
  The reasons a Draft's checks give, kept with the Evidence of those checks, can quote the Draft.
  The reasons an edit record's checks give can quote its `shot` and `source` values whole.
  They are kept in the run's filming Evidence (`ledger/evidence/filming/<run id>.json`), in the day's post verdict in the post Drafts Evidence (`ledger/evidence/post-drafts/<run id>.json`), and in the run report and notice.
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
A post that shows a video keeps it through that change even when the video cannot be cut again in that run, for example while its footage is away or `ffmpeg` is missing: the post that replaces it shows the same finished file, as long as its Draft and its edit record are the ones it was made from and the file is still the one its record names.
Otherwise the open post stands as it is, the run report says so, and the slot reaches it once the video is cut again.

## Set the footage place

The footage place is the one folder where the Founder drops raw footage for gr0wthlab to cut.
It is unset until the Founder sets it, in `filming.footage.local_path` for RepToday in [`config/products.json`](../config/products.json), through a reviewed pull request:

```json
"footage": {"local_path": "~/Movies/gr0wthlab-footage", "env": "GR0WTHLAB_FOOTAGE_DIR", "access": "read-only"}
```

`~/Movies/gr0wthlab-footage` is the proposed place.
It is outside the production clone, Mandu, and every Product checkout, it is not a folder iCloud syncs, and macOS lets the scheduled run read `~/Movies` without the consent prompt that guards the Desktop, Documents, and Downloads folders.
The launcher refuses to start if the place overlaps this repository, Mandu, a Product checkout, or anything else the sandbox reads, since the agent could then open the footage.
`GR0WTHLAB_FOOTAGE_DIR` overrides it on one machine, for example to try a run against test clips.
The change touches `config/products.json`, so it needs the boundary check below.

gr0wthlab only ever reads the footage place: it fingerprints and measures each file and cuts finished videos from them, and nothing in it writes, renames, moves, or deletes anything there.
The sandboxed agent never opens it.
Keep the footage there for as long as its videos may need rebuilding.
Leave a file as it is, under the name it has, once a video was cut from it.
Another recording put in its place under the same name is other footage: the later leg of an A/B pair cut from it is not offered beside a video cut from the first, the notice names the file, and `rebuild-asset` refuses it.
To the pair check a file that is only renamed is still the same footage, since that check knows footage by its fingerprint.
`rebuild-asset` and every edit record find a file by its name, so a renamed file cannot be rebuilt from, and a run that checks an edit record still naming it blocks that day and withdraws its open post; the day stays blocked until the record is written again.
So keep a file under its name for as long as a post or a rebuild needs it.

Name each file for its shot in the approved filming plan, in one folder per 14-day window:

```text
~/Movies/gr0wthlab-footage/
  window-1/
    d01-s1.mov           shot d01-s1 of the plan: day 1's first shot
    d01-s1-take-2.mov    another take: anything may follow the shot's name after a hyphen, space, or underscore
    d06-s1a.mov          leg A's own opening take of a pair whose opening is re-cut
    d06-s1b.mov          leg B's
    d06-s1.mov           everything after that pair's opening, filmed once for both legs
```

- A file's name starts with its shot, `d<two-digit day>-s<number>`, exactly as the plan writes it, in upper or lower case; `.mov`, `.mp4`, and `.m4v` files are read.
- A later leg of an A/B pair adds no shot of its own: day 8 is cut from the footage of `d01`.
  Only a pair whose opening is re-cut has a take per leg, marked `a` or `b` right after the shot's name, and a take marked for one leg is used only in that leg's video, for its opening.
  Everything after the opening is shared by both legs, so it is filmed once, in a take with no leg letter: a pair filmed only as lettered takes has no video, and the run's notice names the shot that needs the shared take.
  When the Founder is on camera in the pair's first shot, each leg's Hook is said there, so each leg also needs its own take of that shot: a leg without one has no video, and the run's notice and report name the take, such as `d06-s1b.mov`.
  A pair that opens on a screen recording needs no take per leg.
- Files sit directly in the window's folder.
  A folder, a link, a file of another type, and a file named for no shot of the plan are left alone and named in the run report.
- Film upright; any resolution and frame rate is taken, and the finished video is always 1080x1920 at 30 frames a second.
  A recording of another shape is shown whole, scaled down with black beside it, and never cropped.
  HDR footage is converted when the installed `ffmpeg` has the `zscale` and `tonemap` filters; with a build that lacks them, a day cut from HDR footage has no video, and the run's notice says why.
- Sound is decided by rule, not in the edit: a cut that plays at the speed it was recorded at keeps its recording's sound, and a cut that plays at another speed, such as a timelapse, is silent.
  A video none of whose cuts carries sound has no sound stream.
- Nothing is cut from a shot's footage until a plan that holds the shot, as the package has it now, is approved in Mandu.

## Video tooling and finished videos

Rendering and measuring use `ffmpeg` and `ffprobe`, as the package's launch-video build does; `brew install ffmpeg` installs both.
The launcher looks on its `PATH`, then in `/opt/homebrew/bin` and `/usr/local/bin`; `GR0WTHLAB_FFMPEG_BIN` and `GR0WTHLAB_FFPROBE_BIN` name them outright.
A run that cannot find them, or finds a build without a filter or the font it needs, says so in its report and skips every edit; everything else still runs.

A finished video is `ledger/assets/window-<n>/day-<nn>-<recipe>.mp4` in the clone that made it.
It never enters git: `.gitignore` leaves the folder out, and the records step refuses any file under it.
Its name ends in a fingerprint of everything it was made from, so a changed edit makes a new file and never overwrites one a post already shows.
Its record, `ledger/evidence/filming/assets/window-<n>-day-<nn>-<recipe>.json`, is committed, and holds the edit record, the text drawn, each source file's fingerprint, and the tooling: everything needed to make it again from the footage.

```sh
~/gr0wthlab/src/bin/gr0wthlab rebuild-asset evidence/filming/assets/window-1-day-01-0a1b2c3d4e5f.json
```

The command renders the video again beside where its record says it was, measures it, and puts it in place only if it came out byte for byte the file its record names.
Anything else, such as a render by other tooling, which can encode the same frames differently, is reported and discarded, and whatever is at that path stays as it was.
A video no open or approved post names can simply be deleted.

## Mark the Waitlist live

No public post may go out before the Waitlist is live.
That is a fact only the Founder sets, in `waitlist` in [`config/run.json`](../config/run.json), through a reviewed pull request once US-ME05's Validation Test has passed on reptoday.app:

```json
"waitlist": {"live_since": "2026-10-20"}
```

It is never inferred from whether a source is connected or what a source is called.
While `live_since` is `null`, or a date still ahead, every post item, the run brief, and the run report say that nothing can be published until the Waitlist is live.
A post queued from that date on says the Waitlist is live; an open post keeps the line it was queued with until the launcher replaces it, and [the ledger's README](../ledger/README.md) says when it replaces a post.

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
Every other process the launcher starts (git, Codex's version and sandbox probes, the boundary check's kernel-log query, and the `ffmpeg` and `ffprobe` that measure footage and cut video) has a fixed time limit of its own, counted on the same two clocks; one that passes it is stopped the same way, and the step that needed it fails with the reason or, where it can do without the answer, goes on with what it has.

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

A change to `src/bin/gr0wthlab` or the launcher's package, `config/guardrails/runtime.json`, `config/guardrails/fetch.json`, or `config/products.json` needs a fresh check on the Founder's Mac, which CI cannot run.
Setting the footage place is one such change: the place is never one of the locations the sandbox reads, so the check should show the same policy as before.

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
