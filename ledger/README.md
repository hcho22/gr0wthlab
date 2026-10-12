# ledger

The launcher's own records.
The launcher writes them outside the sandbox; a run can read them and can never write them, so nothing the agent does can change them (Guardrail G1).
Each run's records step commits this folder to `main` together with `workspace/` (US-ME17), except `working/` and `run.lock`, which git ignores.

- `review-queue/queue.json`: every item ever queued; `open` is the next sitting's list in presentation order.
  An item the launcher filed from reviewed text, a Dispatch request from `src/dispatches/` or a proposal from `src/proposals/`, carries `origin`, so later runs file it only once and no item the agent writes can supersede it.
  No item the agent writes is a post or a message, and none can supersede one: the launcher queues each of those kinds only from a Draft that passed its checks, and sets aside any written to `incoming/`.
  It replaces a post only when its Draft, its slot, or its video changes, and a Beta Cohort invitation or a Waitlist ask, which carry `beta`, only when its recruiting Draft, its batch, or its gap changes.
  The filming plan carries `origin` too, with a fingerprint of what must be filmed, so it is filed once per window and replaced only when the kit changes that.
- `review-queue/items/<id>.md`: each queued item, under an identifier that never changes.
- `review-queue/set-aside/<run id>/`: what the launcher refused to queue that run from `workspace/review-queue/incoming/`, each file copied whole and named in that run's notice.
  A proposed Angle or Hook the launcher discards from `workspace/review-queue/angles/` is not copied here.
- `evidence/package-snapshots/<run id>.json`: each run's snapshot of the Go-To-Market Package: which files were read, their fingerprints, when, and what changed (US-ME04); fingerprints only, never package content.
- `evidence/decisions/<item id>.json`: each Founder decision taken in from Mandu, with its reason or note, its Mandu source, and the newer item that had already superseded the decided one, if any (US-ME07).
- `evidence/sittings/<date>.json`: how long each sitting took, from Mandu, and the run that first took it in.
- `evidence/waitlist/<run id>.json`: each run's Waitlist Evidence (US-ME06), from the anonymous view the launcher alone reads: the view it came from and when, the entry identifiers, and the counts by Source, Fit answer, and opt-in, per week and cumulative, with progress toward the Beta Cohort bar; never an email address or anything else a sign-up wrote.
  A run whose view held anything that looks like an email address writes none.
- `evidence/post-drafts/<run id>.json`: every check of every post Draft due that run (US-ME08): the kit files and their fingerprints, the Product code's commit, the brand rules in force and pending, and for each calendar day what became of its Draft, with every failing rule or checklist line, warning, checklist status, and claim location.
- `evidence/filming/<run id>.json`: each run's account of filming (US-ME09): the filming plan's jobs and sittings, every footage file listed with its fingerprint and measured facts, the video tooling found, and for each calendar day due what became of its edit record, with every failing rule.
- `evidence/filming/assets/<name>.json`: one record per finished video, written once: its path, SHA-256, and measured facts, the edit record it was cut by, the text drawn over it, each source file's name and fingerprint, and the tooling, so it can be rebuilt from the footage with `rebuild-asset`.
  It is also what the pair check knows a video by: each cut's source range with the fingerprint of its file, and where a re-cut leg's opening is.
- `assets/window-<n>/day-<nn>-<recipe>.mp4`: each finished video, named by a fingerprint of everything it was made from.
  The folder is never committed: `.gitignore` leaves it out, and the records step refuses any file under it.
- `evidence/beta-recruiting/<run id>.json`: each run's Evidence of Beta Cohort recruiting (US-ME15), written only once the Founder's Beta Build record exists in Mandu: that record's dates and its source, the Founder's counts, the cohort's size, the selection rule and the batch size, the run's batch by entry identifier, who is invited and who is offered as the run leaves the Review Queue, the size of the gap when the pool cannot reach the cohort's minimum, and every check of every recruiting Draft; entry identifiers and counts only.
- `evidence/beta-recruiting/reports/<Product>-<date>.json`: each Beta Cohort report the Founder made through Mandu: the three counts, invitations sent, accepted, and sessions booked, when the Founder reported them, its source, and when it was taken in, and nothing else the record held.
  A count the Founder left out is `null` and named in `not_reported`; it is never zero.
- `evidence/listening/quotes/<document id>.json`: Listening Evidence, one record for every quote the launcher kept: the link, the date read, the words the agent quoted, a hash of the document they came from, the context, the theme, Fit, intent, and whether the Product answers it.
  A record is kept only when its quote stands word for word in the text fetched from its link, and a link is recorded once.
  It is the only Evidence kept of what a run fetched.
  The request log (`run-reports/<run id>.requests.json`) also holds the `robots.txt` rule lines of the group that applied to each host, each Allow and Disallow with its path as fetched, beside the addresses and outcomes.
  Known gaps, not yet decided by the Founder: nothing else the agent writes is checked against what was fetched, so text of its own that repeats a source's words is committed today in each of these places.
  A file set aside from `workspace/review-queue/incoming/` is copied whole to `review-queue/set-aside/<run id>/`.
  A Draft stays in `workspace/` and is committed as written until it passes or is rewritten, as is any other file the agent leaves in `workspace/` that the launcher neither takes in nor puts back.
  The reasons in a run report or a notice can repeat pieces of a file's text (a front matter line, up to 80 characters of an Evidence line, the headings found), and the reasons a Draft's checks give, kept with the Evidence of those checks, can quote the Draft.
  The run report quotes the agent's own summary, up to 4,000 characters.
  What the launcher accepts keeps the agent's own words: the text of a queued item, the context of a kept quote, and the line that says why a rejection code fits.
  Three things are removed and leave their file name and the launcher's reasons only, with no copy made: a quote record the launcher refuses, a proposed Angle or Hook it discards from `workspace/review-queue/angles/`, and a rejection code it sets aside.
