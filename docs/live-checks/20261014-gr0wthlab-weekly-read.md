# The Weekly Read, from numbers the Founder gives on the sitting page (US-ME11, US-ME12)

This change builds the Weekly Read with no YouTube connection, the Founder's decision of 2026-10-14 ([ADR 0005](../adr/0005-the-weekly-read-uses-no-youtube-connection.md)).
In a read week a run lists, for each post the read covers, the numbers to give from TikTok Studio or YouTube Studio; the Founder types them on the sitting page ([ADR 0006](../adr/0006-the-founder-types-the-weekly-read-numbers.md)), each post's numbers a results record in `ledger/founder/results/`; the next run turns them into Evidence, the Weekly Read session writes the memo, and the launcher checks it, composes the memo the Founder reads, and queues one Weekly Read decision item for each of its lines.
It also shows the scheduling service as not used, since the Founder posts by hand ([ADR 0004](../adr/0004-posting-is-manual.md)).

It changes launcher code, `config/run.json`, and the Product registry (`config/products.json`, which names `read-the-results.md` for the Weekly Read), and adds `ledger/founder/results/`, the sixth folder of the Founder's records, which is a forbidden target of the preflight and of the boundary check.
It changes nothing in the permission profile, the Codex command, or the fetch policy.
The exchange format is version 8.
This file holds every round of that change's live checks.

Every check below ran on 2026-10-14, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.
A run identifier carries its time in UTC.
Most commits named below are earlier states of this work that were rewritten before it was published, so each is given with its `src` tree, which identifies the code it ran.

## First round: the Weekly Read live, the page in a browser, and the boundary

### The Weekly Read, through the launcher on demand and the sitting page

Every run below was started with `src/bin/gr0wthlab run` in a throwaway clone of this work in the Mac's temporary folder, with the agent's network off as always.
One commit was added in the clone: the configuration `make_repo` in `src/tests/fakes.py` gives (no network source, no outreach message, no Product that films), with the window's first sitting set to Sunday 2026-10-04, so that the day-7 read (day 7 is Sunday 2026-10-11) was due on 2026-10-14.
Mandu was the synthetic kit of `src/examples/post-drafts/` with its calendar kept to days 1 to 5, as `fakes.make_mandu` and `fakes.keep_days` make it; RepToday's code, the Immerse checkout, the footage place, the log folder, and the production clone were throwaway locations, set with the `GR0WTHLAB_*` overrides; a clone that is not the production clone saves no records and syncs nothing.
For each run the clone was moved to the code named in its row, with the one commit on top.

The Founder's part was played in Chrome, driven with `chrome-devtools-axi`, on the page `src/bin/gr0wthlab sitting` served from the clone.
Every number given is synthetic: day 1 on TikTok, 150 views and a watched-full rate of 40%; day 2 on TikTok, 1,400 views, 2 comments, and the text of both; day 3 on YouTube, 900 views and 81% viewed rather than swiped away; day 4 on YouTube, 260 views and 3 comments, with no comment text; day 5 on TikTok, 320 views and the text of one comment.
That is the US-ME12 Validation Test's set: day 1 under the 200-view floor, day 2 first on views and short of its signal, and day 3 clearing its signal.

#### With the synthetic `read-the-results.md`

Runs 1 to 5 read the kit's own synthetic `read-the-results.md`, which says the floor counts views and has no rule on how many readable posts a rank needs, so none of them filed the proposal that asks the real file to say it.

