# Instructions

The Marketing Engineer's own working guidance, one file for each workflow, as it is in force.
Every session reads its workflow's file here, and the sandbox can read this folder and never write it.
Instructions are not Guardrails and cannot loosen one; strategy belongs in Mandu, so no file here restates package content, and a strategy-related rejection becomes a package-change proposal instead.

- [`package-review.md`](package-review.md): finding contradictions inside a Go-To-Market Package and writing each as one package-change proposal (US-ME04).
- [`post-drafts.md`](post-drafts.md): turning one calendar day of the 14-day kit into a post Draft: beats, captions, claims, and voice (US-ME08).
- [`filming.md`](filming.md): turning the Founder's raw footage into an edit record: choosing source ranges from measured facts alone, and keeping pair legs on the same footage (US-ME09).
- [`beta-recruiting.md`](beta-recruiting.md): writing the Beta Cohort invitation and the Waitlist ask once the Founder's gate is recorded: identity framing, the recorded first session, and no scarcity (US-ME15).
- [`listening.md`](listening.md): turning what the launcher fetched into quote records, and when a new Angle, a new Hook, or a reply is worth proposing (US-ME13).
- [`outreach.md`](outreach.md): writing the personal-network ask, the messages to creators, and the one follow-up (US-ME14).

A file here changes in two ways only ([ADR 0003](../../docs/adr/0003-instructions-change-only-through-their-example-set.md)):

- The launcher writes a change the agent proposed in `workspace/instructions/` from execution-related rejection reasons, once that workflow's example set in `src/examples/` passed it: no example worse than with the text in force.
  Every such change is recorded in `ledger/evidence/instructions/` and shown to the Founder as a notice at the next sitting.
- A reviewed pull request, like any other change to this repository.

Each workflow's example set lives in `src/examples/`, out of the agent's reach: [`package-review`](../../src/examples/package-review/README.md), [`post-drafts`](../../src/examples/post-drafts/README.md), [`filming`](../../src/examples/filming/README.md), [`beta-recruiting`](../../src/examples/beta-recruiting/README.md), [`listening`](../../src/examples/listening/README.md), and [`outreach`](../../src/examples/outreach/README.md).
