# Live checks: the Founder decides in gr0wthlab, on a local page (US-ME04, US-ME07)

This file records what was run on the Founder's Mac for the change that moves the Founder's decisions and records from Mandu into `ledger/founder/` and adds the sitting page ([ADR 0002](../adr/0002-the-founder-decides-in-gr0wthlab.md)).
It also covers the records the same page now writes for US-ME09 (the filming plan), US-ME14 (a message sent and replied to), and US-ME15 (the Beta Build approval and the Beta Cohort counts).
CI cannot run any of it: it needs the Mac, the Codex login, and a browser.

How to read the paths:

- `~` is the home folder.
- `<tmp>` is the Mac's per-user temporary folder, the one `getconf DARWIN_USER_TEMP_DIR` prints.
- `<lab>` is the throwaway lab under `<tmp>` described below.
- Where a quoted line held the home folder's or the temporary folder's full path, that prefix was replaced with `~` or `<tmp>`.

All times are Mac local time (PDT, UTC-7): rounds 1 and 2 on 2026-10-12, rounds 3 to 7 on 2026-10-13.
A run identifier carries the UTC date, which was already the next day each time.
Codex CLI 0.160.0 with `gpt-6-luna` at `high` reasoning effort throughout.

## What nothing here touched

- The real Mandu, RepToday, and Immerse checkouts were never written.
  Before the first live run and after the last one of rounds 1 and 2, and again before and after round 3, each checkout's `HEAD`, branch, `git status`, stash list, and one SHA-256 over every file outside `.git` were recorded; within each pair the two readings are identical for all three.
- The only commands that named the real checkouts ran from the worktree: `show-config`, the preflights, which try no write in Mandu or a Product, and the boundary checks, which pass only when every write tried there has a record of its refusal.
  Since round 3 both also try to list the footage place, `~/Mandu/projects/RepToday`, from inside the sandbox, which reads nothing when it is refused, as it was each time.
- Every weekly run and every sitting ran in a throwaway lab with a synthetic Mandu, RepToday, and Immerse beside it.
- The weekly schedule was never installed: `~/Library/LaunchAgents` holds no gr0wthlab LaunchAgent.
- Mandu's side of the contract was not built, and nothing was written to Mandu: `~/Mandu/projects/gr0wthlab/` holds no `exchange` folder and no record.
- Every page server this work started was stopped, by its own page's button or by its process id.

## Round 1: the boundary, the hole tests, and the acceptance run

Commit `c68a375b0513e28c0c798afdcdc7a32dffec34af` (`src` tree `1cb558332e6b4353080ffd623e70985ae21e4281`, `config` tree `b7647ce710a152a906b6ac20b9dab1893c7859bd`), from about 17:35 to 17:58.
`git status` was empty in the worktree before and after.

### The boundary, from the worktree

Run from the linked worktree of this change, whose `config/products.json` names the real checkouts.

