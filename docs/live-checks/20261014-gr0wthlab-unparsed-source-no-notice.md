# A package file read and not usable is a failed source (US-ME17)

A package file that the snapshot read but that launcher code then could not parse or decode is now a failed source, as a missing or unreadable one is.
The run report's Sources table shows it as `unusable`, with what the snapshot found and why the file could not be used, its summary counts it among the failed sources, and the run's notice names it once, with the outputs it leaves incomplete.
The outputs are the same ones whose rows read incomplete for it before this change; no output changes status.

## Which sources this applies to

Found by reading every place launcher code reads a source file and can fail to parse or decode it.

Marked `unusable` by `Cycle.unusable_sources` when it fails that way:

- The kit files the post Drafts read (`posts.read_kit`): the calendar, the Angle bank, the A/B pairs, the platform assignment, the pre-publication checklist, and the competitor research folder.
  Each leaves the post Drafts incomplete; the calendar, the Angle bank, and the A/B pairs also leave the filming plan incomplete while a Product films (`filming.ROLES`).
  The competitor research folder, which has no line of its own in the Sources table, gets one when its files were each read and could not be used as a whole.
- `brand-rules.json`, read for the post Drafts (`posts.context_plan`) and, once recruiting has started, for Beta Cohort recruiting (`beta.context`): one line, which names both outputs when both could not use it.
- The outreach channel plan (`outreach.prepare`) when it is not UTF-8 text; it leaves the outreach Drafts incomplete.
  Before this change a channel plan that was not UTF-8 was said to be one that "could not be read"; it is now said to be "not UTF-8 text".

Already a failed source before this change, and left as it was:

- The Waitlist view (`waitlist.read`): a view that is not UTF-8, not JSON, or not in the view's format is `failed` with the reason.
- The network sources (`sources.py`): an answer that could not be parsed is `failed`.
- The App Store reviews when the competitor research could not be used: `failed`, needing Listening.
- The Founder's records (decisions, sittings, outreach records, Beta Build records, Beta Cohort reports): a record that could not be used has its own notice part, or its source line, as before.

Not a source in this sense, and left as it was:

- A Draft, an edit record, an item file, a run state file, and a reviewed Dispatch text: each is told where the item or step that reads it is told.
- A package line a recruiting Draft cites (`beta_drafts.cited_line`): it blocks that Draft and is told on it.
- The Angle bank, the checklist, and the brand rules where a message or reply is checked against them (`messages.check`): those items are told where they are, and an open one stands, as before; the notice's line for the file names only the outputs whose own step cannot go on without it.
- The platform facts in `config/platforms.json`: configuration in this repository, not a source.
- The positioning file Listening reads for Fit: the agent reads it, and launcher code does not parse it.
- A file a folder source no longer holds, such as a channel plan that was removed: the snapshot lists it as removed since the previous snapshot, as before.

## First round, on the change as committed

