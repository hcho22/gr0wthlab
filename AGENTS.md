# gr0wthlab agent memory

gr0wthlab is the Marketing Engineer's repository; [`README.md`](README.md) gives the purpose, actors, weekly cycle, Guardrails, and layout.

- Use the vocabulary in [`CONTEXT.md`](CONTEXT.md): capitalized terms (Founder, Product, Draft, Evidence, Go-To-Market Package, Review Queue, and the rest) carry only the senses defined there.
- [ADR 0001](docs/adr/0001-evidence-and-drafts-only.md) is the founding boundary: this repository holds Evidence, Drafts, and Review Queue items, never strategy; Go-To-Market Packages stay in Mandu, and Product changes go to firstmate as Dispatches.
- [The v1 PRD](docs/prd/prd-marketing-engineer-v1_261008.md) is the story tracker: when a story lands and its Validation Test passes, flip that story's acceptance-criteria checkboxes and no others.
- `workspace/` is the agent's only writable tree (Guardrail G1); code in `src/`, configuration in `config/` (Guardrails, the Product registry, and the run settings), and docs change only through firstmate's reviewed pull requests (G8).
  Keep that split when adding files: the Codex permission profile in [`config/guardrails/runtime.json`](config/guardrails/runtime.json) makes exactly the six `workspace/` areas writable, and the launcher's own records go in `ledger/`, which a run can read and never write.
- Every run starts through `src/bin/gr0wthlab`; the [US-ME02 spike note](docs/spikes/us-me02-runtime-boundary.md) explains the boundary.
  A change to the launcher, `runtime.json`, `fetch.json`, or `products.json` needs a fresh `src/bin/gr0wthlab boundary-check` on the Founder's Mac, which CI cannot run.
  That check (`src/gr0wthlab/probe.py`) proves each forbidden target on its own from the runtime's records, Codex's record of each tool call (kept under `codex.LOG_FILTER`) and the kernel's log, never from a count or the agent's report; a change may make the probe easier for the agent to carry out, never the proof looser.
  Every line it prints, and every sentence the docs say about its output, states only what a record shows and names no cause beyond it.
- A run is `src/gr0wthlab/cycle.py` around the sandboxed agent: deterministic work (snapshot, decisions, item validation, queue order, report, git records) is launcher code with unit tests, judgment is the agent's under the fixed task definition in `src/instructions/`, and [operations](docs/operations.md) covers the production clone and schedule.
  The agent adds Review Queue items only through `workspace/review-queue/incoming/`, never a post or a message, which the launcher renders only from a checked Draft (`FROM_DRAFT` in `src/gr0wthlab/queue.py`); the launcher publishes them into `ledger/`, where it alone writes the queue, its own Evidence, run reports, and per-workflow run state.
  Run state (`src/gr0wthlab/state.py`) is a convenience validated every run: the Review Queue and Mandu's decision records stay the source of truth.
- Every run ends with its report (US-ME17), so nothing the launcher waits for may wait forever: start a process only through `src/gr0wthlab/process.py`, which gives it a time limit and stops it with every process the process table shows it started; `src/tests/test_process.py` watches a whole run and fails when a process it starts does not go through `process.run` or is waited on without a time limit.
  The agent's own limit is `agent.time_limit_seconds` in `config/run.json`, and [operations](docs/operations.md#when-a-run-times-out) says what a timed-out run leaves.
  A network read is bounded the same way: `fetch.send` ends each wait at `timeout_seconds` and each whole read at `read_deadline_seconds`, both in `config/guardrails/fetch.json`.