| Command | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab preflight` | none (no model) | 6 areas written; 19 paths refused, the five folders of the Founder's records among them, each by its own path; neither listed host reachable from the sandbox |
| `src/bin/gr0wthlab boundary-check` | `20261013T003502Z-on-demand-778a` | PASSED at its first probe run; fingerprint `c8053b1e75639d4a653b46b221e8d0e5cc63af93eb2fff6b363d1f315fd922fc`; 42 steps to prove; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials naming the run's sentinels or the check's listeners; 12 of 12 permitted sentinels written; no local connection got through; nothing changed since the snapshot; agent time 36.8 s |

The fourteen targets are the nine the check had before and five new ones, `founder-decisions`, `founder-sittings`, `founder-beta-builds`, `founder-beta-reports`, and `founder-outreach`, each with a file-tool step and a shell step of its own.

### Hole tests, in scratch copies only

Each ran in its own scratch clone of the same commit under `<tmp>`, with a synthetic Mandu, RepToday, and Immerse beside it, so no forbidden target was a real repository.
The committed profile was never loosened: each hole was an uncommitted edit inside its scratch clone, and the clones were removed afterwards.
The four ran at the same time, from 17:36.

| Scratch clone | The edit | Run | What the records showed |
| --- | --- | --- | --- |
| control | none | `20261013T003652Z-on-demand-4876` | PASSED; fingerprint `6f49dcbcdb679fb03a9d20f02c0a95b3a182fc4af3b6653d7a0291bb1d5b3533`; 14 of 14 file-tool targets refused; 16 kernel denials; 12 of 12 permitted; nothing changed |
| writable | `ledger/founder` made writable in the profile | `20261013T003653Z-on-demand-04b6` | FAILED at once: the preflight wrote its sentinel in each of the five folders and named all five, the run ended with exit code 3, and the agent was not started |
| untried | the same, and the preflight told not to try the five folders | `20261013T003653Z-on-demand-7349` | FAILED: 10 sentinels escaped, a file-tool one and a shell one in each of the five folders, and were removed; 9 of 14 file-tool targets refused, with each of the five founder patches recorded by Codex as `Success`; 11 kernel denials; the five founder shell targets had no kernel denial |
| one | only `ledger/founder/outreach` made writable, the preflight told not to try the five folders | `20261013T003653Z-on-demand-d7d5` | FAILED: the shell sentinel in `ledger/founder/outreach` escaped and was removed; `founder-outreach` had no kernel denial; 10 of 14 file-tool targets refused, the other four (`founder-beta-builds`, `founder-beta-reports`, `founder-outreach`, `src`) with no patch naming their sentinel |

The control's Codex log, with its account fields replaced, is the recording `src/tests/fixtures/probe-logs/each-target-alone-with-founder-records.stderr.log`.

### The acceptance run, the way the Founder will use it

The lab: a production clone of this commit under `<lab>/gr0wthlab` with its own bare remote, a synthetic Mandu built from the example sets in `src/examples/`, a synthetic RepToday and Immerse, a seeded anonymous Waitlist view, and one test clip in a footage place, all under `<tmp>` and pointed to by the `GR0WTHLAB_*` overrides.
Two lab-only commits sat on top of `c68a375` in the lab's remote: one set the window, kept two creators, and turned the network sources off; one added a task definition that also writes one Weekly Read decision and one notice, since nothing writes those kinds yet.
The agent was the real one, sandboxed as in production.
The sitting page was the real command, `src/bin/gr0wthlab sitting`, started in the lab clone and driven in Chrome through `chrome-devtools-axi` by its labels and buttons, as a person would.

| Step | Run or sitting | What happened |
| --- | --- | --- |
| Run 1 | `20261013T003522Z-on-demand-1cd2` | The weekly task; agent time 5 min 59 s; 11 items queued |
| Run 1b | `20261013T004207Z-on-demand-8f91` | The lab's task with the two extra kinds; 13 items open: 3 posts, the filming plan, 3 messages, 1 Weekly Read decision, 1 Dispatch request, 3 package-change proposals, 1 notice |
| Sitting 1 | on the page, from 17:43 | Approved the filming plan with a note and the first message to one creator; rejected the personal-network ask and one proposal, each with a reason; left the rest; approved one post by mistake and took it back; recorded the sitting; recorded the Beta Build |
| Run 2 | `20261013T004525Z-on-demand-c7b0` | Took in the four decisions and the sitting; started Beta Cohort recruiting |
| Sitting 2 | on the page, from 17:50 | Approved the day 1 post after playing its video, a second creator message, and the invitation batch; gave the counts; recorded both creator messages as sent, one of them as replied to; corrected the sitting's minutes |
| Run 3 | `20261021T005410Z-on-demand-be7e` | The launcher's clock set 8 days ahead by a driver outside the repository, so the 7-day wait had passed; took in four decisions; offered one follow-up |
| On the page | at 17:58 | Stopped recruiting; approved the follow-up |
| Run 4 | `20261021T005817Z-on-demand-181a` | The same clock; took in the follow-up's approval; withdrew the open recruiting item |

Every run ended with exit code 0 and pushed its records to the lab's remote.

Each scenario below is bound to commit `c68a375`, the lab above, and the times in the table.

| Scenario | Expected | Observed | Result |
| --- | --- | --- | --- |
| US-ME07 Validation Test: one item of each kind, approve two, reject two with reasons, leave the rest, run again | Each decision matched to its item; reasons kept as Evidence; undecided items carried over and marked; no decided item asked again | Run 2 closed `20261012-filming-plan-w1` and `20261012-message-creator-gmb-fitness` as approved and `20261012-message-network-ask` and `20261012-creator-count` as rejected. `ledger/evidence/decisions/20261012-creator-count.json` holds the reason as typed, the path `founder/decisions/20261012-creator-count.json`, and a SHA-256 equal to that file's. Eight items were open with `carried_over` from 2026-10-12. None of the four decided items was in the open queue after run 2, 3, or 4. | pass |
| The reasons are coded | The learning ledger codes each rejection | Run 2 coded the two reasons, one as `tone` (execution) and one as `positioning` (strategy) | pass |
| A mis-click, before a run takes it in | It can be changed or taken back, and the record follows | The day 4 post was approved by mistake; the page showed it saved and offered to change it or take it back; taking it back removed `founder/decisions/20261012-post-w1-day-04.json`, and the item stayed open and was carried over | pass |
| A decision after a run has taken it in | It can no longer be changed | During and after run 2 the page showed for a taken-in item: "A run has taken this decision in, so it can no longer be changed", with no way to change it | pass |
| A decision given while a run is going | It is kept and taken in by the next run | The Dispatch request was approved on the page while run 2 was going; run 2 left it open; run 3 took it in and reported `reptoday-waitlist` approved and never filed again | pass |
| Limits at entry | A line that breaks a limit is refused, nothing is saved, and the page says why | A reason holding an email address was refused with nothing written; a Beta Build approval dated ahead was refused; counts all left blank were refused | pass |
| The sitting's minutes | Measured by the page, correctable by the Founder | The page had measured 2 minutes and the Founder's 41 was saved; at the second sitting the page offered 51, the 41 already recorded and the 10 it had measured, and 55 was saved; run 3 reported "Sitting 2026-10-12: 55 minutes" | pass |
| Beta Build approval | Recruiting starts only from the Founder's record | Before the record, runs 1 and 1b reported "not started: no Beta Build approval is recorded" and queued nothing for the Beta Cohort. After the page wrote `founder/beta-builds/RepToday.json` (approved 2026-10-10, build `1.0 (42)`), run 2 queued invitation batch 1 for 8 Waitlist entries and the Waitlist ask | pass |
| Beta Cohort counts | Only what the Founder reports is kept; a count left out is not reported, never zero | The page saved `invitations_sent` 8 with `accepted` and `sessions_booked` as `null`; run 3 reported "invitations sent 8, accepted not reported, sessions booked not reported" and kept the counts as Evidence | pass |
| Recruiting stopped | Nothing more is offered and the open recruiting item is withdrawn | After the page set `recruiting` to `stopped`, run 4 reported "no batch: the Founder stopped recruiting on 2026-10-12" and withdrew the open `20261012-beta-waitlist-ask` | pass |
| A message sent, and a reply | One follow-up, only to a non-reply, only after the wait | With one creator message recorded as sent with no reply and the other as sent and replied to, run 3 queued `20261020-message-follow-up-gmb-fitness` and offered none for the creator who replied; run 4, after the follow-up was approved, offered nothing more for either | pass |
| The filming plan | Decided on the page like any item, and never asked again | The plan was approved with a note at sitting 1; runs 2, 3, and 4 reported it approved and never asked again | pass |
| A post with its video | The page plays the file the post was queued with | Run 2 replaced the day 1 post with one that shows a rendered video; the page played it (1080 by 1920, 10 s, the browser reporting the whole file ready) and the post was approved with a note | pass |
| The records are saved with the launcher's | A run commits and pushes what the page wrote | Run 2's first commit, "records left before the run", holds the six files sitting 1 wrote under `ledger/founder/`; runs 3 and 4 did the same for what the page wrote before them | pass |
| The page stops cleanly | Its button ends the command | "Stop the page" showed "The page has stopped", the command printed "stopped from the page", and its process had ended | pass |

### What round 1 did not exercise

- Mandu's side reading the queue and the records: nobody has built it, and this change does not touch Mandu; it is the next change, made in Mandu after this one lands.
  It stands on the contract in [`docs/mandu-exchange.md`](../mandu-exchange.md) alone.
- A scheduled run: the weekly schedule was not installed, so every run was on demand.
  The owed-run check with the Founder's records in place stands on `src/tests/test_attempts.py`.
- The real production clone: none exists on this Mac yet, so the lab's clone stood in for it.
- A browser other than Chrome.
- A run and a page change meeting on the lock they share: the wait and the refusal stand on `src/tests/test_founder.py` and `src/tests/test_sitting.py`.
  Live, a decision given during a run was kept and taken in by the next one, as above.
- A message recorded as sent with another wait than the item stated: the wait in both records was left blank.
- Runs 3 and 4 read the time from a driver that sets the launcher's clock ahead, so they are not what a run a week later on the real clock would be in one respect: the page kept the real date, so every record it wrote is dated 2026-10-12.

## Round 2: after the page fixes

Driving the page in round 1 showed eight small flaws, fixed in commit `256628e733283001624aa6f4800a37a294799d6e` (`src` tree `78d3dfed4ae636655c02e41cb7741e6dbf8077f9`, `config` tree unchanged, `b7647ce710a152a906b6ac20b9dab1893c7859bd`); its message lists them.
That commit changes launcher code, so the preflight and the boundary check were run again on it, from 18:20.
`git status` was empty in the worktree before and after.

| Command | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab preflight` | none (no model) | 6 areas written; 19 paths refused, the five folders of the Founder's records among them; neither listed host reachable from the sandbox; no breach and no failure |
| `src/bin/gr0wthlab boundary-check` | `20261013T012101Z-on-demand-6722` | PASSED at its first probe run; the same fingerprint, `c8053b1e75639d4a653b46b221e8d0e5cc63af93eb2fff6b363d1f315fd922fc`; 42 steps to prove; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials, one `file-write-create` for each of the five folders among them; 12 of 12 permitted sentinels written; no local connection got through; nothing changed since the snapshot; agent time 52.2 s |

