# gr0wthlab agent memory

gr0wthlab is the Marketing Engineer's repository; [`README.md`](README.md) gives the purpose, actors, weekly cycle, Guardrails, and layout.

- Use the vocabulary in [`CONTEXT.md`](CONTEXT.md): capitalized terms (Founder, Product, Draft, Evidence, Go-To-Market Package, Review Queue, and the rest) carry only the senses defined there.
- [ADR 0001](docs/adr/0001-evidence-and-drafts-only.md) is the founding boundary: this repository holds Evidence, Drafts, and Review Queue items, never strategy; Go-To-Market Packages stay in Mandu, and Product changes go to firstmate as Dispatches.
- [The v1 PRD](docs/prd/prd-marketing-engineer-v1_261008.md) is the story tracker: when a story lands and its Validation Test passes, flip that story's acceptance-criteria checkboxes and no others.
- `workspace/` is the agent's only writable tree (Guardrail G1); code in `src/`, configuration in `config/` (Guardrails, the Product registry, and the run settings), and docs change only through firstmate's reviewed pull requests (G8).
  Keep that split when adding files: the Codex permission profile in [`config/guardrails/runtime.json`](config/guardrails/runtime.json) makes exactly the six `workspace/` areas writable.
- Every run starts through `src/bin/gr0wthlab`; the [US-ME02 spike note](docs/spikes/us-me02-runtime-boundary.md) explains the boundary.
  A change to the launcher, `runtime.json`, or `products.json` needs a fresh `src/bin/gr0wthlab boundary-check` on the Founder's Mac, which CI cannot run.
- A run is `src/gr0wthlab/cycle.py` around the sandboxed agent: deterministic work (snapshot, decisions, item validation, queue order, report, git records) is launcher code with unit tests, judgment is the agent's under the fixed task definition in `src/instructions/`, and [operations](docs/operations.md) covers the production clone and schedule.
  The agent adds Review Queue items only through `workspace/review-queue/incoming/`; the launcher alone writes the queue, decision Evidence, snapshots, run reports, and per-workflow run state, and undoes any agent change to them.
  Run state (`src/gr0wthlab/state.py`) is a convenience validated every run: the Review Queue and Mandu's decision records stay the source of truth.
- [`docs/mandu-exchange.md`](docs/mandu-exchange.md) is the versioned contract Mandu's own agent implements; a format change bumps its version and needs Mandu's side changed with it.
- Code runs under the Mac's `/usr/bin/python3` (3.9), standard library only; [the CI workflow](.github/workflows/ci.yml) defines the tests and lint every change must pass.
- No reference copy of any Go-To-Market Package lives in this repository: configuration, the Product registry ([`config/products.json`](config/products.json)), and Instructions point to Mandu instead of restating package content.
  A record (Draft, proposal, Evidence, memo) may quote only the specific package text it uses or proposes, citing its Mandu source.
  The specification and decision records under `docs/` (including `docs/prd/design-decisions-2026-10-08.md`) and `CONTEXT.md` are committed as written.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
