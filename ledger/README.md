# ledger

The launcher's own records.
The launcher writes them outside the sandbox; a run can read them and can never write them, so nothing the agent does can change them (Guardrail G1).
Each run's records step commits this folder to `main` together with `workspace/` (US-ME17).

- `review-queue/queue.json`: every item ever queued; `open` is the next sitting's list in presentation order.
  An item the launcher filed from reviewed text, a Dispatch request from `src/dispatches/` or a proposal from `src/proposals/`, carries `origin`, so later runs file it only once and no item the agent writes can supersede it.
  No item the agent writes can supersede a post either: the launcher queues a post from its Draft and replaces it only when that Draft, its slot, or its video changes.
  The filming plan carries `origin` too, with a fingerprint of what must be filmed, so it is filed once per window and replaced only when the kit changes that.
- `review-queue/items/<id>.md`: each queued item, under an identifier that never changes.
- `review-queue/set-aside/<run id>/`: what the launcher refused to queue that run, kept for the record and named in that run's notice.
- `evidence/package-snapshots/<run id>.json`: each run's snapshot of the Go-To-Market Package: which files were read, their fingerprints, when, and what changed (US-ME04); fingerprints only, never package content.
- `evidence/decisions/<item id>.json`: each Founder decision taken in from Mandu, with its reason or note, its Mandu source, and the newer item that had already superseded the decided one, if any (US-ME07).
- `evidence/sittings/<date>.json`: how long each sitting took, from Mandu, and the run that first took it in.
- `evidence/waitlist/<run id>.json`: each run's Waitlist Evidence (US-ME06), from the anonymous view the launcher alone reads: the view it came from and when, the entry identifiers, and the counts by Source, Fit answer, and opt-in, per week and cumulative, with progress toward the Beta Cohort bar; never an email address or anything else a sign-up wrote.
  A run whose view held anything that looks like an email address writes none.
- `evidence/post-drafts/<run id>.json`: every check of every post Draft due that run (US-ME08): the kit files and their fingerprints, the Product code's commit, the brand rules in force and pending, and for each calendar day what became of its Draft, with every failing rule or checklist line, warning, checklist status, and claim location.
- `evidence/filming/<run id>.json`: each run's account of filming (US-ME09): the filming plan's jobs and sittings, every footage file listed with its fingerprint and measured facts, the video tooling found, and for each calendar day due what became of its edit record, with every failing rule.
- `evidence/filming/assets/<name>.json`: one record per finished video, written once: its path, SHA-256, and measured facts, the edit record it was cut by, the text drawn over it, each source file's name and fingerprint, and the tooling, so it can be rebuilt from the footage with `rebuild-asset`.
- `assets/window-<n>/day-<nn>-<recipe>.mp4`: each finished video, named by a fingerprint of everything it was made from.
  The folder is never committed: `.gitignore` leaves it out, and the records step refuses any file under it.
- `run-reports/<run id>.md`: the run report: every source checked with its result, every failure and skip with its reason, whether a scheduled run started late, and the run's approximate cost; its first line counts what the run checked and acted on (`checked=N acted=N note=...`).
- `run-reports/<run id>.brief.md`: the facts the launcher gave the agent before it started.
- `run-reports/<run id>.post-plan.json`: what the launcher fixed for that run's post Drafts, once, after it took in the Founder's decisions and before the agent started: the days due and skipped, each day's open, approved, and rejected posts, whether the Waitlist is live, the commit the Product's code is read at, or why it could not be read, and the fingerprint of each kit file read from Mandu.
  `check-drafts --run <run id>`, the command the brief gives the agent, reads it instead of working the standing out again, since `queue.json` is saved only when the run ends; without a readable record it checks no Draft and says so.
  It checks every claim at the recorded commit, whatever has landed on the Product's branch since, and names each kit file that is no longer as the launcher read it, since it can check only against what Mandu holds now.
  A day due that the calendar no longer holds is named too, and its Draft is not checked.
- `run-reports/<run id>.filming.json`: what the launcher fixed for that run's edit records before the agent started: the footage it listed and measured, each due day's shot list and whether an edit can be cut, and where each day's post stands.
  `check-edits --run <run id>`, the command the brief gives the agent, reads it, since the footage place is outside what the sandbox reads.
- `run-reports/state/<workflow>.json`: each workflow's run state - Review Queue items decided, those carried over with the sitting they were left undecided at, and the Mandu records already reported as unusable; Listening threads already read; outreach targets and their follow-up waits - by identifier and hash only, never a name, address, or URL.
  The launcher checks it every run against the Review Queue and Mandu's decision records, which win any disagreement.
- `notes/<id>.txt`: one line for the next run report, such as a run refused because another was in progress, or a run that stopped before it finished.
- `run.lock`: the lock one run holds from start to finish; it is never committed.

The format of the Review Queue, and what Mandu writes back: [the Mandu exchange](../docs/mandu-exchange.md).