### A configuration that still names the exchange folder

From the worktree, with `GR0WTHLAB_EXCHANGE_DIR` set to a folder: `src/bin/gr0wthlab run` refused to start and exited 2, and `src/bin/gr0wthlab sitting` refused to start, each with one line that says to unset the variable and take it out of any LaunchAgent, that gr0wthlab reads no record from Mandu any more, and where the records are now, naming ADR 0002.
`git status` was empty afterwards, and no run report was written.
The same refusal for `mandu.exchange` in `config/products.json` stands on `src/tests/test_settings.py`.

### Every route into the records, with no model

In a scratch clone of `256628e` under `<tmp>`, with synthetic checkouts beside it and one seeded record, a shell script ran under `codex sandbox` with the launcher's own overrides and environment, as the preflight runs.
It ran 26 commands, each a way to change something under `ledger/founder/` or the two lock files beside it, and printed for each only whether the command succeeded.

- All 26 ended with a failing status, and one digest over every entry under `ledger/founder/` (path, mode, link count, SHA-256) was the same before and after.
- The script did not record why a command failed.
  Round 3 ran it again keeping each command's own error, and that showed two of the 26 had failed for a reason of their own and so had tried nothing: the copy named a source file that does not exist, and the rename of `ledger/` named it by a path that `mv` rejects as an invalid argument.
  This round therefore shows nothing of those two routes; round 3 tries both.
- Reading a record succeeded, and so did making a symbolic link in `workspace/` that points at a record or at a records folder.
  Neither is a write to a record: the launcher reads a record only as a plain single-link file directly in one of the five real folders, and never follows a link in `workspace/`, which `src/tests/test_founder.py` holds.

### The page in a browser, on the final code

The final page code served a synthetic checkout built by the unit tests' fixtures with the real ffmpeg: nine open items, one a post with a rendered video, one a proposal whose text carries markup, a script, a form, an image, and links.
It was driven in Chrome through `chrome-devtools-axi` at 1280 by 800 and at 390 by 844, in light and dark.

| Scenario | Observed | Result |
| --- | --- | --- |
| A note that ends with its own full stop | Shown with one full stop where it is saved, on the next item, and in the queue | pass |
| A saved record that is no decision | The counts, a message sent, the sitting, and the Beta Build each say what they hold beside "Saved", above the record as read back | pass |
| The wait before a follow-up | Asked on a creator's first message; typed as 10, saved as `follow_up_wait_days` 10, and said as "a follow-up waits 10 days" | pass |
| The item whose text carries markup | Shown as the characters it is written with; in the page, no `script`, `img`, `form`, `button`, `b`, or `i` element came from it, and no link to the addresses it names | pass |
| A table of five columns at 390 wide | Scrolls inside its own frame, 600 wide in a frame of 322, with the page itself 390 wide and no sideways scroll | pass |
| The post's video | Ready to play whole, 1080 by 1920, 10 s | pass |

Round 2 did not repeat the lab's acceptance run with the real agent: the fixes are in how the page words and lays out what it shows and in one refusal, each held by a unit test, and nothing a run reads changed.

### Unit tests and lint on `256628e`

- `/usr/bin/python3 -m unittest discover -s src/tests -t src`, under Python 3.9.6: 1122 tests, all passed, in 1184 s.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab`, ruff 0.15.20: clean.
- The test modules this change adds or rewrites most (`test_founder`, `test_page`, `test_serve`, `test_sitting`, `test_settings`, `test_probe`) also passed under Python 3.12.13, 199 tests, as a stand-in for CI's latest-Python job, which runs on Linux and was not run here.

## Round 3: after the merge with `main`

`main` had gained one sandboxed session per workflow, the footage place with its read probe, and a sandbox that reads of Mandu only each Product's package paths.
This round ran on the merge commit `5c61f86d74b05bdb39f3bd69931e875287a59ab0` (`src` tree `a94ec137e77886652a714548bf56091a715c82d8`, `config` tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`), on 2026-10-13 from 17:11, with Codex CLI 0.160.0.
`git status` was empty in the worktree before the first command and after the last.
It repeated every check of this change that goes through the launcher or the sandbox.

### The boundary, from the worktree, on the real configuration

| Command | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab preflight` | none (no model) | 6 areas written; 19 paths refused, each of the five folders of the Founder's records among them by its own path; no breach and no failure; the listing of the footage place refused, none listed, none untried; both listed hosts unreachable, none reached, none untried |
| `src/bin/gr0wthlab boundary-check` | `20261014T001202Z-on-demand-7981` | PASSED at its first probe run; fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`; 43 steps to prove; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials, one `file-write-create` for each of the five folders among them; 1 of 1 forbidden read refused; 12 of 12 permitted sentinels written; no sentinel escaped; no local connection got through; nothing changed since the snapshot; agent time 57.3 s |

### Hole tests, in scratch copies only

Four scratch clones of the merge commit under `<tmp>`, each with a synthetic Mandu, RepToday, and Immerse beside it and a synthetic footage place holding one footage folder with one file, ran at the same time from 17:13.
Each hole was an uncommitted edit inside its scratch clone; the committed profile was never loosened, and the clones were removed afterwards.

| Scratch clone | The edit | Run | What the records showed |
| --- | --- | --- | --- |
| control | none | `20261014T001340Z-on-demand-b684` | PASSED; fingerprint `bb82f2392f2560240991434e42601a15887b67e769a04d0eb7837f3867c947f5`; 45 steps to prove; 14 of 14 file-tool targets refused; 16 kernel denials; 3 of 3 forbidden reads refused; 12 of 12 permitted; nothing changed |
| writable | `ledger/founder` made writable in the profile | `20261014T001341Z-on-demand-24b5` | FAILED: the launcher printed "boundary preflight failed; the agent was not started" and, under it, the file the preflight had created in each of the five folders; the check's verdict line reads "the run ended with exit code 3 before the agent was started, so the probe tested nothing" |
| untried | the same, and the preflight told not to try the five folders | `20261014T001341Z-on-demand-88cc` | FAILED: 10 sentinels escaped, a file-tool one and a shell one in each of the five folders, and were removed; 9 of 14 file-tool targets refused, with each of the five founder patches recorded by Codex as `Success`; 11 kernel denials; the five founder shell targets had no kernel denial |
| one | only `ledger/founder/outreach` made writable, the preflight told not to try the five folders | `20261014T001341Z-on-demand-5d17` | FAILED: the file-tool sentinel and the shell sentinel in `ledger/founder/outreach` escaped and were removed; 13 of 14 file-tool targets refused, with the `founder-outreach` patch recorded by Codex as `Success`; 15 kernel denials; `founder-outreach` had no kernel denial |

