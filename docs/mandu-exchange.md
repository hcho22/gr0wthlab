# Mandu exchange, version 1

How gr0wthlab (the Marketing Engineer) and Mandu pass the Review Queue and the Founder's decisions between them.
Mandu's own agent builds Mandu's side from this page.
Later stories extend the exchange, each with a version bump: the TikTok export (US-ME11), the Beta Build approval (US-ME15), and the US-ME18 confirmation.
Each side writes only its own repository and only reads the other's: gr0wthlab writes items in gr0wthlab, and Mandu writes decisions in Mandu.

## Where things are

| What | Written by | Path on the Founder's Mac |
| --- | --- | --- |
| The Review Queue | gr0wthlab | `~/gr0wthlab/workspace/review-queue/queue.json` |
| Each item | gr0wthlab | `~/gr0wthlab/workspace/review-queue/items/<id>.md` |
| Each run report | gr0wthlab | `~/gr0wthlab/workspace/run-reports/<run id>.md` |
| Decisions | Mandu | `~/Mandu/projects/gr0wthlab/exchange/decisions/<id>.json` |
| Sittings | Mandu | `~/Mandu/projects/gr0wthlab/exchange/sittings/<YYYY-MM-DD>.json` |

`~/gr0wthlab` is gr0wthlab's production clone; each run also pushes its outputs to `main` of `github.com/hcho22/gr0wthlab`, but Mandu reads the local files.
gr0wthlab finds Mandu's folder from `mandu.exchange` in gr0wthlab's `config/products.json`, and `GR0WTHLAB_EXCHANGE_DIR` overrides it on one machine.
To move the folder, change that configuration through a gr0wthlab pull request.

## The sitting

1. Read `queue.json`.
   If its `updated_at` is more than eight days old, tell the Founder first that this week's run has not happened.
2. Show the summary at the top of the run report that `queue.json` names in `run_report`.
3. Present each entry of `open`, in the listed order, by showing its item file.
   Skip any entry that already has a decision record.
   For an entry with `"carried_over": true`, say it was carried over from the sitting on the date in `carried_over_from`.
4. The Founder approves an item, optionally with a one-line note, or rejects it with a one-line reason, or leaves it undecided.
   An undecided item needs nothing written; it returns, marked carried over, at the next sitting.
5. Write one decision record for each decided item as soon as it is decided.
6. At the end, write one sitting record with how many minutes the sitting took.
   Once gr0wthlab reads that record, it marks the items left undecided at the sitting as carried over.

Paths inside `queue.json` are relative to `~/gr0wthlab/workspace/`.

## Items (gr0wthlab writes)

Each item is one Markdown file, named by its identifier, holding the front matter, a `#` title, and four `##` sections in this order, and nothing else:

```markdown
---
exchange: 1
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
- A post also has `slot`, its publishing time with its UTC offset, such as `2026-10-14T19:00-07:00`.
- `supersedes` names an earlier item this one replaces; the earlier one has left `open` and is never presented again.

| `kind` | The section after the title | Options |
| --- | --- | --- |
| `post` | `## Draft` | Approve or reject |
| `message` | `## Draft` | Approve or reject |
| `weekly-read-decision` | `## Recommendation` | Approve or reject |
| `dispatch-request` | `## Request` | Approve or reject |
| `package-change-proposal` | `## Proposal` | Approve or reject |
| `notice` | `## Notice` | Acknowledge (recorded as approve) or reject |

A notice is informational, such as a failed source or a change to the Marketing Engineer's Instructions; acknowledging it records `approve`.

## The queue (gr0wthlab writes)

```json
{
  "exchange": 1,
  "updated_by_run": "20261011T230002Z-scheduled-1a2b",
  "updated_at": "2026-10-11T23:41:09+00:00",
  "run_report": "run-reports/20261011T230002Z-scheduled-1a2b.md",
  "open": [
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

`open` is already in presentation order: posts by nearest slot first, then messages, Weekly Read decisions, Dispatch requests, package-change proposals, and notices, oldest first within each kind.
`carried_over` is `true` for an item that was open at an earlier sitting and left undecided, and `carried_over_from` then gives the date of the first such sitting.
An item queued after the latest sitting is not carried over, whichever run queued it.
`closed` lists every decided or superseded item and is history only; never present it.
gr0wthlab may add fields; ignore any you do not use.

## Decision records (Mandu writes)

One file per decided item, `decisions/<id>.json`, written once and never edited or deleted:

```json
{
  "exchange": 1,
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
A record that does not follow this format, or names no queued item, is reported to the Founder as a notice, and its item stays open.
Such a record is not a decision, so Mandu fixes it by rewriting it in this format.

## Sitting records (Mandu writes)

One file per sitting, `sittings/<YYYY-MM-DD>.json`, with the minutes the Founder spent, measured by Mandu or reported by the Founder:

```json
{"exchange": 1, "date": "2026-10-11", "minutes": 48, "note": null}
```

`minutes` is a whole number from 1 to 600, and `date` equals the file name.
Write it when the sitting ends: gr0wthlab counts an item as left undecided at the sitting when the item is still open, was queued on or before the sitting's date, and was queued before gr0wthlab first read this record.

## Rules for both sides

- Every record states `"exchange": 1`, and every item states `exchange: 1`; a reader that meets a version it does not know reports it and never guesses.
- Times carry their UTC offset; dates are `YYYY-MM-DD`.
- Write each file whole: write a temporary file whose name starts with `.` in the same folder, then rename it; both sides ignore files whose names start with `.`.
- Neither side ever writes, moves, or deletes a file in the other's repository.