| Run | Code | What the records showed |
| --- | --- | --- |
| `20261014T191345Z-on-demand-ac80` | `3d52f652395ffde258b373a0de10fea043bbdad2` (`src` tree `6071e842bd6ea9ec269773c35e7206ee5be1e1cd`) | Before anything was given. One session, Package review; nothing was due for the Weekly Read. The queue's `results` asked for days 1 to 5, each on the platform the calendar names, and one notice listed them. The run report's rows: TikTok Studio numbers and YouTube Studio numbers `skipped`, "not given yet for the window 1 day-7 Weekly Read"; Post results `incomplete`, "not given yet, so not reported", naming all five posts; Weekly Read memo `skipped`; Scheduling service `not used`, "posting is manual, the Founder's choice of 2026-10-11". |
| `20261014T192154Z-on-demand-d6ec` | `e0fca306552deec537112f7b374bb2f14cb3d2d7` (`src` tree `86adcf7b7f257d6ca223711e8caef1dd9134af6f`) | After the five posts' numbers were given on the page. Two sessions, Package review and Weekly Read (56 s of agent time). Post results `complete`, 5 of 5 posts given; the memo passed every check, and 6 Weekly Read decision items were queued: P01 insufficient data (under the floor), P02 missed its signal, P03 cleared its signal, P04 at risk, P05 insufficient data, and the flex slot earned by P03. About $0.022 for the run. |
| `20261014T193312Z-on-demand-3b8f` | `72ae3444fe124275094bbdf6bb4fe3f4d3f32563` (`src` tree `1a46c0d746c7e66ba8ed5a8a4baa54eb246a7ed4`) | After day 1 was saved again on the page with the same numbers. The memo was written again and passed; 6 items were queued, replacing the 6 open ones line for line, each item saying which it replaces. P04 now read insufficient data: "The 3 comments (n=1) were reported without their text". About $0.017. |
| `20261014T193911Z-on-demand-2a10` | `54fd17591d030f0dc1a7fbcb4d26832364e9bd5a` (`src` tree `d0573add8b584adf617a71506bbc6826ffba3762`) | After day 1 was saved again, reached from the start page's new link. 6 items replacing 6; P04 insufficient data again; the items of a keep or a test say approving changes nothing in the Angle bank. About $0.017. |
| `20261014T201207Z-on-demand-42ab` | `bfc101c5eadb072e8bc648d4af91008a4ba3db2f`, on `main` (`src` tree `5cc83367d7f1b547427cd3326e859e4a77b0f4d2`) | After day 2 was given again on the page: "1.4K" for its views was refused and left the record as it was, then "1,400" was saved as 1400. Two sessions; the Weekly Read took 50 s of agent time. The memo passed; 6 items replaced the 6 open ones. The Sources line read "0 failed, 1 changed, 20 read, 5 skipped, 1 not used", and the memo's table "unread: under the floor" for day 1 and "2 comments" of text for day 2. About $0.019. |

In runs 2 to 5 the memo the Founder reads, `ledger/weekly-reads/window-1-read-07.md`, opened with the line that the floor counts each platform's views and the line of what the read cannot tell, then the launcher's table of each post's numbers with its n, the agent's lines with their items, the Waitlist (not configured in the clone: "RepToday's Waitlist build has not landed"), and the Founder's time ("No sitting is recorded from 2026-10-04 to 2026-10-11").
No line killed an Angle, the under-floor post was never judged, and the flex slot went only to P03, whose line says it cleared its signal; day 2's post, first on views, did not earn it.
In run `d6ec` the agent flagged P04 at risk on a comment count whose text was not given.
The task definition now says that where judging an Angle needs a number or comment text the Founder did not give, its result is insufficient data, and every later run read P04 that way.

#### With the real `read-the-results.md`

For runs 6 to 11 the clone's synthetic Mandu was given a copy of the real `read-the-results.md` from `~/Mandu`, unchanged; it stayed in the Mac's temporary folder, and nothing of it is in this repository.
That file still says the floor counts impressions, and it ranks posts only once ten have shipped and cleared the floor.
For runs 8 to 11 the clone's calendar also had the real calendar's day-7 midpoint review gate added under its synthetic rows, which ranks the read's posts once three are readable.

| Run | Code | What the records showed |
| --- | --- | --- |
| `20261014T201804Z-on-demand-610f` | `b149c0045ed44015320157a48e3084b0ab24edce` (`src` tree `09ba89c24e0431eb8bd33c472f8dd505c685f657`) | After day 3 was given again on the page. The run filed `src/proposals/read-the-results-views-floor.md` as `20261014-read-the-results-views-floor`, "filed this run: open for the Founder's decision". The memo passed and replaced the 6 open items; it ranked the 4 readable posts though the only ranking rule the clone held asks for ten: P03 cleared its signal and earned the flex slot. 44 s for the Weekly Read; about $0.018. |
| `20261014T202120Z-on-demand-50c4` | `d2245a24b8e906bd427c95387162b4d002cd735e` (`src` tree `f16dccb75151390a66b9ae81257944d97d962693`), whose task definition says a result that rests on a rank needs as many readable posts as the rules ask | After day 5 was given again. Every Angle read insufficient data, P02 and P03 with "only 4 posts were readable (n=4), too few to rank", and the flex slot was not earned. 48 s; about $0.016. |
| `20261014T202348Z-on-demand-1d1e` | the same | After the midpoint gate was added to the calendar and day 1 was given again. P02 and P03 still read insufficient data: "the available results do not establish its top-half rank". Each post had been asked only for what its own Angle names, so no other post had a viewed rate to rank P03's against, and only P04 had a comment count to rank P02's against. 55 s; about $0.022. |
| `20261014T203524Z-on-demand-f937` | `a05e1c751d576cfb50832e11af424d9ee6e0dc7d` (`src` tree `41a4b8093bc6916f8a3c04b72fce9dceb2848b18`), which asks each post for what the read's posts on its platform name | The queue's `results` asked each TikTok post for its views, its watched-full rate, and its comment count, and each YouTube post for its views, its viewed rate, and its comment count; the memo was written again from the numbers as they stood, the added ones not reported. 37 s; about $0.016. |
| `20261014T203759Z-on-demand-9d8f` | the same | After the added numbers were given on the page: day 1, 3 comments; day 2, a watched-full rate of 18%; day 3, 2 comments; day 4, 55% viewed; day 5, 35% watched full and 4 comments. Every Angle read insufficient data, P02 with "Only 2 readable TikTok posts (n=2), fewer than the three readable posts the midpoint gate needs for ranking", P03 likewise with 2 readable YouTube Shorts posts; the flex slot was not earned. 1 min 15 s; about $0.018. |
| `20261014T204230Z-on-demand-89f1` | `fc8dc8e163d3ea51a5361fe185d693257070c053`, this work as it is (`src` tree `f2a4edf3ded74c37974365134401b91aa9434e76`), whose asks only word their reason differently | With nothing new given; the asks' new wording made the memo due. P03 "cleared its signal", "ranked first of 2 readable YouTube Shorts posts (n=2)", and earned the flex slot: on the same numbers as run `9d8f`, the agent counted the read's 4 readable posts against the gate's three where run `9d8f` had counted each platform's 2. P02 read insufficient data, its line saying its comment text was not given, though the Founder had given the text of both its comments. 1 min 0 s; about $0.023. |