### Every route into the records, with no model

In a scratch clone of the merge commit under `<tmp>`, with synthetic checkouts beside it and one seeded record, the script of round 2 ran again at 17:16 under `codex sandbox` with the launcher's own overrides and environment, now keeping what each command itself said when it failed, and with the two routes round 2 had not really tried put right.

- 27 commands each tried to change something under `ledger/founder/`, `ledger/` itself, or the two lock files beside the records.
  Every one failed, and every one's own message ends `Operation not permitted`.
  They were: overwrite, append to, truncate, remove, rename, and `chmod` a record; create a file in each of the five folders and in `ledger/founder/` itself; make a folder there; copy a workspace file in; move a workspace file in; hard link a record into `workspace/`; hard link a workspace file into a records folder; write through a symbolic link to a record; create a file through a symbolic link to a records folder; make a symbolic link inside a records folder; remove a records folder with all in it; rename `ledger/founder/decisions`, `ledger/founder/`, and `ledger/`; `chmod` a records folder; write `ledger/founder.lock`; create `ledger/sitting.lock`.
- Four commands succeeded: reading a record, writing a file in `workspace/drafts/`, and making a symbolic link in `workspace/` to a record and to a records folder.
- One digest over every entry under `ledger/founder/` (path, mode, link count, SHA-256) was the same before and after.

### A configuration that still names the exchange folder

From the worktree, with `GR0WTHLAB_EXCHANGE_DIR` set to a folder: `src/bin/gr0wthlab run` refused to start and exited 2, and `src/bin/gr0wthlab sitting` refused to start, each with the same line as in round 2.
No run report was written.

### Two runs with the real agent, and a sitting between them

The lab: a production clone of the merge commit under `<lab>/gr0wthlab` with its own bare remote and one lab-only commit on top (the window, two creators, the network sources off); a synthetic Mandu whose package is under `projects/RepToday/gtm/` and whose footage place is its `projects/RepToday/` folder, holding one test clip in `window-1/`; a synthetic RepToday and Immerse; a seeded anonymous Waitlist view.
The agent was the real one, each session sandboxed as in production; the page was the real command, `src/bin/gr0wthlab sitting`, driven in Chrome through `chrome-devtools-axi`, each form read back before it was sent and each record read from its file after.

| Step | Run or sitting | What the records showed |
| --- | --- | --- |
| Run A, from 17:16 | `20261014T001642Z-on-demand-42e6` | Exit 0. Three sessions ran, Package review (96.4 s of agent time), Post Drafts (65.1 s), and Outreach (86.4 s); nothing was due for the other four. 9 items queued. |
| The sitting, 17:21 to 17:22 | on the page | The filming plan approved with a note and one creator message approved; the personal-network ask and one proposal rejected, each with a reason; the Beta Build recorded; the approved message recorded as sent with a wait of 10 days; the sitting recorded as 38 minutes where the page had measured 2. Each record's file held exactly the fields the form had shown. |
| Run B, from 17:22 | `20261014T002224Z-on-demand-746e` | Exit 0. Six sessions ran, Package review (93.5 s), Post Drafts (35.0 s), Filming (23.9 s), Beta Cohort recruiting (45.6 s), Outreach (56.4 s), and Rejection reasons (39.1 s); nothing was due for Listening. |

What each session's own record in the log folder holds, for all nine sessions of the two runs:

- Its preflight refused 18 paths, each of the five folders of the Founder's records among them, with no breach and no failure, before its agent was started.
- Its preflight was refused a listing of the footage place and of the one footage folder in it.
- Its fingerprint is `3f57d260499e92825db3c4238f1376d93548f27e54744861a29020f2434ee3a1`, the same for all nine.

| Scenario | Expected | Observed | Result |
| --- | --- | --- | --- |
| The run takes in what the page wrote | Each decision matched to its item, reasons kept, undecided items carried over | Run B closed `20261013-filming-plan-w1` and `20261013-message-creator-gmb-fitness` as approved and `20261013-message-network-ask` and `20261013-reconcile-creator-count` as rejected, reported "Sitting 2026-10-13: 38 minutes", and left four items open as carried over from 2026-10-13; none of the four decided items was open after it | pass |
| The rejection reasons reach the session that codes them | Each reason coded | The Rejection reasons session ran, and run B reported "2 rejection reasons, 2 of 2 coded; 2 coded this run", one as `tone` and one as `claim` | pass |
| The Beta Build record starts recruiting | Nothing before it, a batch after | Run A reported no session due for Beta Cohort recruiting; run B read the record ("approved on 2026-10-10, build 1.0 (42)"), ran the Beta Cohort recruiting session, and queued `20261013-beta-invitation-batch-01` and `20261013-beta-waitlist-ask` | pass |
| The wait the Founder set on the page | The follow-up waits that long | Run B reported "first message sent 2026-10-13, no reply recorded; a follow-up may be offered from 2026-10-23 (10 days)", and the follow-up as not due | pass |
| The records are saved with the launcher's | A run commits and pushes what the page wrote | Run B's first commit, "records left before the run", holds the seven files the sitting wrote under `ledger/founder/`, and the run pushed it | pass |
| A decision after a run has taken it in | It can no longer be changed | While run B was going, once it had written the decisions' Evidence, the page showed the filming plan as "Decided", with "A run has taken this decision in, so it can no longer be changed" and no form | pass |
| A decision given while a run is going | It is kept | The Dispatch request was approved on the page while run B was going; its record was written, and run B left the item open | pass |
| The page stops cleanly | Its button ends the command | "Stop the page" showed "The page has stopped", the command printed "stopped from the page", and its process had ended | pass |

### What round 3 carried over, and what it did not exercise

- The checks of the page alone were not repeated: its look at both widths in light and dark, the item text shown as text, the video played, the table scrolling in its frame, and the screenshots.
  The merge changed none of the page's own files (`src/gr0wthlab/page.py`, `serve.py`, `sitting.py`, and `src/sitting/`), so round 2's stand.
- `src/gr0wthlab/founder.py`, which the page and a run share, changed in the merge in two small ways: the reason a stray file is no record became a named constant, and the line that refuses a missing records folder names it from the repository's root.
  The sitting between the two runs above went through it for every record it wrote.
- Of round 1's acceptance scenarios, these were not repeated on the merged code and stand on round 1 and the unit tests: the Beta Cohort counts, a stop of recruiting, a reply, a follow-up once its wait has passed, a post with its video, a mis-click taken back, the limits at entry, and a decision given during one run taken in by the next.
- A session whose preflight is not refused in a records folder, in a whole run: the hole test above shows it for the boundary check, which has one agent, and `src/tests/test_founder.py` holds, with a stand-in sandbox, that each session's preflight tries the five folders and that a folder gone between two sessions keeps the next from starting.
- A scheduled run, the real production clone, Mandu's side, and a browser other than Chrome, as in round 1.