This change edits launcher code (`cycle.py`, `report.py`, `package.py`, `posts.py`, `outreach.py`), and nothing in the permission profile, the Codex command, the fetch policy, the Product registry, or the exchange format.
On `4858c8842dd81cd080b2c4190604e97114f0fa73`, whose `src/` is tree `d846a61ef73e6d2692378baae7ac9d974f7cbac2` and whose `config/` is tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`, the full unit suite passed under `/usr/bin/python3`, 1295 tests, as did ruff 0.15.20.
Every check below ran on 2026-10-14, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.
A run identifier carries its time in UTC.
A later commit on the branch adds one unit test, for the competitor research folder, and changes no launcher code.

### The boundary

Both checks ran from this change's linked worktree at that commit, with `git status` empty before the preflight and after the check, against Mandu and the Product checkouts as they are.
The configuration fingerprint `show-config` prints there is `65c0362d7e73a1bc164001414c11a4aa2d3153d5c3658a53128ae58b4f09bb45`.
Their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.

- `src/bin/gr0wthlab preflight`, started at 08:02 and run three times in a row to read its output, passed each time: it wrote and deleted a file in each of the six areas, refused 19 paths, refused a listing of the footage place, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 08:03, passed after two probe runs.

| Run | Verdict | What its record showed |
| --- | --- | --- |
| `20261014T150315Z-on-demand-cdd2` | not yet proven | 43 steps to prove; 13 of 14 file-tool targets refused in a patch of their own, and for `ledger` no patch named its sentinel; 16 kernel denials naming the run's sentinels or the check's listeners; 1 of 1 forbidden read of the footage place refused; 12 of 12 permitted sentinels; no sentinel escaped; no local connection; the network probe's three targets refused inside the sandbox after its control reached the listener; two requests from the launcher's client, both a GET for a listed host's `robots.txt`; an unlisted address refused; nothing changed since the snapshot; it asked again for `ledger:file-tool` |
| `20261014T150505Z-on-demand-86c3` | passed | 1 step to prove; 1 of 1 file-tool target refused in a patch of its own; no sentinel escaped; no local connection; the same network results; nothing changed since the snapshot |

### The change itself, through the launcher on demand

Two runs one after another, each started with `src/bin/gr0wthlab run` from a throwaway clone of `4858c8842dd81cd080b2c4190604e97114f0fa73` in the Mac's temporary folder, with the real task definitions and network off for the agent as always.
Its inputs were throwaway ones, set with the `GR0WTHLAB_MANDU_DIR`, `GR0WTHLAB_REPTODAY_DIR`, `GR0WTHLAB_IMMERSE_DIR`, `GR0WTHLAB_FOOTAGE_DIR`, and `GR0WTHLAB_LOG_DIR` overrides: the example sets' synthetic package as Mandu, their synthetic Product code as a git checkout, and an empty folder for the other Product.
In the clone's configuration no network source was listed and outreach named the synthetic kit's network ask and three creators; nothing else differed from the commit.
Its configuration fingerprint is `d2704c9d943c203a3f91161b46baeee9f6711fdef1222e1696c8f3c1aae0600d`.

| Run | What was done by hand before it | What it showed |
| --- | --- | --- |
| `20261014T150113Z-on-demand-4363` | The calendar's text replaced with a heading and a sentence, no table; the channel plan replaced with bytes that are not UTF-8 | Sources: `2 failed`, both `unusable`, the calendar "read, but could not be used: no table with the columns Day, Asset, Angle, platform." and the channel plan "read, but could not be used: it is not UTF-8 text."; Post Drafts, Filming plan and edits, and Outreach Drafts incomplete, each naming its file; only the package review session ran, and the Sessions table gave "the calendar could not be used" for Post Drafts; one notice, `20261014-notice-run-problems`, titled "2 sources could not be used on 2026-10-14", with one line for each file and its outputs and nothing else; about $0.011 at API prices |
| `20261014T150249Z-on-demand-8606` | Both files put back as they were | Sources: `0 failed`, the two files `changed`; Post Drafts, Filming plan and edits, and Outreach Drafts complete; three sessions ran (package review, post Drafts, outreach); its notice, `20261014-notice-run-problems-2`, was only about five blocked post Drafts and had no part about sources; about $0.043 at API prices |

### What this round did not exercise

- A broken file under an open item was not run live: the open filming plan that stands on an unusable kit file, and an open message that stands on an unusable `brand-rules.json`, stand on the unit tests (`test_an_open_plan_stands_under_its_id_while_the_kit_it_is_compared_with_cannot_be_used`, `test_open_messages_stand_under_their_ids_while_the_brand_rules_cannot_be_read`).
- `brand-rules.json` that is not JSON, the competitor research folder, and Beta Cohort recruiting's read of the brand rules were not run live; each stands on unit tests, recruiting's on `test_brand_rules_that_cannot_be_read_block_a_new_draft_and_keep_an_open_one`.
- A missing calendar stands on a unit test (`test_a_missing_calendar_is_a_source_that_could_not_be_read_as_before`).
- The two live runs used synthetic inputs, never Mandu or a real Product checkout, which no check here may change; Mandu and the Product checkouts were not fingerprinted around the boundary check.
- No weekly run was made on a schedule, and Mandu's side was not shown the notice.

## Re-check after the merge with main

The branch was brought up to `main` at `0587fbd` with one merge commit, `21493b9`, which had no conflicts and brought in launcher code beyond this change's (`cycle.py`, `records.py`, a new `visibility.py`, and the reasons of refused items).
One more commit, `61f99e0`, keeps an unusable package file's own text out of its reason, following main's rule that no reason repeats the file it is about: a kit file or `brand-rules.json` that is not UTF-8 is said to be "not UTF-8 text", and a calendar day that is not a number no longer quotes its cell.
On `61f99e0132afc506209ea7de55ba2cd15a56f53f`, whose `src/` is tree `8eb9251b1c6c80e4fb2e6dfe28438437523846a8` and whose `config/` is tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`, the full unit suite passed under `/usr/bin/python3`, 1329 tests, as did ruff 0.15.20.
Both checks below ran on 2026-10-14, Mac local time (PDT), with Codex CLI 0.160.0, from this change's linked worktree at that commit, with `git status` empty before the preflight and after the check, against Mandu and the Product checkouts as they are.
The configuration fingerprint `show-config` prints there is `65c0362d7e73a1bc164001414c11a4aa2d3153d5c3658a53128ae58b4f09bb45`, the same as in the first round.
Their logs went to a folder in the Mac's temporary directory, named with `GR0WTHLAB_LOG_DIR`.

- `src/bin/gr0wthlab preflight`, started at 13:20, passed: it wrote and deleted a file in each of the six areas, refused 19 paths, refused a listing of the footage place, and reached neither listed host from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, started at 13:20, passed at its first attempt, as `20261014T202038Z-on-demand-b194`: 43 steps to prove, 14 of 14 file-tool targets refused in a patch of their own, 16 kernel denials naming the run's sentinels or the check's listeners, 1 of 1 forbidden read of the footage place refused, 12 of 12 permitted sentinels, no sentinel escaped, no local connection, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, both a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed since the snapshot.

### What this round did not exercise

The two on-demand lab runs of the first round were not made again on the merged head; the merge brought no change to the code this change adds, and its reasons now stand on the unit tests (`test_a_research_file_that_is_not_valid_text_makes_its_folder_one_failed_source`, `test_why_a_calendar_does_not_parse_never_repeats_a_cell`).
Everything the first round did not exercise is still not exercised.
