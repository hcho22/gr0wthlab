# Mandu exchange, version 4

How gr0wthlab (the Marketing Engineer) and Mandu pass the Review Queue and the Founder's decisions between them.
Mandu's own agent builds Mandu's side from this page.
Later stories extend the exchange, each with a version bump: the TikTok export (US-ME11), the Beta Build approval (US-ME15), and the US-ME18 confirmation.
Each side writes only its own repository and only reads the other's: gr0wthlab writes items in gr0wthlab, and Mandu writes decisions in Mandu.

## Where things are

| What | Written by | Path on the Founder's Mac |
| --- | --- | --- |
| The Review Queue | gr0wthlab | `~/gr0wthlab/ledger/review-queue/queue.json` |
| Each item | gr0wthlab | `~/gr0wthlab/ledger/review-queue/items/<id>.md` |
| Each run report | gr0wthlab | `~/gr0wthlab/ledger/run-reports/<run id>.md` |
| Each finished video | gr0wthlab | `~/gr0wthlab/ledger/assets/window-<n>/day-<nn>-<recipe>.mp4` |
| Decisions | Mandu | `~/Mandu/projects/gr0wthlab/exchange/decisions/<id>.json` |
| Sittings | Mandu | `~/Mandu/projects/gr0wthlab/exchange/sittings/<YYYY-MM-DD>.json` |

`~/gr0wthlab` is gr0wthlab's production clone; each run also pushes its outputs to `main` of `github.com/hcho22/gr0wthlab`, but Mandu reads the local files.
A finished video is only ever a local file: it never enters git, so it is not on GitHub, and gr0wthlab can rebuild it from the Founder's footage.
gr0wthlab finds Mandu's folder from `mandu.exchange` in gr0wthlab's `config/products.json`, and `GR0WTHLAB_EXCHANGE_DIR` overrides it on one machine.
To move the folder, change that configuration through a gr0wthlab pull request.

## The sitting

1. Read `queue.json`.
   If the time in its `next_run` has passed, tell the Founder first that the weekly run due then has not finished, so the queue and report are from an earlier run.
2. Show the summary at the top of the run report that `queue.json` names in `run_report`.
3. Present each entry of `open`, in the listed order, by showing its item file.
   Skip any entry that already has a decision record, unless gr0wthlab has asked Mandu to replace that record and it does not show the Founder's decision (see Decision records).
   For an entry with `"carried_over": true`, say it was carried over from the sitting on the date in `carried_over_from`.
4. The Founder approves an item, optionally with a one-line note, or rejects it with a one-line reason, or leaves it undecided.
   An undecided item needs nothing written; it returns, marked carried over, at the next sitting.
5. Write one decision record for each decided item as soon as it is decided.
6. At the end, write one sitting record with how many minutes the sitting took.
   Once gr0wthlab reads that record, it marks the items left undecided at the sitting as carried over.

Paths inside `queue.json` are relative to `~/gr0wthlab/ledger/`, the folder where gr0wthlab keeps its records.

## Items (gr0wthlab writes)

Each item is one Markdown file, named by its identifier, holding the front matter, a `#` title, and four `##` sections in this order, and nothing else:

```markdown
---
exchange: 4
id: 20261011-trademark-status-stale
kind: package-change-proposal
product: RepToday
---

# Approve package change: record the "Rep Today" name as cleared and reserved

## Proposal

The Draft or proposal itself.

## Touches

- `projects/RepToday/gtm/02-brand/brand-guidelines.md`

## Evidence

- What the Evidence says, with its source: `projects/RepToday/02-marketing-launch-checklist_260807.md` line 24

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
```

- `id` never changes once an item is queued: the date it was queued, then a short slug.
- The `#` title is the one-line ask.
- Touches says which posts, messages, or package files change; Evidence lists what the item rests on, each line with its source as a link or a path.
- `product` names the Product, when the item is about one.
- A post also has `window` and `day`: the number of the 14-day window and the calendar day it posts on, such as `window: 1` and `day: 3`.
  It has `slot`, its publishing time with its UTC offset, such as `2026-10-14T19:00-07:00`, once the Founder has set the window's first sitting, which its day 1 follows, and its posting slot; until then it has no slot, and its `## Draft` says so.
  A version 2 post always had a slot and no window or day.
- A post whose video is finished also has `asset`: the video file's path under `~/gr0wthlab/ledger/`, such as `asset: assets/window-1/day-03-0a1b2c3d4e5f.mp4`.
  Play that file for the Founder with the item, so the video and its copy are approved together.
  A post with no `asset` has no video yet: approving it approves its copy and beat plan only.
  When the run prepared filming for the post's Product, its `## Draft` says there is none yet and why, and the video comes back for approval in a later post item for the same day; a post of a Product that does not film, or of a run that could not prepare filming, says nothing of a video.
