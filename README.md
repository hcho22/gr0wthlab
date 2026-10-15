# gr0wthlab

gr0wthlab is the repository of the Marketing Engineer: a standalone agent that runs once a week on the Founder's Mac.
It turns each Product's Go-To-Market Package, kept in Mandu, into the week's Drafts, gathers Evidence, reads results against pre-registered rules, and puts everything that needs a decision into one Review Queue the Founder clears in about an hour, on a small page this repository serves on the Founder's Mac.
It never publishes, sends, or spends, and never changes the Go-To-Market Package, Mandu, or any Product repository; it proposes, and each owner applies what the Founder approves.
v1 serves RepToday's pre-launch phase; Immerse joins as Listening only after RepToday's first 14-day window has run cleanly.

Capitalized terms are defined in [`CONTEXT.md`](CONTEXT.md).
Why this repository holds Evidence and Drafts but no strategy: [ADR 0001](docs/adr/0001-evidence-and-drafts-only.md).
Why the Founder decides here, on a local page, and Mandu only reads: [ADR 0002](docs/adr/0002-the-founder-decides-in-gr0wthlab.md).
Why the Founder posts by hand, with no scheduling service: [ADR 0004](docs/adr/0004-posting-is-manual.md).
Why the Weekly Read reads no platform, and the Founder gives TikTok Studio's and YouTube Studio's numbers on the sitting page: [ADR 0005](docs/adr/0005-the-weekly-read-uses-no-youtube-connection.md).
Why he types those numbers, and the page keeps no screenshot or file: [ADR 0006](docs/adr/0006-the-founder-types-the-weekly-read-numbers.md).
Stories, requirements, and progress: [the v1 PRD](docs/prd/prd-marketing-engineer-v1_261008.md).

## No strategy lives here

Each Product's Go-To-Market Package (positioning, Fit, claims, brand rules, Angles) lives only in Mandu, for RepToday at `~/Mandu/projects/RepToday/gtm/`; the [Product registry](config/products.json) records where each package is.
No reference copy of any Go-To-Market Package lives in this repository: configuration, the Product registry, and Instructions point to Mandu instead of restating package content.
A record (a Draft, proposal, Evidence, or memo) may quote only the specific package text it uses or proposes, citing its Mandu source.
The specification and decision records under `docs/` (the PRD, the [design decisions](docs/prd/design-decisions-2026-10-08.md) it cites, and the ADRs) and the glossary in `CONTEXT.md` are committed as written, even where they name a Product's Fit or a claim as an example.

## Who does what

| Actor | Owns | Never does |
| --- | --- | --- |
| Founder | Every approval and every public act (posting, sending, confirming a publishing schedule), filming, and, in a read week, the TikTok Studio and YouTube Studio numbers of each post | - |
| Marketing Engineer | Evidence, Drafts, Review Queue items, Weekly Read memos, run reports, and its own Instructions; its repository also serves the Founder's sitting page and keeps the Founder's decisions | Publish, send, spend, see email addresses, write to Mandu or a Product repository, write or change a decision of the Founder's, or change its own code or Guardrails |
| Mandu | Each Product's Go-To-Market Package, applying approved package changes and giving the Founder a ready-to-send message for each approved Dispatch request when the Founder asks, and showing the Founder the Marketing Engineer's status | Build the Marketing Engineer, record a decision of the Founder's, or write anything the Marketing Engineer reads but the Go-To-Market Package |
| firstmate | Building and changing the Marketing Engineer's code and Guardrails through reviewed pull requests, and carrying out approved Dispatches | Act on a Dispatch the Founder has not approved |
| Scheduling service | Not used: the Founder posts each approved post by hand, his choice of 2026-10-11 ([ADR 0004](docs/adr/0004-posting-is-manual.md)) | - |

## The weekly cycle

1. **Run.** The Marketing Engineer reads the Go-To-Market Package, the Founder's decisions, and its sources; performs Listening; on read weeks lists exactly which numbers to give for which posts and writes the Weekly Read memo from the numbers given; prepares next week's Drafts, proposals, and Dispatch requests; and writes a run report.
2. **Sitting.** The Founder runs `src/bin/gr0wthlab sitting`, which serves a small page on the Founder's Mac.
   On read weeks the Founder first gives each post's numbers on that page, read from TikTok Studio or YouTube Studio, then starts a run so the Weekly Read takes them in.
   The Founder then approves each Review Queue item or rejects it with a one-line reason, one item at a time; what the Founder clicks is what is saved.
3. **Publish.** The Founder posts each approved post by hand at the fixed slot, and sends approved messages.
4. **Learn.** The next run reads the decisions, keeps every rejection reason as Evidence, refines Instructions for execution reasons only through each workflow's example set, and proposes package changes for strategy reasons; every kept Instructions change is a notice at the next sitting.

