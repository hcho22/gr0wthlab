# The Founder types the Weekly Read's numbers

In a read week the Founder types each number the Weekly Read asks for into the sitting page, as TikTok Studio or YouTube Studio shows it, and pastes the comments as text.
The page takes no screenshot and no file, and keeps none.

Chosen by the change that built the Weekly Read (US-ME11, US-ME12), on 2026-10-14.
The Founder has not decided it: the brief asked for a place on the sitting page to give the TikTok export as screenshots or a file, as US-ME11 does, and this record is for him to confirm or overturn.

## Why

- A screenshot or a Studio download shows more than the Weekly Read uses.
  A screenshot of a post's comments shows who wrote each one, and a Studio's pages and downloads show follower counts, which US-ME11 says are never stored.
  The Founder's records in `ledger/founder/` are committed to git with each run's records, and a committed image or file stays in the history every later push carries to GitHub, for anyone who can read the repository.
  The repository has been public since 2026-10-14; a run in the production clone pushes nothing while it is.
- Nothing outside the sandbox can read an image.
  The launcher is standard library only and calls no model, so it cannot take a number from a screenshot.
  The agent could, but then a number it transcribed would stand as the Founder's record, which only the sitting page writes, on his own act ([ADR 0002](0002-the-founder-decides-in-gr0wthlab.md)), and the model would see every commenter's name.
- No sample of either Studio's download was available to this change, so a reader for one would be built on a guessed format.
- What he types is bounded: each post on the platform that judges it, its views for the floor, and only the numbers the signals and kill criteria of the read's posts on that platform name, about three or four a post, for five posts at the day-7 read and thirteen at the day-14 read.

## What follows

- Each number has a field of its own: a shortened figure such as 1.2K is refused, a blank is not reported and never zero, and the day he read them is the source of every number in the record.
- Comments are pasted one a line, their words only and never who wrote them.
- US-ME11's third acceptance criterion, that the export is "given on the sitting page as screenshots or a file", is not met as written, and its box stays open.
  The rest of it holds: the numbers are given on the sitting page and never through Mandu, and each post's become its Evidence with the date he read them as its source.
- A reader for a Studio download can be added later, once a real download's format is known: it would keep only the numbers asked, and the Founder would still give it on the page.

## Considered Options

- **Screenshots, kept and read by the agent**: rejected for commenters' names in a public repository and for an agent's transcription standing as the Founder's record.
- **A Studio download, read by the launcher**: not built, since no download's format was known; it could follow as above.
- **Each number typed, and the comments pasted as text**: chosen.