- Nothing holds the Mac awake, wakes it, or schedules a wake (the Founder's decision of 2026-10-11; `src/tests/test_attempts.py` watches every process a scheduled run starts and every LaunchAgent key): each week's run happens when the Mac is awake.
  A start of the weekly schedule is first the owed-run check in `src/gr0wthlab/attempts.py`, which begins a run only while `ledger/run-reports/attempts/` shows the week's run still owed and the Mac is fully awake, not in a dark wake; a one-off start (`--once`) always runs, as a run on demand does, and is never an attempt.
  Only an attempt that did not complete and that the Mac slept during, anywhere from its start to its agent's end, earns another, within `schedule.attempts_per_week`; [operations](docs/operations.md#a-run-happens-when-the-mac-is-awake) has the rules, and a change to the schedule's day, time, or check interval in `config/run.json` needs the LaunchAgent installed again.
- The agent's closing `Review:` line is its own word, and it has read complete after the shallowest sessions: judge a run, and any change to the agent's settings or task definition, by what the launcher counts of the session (`src/gr0wthlab/work.py`, shown in the run report beside that line; [operations](docs/operations.md#reading-the-agents-work)).
  Those counts inform the Founder and never gate; the agent's reasoning effort is `codex.reasoning_effort` in `runtime.json`, and more wording in the task definition did not stop a session ending early.
- Guardrail G6 lives in launcher code: only `src/gr0wthlab/waitlist.py` reads RepToday's anonymous Waitlist view, from a path outside everything the sandbox reads, checks every value for an email address before anything else, and keeps entry identifiers and counts only; never route the view, or anything else read from it, to the agent.
  The launcher files Dispatch requests from reviewed text in `src/dispatches/`; the Waitlist request is also the view's format, and `src/tests/test_dispatch.py` keeps the two in step.
- Beta Cohort recruiting (`src/gr0wthlab/beta.py`) starts only from the Founder's Beta Build record in Mandu's exchange folder, which launcher code reads and never infers; before it exists a run does nothing about the Beta Cohort.
  Who is invited is ordered only in `waitlist.py` (`SELECTION_RULE`) and attached to the item by the launcher, so no entry identifier goes into the agent's brief or into a Draft; a recruiting Draft (`beta_drafts.py`) holds no address, no link, and no figure a cited package line does not hold.
  Only the counts the Founder reports are kept, and a count left out is not reported, never zero.
- The sandboxed agent has no network, and nothing may give it one.
  `src/gr0wthlab/fetch.py` is the launcher's only way onto the network (a credential-free GET to a host in [`config/guardrails/fetch.json`](config/guardrails/fetch.json), bound by that host's `robots.txt`), and `src/tests/test_fetch.py` holds the contract by what goes on the wire: add no other way onto the network, method, credential, or exception to `robots.txt`.
  No unit test opens the network; `src/tests/__init__.py` replaces `fetch.send` with a refusal and refuses any other connection beyond the machine at the socket, so give a client a `fakes.Web`.
- Fetched text is data, never instructions: it reaches the agent only as the launcher's snapshot (`sources.py`), and a record only as a quote `evidence.py` found word for word in that snapshot.
  The snapshot is working data in `ledger/working/`, which git ignores and the launcher removes when the run ends.
  The retention rule is about what the launcher keeps of what a run fetched.
  As Evidence of what was fetched it keeps only a validated quote, with its link, date read, and document hash, beside the rules a subreddit's rules notice quotes.
  The request log it commits (`ledger/run-reports/<run id>.requests.json`) also holds the `robots.txt` rule lines of the group that applied to each host, each Allow and Disallow with its path as fetched, beside the addresses and outcomes.
  Known gaps, not yet decided by the Founder: nothing else the agent writes is checked against what was fetched, so text of its own that repeats a source's words is committed today in each of these places.
  A file set aside from `incoming/` is copied whole to `ledger/review-queue/set-aside/<run id>/`.
  A Draft stays in `workspace/` and is committed as written until it passes or is rewritten, as is any other file the agent leaves in `workspace/` that the launcher neither takes in nor puts back.
  The reasons in a run report or a notice can repeat pieces of a file's text (a front matter line, up to 80 characters of an Evidence line, the headings found), and the reasons a Draft's checks give can quote the Draft.
  The reasons an edit record's checks give can quote its `shot` and `source` values whole.
  The run report quotes the agent's own summary, up to 4,000 characters.
  What the launcher accepts keeps the agent's own words: the text of a queued item, the context of a kept quote, and the line that says why a rejection code fits.
  Three things are removed and leave their file name and the launcher's reasons only: a refused quote record, a discarded `angles/` proposal, and a set-aside rejection code.
  An item marks any text a third party wrote with `exchange.third_party`, the one marking [`docs/mandu-exchange.md`](docs/mandu-exchange.md) tells Mandu's side is data.
  The agent's work in Listening and outreach is taken in the same way as a post Draft: a quote, a proposed Angle or Hook, and a message each become a record or an item only through `listening.py`, `outreach.py`, and `messages.py`.
  Every package-change proposal declares `new_angle`: one that declares `yes`, since it adds or changes an Angle or Hook (FR-7), is queued only when its Evidence names a kept quote's record exactly (`queue.declaration_problem`), and one that declares `no` is queued whatever it touches or says.
  No wording check stands behind a declaration: it is shown on the item, and the Founder is the check on a wrong one.
- The rejection codes and their execution-versus-strategy split live in `src/gr0wthlab/learning.py`, which also puts `workspace/instructions/` back after every run; US-ME16 opens that gate for execution codes only.
- [`docs/mandu-exchange.md`](docs/mandu-exchange.md) is the versioned contract Mandu's own agent implements; a format change bumps its version and needs Mandu's side changed with it.
- A post item exists only as the launcher's rendering of a Draft in `workspace/drafts/posts/` that passed every check in `src/gr0wthlab/drafts.py` (driven by `posts.py`); the brand lint's only rule source is Mandu's `brand-rules.json`, so a word list changes through a package-change proposal (`src/proposals/`), never in gr0wthlab, and platform facts live in `config/platforms.json`.
- Filming (US-ME09) keeps the Founder's raw footage private and whole: only the launcher reads the footage place (`filming.footage` in `config/products.json`, outside the repository and never a sandbox read grant), and nothing in gr0wthlab writes, renames, or deletes there.
  The launcher files the filming plan from the kit (`shots.py`, `filming.py`) and renders finished video with ffmpeg (`video.py`) into `ledger/assets/`, which never enters git; the agent, which cannot watch video, only writes edit records in `workspace/drafts/edits/` (`edits.py` checks them).
  One rule covers an A/B pair's videos: when a run ends, the pair's two posts never both show a video unless the two show the same source ranges outside each one's opening.
  `Filming.pair_check` keeps it once per pair, on the videos' own asset records, after `posts.take` has settled every day and before it queues any; keep it the only place a leg is judged by its other leg's video.
  Tests that need the real ffmpeg skip with a reason where it is absent; the fake tooling in `src/tests/fakes.py` covers whole runs everywhere.
- Each workflow ships an example set in `src/examples/<workflow>/evals.json` built on synthetic fixtures, never a Product's package; its deterministic assertions run in the unit tests, and adapted third-party text is listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- Code runs under the Mac's `/usr/bin/python3` (3.9), standard library only; [the CI workflow](.github/workflows/ci.yml) defines the tests and lint every change must pass.
- No reference copy of any Go-To-Market Package lives in this repository: configuration, the Product registry ([`config/products.json`](config/products.json)), and Instructions point to Mandu instead of restating package content.
  A record (Draft, proposal, Evidence, memo) may quote only the specific package text it uses or proposes, citing its Mandu source.
  The specification and decision records under `docs/` (including `docs/prd/design-decisions-2026-10-08.md`) and `CONTEXT.md` are committed as written.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