So with the real rules the agent ranks only as many readable posts as it reads them to allow, and says how many there were.
Runs `9d8f` and `89f1` read the same gate two ways on the same numbers, and run `89f1` misstated what was given for P02.
Neither is a check the launcher can make; each line comes to the Founder beside the launcher's table of what was given, on its item.
A day-7 read covers five posts, and in the real calendar three are judged on TikTok and two on YouTube, so most of its Angles can be expected to read insufficient data.

### What the browser showed, and what was fixed

The page was used at 1280 wide, at 500 wide, the narrowest window Chrome allows, and at 390 wide with Chrome's device emulation, in light and dark.
At 500 and 390 wide the page itself never scrolled sideways; a table of many columns scrolls inside its own frame, as before.

- The comment count and the comment text were one form field name, so the count was lost on save; the text field has its own name now, and a test sends both as a browser does.
- The saved record was shown as Python's own text for a list and a mapping; it is shown in words now.
- A date in an item's table broke at its hyphen; a table cell of one short word stays on one line now.
- Once every post was given, the start page still began "First, the Weekly Read asks", named both Studios whatever was asked, and gave no way back to the numbers but Back through every item; it now says what was given and links to the first post's numbers, names only the Studios asked, and says "1 post's" for one.
- The memo's table said "unread: under the floor or not reported"; it says which now, and how many comments were given as text.
- An item to keep or test an Angle said Mandu changes its row in the Angle bank if approved; only a kill or a change says that now.
- The saved note read "comments 2; 2 comments"; the second now reads "the text of 2 comments".
- The run report's Sources line left the scheduling service out of its counts, and its row said "not used" twice; both are fixed.
- A saved record's comment lines ran to the panel's right edge, since the style of a record's rows also matched each line of a value; only the rows are styled so now.

A shortened figure, "1.4K" for views, was refused with "Video views: give the exact number the Studio shows for the post, not a shortened one like 1.2K", and the record on disk was unchanged; "1,400" was then saved as 1400.

### The boundary

Each round of checks ran from this work's linked worktree, against Mandu and the Product checkouts as they are, with `git status` empty before the preflight and after the check, and its logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`.
The configuration fingerprint `show-config` printed was `3b9e5826d373eb0e34ccb4977e008cc27eceece333267299f2cce1972890d179` each time.

| Code | Preflight | Boundary check |
| --- | --- | --- |
| `b8b20082b1d8aceed9bbff001c7b19d720eb5be0`, before `main`'s #20 and #21 were merged in (`src` tree `a8c9708b2382f649e7c64704ae52a148e634a264`, `config` tree `52d4b7a38ea9fd3527a4c6e00e8c8d081bb32fbb`) | Twice at 13:02, passed both times | `20261014T200308Z-on-demand-7d80`, from 13:03:06 to 13:04:40, passed at its first attempt; 28 tool calls |
| `bfc101c5eadb072e8bc648d4af91008a4ba3db2f`, on `main` (`src` tree `5cc83367d7f1b547427cd3326e859e4a77b0f4d2`, `config` tree `52d4b7a38ea9fd3527a4c6e00e8c8d081bb32fbb`) | Twice at 13:10, passed both times | `20261014T201047Z-on-demand-558e`, from 13:10:45 to 13:11:45, passed at its first attempt; 28 tool calls |
| `b149c0045ed44015320157a48e3084b0ab24edce` (`src` tree `09ba89c24e0431eb8bd33c472f8dd505c685f657`, `config` tree `52d4b7a38ea9fd3527a4c6e00e8c8d081bb32fbb`) | Twice at 13:14, passed both times | `20261014T201433Z-on-demand-40f7`, from 13:14:31 to 13:15:24, passed at its first attempt; 28 tool calls |
| `d2245a24b8e906bd427c95387162b4d002cd735e` (`src` tree `f16dccb75151390a66b9ae81257944d97d962693`, `config` tree `52d4b7a38ea9fd3527a4c6e00e8c8d081bb32fbb`) | Twice at 13:24, passed both times | `20261014T202408Z-on-demand-3d12`, from 13:24:06 to 13:24:54, passed at its first attempt; 27 tool calls |
| `fc8dc8e163d3ea51a5361fe185d693257070c053`, this work as it is (`src` tree `f2a4edf3ded74c37974365134401b91aa9434e76`, `config` tree `52d4b7a38ea9fd3527a4c6e00e8c8d081bb32fbb`) | Twice at 13:40, passed both times | `20261014T204038Z-on-demand-8aa2`, from 13:40:36 to 13:41:52, passed at its first attempt; 46 tool calls |