## Guardrails

Each Guardrail is enforced by the tools the Marketing Engineer works through, not by its Instructions, and the Marketing Engineer cannot change any of them.
The PRD's Guardrails section says what enforces each one.

| ID | Guardrail |
| --- | --- |
| G1 | Writes are possible only in the Evidence, Drafts, Review Queue, Weekly Read, run report, and Instructions areas |
| G2 | No writes to Mandu or any Product repository |
| G3 | The scheduling service can receive drafts only (no scheduling service is connected: [ADR 0004](docs/adr/0004-posting-is-manual.md)) |
| G4 | YouTube access is read-only (gr0wthlab has no YouTube access at all: [ADR 0005](docs/adr/0005-the-weekly-read-uses-no-youtube-connection.md)) |
| G5 | No TikTok, Instagram, X, Reddit, or email sending credentials exist |
| G6 | No email address is ever readable |
| G7 | No spend is possible |
| G8 | Code and Guardrail configuration change only through firstmate's reviewed pull requests |

## Layout

| Path | Holds | Agent may write |
| --- | --- | --- |
| [`workspace/evidence/`](workspace/evidence/) | Evidence | Yes |
| [`workspace/drafts/`](workspace/drafts/) | Drafts | Yes |
| [`workspace/review-queue/`](workspace/review-queue/) | Review Queue items the agent proposes, before the launcher checks them | Yes |
| [`workspace/weekly-reads/`](workspace/weekly-reads/) | Weekly Read memos | Yes |
| [`workspace/run-reports/`](workspace/run-reports/) | Notes the agent writes during a run | Yes |
| [`workspace/instructions/`](workspace/instructions/) | A change to the Instructions the agent proposes, before the launcher re-runs its example set | Yes |
| [`ledger/`](ledger/) | The launcher's records: the published Review Queue, the launcher's own Evidence, run reports, and run state; and, outside git, the finished videos it renders | No |
| [`ledger/instructions/`](ledger/instructions/) | The Marketing Engineer's Instructions in force, changed only by a change its workflow's example set passed, or by a reviewed pull request ([ADR 0003](docs/adr/0003-instructions-change-only-through-their-example-set.md)) | No |
| [`ledger/founder/`](ledger/founder/) | The Founder's own records: each decision, each sitting, the Beta Build record, the Beta Cohort counts, what was sent, and the numbers of each post for a Weekly Read; only the sitting page writes them | No |
| [`src/`](src/) | Code | No |
| [`config/`](config/) | Guardrail configuration, the Product registry, the run's settings, platform facts, and the network sources | No |
| `docs/`, `CONTEXT.md`, this README | Specification and decision records | No |

`workspace/` is the only tree the agent may write (G1); `ledger/` is written only by the launcher, outside the sandbox, but for `ledger/founder/`, which only the Founder's act on the sitting page writes; and everything else changes only through firstmate's reviewed pull requests (G8).

## Runs

Every run, scheduled or on demand, starts through `src/bin/gr0wthlab run`, which runs Codex inside the write boundary in [`config/guardrails/runtime.json`](config/guardrails/runtime.json): one session for each workflow that has work due, one after another, each with its task definition from [`src/instructions/weekly-run/`](src/instructions/weekly-run/) ([operations](docs/operations.md#one-session-per-workflow)).
No session has a network: before the first starts, the launcher itself reads the fixed list of sources in [`config/sources.json`](config/sources.json), with credential-free reads of the hosts in [`config/guardrails/fetch.json`](config/guardrails/fetch.json) and only where each host's `robots.txt` allows, and hands the agent a snapshot it can read and never write.
Each week's run falls due on Sunday afternoon, ahead of the Founder's Sunday evening sitting, and happens when the Mac is awake, Sunday night or Monday morning alike, since nothing holds the Mac awake for it; [`config/run.json`](config/run.json) holds the schedule and the step that saves each run's `workspace/` and `ledger/` records to `main`.
Setting up the production clone and the schedule, and removing them: [operations](docs/operations.md).
The Founder's sitting: `src/bin/gr0wthlab sitting`, which serves the Review Queue one item at a time on the loopback address and writes each decision the Founder clicks into `ledger/founder/` ([operations](docs/operations.md#the-weekly-sitting)).
The format of every record, and what Mandu may read: [the Mandu exchange](docs/mandu-exchange.md).
Where the Founder drops raw footage and how to name it, and where finished videos are: [operations](docs/operations.md).
Why Codex, how the boundary is enforced, and the refused-write evidence: [the US-ME02 spike note](docs/spikes/us-me02-runtime-boundary.md).
Text adapted from other projects, and its licenses: [third-party notices](THIRD_PARTY_NOTICES.md).
