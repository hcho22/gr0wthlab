# An approved Weekly Read decision reaches the package as a proposal (US-ME12, ADR 0007)

This change makes the run that takes in the Founder's approval of a Weekly Read kill, change, resolved pair, or flex slot file one package-change proposal with the exact edit, for him to approve before Mandu changes the file ([ADR 0007](../adr/0007-an-approved-weekly-read-decision-reaches-the-package-as-a-proposal.md), the Founder's choice of 2026-10-15, "angle kill - two approvals").
It changes launcher code, the Weekly Read task definition, the sitting page's style for a code block, and the Product registry (`config/products.json`, which names `creative-log.json` for a kill's edit).
It changes nothing in the permission profile, the Codex command, or the fetch policy, and the exchange stays at version 8.

Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran.
A run identifier carries its time in UTC.

| Commit | Full hash | `src` tree | `config` tree |
| --- | --- | --- | --- |
| `main` before this change | `3789b3ffb769e64696af8cf7f0e95e414f047e43` | `1b5dc00390cddd5029ce31f1248b2fa31c7b851e` | `e3b97b510841032f95c57c5f8f61285f8906e657` |
| The filing | `23ce675b6beb903f8779048716a709565d775d61` | `3b189357074285c9a6c243befb8b7467abe88f82` | `28263a1b24ee1ecb5bf00469884bdc97aa7edc33` |
| The page's code blocks | `7eee0da108d3ba15e17f0398d9460f1b76cf3b12` | `81ec9cb1372aa90ea131a4628488c563ac15ddf9` | `28263a1b24ee1ecb5bf00469884bdc97aa7edc33` |
| The new Hook's checks | `1a2497acaa5a0708723ffdc4a8b977d27f83963c` | `a34d30917e0f841deb8ae97e7767517cc24a174c` | `28263a1b24ee1ecb5bf00469884bdc97aa7edc33` |
| The merge of `main` (second round) | `e6b70f9fa4df9e434e8b7403e98616ca72753183` | `1077d54c9bf80b635e51259d999b7ab675e1184a` | `28263a1b24ee1ecb5bf00469884bdc97aa7edc33` |

## First round

### The labs

Each lab was a throwaway clone of the commit named, in the Mac's temporary folder, with one commit added in it: the configuration `make_repo` in `src/tests/fakes.py` gives (no network source, no outreach message, no Product that films).
Mandu was the synthetic kit of `src/examples/post-drafts/`, RepToday's code was its synthetic code, and the footage place, the log folder, and the production clone were throwaway locations, each set with its `GR0WTHLAB_*` override; a clone that is not the production clone saves no records.
The window's first sitting was Sunday 2026-10-04 for the day-7 read, with the calendar kept to days 1 to 5 and the flex slot as `fakes.keep_days` keeps it, then moved to Sunday 2026-09-27 with the whole calendar for the day-14 read, so each read was due on 2026-10-15.
Each read's numbers were the Weekly Read example set's (`src/examples/weekly-read/files/results/`), written into `ledger/founder/results/` as the sitting page writes them; every number is synthetic.
Where no real agent is named, the agent was the repository's no-model stand-in (`tests.fakes.install_codex`), which wrote the example set's day-7 memo and a day-14 memo with P04 killed, P07 changed, AB-2 resolved with leg A leading, and AB-1 reposted.
Every decision of the Founder's in these three labs was given on the page `src/bin/gr0wthlab sitting` served from the clone, in Chrome driven with `chrome-devtools-axi`, and read back from its record in `ledger/founder/decisions/`.

### The reproduction on `main`

On `3789b3ffb769e64696af8cf7f0e95e414f047e43`:

| Run | What the records showed |
| --- | --- |
| `20261015T203929Z-on-demand-562d` | The day-7 read: 6 decision items queued, the flex slot earned by P03. On the page the flex item's Touches read "Day 14 of the calendar, `projects/RepToday/gtm/05-social-pmf/cadence-14-day.md`", and it was approved. |
| `20261015T204058Z-on-demand-475a` | The day-14 read: 9 decision items queued, and the flex approval taken in. The kill item's Touches read "P04's row in `projects/RepToday/gtm/05-social-pmf/angles.md`, which Mandu changes if you approve". On the page the kill of P04, the change of P07, and AB-2 resolved were approved. |
| `20261015T204135Z-on-demand-e03a` | 3 decisions taken in; the queue's four approved decisions closed as approved, and no `package-change-proposal` in it, open or closed. The SHA-256 of all 16 files of the lab's Mandu were the same before the day-14 run and after this one. |

### The same flow on this change

On `23ce675b6beb903f8779048716a709565d775d61`; before the third sitting, the two files of `7eee0da108d3ba15e17f0398d9460f1b76cf3b12` (`src/gr0wthlab/page.py` and `src/sitting/page.css`) were copied into the clone's working tree, so the page from then on was that commit's.