Each preflight: six areas writable, 20 paths refused, among them all six folders of the Founder's records, `results/` with them; no breach; a listing of the footage place `~/Mandu/projects/RepToday` refused; and neither listed host reached from inside the sandbox.
Each boundary check: 45 steps to prove, among them `founder-results` by the file tool and by the shell; no problem in Codex's record of its tool calls; 15 of 15 file-tool targets refused, each in a patch of its own; 17 kernel sandbox denials, and no shell target without one; the footage place's shell read refused, 1 of 1; 12 of 12 permitted sentinels written and none escaped; nothing unproven; the network probe's three targets refused inside the sandbox after its control reached the listener; two requests from the launcher's client, each a GET for a listed host's `robots.txt`, and an unlisted address refused; and nothing changed outside the areas.

### Tests

- The whole unit suite ran under `/usr/bin/python3`, Python 3.9.6, one process for each test module, in a linked worktree of this work as it is, `fc8dc8e163d3ea51a5361fe185d693257070c053`: 1387 tests in 51 modules, and none failed.
- This work's first commit alone, `4c698149ba0bc109a860eba904ca2e4d3815a292` (posting is manual), ran the same way with `test_filming` left out: 1207 tests in 45 modules, and none failed.
- The test that gives a comment count and comment text as a browser sends them, `test_a_post_asked_for_its_comment_count_keeps_the_count_and_the_text_apart`, failed with the two fields under one name, as the code was before its fix.
- CI's run on Linux with the latest Python was not part of this round.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab` passed, with ruff 0.15.20.

### What this round did not exercise

- No real post has gone out, so no real Studio numbers were given; every number in the lab was synthetic.
- The day-14 read was not run live: its pairs, a kill after a day-7 at-risk flag, and the refusals of a pair resolved on an unread leg and of a kill without that flag stand on `tests.test_weekly_read` and the example set's examples 9 to 11 (`tests.test_weekly_read_examples`).
- The proposal that the floor counts views was filed live in run `610f`, but the Founder's decision on it was not made, and that it is never filed again stands on `test_the_proposal_that_the_floor_counts_views_is_filed_once`.
- No run had three readable posts on one platform, so no memo that ranks under the midpoint gate was seen live; ranking stands on the example set's day-7 and day-14 memos, which the launcher's checks pass.
- A memo that fails a check was not made live; it stands on `test_a_memo_that_fails_a_check_queues_nothing_and_the_notice_says_why`.
- No result in the lab bore on the product, so no Dispatch request came from a Weekly Read session; a Dispatch request the agent writes to `incoming/` is queued as `test_one_item_of_each_kind_two_approved_two_rejected_two_undecided` in `tests.test_cycle` holds, and no test has a Weekly Read session write one.
- The Waitlist counts by Source and Fit in the memo, and the Founder's sitting time, were not made live, since the clone has no Waitlist view and no sitting was ended there; they stand on `test_the_memo_carries_the_waitlist_counts_and_the_founder_s_time_that_week`.
- The Founder deciding a Weekly Read item, which keeps that read's memo as it is, was not made live; it stands on `test_a_decided_item_keeps_its_memo`.
- Mandu's gr0wthlab-reader, built for version 7, was not run against version 8; by the exchange's rules it finds each version-8 record newer than it knows and acts on nothing in it.
- A scheduled run, the real production clone, and a browser other than Chrome.

## Second round: the re-check after the merge with `main`

Before this work was validated, `main` gained #22, #23, and #24, and one ordinary merge commit brought them in: `3a17b77652bb91e3cdd4162b1de9790b82720d97` (`src` tree `c06356769a8667e837d034f0aff3564dbc86d4be`, `config` tree `74f0fa22a012c321a572f8297a3449401026ebb8`).
#23 added an ADR 0003 of its own, so this work's ADRs are now 0004, 0005, and 0006, and ADR 0006 records the Founder's decision of 2026-10-14, "weekly read - type".
This work as it is now is `5a7440884f0cc785f32d2c4b8244b62b8a2ecadb` (`src` tree `75be1d7cfa72cf009531f293e0fbb078041bf351`, `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`): after the merge its commits change only documents, comments, the scheduling service's reason in `config/run.json`, and one test's expected path.
Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort.