### The sentences about these probes, checked against what their records show

The rule on `main` is that a line the launcher prints, and a sentence a document says about a probe, states only what a record shows.
Each sentence this change makes about the preflight's tries in the records folders, the boundary check's five targets, the route check, and the hole tests was read against that, in the merged tree:

| Where | The sentence now | What was changed |
| --- | --- | --- |
| `AGENTS.md` | "Each of the five record folders is a forbidden target of the preflight before every session and of the boundary check" | said "every run's preflight" |
| `docs/operations.md`, what a run does | "Before each session's agent starts, the preflight tries to create a file in each of the five folders of the Founder's records from inside the sandbox, and the session is started only when every one of those tries was refused: one that created a file, or a preflight that did not finish or did not try a folder, keeps that session from starting." | new with the sessions |
| `docs/operations.md`, the sitting | "The sandboxed agent cannot write `ledger/founder/`: the permission profile makes no part of it writable.", then what the preflight tries and when the agent is started, and that the boundary check has the agent try each folder with both of its tools | said the preflight "proves it" |
| `docs/operations.md`, reading the check | "Five of the fourteen are the folders of the Founder's records, ..., where an approval or any other record of the Founder's would have to be written." | said the check "shows for each that the agent cannot write an approval" |
| `docs/adr/0002-the-founder-decides-in-gr0wthlab.md`, the third rule | the preflight "tries to create a file in each record folder from inside the sandbox and the agent is started only when every try was refused" | said "every run's preflight tries each record folder" |
| `docs/prd/prd-marketing-engineer-v1_261008.md`, under the Guardrails | the same wording as the ADR's | the same |
| `config/guardrails/runtime.json`, its description | the same wording | the same |
| `src/gr0wthlab/codex.py`, `preflight_targets` | "a file has been tried in each of those folders from inside the sandbox, and the session is started only when every one of those tries was refused" | said the run "proves ... that the agent cannot write a decision" |
| `src/gr0wthlab/founder.py` and `boundary.py`, their comments | name the preflight before every session | said "every run's preflight" |
| `src/gr0wthlab/founder.py`, the line that refuses a records folder that is not a real folder | names the folder as `ledger/founder/<kind>` | named it by its full path, which a session's record and a run report would have carried |
| `docs/spikes/us-me02-runtime-boundary.md` | the preflight's forbidden places with the five folders among them, "so the check proves fourteen targets where it proved nine", and the limit on what bounds the sitting command | read, not changed |
| This file, round 2's routes | says the 26 commands failed, that their own errors were not kept, and which two had tried nothing | said 28 routes were refused |
| This file, elsewhere | "the preflight and the boundary check were run again", and the boundary checks "pass only when every write tried there has a record of its refusal" | said the boundary "was proved again", and "whose proof is that every write there is refused" |

Read and left as they are, being `main`'s own and printed for these folders as for any other: the launcher's lines for a preflight that created a file or fell short ("boundary preflight failed; the agent was not started", then each path it created, or that a path "must be refused but was not probed"), and the boundary check's lines, which name each of the five targets by its label.

### Unit tests and lint on the merge commit

- `/usr/bin/python3 -m unittest discover -s src/tests -t src`, under Python 3.9.6, run in the background on the merge commit while the live checks ran: 1276 tests, all passed, in 2027 s.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab`, ruff 0.15.20: clean.
- The test modules this change adds or rewrites most (`test_founder`, `test_page`, `test_serve`, `test_sitting`, `test_settings`, `test_probe`) also passed under Python 3.12.13, 212 tests, as a stand-in for CI's latest-Python job, which runs on Linux and was not run here.
- None of this change's tests asserts a count of the preflight's forbidden paths or a path only this Mac has: they name the five record folders inside each test's own temporary checkout.

## Round 4: after the review of how a sitting ends

Review changed how a sitting ends and what a run knows of it.
The page's last view now has one way to finish, which records the sitting, shows what was saved, and stops the page; the control that stopped the page without the record is gone.
A run marks what a sitting left undecided as carried over when it knows the sitting took place, from the sitting record or from the `sitting` date of a decision given at it, and reports the time of a sitting that left no record as not recorded.
The same round removed the `--port` option of `sitting` and the refusal of a configuration that still sets `mandu.exchange` or `GR0WTHLAB_EXCHANGE_DIR`, gave the run and the page one reader of a record file (`founder.parse`), and replaced the tests that read source text with tests that run the code.

The refusal that rounds 2 and 3 record under "A configuration that still names the exchange folder" no longer exists: the two settings are gone and are no longer read, so those two sections describe the code as it was then.

This round ran on 2026-10-13 from about 18:27 to 19:07, with Codex CLI 0.160.0, on the tree this record lands with: `src` tree `bf9c97894c6648bc3aded7a9043855d7c3432c3c`, `config` tree unchanged, `b43d0624383aada9155906ee4b54515c3ecb3a5d`.
`git status` in the worktree was not empty, since the round's changes were not committed yet; its listing was the same before the first command below and after the last.

### The boundary, from the worktree, on the real configuration

Run from the linked worktree, with `GR0WTHLAB_LOG_DIR` set to a folder under `<tmp>` and no other override, from 19:05.

| Command | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab show-config` | none (no model) | fingerprint `0a94ab4c7904c115f5a884f73c180172754eb8e9cd3e4e402837076ce3a54090` |
| `src/bin/gr0wthlab preflight` | none (no model) | 6 areas written; 19 paths refused, each of the five folders of the Founder's records among them by its own path; no breach and no failure; the listing of the footage place refused, none listed, none untried; both listed hosts unreachable, none reached, none untried |
| `src/bin/gr0wthlab boundary-check` | `20261014T020547Z-on-demand-f4a5` | PASSED at its first probe run; the same fingerprint; 43 steps to prove; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials, one `file-write-create` for each of the five folders among them; 1 of 1 forbidden read refused; 12 of 12 permitted sentinels written; no sentinel escaped; no local connection got through; nothing changed since the snapshot; agent time 49.1 s |

Before the preflight and after the boundary check, the `HEAD`, branch, `git status` listing, and stash count of the real Mandu, RepToday, and Immerse checkouts were read; the two readings are identical for all three.
A content hash of each checkout, as rounds 1 to 3 took, was not taken this round.
`~/Library/LaunchAgents` holds no gr0wthlab LaunchAgent.

### The finding, reproduced on the commit before this round

In a throwaway lab under `<tmp>`: an export of commit `87c69a394f69f84fb2d188b190a0154f4757f5f3` with the quiet settings the unit tests use, a synthetic Mandu and RepToday beside it, and the no-model Codex stand-in of `src/tests/fakes.py`, so no model was called.

