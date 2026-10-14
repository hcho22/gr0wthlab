# A refused item leaves only its name and the reasons

A file the launcher sets aside from `workspace/review-queue/incoming/`, of any kind and the filming plan included, is no longer copied whole into `ledger/review-queue/set-aside/<run id>/`.
It is removed, and the run's set-aside record, `ledger/review-queue/set-aside/<run id>.json`, keeps its name, the kind its front matter names when that is one of the item kinds, when it was set aside, and the reasons.
No reason repeats what the refused file or an edit record says: a front matter line is named by its number, an Evidence line by its place in the list, an unexpected section by count, a `supersedes` value only when it is a queued item's identifier, and an edit record's shot and source by their segment.
A Draft waiting for a fix stays exactly as it is.
This was the Founder's choice of 2026-10-13, and [operations](../operations.md#where-the-agents-own-words-are-kept) is now the one list of where the agent's own words may sit.
This file holds every round of that change's live checks.

## First round: the change, its reproduction, and the boundary

This work changes launcher code in `queue.py`, `exchange.py`, and `edits.py`.
It changes nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format, which stays version 7.
The repository holds no set-aside copy to remove: `ledger/` on `main` holds only its READMEs and the Founder's empty folders, so nothing stored needed moving.

Every check below ran on 2026-10-14, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.
A run identifier carries its time in UTC.

### The change itself, through the launcher on demand

The change was seen live in two runs, each started with `src/bin/gr0wthlab run` from a throwaway clone in the Mac's temporary folder, network off for the agent as always.
One clone was of `main` at `f2eded70a18aa90d90842adebbdadf72d3e6e5af`, the other of this work at `7941dcb9bbf28651003e5a9c39df4c1fb8272b74`.
In each clone one commit was added: the configuration `make_repo` in `src/tests/fakes.py` gives (a window far in the future, no network source, no outreach message, no Product that films), a folder of nine prepared items, and a paragraph at the top of `src/instructions/weekly-run/common.md` telling every session to copy those nine files into `workspace/review-queue/incoming/` and do nothing else.
The nine files are the ones `fakes.refused_items` writes: a post, a message, a filming plan, a proposal that declares `new_angle: yes` with no kept quote, an item with an unknown front matter line, one that supersedes no queued item, one with an Evidence line that has no source, one with an unexpected section, and one whose kind is no item kind.
Every one carries the marker `zqxstranger` in its title or body and in each line that fails.
Mandu, RepToday's code, the Immerse checkout, the footage place, the Waitlist view, the log folder, and the production clone were throwaway locations, set with the `GR0WTHLAB_*` overrides; a clone that is not the production clone saves no records and syncs nothing.

| Run | Code | What the records showed |
| --- | --- | --- |
| `20261014T134620Z-on-demand-967d` | `main` | One session, Package review, ended by itself in 9 s (about $0.003). The run report counts 9 set aside. `ledger/review-queue/set-aside/20261014T134620Z-on-demand-967d/` held all nine files, each whole. The run report and the notice `20261014-notice-run-problems` held the marker in four reasons: the front matter line, the `supersedes` value, the headings found, and the Evidence line. |
| `20261014T134641Z-on-demand-5963` | this work | One session, Package review, ended by itself in 7 s (about $0.003). The run report counts 9 set aside. `ledger/review-queue/set-aside/` held one file, `20261014T134641Z-on-demand-5963.json`, with nine entries, each a name, a kind (`null` for the file whose kind is no item kind), the same `set_aside_at`, and its reasons. `workspace/review-queue/incoming/` was empty. No file in the clone's `ledger/` or `workspace/`, or in the run's log folder, held the marker. The four reasons read "line 3 of the front matter is not one of: ...", "supersedes names no item in the Review Queue; name an open item by its identifier", "sections must be exactly: ## Proposal, ## Touches, ## Evidence, ## Options; missing ## Touches, 1 other section", and "Evidence item 2 has no source (a URL or a `path`)". |

### The boundary

Both checks ran from this work's linked worktree at `7941dcb9bbf28651003e5a9c39df4c1fb8272b74`, whose `src/` is tree `dfb73700ac634645809612cd777d77596c2f259c` and whose `config/` is tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`, with `git status` empty before the preflight and after the check, against Mandu and the Product checkouts as they are.
The configuration fingerprint `show-config` prints there is `e73481e3e3e4425625eb8cd7c121b6043119ed3bf6737e0b6f476b23500e6168`.
Their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.

- `src/bin/gr0wthlab preflight`, run twice at 06:46 and 06:47, passed both times: six areas writable, 19 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 06:47, passed at its first attempt, as `20261014T134713Z-on-demand-ac13`, in 79 s: 43 steps to prove, 27 tool calls in Codex's record with no problem, no file-tool target without a refusal, 16 kernel sandbox denials, no shell target without a kernel denial, the footage place's shell read refused, every permitted area written, no sentinel escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- Three of the four new tests were first run on the code of `main`, with this work's test files copied over a throwaway export, and none passed.
  The ledger's own test found no `kind` on a set-aside file; the whole run found no set-aside record, and with the record assertions taken out it found the marker in the run report; the edit-record test found the marker in a finding in each of its four cases.
  The fourth, a set-aside record that cannot be written, tests a step `main` does not have.
- `ruff check src src/bin/gr0wthlab` and `ruff format --check src src/bin/gr0wthlab` passed, with ruff 0.15.20.
- The full unit suite ran under `/usr/bin/python3` on a `git archive` export of `main` (1290 tests) and of this work at `f03018d` (1294 tests), the commit after the boundary checks, which adds one test and no code.
  Each failed the same two tests and no other: `test_no_media_file_is_in_the_repository` and `test_missing_codex_refuses_to_start_and_records_why`, both of which read the checkout with git and found no `.git` in the export.
  Both passed when run again from this work's linked worktree, a git checkout.

### What this round did not exercise

- A Draft waiting for a fix was not made live; it stands on the whole-run test `test_a_refused_item_leaves_its_name_and_reasons_and_a_draft_waiting_for_a_fix_stays_as_written`, whose day 3 Draft is blocked and is the same text after the run.
- An edit record's checks were not run live, since no Product films in the lab; they stand on `test_no_finding_repeats_a_shot_or_source_the_record_gives` and the filming tests.
- A set-aside record that cannot be written was not made live; it stands on `test_a_set_aside_record_that_cannot_be_written_is_said_in_each_file_s_reasons`.
- An item that passes the format but cannot be queued, whose reason is unchanged, was not made live and stands on no test.
- The agent copied the files with `cp`, so its session logs held only the command; a session that writes such a file with a patch leaves its text in Codex's event stream and log in the log folder, which this change does not touch and `docs/operations.md` names.
- No weekly run was made on a schedule, and Mandu's side was not shown the notice.