- `supersedes` names an earlier item this one replaces; the earlier one has left `open` and is never presented again.

| `kind` | The section after the title | Options |
| --- | --- | --- |
| `post` | `## Draft` | Approve or reject |
| `filming-plan` | `## Plan` | Approve or reject |
| `message` | `## Draft` | Approve or reject |
| `weekly-read-decision` | `## Recommendation` | Approve or reject |
| `dispatch-request` | `## Request` | Approve or reject |
| `package-change-proposal` | `## Proposal` | Approve or reject |
| `notice` | `## Notice` | Acknowledge (recorded as approve) or reject |

A notice is informational, such as a failed source or a change to the Marketing Engineer's Instructions; acknowledging it records `approve`.

A post's `## Draft` is everything the Founder needs to judge it in under a minute: the day, its Angle and pair leg, the primary platform, the slot or that none is set yet, and whether anything can be published yet (nothing can until the Waitlist is live); the frozen Hook; the video beat by beat; each platform's text, hashtags, and alt text; each behavioral claim its Draft lists with the code that supports it, and that only those were checked; and the checks it passed, with any warnings, its status against the pre-publication checklist, and the kit's own checklist lines for every asset, which are the Founder's to judge.
Its Evidence cites the calendar row, the Angle, its sourced pain, and its pre-registered signal and kill criterion in the package.
gr0wthlab queues a post only from a Draft that passed every check; a Draft that did not is never an item, and a notice names it with the rule that blocked it.
Once a post's video is finished, its `## Draft` also holds a Video file block: the file's path, length, measured shape, and SHA-256, the source range of the Founder's footage each part was cut from, and the checks it passed.
gr0wthlab offers a video only after measuring it as 9:16 at the expected resolution and checking its cuts against the shot list, and every frame of it is the Founder's footage with text drawn over it.
A post queued before its video existed is replaced by one that shows it; a day whose copy the Founder approved before its video existed is offered once more with the video, and that item says so.
The two legs of an A/B pair show videos gr0wthlab compared with each other: when one run cuts both legs anew, their videos are offered in that run together or not at all.

A filming plan asks the Founder to approve what a 14-day window must film before any of it is filmed: the sittings, and one shot list per asset, each stating what to record, on which device, in real time or not, and what may not be cut, in the words of the Angle's Format in the package.
gr0wthlab files it from the package, one item per window, and never asks it again once decided; a new plan replaces it, naming it in `supersedes`, only when the package changes what must be filmed.
gr0wthlab cuts a video only from footage of a shot list that a plan the Founder approved holds as the package has it now.
A shot list no approved plan holds has no video while its plan is undecided or rejected.
One that an earlier approved plan holds unchanged is still cut while the plan that replaced it is undecided or rejected, since the Founder already approved filming it.

A Dispatch request asks the Founder to approve a change to the Product it names in `product`, which firstmate then builds through that Product's normal reviewed path.
gr0wthlab never sends a Dispatch request anywhere itself.
Once the Founder approves one, Mandu hands that item, with the Founder's note if there is one, to firstmate under Mandu's existing Dispatch arrangement; a Dispatch request that is undecided, rejected, or superseded never reaches firstmate.

## The queue (gr0wthlab writes)

```json
{
  "exchange": 4,
  "updated_by_run": "20261011T230002Z-scheduled-1a2b",
  "updated_at": "2026-10-11T23:41:09+00:00",
  "run_report": "run-reports/20261011T230002Z-scheduled-1a2b.md",
  "next_run": "2026-10-18T16:00:00-07:00",
  "open": [
    {
      "id": "20261011-post-w1-day-03",
      "kind": "post",
      "ask": "Approve day 3 post: missed-day score record",
      "file": "review-queue/items/20261011-post-w1-day-03.md",
      "product": "RepToday",
      "window": 1,
      "day": 3,
      "published_at": "2026-10-11T23:40:57+00:00",
      "carried_over": false
    },
    {
      "id": "20261011-trademark-status-stale",
      "kind": "package-change-proposal",
      "ask": "Approve package change: record the \"Rep Today\" name as cleared and reserved",
      "file": "review-queue/items/20261011-trademark-status-stale.md",
      "product": "RepToday",
      "published_at": "2026-10-11T23:40:58+00:00",
      "carried_over": false
    }
  ],
  "closed": []
}
```