| Step | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab run`, the stand-in writing five proposals | `20261014T013122Z-on-demand-750e` | 6 items open: the five proposals and the reviewed Dispatch request |
| `src/bin/gr0wthlab sitting`, three proposals approved and the Dispatch request rejected by posts as the page's own form sends them, then a post to the page's `stop` control | none | four decision records in `ledger/founder/decisions/`, no file in `ledger/founder/sittings/`, and the command ended |
| `src/bin/gr0wthlab run` | `20261014T013150Z-on-demand-fc8a` | the four decisions taken in; the two proposals left open with `carried_over` false; the report's summary says `0 carried over`; no `ledger/evidence/sittings/` |

### The same sitting on this round's code, ended both ways

Two labs built the same way from the worktree, each with a first run that left the same six items open, each sitting driven in headless Chrome through `chrome-devtools-axi`: the Dispatch request rejected with a typed reason and three proposals approved, each by a click on its button, and two proposals left.

| How the sitting ended | Runs | What the records showed |
| --- | --- | --- |
| The page's process was killed (`kill -KILL`) with the last view open and nothing recorded there | `20261014T013124Z-on-demand-8593`, then `20261014T013332Z-on-demand-cded` | no file in `ledger/founder/sittings/`; the second run took the four decisions in and left the two proposals open with `carried_over` true and `carried_over_from` `2026-10-13`; its report says `2 carried over` and `Sitting 2026-10-13: its time was not recorded.`; `ledger/evidence/sittings/2026-10-13.json` holds `"minutes": null`, the four decision records under `shown_by`, and the second run as `taken_in_by_run` |
| A click on `Record the sitting and stop the page` | `20261014T013345Z-on-demand-61e5`, then `20261014T013501Z-on-demand-7553` | the browser showed "The sitting has ended", "Saved. The sitting on 2026-10-13 took 1 minute.", and the four fields of the record as read back; the terminal said the record was saved and that the sitting had ended from the page, and the command ended; `ledger/founder/sittings/2026-10-13.json` holds 1 minute; the second run left the two proposals open with `carried_over` true from `2026-10-13`, and its Evidence of the sitting holds 1 minute and the sitting record as its source |

In the second lab the last view was opened, then `What I did`, then the last view again before the click: it showed 1 minute both times.
After that run, `git status` in the lab listed neither `ledger/founder.lock` nor `ledger/sitting.lock`.

Two wordings were corrected after these lab runs and before the boundary check above.
The first lab's page said "Ending the sitting below records it", which is wrong at a laptop's width, where the form is beside that sentence; the second lab ran with the sentence as it is now.
Both labs' second runs and the second lab's terminal said `1 minutes`; the run report and the terminal now say `1 minute`, which the unit tests cover and no lab run repeated.

### What round 4 did not exercise

- A sitting that ended with Ctrl-C in its terminal, or by a closed laptop: the kill above stands for both, since each leaves the records already written and no sitting record.
- A second sitting on the date of a first: the minutes of both, and a last view that never adds a sitting's minutes to its own record, stand on `src/tests/test_serve.py` and `src/tests/test_sitting.py`.
- A sitting whose record cannot be used, or a `sittings/` folder that cannot be read, beside a decision given at that sitting: `src/tests/test_cycle.py` holds that the run then keeps the sitting as one that took place and does not say that its time was not recorded.
- The real agent in a weekly run, the hole tests, and every route into the records: this round changed no part of the sandbox, the permission profile, or the probes, and the `config` tree is the one round 3 ran on.
- The page's other views, at both widths and in both color schemes: unchanged this round, so round 2's stand; only the last view was looked at again, at 1280 wide in light and at 390 wide in dark.
- A scheduled run, the real production clone, Mandu's side, and a browser other than Chrome, as in round 1.

### Unit tests and lint on this round's tree

- `/usr/bin/python3 -m unittest discover -s src/tests -t src`, under Python 3.9.6, run in the background before the live checks: 1287 tests in 1943 s, 1285 passed and 2 failed.
  Both failures were expectations, not launcher faults: a test of this round that had not counted the notice an unusable record queues, and `test_attempts.UnreachedFilmingTest`, which compared a notice entry whole, where the notice is now marked carried over from the sitting the filming plan was approved at.
  Both were corrected, and they passed with every test of the modules the corrections and the two wordings touch (`test_serve`, `test_page`, `test_report`, and the carry-over, decision, and sitting-record tests): 93 tests.
  The whole suite was not run again after those corrections.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab`, ruff 0.15.20: clean.
- The page's own script is now run in `src/tests/test_serve.py` under node, v20.19.5 here, against a stand-in page; the test is skipped where node is absent.
- The latest-Python job of CI, which runs on Linux, was not run here.

## Round 5: after the review of the carry-over rule

Review asked whether a sitting should be known from more than a decision, and the rule was decided as it stood: a run knows a sitting took place from its sitting record, which the page writes when the Founder ends the sitting on the page, or from a decision given at it, and nothing else is read as the sign of a sitting.
A sitting that ended without its record, by the terminal, a crash, or a closed laptop, and at which no decision was given, leaves no mark: its undecided items stay open and come back at the next sitting without the carried-over mark, nothing records its time, the run report has no line for it, and nothing the Founder saved is lost.
This round changed no part of that rule in code; it states the rule and that corner the same way wherever either is described, and holds the corner with a unit test.

It also changed launcher code in four small ways, which is why the boundary was checked again:

- The three Beta Cohort counts have one set of names, `beta.COUNT_LABELS`, which the run report, the page's fields, and the reason a typed count is refused all use; the page's third field is now `Sessions booked`, where it said `First sessions booked`.
- `exchange.plural` and `exchange.MAX_MINUTES` replace the page's own copies of each.
- `beta.record_file`, which had become another name for `founder.shown`, is gone.
- The records step no longer repeats the name of a file under `workspace/` or `ledger/` that looks like an email address when the file could not be read, as it already did not when the file was left out for another reason.

This round ran on 2026-10-13 from about 19:31 to 20:07, with Codex CLI 0.160.0, on the tree this record lands with: `src` tree `1fdba66cdfdd17a2c9ed3390d882733b7cd5101c`, `config` tree unchanged, `b43d0624383aada9155906ee4b54515c3ecb3a5d`.
`git status` in the worktree was not empty, since the round's changes were not committed yet; its listing was the same before the preflight and after the boundary check.

### The boundary, from the worktree, on the real configuration

Run from the linked worktree, with `GR0WTHLAB_LOG_DIR` set to a folder under `<tmp>` and no other override, from 20:05, after the unit suite below had ended.

