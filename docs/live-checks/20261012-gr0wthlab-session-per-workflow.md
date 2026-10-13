# One sandboxed agent session for each workflow in the weekly run (US-ME17)

The weekly run starts one sandboxed agent session for each workflow that has work due, one after another, where it started one session that did every workflow's work.
This file holds the change's design and every round of its live checks.
The first section was written into [the US-ME02 spike note](../spikes/us-me02-runtime-boundary.md) and was moved here in the merge with `main` that brought in this folder, with no new run.
It is word for word what stood there, but for five things: the three places that pointed at the single session's measurements as "above" now name that note, the sentence on where the boundary check's record is now says below, one sentence was added with the Founder's decision on the run's bound, and the sentence on the Instructions guard was corrected after review, as [the second round after review](#second-re-check-after-review) says.

## One session per workflow (US-ME17)

The weekly run was one agent session that did every workflow's work, and each workflow added to it made that session longer for every other.
The Founder approved running one sandboxed session per workflow on 2026-10-11.
This section is the design, written before the change was built.

### The sessions, and their order

A run starts at most one session for each of seven workflows, in this order:

| Order | Session | What it writes | Why it comes here |
| --- | --- | --- | --- |
| 1 | Package review | Package-change proposals in `workspace/review-queue/incoming/` | Every later session can read what it proposed before resting anything on the package |
| 2 | Post Drafts | The due days' Drafts in `workspace/drafts/posts/` | After the review, whose proposals name the package text a claim should not rest on |
| 3 | Filming | Edit records in `workspace/drafts/edits/` | After the post Drafts: an edit record runs exactly as long as its day's Draft, and a video is cut only from a Draft that passes |
| 4 | Beta Cohort recruiting | The recruiting Drafts in `workspace/drafts/beta-recruiting/` | It needs nothing an earlier session writes |
| 5 | Listening | Quote records, proposed Angles and Hooks, and reply Drafts | A reply is drafted only for a quote the same session recorded, so the three stay together, as their take-in already has them |
| 6 | Outreach | The personal-network ask, the creator messages, and the one follow-up | It needs nothing an earlier session writes |
| 7 | Rejection reasons | A code for each reason, and the proposal a strategy reason needs | Last, so its proposals can take account of every proposal the run already holds |

The order is fixed in launcher code, not in configuration: it follows from what each session needs, and a test holds it.
Sessions never run at once.
One checkout has one run lock and one `workspace/`, and two agents writing there together would make every count of one session's work a guess.

Which sessions a run starts is decided once, before the first one, from what the launcher read by then.
A workflow with nothing due starts no session, and the run report says so with the reason.

| Session | It has work due when |
| --- | --- |
| Package review | The snapshot read at least one package file |
| Post Drafts | The plan lists a calendar day the Founder has not approved |
| Filming | The filming table marks a day ready for an edit record |
| Beta Cohort recruiting | The Founder's gate is recorded and the plan asks for a Draft |
| Listening | The snapshot holds a thread or a review to read |
| Outreach | The plan holds a message that is due |
| Rejection reasons | A rejection reason has no code yet, or a strategy reason has no proposal yet |

### What each session sees

Each session is a fresh `codex exec` process started by the launcher through `process.py`, with the same command but for the path of its own closing message.
So every session runs under the same committed permission profile, with the network off and with `--ephemeral`, and the configuration fingerprint is the same for every session of a run.
The boundary preflight and the sandbox's network proof run before each session, not once per run: no agent starts on a boundary that was last proved before another agent ran.
Nothing is carried from one session to the next but the files in `workspace/`, which every session can read and write as before, and the launcher's records in `ledger/`, which none can write.

A session is told only its own workflow's work:

- Its task definition is the common part every session shares, then its workflow's own part.
  Both are reviewed files under `src/instructions/weekly-run/`, and the launcher puts them together, so a rule that binds every session is written once.
  A test reads every session's composed definition and fails when one lacks the common rules.
- Its brief is written just before it starts and holds the run's common facts, then its workflow's section alone.
  The package files it lists are the ones the Product registry says that workflow's output needs (`needed_by` in `config/products.json`); the package review's brief lists them all.
- Its brief also names what earlier sessions of the same run left in `workspace/review-queue/incoming/`, which the launcher has not taken in yet, so a later session neither repeats a proposal nor rests a claim on text an earlier one found stale.
  The Filming session's brief says which ready days have a post Draft in place.

### The launcher takes every session's work in once, when the last has ended

The alternative was to take each session's work in before the next one starts.
It was rejected because it changes the take-in rules:

- A post is queued together with its video, and the two videos of an A/B pair are compared once, when every day is settled and before any post is queued.
  Taking the post Drafts in before the Filming session had written its edit records would queue each post without its video and then replace it in the same run.
- The Review Queue is written once, when the run ends, and Mandu reads it only then.
  Nothing a run queues is withdrawn again in the same run today, and that stays so.
- A package-change proposal is refused when it asks the same as one already open, decided, or also in `incoming/`; one pass over everything in `incoming/` keeps that rule as it is.

So the take-in is the code it was, run once, in the order it had: the items in `incoming/`, the posts with their videos, the recruiting Drafts, the Listening work, the outreach Drafts, and the codes.
A session reads an earlier session's work as files in `workspace/`, never as queued items.
The Instructions guard is the one thing that is not left to the end: the launcher notes `workspace/instructions/` before the first session and puts back any change after every session, before the next one starts, so no session reads Instructions another session of the same run changed.
This is a restore and no take-in.
As first written, this design said the guard was unchanged and put changes back once, after the last session; that let a later session work from guidance an earlier one had changed, which one session per run never could.

What this costs: a later session can change or remove a file an earlier one wrote before the launcher has read it, as one long session could change its own earlier work.
The sandbox gives every session the same six areas, and narrowing that per workflow is left for later.
The counts make it visible: each session's Draft claims and proposals are counted from one reading of the Drafts due and of `incoming/` before that session starts and one once it has ended.

### One workflow's trouble stays its own

A session can fall short in four ways: it does not start (the preflight failed, or Codex could not be started), it is stopped at its time limit, it ends with an error, or the model's provider refuses it.
The last is an error exit too; the launcher reads Codex's last reported error from the session's event stream and quotes it, so a `429` reads as a refusal and not as a failure of the agent's work.
In each case the launcher goes on with the next session, takes in whatever the session had written by the rules above, and marks only that workflow's outputs incomplete, with the real reason.
The run's one notice names each session that fell short.
Every run still ends with its report.

Where a later session could not do its work because an earlier one fell short, its own section of the report shows the work not done, as it does today: a ready day with no edit record, for example.
Its output is not marked incomplete for the other session's trouble.

The package review stays the one output the agent's own word decides: its row is complete only when the Package review session's summary ends with the closing line.
Every other output is judged by what the launcher itself can check, as before.

### The closing line

Every session ends its summary with one line, `Session: complete` or `Session: incomplete: <what, and why>`.
It replaces the single session's `Review:` line, which named one workflow's work.
The line is the agent's own word, and the report quotes each session's beside what the launcher counted of that session.

### Time limits

Each session has its own limit, and the limit applies to that session alone: `agent.time_limit_seconds` in `config/run.json`, or the value `agent.session_time_limit_seconds` gives its workflow.
A session still running at its limit is stopped as the single agent was, with every process the process table shows it started, and the run goes on.

A run also has one bound on all its sessions together, `agent.run_time_limit_seconds`.
Without it the longest a run can take would grow by one session limit with every workflow added, and a provider outage that stalls every session would hold the report back for seven limits.
A session starts only while the run has time left, and gets its own limit or what is left of the run's, whichever is less; a session the bound leaves no time for is not started, and its workflow is marked incomplete for that reason.
The time counted is each session's own, as its limit counts it, the Mac's sleep included.

The numbers are set from [the measurement below](#the-limits-set-from-the-measurement), not from this design.

### A run happens when the Mac is awake, across several sessions

Nothing here holds the Mac awake, wakes it, or schedules a wake, and the owed-run check is unchanged.

- The week's run completed when every session the run had work for started and ended without an error and, where the Mac slept at any time from the run's start to its last session's end, every one of them also confirmed its work with the closing line `Session: complete`.
  A workflow with nothing due is no part of that.
- The attempts rule therefore reads every session's closing line, not one.
  Sleep can freeze whichever session is running, and a frozen session can end without an error and with its work unfinished, so no single session's word can speak for the run.
- A run that did not complete and that the Mac slept during, in any session or between two, was cut short by sleep and earns another attempt, within `schedule.attempts_per_week`.
  As before, the sleep counts wherever it fell and however the run then ended.
- A run that did not complete with the Mac awake throughout earns none and waits for the Founder.
  Its recorded ending is that of the first session that fell short: never started, timed out, or stopped early.
- A fresh run is a fresh, whole run: it starts every session that has work due again, the ones that finished in the cut-short attempt included.
  Resuming at the first unfinished session was considered and left out.
  It would need a record of which sessions an attempt finished, and a rule for when that record is stale, since a decision or a package change between two attempts changes what a finished session would have written.
  Repeating a finished session costs the Founder nothing new: the cut-short attempt has already taken in what that session wrote, the fresh session's brief lists it as open, and a Draft already in place is rewritten only for a reason.
  It costs API time and money, at most one run's worth for each attempt, which `attempts_per_week` already bounds.
- A run on demand and a one-off scheduled run always run, as before, and are never attempts.

### What the report shows

For every workflow the report says whether its session ran, and why not when it did not.
For every session that ran it gives how the session ended, its agent time against its limit, its approximate cost, the agent's closing line quoted as the agent's word, and the launcher's counts of that session alone: package files read of the ones its brief listed, the Draft claims in the Drafts it wrote or changed, and the proposals it wrote to `incoming/` that were queued.
Then it gives the run's totals: sessions run, agent time against the run's bound, and cost.

### What is unchanged

The permission profile, the six writable areas, what the sandbox reads, and the network being off.
Every check of an item, a Draft, an edit record, a quote, a message, and a code.
How Founder records are read.
The Mandu exchange, version 6.

### The weekly run timed with one session per workflow

One whole weekly run was made with the real agent at high effort on the launcher this change leaves, on 2026-10-12, the Mac's local date, with Codex CLI 0.160.0 and `gpt-6-luna`.
It was made once.

It ran in a throwaway production clone of this branch, with a throwaway remote of its own, on the Mac's real clocks and its own answer about its power state, with the real ffmpeg and the launcher's own client on the real network.
The clone's configuration was the committed one with nothing changed, the run bound at the 5400 seconds it stood at before this measurement set it.
The checkouts, the exchange folder, the Waitlist view, the footage place, and the log folder were the lab's own, named through the environment variables the Product registry and the launcher read.

- Mandu was a copy of the real checkout's RepToday package and launch checklist as they stood, 363 files, with every file and folder made read-only.
  So the run read the real package: 25 files in the snapshot, where the ten runs of 2026-10-11 read 24.
- RepToday was a clone of the real checkout at `de0355d`, and Immerse an empty folder.
- The Waitlist view held 12 made-up entries, and the footage place 13 video files, 1.3 GB in all, which the Mac's ffmpeg made from its own test pattern: at least one for every shot of days 1 to 7.

The week was set up first, with no model: two runs on demand with a stand-in for Codex that writes what a test tells it to.

- The first filed the filming plan and the Waitlist Dispatch request, and its stand-in wrote one package-change proposal, which was queued.
- Simulated decision records then approved the plan and rejected that proposal with a reason, and a Beta Build record with recruiting open was put in the exchange folder.
- The second took both decisions in, measured the footage, and counted the Waitlist; its stand-in wrote nothing, so no Draft, edit record, or message stood in `workspace/` afterwards and the rejection reason had no code.

Each of the two also let the launcher's own client make its requests, a GET for the `robots.txt` of `www.reddit.com` and of `itunes.apple.com`.
The first disallows every address for automated readers and the second every review feed, so no thread or review was asked for.
The timed run made the same two requests and no other.

The timed run was `src/bin/gr0wthlab run --trigger on-demand`, started on Monday 2026-10-12 at 16:23 local time, as run `20261012T232337Z-on-demand-7a32`.
Its own pre-run sync fast-forwarded the clone to the commit under test and restarted the launcher on it.
The launcher package, the task definitions, and the configuration it ran were tree for tree those of this branch at `c4d98d2`.
The window's first sitting is not set in the committed configuration, so the run prepared days 1 to 7 as the first batch.

What the launcher found due, and what it started:

| Session | Due in this run |
| --- | --- |
| Package review | 25 package files, none changed since the run before |
| Post Drafts | Days 1 to 7, none with a Draft in place |
| Filming | Days 1 to 7, all seven marked ready, from the 13 footage files |
| Beta Cohort recruiting | The invitation, for a batch of 8 entries, and the Waitlist ask |
| Listening | No session: no thread or review could be read |
| Outreach | The personal-network ask and a first message to each of the three creators; no follow-up was due |
| Rejection reasons | One rejection reason with no code |

How each session ended, with the launcher's own counts of that session alone:

| Session | How it ended | Agent time, of its 30 min limit | Cost | Input tokens (cached), output tokens | Package files read | Other counts | Agent's own word |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Package review | by itself, exit code 0 | 3 min 36 s (216.5 s), 12 percent | $0.048 | 2,546,269 (2,402,560), 19,536 | 19 of 25 | 4 proposals it wrote to `incoming/` queued | `Session: complete` |
| Post Drafts | by itself, exit code 0 | 3 min 6 s (185.6 s), 10 percent | $0.035 | 1,407,367 (1,295,104), 20,940 | 13 of 18 | 7 of 7 Draft claims name a code location, in the 7 of 7 due Drafts it wrote; 1 proposal queued | `Session: complete` |
| Filming | by itself, exit code 0 | 56 s (56.1 s), 3 percent | $0.008 | 276,339 (244,736), 4,159 | none listed | nothing the launcher counts | `Session: complete` |
| Beta Cohort recruiting | by itself, exit code 0 | 42 s (42.1 s), 2 percent | $0.009 | 297,392 (247,040), 3,309 | 7 of 7 | none | `Session: complete` |
| Outreach | by itself, exit code 0 | 1 min 11 s (71.2 s), 4 percent | $0.015 | 661,144 (602,880), 6,731 | 5 of 7 | none | `Session: complete` |
| Rejection reasons | by itself, exit code 0 | 1 min 22 s (82.3 s), 5 percent | $0.006 | 200,579 (168,192), 2,483 | none listed | 0 proposals queued | `Session: complete` |
| All six | 6 ran of the 6 with work due | 10 min 54 s (653.8 s) | $0.121 | 5,389,090 (4,960,512), 57,158 | | 5 proposals queued | |

The run ended with exit code 0 and no launcher problem, 664 seconds after it started, so everything the launcher did around the six sessions took about 10 seconds; the Mac was awake throughout.
The boundary preflight passed before each of the six sessions, each time refusing 13 paths, allowing the six areas, and reaching neither listed host from inside the sandbox, and each session's record holds the same configuration fingerprint.

What the launcher made of the sessions' files, in its one take-in after the last:

- The five proposals were queued and nothing was set aside.
- All seven post Drafts were blocked: each by the package's open trademark line, which blocks every post today, and four of them by a brand rule as well.
  No video was cut, since a video is cut only from a Draft that passes, so the seven edit records the Filming session wrote were left unchecked and the real ffmpeg rendered nothing.
- The invitation, with its batch of 8 entries, and the Waitlist ask were queued.
- The personal-network ask and the three creator messages were queued.
- The one rejection reason was coded, as an execution reason, so it needed no proposal.
- One notice was queued, for the sources that could not be read and the blocked Drafts.

The clone was left with a clean git status and its records pushed to its own remote.

Beside the single session's measurements in [the US-ME02 spike note](../spikes/us-me02-runtime-boundary.md#re-check-after-the-agents-reasoning-effort-and-the-work-counts-us-me17):

| What was measured | Sessions | Package | Work due | Agent time | Cost |
| --- | --- | --- | --- | --- | --- |
| Ten runs on 2026-10-11 | one | real, 24 files | the review and seven post Drafts | 283 to 1,122 s, median 646 | $0.056 to $0.158, $0.099 on average |
| Run `3205` on 2026-10-12 | one | synthetic, 18 short files | the review, seven post Drafts, seven edit records, both recruiting Drafts, four messages | 275 s | $0.038 |
| Run `7a32`, the review and post Drafts sessions | two | real, 25 files | the review and seven post Drafts | 402 s | $0.083 |
| Run `7a32`, the other four sessions | four | real, 25 files | seven edit records, both recruiting Drafts, four messages, one rejection code | 252 s | $0.038 |
| Run `7a32`, all six | six | real, 25 files | all of the above | 654 s | $0.121 |

What this one run shows:

- The sessions together did not take or cost materially more than the single session did, on the readings there are.
  The two sessions that do what the ten runs did took 402 seconds, inside the ten's range and under their median, at $0.083 against their $0.099 on average.
  The whole run, with four more workflows' work in it than those ten carried, took 654 seconds against their median of 646 and cost $0.121, inside their range and about a fifth above their average.
  Starting six sessions did not multiply what the model was sent: the run's 5.4 million input tokens, 92 percent of them cached, are fewer than the 5.9 million of the single session of run `000d` in that note, which took 8 min 32 s.
- No session came near its limit: the longest took 12 percent of it.
- The four sessions that the review and the post Drafts no longer wait for took 42 to 82 seconds each.
- What the launcher does around the sessions, with a preflight before each, took about 10 seconds of the run.

What it does not show:

- A like-for-like comparison.
  No single session was ever timed on the real package with this whole week due, so the comparison is against runs that carried less work or read a far smaller package.
- More than one reading.
  It is one run, on one day, on a Mac that other work was using throughout, so each time is an upper reading and none is a rate.
- Listening with anything to read.
  That session did not run, and its quote records, proposed Angles and Hooks, and reply Drafts are the part of a week no measurement here has timed.
- A video cut from an edit record, since no Draft passed.
  Run `3205` in [that note](../spikes/us-me02-runtime-boundary.md#the-weekly-run-timed-on-the-merged-launcher) shows that on the real ffmpeg, for the single session.
- That splitting the work made any session more thorough.
  The Package review session read 19 of its 25 files and the Post Drafts session 13 of its 18, and both said `Session: complete`; the ten single sessions read 11 to 24 of 24.
- A session that fell short, a run bound reached, the Mac asleep in a session, or a start of the weekly schedule.
  The run was on demand, so it was no attempt at the week's run; the unit tests show each of those with the stand-in agent and a simulated Mac.
- A follow-up message, or the window's second week with the second legs of its A/B pairs.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the lab was built as after the timed run.
The lab sat in the Mac's per-user temporary folder and was removed from it.

### The limits set from the measurement

A session's limit stays at 1800 seconds, 30 minutes, for every workflow, and `agent.session_time_limit_seconds` names none with another.
The longest of the six sessions took 217 seconds, and the longest single session ever measured on the real package, which held the review and the post Drafts together on a busy Mac, 1,122.
Nothing measured says a session needs more than 30 minutes, and one reading of each session is no ground for giving any of them less.

The bound on all of a run's sessions together, `agent.run_time_limit_seconds`, is proposed at 3600 seconds, 60 minutes.
It is the smallest round figure that keeps one workflow's trouble its own when that trouble is a session stopped at its limit: one session can run its full 30 minutes and the others still have 30 minutes between them.
The six sessions measured took 654 seconds together, 18 percent of the bound, and the 30 minutes left after one stopped session is more than two and a half times that.
A bound equal to one session's limit would keep the report within the 30 minutes of agent time the documents gave the Founder until this change, but the first session stopped at its limit would then leave no time for any after it.
Without a bound, seven sessions of 30 minutes could hold the report back three and a half hours.

So the longest a run's agent sessions can take together is now 60 minutes where it was 30, and that differs from what the documents told the Founder.
It was put to the Founder as a decision with these measurements.
He chose it on 2026-10-12: 60 minutes for all of a run's sessions together, with 30 minutes for each session.

With the bound set and the documents changed, the full unit suite passed under `/usr/bin/python3`, 994 tests, as did ruff, and `src/bin/gr0wthlab preflight` passed from this work's worktree: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
The boundary check is made on the launcher this branch and `main` leave together, and its record is the round below.

## Re-check after the merge with `main`

The branch was brought up to `main` at `109341f` with one merge commit, `326f93585ec6414e265d924c4eb6757e34ca9bb5`.
`main` had gained the boundary check that proves each target on its own, this folder, the kept-video file check, and the rule that a failed read leaves an open item standing.
The section above was moved here from the US-ME02 spike note in that commit.

What the merge changed in the launcher this branch had, beyond taking both sides:

- `launcher.run` removes what a stopped boundary check left in the areas before each session's preflight, as it did before the one agent's, and the run report gathers what was removed from every session's record.
- The two sentences `main` changed in the single task definition now stand in the Filming session's part, `src/instructions/weekly-run/filming.md`, since this branch split that file.
- What the post Drafts session's brief says of a day whose open post names a video that cannot be cut again follows `main`'s rule: it says the post keeps the video only when the finished file is intact, and otherwise says where that file stands, in the words `filming.kept` gives the Filming table.

On the merge commit the full unit suite passed under `/usr/bin/python3`, 1106 tests in 42 modules, as did ruff 0.15.20.
In the suite's one whole run the three tests of `main` that quote the report's line on removed probe files failed on that line's wording, which this merge changed for a run of several sessions; their module, `tests.test_cycle`, passed whole, 84 tests, once they quoted the line as the report now gives it.

### The boundary

Both checks ran on 2026-10-13, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, from this work's linked worktree at `326f93585ec6414e265d924c4eb6757e34ca9bb5`, whose `src/` is tree `1393b5b54d49b6f8369f8e1780da85a34b7e08c8` and whose `config/` is tree `b63fbe4023bdef4ff11226df3af0ee21939cdce3`, with `git status` empty before the preflight and after the check, against Mandu and the Product checkouts as they are.
The configuration fingerprint `show-config` prints there is `f22e6c34ddca9db74825e6ade7696084d3188795d2f1bf37240bb704e4918b76`.
Their logs went to `~/Library/Logs/gr0wthlab`.

- `src/bin/gr0wthlab preflight`, started at 06:36, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 06:36, passed at its first and only attempt, as `20261013T133623Z-on-demand-41d4`: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.
  The run's record gives the probe's agent 99.9 seconds of its 30 minute limit, with exit code 0.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

The commit that adds this record also adds one assertion to a unit test, on what the post Drafts session's brief says of a video whose finished file cannot be read; it changes nothing in `src/gr0wthlab/`, `src/instructions/`, or `config/`.

### What this re-check did not exercise

- A weekly run with the real agent on the merged code.
  The one timed run above was made before the merge, and nothing here repeats it; what the merge changed in the launcher, listed above, stands on the unit tests.
- A session that does not start, is stopped at its limit, ends with an error, or is refused by the model's provider; the run's bound being reached; the Mac asleep in a session; a start of the weekly schedule and its attempts.
  Each stands on the unit tests, with the stand-in agent and a simulated Mac.
- A stopped boundary check's files being removed before a session of a weekly run, which stands on the unit tests (`tests.test_launcher`, `tests.test_cycle`).
- The boundary check's hole tests, which were not repeated; they stand on the rounds `main` holds and on the unit tests.
- Listening with anything to read, and a video cut from an edit record in a run of several sessions, as the section above says.

## Re-check after review

The review of this change made eight findings, and this round applies what was decided on each.
Where a sentence of the design above says otherwise, this section is what the launcher now does; the design is left as it was written.

- **One time limit for every session.**
  `agent.session_time_limit_seconds` is gone, with its validation and its wording in the notice.
  Every session runs under `agent.time_limit_seconds`, 30 minutes, counted for that session alone, and `agent.run_time_limit_seconds`, 60 minutes, still bounds a run's sessions together, which is the Founder's decision of 2026-10-12.
  The design's "Time limits" and "The limits set from the measurement" name the removed option.
- **Codex's error is never repeated.**
  The last error Codex reported for a session is text Codex or the model's provider wrote.
  The design said the launcher quotes it; it no longer does, anywhere in `ledger/` or `workspace/`.
  The Outputs row, the workflow's line under Run state, the Sessions section, the summary, and the notice give the exit code and the launcher's own class of the error, from one wording (`Session.failure` in `src/gr0wthlab/sessions.py`), and say that the error's own text is only in the run's local log.
  It stays in the run's record in the log folder, as `codex_last_error`, which is read through `codex.last_error`; the second copy of that parser is removed.
- **A recognized refusal is a class of the error and no more.**
  The launcher still recognizes an error as the model's provider refusing or limiting the request.
  It no longer says from that match that the agent did no work: the session's work is counted and taken in as any other session's, and the notice says so.
  The design's fourth way to fall short, "the model's provider refuses it", is an error exit told with that class.
- **Starting a session and marking its output are one test.**
  A session is due exactly when its workflow owes work the launcher can name, and a session that was started and fell short always leaves its own workflow's output incomplete with the reason, whatever it had written by then.
  The notice names that output, and no longer has a way to read `nothing`.
  Two gap rules were narrower than the test that starts a session, and are now the same.
  The rejection reasons' rule names each strategy reason that still has no package-change proposal when its session fell short.
  The filming rule marks its output whenever a Filming session fell short, and names each ready day still without an edit record.
- **A Filming session still starts for a week whose ready days all keep their edit records.**
  The review asked whether the agent has work in such a week, and to start no session if it has none.
  It has: an edit record in place that fails its checks against the day's post Draft and the footage is the session's to write again, as is the record of a day whose post was rejected with its video, and the launcher cannot tell before the first session whether the post Drafts session will rewrite a Draft.
  The unit test `test_check_edits_gives_the_agent_the_launcher_s_verdict_without_opening_the_footage` in `src/tests/test_filming.py` is such a week: its second run starts with a blocked record in place for the one ready day, and the session's rewrite of it is what passes.
  So the test that starts the session stays "a day is ready for an edit record", and the marking rule now uses the same one.
- **The `--instruction` option stays removed.**
  A LaunchAgent rendered before this change passes it, and `run` no longer takes it, so every start of such a LaunchAgent ends at argument parsing with no run, no report, and no notice.
  [Operations](../operations.md#install-the-weekly-schedule) now says to remove and install the LaunchAgent again after this change, or any later change to the launcher's command line, has reached the production clone.
  No weekly schedule was installed when this was validated.
  On 2026-10-13 at 07:16 PDT `~/Library/LaunchAgents` held no file with `gr0wthlab` in its name, `launchctl print gui/$(id -u)/gr0wthlab.weekly-run` answered that it could not find the service, `launchctl list` named no gr0wthlab job, and `~/gr0wthlab`, the production clone's path in `config/run.json`, did not exist.
  So a start of the weekly schedule was not exercised, with the old command line or the new.
- **The task definition tests assert on what a session is started with.**
  The tests that searched the instruction files for phrases are removed.
  What stands instead: every workflow's composed definition is the common part, its shared parts, and its own part, whole and in that order, and in a week with every workflow due each session's prompt ends with exactly that definition.
- **The Rejection reasons brief no longer points at a Changes list it does not have.**
  It tells its session to cite a package file by its path inside the Mandu checkout, and adds "as in the Changes list" only in a brief that lists package files.

The round changed `src/gr0wthlab/` (`sessions.py`, `settings.py`, `cycle.py`, `report.py`, `filming.py`, `learning.py`), `config/run.json`, the unit tests, and the documents.
It changed no task definition, nothing in `src/gr0wthlab/launcher.py`, `codex.py`, or `probe.py`, and nothing in `config/guardrails/` or `config/products.json`.

### What was run

Everything ran on 2026-10-13, Mac local time (PDT), from this work's linked worktree at `9a05542eb80c756be04b6b1a42b896ba56246d21` with this round's changes not yet committed.
`git status` listed the same 19 changed files, none of them new, before the preflight and after the boundary check.
The trees git gives the two folders as they stood are `c296ea9a8e4a3a83b0f16c006035055bc1a99ec6` for `src/` and `ba4a9b11e1e7412df76184fcdf9e1058209490fd` for `config/`, worked out without a commit and the same before the preflight as after the check; `git rev-parse <commit>:src` and `git rev-parse <commit>:config` print them for any commit that holds the same code.
This record was finished after the check and changes neither folder.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab`, with ruff 0.15.20, passed: 87 files.
- `/usr/bin/python3 -m unittest discover -s tests -t .`, from `src/`, under Python 3.9.6, started at 07:15 and ran 1106 tests in 1402.6 seconds, with one failure.
  The failure was in a test this round adds, `tests.test_sessions.FullWeekTest.test_every_session_that_falls_short_leaves_its_own_output_incomplete_and_the_notice_names_it`, at an assertion of its own that looked for the filming tally in the Outputs table, where an incomplete row gives its reasons; the assertions before it, on all seven outputs and on the notice, had passed.
  With that assertion made on the Run state lines, and one assertion added on which briefs name a Changes list, `/usr/bin/python3 -m unittest tests.test_sessions` passed whole, 34 tests in 53.5 seconds.
  The other 41 modules were not run again after that, and nothing outside `src/tests/test_sessions.py` changed after the whole run.
- `src/bin/gr0wthlab preflight`, started at 07:40, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 07:40 and ended at 07:42, passed at its first and only attempt, as `20261013T144027Z-on-demand-225d`, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.
  The run's record gives the probe's agent 97.3 seconds of its 30 minute limit, with exit code 0.

The two live commands ran against Mandu and the Product checkouts as they are, each wrapped in `caffeinate -i -s -m`, with one override: `GR0WTHLAB_LOG_DIR` named a folder in the Mac's per-user temporary folder, so their logs went there and not to `~/Library/Logs/gr0wthlab`.
The configuration fingerprint `show-config` prints there is `8f9d66390d749976b6da1e2975ba541e8cf63c68781c3c84765a96dd25ce3bf8`, and the probe run's record holds the same one.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What this round did not exercise

- A weekly run with the real agent on this round's code.
  What the round changed in a run, which is the wording of a session that ended with an error, the two gap rules, and the one limit for every session, stands on the unit tests with the stand-in agent.
- A session that ends with an error with the real agent, and one the model's provider refuses or limits.
  The stand-in reports an error as Codex does in the recorded `429` fixture; no run of this round ended that way, and the boundary check ended with exit code 0.
- A session that fell short after it had written its work, with the real agent.
  The unit tests show it with the stand-in, for all seven workflows in one run.
- A start of the weekly schedule, as said above: no weekly schedule was installed.
  That a LaunchAgent rendered before this change ends at argument parsing stands on the unit test that the parser refuses `--instruction` (`tests.test_launcher`), not on a LaunchAgent that was loaded.
- The boundary check's hole tests, which were not repeated; they stand on the rounds `main` holds and on the unit tests.
- Everything the earlier rounds of this file list as not exercised, none of which this round took up.

## Second re-check after review

The second review of this change made two findings, and this round applies what was decided on each.

- **The agent's Instructions are put back after every session.**
  The launcher noted `workspace/instructions/` before the first session and put changes back only once the last had ended, while every session is told to read its working guidance there.
  So a file one session changed was the guidance of every later session of the same run, which a run of one session never allowed.
  The launcher now puts the folder back as noted after each session, in the step that restores access to `workspace/`, before the next session starts and before anything is counted or taken in.
  That step after the last session is the only put-back there is: the one the take-in made is removed.
  The report's Learning section and the notice name each change once, with the session it was found after.
  The design's sentence that said the guard was unchanged is corrected in place, and says what it first said.
- **A slept attempt in which a session did not confirm its work always has its part in the notice.**
  A weekly attempt the Mac slept during is cut short when any session's summary does not end `Session: complete`, and the notice had a part only for the package review.
  With every session ended without an error, the review confirmed, and another session not, the last attempt a week's run may take queued no notice, so nothing in the Review Queue asked the Founder to start a run on demand.
  Each session that ended without an error and did not confirm now has its own part in the notice of an attempt the Mac's sleep cut short, the package review's being the part it has in any run.
  The first such part says that the attempt was cut short and what follows, as a part for a session that fell short already did.
  An attempt a fresh run follows still queues no notice for that alone.

The round changed `src/gr0wthlab/cycle.py` and `src/gr0wthlab/report.py`, the unit tests, and the documents.
It changed no task definition, nothing in `src/gr0wthlab/learning.py`, `launcher.py`, `codex.py`, or `probe.py`, and nothing in `config/`.

### What was run in the second round

Everything ran on 2026-10-13, Mac local time (PDT), from this work's linked worktree at `e552973d2f837337544ed57ab82d9dd8e0f39a79` with this round's changes not yet committed.
`git status` listed the same eight changed files, none of them new, before the preflight and after the boundary check.
The trees git gives the two folders as they stood are `183cfb327590eb7cfa8beb721706d6b0449f74c8` for `src/` and `ba4a9b11e1e7412df76184fcdf9e1058209490fd` for `config/`, worked out without a commit and the same before the preflight as after the check; `config/` is the tree of the round above, which this round did not change.
This record was finished after the check and changes neither folder.

- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab`, with ruff 0.15.20, passed: 87 files.
- `/usr/bin/python3 -m unittest discover -s tests -t .`, from `src/`, under Python 3.9.6, started at 08:06 and passed: 1108 tests in 1369.4 seconds.
  Nothing in `src/` or `config/` changed after that run started.
- `src/bin/gr0wthlab preflight`, started at 08:29, passed: it wrote and deleted a file in each of the six areas, refused 14 paths, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 08:29 and ended at 08:31, passed at its first and only attempt, as `20261013T152916Z-on-demand-407a`, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort: 32 steps to prove, nine of nine file-tool targets refused in a patch of their own, eleven kernel denials naming the run's sentinels or the check's listeners, twelve of twelve permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.
  The run's record gives the probe's agent 109.3 seconds of its 30 minute limit, with exit code 0.

The two live commands ran against Mandu and the Product checkouts as they are, each wrapped in `caffeinate -i -s -m`, with one override: `GR0WTHLAB_LOG_DIR` named a folder in the Mac's per-user temporary folder, so their logs went there and not to `~/Library/Logs/gr0wthlab`.
The configuration fingerprint `show-config` prints there is `8f9d66390d749976b6da1e2975ba541e8cf63c68781c3c84765a96dd25ce3bf8`, the one of the round above, and the probe run's record holds the same one.

Mandu's, RepToday's, and Immerse's HEAD, branch, git status, stash, and a digest over every file outside `.git` were the same before the preflight and after the boundary check.

### What the second round did not exercise

- A weekly run with the real agent on this round's code.
  That the Instructions are put back after each session stands on the unit tests, with the stand-in agent: a test in which the middle session of three changes one Instructions file and adds another, and the tests of the guard `main` holds.
- A session of the real agent that changes its Instructions: no run of this round was a weekly run.
- A put-back that fails between two sessions, which no test of this round makes; `learning.put_back` says so in its line, as it did when it ran once.
- An attempt of the weekly schedule, slept through or not: no weekly schedule is installed, as the round above says.
  The notice's new parts stand on the unit tests of `report.problems_notice` in `src/tests/test_attempts.py`, on states built by hand.
- The boundary check's hole tests, which were not repeated.
- Everything the earlier rounds of this file list as not exercised, none of which this round took up.
