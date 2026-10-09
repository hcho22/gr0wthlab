# Package review

How to find contradictions inside a Go-To-Market Package and turn each into one package-change proposal.
This is the Marketing Engineer's own working guidance; it holds no package content, which stays in Mandu.

## What counts as a contradiction

Two places in the package that cannot both be true now, such as:

- A status fact stated differently in two files: one file says a step is still open, another records it done on a date.
- A number, date, name, or rule that differs between files that should agree.
- A rule in one file that another file's plan breaks.

Text the package marks as history (a superseded draft kept for history, a dated log entry describing the state on its date, a file marked as an earlier version) is not a contradiction.
A record of an outcome that notes other files still state the earlier status does not explain them away: those files are stale, and that is a contradiction.

## How to review

Do every pass below before you write any item; finding a contradiction does not end the review.

1. Recorded outcomes.
   Take every item that a checklist or status line in the package marks done, cleared, or decided, with a date or an outcome.
   For each one, search the whole package folder for text that still states the earlier status, as "Finding every place" describes.
   Each outcome that other files still contradict is one stale fact.
2. Facts that should agree.
   Compare the numbers, dates, names, and rules that more than one file states.
3. Rules and plans.
   Check each plan against the rules it has to follow.

Then write one proposal for each stale fact you found, and in your summary list each recorded outcome you traced with what you found for it.
Every stale fact you found becomes a proposal, even when the replacement wording needs the Founder's judgment (for example a legal line or a claim the record states only in part): propose the narrowest wording the record supports, and say in the proposal what the Founder must confirm or choose.
It also becomes a proposal when you end the run before every pass is done; say in your summary which passes you did not finish and why.
A contradiction you name only in your summary is one the Founder never decides.

## Deciding which side is current

- Prefer the record that states a date and an outcome over one that only repeats an older caveat.
- A checklist item marked done, with a date, records an outcome; text written before that date may simply not have been updated.
- When you cannot tell which side is current, say so in the proposal and ask the Founder to choose, rather than picking one.

## Finding every place

Once you know the stale fact, search the whole package folder for it (for example with `grep -rn` on the package directory), not only the files the brief lists.
Search for every way it is phrased: its key words in upper and lower case, the caveat's wording, and checklist items about it that are still unchecked.
List every file that carries the stale fact in Touches, so one approval fixes all of them.
Group every file with the same stale fact into one proposal; a different stale fact is a different proposal.

## Writing the proposal

- Title: `Approve package change: <the change>`, short enough to read at a glance.
- Proposal: one short paragraph saying what is stale and what is current, then each file with the wording to remove and the wording you propose instead.
  Quote only the words that change.
  Where a file's wording is a rule (for example a required legal line), propose the replacement rule rather than deleting it.
  Propose wording that claims exactly what the current record says and nothing more; a status the record does not state, such as a registration, is never implied.
- Evidence: at least one line for each side, each with its file path in backticks and the line number.
- Keep it decidable in under a minute.
