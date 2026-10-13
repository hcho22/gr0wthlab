# The Founder decides in gr0wthlab, on a local page, and Mandu reads

The Founder's decisions and the records of what the Founder did live in gr0wthlab, in `ledger/founder/`, where the sandboxed agent can read and can never write.
The Founder gives them on a small page that `src/bin/gr0wthlab sitting` serves on the Founder's own Mac, which asks one thing at a time and saves exactly what the Founder clicks, with no AI between the answer and the record.
Each Product's Go-To-Market Package stays in Mandu, as [ADR 0001](0001-evidence-and-drafts-only.md) decided, and gr0wthlab still never writes to Mandu or to a Product repository.
Mandu only reads gr0wthlab, to show the Founder status and to apply a package change the Founder approved.

Decided by the Founder on 2026-10-12.

## Why

Until this decision, gr0wthlab wrote the Review Queue and Mandu wrote back: the Founder's decisions, the sitting record, the Beta Build approval, the Beta Cohort counts, and what the Founder sent.
Both sides wrote records in one numbered format, and a reader treats a record of a newer version than it knows as unreadable.
Listening and outreach took the format to version 5 and filming to version 6, so every new kind of item needed new work in Mandu before the Founder could approve it, and a Mandu side built for an older version would have lost the whole Review Queue.
Two repositories also validated what the Founder decides, so gr0wthlab carried the handling of another repository's records being missing, unreadable, or malformed.

