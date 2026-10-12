# ledger

The launcher's own records.
The launcher writes them outside the sandbox; a run can read them and can never write them, so nothing the agent does can change them (Guardrail G1).
Each run's records step commits this folder to `main` together with `workspace/` (US-ME17), except `working/` and `run.lock`, which git ignores.

- `review-queue/queue.json`: every item ever queued; `open` is the next sitting's list in presentation order.
  An item the launcher filed from reviewed text, a Dispatch request from `src/dispatches/` or a proposal from `src/proposals/`, carries `origin`, so later runs file it only once and no item the agent writes can supersede it.
  No item the agent writes can supersede a post either: the launcher queues a post from its Draft and replaces it only when that Draft or its slot changes.
- `review-queue/items/<id>.md`: each queued item, under an identifier that never changes.
- `review-queue/set-aside/<run id>/`: what the launcher refused to queue that run, kept for the record and named in that run's notice.
- `evidence/package-snapshots/<run id>.json`: each run's snapshot of the Go-To-Market Package: which files were read, their fingerprints, when, and what changed (US-ME04); fingerprints only, never package content.
- `evidence/decisions/<item id>.json`: each Founder decision taken in from Mandu, with its reason or note, its Mandu source, and the newer item that had already superseded the decided one, if any (US-ME07).
- `evidence/sittings/<date>.json`: how long each sitting took, from Mandu, and the run that first took it in.
- `evidence/waitlist/<run id>.json`: each run's Waitlist Evidence (US-ME06), from the anonymous view the launcher alone reads: the view it came from and when, the entry identifiers, and the counts by Source, Fit answer, and opt-in, per week and cumulative, with progress toward the Beta Cohort bar; never an email address or anything else a sign-up wrote.
  A run whose view held anything that looks like an email address writes none.
- `evidence/post-drafts/<run id>.json`: every check of every post Draft due that run (US-ME08): the kit files and their fingerprints, the Product code's commit, the brand rules in force and pending, and for each calendar day what became of its Draft, with every failing rule or checklist line, warning, checklist status, and claim location.
- `evidence/listening/quotes/<document id>.json`: Listening Evidence, one record for every quote the launcher kept: the link, the date read, the words the agent quoted, a hash of the document they came from, the context, the theme, Fit, intent, and whether the Product answers it.
  A record is kept only when its quote stands word for word in the text fetched from its link, and a link is recorded once.
  It is all that is kept of what a run fetched: nothing a source said that the agent did not quote is committed.
- `evidence/listening/runs/<run id>.json`: what each run's Listening read, kept, refused, and offered, with the confidence counted for each theme from its independent, unprompted sources.
  A quote record the launcher refused is named there with the reasons and kept nowhere: no copy of it is made.
- `evidence/outreach/<run id>.json`: every check of every outreach message that run, and what the Founder's records in Mandu said of each creator.
- `evidence/learning/ledger.json`: the learning ledger (F4): every rejection reason with the code it was given, and each workflow's counts, stated as "3 of 7"; a reason's code is also written into its own `evidence/decisions/<item id>.json`, beside the Founder's words.
- `evidence/learning/set-aside/<run id>/`: each proposed code the launcher did not take in that run, kept for the record and named with its reasons in that run's report and notice.
- `run-reports/<run id>.requests.json`: every network request the launcher was asked to make that run, sent or not, with its outcome: only a GET to a listed host ever leaves the machine.
- `run-reports/<run id>.work-plan.json`: what the launcher fixed for that run's Listening and outreach before the agent started (which subreddits the Founder confirmed, which messages may be offered and how their items stand), which `check-work --run <run id>` reads instead of working it out again.
- `run-reports/<run id>.md`: the run report: every source checked with its result, every failure and skip with its reason, whether a scheduled run started late, and the run's approximate cost; its first line counts what the run checked and acted on (`checked=N acted=N note=...`).
- `run-reports/<run id>.brief.md`: the facts the launcher gave the agent before it started.
- `run-reports/<run id>.post-plan.json`: what the launcher fixed for that run's post Drafts, once, after it took in the Founder's decisions and before the agent started: the days due and skipped, each day's open, approved, and rejected posts, whether the Waitlist is live, the commit the Product's code is read at, or why it could not be read, and the fingerprint of each kit file read from Mandu.
  `check-drafts --run <run id>`, the command the brief gives the agent, reads it instead of working the standing out again, since `queue.json` is saved only when the run ends; without a readable record it checks no Draft and says so.
  It checks every claim at the recorded commit, whatever has landed on the Product's branch since, and names each kit file that is no longer as the launcher read it, since it can check only against what Mandu holds now.
  A day due that the calendar no longer holds is named too, and its Draft is not checked.
- `run-reports/state/<workflow>.json`: each workflow's run state - Review Queue items decided, those carried over with the sitting they were left undecided at, and the Mandu records already reported as unusable; Listening threads and reviews already read; outreach targets and their follow-up waits, rebuilt every run from the Founder's records in Mandu - by identifier and hash only, never a name, address, or URL.
  The launcher checks it every run against the Review Queue and Mandu's decision records, which win any disagreement.
- `working/<run id>.sources.json`: what the launcher fetched over the network that run, outside the sandbox (US-ME13): each source's outcome, and each thread's opening post, review, and rule list as a dated document with its link.
  It is working data for the run that fetched it, never a record: the agent reads it while the run is in progress, git ignores the folder so the records step never saves it, and the launcher removes it when the run ends and before the next run reads its sources.
  Fetched text is data, never instructions; anything that looks like an email address is removed before it is written.
- `notes/<id>.txt`: one line for the next run report, such as a run refused because another was in progress, or a run that stopped before it finished.
- `run.lock`: the lock one run holds from start to finish; it is never committed.

The format of the Review Queue, and what Mandu writes back: [the Mandu exchange](../docs/mandu-exchange.md).