### What the merge needed

- #23 made the Instructions in force and the example sets forbidden targets, beside this work's sixth folder of the Founder's records, so the check now has seventeen targets.
- An example's lab made the Founder's folders from a list of its own in `src/gr0wthlab/examples.py`, without `results/`, so every lab's run refused to start; it now uses `boundary.FOUNDER_KINDS`.
- A lab's run for another workflow filed the Weekly Read's floor proposal, which package review's example 8 read as a proposal of its own; a lab for another workflow now files neither that proposal nor the Weekly Read's notice (`Cycle.lab_of_another`), and `test_an_example_s_lab_for_another_workflow_files_none_of_the_weekly_read_s_items` failed without it.
- The Weekly Read has no Instructions of its own, so the gate never re-runs its example set; its deterministic assertions run in the unit tests as before.

### A new recorded probe log

In the throwaway clone, with its synthetic checkouts, on the merged code before the probe's tests were reworked (`src` tree `bcf5ce36ddc91f8d9b67e61a0ed0e5bbcc282968`, which differs from the merge commit's only under `src/tests/`), `src/bin/gr0wthlab boundary-check` passed at its first attempt as `20261015T145051Z-on-demand-80b6`.
Its record: 48 steps to prove, 29 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials, no forbidden read (the clone films nothing), and nothing changed outside the areas.
Its Codex log is now `src/tests/fixtures/probe-logs/each-target-alone-with-results-instructions-and-examples.stderr.log`, with only the account, the clone's paths, the run, and one path Codex cut short replaced, as the fixtures' README says.
`src/tests/test_probe.py` proves the seventeen targets on it, and holds that each earlier log proves nothing of the targets added after it.

### The Weekly Read on the merged code

In the same clone, moved to `5a7440884f0cc785f32d2c4b8244b62b8a2ecadb` with its configuration commit on top, day 4's comment text (three synthetic comments) was given on the sitting page in Chrome, and `src/bin/gr0wthlab run` ran as `20261015T151953Z-on-demand-d55d`.
Two sessions ran, Package review and Weekly Read (1 min 6 s of agent time), about $0.020 in all.
The Sources line read "0 failed, 1 changed, 20 read, 5 skipped, 1 not used", the scheduling service's row named `docs/adr/0004-posting-is-manual.md`, and the memo passed and replaced the 6 open items.
With day 4's comments given, P04 read at risk on them ("It has no comments naming offline"), and the flex slot went to P03, which cleared its signal.

### The boundary

From this work's linked worktree at `5a7440884f0cc785f32d2c4b8244b62b8a2ecadb`, against Mandu and the Product checkouts as they are, with `git status` empty before the preflight and after the check, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`; `show-config` printed the configuration fingerprint `3b9e5826d373eb0e34ccb4977e008cc27eceece333267299f2cce1972890d179`.

- `src/bin/gr0wthlab preflight`, run twice at 08:19, passed both times: six areas writable, 22 paths refused, among them the six folders of the Founder's records, the Instructions in force, and the example sets; no breach; a listing of the footage place `~/Mandu/projects/RepToday` refused; and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 08:19:09 to 08:20:15, passed at its first attempt as `20261015T151911Z-on-demand-b4cd`: 49 steps to prove, 30 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials and no shell target without one, the footage place's shell read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, nothing unproven, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and nothing changed outside the areas.

### Tests

- The whole unit suite ran under `/usr/bin/python3`, Python 3.9.6, one process for each test module: on the merge commit's tree before it was committed, and again in a linked worktree of `5a7440884f0cc785f32d2c4b8244b62b8a2ecadb`, 1456 tests in 53 modules each time, and none failed.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab` passed, with ruff 0.15.20.

### What this round did not exercise

- Everything the first round did not, which the merge leaves as it was.
- The Instructions-change gate re-running any example on a change of this work's: no change of this work's touches a workflow's Instructions, and `src/tests/test_example_runs.py` holds every re-run example on the merged code.

## Third round: the day each post went out, after review

Review found that nothing asked whether or when a post went out, while the sitting page, the notice, and the agent's brief each called the calendar's day the day the post was posted.
As review then asked, the sitting page now asks, beside each post's numbers, the day it went out, filled in with the day the calendar planned it.
The results record keeps it as `posted_on`, never after `read_on`; each post's Evidence carries it, the brief gives it beside the planned day when the two differ, and the memo's table has a Posted column.
Until it is given, the page, the notice, and the brief call the calendar's day the day the post was planned, never posted, and the memo's table says the day it went out is not reported.
The queue's ask now names the calendar's day `planned`, where it was `date`.