With the decisions kept in gr0wthlab, one place writes and validates them, a new kind of item needs nothing from Mandu, and Mandu's side shrinks to reading.
Nothing had run for real when this was decided, so there was no history to move ([Nothing was moved](#nothing-was-moved)).

## The invariant

Nothing reaches the public unless the Founder approved it, and nothing but the Founder's own act on the page is ever an approval.
Three rules hold that, and [`src/gr0wthlab/founder.py`](../../src/gr0wthlab/founder.py) states and enforces them in one place:

1. Only the Founder-side command, `gr0wthlab sitting`, writes a Founder record, and only when a request from its own page asks it to.
   The Founder starts it, outside the sandbox.
   The weekly run, the agent, and every other command only read the records: the launcher's own writer refuses every path in `ledger/founder/`.
2. A Founder record is a plain file with one link, directly inside one of the five record folders, each a real folder.
   Nothing under `workspace/` is ever read as one, whatever its name, location, or content: the reader opens no path outside those folders and follows no link.
   A record folder that is missing, or that is a link, stops every run, check, and sitting before it starts.
3. The sandboxed agent can read the records and can never write them.
   `ledger/` is no writable area, every run's preflight tries each record folder from inside the sandbox before the agent starts, and the boundary check proves each record folder on its own from the runtime's records ([the US-ME02 spike note](../spikes/us-me02-runtime-boundary.md)).

Before this decision the third rule held because the records were in Mandu, which the run cannot write.
It now holds by the same write boundary that keeps the agent out of `ledger/`, `src/`, and `config/`, proved per folder.

## Where the records live

| What | Path under `ledger/founder/` | Written |
| --- | --- | --- |
| Decisions | `decisions/<item id>.json` | When the Founder approves or rejects an item |
| Sittings | `sittings/<YYYY-MM-DD>.json` | When the Founder ends a sitting |
| The Beta Build record | `beta-builds/<Product>.json` | When the Founder says a Beta Build passed Apple's review, stops recruiting, or reopens it |
| Beta Cohort reports | `beta-reports/<Product>-<YYYY-MM-DD>.json` | When the Founder gives the counts |
| Outreach records | `outreach/<item id>.json` | When the Founder sent a message, or heard back |

Each record keeps the format and the meaning it had in Mandu's exchange folder; [the Mandu exchange](../mandu-exchange.md) has every field.
The records are saved with the launcher's other records: the production clone's records step commits `ledger/` and pushes it to `main`, so a sitting's records go with the next run's.
Each file is written whole, through a temporary file in the same folder that is then renamed.

gr0wthlab reads no record from Mandu any more.
`mandu.exchange` in `config/products.json` and `GR0WTHLAB_EXCHANGE_DIR` are gone, and a configuration that still sets either stops the run with a message that says where the records are now.

## The page

`src/bin/gr0wthlab sitting` serves the page and prints its address; the Founder opens it in a browser on the same Mac.

- It walks the sitting in the Review Queue's order, one thing in front of the Founder at a time: the run report's summary, a warning when the weekly run due has not finished, then each open item whole, with what it touches and its Evidence.
- For each item the Founder approves, with an optional one-line note, rejects, with a one-line reason, or leaves it for later, which writes nothing.
  A carried-over item says so and from which sitting.
  A post that shows a video plays that file, checked against the fingerprint the Review Queue holds for it, so the video and its copy are approved together; a post whose video cannot be shown offers no approval.
  The filming plan is decided like any item.
- While a Product's Beta Cohort is being recruited, it asks for the three counts.
  A count left blank is recorded as not reported, never as zero.
- At the end it records how long the sitting took, which the page measured and the Founder can correct.
- Beside the walk it has one plain place for what the Founder did: a message sent, a reply received, the wait before a follow-up, a Beta Build approved, recruiting stopped or reopened.

What the Founder clicks is what is saved, and the page then shows the record as it reads it back from the file.
The page builds each record only from the fields the Founder filled and the Mac's clock, and passes it through the same check the weekly run reads it with before it writes anything, so it never writes a record a run cannot use.
Every limit holds at entry, refused with a plain reason: one line of at most 300 characters, a reason for every rejection, dates that are real and not ahead, counts that are whole numbers, and nothing that looks like an email address.
No record names a person: a person is only ever a Waitlist entry identifier, and the page says so beside every line the Founder can type.

There is no AI, no model call, and no network use anywhere in it.

### The page cannot be made to decide for the Founder

- It listens on `127.0.0.1` only, on a port and behind a secret in its address that are new each time it starts.
- A request without the secret gets nothing.
  A request that changes anything is a POST to an address that holds the secret, whose `Host` and `Origin` are the page's own; any other is refused and writes nothing.
- Everything the agent or a third party wrote is shown as text: an item, a run report, a record.
  The page lays an item out by its lines, a heading line, a list line, a quoted line, a table row, so it reads as it does in its file, and shows every character of it as written.
  It makes no link, image, style, script, form, or tag from anything it shows.
- It loads nothing from anywhere else: it ships its own style sheet and script, and its content security policy forbids every script, style, image, video, and request the page did not ship itself.
- It runs under the Mac's `/usr/bin/python3` with the standard library only, and stops on Ctrl-C or from its last page.

## Correcting a record

A mis-click is corrected on the page, under these rules and no others:

- **A decision** can be changed or taken back until a run has taken it in, and never after.
  Changing it writes the record again, whole; taking it back removes the record, which leaves the item undecided.
  A run takes a decision in when it closes the item and writes the decision's Evidence (`ledger/evidence/decisions/<item id>.json`); from then on the page shows the decision and offers no change, and the item is never asked again.
  The page and the run take the same short lock around the two, so a change and a run that starts in the same moment cannot both win.
- **A sitting record, a Beta Cohort report, and an outreach record** can be corrected at any time by giving them again; the file is written again, whole.
  None can be removed on the page.
- **The Beta Build record** is written again, whole, when recruiting is stopped or reopened; the approval date stays as it was first given, and the record cannot be removed on the page.
  A Beta Build recorded by mistake is undone by stopping recruiting.

A record changed by hand, or damaged, is not a record.
The run names it with the exact problem, takes nothing from it, and leaves everything as it was: an item it would have decided stays open, and a decision already taken stands.
The Founder corrects it by giving the answer again on the page.

Known limit: a message recorded as sent by mistake cannot be marked as not sent.
Its record can only be corrected, and the one thing that follows from it is a follow-up Draft offered after the waiting period, which the Founder can reject.

## When a run and a sitting overlap

A run and a sitting may overlap, as when the Mac was asleep at the weekly time and the run starts as the Founder sits down.

- The page reads the Review Queue each time it shows something.
  While the weekly run due has not finished, it says so first, and the queue and the report it shows are the earlier run's.
  When a run finishes during the sitting, the page says that the queue changed and shows the new one.
- A run reads the Founder's records once, before its agent starts.
  A decision given later, during the run, is taken in by the next run.
- A decision on an item that the run in progress replaced with a newer item is kept, as before: its Evidence names the newer item, which stays open, and the Marketing Engineer sees the decision beside it.
- A decision the run in progress has already taken in can no longer be changed, and the page says so.
- Only one sitting page is served per checkout at a time.

## What Mandu does now

Mandu writes nothing that gr0wthlab reads except its own Go-To-Market Package.
It may read gr0wthlab's Review Queue, items, run reports, and the Founder's records to show the Founder status.
It still acts on two kinds of approval, as it did before, and now reads each from gr0wthlab:

- It applies a package change the Founder approved to the Go-To-Market Package.
- It hands an approved Dispatch request to firstmate under its existing Dispatch arrangement.

It acts on an approval only once a run has taken the decision in, which is when the decision can no longer change: the Review Queue lists the item as closed and approved, and the decision record says `approve`.

Mandu's read-only side is Mandu's own work, built by Mandu's own agent from [the Mandu exchange](../mandu-exchange.md), and nothing in gr0wthlab waits for it: the Founder can run a sitting without it.

## Nothing was moved

The exchange's own rule is that a change which is not additive needs its story told, not only a version number.
This change is not additive: it moves who writes five kinds of record.
Its story is short, because nothing had run for real.

On 2026-10-12, on the Founder's Mac, there was no production clone at `~/gr0wthlab`, the weekly schedule had never been installed, and Mandu held no exchange folder and no record: `~/Mandu/projects/gr0wthlab/` held a project note and a log, and no `exchange/` folder.
So no decision, sitting, Beta Build record, Beta Cohort report, or outreach record existed anywhere, and nothing was moved or converted.
The format is version 7 from this change on, and no reader of an earlier version was ever built.

## What this changes in ADR 0001

ADR 0001 kept each Go-To-Market Package in Mandu "because Mandu already tracks the Products and is where the Founder reviews and decides", and rejected moving the package here "so that Mandu remains the Founder's single record".
The Founder no longer reviews and decides in Mandu, and Mandu is no longer the record of the Founder's decisions.
Everything else in ADR 0001 stands: this repository holds Evidence, Drafts, and Review Queue items and no strategy, the Go-To-Market Package stays in Mandu as its single copy, Mandu applies the changes the Founder approves, a Product change is a Dispatch, and every public act is the Founder's.
A decision record holds the Founder's answer to one item, never positioning, Fit, a claim, or an Angle.

## Considered Options

The Founder was given these on 2026-10-12.

- **Keep the decisions in Mandu and build Mandu's side for version 6.**
  Rejected: every later kind of item would again wait on Mandu, and two repositories would go on validating one decision.
- **Move everything to gr0wthlab, the Go-To-Market Package included.**
  Rejected: keeping strategy out of this repository is the founding decision of ADR 0001.
- **Move the decisions and the records of what the Founder did, keep the package in Mandu, and make Mandu a reader.**
  Chosen.

How the Founder gives a decision, once it is kept here:

- **Telling Mandu in conversation.**
  Rejected: an agent would again stand between the Founder's answer and the record.
- **A command in the terminal.**
  Not chosen: an item with a video and its Evidence does not fit a terminal.
- **A small local page, like the review boards the Founder already uses.**
  Chosen.

What "as a conversation" means on that page:

- **A: one thing at a time, a click or a typed line, no AI, and what is clicked is what is saved.**
  Chosen.
- **B: a chat with an AI that works out what the Founder meant and saves it on a yes.**
  Rejected by the Founder.

## Not decided here

Two stories that are not built yet say their input goes into Mandu: the Founder's TikTok export (US-ME11) and the Founder's confirmation that starts Immerse Listening (US-ME18).
Their sentences are left as they were, for the Founder to decide when those stories are built.
