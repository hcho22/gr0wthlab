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
  The agent adds Review Queue items only through `workspace/review-queue/incoming/`; the launcher publishes them into `ledger/`, where it alone writes the queue, its own Evidence, run reports, and per-workflow run state.
  Run state (`src/gr0wthlab/state.py`) is a convenience validated every run: the Review Queue and Mandu's decision records stay the source of truth.
- Guardrail G6 lives in launcher code: only `src/gr0wthlab/waitlist.py` reads RepToday's anonymous Waitlist view, from a path outside everything the sandbox reads, checks every value for an email address before anything else, and keeps entry identifiers and counts only; never route the view, or anything else read from it, to the agent.
  The launcher files Dispatch requests from reviewed text in `src/dispatches/`; the Waitlist request is also the view's format, and `src/tests/test_dispatch.py` keeps the two in step.
- [`docs/mandu-exchange.md`](docs/mandu-exchange.md) is the versioned contract Mandu's own agent implements; a format change bumps its version and needs Mandu's side changed with it.
- A post item exists only as the launcher's rendering of a Draft in `workspace/drafts/posts/` that passed every check in `src/gr0wthlab/drafts.py` (driven by `posts.py`); the brand lint's only rule source is Mandu's `brand-rules.json`, so a word list changes through a package-change proposal (`src/proposals/`), never in gr0wthlab, and platform facts live in `config/platforms.json`.
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