- `evidence/listening/runs/<run id>.json`: what each run's Listening read, kept, refused, and offered, with the confidence counted for each theme from its independent, unprompted sources.
  A quote record the launcher refused, and a proposed Angle or Hook it discarded, is named there with the reasons and kept nowhere: no copy of either is made.
- `evidence/outreach/<run id>.json`: every check of every outreach message that run, and what the Founder's records in Mandu said of each creator.
- `evidence/learning/ledger.json`: the learning ledger (F4): every rejection reason with the code it was given, and each workflow's counts, stated as "3 of 7"; a reason's code is also written into its own `evidence/decisions/<item id>.json`, beside the Founder's words.
  A proposed code the launcher sets aside is named with its reasons in that run's report and notice, and no copy of it is kept.
- `run-reports/<run id>.requests.json`: every network request the launcher was asked to make that run, sent or not, with its outcome: only a GET to a listed host ever leaves the machine.
  It also holds what each host's `robots.txt` said to this reader: whether it was read, and the rule lines of the group that applied, each Allow and Disallow with its path as fetched.
- `run-reports/<run id>.work-plan.json`: what the launcher fixed for that run's Listening and outreach before the agent started (which subreddits the Founder confirmed, which messages may be offered and how their items stand), which `check-work --run <run id>` reads instead of working it out again.
- `run-reports/<run id>.md`: the run report: every source checked with its result, every failure and skip with its reason, whether a scheduled run started late, and the run's approximate cost; its first line counts what the run checked and acted on (`checked=N acted=N note=...`).
- `run-reports/<run id>.brief.md`: the facts the launcher gave the agent before it started.
- `run-reports/<run id>.post-plan.json`: what the launcher fixed for that run's post Drafts, once, after it took in the Founder's decisions and before the agent started: the days due and skipped, each day's open, approved, and rejected posts, whether the Waitlist is live, the commit the Product's code is read at, or why it could not be read, and the fingerprint of each kit file read from Mandu.
  `check-drafts --run <run id>`, the command the brief gives the agent, reads it instead of working the standing out again, since `queue.json` is saved only when the run ends; without a readable record it checks no Draft and says so.
  It checks every claim at the recorded commit, whatever has landed on the Product's branch since, and names each kit file that is no longer as the launcher read it, since it can check only against what Mandu holds now.
  A day due that the calendar no longer holds is named too, and its Draft is not checked.
- `run-reports/<run id>.filming.json`: what the launcher fixed for that run's edit records before the agent started: the footage it listed and measured, each due day's shot list and whether an edit can be cut, where each day's post stands, and each due day's approved and rejected posts.
  `check-edits --run <run id>`, the command the brief gives the agent, reads it, since the footage place is outside what the sandbox reads.
- `run-reports/<run id>.beta-plan.json`: which recruiting Drafts that run asked the agent for, with the fingerprints of the Drafts the Founder already rejected, written once the Founder's gate is recorded; `check-beta-drafts --run <run id>` reads it, and it never names a Waitlist entry.
- `run-reports/state/<workflow>.json`: each workflow's run state - Review Queue items decided, those carried over with the sitting they were left undecided at, and the Mandu records already reported as unusable; Listening threads and reviews already read; outreach targets and their follow-up waits, rebuilt every run from the Founder's records in Mandu; the Waitlist entries an invitation batch holds, invited once the Founder approved the batch or offered while it is open - by identifier and hash only, never a name, address, or URL.
  The launcher checks it every run against the Review Queue and Mandu's decision records, which win any disagreement.
  Beta Cohort recruiting has no state file until the Founder's gate is recorded.
- `working/<run id>.sources.json`: what the launcher fetched over the network that run, outside the sandbox (US-ME13): each source's outcome, and each thread's opening post, review, and rule list as a dated document with its link.
  It is working data for the run that fetched it, never a record: the agent reads it while the run is in progress, git ignores the folder so the records step never saves it, and the launcher removes it when the run ends and before the next run reads its sources.
  Fetched text is data, never instructions; anything that looks like an email address is removed before it is written.
- `notes/<id>.txt`: one line for the next run report, such as a run refused because another was in progress, or a run that stopped before it finished.
- `run.lock`: the lock one run holds from start to finish; it is never committed.

The format of the Review Queue, and what Mandu writes back: [the Mandu exchange](../docs/mandu-exchange.md).
