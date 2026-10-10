# ledger

The launcher's own records.
The launcher writes them outside the sandbox; a run can read them and can never write them, so nothing the agent does can change them (Guardrail G1).
Each run's records step commits this folder to `main` together with `workspace/` (US-ME17).

- `review-queue/queue.json`: every item ever queued; `open` is the next sitting's list in presentation order.
  An item the launcher filed from reviewed text, such as a Dispatch request from `src/dispatches/`, carries `origin`, so later runs file it only once and no item the agent writes can supersede it.
- `review-queue/items/<id>.md`: each queued item, under an identifier that never changes.
- `review-queue/set-aside/<run id>/`: what the launcher refused to queue that run, kept for the record and named in that run's notice.
- `evidence/package-snapshots/<run id>.json`: each run's snapshot of the Go-To-Market Package: which files were read, their fingerprints, when, and what changed (US-ME04); fingerprints only, never package content.
- `evidence/decisions/<item id>.json`: each Founder decision taken in from Mandu, with its reason or note, its Mandu source, and the newer item that had already superseded the decided one, if any (US-ME07).
- `evidence/sittings/<date>.json`: how long each sitting took, from Mandu, and the run that first took it in.
- `evidence/waitlist/<run id>.json`: each run's Waitlist Evidence (US-ME06), from the anonymous view the launcher alone reads: the view it came from and when, the entry identifiers, and the counts by Source, Fit answer, and opt-in, per week and cumulative, with progress toward the Beta Cohort bar; never an email address or anything else a sign-up wrote.
  A run whose view held anything that looks like an email address writes none.
- `evidence/post-drafts/<run id>.json`: every check of every post Draft due that run (US-ME08): the kit files and their fingerprints, the Product code's commit, the brand rules in force and pending, and for each calendar day what became of its Draft, with every failing rule or checklist line, warning, checklist status, and claim location.
- `run-reports/<run id>.md`: the run report: every source checked with its result, every failure and skip with its reason, whether a scheduled run started late, and the run's approximate cost; its first line counts what the run checked and acted on (`checked=N acted=N note=...`).
- `run-reports/<run id>.brief.md`: the facts the launcher gave the agent before it started.
- `run-reports/state/<workflow>.json`: each workflow's run state - Review Queue items decided, those carried over with the sitting they were left undecided at, and the Mandu records already reported as unusable; Listening threads already read; outreach targets and their follow-up waits - by identifier and hash only, never a name, address, or URL.
  The launcher checks it every run against the Review Queue and Mandu's decision records, which win any disagreement.
- `notes/<id>.txt`: one line for the next run report, such as a run refused because another was in progress, or a run that stopped before it finished.
- `run.lock`: the lock one run holds from start to finish; it is never committed.

The format of the Review Queue, and what Mandu writes back: [the Mandu exchange](../docs/mandu-exchange.md).