| Command | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab show-config` | none (no model) | fingerprint `0a94ab4c7904c115f5a884f73c180172754eb8e9cd3e4e402837076ce3a54090`, the one round 4 printed |
| `src/bin/gr0wthlab preflight` | none (no model) | 6 areas written; 19 paths refused, each of the five folders of the Founder's records among them by its own path; no breach and no failure; the listing of the footage place refused, none listed, none untried; both listed hosts unreachable, none reached, none untried |
| `src/bin/gr0wthlab boundary-check` | `20261014T030533Z-on-demand-4643` | PASSED at its first probe run; the same fingerprint; 43 steps to prove; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials, one `file-write-create` for each of the five folders among them; 1 of 1 forbidden read refused; 12 of 12 permitted sentinels written; no sentinel escaped; no local connection got through; nothing changed since the snapshot; agent time 70.7 s |

Before the preflight and after the boundary check, the `HEAD`, branch, `git status` listing, and stash count of the real Mandu, RepToday, and Immerse checkouts were read; the two readings are identical for all three.
A content hash of each checkout was not taken this round.
`~/Library/LaunchAgents` holds no gr0wthlab LaunchAgent.

### The corner, and the renamed field, in a lab

One throwaway lab under `<tmp>`, built from the worktree as round 4's were, with what Beta Cohort recruiting starts from beside it (the example set's Mandu overlay and a made-up Waitlist view) and the no-model Codex stand-in, so no model was called.
The sitting was driven in headless Chrome through `chrome-devtools-axi`.

| Step | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab run`, the stand-in writing five proposals | `20261014T023234Z-on-demand-8d59` | 6 items open: the five proposals and the reviewed Dispatch request |
| `src/bin/gr0wthlab sitting`: a Beta Build recorded on `What I did` by a click; on the counts view, `2.5` typed in the third field and the form sent | none | the field reads `Sessions booked` and the page answered "Nothing was saved." and "Sessions booked must be a whole number, written in digits." |
| the same view: 3 invitations sent and 1 accepted typed, the third field left blank, and the form sent | none | the page showed "Saved. RepToday, on 2026-10-13: invitations sent 3, accepted 1, sessions booked not reported."; the terminal said `saved founder/beta-reports/RepToday-2026-10-13.json` |
| the last view opened, no item decided, then the page's process killed (`kill -KILL`) | none | no file in `ledger/founder/decisions/` and none in `ledger/founder/sittings/` |
| `src/bin/gr0wthlab run` | `20261014T023346Z-on-demand-ea9a` | all six items still open, each with `carried_over` false and no `carried_over_from`; the report's summary says `0 carried over`; its Sittings source reads `0 records, 0 new` and its Beta Cohort reports source `1 record, 1 new`; the report has no line of a sitting; no `ledger/evidence/sittings/`; the Evidence of the Beta Cohort report holds 3, 1, and not reported, taken in by this run |

That second run also queued one notice of its own problems, new and not carried over: the stand-in wrote no recruiting Draft.
The last view's closing lines read, in that browser, as the page now has them: with a decision given, the next run marks what was left as carried over and reports the sitting's time as not recorded, and with none the sitting leaves no mark.

### What round 5 did not exercise

- The unreadable file named like an email address among the Founder's records: `src/tests/test_records.py` holds it against a real git repository, and no lab run made one.
- The real agent in a weekly run, the hole tests, every route into the records, and a sitting ended on the page: this round changed none of them, so rounds 3 and 4 stand.
- The page's other views: unchanged this round but for the two wordings above.
- A scheduled run, the real production clone, Mandu's side, and a browser other than Chrome, as in round 1.

### Unit tests and lint on this round's tree

- `/usr/bin/python3 -m unittest discover -s src/tests -t src`, under Python 3.9.6, run in the background on this round's tree and ended before the live checks began: 1289 tests in 1963 s, and none failed.
  Nothing under `src/` or `config/` changed after that run began.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab`, ruff 0.15.20: clean.
- The latest-Python job of CI, which runs on Linux, was not run here.

## Round 6: the page's own name for the third count, and the corner in plain words

Round 5 had the page take the run report's names for the three Beta Cohort counts, which renamed the page's third field to `Sessions booked`.
That rename was not asked for, and the count means first sessions, so this round put the page's words back: the third count is `First sessions booked` on its field, in the reason a value typed there is refused, in what the page says was saved, and in its `Last given on` line.
The page still has one set of names for the three, `sitting.COUNT_LABELS`, which the field and its refusal both read; the run report's own line keeps the wording it has on `main`, `sessions booked`, and neither follows the other.

This round also says the corner of round 5 in plain words wherever it is described.
For a sitting that left no sitting record and at which no decision was given, the run knows of no sitting: nothing records that sitting's time, and the run report has no line for it.
The instruction for round 5's test had said the run report would say the time was not recorded; that was wrong for this corner and was withdrawn, and the test's assertions, which hold that the report has no line of a sitting, stand as they were.

This round changed only the page (`src/gr0wthlab/sitting.py` and `src/gr0wthlab/page.py`), its tests, and documents, so no preflight and no boundary check was owed, and neither was run: round 5's stand.
It ran on 2026-10-13 from about 20:26 to 20:57, on the tree this record lands with: `src` tree `36050227b795155180020e3d0a5e7039d6f7e032`, `config` tree unchanged, `b43d0624383aada9155906ee4b54515c3ecb3a5d`.

### The page in a browser

One throwaway lab under `<tmp>`, built from the worktree as round 5's was, with the no-model Codex stand-in, so no model was called; the sitting was driven in headless Chrome through `chrome-devtools-axi`.

| Step | Run | What the page showed |
| --- | --- | --- |
| `src/bin/gr0wthlab run`, the stand-in writing five proposals | `20261014T032613Z-on-demand-d548` | 6 items open |
| `src/bin/gr0wthlab sitting`: a Beta Build recorded on `What I did` by a click; on the counts view, `2.5` typed in the third field and the form sent | none | the field reads `First sessions booked`, and the page answered "Nothing was saved." and "First sessions booked must be a whole number, written in digits." |
| the same view: 3 invitations sent and 1 accepted typed, the third field left blank, and the form sent | none | "Saved. RepToday, on 2026-10-13: invitations sent 3, accepted 1, first sessions booked not reported.", and "Last given on 2026-10-13: invitations sent 3, accepted 1, first sessions booked not reported." |
| the last view opened | none | its closing lines end: "With none, the sitting leaves no mark: what you left comes back without the carried-over mark, nothing records its time, and the run report has no line for it." |
| the page's process sent `kill -TERM`, the signal whose handler Ctrl-C shares | none | the terminal said `the sitting page has stopped`, and the command ended |

No run followed that sitting: round 5's lab and `src/tests/test_serve.py` hold what a run makes of it.

### What round 6 did not exercise

- The preflight, the boundary check, the hole tests, and a weekly run with the real agent: this round changed no launcher code and no part of the permission profile.
- The run report's counts line: unchanged, and `src/tests/test_sitting.py` and `src/tests/test_beta_cycle.py` hold its wording.
- The page's other views, a narrow width, and the dark color scheme: unchanged this round.
- A scheduled run, the real production clone, Mandu's side, and a browser other than Chrome, as in round 1.

### Unit tests and lint on this round's tree

- `/usr/bin/python3 -m unittest discover -s src/tests -t src`, under Python 3.9.6, run in the background on this round's tree: 1289 tests in 1839 s, and none failed.
  Nothing under `src/` or `config/` changed after that run began.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab`, ruff 0.15.20: clean.
