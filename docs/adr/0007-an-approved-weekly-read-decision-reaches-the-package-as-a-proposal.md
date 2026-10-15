# An approved Weekly Read decision reaches the package as a proposal

Approving a Weekly Read decision changes no package file by itself.
When the Founder approves an Angle's kill or change, a resolved A/B pair, or the flex slot, the next run files one package-change proposal with the exact edit to the package file the decision touches, and the Founder approves or rejects it like any other proposal; Mandu applies it only once he has approved it.

Decided by the Founder on 2026-10-15, in his words: "angle kill - two approvals."
How each decision marks the package was decided by firstmate the same day, from the package's own rules where it has one.

## Why

- Mandu acts on only two kinds of approval, a package-change proposal and a Dispatch request ([the Mandu exchange](../mandu-exchange.md#what-mandu-does)), and applies only the exact text the Founder approved.
  A Weekly Read decision item said "which Mandu changes if you approve" of an Angle's row, but no record gave Mandu the edit, so an approved kill changed nothing in the package and later plans could keep using the killed Angle.
- The proposal takes the path every package change already takes, and the Founder sees the precise wording before his package changes.
  The cost is one more approval, and only when he kills or changes an Angle, resolves a pair, or fills the flex slot.
- The exchange stays at version 8, and Mandu's reader needs no change: the proposal is an ordinary `package-change-proposal`.

## What each decision files

The launcher writes each edit, but for the new Angle a change asks for, whose words the Weekly Read session writes, under checks of their own ([`src/gr0wthlab/weekly_changes.py`](../../src/gr0wthlab/weekly_changes.py)).

| Approved decision | The proposal's edit |
| --- | --- |
| An Angle's kill | Its record in `creative-log.json` takes `"status": "killed"` and `"killed_on_reads"` with the dates of the two Weekly Reads, as the calendar's own kill rule says; its row in the Angle bank is not changed |
| An Angle's change | A changed Hook, signal, or kill criterion enters only as a new Angle (FR-7): a new row at the end of the Angle bank, under the next free number, with the changed Angle's pain and source as they are; the changed Angle stays as it is, since it did not meet its kill criterion |
| A resolved pair | One line at the end of the pair's section in the A/B pairs file, saying which leg's Hook leads; the memo's pair line names that leg |
| The flex slot, earned or not | The calendar's flex row names the Angle that earned it, or the one Angle the row names for when none did, on that Angle's own platform |

An Angle kept or tested, a pair to repost, a result that bears on the product, and every rejected decision file nothing.

Every edit replaces a text that appears exactly once in the file as the run read it, so Mandu applies it with no judgment, and is filed only when applying it changes exactly what the decision fixes and nothing else.
A decision's proposal is filed once, and never again, whatever the Founder decides of it.

## Considered Options

The Founder was given these on 2026-10-15.

- **Two approvals: approve the decision, then the exact edit as a normal package-change proposal at the next run.**
  Chosen ("angle kill - two approvals").
- **One approval: the decision item carries the exact edit.**
  Not chosen: it needs another change to the gr0wthlab and Mandu record format.

How a kill, a resolved pair, and a changed Angle are marked, put to firstmate on 2026-10-15:

- A kill: the package's own rule, in `creative-log.json` (chosen); the same and a mark in the Angle's row; or a mark in the row alone.
- A resolved pair, where the package has no rule: one line under the pair in the A/B pairs file (chosen); or that line and the `ab_pair` text in `creative-log.json`.
- A changed Angle, where the package has no rule: the old Angle stays as it is (chosen); or it takes a status of its own in `creative-log.json` and the new Angle a record there.
