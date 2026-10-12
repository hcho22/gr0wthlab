# gr0wthlab agent memory

gr0wthlab is the Marketing Engineer's repository; [`README.md`](README.md) gives the purpose, actors, weekly cycle, Guardrails, and layout.

- Use the vocabulary in [`CONTEXT.md`](CONTEXT.md): capitalized terms (Founder, Product, Draft, Evidence, Go-To-Market Package, Review Queue, and the rest) carry only the senses defined there.
- [ADR 0001](docs/adr/0001-evidence-and-drafts-only.md) is the founding boundary: this repository holds Evidence, Drafts, and Review Queue items, never strategy; Go-To-Market Packages stay in Mandu, and Product changes go to firstmate as Dispatches.
- [The v1 PRD](docs/prd/prd-marketing-engineer-v1_261008.md) is the story tracker: when a story lands and its Validation Test passes, flip that story's acceptance-criteria checkboxes and no others.
- `workspace/` is the agent's only writable tree (Guardrail G1); code in `src/`, configuration in `config/` (Guardrails, the Product registry, and the run settings), and docs change only through firstmate's reviewed pull requests (G8).
  Keep that split when adding files: the Codex permission profile in [`config/guardrails/runtime.json`](config/guardrails/runtime.json) makes exactly the six `workspace/` areas writable, and the launcher's own records go in `ledger/`, which a run can read and never write.
- Every run starts through `src/bin/gr0wthlab`; the [US-ME02 spike note](docs/spikes/us-me02-runtime-boundary.md) explains the boundary.
  A change to the launcher, `runtime.json`, or `products.json` needs a fresh `src/bin/gr0wthlab boundary-check` on the Founder's Mac, which CI cannot run.
- A run is `src/gr0wthlab/cycle.py` around the sandboxed agent: deterministic work (snapshot, decisions, item validation, queue order, report, git records) is launcher code with unit tests, judgment is the agent's under the fixed task definition in `src/instructions/`, and [operations](docs/operations.md) covers the production clone and schedule.
  The agent adds Review Queue items only through `workspace/review-queue/incoming/`, never a post or a message, which the launcher renders only from a checked Draft (`FROM_DRAFT` in `src/gr0wthlab/queue.py`); the launcher publishes them into `ledger/`, where it alone writes the queue, its own Evidence, run reports, and per-workflow run state.
  Run state (`src/gr0wthlab/state.py`) is a convenience validated every run: the Review Queue and Mandu's decision records stay the source of truth.
- Every run ends with its report (US-ME17), so nothing the launcher waits for may wait forever: start a process only through `src/gr0wthlab/process.py`, which gives it a time limit and stops it with every process the process table shows it started; `src/tests/test_process.py` watches a whole run and fails when a process it starts does not go through `process.run` or is waited on without a time limit.
  The agent's own limit is `agent.time_limit_seconds` in `config/run.json`, and [operations](docs/operations.md#when-a-run-times-out) says what a timed-out run leaves.
- Guardrail G6 lives in launcher code: only `src/gr0wthlab/waitlist.py` reads RepToday's anonymous Waitlist view, from a path outside everything the sandbox reads, checks every value for an email address before anything else, and keeps entry identifiers and counts only; never route the view, or anything else read from it, to the agent.
  The launcher files Dispatch requests from reviewed text in `src/dispatches/`; the Waitlist request is also the view's format, and `src/tests/test_dispatch.py` keeps the two in step.
- Beta Cohort recruiting (`src/gr0wthlab/beta.py`) starts only from the Founder's Beta Build record in Mandu's exchange folder, which launcher code reads and never infers; before it exists a run does nothing about the Beta Cohort.
  Who is invited is ordered only in `waitlist.py` (`SELECTION_RULE`) and attached to the item by the launcher, so no entry identifier goes into the agent's brief or into a Draft; a recruiting Draft (`beta_drafts.py`) holds no address, no link, and no figure a cited package line does not hold.
  Only the counts the Founder reports are kept, and a count left out is not reported, never zero.
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