The code is not committed yet: it is `9b3b995768072d62975f781034a8efa99d50f639` with this round's changes on top, `src` tree `f91154dabe09a13953486b2aa7a193fdbdedba5b` and `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0.

### The page in Chrome, and the runs around it

The runs below were started with `src/bin/gr0wthlab run` in a throwaway clone of this worktree's files in the Mac's temporary folder, set up as in the first round: the configuration `make_repo` in `src/tests/fakes.py` gives, the window's first sitting on Sunday 2026-10-04, and the synthetic kit kept to days 1 to 5.
The agent was the repository's no-model stand-in (`tests.fakes.install_codex`), which wrote the memo `MEMO` of `src/tests/test_weekly_read_cycle.py` in the second and third runs; no model ran in them.
The Founder's part was played in Chrome, driven with `chrome-devtools-axi`, on the page `src/bin/gr0wthlab sitting` served from the clone; every number, comment, and date given is synthetic.

| Run | What the records showed |
| --- | --- |
| `20261015T161133Z-on-demand-2f5c` | Before anything was given. The queue's `results` asked for days 1 to 5, each with its `planned` day, 2026-10-05 to 2026-10-09. The notice listed each post as planned, such as "day 2 (P02), TikTok, planned for Tuesday 2026-10-06: the day it went out, Video views, Watched full video, in percent, Comments, and the text of its comments", and the word "posted" was not in it. |
| `20261015T161341Z-on-demand-aa55` | After days 1, 2, and 5 were given on the page, below. Weekly Read memo `complete`, 6 decision items queued; Post results `incomplete`, "not given yet, so not reported", naming days 3 and 4. The brief's line for day 2 read "posted 2026-10-07 (planned for 2026-10-06), read on 2026-10-15", for day 1 "posted 2026-10-05, read on 2026-10-15", and for day 3 "planned for 2026-10-07, nothing given". Day 2's Evidence held `"posted_on": "2026-10-07"`. The memo's Posted cell for day 2 read "2026-10-07 (planned for 2026-10-06)". |
| `20261015T161540Z-on-demand-cfc4` | After the table change below, and day 2 saved again as it was. Weekly Read memo `complete`, 6 decision items queued, replacing 6 open items. The memo's Posted column read 2026-10-05, 2026-10-07, not reported, not reported, and 2026-10-09 for days 1 to 5. |

On the page:

- Before anything was given, day 2's step said "Planned for 2026-10-06, P02.", and its field "The day it went out" held 2026-10-06, with the hint "YYYY-MM-DD; the calendar planned it for 2026-10-06".
- Day 2 was given as gone out on 2026-10-07, with 1,400 views, 18% watched full, 2 comments, and their text: the record on disk held `"posted_on": "2026-10-07"`, the step then said "Posted 2026-10-07, planned for 2026-10-06, P02.", and the saved note "posted on 2026-10-07".
- On day 3, at 500 wide, 2026-10-14 as the day it went out with 2026-10-13 as the day read was refused with "The day it went out, 2026-10-14, is after the day you read them, 2026-10-13."; no record was written, and the typed values stayed in the form.
- Days 1 and 5 were saved with the day as filled in: "Posted 2026-10-05, P01, AB-1 leg A." and "Posted 2026-10-09, P05."
- After run `aa55`, day 2's decision item showed its Posted cell "2026-10-07 (planned for 2026-10-06)" broken at a hyphen of the planned date.
  The memo's table now holds only the day given, a single date the page keeps on one line, or "not reported", and the brief alone gives the planned day beside it; after run `cfc4` the item's cell read "2026-10-07" on one line.

### The boundary

From this work's linked worktree, with the code above, against Mandu and the Product checkouts as they are, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`.
`git status` was not empty, since this round's changes are not committed, and `git status --porcelain` printed the same 18 changed files, with the same SHA-256, before the preflight and after the check.
`show-config` printed the configuration fingerprint `7d5667ffe1083f3be5b37ed32095fd52a70e24ef56b3461be5277838949a0e79`; its output names this worktree's own path.

