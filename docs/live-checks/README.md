# Live checks

Each change records its live checks here, in a new file of its own.
A live check is anything a change runs on the Founder's Mac that CI cannot run: the re-check after a change to the launcher or the configuration (`preflight`, `boundary-check`, hole tests), a timed run, and the list of what a re-check did not exercise.

Until 2026-10-12 every change added these to [the US-ME02 spike note](../spikes/us-me02-runtime-boundary.md), so merging one change made every other waiting change clash with that note.
The note keeps that history and its explanation of the boundary.
A change still edits the note, [operations](../operations.md), or any other document when what that document explains has changed; it never adds a record of its own checks to one.

## One file per change

- A change adds one file here and puts every round of its checks in it: the first re-check, the re-check after review, the re-check after a merge with `main`.
- A change edits no other change's file, and no file lists the files in this folder: the folder listing is the index.
- A correction to a record that is already on `main` goes in the correcting change's own file, which links the file it corrects.

## The file name

`<date>-<branch>.md`

- `<date>` is the UTC date of the first check the file records, as the eight digits a run identifier starts with: `20261012` in `20261012T220142Z-on-demand-b797`.
- `<branch>` is the change's branch name after its last `/`: `gr0wthlab-owed-run-check` for the branch `fm/gr0wthlab-owed-run-check`.

Two changes open at the same time have different branch names, so they pick different file names without asking each other, and the folder sorts by date.
A story identifier is not part of the name, since several changes share one; the file's title names the stories.
The name is set when the file is added and does not change when a later round runs on a later date.

## What a file holds

Start with a title that says what the change is and which stories it serves, then one section per round of checks.
Each round states:

- **What was run:** each command as typed, where it ran from (the production clone, a linked worktree, a scratch clone beside synthetic checkouts), the date and time with its time zone, and the Codex CLI version.
- **On which commit:** the full hash of the commit the checks ran on.
  When the record lands in the commit that holds the code, a commit cannot name itself, so give the `src` and `config` tree hashes instead, which `git rev-parse <commit>:src` and `git rev-parse <commit>:config` print for any commit that holds the same code.
  Say whether `git status` was empty before and after, and give the configuration fingerprint `show-config` prints.
- **Each run's identifier:** every run, the ones that failed or were run again included, such as `20261012T221703Z-on-demand-13a9`.
  A streak is a table with one row per attempt.
- **What the records showed:** the verdict and the counts behind it, each from the record that holds it.
- **What was not exercised:** every case this round left out, and what it stands on instead (a unit test, an earlier round, nothing).
  A round that left nothing out says so.

Every sentence about a check's output states only what a record shows and names no cause beyond it, the rule [`AGENTS.md`](../../AGENTS.md) sets for the boundary check.
A count that was not read is left out, never written as zero.

Write the file as the rest of `docs/` is written: one sentence per line.

## Paths and what stays out

This repository is public.

- Write a path inside the repository from the repository's root (`src/gr0wthlab/probe.py`), and a path under the home folder with `~` (`~/gr0wthlab`, `~/Library/LaunchAgents`).
- When a quoted record line holds the home folder's full path, replace that prefix with `~` and say beside the quote that it was replaced.
- Leave out account names, host names, email addresses, tokens, and any raw log that holds one; quote the lines the record needs, not the whole log.
- Before committing, run `grep -n "/Users/" docs/live-checks/<file>`, which must print nothing.
