# ledger

The launcher's own records.
The launcher writes them outside the sandbox; a run can read them and can never write them, so nothing the agent does can change them (Guardrail G1).
Each run's records step commits this folder to `main` together with `workspace/` (US-ME17).

- `review-queue/queue.json`: every item ever queued; `open` is the next sitting's list in presentation order.
  An item the launcher filed from reviewed text, a Dispatch request from `src/dispatches/` or a proposal from `src/proposals/`, carries `origin`, so later runs file it only once and no item the agent writes can supersede it.
  No item the agent writes is a post or a message, and none can supersede one: the launcher queues each of those kinds only from a Draft that passed its checks, and sets aside any written to `incoming/`.
  It replaces a post only when its Draft or its slot changes, and a Beta Cohort invitation or a Waitlist ask, which carry `beta`, only when its recruiting Draft, its batch, or its gap changes.
- `review-queue/items/<id>.md`: each queued item, under an identifier that never changes.
- `review-queue/set-aside/<run id>/`: what the launcher refused to queue that run, kept for the record and named in that run's notice.
- `evidence/package-snapshots/<run id>.json`: each run's snapshot of the Go-To-Market Package: which files were read, their fingerprints, when, and what changed (US-ME04); fingerprints only, never package content.
- `evidence/decisions/<item id>.json`: each Founder decision taken in from Mandu, with its reason or note, its Mandu source, and the newer item that had already superseded the decided one, if any (US-ME07).
- `evidence/sittings/<date>.json`: how long each sitting took, from Mandu, and the run that first took it in.
- `evidence/waitlist/<run id>.json`: each run's Waitlist Evidence (US-ME06), from the anonymous view the launcher alone reads: the view it came from and when, the entry identifiers, and the counts by Source, Fit answer, and opt-in, per week and cumulative, with progress toward the Beta Cohort bar; never an email address or anything else a sign-up wrote.
  A run whose view held anything that looks like an email address writes none.
- `evidence/post-drafts/<run id>.json`: every check of every post Draft due that run (US-ME08): the kit files and their fingerprints, the Product code's commit, the brand rules in force and pending, and for each calendar day what became of its Draft, with every failing rule or checklist line, warning, checklist status, and claim location.
- `evidence/beta-recruiting/<run id>.json`: each run's Evidence of Beta Cohort recruiting (US-ME15), written only once the Founder's Beta Build record exists in Mandu: that record's dates and its source, the Founder's counts, the cohort's size, the selection rule and the batch size, the run's batch by entry identifier, who is invited and who is offered as the run leaves the Review Queue, the size of the gap when the pool cannot reach the cohort's minimum, and every check of every recruiting Draft; entry identifiers and counts only.
- `evidence/beta-recruiting/reports/<Product>-<date>.json`: each Beta Cohort report the Founder made through Mandu: the three counts, invitations sent, accepted, and sessions booked, when the Founder reported them, its source, and when it was taken in, and nothing else the record held.
  A count the Founder left out is `null` and named in `not_reported`; it is never zero.
- `run-reports/<run id>.md`: the run report: every source checked with its result, every failure and skip with its reason, whether a scheduled run started late, and the run's approximate cost; its first line counts what the run checked and acted on (`checked=N acted=N note=...`).
- `run-reports/<run id>.brief.md`: the facts the launcher gave the agent before it started.
- `run-reports/<run id>.post-plan.json`: what the launcher fixed for that run's post Drafts, once, after it took in the Founder's decisions and before the agent started: the days due and skipped, each day's open, approved, and rejected posts, whether the Waitlist is live, the commit the Product's code is read at, or why it could not be read, and the fingerprint of each kit file read from Mandu.
  `check-drafts --run <run id>`, the command the brief gives the agent, reads it instead of working the standing out again, since `queue.json` is saved only when the run ends; without a readable record it checks no Draft and says so.
  It checks every claim at the recorded commit, whatever has landed on the Product's branch since, and names each kit file that is no longer as the launcher read it, since it can check only against what Mandu holds now.
  A day due that the calendar no longer holds is named too, and its Draft is not checked.
- `run-reports/<run id>.beta-plan.json`: which recruiting Drafts that run asked the agent for, with the fingerprints of the Drafts the Founder already rejected, written once the Founder's gate is recorded; `check-beta-drafts --run <run id>` reads it, and it never names a Waitlist entry.
- `run-reports/state/<workflow>.json`: each workflow's run state - Review Queue items decided, those carried over with the sitting they were left undecided at, and the Mandu records already reported as unusable; Listening threads already read; outreach targets and their follow-up waits; the Waitlist entries an invitation batch holds, invited once the Founder approved the batch or offered while it is open - by identifier and hash only, never a name, address, or URL.
  The launcher checks it every run against the Review Queue and Mandu's decision records, which win any disagreement.
  Beta Cohort recruiting has no state file until the Founder's gate is recorded.
- `notes/<id>.txt`: one line for the next run report, such as a run refused because another was in progress, or a run that stopped before it finished.
- `run.lock`: the lock one run holds from start to finish; it is never committed.

The format of the Review Queue, and what Mandu writes back: [the Mandu exchange](../docs/mandu-exchange.md).
