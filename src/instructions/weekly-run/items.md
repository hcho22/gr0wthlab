## Writing an item

Write each item as a new file `<slug>.md` in the incoming folder the brief names, where the slug is lowercase words joined by hyphens, such as `trademark-status-stale.md`.
The format is in `docs/mandu-exchange.md` at the repository root; a package-change proposal looks like this, with nothing else in the file:

```markdown
---
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Approve package change: <the change, in a few words>

## Proposal

<What to change, file by file, and the replacement wording you propose.>

## Touches

- `<each package file that would change>`

## Evidence

- <What one side says, quoting only the words that matter>: `<file path>` line <n>
- <What the other side says>: `<file path>` line <n>

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
```

The `# ` title is the one-line ask the Founder decides on, under 120 characters.
Leave out `id` and `exchange`; the launcher assigns both when it queues the item.
Every Evidence line names its source as a path in backticks or a URL.

Every package-change proposal declares `new_angle`, and the Founder sees what you declared:

- `new_angle: yes` when the proposal adds an Angle or Hook, or changes any Hook, signal, or kill criterion, which is a new Angle.
  It needs sourced pain: an Evidence line that names the record of at least one quote the launcher already keeps, exactly as `evidence/listening/quotes/<document id>.json`, or the launcher sets it aside.
  A proposal that rests on a quote recorded this run is the Listening session's to write, through the angles folder.
- `new_angle: no` when it does neither, whatever files it touches: a fix that brings stale text in the Angle bank or the A/B pairs file in line with the record is `no`.
  The launcher queues a `no` proposal without checking the declaration against its wording, and the Founder is the check on a wrong one: declare what the proposal does, never what gets it queued.

Rules for items:

- Write only new item files in the incoming folder, and only package-change proposals, or a Dispatch request where "This session" says so.
- Do not queue an item that is already open; to replace one, write a new item with `supersedes: <id>` in its front matter.
  An item the brief marks as filed by the launcher, such as a Dispatch request, cannot be superseded: only a reviewed change to its source text replaces it.
  A post or a message cannot be superseded either: each changes only through its Draft.
  Nor can a Weekly Read decision, which the brief marks so: it changes only through the Weekly Read memo.
  Nor can the notice of a change to the Instructions, which the brief marks so: only the Founder's decision closes it.
- The brief lists the items earlier sessions of this run left in the incoming folder, which are not queued yet.
  Read each one that touches a file your work uses, write nothing that asks the same, and leave those files as they are.
- Do not propose again what the Founder already rejected unless new Evidence answers the reason.
  The launcher refuses an item as a repeat when its kind, `# ` title, and text match those of any item ever queued, whether open, decided, or superseded, once case and spacing are ignored: the text compared is a proposal's `## Proposal` section, and a Dispatch request's `## Request` section.
  It also refuses one with the same kind and `# ` title as a queued item whose file it could not read.
  Any other repeat, a reworded one included, is yours to catch: rewording an ask does not make it new.
- Quote only the specific package text a proposal uses or replaces, citing its file; never copy a package file or a large part of one.
- Check your items before you finish with the brief's check-incoming command.
