# Live checks: the Founder decides in gr0wthlab, on a local page (US-ME04, US-ME07)

This file records what was run on the Founder's Mac for the change that moves the Founder's decisions and records from Mandu into `ledger/founder/` and adds the sitting page ([ADR 0002](../adr/0002-the-founder-decides-in-gr0wthlab.md)).
It also covers the records the same page now writes for US-ME09 (the filming plan), US-ME14 (a message sent and replied to), and US-ME15 (the Beta Build approval and the Beta Cohort counts).
CI cannot run any of it: it needs the Mac, the Codex login, and a browser.

How to read the paths:

- `~` is the home folder.
- `<tmp>` is the Mac's per-user temporary folder, the one `getconf DARWIN_USER_TEMP_DIR` prints.
- `<lab>` is the throwaway lab under `<tmp>` described below.
- Where a quoted line held the home folder's or the temporary folder's full path, that prefix was replaced with `~` or `<tmp>`.

All times are Mac local time (PDT, UTC-7) on 2026-10-12; a run identifier carries the UTC date, which was already 2026-10-13.
Codex CLI 0.160.0 with `gpt-6-luna` at `high` reasoning effort throughout.

## What nothing here touched

- The real Mandu, RepToday, and Immerse checkouts were never written.
  Before the first live run and after the last one, each checkout's `HEAD`, branch, `git status`, stash list, and one SHA-256 over every file outside `.git` were recorded; the two readings are identical for all three.
- The only commands that named the real checkouts ran from the worktree: `show-config`, the two preflights, which leave Mandu and the Products out of what they try, and the two boundary checks, whose proof is that every write there is refused.
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

- Mandu's side reading the queue and the records: nobody has built it, and this change does not touch Mandu.
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
That commit changes launcher code, so the boundary was proved again on it, from 18:20.
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

In a scratch clone of `256628e` under `<tmp>`, with synthetic checkouts beside it and one seeded record, a shell script ran under `codex sandbox` with the launcher's own overrides and environment, as the per-run preflight runs.
It tried 28 routes and printed, for each, whether the command succeeded.

- Refused, all 28: overwrite, append to, truncate, remove, rename, and `chmod` a record; create a file in each of the five folders and in `ledger/founder/` itself; make a folder there; copy a file in; move a workspace file in; hard link a record into `workspace/`; hard link a workspace file into a records folder; write through a symbolic link to a record; create a file through a symbolic link to a records folder; rename `ledger/founder/decisions`, `ledger/founder/`, and `ledger/`; replace a records folder with a link; `chmod` a records folder; write `ledger/founder.lock`; create `ledger/sitting.lock`.
- Allowed: reading a record, and making a symbolic link in `workspace/` that points at a record or a records folder.
  Neither gains anything: the launcher reads a record only as a plain single-link file directly in one of the five real folders, and never follows a link in `workspace/`.
- One digest over every entry under `ledger/founder/` (path, mode, link count, SHA-256) was the same before and after.

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

## Screenshots

Taken in round 2, on the final page code, from the synthetic checkout; every name, message, and figure in them is fixture text.

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
- The lock a run and a page change share, `ledger/founder.lock`, is a file a sandboxed process can read and cannot write.
  A process the agent started that outlived the run and held that lock would make the next run's take-in, or a change on the page, wait its 10 seconds and say so; it could not write a record.
  This was not tried live.
- The page says a run is overdue once the next run's time has passed; it does not say that a run is going right now.