`next_run` is when the next weekly run is due on gr0wthlab's schedule, and every run that writes `queue.json` moves it forward.
Once it has passed, that run was missed, started late, is still running, or was refused because another run was in progress.
`open` is already in presentation order: posts by nearest slot first, then posts with no slot yet by window and day, then the filming plan, messages, Weekly Read decisions, Dispatch requests, package-change proposals, and notices, oldest first within each kind.
A post entry whose video is finished carries `asset`, the same path as in its item, and `asset_sha256`, the file's SHA-256.
`carried_over` is `true` for an item that was open at an earlier sitting and left undecided, and `carried_over_from` then gives the date of the first such sitting.
An item queued after the latest sitting is not carried over, whichever run queued it.
`closed` lists every decided or superseded item and is history only; never present it.
An open post whose Draft stops passing gr0wthlab's checks, for example after a package change, leaves `open` the same way, with `"withdrawn": true` and `superseded_by` naming the notice that says why; a decision on it is kept like any decision on a superseded item.
gr0wthlab may add fields; ignore any you do not use.

## Decision records (Mandu writes)

One file per decided item, `decisions/<id>.json`, written once and never edited or deleted, except to replace a record gr0wthlab could not use for an item still open (below):

```json
{
  "exchange": 4,
  "item": "20261011-trademark-status-stale",
  "decision": "reject",
  "reason": "Keep the legal line until counsel confirms the filing.",
  "note": null,
  "decided_at": "2026-10-11T19:42:00-07:00",
  "sitting": "2026-10-11"
}
```

- `item` equals the file name without `.json`.
- `decision` is `approve` or `reject`.
- A rejection needs `reason`: one line of at most 300 characters.
- An approval may carry `note`, one line of at most 300 characters, and has no `reason`.
- `decided_at` is the time of the decision with its UTC offset; `sitting` is the sitting's date and may be left out.

gr0wthlab matches each record to its item by `item`, keeps every reason and note as Evidence, and never asks about that item again.
A decision on an item that a newer item superseded before gr0wthlab read the decision, for example while a late run was still running during the sitting, is kept the same way.
Its Evidence also names the newer item, which stays open, and the Marketing Engineer sees the decision, with its reason or note, beside that newer item.

A decision record for an item still open that does not follow this format is not a decision, and gr0wthlab does not take it in.
gr0wthlab names it, with the exact problem, in the run report and in a notice at every run while the item stays open.
Mandu replaces it with a valid record in this format of the Founder's decision; if the record does not show that decision, Mandu presents the item again at the next sitting and writes the new decision in its place.
This is the only case where a record is rewritten.

gr0wthlab also cannot use a decision that names no queued item, a decision that differs from the one already taken for its item, or any other record that does not follow its format, such as a decision on an item no longer open or a sitting record.
It reports each such record to the Founder once, in one notice, and again only if the file changes.
Such a record changes nothing: a decision already taken stands, and Mandu does not need to rewrite or remove it.

## Sitting records (Mandu writes)

One file per sitting, `sittings/<YYYY-MM-DD>.json`, with the minutes the Founder spent, measured by Mandu or reported by the Founder:

```json
{"exchange": 4, "date": "2026-10-11", "minutes": 48, "note": null}
```

`minutes` is a whole number from 1 to 600, and `date` equals the file name.
Write it when the sitting ends: gr0wthlab counts an item as left undecided at the sitting when the item is still open, was queued on or before the sitting's date, and was queued before gr0wthlab first read this record.

## Rules for both sides

- Every record states the exchange version its writer follows, `"exchange": 4` today, and every item states `exchange: 4`.
- Versions are additive: a new version only adds record types or optional fields, so every record of an earlier version stays valid as written.
- A reader reads every record at or below its own version, by that record's version: a field added after it is simply absent.
- A record of a newer version than the reader knows is reported as unreadable and never guessed at.
- A change that is not additive needs a migration story of its own, not a version bump.
- Version 2 added `next_run` and `carried_over_from` to the queue.
- Version 3 added a post's `window` and `day`, made its `slot` wait until the window's first sitting and posting slot are set, and added `withdrawn` to the queue.
  Mandu's own records change nothing: a decision or sitting record of version 2 reads as it is.
- Version 4 added the `filming-plan` kind, a post's `asset`, and `asset` and `asset_sha256` in a post's queue entry.
  Mandu's own records change nothing again: a filming plan is decided with the same decision record as any item.
- Times carry their UTC offset; dates are `YYYY-MM-DD`.
- Write each file whole: write a temporary file whose name starts with `.` in the same folder, then rename it; both sides ignore files whose names start with `.`.
- Neither side ever writes, moves, or deletes a file in the other's repository.
