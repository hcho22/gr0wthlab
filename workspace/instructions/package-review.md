# Package review

How to find contradictions inside a Go-To-Market Package and turn each into one package-change proposal.
This is the Marketing Engineer's own working guidance; it holds no package content, which stays in Mandu.

## What counts as a contradiction

Two places in the package that cannot both be true now, such as:

- A status fact stated differently in two files: one file says a step is still open, another records it done on a date.
- A number, date, name, or rule that differs between files that should agree.
- A rule in one file that another file's plan breaks.

A difference that the package itself explains (a superseded draft kept for history, a dated log entry, a file marked as an earlier version) is not a contradiction.

## Deciding which side is current

- Prefer the record that states a date and an outcome over one that only repeats an older caveat.
- A checklist item marked done, with a date, records an outcome; text written before that date may simply not have been updated.
- When you cannot tell which side is current, say so in the proposal and ask the Founder to choose, rather than picking one.

## Finding every place

Once you know the stale fact, search the whole package folder for it (for example with `grep -rn` on the package directory), not only the files the brief lists.
List every file that carries the stale fact in Touches, so one approval fixes all of them.
Group every file with the same stale fact into one proposal; a different stale fact is a different proposal.

## Writing the proposal

- Title: `Approve package change: <the change>`, short enough to read at a glance.
- Proposal: one short paragraph saying what is stale and what is current, then each file with the wording to remove and the wording you propose instead.
  Quote only the words that change.
  Where a file's wording is a rule (for example a required legal line), propose the replacement rule rather than deleting it.
- Evidence: at least one line for each side, each with its file path in backticks and the line number.
- Keep it decidable in under a minute.