| Run | What the records showed |
| --- | --- |
| `20261015T213133Z-on-demand-b3fd` | The day-7 read: 6 decision items. Each queue entry held its line, as `{"section": "Flex slot", "result": "earned", "decision": "test", "earned_by": "P03"}` for the flex slot, and the read's date. The flex item's Touches read "Nothing yet: approving it has the next run file a package-change proposal with the exact edit that puts P03 in the flex slot of the calendar, `projects/RepToday/gtm/05-social-pmf/cadence-14-day.md`, for you to approve before Mandu changes the file." It was approved on the page. |
| `20261015T213206Z-on-demand-2100` | The day-14 read: 9 decision items, AB-2's asked as "Weekly Read day 14: AB-2, resolved, leg A leads: keep". The flex approval was taken in and `20261015-weekly-read-flex` filed, origin `weekly-read/20261015-weekly-read-07-flex`. The Weekly Read memo row: "memo `weekly-reads/window-1-read-14.md`; 9 decision items queued; package-change proposals owed by approved decisions: 1 of 1 filed". The kill, change, resolved pair, and repost items' Touches each said what approving it does; AB-1's, a repost, read "Nothing: approving changes no package file, and AB-1 is not declared resolved". On the page the kill of P04, the change of P07, AB-2 resolved, AB-1's repost, P02's keep, and P01's test were approved. |
| `20261015T213330Z-on-demand-5c7a` | The Weekly Read session ran with no memo due; its brief said "No memo is due this run: the Founder has decided items of the window 1 day-14 Weekly Read, so its memo stands as it is. Write none." and asked for P07's new Angle as P08. The stand-in wrote it, and 3 proposals were filed: `20261015-weekly-read-pair-ab-2`, `20261015-weekly-read-kill-p04`, and `20261015-weekly-read-change-p07` (`new_angle: yes`); none for the repost, the keep, or the test. The row: "package-change proposals owed by approved decisions: 3 of 3 filed". |
| `20261015T213552Z-on-demand-9200` | After all four proposals were approved on the page: each closed as approved. |
| `20261015T213608Z-on-demand-020b` | After each approved proposal was applied to the lab's Mandu as Mandu's reader applies one, each "from" text found exactly once and replaced: exactly 4 files of the lab's Mandu differed from before, and the kit read P08 in the bank and P03 on day 14. The Sources line read "3 changed", and no proposal was filed: 4 in the queue, as before. |

### A rejected decision on this change

On `1a2497acaa5a0708723ffdc4a8b977d27f83963c`, the same lab, with each decision rejected on the page with the reason "Not this window.":

| Run | What the records showed |
| --- | --- |
| `20261015T214923Z-on-demand-bebf` | The day-7 read; the flex slot rejected. |
| `20261015T214949Z-on-demand-03b3` | The day-14 read; no proposal filed. The kill of P04, the change of P07, and AB-2 resolved rejected. |
| `20261015T215013Z-on-demand-5474` | 3 decisions taken in, the four closed as rejected, no `package-change-proposal` in the queue, and the SHA-256 of every file of the lab's Mandu the same as before the run. |

### What the page showed, and what was fixed

The page was used at 1280 wide in dark, and at 390 wide in light with Chrome's device emulation; the page never scrolled sideways.

- A proposal's code block kept each line on one line and scrolled it inside its frame with no scrollbar shown, so a calendar row was cut off at the frame's edge and an Angle bank row could not be read whole.
  Each line of a block is now its own line that wraps, with its wrapped part indented under its start (`7eee0da108d3ba15e17f0398d9460f1b76cf3b12`): the change's two rows read as two, and at 390 wide too.

### Every edit, against the shape of the real package files