- `src/bin/gr0wthlab preflight`, run twice at 09:19, passed both times: six areas writable, 22 paths refused, among them the six folders of the Founder's records, the Instructions in force, and the example sets; no breach; a listing of the footage place `~/Mandu/projects/RepToday` refused; and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 09:19:44 to 09:20:47, passed at its first attempt as `20261015T161946Z-on-demand-b05b`, with `gpt-6-luna` at `high` reasoning effort and 53 s of agent time: 49 steps to prove, 31 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials naming the run's sentinels or the check's listeners, the footage place's read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, no local connection through, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and no change since the snapshot from before the check.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the code above: `tests.test_results`, `tests.test_weekly_read`, `tests.test_weekly_read_examples`, `tests.test_weekly_read_cycle`, `tests.test_page`, `tests.test_sessions`, `tests.test_sitting.ResultsTest`, `tests.test_serve.ResultsServeTest`, and `tests.test_cycle.DecisionRoundTripTest`, 140 tests in one process, and none failed.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab` passed, with ruff 0.15.20.

### What this round did not exercise

- No model wrote a memo from a day a post went out: the lab's sessions were the no-model stand-in's, so how the agent weighs a post that went out late is not seen live; what its brief says stands on `PostedTest` in `tests.test_weekly_read` and on `tests.test_weekly_read_cycle`.
- No real post has gone out, so no real day or Studio number was given.
- The day-14 read was not run live.
- The whole unit suite, and CI's run on Linux with the latest Python.
- Mandu's gr0wthlab-reader, which reads version 7, was not run on a results record.

## Fourth round: a later read offers the day given at the earlier one

Review then found that the day-14 read, which asks again for days 1 to 5, filled in the day a post went out with the calendar's day even where the Founder had given another day for the same post at the day-7 read.
As review then asked, a post's step now fills in the day from the same post's usable record on the same platform at the window's earlier read, and says so; the calendar's day fills it in only where no such record exists.
A day the Founder changes at the later read is what that read's record, the brief, the memo, and the Evidence use, as before.
The line under a step with nothing given now names its read, such as "Nothing is given for this post for the day-14 read yet."
The lab's first run below also showed a memo that was not written reported as "`weekly-reads/window-1-read-14.md` could not be read (cannot open without following links: No such file or directory)": `read_plain` raises its own error for a missing file, so the branch that names a memo not written never ran; it now checks for the file first, as `posts.read_draft` does.

The code is not committed yet: it is `c0d18096a84a0f028cad8b341d4d64f221bef83d` with this round's changes on top, `src` tree `955ee3923903668bafe889761a5cc6fa33b8cd0b` and `config` tree `e3b97b510841032f95c57c5f8f61285f8906e657`.
Every check below ran on 2026-10-15, Mac local time (PDT), with Codex CLI 0.160.0.

### The page in Chrome, and the runs around it

The lab was set up as in the third round, in a new throwaway clone of this worktree's files, with the no-model stand-in agent, which wrote no memo in any run; no model ran in them.

| Run | What the records showed |
| --- | --- |
| `20261015T163417Z-on-demand-0545` | The day-7 read due, with the window's first sitting on 2026-10-04. Day 2 was then given on the page as gone out on 2026-10-07, planned for 2026-10-06, with 1,400 views: the record `window-1-read-07-tiktok-day-02.json` held `"posted_on": "2026-10-07"`. |
| `20261015T163454Z-on-demand-6694` | After the clone's window was moved a week earlier, to a first sitting on 2026-09-27, so that the day-14 read was due the same day; the calendar's days moved with it, and the queue's `results` asked for days 1 to 5 of the day-14 read, day 2 `planned` for 2026-09-29. |
| `20261015T163529Z-on-demand-4190` | After day 2 was given for the day-14 read, below. Day 2's record for the day-14 read held `"posted_on": "2026-10-08"` and 2,100 views, and its record for the day-7 read still held 2026-10-07 and 1,400. The brief's line read "day 2 (P02), TikTok, posted 2026-10-08 (planned for 2026-09-29), read on 2026-10-15", and `evidence/results/window-1/read-14/day-02.json` held `"posted_on": "2026-10-08"`. Weekly Read memo `incomplete`, "`weekly-reads/window-1-read-14.md` could not be read (cannot open without following links: No such file or directory)". |
| `20261015T163642Z-on-demand-eb9d` | After `read_memo` checked for the file first. Weekly Read memo `incomplete`, "no memo was written at `weekly-reads/window-1-read-14.md`", and the notice's line for the memo said the same. |

On the page, after run `6694`:

- Day 2's step for the day-14 read said "Posted 2026-10-07, as you gave it for the day-7 read, planned for 2026-09-29, P02." and "Nothing is given for this post for the day-14 read yet.", and its field "The day it went out" held 2026-10-07.
- Day 5, given nothing at the day-7 read, said "Planned for 2026-10-02, P05.", and its field held 2026-10-02.
- Day 2 was given for the day-14 read as gone out on 2026-10-08, with 2,100 views; the step then said "Posted 2026-10-08, planned for 2026-09-29, P02.", and the saved note "posted on 2026-10-08".

### The boundary

From this work's linked worktree, with the code above, against Mandu and the Product checkouts as they are, and logs in a folder of the Mac's temporary directory named with `GR0WTHLAB_LOG_DIR`.
`git status --porcelain` printed the same 7 changed files, with the same SHA-256, before the preflight and after the check.
`show-config` printed the configuration fingerprint `7d5667ffe1083f3be5b37ed32095fd52a70e24ef56b3461be5277838949a0e79`.

- `src/bin/gr0wthlab preflight`, run twice at 09:41, passed both times: six areas writable, 22 paths refused, among them the six folders of the Founder's records, the Instructions in force, and the example sets; no breach; a listing of the footage place `~/Mandu/projects/RepToday` refused; and neither listed host reached from inside the sandbox.
- `src/bin/gr0wthlab boundary-check`, from 09:41:13 to 09:42:55, passed at its first attempt as `20261015T164116Z-on-demand-0533`, with `gpt-6-luna` at `high` reasoning effort and 87 s of agent time: 49 steps to prove, 30 tool calls in Codex's record with no problem, 17 of 17 file-tool targets refused each in a patch of its own, 19 kernel sandbox denials naming the run's sentinels or the check's listeners, the footage place's read refused, 1 of 1, 12 of 12 permitted sentinels written and none escaped, no local connection through, the network probe's three targets refused inside the sandbox after its control reached the listener, two requests from the launcher's client, each a GET for a listed host's `robots.txt`, an unlisted address refused, and no change since the snapshot from before the check.

### Tests

- Under `/usr/bin/python3`, Python 3.9.6, on the code above: `tests.test_results`, `tests.test_weekly_read`, `tests.test_weekly_read_examples`, `tests.test_weekly_read_cycle`, `tests.test_page`, `tests.test_sessions`, `tests.test_sitting.ResultsTest`, `tests.test_serve.ResultsServeTest`, and `tests.test_cycle.DecisionRoundTripTest`, 140 tests in one process, and none failed.
- `test_the_day_14_read_offers_the_day_given_at_the_day_7_read_and_keeps_the_day_changed_there` failed on the code before this round, its field holding 2026-10-06 where 2026-10-07 was given at the day-7 read.
- `ruff check` and `ruff format --check` on the files this round changed passed, with ruff 0.15.20.

### What this round did not exercise

- No model ran: the stand-in wrote no memo, so no memo was composed for the day-14 read in the lab, and the memo's Posted column for it stands on `test_the_day_14_read_uses_the_day_given_for_it_over_the_day_7_read_s`.
- The lab reached the day-14 read by moving the window's first sitting a week earlier, not by a week passing, so its day-14 calendar days fall before the days given at its day-7 read.
- Everything the third round did not exercise.

## Screenshots

The first six were taken in the first round's clone, on the page's code as it stood after `b149c0045ed44015320157a48e3084b0ab24edce`; the numbers step after run `89f1`, the rest after run `42ab`.
The third round then added the day a post went out to a post's numbers step and its saved record, and a Posted column to an item's table; the next four, taken in the third round's clone after runs `2f5c` and `cfc4`, show those screens as they were after that round.
The fourth round made a later read offer the day given at the earlier one, and the line under a step with nothing given name its read; the last two, taken in the fourth round's clone after run `6694`, show a step of the day-14 read.
Every number, comment, date, and name in them is synthetic.
The 390-wide view is Chrome's device emulation at twice the pixels; the 500-wide view is Chrome's narrowest window.

| Screen | Laptop, 1280 wide | Narrow, 390 wide |
| --- | --- | --- |
| The start, once every post's numbers are given | [dark](20261014-gr0wthlab-weekly-read/01-start-laptop-dark.png) | |
| A post's numbers step, as given | [dark](20261014-gr0wthlab-weekly-read/02-numbers-step-laptop-dark.png) | |
| A shortened figure refused | [light](20261014-gr0wthlab-weekly-read/03-refused-figure-laptop-light.png) | |
| The numbers saved, with the record read back | [light](20261014-gr0wthlab-weekly-read/04-saved-read-back-laptop-light.png) | |
| A Weekly Read decision item that replaces an earlier one | [dark](20261014-gr0wthlab-weekly-read/05-weekly-read-item-laptop-dark.png) | [light](20261014-gr0wthlab-weekly-read/06-weekly-read-item-narrow-light.png) |
| A post's numbers step before anything is given, its day planned (third round) | [dark](20261014-gr0wthlab-weekly-read/07-numbers-step-planned-laptop-dark.png) | |
| The numbers saved with the day the post went out (third round) | [dark](20261014-gr0wthlab-weekly-read/08-numbers-step-posted-laptop-dark.png) | |
| A day it went out after the day read, refused (third round) | | [dark, 500 wide](20261014-gr0wthlab-weekly-read/09-posted-after-read-refused-500-dark.png) |
| A Weekly Read decision item with its Posted column (third round) | [dark](20261014-gr0wthlab-weekly-read/10-weekly-read-item-posted-laptop-dark.png) | |
| A day-14 step that offers the day given at the day-7 read (fourth round) | [dark](20261014-gr0wthlab-weekly-read/11-day-14-step-offers-day-7-day-laptop-dark.png) | |
| The same step once the day is changed there and saved (fourth round) | [dark](20261014-gr0wthlab-weekly-read/12-day-14-step-day-changed-laptop-dark.png) | |
