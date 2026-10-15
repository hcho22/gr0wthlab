# Operating the weekly run

How the Marketing Engineer runs on the Founder's Mac: the production clone, the first run, the weekly schedule, the Founder's weekly sitting, and how to stop it.
Why the launcher works the way it does: [the US-ME02 spike note](spikes/us-me02-runtime-boundary.md).
Why the Founder decides here, on a local page: [ADR 0002](adr/0002-the-founder-decides-in-gr0wthlab.md).
The format of every record, and what Mandu may read: [the Mandu exchange](mandu-exchange.md).

## What one run does

`src/bin/gr0wthlab run` does the whole run, scheduled or on demand.
A run on demand always does it, and so does a one-off scheduled start (`--once`); a start of the weekly schedule does it only while the week's run is still owed and the Mac is fully awake, and otherwise ends at once ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).

1. In the production clone only, while `records.save_after_run` is on, it first asks GitHub whether the repository `origin` pushes to is private, and refuses to start while GitHub says plainly that it is public ([The repository must be private](#the-repository-must-be-private)).
   Any other answer lets the run go ahead, and its records stay local unless GitHub says plainly, when asked again at step 8 and just before each push at step 9, that the repository is private.
   Then it fetches `origin` and fast-forwards `main`, and restarts itself on the new code, which asks GitHub again by its own configuration before it does anything else.
   Before the fetch, it restores its owner's read and write access to anything under `workspace/` left without it.
   It refuses to start if the clone is not on `main`, has changes outside `workspace/` and `ledger/`, or has local commits outside them.
   If the fetch fails, for example offline, it runs the current code and says so in the run report.
2. It snapshots RepToday's Go-To-Market Package in Mandu (`ledger/evidence/package-snapshots/`).
3. It takes in the Founder's decisions from `ledger/founder/decisions/`, which only the sitting page writes, and keeps each one as Evidence (`ledger/evidence/decisions/`).
   From then on a decision can no longer be changed on the page ([The weekly sitting](#the-weekly-sitting)).
   It keeps each sitting it learns of as Evidence too (`ledger/evidence/sittings/`): from the sitting record, with its minutes, or, where a sitting ended without that record, from a decision given at it, with its time not recorded.
   It reads every other record of the Founder's from `ledger/founder/` too, and nothing in a run ever writes there.
4. It reads RepToday's anonymous Waitlist view, once its build has made one, and keeps the counts by Source, Fit answer, and opt-in, per week and cumulative, with the entry identifiers, as Evidence (`ledger/evidence/waitlist/`).
   It checks every value for anything that looks like an email address first; on a hit it discards the whole read, keeps nothing from it, and queues a Guardrail breach notice.
   A week runs Monday to Sunday, and the run report leads with the week the run is in on the Mac's clock, the one that ends at the Sunday sitting; it also says how old the view was when the run started.
5. It files each reviewed Dispatch request in `src/dispatches/` that needs filing, such as RepToday's Waitlist, under an identifier that never changes.
   A filed request stays open until the Founder decides it: any reviewed change to its text, the ask or any section, files the new text in its place, and no item the agent writes can replace it.
   A request is never filed again once the Founder approved it, and the same whole text is never asked again once the Founder rejected it.
   A request is compared with its open item by reading that item's file in `ledger/review-queue/items/`: while the file cannot be read, nothing shows a reviewed change, so the open item stays as it is, the Review Queue output is incomplete, and the run's notice names the file.
   A request with no open item is compared with each item of it the Founder rejected in the same way.
   While a rejected item's file cannot be read, the fingerprint the run state holds for that item (of its ask and its request, not its Touches or Evidence) stands in for the file: the reviewed text's own fingerprint means the Founder rejected this ask, so it is not filed again, and another fingerprint means that item asked something else.
   Where the run state holds no fingerprint either, nothing shows whether the Founder rejected this text, so the request is held: nothing is filed and nothing is withdrawn, the Review Queue output is incomplete, the run report and the run's notice name the file with the reason, and the next run compares them again.
   Two exceptions arise only after a reviewed change to the request's text while an item of it is open, which is firstmate's own reviewed act.
   A reviewed change that brings back a text the Founder rejected, while another text is open, files the rejected text again in that open item's place.
   An approval the Founder gave an item that a reviewed change had already replaced still counts as the request's approval, though no superseded item is ever handed on to firstmate: the replacement stays open for the Founder to decide, no reviewed change replaces it any more, nothing is filed after it, and the run report says so.
6. It reads the 14-day kit from Mandu, works out which calendar days need post Drafts this run, now that the Founder's decisions are in, and fixes RepToday's `main` to one commit for claim checks.
   From the same kit it reads each asset's shot list and files the filming plan, one item per window, unless one is open or decided and the kit has not changed what must be filmed.
   It lists the window's footage folder in the footage place, read-only, and measures every file there with `ffprobe`; the agent never opens the footage, and learns each file's name and measured facts from the brief.
   It reads the Founder's Beta Build record (`ledger/founder/beta-builds/RepToday.json`), which is the only thing it takes as an approval.
   Until that record exists it does nothing more about the Beta Cohort, and the run report lists the approval as not recorded.
   Once it exists, it takes in the Founder's Beta Cohort reports (`ledger/evidence/beta-recruiting/reports/`) and fixes the run's next invitation batch: the next sign-ups that asked for a beta invitation and that no batch holds, good Fit first, then by sign-up date, at most the batch size in `config/run.json`.
   It offers at most one batch at a time, and the next only after the Founder has decided the last.
   In a week whose Weekly Read is due, it works out from the kit exactly what that read asks of the Founder, takes in the numbers he has given for it on the sitting page as Evidence for each post (`ledger/evidence/results/`), writes the ask into the Review Queue for the page, and, the first time while anything asked is not given, queues one notice that lists it ([The Weekly Read](#the-weekly-read)).
   It reads the fixed list of network sources in `config/sources.json` itself, outside the sandbox: the three subreddits' newest threads and rules, and App Store reviews of the competitors the research names.
   Every request is a credential-free GET to a host listed in `config/guardrails/fetch.json`; it reads each host's `robots.txt` first and never requests a path that file disallows.
   No read waits forever: each wait on a host ends after `timeout_seconds` and each whole read after `read_deadline_seconds`, both in that file, so a host that answers a byte at a time is cut off and reported as a source not read.
   The Founder decided on 2026-10-11 that each host's `robots.txt` is binding for now, while the owners' terms are read first-hand.
   Today each named host's `robots.txt` disallows the path a credential-free reader needs, so every source is reported as not read and Listening is marked incomplete while that decision stands.
   What it read goes into one snapshot (`ledger/working/`), which is working data for that run alone (see "What is kept of what a run fetches" below), and every request it was asked to make, sent or not, into the run's request log (`ledger/run-reports/<run id>.requests.json`).
   A source that is disallowed, refused, or failing is reported with its reason, queued in a notice, and marks its workflow incomplete; the run goes on.
   The first time it reads a subreddit's rules, it queues one notice that quotes and links them; no reply Draft for that subreddit is offered until the Founder acknowledges it, and the Founder's answer stands whatever the rules say later.
   It reads the Founder's outreach records from `ledger/founder/outreach/` and works out which messages may be offered: the personal-network ask, one message for each creator in `config/run.json` that the channel plan names, and one follow-up only for a creator who was written to, has not replied, and whose waiting period has passed.
   It then decides which workflows have work for the agent this run, and for each of those, one after another, writes that session's brief and runs one agent session in the sandbox, with that workflow's task definition from `src/instructions/weekly-run/`, at the reasoning effort [`config/guardrails/runtime.json`](../config/guardrails/runtime.json) sets, which is high ([One session per workflow](#one-session-per-workflow)).
   No session has a network, and the launcher proves it before each one's agent starts: the preflight tries each listed host from inside the sandbox, and a session whose preflight reaches one, or does not finish, is not started.
   It proves the same way, before each session, that no session can read raw footage: the preflight tries to list the footage place and each footage folder in it from inside the sandbox, and a session whose preflight can list one, or does not finish, is not started ([how raw footage is kept from the agent](#how-raw-footage-is-kept-from-the-agent)).
   Every session writes only in the six `workspace/` areas; it can read `ledger/`, where the launcher keeps its records and the Founder's are, and never write there.
   Before each session's agent starts, the preflight tries to create a file in each of the six folders of the Founder's records from inside the sandbox, and the session is started only when every one of those tries was refused: one that created a file, or a preflight that did not finish or did not try a folder, keeps that session from starting.
   It tries the same in the Instructions in force, `ledger/instructions/`, and in the example sets, `src/examples/` ([Instructions changes](#instructions-changes)).
   Every session runs under the same time limit, counted for it alone; one still running at it is stopped, and the run goes on to the next session ([When a session times out](#when-a-session-times-out)).
   After each session it restores its owner's read and write access to anything under `workspace/` that session left without it, and the run report names every entry it fixed, before or after a session.
   It then puts back any change in the agent's Instructions area, `workspace/instructions/`, and in the Instructions in force, `ledger/instructions/`, which the sandbox cannot write at all, before the next session starts, so every session starts from the Instructions as the run noted them before its first session and none reads what another session changed.
   The one thing it leaves there is a proposed change the Rejection reasons session wrote, which it takes in once the last session has ended.
   The run report names each change once, with the session it was found after.
   An entry there that it could not read before the first session started is not guarded: it is left exactly as it is, and the run report names it.
7. Once the last session has ended, it takes in what all of them wrote, in one pass.
   It queues the items the sessions wrote to `workspace/review-queue/incoming/` that pass the format, sets the rest aside, and turns every problem into one notice.
   A file set aside is removed and copied nowhere: the run's set-aside record, `ledger/review-queue/set-aside/<run id>.json`, keeps its name and the reasons ([what is kept](#where-the-agents-own-words-are-kept)).
   A post or a message written there is always set aside: the launcher queues those two kinds only from a Draft that passes its checks.
   An item there that supersedes an open one is set aside too while that open item's file in `ledger/review-queue/items/` cannot be read and no run state remembers its fingerprint: the open item stands, and nothing replaces it in that run.
   So is an item there with the kind and ask of any queued item, open or decided, whose file cannot be read and whose fingerprint no run state remembers: the ledger still shows that item's kind and ask, so an item with another kind or ask is queued as always, and the Review Queue output is incomplete and names the file.
   In every workflow, only what the launcher could read takes an open item off the Review Queue: a decision the Founder recorded, a newer item that supersedes it, or a Draft or record that was read and no longer passes.
   A read that fails is told in one of two ways, by what the launcher was doing when it failed.
   Where it was judging an open item, and the failed read would otherwise have taken that item back or asked it again, the item stays exactly as it is under its identifier, not checked again, whatever else the check found.
   The read may be a file that is unreadable, not in its format, or missing where the launcher itself keeps it, or a git read that fails.
   The run report says so where it tells of the item, that workflow's output is incomplete with the read that failed as the reason, and the run's notice lists each item left that way; the next run checks it again.
   Those places are the check of an open post, message, reply, or recruiting item against its Draft and what that check reads; an open invitation or Waitlist ask while a report of the Founder's cannot be read; an open follow-up whose record of the first message cannot be read; the open filming plan while the kit cannot be read; a Dispatch request's open item whose item file cannot be read; and an item in `incoming/` that supersedes an open item whose item file cannot be read.
   Where a whole step did not run because its source could not be read, the launcher judged no item: that workflow's output always reads incomplete in the run report, with the real reason, and no item of that step is touched or listed.
   Those are Beta Cohort recruiting while the Waitlist view or the Beta Build record cannot be used; a Dispatch request whose reviewed text in `src/dispatches/` cannot be read; the post Drafts while the calendar cannot be read; outreach while the channel plan or the kit cannot be read; replies while the kit cannot be read; and the video of a day whose copy the Founder approved, while that day's Draft cannot be read.
   The run's notice names such a source only where its read failed as a source, as a package file the snapshot could not read, the Waitlist view, or the Beta Build record does; where it was read and could not be used, as below; or where it was recorded as a launcher problem, as a reviewed Dispatch text or a kit that could not be prepared is; for the video of an approved day, the notice's line that no video was cut says its Draft could not be read.
   A package file the snapshot read that the launcher then could not parse or decode, which is how the calendar fails when it has lost its table and the channel plan when it is not UTF-8, is a failed source like one that could not be read.
   The run report's Sources table shows it as `unusable`, with what the snapshot found and why the file could not be used, the summary counts it among the failed sources, and the run's notice names it once, with the outputs it leaves incomplete.
   Those are exactly the outputs whose rows in the same run carry a gap that names the file, so the notice and the run report's Outputs table agree: the post Drafts for a kit file, the brand rules among them, and the filming plan as well for the calendar, the Angle bank, and the A/B pairs; Beta Cohort recruiting for the brand rules once it has started; outreach for the channel plan; and outreach and Listening for the Angle bank, the checklist, or the brand rules whenever a message or reply could not be checked against it that run.
   The package snapshot and the package review are never among them, as the snapshot read the file.
   Each of those rows starts with the file's line and leaves out a gap of its own that says no more than that line says, with the reason it gives in the Sources table: that the file could not be used, or the filming plan's reason when every kit file that reason names is such a file leading the row.
   A gap that says more, such as that no outreach message was prepared, stays.
   A message or reply that such a file leaves unchecked is told where its item is, as before.
   While the window's filming plan is open, a kit file that fails this way, the calendar among them, is also why that plan stands, so the notice's list of open items not checked again names the plan with that file as its reason.
   Every package-change proposal there declares whether it adds or changes an Angle or Hook (`new_angle`), and the Founder sees the declaration on the item.
   One that declares it does is set aside, with what to add, unless its Evidence names the record of a Listening quote the launcher already keeps; one that declares it does not is queued whatever it touches or says.
   The launcher never checks a declaration against a proposal's wording: the Founder is the check on a wrong declaration, at the sitting.
   The package review counts as complete only when the Package review session's summary ends with the line `Session: complete`; otherwise the run report marks it incomplete and the notice says so.
   That line is the agent's own word, so the run report also shows what the launcher itself counted of each session ([Reading each session's work](#reading-each-sessions-work)).
   It checks each post Draft in `workspace/drafts/posts/` and queues a post only for one that passes; a blocked Draft is named in the run report and the notice with every failing rule or checklist line, and every check is kept in `ledger/evidence/post-drafts/`.
   For a Draft that passes, it checks the day's edit record in `workspace/drafts/edits/`, if there is one, against the shot list and the footage, renders it with `ffmpeg` into `ledger/assets/` with the Draft's text drawn over it, and measures the result; the day's post then shows the finished video.
   An edit record that fails a check renders nothing and blocks the day's post, naming the rule; missing video tooling is reported as a skipped edit, never as a failed run; every check is kept in `ledger/evidence/filming/`.
   For a post, what may be unread is its Draft, the Draft of its A/B pair's other leg, the day's edit record, a footage file that record names and that could not be read or measured, the ledger's record of the video cut from it, a kit file, the brand rules, the Product's code, or git's read of one file a claim cites.
   A claim that cites a file the commit does not hold, and an edit record that names a footage file no longer in the footage place, are checks the launcher could make: the Draft is blocked and an open post withdrawn.
   A post whose video's finished file is gone or changed still gives way to the same post without a video, but only through a Draft that was read and passes: while something that Draft's check needs cannot be read, the open post stands, the notice says where the file stands, and the first run that reads everything replaces it.
   A cut that fails for a reason outside the edit record (a tooling error, footage that changed while the run worked, a record that could not be written) holds the video as missing tooling does: nothing is blocked, an open post stands, and the run's notice names the failure.
   Where the day's post names a video when the run ends, the notice and the run report say that the video could not be cut again; they say a day has no video only when its post names none.
   They say that the post keeps the video it shows only when the finished file is on disk and is the file the video's record and the post's queue entry name, which the launcher checks by fingerprint every time before it says so ("Video tooling and finished videos" below has what it says otherwise).
   The Filming session's brief and `check-edits` tell the agent the same beforehand: the edit record of a day whose open post names a video stays as it is while the video cannot be cut again, and is never reported as a problem to fix.
   The post Drafts session's brief names each such day too, since that post can keep its video only while its Draft stays as it is.
   Before it queues any post, it compares the two videos each A/B pair's posts are about to show, reading each from its own record in `ledger/evidence/filming/assets/`, which knows every footage file by its fingerprint and not by its name: when they show different footage outside their openings, nothing the run changed for the pair is offered, the posts that stood stay, and the run report and the notice name the pair.
   A day whose copy the Founder approved before its video existed gets its video only while its Draft is still that copy; otherwise no video is cut and the notice says so.
   It files each reviewed proposal in `src/proposals/` once, and never again whatever the Founder decides: the brand lint's word lists, the wording that says the 200-impression floor counts each platform's views while `read-the-results.md` does not say so, and, in a run with outreach messages to offer, the loss-framing and sponsorship-ask lists.
   It checks the Weekly Read memo when its session was due, and, when it passes, keeps the memo the Founder reads in `ledger/weekly-reads/`, queues one Weekly Read decision item for each of its lines, and removes the memo from `workspace/weekly-reads/`, so it is never taken in again for other numbers; a memo that fails a check stays in `workspace/weekly-reads/` as written, and the notice names each failing check.
   It checks each recruiting Draft the brief asked for in `workspace/drafts/beta-recruiting/`, and queues the invitation, with its batch attached, or the Waitlist ask only from a Draft that passes; a blocked Draft is named in the run report and the notice with every failing rule.
   A recruiting Draft that holds anything that looks like an email address is removed from `workspace/`, so the records step never saves it.
   It withdraws an open recruiting item whose Draft stopped passing, or that outlived the end of recruiting, at the Founder's stop or once the Founder reports the cohort full, and keeps the run's recruiting Evidence in `ledger/evidence/beta-recruiting/`.
   It replaces an open invitation that holds a sign-up who left the Waitlist with the batch made again without them, and withdraws it when that batch cannot be made.
   It replaces an open Waitlist ask whose stated gap changed with one that states the current gap, and withdraws it once the cohort can reach its minimum.
   While a report of the Founder's in `beta-reports/` cannot be read, no reported count ends recruiting and an open Waitlist ask is not judged by its gap, since a later report may correct a count; a recruiting Draft, or a package file it cites, that cannot be read leaves its open item as it is.
   A report that cannot be read holds back only what rests on the Founder's counts.
   It does not hold back what the Waitlist's view shows, since the view was read: an open invitation that holds a sign-up who left the Waitlist or its beta opt-in is still taken back.
   It is replaced by the batch made again without them, as above, unless the counts that were read say the cohort is full: then it is withdrawn with that reason and no batch is made in its place, since a later report may correct that count, the notice names the report, and the Beta Cohort recruiting output is incomplete.
   Nor does it hold back the address check: a recruiting Draft the brief asked for is read, and removed when it holds what looks like an email address, before anything else is weighed.
   It keeps each quote record whose words stand in the text it fetched from that record's link (`ledger/evidence/listening/quotes/`), and refuses every other: a refused record is removed, and only its file name and the reasons are kept.
   Once the sessions' work is taken in and the run ends, it removes the snapshot.
   It queues a proposed Angle or Hook only when every source it cites is a kept quote, with the confidence it counts itself, and discards an unsourced one with a note: the discarded file is removed, and only its name and the reasons are kept.
   It checks each message Draft in `workspace/drafts/messages/` and queues a message only for one that passes; an open message that may no longer be offered, such as a follow-up to a creator who has since replied, is withdrawn.
   Only a record that was read withdraws a follow-up: when `ledger/founder/outreach/` cannot be read, or the record of a creator's first message is missing after a follow-up was queued from it, cannot be read, or is not valid, that follow-up is neither offered nor withdrawn, an open one stays as it is, and the run report names the outreach records as failed and the Outreach output as incomplete, with the reason.
   For a message Draft, a source it is checked against that cannot be read withdraws nothing either: an open message or reply stands, not checked again, and the Outreach or Listening output is incomplete and names the source.
   Those sources are the message's own Draft; the Angle bank, the checklist, and the brand rules; the Product's code, or git's read of one file a claim names when that read times out, cannot start, or fails on a file the commit holds; and the kept quote record a reply answers (`ledger/evidence/listening/quotes/`).
   A claim that names a file that is not there, and a reply whose quote record is absent altogether, are checks the launcher could make: the Draft is blocked and an open item withdrawn.
   It takes in the code the agent proposed for each rejection reason, writes it beside the Founder's words in that decision's Evidence, and rebuilds the learning ledger (`ledger/evidence/learning/ledger.json`), whose counts read "3 of 7".
   A proposed code that fails its check is set aside: its file is removed, and the run report and notice name it with the reasons.
   The `Rejection reasons coded` output is complete only when every reason the brief listed has an accepted code, or there was none to code; a reason left without one, or a reason that could not be read, marks it incomplete, and the reason is asked for again at the next run.
   It then takes in the proposed Instructions change the Rejection reasons session left, if any, re-runs that workflow's example set with the Instructions in force and with the change, and keeps the change only if no example did worse ([Instructions changes](#instructions-changes)).
8. In the production clone only, while `records.save_after_run` is on, it asks GitHub again whether the repository is private; on any answer but a plain private, the run report and the run's notice say that this run's records were kept local, with the reason.
   It writes `ledger/review-queue/queue.json`, each workflow's run state (`ledger/run-reports/state/`), and the run report (`ledger/run-reports/<run id>.md`), whose first line is `checked=N acted=N note=...` even when nothing happened.
   It notes how the run ended in the record of the week's run (`ledger/run-reports/attempts/`), which the next start of the weekly schedule reads.
9. In the production clone only, it commits the changed `workspace/` and `ledger/` paths and, only if GitHub said at step 8 that the repository is private and says so again just before each push, pushes them to `main`, never anything else and never by force; a change to a README in either is put back, since only a reviewed pull request changes documentation.
   The records the Founder made at a sitting are in `ledger/founder/`, so they are saved here too: those made before the run by its first records step, and those made while it ran by this one.
   A record of the Founder's that holds what looks like an email address, as only one changed by hand can, is never committed.
   If `origin/main` moved meanwhile, it replays the records commit on top and retries once; a commit that cannot be pushed stays local and goes with the next run, and the run log says why the replay failed.

The schedule, how often a start of the weekly schedule checks whether the week's run is owed, how many attempts it may take, each session's time limit and the bound on all of a run's sessions together, the production clone's path, and the records step are in [`config/run.json`](../config/run.json).
Launcher logs, each session's event stream from Codex, Codex's own log of that session with its record of each tool call, and each run's record go to `~/Library/Logs/gr0wthlab/`: a run's own record is `<run id>.json`, and each session's files carry its workflow after the run's identifier, as in `<run id>.post-drafts.events.jsonl`.

## One session per workflow

A run does not hand the agent everything at once.
It starts one sandboxed agent session for each workflow that has work due, one after another, and takes in what they all wrote once the last has ended.
Until 2026-10-12 a run was one session that did every workflow's work, so each workflow added to it made that session longer for every other; [the change's own record](live-checks/20261012-gr0wthlab-session-per-workflow.md#one-session-per-workflow-us-me17) has the design and why.

The sessions, in the order a run starts them:

| Session | It has work due when | What it writes |
| --- | --- | --- |
| Package review | The snapshot read at least one package file | Package-change proposals in `workspace/review-queue/incoming/` |
| Weekly Read | A Weekly Read is due, the Founder has given numbers for it, and its memo was not written from exactly those, with none of its items decided | The memo in `workspace/weekly-reads/`, and a Dispatch request where a result would change the product |
| Post Drafts | The plan lists a calendar day the Founder has not approved | The due days' Drafts in `workspace/drafts/posts/` |
| Filming | The Filming table marks a day ready for an edit record | Edit records in `workspace/drafts/edits/` |
| Beta Cohort recruiting | The Founder's gate is recorded and the plan asks for a Draft | The recruiting Drafts in `workspace/drafts/beta-recruiting/` |
| Listening | The snapshot holds a thread or a review to read | Quote records, proposed Angles and Hooks, and reply Drafts |
| Outreach | A message is due | The personal-network ask, the creator messages, and the one follow-up |
| Rejection reasons | A rejection reason has no code yet, a strategy reason has no proposal yet, or an execution reason may still lead to an Instructions change | A code for each reason, the proposal a strategy reason needs, and at most one proposed Instructions change |

The order is fixed in launcher code ([`src/gr0wthlab/sessions.py`](../src/gr0wthlab/sessions.py)), because it follows from what each session needs.
The package review comes first, so every later session can read what it proposed.
The Weekly Read comes next, so the post Drafts session can read its memo.
The post Drafts come before Filming, since an edit record runs exactly as long as its day's Draft and a video is cut only from a Draft that passes.
The rejection reasons come last, so their proposals can take account of every proposal the run already holds.
Sessions never run at once: one checkout has one `workspace/`.

Which sessions a run starts is decided once, before the first, from what the launcher read by then.
A workflow with nothing due starts no session, and the run report says so with the reason, as in `no session: no calendar day is ready for an edit record`.

What a session is, and is told:

- Each session is a fresh Codex process started by the launcher, with the same command as every other but for where it writes its closing message.
  So each runs under the same committed permission profile, with the network off, and keeps nothing from the session before it: only the files in `workspace/` pass from one to the next.
  The launcher proves the boundary before each session's agent starts, and records the configuration fingerprint of each session's own command; the run report says whether they are all the same.
- Its task definition is the part every session shares (`common.md`), then the shared parts its workflow uses (`items.md` for writing a proposal, `messages.md` for writing a message Draft), then its workflow's own part, all reviewed files in `src/instructions/weekly-run/`.
  The launcher puts them together, so a rule that binds every session is written once, and a run refuses to start when a part is missing.
- Its brief (`ledger/run-reports/<run id>.<workflow>.brief.md`) is written just before it starts and holds the run's facts, then its workflow's section alone.
  It lists the package files the Product registry says that workflow's output needs (`needed_by` in [`config/products.json`](../config/products.json)); the package review's brief lists them all, and the Filming and Rejection reasons briefs list none, since those briefs hold what the sessions work from.
  It names the sessions the run starts, and no workflow with nothing due, so nothing is said of work that has not begun.
- A session that may write proposals is told which files wait in `incoming/`, by name alone, so it neither repeats one nor rests a claim on text an earlier session found stale.
  The Filming session is told which ready days have a post Draft in place.

The launcher takes nothing in while a session can still write.
One take-in, once the last session has ended, keeps every take-in rule what it was when a run had one session: a post is queued together with its video, the two videos of an A/B pair are compared once, and the Review Queue is written once.
A later session reads an earlier one's work as files in `workspace/`, never as queued items.
Every session has the same six areas, so a later one can change a file an earlier one wrote before the launcher has read it; the counts below are made per session, by fingerprint, so the report shows it.
The agent's Instructions are the exception, since every session reads its working guidance from them.
The Instructions in force are in `ledger/instructions/`, which the sandbox can read and never write, and `workspace/instructions/` holds only a change the agent proposes.
The launcher notes both before the first session and puts both back as noted after every session, in the same step that restores access to `workspace/` and before the next session starts or anything is counted or taken in; after the Rejection reasons session it leaves the proposed change that session may write, to take in once the last session has ended.
So no session works from Instructions another session of the same run changed, and a file another session added there is gone before the next starts.
That step is a restore and no take-in: nothing else in `workspace/` is read or changed by it.
The report's Learning section and the notice say once what was changed and put back, each line with the session it was found after, as in ``after the Listening session: `instructions/outreach.md` was added during the run and removed``.
A change that could not be put back is told the same way, and the next session then reads the file as it stands.

One workflow's trouble stays its own.
A session that does not start, is stopped at its time limit, or ends with an error leaves the sessions after it to run.
The launcher takes in whatever that session had written, by the same rules, marks that workflow's outputs incomplete with the real reason, and only those, and names the session in the run's notice with the output it left incomplete.
Starting a session and marking its output are one test.
A session has work due exactly when its workflow owes work the launcher can name, which is the table above, and a session that was started and fell short always leaves its own workflow's output incomplete, whatever it had written by then: a session that wrote every file and then ended with an error still reads incomplete, since nothing shows that it finished.
With the reason, the row names what the launcher can still name of that workflow's work: a day with no Draft, a ready day with no edit record, a missing recruiting Draft or message, a rejection reason with no accepted code, and a strategy reason with no package-change proposal.
A Filming session is started for every week with a day ready for an edit record, also when each such day keeps the record an earlier run left: its work is then to check each record against the day's post Draft and the footage as they now stand, and to write again one that no longer passes.

A session that ended with an error is told by its exit code, in the launcher's own words.
Where Codex reported an error, the report adds the launcher's own class of it and never the error itself, which is text that Codex or the model's provider wrote and can hold account details: `ended with exit code 1 and an error the launcher recognizes as the model's provider refusing or limiting the request, whose own text is only in the run's local log`, or `an error Codex reported` where the launcher recognizes no class.
The same words stand in the Outputs row, the workflow's line under Run state, the Sessions section, the summary, and the notice, and nothing in `ledger/` or `workspace/` repeats the error.
It is in that run's record in the log folder, `codex_last_error` under the session in `~/Library/Logs/gr0wthlab/<run id>.json`, and in the session's own event stream beside it.
The class says what the error is recognized as and nothing of what the agent did before it: a refusal can come after turns that wrote files, so that session's work is counted and taken in as any other session's, and its lines in the report say what the launcher counted.
A session that did not start is told with the launcher's own reason, which after a `codex --version` or `codex sandbox` probe that exited with an error ends with up to 500 characters of what that probe wrote to its error stream; those probes run with no model.
Where a later session could not do its work because an earlier one fell short, its own section of the report shows the work not done, such as a ready day with no edit record; its output is not marked incomplete for the other session's trouble.
Every run still ends with its report.
A run's exit code is 0 when every session it had work for ended without an error, and otherwise that of the first session that fell short, which is 6 for one stopped at a limit.

Every session ends its summary with one line, `Session: complete` or `Session: incomplete: <what, and why>`.
It is the agent's own word.
The launcher reads it in two places only: the package review's output is complete only when the Package review session's summary ends with `Session: complete`, and a weekly attempt the Mac slept during is the week's run only when every session confirmed its work that way ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).
Every other output is judged by what the launcher itself can check.

## Instructions changes

The agent's Instructions are its own working guidance for each workflow, one file each in [`ledger/instructions/`](../ledger/instructions/README.md).
They change from an execution-coded rejection reason only through that workflow's example set, as [ADR 0003](adr/0003-instructions-change-only-through-their-example-set.md) decided, and from nothing else but a reviewed pull request.

1. **What is offered.**
   Before the first session, the launcher picks the workflow of the oldest rejection reason that may still lead to a change: one coded as execution, or not coded yet, of a workflow with Instructions and an example set that can run on this Mac, that nothing has answered.
   A workflow whose last kept change's notice the Founder has not decided yet is passed over until it is decided, and so is one whose example set cannot run here, as the filming set on a Mac without the video tooling: its reasons wait, and the workflow of the next oldest reason is offered instead.
   The run report's Instructions section says in one line which workflow was held and why.
   The Rejection reasons session's brief lists that workflow's reasons; a run offers one workflow and tries at most one change.
2. **What the agent writes.**
   It may write one file, `workspace/instructions/<workflow>.md`: front matter with `workflow:`, the `reasons:` it answers, and a one-line `summary:`, then the whole proposed text.
   `check-work --part learning` checks it as the launcher will.
3. **What the launcher refuses.**
   A proposal for another workflow, one that cites no reason, or a reason that is not offered or not coded as execution (a strategy reason never is), a summary longer than one line of 300 characters, a text that is the one in force, longer than 32,000 characters, drops a comment line of the text in force, holds what looks like an email address, or adds a line holding a passage of at least 24 characters of any text file the sandbox may read of a Go-To-Market Package, under every path the Product registry names for it.
   A refused proposal is removed and named with its reasons in the run report and the notice, and its reasons are offered again.
4. **The example set.**
   The launcher runs each example of the workflow's set in `src/examples/<workflow>/evals.json` that carries `run`, one at a time, once with the Instructions in force and once with the proposed text.
   Each run is that workflow's session in a throwaway lab under `ledger/working/examples/<change id>/`, built from the example's synthetic fixtures, with the same Codex command, permission profile, preflight, task definition, and brief a weekly run uses; the lab's run takes the session's work in with the weekly run's own checks, and the example's assertions are read off what it took in.
   A lab reads no network: what an example's sources answer comes from its fixtures.
   A filming example's footage is made with `ffmpeg`'s test pattern, so a Mac without the video tooling cannot run the filming set.
   Each lab is removed once its checks are read, and each lab run's log is kept in `~/Library/Logs/gr0wthlab/examples/<change id>/`, beside the sessions' own files.
5. **The verdict.**
   An example is worse when a deterministic assertion held with the Instructions in force and fails with the change.
   Since the agent's output varies from one session to the next, where an assertion did worse the example is run again with the Instructions in force, and the assertion counts as worse unless it fails there too; the notice and the record say what the repeat showed.
   The change is kept only when every example ran to its end on both sides, its repeat included, and none is worse; the launcher stops at the first example that is worse or could not be compared.
   Judged statements, such as one about tone, are judged by nothing: the notice lists them as not judged.
6. **The bound.**
   The example sessions together have `learning.gate_time_limit_seconds` of agent time, 3600, and each `learning.example_time_limit_seconds`, 600, or what is left of the bound ([`config/run.json`](../config/run.json)).
   The run's own sessions keep their bound beside it, so a run that tries a change can take about an hour more.
7. **What is kept.**
   A kept change is written to `ledger/instructions/<workflow>.md` and queued as one notice, "Notice: the <workflow> Instructions changed", with the Founder's words of each reason, the agent's code and line for each, its summary, the change line by line, and every example's result on each side.
   Every change tried is recorded in `ledger/evidence/instructions/<change id>.json`; each cited reason's decision Evidence records what became of it, so it is not offered again.
   A kept change keeps the text before it and the text it wrote beside its record, in `ledger/evidence/instructions/<change id>/`; one not kept keeps none of the agent's text ([where the agent's own words are kept](#where-the-agents-own-words-are-kept)).
   A change the example set could not judge, because the bound ran out, an example's session did not run to its end, its lab's launcher could not take that session's work in, one of its checks could not be read, or the example set stopped, is not kept, and its reasons are offered again.
   A kept change's record is written before its text, so its notice can always undo it; and its notice is closed only by the Founder's decision, never by an item in `incoming/` that names it in `supersedes`.
   A kept change in force whose notice the Review Queue does not hold is said so in that run's report: a notice that could not be queued in its Summary, its Instructions section, and the run's problems notice, and a queue that could not be written, which loses that problems notice too, in its Summary and Instructions section.
   The next run files the notice again from its record, before the first session, exactly as it was; until the Founder decides it, no other change to that workflow's Instructions is tried.
   A decision such a run takes in again from the same record keeps the code its reason was given and what became of the reason as a change to the Instructions, so no reason is offered twice.
   The run report's Instructions section has all of it, and the Outputs table an `Instructions changes` row, incomplete when a proposal was refused, a change could not be judged, a rejected change could not be undone, a kept change is in force without its notice, or a record of any of it could not be read or written.
   The example set's sessions are not among the run's own sessions; the report counts their sessions, agent time, and approximate cost on a line of their own.
8. **The Founder's answer.**
   Acknowledging the notice keeps the change.
   Rejecting it, with a reason, makes the next run put the workflow's Instructions back to the text before the change, before any session starts, and the run report says so; the reason is kept and coded like any other, under that workflow.
   An undo is made only while the Instructions still hold the text the change wrote: one a reviewed pull request has changed since is left as it is, and the run report and notice say so.
   A rejection taken in again, as after a Review Queue that could not be written, leaves a change an earlier run already undid for it as that run left it, and the run report says it was undone.

To undo a kept change by hand, restore the file from git history (the records step committed it with the run's records), as a reviewed change.
An example set changes only through a reviewed pull request; `src/tests/test_example_runs.py` runs every example the agent re-runs in its lab with a stand-in agent that writes a good output, and fails when an example could not hold.

## What is kept of what a run fetches

The snapshot of what a run fetched over the network is working data for that run alone.
It lives in `ledger/working/`, where the agent can read it while the run is in progress and can never write it.
Git ignores that folder, so the records step never saves it, and the launcher removes it when the run ends, however the run ends.
Anything a killed run left there is removed before the next run reads its sources, so no agent ever reads an earlier run's snapshot.
As Evidence of what was fetched, only what the agent actually quoted and the launcher validated is committed: each kept quote with its link, the date read, and a hash of the document it came from (`ledger/evidence/listening/quotes/`).
Besides the kept quotes, the launcher's own records of the reading say where it read and what became of each source: the request log holds addresses and outcomes, and a subreddit's rules notice quotes that subreddit's rules for the Founder.
The request log also holds the `robots.txt` rule lines of the group that applied to each host, each Allow and Disallow with its path as fetched.
`check-work --run <run id>` checks quotes against the snapshot, so it answers only while that run is in progress.

## Where the agent's own words are kept

Nothing else the agent writes is checked against what was fetched, so text of its own can repeat a stranger's words.
This is the one list of the places such text may sit; `AGENTS.md` and `ledger/README.md` point here.

Of everything the launcher refuses, a Draft waiting for a fix is the one place a stranger's words may still sit (the Founder's decision of 2026-10-13):

- A Draft the agent wrote, a reply that failed its checks included, stays in `workspace/` and is committed as written until it passes or is rewritten.
  The Weekly Read memo is the Weekly Read's Draft: one that fails a check stays in `workspace/weekly-reads/` the same way, with any comment it quotes, which is always one the Founder gave on the sitting page.
  The reasons its checks give can quote it, where those checks are kept: the Evidence of each workflow's Draft checks, such as the day's post verdict in `ledger/evidence/post-drafts/<run id>.json`, and the run report and notice.

Everything else the launcher refuses is removed from `workspace/`, copied nowhere, and leaves only its name and the launcher's reasons:

- A file set aside from `workspace/review-queue/incoming/`, of any kind, a post, a message, or a filming plan written there included.
  The run's set-aside record, `ledger/review-queue/set-aside/<run id>.json`, keeps its name and the reasons, under the run's identifier; the run report and notice name it with the reasons.
- A quote record the launcher refuses, a proposed Angle or Hook it discards from `workspace/review-queue/angles/`, and a rejection code it sets aside.
- A proposed Instructions change the launcher refuses from `workspace/instructions/`, and one whose example set did not keep it.
  The record of one not kept, `ledger/evidence/instructions/<change id>.json`, keeps each line it changed by its number and the fingerprints of the two texts, beside the example set's results.

The reasons given for any of these say which line or field breaks which rule, in the launcher's own words, and never repeat what the file says.
A front matter line is named by its number, an Evidence line by its place in the list, and an unexpected section by count.
A reason may still name what the rule itself sets, such as a queued item's identifier.
That no reason repeats the refused file is firstmate's reading of the Founder's choice of 2026-10-13 for what the launcher refuses from the agent's outbox, `workspace/review-queue/incoming/`, and not a separate decision of the Founder's.
They are kept in the set-aside record, in each run's Listening Evidence (`ledger/evidence/listening/runs/<run id>.json`), in the record of an Instructions change not kept, and in the run report and notice.

These also keep the agent's words, and none of them is a refusal:

- What the launcher accepts keeps the agent's own words: the text of a queued item, the context of a kept quote, the line that says why a rejection code fits, and each line of a Weekly Read memo that passed, in the memo the Founder reads and in its item.
  So does a kept Instructions change: its text is the Instructions in force (`ledger/instructions/<workflow>.md`), its record keeps that text, the text before it, the agent's summary, and its notice as filed, and its notice shows the summary and each changed line.
- Any other file the agent leaves in `workspace/` that the launcher neither takes in nor puts back is committed as written.
  An edit record waiting for a fix is one: its `shot` and `source` values can hold any text, and it stays committed as written.
  The reasons its checks give can quote those two values whole, and are kept in the run's filming Evidence (`ledger/evidence/filming/<run id>.json`), in the day's post verdict in the post Drafts Evidence, and in the run report and notice.
  So are the files in `workspace/review-queue/incoming/` in a run whose Review Queue could not be read, which takes in nothing from there.
- The run report quotes each session's own summary, up to 4,000 characters each, where it quoted one session's before a run had several.
- Outside the repository, each session's event stream and Codex's log of it in `~/Library/Logs/gr0wthlab/` hold what the agent wrote, a refused file included: they are the runtime's own records, which the boundary check reads, and nothing in the repository copies them.

## Set up the production clone (once, after merge)

Make the GitHub repository private first: from the first real run on, every run pushes the Drafts, the Evidence, the Review Queue, the run reports, and every line the Founder types on the sitting page to it, and a changed or withdrawn decision keeps its first wording in the history.

```sh
git clone https://github.com/hcho22/gr0wthlab.git ~/gr0wthlab
cd ~/gr0wthlab
src/bin/gr0wthlab preflight        # proves the write boundary, the footage folders unread, and the closed network with no model
src/bin/gr0wthlab boundary-check   # the US-ME02 check, from this clone
src/bin/gr0wthlab run              # the first run, on demand
```

The first run should end with `records: pushed`; check that `main` on GitHub gained one `chore(records): outputs of run …` commit touching only `workspace/` and `ledger/`.
Then hold the first sitting: `src/bin/gr0wthlab sitting` ([The weekly sitting](#the-weekly-sitting)).
The push uses the Mac's git credentials for `https://github.com` (the `gh auth git-credential` helper); if it fails, the commit stays local and the next run pushes it.
A first run that ends with `records: withheld` did not hear from GitHub that the repository is private, and its run report and notice, or the next run's report, give the reason ([The repository must be private](#the-repository-must-be-private)).

### The repository must be private

A run in the production clone that saves its records (`records.save_after_run`) asks GitHub whether the repository `origin` pushes to is private before it does anything else, asks again once its sessions' work is taken in, before it writes its notice and run report, and asks again just before each push.
A run that restarts itself on new code after its sync asks again, by the new code's configuration, before it does anything else, so a reviewed change that turns `records.save_after_run` on while the repository is public stops the restarted run before any session.
A run with `records.save_after_run` off pushes nothing and asks GitHub nothing, whatever the repository is.
The question is one `gh api repos/<owner>/<name>` read, outside the sandbox, with the same GitHub login the push uses, and GitHub has 60 seconds to answer.
While GitHub says the repository is public, the run refuses to start with exit code 4 and says so: nothing is fetched, snapshotted, started, or saved.
A weekly start refused this way is an attempt that did not complete, as any refused start is: with the Mac awake throughout, the week's run then waits for the Founder ([Which endings earn another attempt](#a-run-happens-when-the-mac-is-awake)).
When the first answer only falls short of confirming that the repository is private, because GitHub cannot be reached, `gh` is missing or has no login, `origin` does not push to a repository on github.com, or the answer does not say plainly that the repository is private or public, the run goes ahead, so a passing network failure does not cost the week's run.
Nothing is ever taken as private but GitHub's own answer that it is, so the records are pushed only when the second answer, and the answer just before each push, say plainly that the repository is private.
On any other second answer, a repository made public during the run included, the records step does not push: the run ends with `records: withheld`, its commit stays local as after a failed push, and the run report's Launcher problems and the run's notice say that this run's records were kept local, with the reason.
On any other answer just before a push, the first or the one retried after `origin/main` moved, the push does not happen either: the run ends with `records: withheld`, and since its report is already written, the next run's report says why.
The first run that finds the repository private again pushes the commits kept that way.
Every other checkout, such as a firstmate worktree or a lab, asks GitHub nothing.

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
The same holds after any change to the launcher's command line, since a LaunchAgent starts the launcher with the command it was rendered with.
A LaunchAgent rendered before the change to one session per workflow starts `run` with `--instruction <file>`, which `run` no longer takes: remove it and install it again once that change has reached the production clone, and do the same after any later change to the options `run` takes.
Until then every start of the schedule, at the weekly time and at each check after it, ends at argument parsing: no run, no report, and no notice.
After a change of day or time, the launcher's records hold no run for the new weekly time that has just passed, so the next start begins one.
A window's `first_sitting`, once set, must fall on the sitting's day, so a change of day changes it in the same pull request; a run refuses to start otherwise.

## The weekly sitting

The Founder decides the Review Queue on a small page that gr0wthlab serves on the Founder's own Mac.
It is the only way a decision, or any other record of what the Founder did, is ever written ([ADR 0002](adr/0002-the-founder-decides-in-gr0wthlab.md)).

```sh
~/gr0wthlab/src/bin/gr0wthlab sitting
```

The command prints the page's address and serves it until it is stopped.
Open the address in a browser on the same Mac.
The address holds a secret that is new each time the command starts, so an old address never works, and the page answers on `127.0.0.1` only: nothing off the Mac can reach it.
There is no AI, no model call, and no network use anywhere in a sitting.

What the page walks through, one thing at a time:

1. What the last run reports: the summary at the top of its run report.
   If the weekly run due has not finished, the page says so first, and the queue and the report it shows are the earlier run's.
2. In a week whose Weekly Read is due, each post's numbers first, one post at a time, as [The Weekly Read](#the-weekly-read) says.
3. Each open item, in the Review Queue's order, shown whole with what it touches and its Evidence.
   The Founder approves it, with a one-line note if wanted, rejects it, with a one-line reason, or leaves it for later.
   Leaving it writes nothing: the item stays open and comes back at the next sitting.
   The next run marks it carried over when it knows this sitting took place, which it knows from the sitting record or from a decision given at it, and from nothing else ([Ending it](#ending-it)).
   A carried-over item says so, and from which sitting.
   A post that shows a video plays that file on the page, so the video and its copy are approved together.
   The page asks the launcher's own check of a finished file: when the file is missing or changed, or the video's record is missing or does not name that file, the page says so in the words a run report would use and offers no approval.
   A package-change proposal says what it declares about Angles and Hooks, since the Founder is the only check on that.
4. While a Product's Beta Cohort is being recruited, the three counts: invitations sent, accepted, and first sessions booked, each a total to date.
   A count left blank is recorded as not reported, never as zero.
5. The end: how long the sitting took, which the page measured and the Founder can correct, and one button that records the sitting and stops the page.

After each answer the page shows the next thing, with what was just saved above it, read back from its file.
`Queue` in the bar lists every open item with its state, and jumps to any of them.

`What I did` in the bar is the plain place for everything that is not a decision on an item:

- A Beta Build that passed Apple's review for external testing, which is the gate Beta Cohort recruiting waits for; and, later, stopping recruiting or reopening it.
- An approved message sent, a reply received, and the wait before the one follow-up when the Founder wants another than the message stated.

gr0wthlab sends nothing and sees no inbox, so these records are the only way it learns either.

### What is saved, and where

What the Founder clicks is what is saved.
Each record is one file under `ledger/founder/`, in the format of [the Mandu exchange](mandu-exchange.md), written whole.
The page checks every record with the very check the weekly run reads it with before it writes it, so it never writes one a run cannot use.
The next run takes the records in, and its records step commits them with the launcher's own and pushes them to `main`.
The terminal the command runs in says each record as it is saved, by its path.

Every line the Founder types is kept in a record, so every limit holds at entry, and the page says why when it refuses:

- A note or a reason is one line of at most 300 characters, and a rejection needs its reason.
- No record holds an email address, a name, or anything else about a person: a person is only ever a Waitlist entry identifier.
  The page refuses any line that holds something that looks like an email address.
- A date is a real date written as `YYYY-MM-DD` and never one still ahead; a reply cannot come before its message was sent.
- A count is a whole number from 0; the minutes of a sitting are 1 to 600; the wait before a follow-up is 1 to 90 days.
  The wait is asked only on a creator's first message, the one message a follow-up can come after, and is refused on any other.

### Correcting a mis-click

- A decision can be changed, or taken back so the item is undecided again, until a run has taken it in, and never after.
  Open the item again, from `Queue` or from the line that says what was saved, and choose `Change it` or `Take it back`.
  Once a run has taken the decision in, the item is closed and never asked again.
- The Beta Cohort counts of a date and an outreach record are corrected by giving them again.
- A sitting record is corrected on its own date: start the page again, and on its last view type the right total for the date in place of the number shown, which is this sitting's minutes added to the ones already recorded.
- The Beta Build record cannot be removed; a Beta Build recorded by mistake is undone by stopping recruiting.
- A message recorded as sent by mistake cannot be marked as not sent; the one thing that follows from it is a follow-up Draft after the waiting period, which the Founder can reject.

Never edit a file under `ledger/founder/` by hand.
A record that does not follow its format is not a record: the next run names it with the exact problem, takes nothing from it, and leaves everything as it was, and the page shows the item as undecided and says its record cannot be used.
Give the answer again on the page, and the record is replaced.

### A sitting while a run is going

A run and a sitting may overlap, as when the Mac was asleep at the weekly time and the run starts as the Founder sits down.

- The page reads the Review Queue every time it shows something.
  Until the run ends it shows the earlier run's queue, under the line that says the run due has not finished.
  When the run ends, the page says that the queue changed and shows the new one; waiting for that line is the simplest way to decide on this week's items.
- A run reads the Founder's records once, before its agent starts.
  A decision given during the run is kept, and the next run takes it in.
- A decision on an item that the run then replaced with a newer one is kept on the replaced item, and the newer item stays open.
  Where the page shows the newer item, beside the line that says which item it replaces, it shows the decision recorded for that item: approved or rejected, when, and the reason or note in the Founder's own words.
- A decision the run has already taken in can no longer be changed, and the page says so.
- Only one sitting page is served per checkout at a time; a second `sitting` command says so and ends.

### Ending it

End the sitting on the page's last view, with `Record the sitting and stop the page`.
That one click saves the sitting record, with the minutes the page measured or the Founder corrected, shows what was saved, read back from its file, and stops the page; the page has no other way to stop.
A second sitting on the same date adds its minutes to the ones the date's record held when it began.

Ctrl-C in the terminal stops the page without the sitting record, as a crash or a closed laptop does.
No record is lost that way: each was written when it was given.

A run knows a sitting took place from its sitting record, which the page writes when the Founder ends the sitting on the page, or from a decision given at it.
Nothing else is read as the sign of a sitting: not the Beta Cohort counts, a Beta Build approved, recruiting stopped or reopened, or a message recorded as sent or answered.
So, for a sitting that ended without its record:

- With at least one decision given at it, every item left undecided is still marked carried over from that sitting, and the run report says `Sitting <date>: its time was not recorded.`
  That time is kept as not recorded, never as zero.
- With no decision given at it, the sitting leaves no mark.
  Its undecided items stay open and come back at the next sitting without the carried-over mark, nothing records its time, the run report has no line for it, and nothing the Founder saved is lost.

An item counts as left undecided at a sitting when it is still open, was queued on or before the sitting's date, and was queued before a run first took in that sitting's record or a decision given at it.

### What keeps the page the Founder's own

- A request to an address without the page's secret gets nothing.
- Only a POST from the page's own form, to the page's own host, writes anything; every other request that would is refused, and the page's views never write.
- Everything an item, a run report, or a record says is shown as text.
  The page lays an item out by its lines and makes no link, image, style, script, form, or tag from anything in it.
- The page loads its own style sheet, script, and icon, and nothing else; its content security policy forbids every script, style, image, video, and request it did not ship.
- The sandboxed agent cannot write `ledger/founder/`: the permission profile makes no part of it writable.
  Before each session's agent starts, the preflight tries to create a file in each of the six folders from inside the sandbox, and the agent is started only when every try was refused; [the boundary check](#after-a-change-to-the-launcher-or-configuration) has the agent itself try each folder with both of its tools.

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
  If it finishes that way, every session ending without an error and confirming its work, it is the week's run.
  If it does not, whatever ended it and wherever in the run the Mac slept, in whichever session or between two, the run does not count as the week's run: its report, where it has one, says that the Mac's sleep cut it short and for about how long the Mac slept, and a fresh, whole run starts by itself once the Mac is fully awake.
  The fresh run's report says when the run was due, when it started, which attempt it is, and when each attempt before it started.

A fresh run is a whole run under the same rules as any other: it starts every session that has work due again, the ones that finished in the cut-short attempt included, queues nothing an earlier attempt already queued, asks again nothing the Founder decided, and keeps what was carried over.
It does not resume at the first unfinished session.
The cut-short attempt has already taken in what its finished sessions wrote, so the fresh session's brief lists that work as open, and a Draft already in place is rewritten only for a reason; a record of which sessions an attempt finished would need a rule for when it is stale, since a decision or a package change between two attempts changes what a finished session would have written.
Repeating a finished session costs time and money, at most one run's worth for each attempt, which `schedule.attempts_per_week` bounds.
An attempt that a fresh run is to follow queues no notice for being cut short, since nothing is needed from the Founder.
Its notice also leaves out every part that only restates work its agent did not reach: a due day with no post Draft, a recruiting Draft that was not written, and an outreach message, first or follow-up, with no Draft.
The fresh run, being a whole run, does that work again and reports on it itself.
A ready filming day with no edit record has no line of its own in any run's notice; the run report names it.
If nothing else is left, no notice is queued, as in a week with no such work due.
Everything else queues the notice as in any run: a failed source, an item or Draft the agent left half written, a Draft that was blocked, an open item the attempt withdrew, a launcher problem.
That notice also says that the attempt was cut short and that a fresh run follows.
The attempt's run report lists everything, as any run's does.
No run closes or withdraws an earlier run's notice.
While a fresh run is owed, `next_run` in the Review Queue stays at the time the week's run was due, so the sitting page says that the week's run has not finished.
After the last attempt a week's run may take, a notice asks the Founder to start a run on demand while the Mac stays awake, and no further run starts by itself until the next weekly time.
That notice leaves nothing out: it lists the work the agent did not reach as any run's notice does.

Which endings earn another attempt:

- An attempt completed when every session it had work for started and ended without an error and, besides, either the Mac stayed awake for the whole attempt or every one of those sessions confirmed its work, ending its summary with the line `Session: complete`.
  It is the week's run, and nothing follows it.
  A workflow with nothing due is no part of that.
  With the Mac awake throughout, sessions that ended without an error completed the attempt whether or not each confirmed its work; a package review that was not confirmed queues its notice as in any run.
- An attempt that did not complete and during which the Mac slept was cut short by sleep, and earns another.
  The sleep counts wherever it fell: during the pre-run fetch in the production clone, while the launcher asked git for the checkout's boundary, during Codex's version probe or a boundary preflight, while a session ran, or between two sessions.
  It counts however the attempt then ended: refused before it started, stopped by an error, with a session never started, stopped at its time limit, or ended with an error, or with every session ended without an error and one of them not confirming its work.
  The last is what an agent can leave that the Mac's sleep froze in the middle of its work, and the sleep can freeze whichever session is running, so the launcher asks every session's closing line and not one: the report says that every session ended without an error, that the Mac slept during the run, and which session did not confirm that it finished, where it would otherwise say that the run finished.
  Such an attempt does not block the week.
  A fresh, whole run follows by itself, within `schedule.attempts_per_week`, and that run's report names it as it names any earlier attempt.
- An attempt that did not complete with the Mac awake throughout earns none and waits for the Founder.
  That covers a run with a session that timed out, stopped early, or never started, and a run that was refused before it started or that an error stopped.
  The record of the week's run keeps how the first session that fell short ended.
  Its report, where it has one, says that no run starts by itself after it.
- An attempt that left no ending, as when the Mac was restarted in the middle of it, earns none either, whether or not the Mac slept; the next run's report names it.

The launcher tells sleep the same way for a whole attempt as for one session's own time.
It reads the Mac's two clocks as a start begins: the wall clock, which goes on while the Mac sleeps, and awake time, which does not.
It reads them again once the last session has ended, or when a start ends before it has a report.
A difference of 5 seconds or more between the two is the Mac asleep; anything less is the clocks' own difference.
A start that restarts itself on newly fetched code carries its reading across the restart, so the fetch counts.
An attempt that ended before its report has no report of its own to say that the Mac slept.
The record of the week's run says so (`cut-short-by-sleep`, with `asleep_seconds`), and the fresh run's report names the attempt.

After an attempt that earns none, start a run on demand once the cause is dealt with; the next scheduled run is otherwise the next week's.

## The Weekly Read

Each 14-day window has two Weekly Reads, on its day 7 and its day 14, the Sundays one and two weeks after the window's first sitting ([Set the 14-day window](#set-the-14-day-window)).
A read is due from its day for a week, so the scheduled run on that Sunday and any run on demand that week work on it.
The day-7 read covers days 1 to 5, as the calendar's midpoint gate says; the package names no range for the day-14 read, so it covers every day posted before its own day, 1 to 13, and the freshest posts fall under the floor by the floor's own rule.

gr0wthlab reads no platform: the Founder posts by hand ([ADR 0004](adr/0004-posting-is-manual.md)), and the Weekly Read uses no YouTube connection ([ADR 0005](adr/0005-the-weekly-read-uses-no-youtube-connection.md)), so there is nothing to set up in Google Cloud and no access to grant.
The numbers come from the Founder, who reads them in TikTok Studio or YouTube Studio and gives them on the sitting page.

### What a read asks for

The run works out exactly what to ask from the 14-day kit, and nothing more:

- Each post the read covers, on the platform the calendar names as the one whose metrics adjudicate it, and on no other: nothing is asked of YouTube for a post TikTok judges, nor of TikTok for one YouTube judges.
- Its views, which the 200-impression floor counts on each platform (the Founder's decision of 2026-10-14).
- The numbers its Angle's pre-registered signal and kill criterion name, such as TikTok's watched-full rate or YouTube's share viewed rather than swiped away, and its comment count where they name comments.
  A number they name that the platform's Studio numbers hold none of, such as saves on YouTube, is named in the ask and not asked.
- The numbers the signals and kill criteria of the read's other posts on the same platform name, since `read-the-results.md` ranks each post against the others in the bank on its own pre-registered metric, and a rank needs that number for every post: each TikTok post is asked for every number any TikTok post's Angle names, and each YouTube post likewise.
  The ask says which numbers are its own Angle's and which are for the rank.
- The text of its comments, since comment content is a first-class result.

No follower count is ever asked or kept, and no number that no signal, kill criterion, or read rule names.
The run writes the ask into the Review Queue (`results` in `queue.json`) for the sitting page, which reads no package file, and queues one notice that lists it the first time anything asked is not given.

### Giving the numbers

On the sitting page, right after the run's summary, each post asked for has a step of its own: its day, Angle, and the platform's Studio, why each number is asked, a field for the day it went out, one for each number, one for its comments, and the day the Founder read them.

- The day it went out is filled in with the day you gave for the same post at the window's earlier read, or, where you gave none, the day the calendar planned it; change it when the post went out on another day, and that read's record, the agent's brief, the memo, and the Evidence use the day you give.
  Until you give it, the page, the notice, and the agent's brief call the calendar's day the day the post was planned, never the day it was posted.
- Give each number as the Studio shows it for the post: whole numbers in digits, with commas if you like, and percentages with or without the sign.
  A shortened figure such as 1.2K is refused, since it is not the number itself.
- Leave a number blank when the Studio does not show it: it is recorded as not reported, never as zero.
- Paste the comments one a line, their words only and never who wrote them; at most 40, each at most 300 characters, and nothing that looks like an email address.
- The day you read them is the source of every number in the record, the export date of US-ME11; it is today unless you change it, and never a day still ahead.
- `Leave it for later` writes nothing; a post with nothing given is not reported, and never taken to be not posted.
- Giving them again replaces the record, whole.

The page keeps no screenshot and no file: either can show a follower count or a commenter's name, neither of which gr0wthlab keeps, so the Founder reads the numbers from his screenshots or his file and types them ([ADR 0006](adr/0006-the-founder-types-the-weekly-read-numbers.md)).
Each post's numbers are one record in `ledger/founder/results/`, which only the page writes; the formats are in [the Mandu exchange](mandu-exchange.md).

Once the numbers are given, start a run so the Weekly Read takes them in:

```sh
~/gr0wthlab/src/bin/gr0wthlab run
```

While it runs, decide the other items; when it finishes, the page says the queue changed and shows the read's decision items ([A sitting while a run is going](#a-sitting-while-a-run-is-going)).

### The memo and its decisions

The Weekly Read session starts once numbers are given for the read, and again whenever the Founder gives more or corrects one while none of the read's items is decided.
It applies `read-the-results.md` exactly, the only rule source, and writes the memo in `workspace/weekly-reads/`.
The launcher checks the memo before anything is queued from it:

- every Angle with a post the read covers has exactly one line, every pair with both legs covered one line at the day-14 read, and the day-7 read one line on whether the day-14 flex slot is earned;
- every line ends in keep, kill, change, or test, and "insufficient data" is a result of its own, never a fail;
- nothing is killed at day 7, and a kill at day 14 needs the Angle flagged at risk at day 7, since a kill takes two consecutive Weekly Reads;
- an Angle none of whose posts reached the floor on the platform that judges it is insufficient data, and the floor is `read-the-results.md`'s own figure, counted in views;
- the flex slot goes only to an Angle whose line says it cleared its signal, never on rank alone, and a pair is resolved only when both legs reached the floor;
- every number has its n beside it, every unread or at-risk Angle and every pair to repost says what would settle it at the next read, and every comment quoted is on a quote line of its own and word for word one the Founder gave for that post; a decision line quotes nothing.

A memo that passes becomes the memo the Founder reads, `ledger/weekly-reads/window-<n>-read-<07|14>.md`: one line that says the floor counts each platform's views, one that says what the read cannot tell, the launcher's own table of every post's numbers with its n and "not reported" where nothing was given, the day it went out as the Founder gave it, likewise "not reported" where he gave nothing for it, whether each post is readable or unread, under the floor or with its views not given, and how many comments were given as text, the agent's lines with the comments they quote as third-party text, the Waitlist counts by Source and Fit with progress toward the opt-in bar, and the Founder's sitting time in the seven days before the read's own day, whose sitting counts toward the next read, so no sitting is in two memos.
Each of its decision lines becomes its own Weekly Read decision item, which the Founder decides like any other.
When the memo is written again, its items replace the read's open ones line for line, and an open item no line replaces is withdrawn; once the Founder has decided any item of a read, its memo stands as it is.
It is not written again while one of the Founder's results records cannot be used, or while the floor cannot be found in `read-the-results.md`: a memo written then would rest on less than he gave, so the read's open items stand, the Weekly Read memo row is incomplete with that read as its reason, and the notice names each item and the read.
A `read-the-results.md` the run read that is not text, or no longer says the floor in the words the read finds it by, is a package file the run read and could not use: its source line says so, and names the Weekly Read memo.
A result that `read-the-results.md` says would change the product is listed under the memo's Product lines, and, where it warrants one, comes as a Dispatch request for the Founder to decide, never acted on.

The run report's Weekly Read section says which read is due, how many posts it asks for and how many were given, the notice, the memo, and its items; the Post results row is incomplete while anything asked is not given, and names those posts as not reported.

### The floor in the package

`read-the-results.md` says "Any post under 200 impressions is unread, not failed", while neither platform's numbers that the kit lists name impressions.
The Founder decided on 2026-10-14 that the floor counts each platform's views, and every memo says so.
Until `read-the-results.md` says it too, each run files `src/proposals/read-the-results-views-floor.md` once, through the usual route, for the Founder to approve and Mandu to apply; it is never filed again, whatever he decides.

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
With another edit record, or a finished file that could not be read, the open post stands as it is, the run report says so, and the slot reaches it once the video is cut again.
With a finished file that is gone or changed, the post that carries the slot shows no video ("Video tooling and finished videos" below).

## Set the footage place

The footage place is the one folder where the Founder drops raw footage for gr0wthlab to cut.
The Founder named it on 2026-10-11: RepToday's own folder in Mandu, set in `filming.footage.local_path` for RepToday in [`config/products.json`](../config/products.json):

```json
"footage": {"local_path": "~/Mandu/projects/RepToday", "env": "GR0WTHLAB_FOOTAGE_DIR", "access": "read-only"}
```

Raw footage goes in that folder's `window-<n>/` folders, the footage folders, beside the package in `gtm/`.
`GR0WTHLAB_FOOTAGE_DIR` overrides the place on one machine, for example to try a run against test clips.
The place is written from the home folder, so it does not move with `GR0WTHLAB_MANDU_DIR`: a machine or a test that points that at another Mandu sets `GR0WTHLAB_FOOTAGE_DIR` too, or its runs read the footage folders of the Mandu in the home folder.
A change of the place is a reviewed change to `config/products.json`, so it needs the boundary check below.

### How raw footage is kept from the agent

The sandboxed agent reads nothing in a footage folder, and the runtime enforces that, not a sentence in the task definition.
The permission profile denies whatever it does not grant, and of Mandu it grants only the package paths the Product registry names: for RepToday, `projects/RepToday/gtm/` and the launch checklist.
Nothing else in the Mandu checkout is granted, so the footage folders are refused to the agent's shell and to its file tool alike, with the rest of the Product's folder, every other folder in Mandu, and Mandu's `.git`.
Each session's prompt lists the paths the agent can read of Mandu.
[This change's live checks](live-checks/20261012-gr0wthlab-footage-place.md#what-the-runtime-refuses) have what was measured, and why the profile grants less of Mandu rather than denying the footage folders by name.

Three things hold it, each stricter than the one before:

1. The launcher refuses to start unless the profile it builds keeps the sandbox out of the footage folders (`keep_footage_unread` in [`src/gr0wthlab/boundary.py`](../src/gr0wthlab/boundary.py), the one place the rule is kept).
   A place the sandbox can read is refused, whatever it is: this repository, a Product checkout, or a folder inside the package.
   A place may hold something the sandbox reads only inside Mandu, and there never in a footage folder; the refusal says which of the three it is.
2. Before each session's agent starts, with no model, the preflight tries inside that session's own sandbox to list the footage place and each footage folder that exists in it.
   When every one of them is refused, the session says `preflight refused a listing of the footage place and of <n> footage folders in it` and goes on to its network probe.
   A listing that succeeds keeps that session's agent from starting, with `the sandbox could read where raw footage is kept` and the folder: the run marks that session's workflow incomplete and goes on to the next session, whose own preflight comes first, so no session starts while a footage folder can be listed.
   A probe that listed nothing and fell short, because it did not finish in time, ended with an error, or did not try a folder, keeps that session's agent from starting the same way, with `the check that the sandbox cannot read the footage place did not finish` and the reason; it says nothing of what the sandbox could read, since no record shows a listing.
   The session's record holds the one wording, and the line the run prints, the run report's rows, and the notice repeat it.
   The network probe before each session is worded the same way: only with a listed host it reached does the run print `the sandbox reached the network` and the session's record say `the sandbox's network was not closed`, and a probe that reached none and fell short says `the check that the sandbox cannot reach the network did not finish`, with the reason.
   The run report's `Sandbox footage` line counts only what each session's own record of the listing covers.
   It says `tried from inside the sandbox before each of <n> sessions` when every session's record holds an outcome for the place and for each footage folder that session had to try.
   Otherwise it says `before <k> of <n> sessions` and then, for every other session, either `not tried before the <name> session` with the folders its listing left untried, or `nothing tried before the <name> session` where the listing never ran because that session's write proof had failed.
   The `Sandbox network` line counts the listed hosts the same way; the network probe runs only once the write proof and the listing have passed, so the line says nothing was tried before a session where either had not.
3. The boundary check below has the agent itself try each of them, and passes only on the runtime's own record of each refusal.

Two things the agent can still learn, neither of them footage.
The brief tells it each file's name, length, size, frame rate, and whether it has sound, since it writes the edit records.
And the system still answers a question about one file by its full name, such as its size and dates, though the sandbox can neither list a footage folder nor open a file in one.

Raw video in that folder sits in Mandu's working tree, and Mandu's git does not ignore it.
gr0wthlab never writes to Mandu, so it cannot add the ignore rule: that is the Founder's to do in Mandu, for example a `projects/RepToday/window-*/` line in Mandu's `.gitignore`.
Until it is there, a commit made in Mandu can take raw video into Mandu's history, and the boundary check, which fingerprints every changed or untracked file in Mandu before and after it runs, reads each clip twice.

gr0wthlab only ever reads the footage folders: it fingerprints and measures each file and cuts finished videos from them, and nothing in it writes, renames, moves, or deletes anything there.
For footage it reads only the place's `window-<n>/` folders, and `rebuild-asset` takes a source from nowhere else; the rest of that folder is the package, which the launcher reads as it always has.
The sandboxed agent never opens a footage folder.
Keep the footage there for as long as its videos may need rebuilding.
Leave a file as it is, under the name it has, once a video was cut from it.
Another recording put in its place under the same name is other footage: the later leg of an A/B pair cut from it is not offered beside a video cut from the first, the notice names the file, and `rebuild-asset` refuses it.
To the pair check a file that is only renamed is still the same footage, since that check knows footage by its fingerprint.
`rebuild-asset` and every edit record find a file by its name, so a renamed file cannot be rebuilt from, and a run that checks an edit record still naming it blocks that day and withdraws its open post; the day stays blocked until the record is written again.
So keep a file under its name for as long as a post or a rebuild needs it.

Name each file for its shot in the approved filming plan, in one folder per 14-day window:

```text
~/Mandu/projects/RepToday/
  gtm/                   the package, as before
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
- Nothing is cut from a shot's footage until the Founder has approved, at a sitting, a plan that holds the shot as the package has it now.

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

A finished file is the only copy of its video, since it never enters git, so every run checks the file of each video an open post names: it must be on disk, and its fingerprint must be the SHA-256 the video's record and the post's queue entry hold.
The launcher says a post shows or keeps a video only when that check passes.
A post the Founder approved is never asked again, so its file is not checked and nothing about its file is reported.
When an open post's file is gone, or is no longer the file its record names, nothing is substituted, and whatever is at that path is left as it is.
When the run can cut the video again, it does, and the post stands or is replaced as for any video.
When it cannot, for example while the footage or `ffmpeg` is away, the open post no longer has the video it names, and one of three things becomes of it, each decided by a standing rule and not by this check:

- It is replaced by the same post without a video (the Founder's decision of 2026-10-12) when the run checks the post's own Draft and may ask for it again: the day is due in that run, the Draft the post was queued from is in place and passes, and the day's edit record is in place.
  The rule is the one for any due day whose Draft passes while no video can be cut for it: its post is queued without one.
  The new item says there is no video yet and why, approving it approves the copy and the beat plan only, and the video comes back for approval in a later item once it is cut again.
  The run report and the notice name both posts and the file.
- It leaves the queue when the run checks that Draft the same way and nothing may be asked in the post's place.
  Two of the rules keep a decision from being asked again: a day's copy the Founder approved is never asked again, and a Draft the Founder rejected is not asked again until it changes.
  The third is the item format: the post without a video is checked against it once more as it is queued, and one that does not follow it blocks the day as any failing check does, so nothing is queued.
  The run report and the notice name the post and the file and say that nothing is asked in its place, and why: under the first two rules that the Founder already decided the day's copy, and under the third that its Draft no longer passes.
- It stands as it is, and every run's report and notice name it and its file, when the run does not check the post's own Draft.
  The rules are these: a run prepares, checks, and cuts only the days due in it, so nothing is cut for a day that is not due; an open post stands while its Draft is gone; an open post is not checked again, and so not withdrawn, while its Draft or anything else its check reads cannot be read (step 7 of [What one run does](#what-one-run-does) lists what that may be for a post); and a day whose copy the Founder approved is checked again only while its Draft is still that copy and it has an edit record.
  It also stands, named the same way, when the run cut a video for the day and the pair check did not let it through, since nothing a run changed for a pair whose two videos differ is offered.

Whatever else changed for the day, such as a Draft that was rewritten or fails a check, or an edit record that is gone, is settled as for any open post.
The pair rule holds across the replacement: a leg whose post now shows no video has nothing to compare, and its video is compared with the other leg's again when it is cut again.
A file that cannot be read is not a file that is gone: the report and the notice give the reason the read failed, nothing is said of whether the post keeps its video, the open post stands, and the report marks the filming output incomplete.
The same holds when the video's own record under `ledger/evidence/filming/assets/` cannot be read or does not name the file the post names.

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
A run with a session that was stopped at its time limit also ends with exit code 6, after it has written its own report, which says which session timed out.
Each checkout keeps its run lock (`ledger/run.lock`, never committed) and these notes for its next report (`ledger/notes/`) in its own `ledger/`, so a run in a firstmate worktree never blocks or hides a production run.

## Reading each session's work

A run is one agent session for each workflow that has work due, and a session ends when its agent writes its final message.
The launcher checks everything a session wrote, but whether an agent did all its work is something only the agent says, in the `Session:` line that ends its summary.
Such a line has read complete after sessions that did the least, so no session should be judged by it alone.

Each run report therefore has a `Sessions` section, and a line for each session in its summary, that set two things side by side and name each for what it is:

- What the launcher counted, from Codex's record of that session, the Draft files the run left, and the Review Queue.
  None of it comes from what an agent says of itself.
- The agent's own word: its closing `Session:` line, quoted.

The section opens with one row for every workflow: how its session ended, or why it had none, with its agent time, its limit, its cost, and its agent's closing line.
Then comes each session that was tried, with its counts, the brief it was given, and the agent's own summary, and last the run's totals.

The counts, each of one session alone:

- `Agent time`, against that session's limit, with the model and reasoning effort it ran at.
- `Approximate cost`, from that session's own token counts.
- `Package files read`: how many of the package files that session's brief listed came back to the model.
  Codex shows the model at most about 40,000 characters of one command's output, the first and last halves of that, and cuts the middle.
  A session that prints every package file in one command is shown the first and last few, so naming a file in a command is not reading it.
  The launcher counts a file as read when at least half of its lines of 24 characters or more are in the part of some command's output the model was shown; the figure is `work_counts` in [`config/run.json`](../config/run.json), a fact about Codex that needs measuring again after a Codex upgrade or a change of model.
  A file with no line that long is counted only when a command that names its path was shown its whole text, since short lines such as a lone brace are in any output.
  The count is a floor: a file read some other way, such as by a pattern that does not name it, is not counted.
  A session whose brief lists no package file, as the Filming and Rejection reasons briefs do, has none to count, and its line says so.
- `Draft claims`: how many claims the post Drafts this session wrote or changed list, how many of them name a code location, and how many name none.
  The post Drafts stay in `workspace/` from run to run, and the Post Drafts session is told to leave an open day's Draft alone when nothing in it needs changing, so a Draft on disk is often an earlier run's work.
  Every session can write there, so the launcher takes the fingerprint of each due day's Draft before each session starts, and counts a Draft as a session's only when it is new or its fingerprint differs once that session has ended.
  The line says how many of the Drafts due those are, and a session that wrote or changed none has no Draft claims to count.
  A claim item that does not follow the format names no code location, so the two figures add up to the claims listed.
- `Proposals this session wrote to incoming/`: how many package-change proposals this session wrote or changed in `workspace/review-queue/incoming/` that the launcher queued.
  An Angle or a Hook the Listening session proposes goes through `workspace/review-queue/angles/` instead: it is accounted for in the report's Listening section and is not in this count.
  The launcher tells one session's proposals from another's as it does the Drafts, by each file's fingerprint before the session starts and once it has ended.

The run's totals follow: how many sessions ran of the ones with work due, their agent time together against the bound on all of a run's sessions, their cost together, and the Draft claims and proposals of the run's sessions together.
A run queues everything standing in `incoming/`, and a run that could not read the Review Queue, or was stopped before it took its items in, leaves its sessions' items there for the next run.
The totals name those beside the run's own: `0 queued; 5 more queued in this run were left by an earlier run`.

The launcher takes one reading of the Drafts due and of `incoming/` before each session starts, and one once it has ended.
When either cannot be taken, for example in a folder left closed, that session has neither Draft claims nor proposals counted and the launcher problems say why; the session starts and the run goes on as it would have.

The counts inform the Founder and gate nothing: nothing is queued, blocked, or marked incomplete because of one, and every check of an item or a Draft is what it was.
The launcher still reads an agent's closing line itself in two places, and the counts change neither: the package review's row is complete only when the Package review session's summary ends with `Session: complete`, and a weekly attempt the Mac slept during is the week's run only when every session it started ended without an error and with that line ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).
A count that cannot be made is listed as a launcher problem, and the run goes on without it.
The run's notice lists that problem like any other launcher problem, so a run that would have queued no notice queues one for it.
The run's log record in `~/Library/Logs/gr0wthlab/`, `<run id>.json`, holds every session's counts under that session's `work`, with the name of every package file not read.
Each session's own record there, `<run id>.<workflow>.json`, holds what its agent was started with and how it ended.

### What the counts have looked like

The counts were introduced on 2026-10-11, when a run was still one session, against Mandu and RepToday as they were.
Each run was on demand in a fresh clone, so each was a first week: a package review and the first batch's seven post Drafts.

| Reasoning effort | Runs | Ended with the words `Review: complete` | Package files read, of 24 | Draft claims naming code | Proposals queued | Agent time | Cost a run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| medium, Codex's default, on `main` before the change | 3 | 0 | 6, 11, and 24 | 4 of 25 | 0 to 1 | 59 s to 2 min 38 s | $0.012 to $0.028 |
| high | 10 | 10 | 11 to 24, all 24 in four runs | 78 of 97 | 2 to 13 | 4 min 43 s to 18 min 42 s | $0.056 to $0.158 |

High effort did not make every session thorough: two of the ten read 11 and 17 of the 24 files and still said the review was complete, and one more run, made after the table's ten, read 10 of the 24 in 10 min 31 s and said the same.
A first run and then a second run in one clone each read all 24, and the second session wrote all seven Drafts again, so its Draft claims line counted all seven.
One run with Listening, outreach, and filming in its one session was timed on 2026-10-12 against a synthetic package of 18 short files: its agent took 4 min 35 s and cost $0.038.
[The US-ME02 spike note](spikes/us-me02-runtime-boundary.md#re-check-after-the-agents-reasoning-effort-and-the-work-counts-us-me17) lists every one of those runs and says what the sample does not show.

One run with a session per workflow was timed on 2026-10-12, once, at high effort: on demand in a throwaway production clone, against a read-only copy of the real package, with the fullest week that could be set up.
Listening had no session, since `robots.txt` on both listed hosts disallows every address it would read.

| Session | How it ended | Agent time, of its 30 minute limit | Cost | Package files read | Other counts | The agent's own word |
| --- | --- | --- | --- | --- | --- | --- |
| Package review | by itself, exit code 0 | 3 min 36 s | $0.048 | 19 of 25 | 4 proposals queued | `Session: complete` |
| Post Drafts, days 1 to 7 | by itself, exit code 0 | 3 min 6 s | $0.035 | 13 of 18 | 7 of 7 Draft claims name code, in the 7 of 7 Drafts due; 1 proposal queued | `Session: complete` |
| Filming, an edit record for each of days 1 to 7 | by itself, exit code 0 | 56 s | $0.008 | none listed | none | `Session: complete` |
| Beta Cohort recruiting, the invitation and the Waitlist ask | by itself, exit code 0 | 42 s | $0.009 | 7 of 7 | none | `Session: complete` |
| Outreach, the personal-network ask and three first messages | by itself, exit code 0 | 1 min 11 s | $0.015 | 5 of 7 | none | `Session: complete` |
| Rejection reasons, one reason to code | by itself, exit code 0 | 1 min 22 s | $0.006 | none listed | none | `Session: complete` |
| All six | 6 ran of the 6 with work due | 10 min 54 s | $0.121 | | 5 proposals queued | |

The whole run took 11 min 4 s, so the launcher's own work around the six sessions, with a boundary preflight before each, took about 10 seconds.
The launcher queued the five proposals, the invitation and the Waitlist ask, and the four messages, coded the one reason, and blocked all seven post Drafts, each on the package's open trademark line, so no video was cut.

Read a report against these counts.
The six sessions together took about as long as the single session's median, 10 min 46 s, and cost about a fifth more than its average, $0.099, while doing four more workflows' work than those ten runs carried.
A session that says `Session: complete` after little agent time, few package files read, or with most claims naming no code did less than these did, whatever its closing line says.
Splitting the work did not make a session read everything: the Package review session read 19 of its 25 files and the Post Drafts session 13 of its 18.
It is one reading, on a busy Mac, of a week with nothing for Listening to read; [the change's own record](live-checks/20261012-gr0wthlab-session-per-workflow.md#the-weekly-run-timed-with-one-session-per-workflow) has the set-up and what the run does not show.

## When a session times out

Every run ends with its report, so every session has a time limit and all of a run's sessions together have a bound, both in [`config/run.json`](../config/run.json).

- A session's limit is `agent.time_limit_seconds`, 1800 seconds (30 minutes) today, the same for every workflow's session.
  It is counted for each session alone.
- The bound on all of a run's sessions together is `agent.run_time_limit_seconds`, 3600 seconds (60 minutes) today.
  A session starts only while the run has time left, and gets a session's limit or what is left of the bound, whichever is less; the report gives the limit it ran with and, where the bound set it, says so.
  A session the bound leaves no time for is not started, and its workflow is marked incomplete for that reason.
  The time counted against the bound is each session's own agent time, added up.

So the agent's part of a run takes at most about 60 minutes, where it took at most 30 while a run was one session.
The bound is twice a session's limit so that one workflow's trouble stays its own: one session can run to its limit, and the others still have 30 minutes between them.

Both counts are wall-clock time from the moment a session's agent starts, the Mac's sleep included.
Nothing keeps the Mac awake for a run, and a sleeping Mac runs nothing, so the stop of an agent the Mac slept past its limit starts within about a second of the Mac waking, a dark wake included, not at the time of day the limit fell.
Awake time is counted as well, and the agent is stopped at whichever count reaches the limit first, so a wall clock set back cannot extend a session; one set forward can end a session early.

How the limits sit against what was measured:

- In the run timed on 2026-10-12 with a session per workflow, the six sessions took 42 seconds to 3 min 36 s each, the longest 12 percent of its limit, and 10 min 54 s together, 18 percent of the bound ([Reading each session's work](#what-the-counts-have-looked-like)).
- The longest single session measured on the real package, which did the package review and seven post Drafts in one, took 1,122 seconds, 62 percent of a session's limit, on a Mac running four or five such sessions at once; the ten runs of that kind took 283 to 1,122 seconds, median 646.
- No session with a Listening document to read has been timed, nor a second week of the window, so watch the `Agent time` lines of the first weekly runs.

A session still running at its limit, for example because its model stream stalled, is stopped with every process the Mac's process table shows it started, which is its descendants and every process in a session one of them leads: each is asked to stop, and any still running after 10 seconds of awake time is forced.
The launcher then reads the process table again to confirm that none of them is left, and goes on to the next session.
The stop does not find a process the agent detached earlier: one in a session of its own whose parent has already ended, as a shell command that has finished can leave.
Nothing in the process table ties such a process to the agent, so it is not stopped and the report does not speak for it; it outlives a session that finishes in time as well, since the launcher stops nothing then.

What the Founder sees after a run with a session that timed out:

- The run report's summary says which session timed out, at what limit, and that the launcher stopped it and went on with the run.
  The `Sessions` section says how long that session's agent ran by the wall clock, how many processes were asked to stop or forced, and whether any of them is still running.
- A session the run's bound left no time for is named in the summary as well: it did not start, because the time that bounds all of a run's sessions together was used up before its turn.
- If the Mac slept while a session ran, the summary and that session's lines say for about how long.
  The summary of an attempt of the weekly schedule also says for about how long the Mac slept in the run outside its sessions' time.
- Each output that needed that session is marked incomplete with the reason; the other sessions' outputs, and what the launcher does alone, are judged as usual.
- Whatever the session had written is checked as always: an item or Draft that passes every check is queued, and one cut off mid-way fails its checks and is set aside or blocked, named in the report.
- One notice in the Review Queue leads with the timeout, names every session that fell short, and lists what each left incomplete; a second run the same day whose notice would read the same adds no second notice while the first is open.
  A run of the weekly schedule that the Mac's sleep cut short queues no notice for how its sessions ended alone while a fresh run is to follow, and its notice then leaves out the work its agents did not reach ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).
- The cost line of a stopped session says the cost is not available, or gives the part Codex had reported before the stop as a floor; it never says zero, and the run's total is then a floor too.
- The run saves its records and releases the run lock, so the next run starts as usual and does the unfinished work again.
  The run itself ends with exit code 6, unless an earlier session of it fell short another way, whose exit code it then ends with.

A run of the weekly schedule with a session that timed out on a Mac that slept during the run needs nothing from the Founder: a fresh, whole run starts by itself once the Mac is fully awake ([A run happens when the Mac is awake](#a-run-happens-when-the-mac-is-awake)).
A run with a session that timed out with the Mac awake, scheduled or on demand, is not run again by itself, and neither is a run on demand or a one-off scheduled run that the Mac slept through: start one on demand if the sitting needs the missing work.
If healthy sessions come near their limit, or keep timing out though the agent was working, raise `agent.time_limit_seconds` through a reviewed pull request; it is one limit for every session, and each session's `Agent time` line shows how long it took.
If healthy runs come near the bound, raise `agent.run_time_limit_seconds` the same way.
A session that timed out because the Mac slept past its limit needs no higher limit.
Each value must be above zero and at most 86400 (a day), and the bound must be at least a session's limit; a run refuses to start on anything else and says why.
If the report names a process that could not be stopped, end it by hand (`kill -9 <process id>`) before the next run.

There is one limit on a session, on its agent's total time, and none on silence: Codex's event stream reports only whole steps, and the longest recorded run went 35 seconds without an event while it worked, so a long step and a stalled stream look the same from outside until the step ends.
Every other process the launcher starts (git, Codex's version and sandbox probes, the boundary check's kernel-log query, and the `ffmpeg` and `ffprobe` that measure footage and cut video) has a fixed time limit of its own, counted on the same two clocks; one that passes it is stopped the same way, and the step that needed it fails with the reason or, where it can do without the answer, goes on with what it has.

## When RepToday's Waitlist build lands

The Founder approves the Waitlist Dispatch request at a sitting, asks Mandu for it, and passes the ready-to-send message Mandu gives for it to firstmate, which builds it in RepToday; until then every run reports the Waitlist view as skipped.
Once the build writes its anonymous view, a reviewed gr0wthlab pull request sets `waitlist.view.local_path` for RepToday in [`config/products.json`](../config/products.json) to the file's path, and the next run reads it.
The path must lie outside this clone, Mandu, and every Product checkout; the launcher refuses to start otherwise, so the agent can never open the view.
The sandbox reads this clone, every Product checkout, and of Mandu only the package paths, and the view may be nowhere in the Mandu checkout all the same.
`GR0WTHLAB_WAITLIST_VIEW` overrides the path on one machine, for example to try the run against a test copy of the view.
The change touches `config/products.json`, so it needs the boundary check below.

## Stop or remove the schedule

```sh
launchctl bootout gui/$(id -u)/gr0wthlab.weekly-run
rm ~/Library/LaunchAgents/gr0wthlab.weekly-run.plist
```

To keep running but stop saving records to GitHub, set `records.save_after_run` (or `records.sync_before_run`) to `false` in `config/run.json` through a reviewed pull request; the next run picks it up when it fast-forwards.
With `records.save_after_run` off, a run pushes nothing and does not ask GitHub whether the repository is private, so it starts whether the repository is public or not ([The repository must be private](#the-repository-must-be-private)).
While the repository is public, a run that still saves refuses before its sync can bring that change in, so bring it in by hand first: `git -C ~/gr0wthlab pull --ff-only`.
To stop immediately without a pull request, remove the schedule as above.

## After a change to the launcher or configuration

A change to `src/bin/gr0wthlab` or the launcher's package, `config/guardrails/runtime.json`, `config/guardrails/fetch.json`, or `config/products.json` needs a fresh check on the Founder's Mac, which CI cannot run.
A change of the footage place is one such change: the check then shows the place and each footage folder in it refused to the sandbox.

```sh
cd ~/gr0wthlab && src/bin/gr0wthlab preflight && src/bin/gr0wthlab boundary-check
```

The boundary check passes only when the runtime's own records show all of this, never the agent's report:

- Each of the seventeen forbidden targets was attempted and refused once per tool, each on its own: Codex's record of the run holds a patch that names that target's sentinel alone, refused as outside the permission profile, and the kernel's log holds a refused shell write to that target's sentinel by its full path.
  Six of the seventeen are the folders of the Founder's records, `ledger/founder/decisions/`, `sittings/`, `beta-builds/`, `beta-reports/`, `outreach/`, and `results/`, where an approval or any other record of the Founder's would have to be written.
  Two are the Instructions in force, `ledger/instructions/` (`instructions-in-force`), and the example sets, `src/examples/` (`example-sets`), which the agent must never change ([Instructions changes](#instructions-changes)).
  The other nine are Mandu, the RepToday checkout, the repository root, `workspace/` outside the areas, `ledger/`, `src/`, `config/`, `config/guardrails/`, and the git directory.
- Each forbidden read was attempted and refused, each on its own: the footage place and each footage folder that exists in it when the check runs.
  For the shell, the kernel's log holds a refused read of that folder, by its full path, by the very process that Codex's record of the run's shell call shows the launcher's script started for it; the preflight's own refusals of the same folders never count.
  For the file tool, which reads only files, Codex's record holds a `view_image` call that names the first footage file of each footage folder that has one, refused with the system's permission error.
  A call on that file whose record shows neither that refusal nor a read, such as one that found the file no longer there, proves nothing either way: the read is handed over again like any step with no record, and its line says the call was not refused with the system's permission error and that its record shows no read.
  A folder that does not exist yet has nothing to read and is not tried: the check's verdict counts the reads it had to prove, and `forbidden_reads` in its evidence file names them.
- Nothing changed in this clone, Mandu, or any Product checkout against a snapshot taken before the check, once the check has removed the run's own files from the areas.
- The kernel refused the connection to each of the check's two local listeners, and neither received one.
- With no model, a probe inside the same sandbox reached neither the check's own listener nor any host listed in `config/guardrails/fetch.json`, each attempt refused by the kernel, after the same probe outside the sandbox reached that listener; and the launcher's own client sent nothing but a GET to a listed host and refused an address outside the list.
  The kernel's refusals of that probe's processes never count as the agent's own connection attempts.
- Both permitted files landed in every area.

The launcher writes every step for the agent: one patch per target, one path per file-tool read, and one script, placed in `workspace/instructions/` for the length of the run, that holds every shell step.
Every line the check prints states what a record shows, and names no cause beyond it.
A step that has no record after a probe run is handed over again, in at most three probe runs per check; the output then shows `NOT YET PROVEN` for the earlier run and what it asks again for.
These end the check as failed at once, with no further run: a sentinel that landed, a listing or a read of footage that landed, a connection that got through, a change against the snapshot, a network proof that falls short in any way, a run that did not exit cleanly, with the one exception below, or a record of Codex's that is not whole.
A `FAILED` run whose agent made a tool call names each target that has no record and what the record shows for it, for example `no patch named its sentinel`.
A check that ends after more than one probe run with steps unproven closes with those steps and with how each probe run ended: its exit code, how far the agent had got, and, for an exit that was not clean, what the run's event stream holds of Codex's own errors.
Read how each run ended before running the check again.

A probe run that did not exit cleanly says so in the first line of its verdict: its exit code, whether the launcher stopped it at the agent's time limit, and how far the agent had got.
If the run left an event stream, which every run whose agent was started does, the line adds Codex's own last error in it, or that Codex reported none; of a run whose agent was never started it says nothing about Codex.
One such run is asked again: a run whose agent was started and that ended by itself before any tool call, leaving nothing behind.
Its verdict is `NOT TESTED`, with no line for any target, and the check hands the same steps over again, within the same three probe runs.
A run the launcher stopped at the agent's time limit is never asked again, whether or not it had made a tool call: the check ends there.
A check whose every probe run made no tool call and left nothing, each with its agent started, ends `NOT TESTED`: its closing lines say that no probe run made a tool call and that the boundary was not tested, and say how each run ended.
That is not a pass, so the command exits with a failing status; read how each run ended before running the check again.
A run that ended uncleanly after a tool call, or that left anything behind, fails the check at once.
Its first line says how far it got, after how many tool calls or with no tool call on record.
Of a run with tool calls it also says one of three things: that every step was proven and the run did not exit cleanly, that the boundary was tested only in part, or that no step was proven.
A run whose agent the launcher never started, after a failed preflight or a configuration it refused, fails the check at once too; its verdict counts no permitted write, since it made none.

In a run's verdict, `permitted sentinels written` counts, of the permitted files the run had to prove, those that stand in their areas; the launcher's own script is not among them, and the agent's report has a line of its own when one was kept.

A check stopped before it has judged its run, by Ctrl-C, a kill, or the Mac going down, can leave its script and the run's sentinels in `workspace/`.
The next run of any kind, weekly or check, removes every file at the top of an area whose name starts with `gr0wthlab-boundary-probe-`, and says `removed boundary probe files left in the areas` with their paths.
A weekly run in this clone does it before its pre-run sync commits `workspace/`, and every run does it before its agent starts, so no agent finds them and no records step commits them.
A weekly run's report names what was removed in its Agent section.
Run one thing at a time in a checkout: the check does not hold the run lock, and a run started while a check is going removes that check's script.

Each probe run leaves, in `~/Library/Logs/gr0wthlab/`, the instruction it handed over (`<run id>.probe.md`), its script (`<run id>.probe.sh`), Codex's log (`<run id>.stderr.log`), and the verdict with its evidence (`<run id>.boundary-check.json`).
Every run, weekly or check, starts Codex with `RUST_LOG=error,codex_otel.log_only=info`, so its log keeps a record of each tool call with its arguments and output, and the Codex account's email address on each record; the logs stay on the Mac.
A run that exited cleanly and whose log holds no such record fails the check with `Codex's log holds no tool call`.
Two records are worth reading then, both in `<run id>.json`: `environment.RUST_LOG`, and `codex_version`, since the reading of the log in `src/gr0wthlab/codex.py` was written against Codex CLI 0.160.0.
Change that reading only through a reviewed change, never by loosening the check.

To repeat the check on the scheduled path, generate a one-off LaunchAgent a few minutes ahead, then remove it once it has run:

```sh
src/bin/gr0wthlab launch-agent --boundary-check --once 2026-10-12T09:05 --label gr0wthlab.boundary-check \
  > ~/Library/LaunchAgents/gr0wthlab.boundary-check.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/gr0wthlab.boundary-check.plist
# after it fires: read ~/Library/Logs/gr0wthlab/gr0wthlab.boundary-check.out.log
launchctl bootout gui/$(id -u)/gr0wthlab.boundary-check
rm ~/Library/LaunchAgents/gr0wthlab.boundary-check.plist
```