The real `angles.md`, `ab-pairs.md`, `cadence-14-day.md`, and `creative-log.json` of RepToday's `gtm/05-social-pmf/`, and its `brand-rules.json`, were copied from `~/Mandu` into a folder of the Mac's temporary directory, read-only, and nothing of them is in this repository.
Their SHA-256: `angles.md` `73649503bc9c48682a033b5dcd169f74dba60582a004c881f8e65cb91c0271b1`, `ab-pairs.md` `06ef86f0f3adf5c044ce3b27f5481e76e0969ce46eb86c55eda550422cb154ab`, `cadence-14-day.md` `ce350354ea269d4ec3ac9b89008cc8ba200af9cb13c0b4610c352e0215a35667`, `creative-log.json` `412dd26340322fa58586cf9aacd4e06e44ed203ffaf7eca93ab77cb39a054d79`.
A scratch script made, with `src/gr0wthlab/weekly_changes.py`, every edit a decision can file against them: a kill of each of the log's 16 Angles, a change of each of the bank's 16 (a new row with that Angle's pain and a Hook of its own), each of the 6 pairs resolved by each leg, and the flex slot earned by each of the bank's 16 Angles and not earned.
For each it checked that the text it replaces appears exactly once in the file, that the proposal is a valid item, and the launcher's own check that applying it changes what the decision fixes and nothing else.

- Its first pass, on the code before `23ce675b6beb903f8779048716a709565d775d61` was committed, refused 10 of the 12 pair edits, every pair but the file's last: adding a line to one pair's section moved every later section down, and the check compared their line numbers.
  The check now compares each section's content; `test_a_resolved_pair_before_another_moves_the_later_section_down_and_changes_nothing_in_it` holds it.
- On `1a2497acaa5a0708723ffdc4a8b977d27f83963c`, with the real brand rules held to each new Hook: 16 kills, 16 changes, 12 pair resolutions, and 17 flex slots, 61 edits, made and checked, and none refused.
  Each kill's edit spans its record from the `angle_id` line to the `status` line, 12 lines, so it names one record of the 16, each of which has a `status` line.

### The agent's work under the task definition's change

The task definition's change has a resolved pair's line name the leg whose Hook leads, and has the Weekly Read session write a changed Angle's new row when the brief asks for one.
The Weekly Read has no example set the gate re-runs, so these were measured as `AGENTS.md` asks, by what the launcher counted of each session, in throwaway clones like the labs above with the real agent in the run measured and the stand-in in every run before it, and the Founder's decisions written as the page writes them.
In every memo lab day 10's viewed rate was given as 38%, so AB-2's legs, 81% and 38%, differ widely.
Each run started two sessions, the package review and the Weekly Read; the agent time is the Weekly Read session's, the cost the whole run's, and every Weekly Read session read 4 of 4 package files and closed "Session: complete".

| Code | Run | What the agent did | Agent time | Cost |
| --- | --- | --- | --- | --- |
| `main` | `20261015T213902Z-on-demand-4cef` | Memo passed; AB-2 "repost" | 1 min 35 s | about $0.022 |
| `main` | `20261015T213902Z-on-demand-6b0a` | Memo passed; AB-2 "resolved." | 1 min 28 s | about $0.023 |
| `main` | `20261015T214150Z-on-demand-f486` | Memo passed; AB-2 "resolved." | 1 min 12 s | about $0.033 |
| `7eee0da` | `20261015T213902Z-on-demand-f49c` | Memo passed; AB-2 "resolved, leg A leads." | 1 min 20 s | about $0.025 |
| `7eee0da` | `20261015T213902Z-on-demand-b022` | Memo passed; AB-2 "resolved, leg A leads." | 1 min 20 s | about $0.025 |
| `7eee0da` | `20261015T214148Z-on-demand-5be1` | Memo passed; AB-2 "resolved, leg A leads." | 52 s | about $0.021 |
| `7eee0da` | `20261015T213902Z-on-demand-5128` | P07's new Angle filed as P08 | 34 s | about $0.015 |
| `7eee0da` | `20261015T214052Z-on-demand-344a` | P07's new Angle filed as P08 | 35 s | about $0.022 |
| `7eee0da` | `20261015T214216Z-on-demand-8d58` | P07's new Angle filed as P08 | 36 s | about $0.021 |
| `7eee0da`, real bank | `20261015T213902Z-on-demand-3282` | P07's new Angle filed as P17 | 1 min 15 s | about $0.026 |
| `7eee0da`, real bank | `20261015T214142Z-on-demand-bb52` | P07's new Angle filed as P17 | 58 s | about $0.030 |
| `1a2497a` | `20261015T214854Z-on-demand-9070` | P07's new Angle filed as P08 | 38 s | about $0.016 |
| `1a2497a` | `20261015T214854Z-on-demand-6b80` | P07's new Angle filed as P08 | 29 s | about $0.014 |
| `1a2497a` | `20261015T214854Z-on-demand-644a` | P07's new Angle filed as P08 | 30 s | about $0.015 |
| `1a2497a` | `20261015T214854Z-on-demand-fec4` | P07's new Angle filed as P08 | 35 s | about $0.021 |
| `1a2497a`, real bank | `20261015T214854Z-on-demand-b224` | P07's new Angle filed as P17 | 48 s | about $0.025 |
| `1a2497a`, real bank | `20261015T214854Z-on-demand-7a45` | P07's new Angle filed as P17 | 39 s | about $0.019 |
| `1a2497a`, real bank | `20261015T214854Z-on-demand-d687` | P07's new Angle filed as P17 | 44 s | about $0.021 |

In the "real bank" runs the lab's Mandu held copies of the real `angles.md` and `ab-pairs.md`, and in the last three also of `brand-rules.json`, so P07 was the real bank's P07 and the new number P17.
Every new row carried P07's pain and source as the bank has them and a Hook of its own in one quoted line.
In run `5128` the new Hook was a question, which the brand lint refuses in every post's Hook, so once approved every post Draft of that Angle would have been blocked; `1a2497acaa5a0708723ffdc4a8b977d27f83963c` holds a new Hook to the brand lint and to one quoted line before it is filed, says so in the task definition, and in its seven runs every new Hook passed.
The memo runs show the pair line naming its leg in 3 of 3 sessions, with every memo passing its checks on both sides.
In each of the seven runs on `1a2497a` the Weekly Read session ran its brief's `check-work` command, and Codex's record of it holds the line "OK new Angle P08 for `20261015-weekly-read-14-p07`: its proposal can be filed", or P17 on the real bank, and no problem line.

### The boundary

From this work's linked worktree at `1a2497acaa5a0708723ffdc4a8b977d27f83963c`, against Mandu and the Product checkouts as they are, with `git status` empty before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`.

- `src/bin/gr0wthlab preflight`, run four times from 14:51 to 14:52, passed each time: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 14:52:12 to 14:53:18, passed at its first attempt as `20261015T215213Z-on-demand-1954`: 49 steps to prove, 50 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials and no shell target without one, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- The whole unit suite ran under `/usr/bin/python3`, Python 3.9.6, one process for each test module, in a clone of `1a2497acaa5a0708723ffdc4a8b977d27f83963c`: 1495 tests in 54 modules, none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab` passed, with ruff 0.15.20.
- CI's run on Linux with the latest Python was not part of this round.

### A correction to the Weekly Read's record

[The Weekly Read's record](20261014-gr0wthlab-weekly-read.md#what-the-browser-showed-and-what-was-fixed) says that after its fix "only a kill or a change says" that Mandu changes an Angle's row in the Angle bank if approved.
That was not so of a kill or a change either: Mandu applies only an approved package-change proposal, so approving a Weekly Read decision changed no package file.
Since `23ce675b6beb903f8779048716a709565d775d61` a kill's, a change's, a resolved pair's, and the flex slot's Touches each say that approving it has the next run file a package-change proposal with the exact edit, for the Founder to approve before Mandu changes the file, as the runs above show.

### What this round did not exercise

- No real post has gone out and no real Weekly Read has run, so no proposal was filed from a real decision, and none was applied to the real package; every application here was to a lab's copy, by a script that does what Mandu's reader says it does.
- Mandu's reader itself, merged for version 8 in https://github.com/hcho22/Mandu/pull/13, was not run on these proposals; its skill says it applies an approved proposal by finding its "from" text exactly once and editing only the files `## Touches` lists, which is what each of these proposals gives it.
  It also says approving a Weekly Read decision changes no package file by itself, which stays true, and says nothing of the proposal that now follows.
- The real agent never wrote a day-14 memo that killed or changed an Angle and had it approved and filed in one lab; the memo runs and the new-Angle runs above are separate labs, and the stand-in wrote the memos that the filing labs rest on.
- A new Angle that fails its checks in a live run: the real agent's rows all passed, so its removal with only its name and reasons kept stands on `test_a_change_whose_new_angle_is_not_filed_still_owes_it_and_says_why`, as does a Weekly Read session due only for a new Angle that falls short.
- A flex decision once the next window's calendar is in force, a kill whose record already says killed, and an edit whose text the package no longer holds exactly once stand on `tests.test_weekly_changes` and the code's own checks.
- A scheduled run, the real production clone, a browser other than Chrome, and the sitting page in Safari.

## Second round: after the merge of `main`

`main` had moved to `2af81a45181bc0ddb297cf604cecf73ed7d07fee` with three pull requests that this change had not seen: the Hook claim fix, its live-check record, and the guidance that no item supersedes an Instructions notice or a Weekly Read decision (https://github.com/hcho22/gr0wthlab/pull/28).
The branch took `main` in with one ordinary merge commit, `e6b70f9fa4df9e434e8b7403e98616ca72753183`, with no conflict.
Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran; a run identifier carries its time in UTC.

### What the merge changed that the Weekly Read session reads

- `src/instructions/weekly-run/items.md`, which the Weekly Read session's task definition holds as a shared part: an item that supersedes a Weekly Read decision or an Instructions notice is refused, and the exact repeat rule.
- The brief's list of open Review Queue items (`item_lines` in `src/gr0wthlab/report.py`): a Weekly Read decision is marked as changing only through the Weekly Read memo, and each package-change proposal is listed with its item file.
- Not read by the Weekly Read session: `post-drafts.md`, which the Hook claim fix changed, since only the Post Drafts session holds it.

The two sets of words say different things and none twice.
The task definition's `weekly-read.md` says that approving a decision changes no package file by itself and that the launcher files the package-change proposal, and `items.md` and the brief say what an item may supersede.
In the lab runs below the brief marks the flex proposal this change files as "package-change-proposal, filed by the launcher" with the path of its item file, and a Weekly Read decision as "which changes only through the Weekly Read memo".
Nothing in `weekly-read.md`, `docs/operations.md`, or `AGENTS.md` needed to change for the merge.

### The labs, and a first attempt that is not counted

Each lab was built as in the first round, with `tests.fakes` and the repository's no-model stand-in for every run before the real agent's, from a clone of `e6b70f9fa4df9e434e8b7403e98616ca72753183` with one lab commit on it.
There were ten labs, of the three kinds the first round measured: three on the day-14 memo, four on a changed Angle's new row with the synthetic Angle bank, and three on it with copies of the real Angle bank and A/B pairs file in the lab's Mandu.

The first attempt put the labs in a scratch folder under `/private/tmp`, which `config/guardrails/runtime.json` denies to the agent (`:slash_tmp`).
Five of its ten sessions closed after 6 to 13 seconds with nothing written, each in its own words as unable to read its brief, and the other five read it.
Codex's record of one of the five (`20261016T045242Z-on-demand-5465`) shows a `cat` of the brief by a path relative to its working folder failing, one `ls`, and the agent then saying the brief is under `/private/tmp`, a path the policy denies.
That is where the lab was, not the provider refusing a request, and no run of this attempt is counted.
The labs were removed and rebuilt in the Mac's temporary folder, where the first round's labs were.

| Run | Lab | What the records showed |
| --- | --- | --- |
| `20261016T045054Z-on-demand-1877` | memo 1 | Read the brief, wrote the memo |
| `20261016T045054Z-on-demand-63c9` | memo 2 | Read the brief, wrote the memo |
| `20261016T045054Z-on-demand-eb96` | memo 3 | Read the brief, wrote the memo |
| `20261016T045054Z-on-demand-a3de` | new Angle 1 | Closed after 6 s, brief unread, no new Angle |
| `20261016T045054Z-on-demand-609b` | new Angle 2 | Closed after 13 s, brief unread, no new Angle |
| `20261016T045112Z-on-demand-b10b` | new Angle 3 | Closed after 7 s, brief unread, no new Angle |
| `20261016T045228Z-on-demand-0ebc` | new Angle 4 | Read the brief, filed the new Angle |
| `20261016T045234Z-on-demand-5bca` | new Angle, real bank 1 | Read the brief, filed the new Angle |
| `20261016T045242Z-on-demand-5465` | new Angle, real bank 2 | Closed after 13 s, brief unread, no new Angle |
| `20261016T045310Z-on-demand-ddef` | new Angle, real bank 3 | Closed after 10 s, brief unread, no new Angle |

### The agent's work with the merged task definition and brief

As in the first round, these are measured by what the launcher counted of each session.
Each run started two sessions, the package review and the Weekly Read; the agent time is the Weekly Read session's, the cost the whole run's, and every Weekly Read session read 4 of 4 package files and closed "Session: complete".
In every memo lab day 10's viewed rate was 38%, so AB-2's legs, 81% and 38%, differ widely.

| Run | What the agent did | Agent time | Cost |
| --- | --- | --- | --- |
| `20261016T045816Z-on-demand-e196` | Memo passed; AB-2 "resolved, leg A leads." | 1 min 1 s | about $0.023 |
| `20261016T045816Z-on-demand-ee11` | Memo passed; AB-2 "resolved, leg A leads." | 1 min 3 s | about $0.031 |
| `20261016T045816Z-on-demand-fefe` | Memo passed; AB-2 "resolved, leg A leads." | 1 min 7 s | about $0.026 |
| `20261016T045816Z-on-demand-d82f` | P07's new Angle filed as P08 | 35 s | about $0.023 |
| `20261016T045816Z-on-demand-65f2` | P07's new Angle filed as P08 | 26 s | about $0.013 |
| `20261016T045942Z-on-demand-3231` | P07's new Angle filed as P08 | 31 s | about $0.019 |
| `20261016T050021Z-on-demand-5af9` | P07's new Angle filed as P08 | 27 s | about $0.018 |
| `20261016T050043Z-on-demand-9b22`, real bank | P07's new Angle filed as P17 | 37 s | about $0.019 |
| `20261016T050043Z-on-demand-b855`, real bank | P07's new Angle filed as P17 | 41 s | about $0.027 |
| `20261016T050057Z-on-demand-2b16`, real bank | P07's new Angle filed as P17 | 33 s | about $0.020 |

- The memo runs show the pair line naming its leg in 3 of 3 sessions, with every memo passing its checks, and each queued 9 decision items with "package-change proposals owed by approved decisions: 1 of 1 filed" (the flex slot approved before the run).
- In each of the seven new-Angle runs the Weekly Read session ran its brief's `check-work` command, and Codex's record of it holds "OK new Angle P08 for `20261015-weekly-read-14-p07`: its proposal can be filed", or P17 on the real bank, followed by "1 checked, 0 with problems".
  The Weekly Read row read "no memo this run: the Founder has decided items of the window 1 day-14 Weekly Read, so its memo stands as it is; package-change proposals owed by approved decisions: 1 of 1 filed" in each, and `20261015-weekly-read-change-p07` was in the queue.
- These counts are within what the first round counted for the same labs on `1a2497acaa5a0708723ffdc4a8b977d27f83963c`: memo sessions of 52 s to 1 min 20 s there and 1 min 1 s to 1 min 7 s here, new-Angle sessions of 29 s to 48 s there and 26 s to 41 s here.
  Nothing in these counts shows the merged `items.md` or brief lines changing what the session read or wrote.

### The boundary

From this work's linked worktree at `e6b70f9fa4df9e434e8b7403e98616ca72753183`, against Mandu and the Product checkouts as they are, with `git status` empty before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`, the same as in the first round.

- `src/bin/gr0wthlab preflight`, run three times from 22:03 to 22:04 and the last read in full, passed: six areas writable, 22 paths refused, no breach, a listing of the footage place refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 22:04:04 to 22:04:50, passed at its first attempt as `20261016T050405Z-on-demand-014b`: 49 steps to prove, 30 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- The whole unit suite ran under `/usr/bin/python3`, Python 3.9.6, one process for each test module, at the merge commit: 1498 tests in 54 modules, none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab` passed, with ruff 0.15.20.
- CI's run on Linux with the latest Python was not part of this round.

### What this round did not exercise

- Everything the first round did not exercise stands as it is.
- A session that exits within seconds with a 429 in its Codex log was not seen; the five early closes of the first attempt were the lab's placement, as above.
- The full week-14 flow of the first round (the sitting page, each decision kind approved and rejected, each proposal applied to a lab copy of the package) was not run again on the merged head; the merge changed no code that files, checks, or applies those proposals, and the unit tests that hold them passed.

## Third round: the review's two fixes

The review of the merged head found two gaps, and this round closes both on top of `a62e901c1679a7486e6911214ee854cf5dfdf7b2`:

- A change's proposal added the new Angle to the Angle bank alone, while a kill marks the Angle's record in `creative-log.json`, so a later approved kill of the new Angle could never be filed.
  The proposal now carries a second exact edit, the new Angle's record at the end of `creative-log.json` in the shape of the changed Angle's record, so one approval applies both ([ADR 0007](../adr/0007-an-approved-weekly-read-decision-reaches-the-package-as-a-proposal.md) records the choice and why).
- A flex decision approved once its window was no longer the one in force filed nothing and no run said so, and an open flex proposal stayed open once its window had passed.
  Now the run that finds such an approval files nothing and says so in its report and its notice, once, and an open flex proposal whose window has passed is withdrawn before the run takes in any decision, so an approval given on it at a sitting is kept on a superseded item, which Mandu never acts on.

Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran; a run identifier carries its time in UTC.
The fix was not committed when they ran: its `src` tree was `4da6aefe5653699ceabab4f6e64da661a5ff170e` and its `config` tree `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a`, written from a throwaway index over `a62e901c1679a7486e6911214ee854cf5dfdf7b2` with the working tree's `src` and `config`.

### The failures before the fix

Three new tests were run in a scratch copy of the working tree with the four launcher files the fix changes (`weekly_changes.py`, `cycle.py`, `report.py`, and `weekly_read.py` under `src/gr0wthlab/`) put back as `a62e901c1679a7486e6911214ee854cf5dfdf7b2` has them.
Each failed there, and each passes on the fix.

| Test | What it showed before the fix |
| --- | --- |
| `ChangeThenKillTest.test_a_new_angle_a_change_added_is_killed_by_its_own_approved_kill_later` | The change of P07 into P08 filed a proposal whose edits named `angles.md` alone, not `creative-log.json` |
| `test_a_flex_slot_approved_once_its_window_has_passed_files_nothing_and_says_so_once` | With window 2 in force, the window 1 flex approval was taken in, nothing was filed, and the run report had no line for it |
| `test_an_open_flex_slot_proposal_is_withdrawn_once_its_window_has_passed_and_its_approval_is_never_acted_on` | With window 2 in force, the window 1 flex proposal the Founder approved closed as `approved`, with no `withdrawn` |

The two flex tests are whole runs of `cycle.Cycle` with the no-model stand-in, as `src/bin/gr0wthlab run` starts one; the first drives `weekly_changes.prepare` and `weekly_changes.take`, the two steps a run calls, on a copy of the synthetic kit, and applies each proposal as Mandu's reader does.

### The new record, against the shape of the real package files

The same five real files as in the first round were copied from `~/Mandu` into a folder of the Mac's temporary directory, read-only, and nothing of them is in this repository; their SHA-256 were the four listed in the first round, unchanged.
A scratch script made, with `src/gr0wthlab/weekly_changes.py`, a change of each of the bank's 16 Angles into P17, the number after the bank's and the log's, with a Hook of its own.

- All 16 rows passed the row checks with the real brand rules, and all 16 made both edits, each text found exactly once and checked by the launcher's own check that applying it changes nothing else.
- Each new record had the changed Angle's record's 14 fields in their order, and the changed Angle's platform as that record names it.
- On each log with its edit applied, the kill of P17 was made, checked, and applied, and the record read `"killed"` with both read dates: 16 of 16.
- With each new row's platform moved to the other one, each of the 16 new records named its platform as the log's other records do, and none was refused.

### The boundary

From the gate's linked worktree at `a62e901c1679a7486e6911214ee854cf5dfdf7b2` with the fix in its working tree, against Mandu and the Product checkouts as they are, with the SHA-256 of `git status --porcelain` the same before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`.
`show-config` printed the configuration fingerprint `32af654b78b3cfc5e0c257fc93ed76e5c5f6a2c6efe42f2898b6f270e2276e43`; the command it covers names the checkout's own path, and this worktree is not the one the earlier rounds ran from.

- `src/bin/gr0wthlab preflight`, run twice at 22:44, passed each time: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 22:45:02 to 22:45:52, passed at its first attempt as `20261016T054504Z-on-demand-4f7c`: 49 steps to prove, 28 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the working tree: `tests.test_weekly_changes` (19 tests), `tests.test_weekly_read` (28), `tests.test_weekly_read_cycle` (17), `tests.test_weekly_read_examples` (3), and `tests.test_sessions` (35), none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` passed, with ruff 0.15.20.
- The whole unit suite and CI's run were not part of this round.

### What this round did not exercise

- No lab ran `src/bin/gr0wthlab run` or the sitting page on this round's code: the change-then-kill sequence and both flex cases stand on the tests above.
- No real agent ran on this round's code but the boundary check's probe agent; the task definition and the brief's section on new Angles did not change.
- Mandu's reader was not run on a proposal with two edits; its skill says it edits only the files `## Touches` lists, and a change's Touches now lists both.

## Fourth round: one Hook for one Angle, across new Angles

The review of the third round found that a new Angle's Hook was held only to the Angle bank and the A/B pairs as the run read them, so two new Angles filed in one run, or one filed while an earlier change's proposal still waited to be applied, could share a Hook.
On top of `2e3d6e4df23e03c3528ed378e598a6f0edc560ff`, the take-in that a run and `check-work` both call now holds each new Hook also to every new Angle filed earlier in it and to the Hook of every change proposal that is open or approved, which each such proposal's queue entry now keeps (`weekly_change.hook`).
A rejected proposal's Hook belongs to no Angle, so it does not count.
`AGENTS.md` now says the proposal of an approved change declares `new_angle: yes` with the changed Angle's own row as its sourced pain, as `docs/mandu-exchange.md` already did.

Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran; a run identifier carries its time in UTC.
The fix was not committed when they ran: its `src` tree was `4d471dd73d67c0463fa842821d5e510447d06319` and its `config` tree `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a`, written from a throwaway index over `2e3d6e4df23e03c3528ed378e598a6f0edc560ff` with the working tree's `src` and `config`.

### The failure before the fix

`ChangeThenKillTest.test_no_two_new_angles_share_a_hook_in_one_run_or_while_a_proposal_that_adds_one_stands` was run in a scratch copy of the working tree with `src/gr0wthlab/weekly_changes.py` put back as `2e3d6e4df23e03c3528ed378e598a6f0edc560ff` has it, and ended with an error there: the first change's proposal was filed with no Hook in its queue entry.
On the fix it passes: of two changes written with the same Hook in one take-in the second is refused, again at the next take-in while the first proposal is open, and filed once the Founder has rejected the first.

### The boundary

From the gate's linked worktree at `2e3d6e4df23e03c3528ed378e598a6f0edc560ff` with the fix in its working tree, against Mandu and the Product checkouts as they are, with the SHA-256 of `git status --porcelain` the same before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `32af654b78b3cfc5e0c257fc93ed76e5c5f6a2c6efe42f2898b6f270e2276e43`, the same as in the third round.

- `src/bin/gr0wthlab preflight`, run twice at 22:58, passed each time: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 22:58:51 to 23:00:10, passed at its first attempt as `20261016T055853Z-on-demand-aaff`: 49 steps to prove, 29 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the working tree: `tests.test_weekly_changes` and `tests.test_weekly_read`, 48 tests, none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` passed, with ruff 0.15.20.
- The whole unit suite and CI's run were not part of this round.

### What this round did not exercise

- No real agent wrote two new Angles in one session; the refusal stands on the test above, which drives the take-in a run calls.
- A change proposal filed before this round keeps no Hook in its queue entry, so it would not count; none was filed outside a lab.

## Fifth round: a Hook spoken inside a stage direction

The review of the fourth round found that the Angle bank's side of the one-Hook-one-Angle check compared each bank Hook cell whole, so a cell that wraps its spoken Hook in a stage direction never matched a new Angle that repeats the spoken words, and such a new Angle could be filed holding another Angle's Hook.
On top of `c54361acd11cc8698b39809a98707efb63649723`, `known_hooks` now also counts each quoted text in a bank Hook cell, with the pattern the kit already reads an A/B pair leg's Hook with (`kit.QUOTED`), and `docs/operations.md` says so.
The other half of that rule, a new Angle filed earlier in the same take-in or by a change proposal that is open or approved, is the fourth round's, and its test passed again here with no change to it.

Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran; a run identifier carries its time in UTC.
The fix was not committed when they ran: its `src` tree was `264b6704745d7fa7b3ef604826bc1c9fb79a56b4` and its `config` tree `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a`, written from a throwaway index over `c54361acd11cc8698b39809a98707efb63649723` with the working tree's `src` and `config`.

### The failure before the fix

- `EditTest.test_a_new_angle_s_hook_is_refused_when_a_bank_hook_cell_speaks_it_inside_a_stage_direction`, on the synthetic bank with P07's Hook cell put inside a stage direction, was run in a scratch copy of the working tree with `src/gr0wthlab/weekly_changes.py` put back as `c54361acd11cc8698b39809a98707efb63649723` has it: the new Angle that repeats P07's spoken words had no problem there, and the test failed.
  On the fix it passes, and the same row with a Hook of its own still has none.
- The real `angles.md` and `ab-pairs.md` of RepToday's `gtm/05-social-pmf/` were copied from `~/Mandu` into a folder of the Mac's temporary directory, read-only, and removed after; their SHA-256 were the first round's.
  The bank has 1 Hook cell that is not one quoted line, and it holds 1 quoted text.
  A change of that Angle whose new row repeats that text as its Hook, every other cell the Angle's own, was refused 0 times of 1 on `c54361acd11cc8698b39809a98707efb63649723` and 1 time of 1 on the fix, with the reason that the Hook is one the Angle bank already holds.

### The boundary

From the gate's linked worktree at `c54361acd11cc8698b39809a98707efb63649723` with the fix in its working tree, against Mandu and the Product checkouts as they are, with the SHA-256 of `git status --porcelain` the same before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `32af654b78b3cfc5e0c257fc93ed76e5c5f6a2c6efe42f2898b6f270e2276e43`, the same as in the third and fourth rounds.

- `src/bin/gr0wthlab preflight`, run twice at 23:09, passed each time: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 23:09:58 to 23:10:51, passed at its first attempt as `20261016T060959Z-on-demand-1e13`: 49 steps to prove, 28 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the working tree: `tests.test_weekly_changes`, 21 tests, none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` passed, with ruff 0.15.20.
- The whole unit suite and CI's run were not part of this round.

### What this round did not exercise

- No real agent wrote a new Angle for a change of an Angle whose Hook cell is a stage direction; the refusal stands on the test and the scratch check above, which call the check the take-in runs.

## Sixth round: an A/B pairs file that reads and does not parse

The review of the fifth round found that the A/B pairs side of the one-Hook-one-Angle check failed open: when the A/B pairs file read but did not parse, the take-in checked a new Angle's Hook against no pair at all and filed the change, and nothing before the session parsed that file.
On top of `f1c546358cbdb41d39d8d1ef34bed1b85ab71564`, one check (`weekly_changes.unusable`) now says why each package file a change edits or is checked against could not be used: an Angle bank or A/B pairs file that does not parse, brand rules that are not the brand rules, or a creative log with no list of Angle records.
The plan made before the sessions uses it, so such a change waits with the file named and no session is asked for its new Angle, and so does the take-in of a change, which is what `check-work` runs on the plan recorded before the session, so that dry run names the file too instead of checking against no pairs, raising on an Angle bank that does not parse, or skipping the brand lint.
A resolved pair's decision, which also needs the A/B pairs file, waits with the same reason its own edit gave before.
The pairs file is one the post kit reads every run, and that read already marks its source line `unusable`; since the change's gap names the file, the line also names the Weekly Read memo, as the rule for such a file says, and `docs/operations.md` says so.

Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran; a run identifier carries its time in UTC.
The fix was not committed when they ran: its `src` tree was `2288f39cadfbd7ca6187196893590eb7b978e66d` and its `config` tree `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a`, written from a throwaway index over `f1c546358cbdb41d39d8d1ef34bed1b85ab71564` with the working tree's `src` and `config`.

### The failures before the fix

Two new tests were run in a scratch copy of the working tree with `src/gr0wthlab/weekly_changes.py` put back as `f1c546358cbdb41d39d8d1ef34bed1b85ab71564` has it, the synthetic A/B pairs file in each with AB-2's leg B line lost and the new Angle for P07's change written with AB-1's leg B Hook.
Each failed there, and each passes on the fix.

| Test | What it showed before the fix |
| --- | --- |
| `ChangeThenKillTest.test_a_pairs_file_that_reads_and_does_not_parse_leaves_a_change_owed_and_names_the_file` | `check-work`'s dry run on the recorded plan filed the change with no problem, as `change-p07` |
| `ApprovedDecisionRunTest.test_a_pairs_file_that_reads_and_does_not_parse_files_no_change_and_is_named_as_the_weekly_read_s_gap` | The run started the Weekly Read session for the new Angle |

On the fix, the whole run starts no Weekly Read session and files no change, its Weekly Read memo row reads incomplete with the pairs file's source line first and then the change's own gap naming the file and the parse error, the file's source line reads `unusable` with that error, and the notice's line for the file names the Weekly Read memo among what it left incomplete.

### The boundary

From the gate's linked worktree at `f1c546358cbdb41d39d8d1ef34bed1b85ab71564` with the fix in its working tree, against Mandu and the Product checkouts as they are, with the SHA-256 of `git status --porcelain` the same before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `32af654b78b3cfc5e0c257fc93ed76e5c5f6a2c6efe42f2898b6f270e2276e43`, the same as in the third to fifth rounds.

- `src/bin/gr0wthlab preflight`, run twice at 23:23, passed each time: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 23:23:37 to 23:24:26, passed at its first attempt as `20261016T062339Z-on-demand-1d8c`: 49 steps to prove, 28 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the working tree: `tests.test_weekly_changes` and `tests.test_weekly_read`, 51 tests, none failed and none skipped.
- `ruff check` and `ruff format --check` on `src` passed, with ruff 0.15.20.
- The whole unit suite and CI's run were not part of this round.

### What this round did not exercise

- No lab ran `src/bin/gr0wthlab run` or `check-work` from a terminal on this round's code: the whole run above is `cycle.Cycle` with the no-model stand-in, and the dry run is the restore and take-in `check-work` calls.
- The real A/B pairs file was not altered or read for this round; only the synthetic one was broken, in each test's own copy.

## Seventh round: a code block's indented lines, and a Touches that names two files

The test of the sixth round's code found that the sitting page's code block, which this change made wrap, garbled an indented line of an exact edit when the line wrapped.
At 390 wide, the six spaces that indent `"preregistered_success_signal"` in a change proposal's creative-log record were drawn alone on a row of their own, so the edit looked as if it held a blank line it does not have, and at any width the wrapped part of an indented line started at 2ch, left of its own key.
The same test found that a change item's Touches, which names two files, ended "for you to approve before Mandu changes the file".
On top of `6fe9780392460e92b0af2f3ea546b66d67177e02`, each line of a code block is now its indentation, a cell that never wraps, and the rest of the line beside it, which wraps 2ch past where the line's text begins (`codeline` in `src/gr0wthlab/page.py`, `.doc-codeline` and `.doc-indent` in `src/sitting/page.css`).
The rest of the line is no element of its own, so a selected line is its exact text, with nothing between its indentation and the rest.
An indentation that would leave the rest of its line less than 16ch is drawn only as wide as that, so no line reaches past its block.
Each Touches that says a package-change proposal follows approval now ends "for you to approve before Mandu changes the package".

Every check below ran on 2026-10-16, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort where a real agent ran; a run identifier carries its time in UTC.
The fix was not committed when they ran: its `src` tree was `f5b3800fb361b388149995c36778689332e409dd` and its `config` tree `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a`, written from a throwaway index over `6fe9780392460e92b0af2f3ea546b66d67177e02` with the working tree's `src` and `config`.
The page checks, the tests, and the first boundary check below ran on the `src` tree `e2cee26278e80af98f77096888dd57b21ebc2c64`, which differs from it only in the docstring of `codeline` in `src/gr0wthlab/page.py`, made accurate after them; the second boundary check ran on `f5b3800fb361b388149995c36778689332e409dd`.

### The page before the fix and on it

A copy of the test's lab H, a throwaway clone of `6fe9780392460e92b0af2f3ea546b66d67177e02` in the Mac's temporary directory whose queue held the open change proposal `20261015-weekly-read-change-p07` with its creative-log edit, was served by `src/bin/gr0wthlab sitting` from its clone twice.
The first time `src/gr0wthlab/page.py`, `src/sitting/page.css`, and `src/gr0wthlab/weekly_read.py` were as `6fe9780392460e92b0af2f3ea546b66d67177e02` has them, and the second time as the working tree has them.
Each time the item's page was opened in headless Chrome through `chrome-devtools-axi`, and a script in the page found where each character of the item's four code blocks was drawn, then selected each block and compared the selection's text with the block in the item file.

| Page code | Window | What the page showed |
| --- | --- | --- |
| `6fe9780` | 390 by 844, light | A row holding only the six spaces before `"preregistered_success_signal"`, and every wrapped row of the record's eight long lines at 2ch, under keys at 6ch |
| `6fe9780` | 1280 by 800, dark | No line of the record wrapped |
| This change | 320 by 640 light, 390 by 844 light and dark, 1280 by 800 light and dark | No row holding only spaces, each record line's first row at 6ch and each of its wrapped rows at 8ch, and each Angle bank row's wrapped rows at 2ch as before |

In every window each block's selection was its text in the item file, character for character, and no block and no page was wider than the window.

A static page of `document()`'s output with `src/sitting/page.css`, opened the same way, held a line indented by a tab, a line of spaces only, an empty line, and a line indented by 60 spaces.
The tab's line wrapped 2ch past its 8ch tab.
The 60-space line was drawn at 60ch at 1280 wide, and at 390 and 320 wide was held inside its block, where before the indentation's cell had its cap it made the page 569 wide at 390.
The empty line drops out of a selection's text, as it did on `6fe9780392460e92b0af2f3ea546b66d67177e02`; nothing applies an edit from the page, and Mandu reads the item file.

### The boundary

From the gate's linked worktree at `6fe9780392460e92b0af2f3ea546b66d67177e02` with the fix in its working tree, against Mandu and the Product checkouts as they are, with the SHA-256 of `git status --porcelain` the same before each tree's preflights and after its check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `32af654b78b3cfc5e0c257fc93ed76e5c5f6a2c6efe42f2898b6f270e2276e43` on each tree, the same as in the third to sixth rounds.

- `src/bin/gr0wthlab preflight`, run three times at 00:08 and 00:09 on `e2cee26278e80af98f77096888dd57b21ebc2c64` and twice at 00:11 on `f5b3800fb361b388149995c36778689332e409dd`, passed each time: six areas writable, 22 paths refused, no breach, a listing of the footage place `~/Mandu/projects/RepToday` refused, and neither listed host reached from inside the sandbox.

| Run | `src` tree | Time | What its record showed |
| --- | --- | --- | --- |
| `20261016T070902Z-on-demand-f3d7` | `e2cee26278e80af98f77096888dd57b21ebc2c64` | 00:09:00 to 00:10:00 | Passed at its first attempt, 30 tool calls in Codex's record with no problem |
| `20261016T071201Z-on-demand-f872` | `f5b3800fb361b388149995c36778689332e409dd` | 00:12:00 to 00:14:14 | Passed at its first attempt, 52 tool calls in Codex's record with no problem |

Each `src/bin/gr0wthlab boundary-check` above showed 49 steps to prove, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached its listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the working tree: `tests.test_page`, `tests.test_weekly_read`, `tests.test_weekly_changes`, and `tests.test_serve`, 109 tests, none failed and none skipped.
- `DocumentTest.test_each_line_of_a_block_is_its_own_line` in `tests.test_page` now holds each line's indentation as a part of its own; run in a scratch copy of the working tree with `src/gr0wthlab/page.py` put back as `6fe9780392460e92b0af2f3ea546b66d67177e02` has it, it failed, and on the fix it passes.
- Ruff, the whole unit suite, and CI's run were not part of this round.

### What this round did not exercise

- No run filed a Weekly Read decision item with the new Touches ending; the ending stands on `TakeTest`'s `test_each_item_says_what_approving_it_changes_in_the_package` and on `ApprovedDecisionRunTest` in `tests.test_weekly_changes`, which read the items those write.
- A browser other than Chrome, and the sitting page in Safari.