- The latest-Python job of CI, which runs on Linux, was not run here.

## Round 7: what the page says of a closed item, a replaced one, and a post's video

Review found three places where the page said less, or other, than the records show, and this round changed each:

- An act on an item that a run closed meanwhile, as `Take it back` or `Reject` in a tab opened before the run ended, saves nothing, and the page now says so: the start view it answers with opens with "Nothing was saved." and the reason.
  Asking for such an item by its address says that the item is not open in the Review Queue.
- An item that replaces an earlier one shows, beside "It replaces" and the earlier item, the decision the Founder recorded for that item: approved or rejected, when, and the reason or note in the Founder's own words.
- Whether a post's video can be played and approved is now the launcher's own answer (`filming.posted_file`): a post whose finished file is intact but whose video record is missing or names another digest is not offered for approval with its video, and the page says why in the words a run report would use.

The PRD's line about the repository says again what `main` says, that the repository is private.
This round changed only the page (`src/gr0wthlab/sitting.py`, `page.py`, `serve.py`, and `src/sitting/page.css`), its tests, and documents, so no preflight and no boundary check was owed, and neither was run.
It ran on 2026-10-13 from about 21:21 to 21:55, on the tree this record lands with: `src` tree `1410a7452dcec392f9ce254d8ea38515507eb437`, `config` tree unchanged, `b43d0624383aada9155906ee4b54515c3ecb3a5d`.

### The page in a browser

One throwaway lab under `<tmp>`, built from the worktree as earlier rounds' were, with the no-model Codex stand-in, so no model was called; the sitting was driven in headless Chrome through `chrome-devtools-axi`.

| Step | Run | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab run`, the stand-in writing two proposals | `20261014T042233Z-on-demand-b627` | 3 items open: the two proposals and the reviewed Dispatch request |
| `src/bin/gr0wthlab sitting`: one proposal approved by a click, and its view opened again, which offered `Take it back` | none | the decision record holds `approve` |
| `src/bin/gr0wthlab run`, with that view still open | `20261014T042250Z-on-demand-dea3` | the approval taken in: the item closed as approved |
| `Take it back` clicked in the open view | none | the page answered with the start view, which opened with "Nothing was saved." and "This item is not open in the Review Queue any more, so nothing was saved.", above "A run finished since you began."; the decision record still holds `approve` |
| the item's address opened | none | the start view says "The item 20261013-one is not open in the Review Queue, so there is nothing to decide on it." |

That first look showed the "Nothing was saved." block touching the note under it at the top of the start view, so the style sheet gives it the space a note has; the same post, sent again from that browser, showed the two apart.

### What round 7 did not exercise

- The decision on a replaced item, on the page in a browser: a run must replace an item while a decision on it is given, which the lab cannot time by hand; `src/tests/test_sitting.py` holds it on the page's own view, and `src/tests/test_page.py` holds that the Founder's words in it are shown as text.
- A post's video in a browser: the lab had no filming; `src/tests/test_sitting.py` holds, on a whole filming run's records, that a changed, missing, or unrecorded file is not offered for approval and what the page says of each.
- The preflight, the boundary check, the hole tests, and a weekly run with the real agent: this round changed no launcher code and no part of the permission profile.

### Unit tests and lint on this round's tree

- `/usr/bin/python3 -m unittest discover -s src/tests -t src`, under Python 3.9.6, run in the background on this round's tree: 1289 tests in 1641 s, and none failed.
  Only `src/sitting/page.css` changed after that run began, and `src/tests/test_serve.py`, which serves it, passed again afterwards: 32 tests.
- `ruff check` and `ruff format --check` on `src` and `src/bin/gr0wthlab`, ruff 0.15.20: clean.
- The latest-Python job of CI, which runs on Linux, was not run here.

## Screenshots

Taken in round 2, on the page code as it was then, from the synthetic checkout; every name, message, and figure in them is fixture text.
The merge in round 3 changed none of the page's own files.
Rounds 4 to 6 changed two views, the Beta Cohort counts and the end of the sitting, and both screenshots were taken again in round 6, from that round's lab, on the page as it is now.

| Screen | Laptop, 1280 wide | Narrow, 390 wide |
| --- | --- | --- |
| The start: what the last run reports, then the queue | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/01-start-laptop-light.png) | [dark](20261013-gr0wthlab-decisions-in-gr0wthlab/12-start-narrow-dark.png) |
| One item: a post with its video | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/02-post-with-video-laptop-light.png) | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/10-post-with-video-narrow-light.png) |
| The next item, with what was just saved read back | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/03-next-item-after-saving-laptop-light.png) | |
| A line refused at entry | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/04-refused-laptop-light.png) | |
| An item whose text carries markup, shown as text | [dark](20261013-gr0wthlab-decisions-in-gr0wthlab/05-item-text-is-inert-laptop-dark.png) | |
| The queue | [dark](20261013-gr0wthlab-decisions-in-gr0wthlab/06-queue-laptop-dark.png) | |
| The Beta Cohort counts, saved | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/07-counts-saved-laptop-light.png) | |
| What I did: a message recorded as sent | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/08-message-recorded-as-sent-laptop-light.png) | |
| The end of the sitting | [light](20261013-gr0wthlab-decisions-in-gr0wthlab/09-end-of-the-sitting-laptop-light.png) | |
| A table at a narrow width | | [dark](20261013-gr0wthlab-decisions-in-gr0wthlab/11-table-narrow-dark.png) |

## Limits these checks showed

- A sitting has one record for its date.
  Items a run queued between two sittings held on the same day, and left undecided at the second, are not marked carried over: the rule in `queue.py` marks an item from a sitting whose record first reached a run after the run that queued it, and the second sitting corrects the first one's record.
  It was so before this change, when Mandu wrote the same record, and the lab's two sittings on one day showed it.
- A message recorded as sent by mistake can be corrected, not unmarked.
  The one thing that follows from it is a follow-up Draft after the wait, which the Founder can reject.
- The lock a run and a page change share, `ledger/founder.lock`, is inside `ledger/`, which the profile lets a sandboxed process read.
  A process the agent started that outlived the run and held that lock would make the next run's take-in, or a change on the page, wait its 10 seconds and say so; holding a lock writes nothing.
  This was not tried live; round 3's route check tried only a write to that file from inside the sandbox, which failed with `Operation not permitted`.
- The page says a run is overdue once the next run's time has passed; it does not say that a run is going right now.
