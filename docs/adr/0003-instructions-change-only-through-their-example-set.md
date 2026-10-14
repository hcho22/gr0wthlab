# The Marketing Engineer's Instructions change only through their example set

The Marketing Engineer's Instructions are its own working guidance for each workflow: how to write a post Draft, an edit record, a quote record, a message.
US-ME16 lets them improve from the Founder's rejection reasons, and FR-14 says how: every change re-runs that workflow's example set, a change that makes any example worse is not kept, and every kept change is shown to the Founder at the next sitting.
This record says where a change comes from, who applies it and when, how an example is judged, what it costs, and what the Founder sees.

Decided on 2026-10-14.
The three choices that change what the Founder sees or what a week costs were put to the Founder, who answered "gr0wthlab - A, A, A" ([The Founder's three choices](#the-founders-three-choices)).

## The rule

The agent proposes; the launcher applies, outside the sandbox, only what the workflow's example set passed.
Nothing the agent writes is ever its Instructions until then, and nothing it can write reaches its Instructions or the example sets at all.

## Where everything lives

| What | Where | Who writes it |
| --- | --- | --- |
| The Instructions in force | `ledger/instructions/<workflow>.md` | The launcher, only for a change its example set passed; and firstmate's reviewed pull requests |
| A proposed change | `workspace/instructions/<workflow>.md` | The agent, in the session that codes the rejection reasons |
| The example sets | `src/examples/<workflow>/evals.json`, with their synthetic files | Only firstmate's reviewed pull requests (G8) |
| What each change was, and how its examples did | `ledger/evidence/instructions/<change id>.json`, with the text before and the text proposed beside it | The launcher |

Until this decision the Instructions were in `workspace/instructions/`, one of the six areas the agent can write, and the launcher put back any change a session made there.
They move to `ledger/`, which the sandbox reads and never writes, so the boundary itself keeps them, not a put-back after the fact.
`workspace/instructions/` stays the agent's Instructions area, as Guardrail G1 names it, and now holds only what the agent proposes.

`ledger/instructions/` and `src/examples/` are each a forbidden target of the preflight before every session and of the boundary check, in the form the five folders of the Founder's records have: the preflight tries to create a file in each from inside the sandbox and starts the agent only when both tries were refused, and the boundary check proves each refused on its own, once per tool, from the runtime's records.
`src/examples/` was already out of the agent's reach as part of `src/`; it is named on its own so a profile that ever opened it would fail the check by name.

The launcher still notes the Instructions in force and the outbox before the first session and puts both back after every session, so no session reads what another wrote there.
The one exception is a proposed change the rejection reasons' session leaves in the outbox, which the launcher takes in once the last session has ended.

## Where a change comes from

Only the session that codes the rejection reasons may propose one.
That session reads no fetched text: its brief holds the Founder's reasons and nothing a third party wrote, so no thread or review can steer a change.

Its brief lists each rejection reason that may lead to an Instructions change: one that has, or is given in this session, an execution code, of an item whose workflow has Instructions and an example set, that no change has answered yet.
For those, the agent may write one proposed new text of that workflow's Instructions:

```markdown
---
workflow: post-drafts
reasons: 20261011-post-w1-day-03
summary: Keep each caption line under twelve words, since the Founder rejected a caption as too long.
---

<the whole of ledger/instructions/post-drafts.md as it should read>
```

Once the last session has ended, and after it has taken in the codes, the launcher checks the proposal, and refuses it with its reasons unless every one of these holds:

- Its name and its `workflow:` name one workflow with Instructions in force and an example set.
- Every reason it cites is a kept rejection reason of that workflow's items, coded as execution, that no change has answered.
  A strategy reason can never be cited: it becomes a package-change proposal, as it did before.
- Its summary is one line of at most 300 characters.
- Its text differs from the text in force, is at most 32,000 characters, keeps every comment line of the text in force as it is (the third-party attributions are kept that way), holds nothing that looks like an email address, and adds no line of 24 characters or more that a Go-To-Market Package file holds, so no package content enters gr0wthlab through it (ADR 0001).

A reason is offered for a change once.
One the agent codes as execution and leaves without a change, in a session that finished, is answered by no change, and is not offered again.

## Who applies it, and when

The launcher, in the same weekly run, after it has taken in everything the sessions wrote and before it writes the run report, so the notice reaches the sitting that follows.

1. It runs the workflow's example set twice, on the same day and the same model: once with the Instructions in force, once with the proposed text.
2. It compares the two, example by example.
3. It keeps the change only if no example is worse and every example was compared: it writes the proposed text to `ledger/instructions/<workflow>.md` and queues the notice.
4. Otherwise the Instructions stay byte for byte as they were, and the run report says which example got worse, and how, or why it could not be compared.

Either way the record in `ledger/evidence/instructions/` keeps the reasons, the text before, the text proposed, every example's result on each side, and how many sessions and how much agent time and cost the gate took.
The records step commits it with the run's other records, so `git log` shows every change and restoring a file from history undoes one.

## How an example is run

An example is an input the agent works from and the output expected of it, in the marketingskills `evals.json` shape.
Each workflow has about ten, built on synthetic fixtures, never a Product's package, and holding no stranger's words.
An example that carries `run` is re-run by the agent; one without it holds a fixed candidate output and tests the launcher's own checks in the unit tests, as every example did before this decision.

Each re-run is the workflow's own session, run the way a weekly run runs it:

- The launcher builds a throwaway lab under `ledger/working/examples/`, which git ignores and the run removes when it ends: a copy of the repository's code, configuration, and task definitions, the lab's own `ledger/` and `workspace/` holding the example's starting state, the Instructions under test in its `ledger/instructions/`, and a synthetic Mandu, Product checkout, and, for filming, footage made with ffmpeg's test pattern, each beside it.
- It runs one weekly run in the lab with only that workflow's session, through the same launcher code: the same Codex command, permission profile, closed network, preflight, task definition, and brief.
  The lab's own run reads no network: what an example's sources answer comes from its fixtures, through the launcher's client with a transport that reads them, never through `fetch.send`.
- The lab's run takes the session's work in with the same checks a weekly run uses, and the example's assertions are read off what it took in: a Draft that passed every check, one blocked by a named rule, a quote kept or refused, a proposal queued, and so on.

A lab never writes the real `ledger/`: the launcher copies an example's synthetic records, the Founder's among them, into the lab's own `ledger/`, which is the lab's alone.

## How an example is judged better or worse

Deterministic assertions first.
One is worse when it held with the Instructions in force and fails with the change, and holds again when the example is run again with the Instructions in force.
The agent's output varies from one session to the next, so an assertion that also fails without the change is not taken as the change's doing: where one did worse, the launcher runs the example again with the Instructions in force, and the assertion is worse unless it fails there too.
Two live findings of 2026-10-14 set this rule ([their record](../live-checks/20261014-gr0wthlab-learning-loop.md)).
The first gate lost a one-line change on one assertion of one example while nine did no worse, and the assertion it lost on also failed with the Instructions in force in a later gate.
Then a change written to do harm, which told the agent to stop looking for code behind a claim, was followed in one session of two: one Draft was blocked, its repeat with the change passed, and the Instructions in force held both times.
A rule that asked the change to fail twice lets each such failure through about three times in four; one failure against an assertion that held again without the change is enough.
An example whose session did not run to its end on either side, was not started, or whose lab could not be built, cannot be compared, so the change is not kept.
A change is never kept on the strength of an example getting better; it is kept when none got worse.

Judged statements, such as "the captions read as calm and plain, with no hype", say what no check can decide, and nothing judges them.
They stay in the example sets, and the notice lists each one plainly as not judged by anything, so the Founder knows what the gate did not look at.
No model ever judges an example.

## What it costs

One example is one agent session, at the reasoning effort every session has.
The whole sessions measured on 2026-10-12 took 42 to 217 seconds at about $0.02 each, so one example is estimated at 1 to 2 minutes and $0.01 to $0.03 at API prices, and one change, with both sides and about ten examples, at about 20 sessions, before any judging.
The live validation of this change measures one and records it.

A weekly run tries at most one change.
When reasons of several workflows wait, the workflow of the oldest waiting reason goes first, and the others wait for a later run.
The gate's sessions have a bound of their own, 60 minutes of agent time, beside the bound on the run's sessions (`learning` in `config/run.json`).
The gate stops as soon as an example is worse, since the change can then no longer be kept, and runs no more examples.
A change the bound cuts short, or whose examples could not be run, is not kept, and the reasons it cites are offered again at the next run.

## What the Founder sees

A kept change becomes one notice in the Review Queue, decided at the next sitting like any item.
It holds the Founder's own words of each reason that prompted the change, the code the agent gave each and its line on why, the agent's one-line summary, the change itself line by line, and every example's result with the Instructions in force and with the change.
A change that was not kept puts nothing in front of the Founder but the run report, whose summary names it and whose Instructions section says what was tried, from which reasons, and which example got worse and how.

The Founder acknowledges the notice, which keeps the change, or rejects it with a one-line reason, which undoes it.
The next run takes the rejection in, puts that workflow's Instructions back to the text they had before the change, says so in the run report, and keeps the reason as Evidence and codes it like any other rejection.
While a kept change's notice is undecided, no further change to that workflow's Instructions is tried, so an undo never has to unpick a later change.

## The Founder's three choices

Put to the Founder on 2026-10-14, each with a recommendation; the Founder answered "gr0wthlab - A, A, A".

1. **Judged statements: A, checks only.**
   Only deterministic assertions decide, and the judged statements are listed as not judged.
   Not chosen: B, a model that reads both outputs without knowing which Instructions wrote which and can only stop a change, at about one more session per example.
2. **What a week may spend: a, at most one change per run, inside the weekly run, with a gate bound of its own of 60 minutes.**
   Not chosen: b, one change per workflow per run with a bound of 120 minutes; c, the gate as its own command outside the weekly run, which would bring a kept change to the Founder a week later.
3. **The notice: A, rejecting it undoes the change at the next run, and no further change to that workflow is tried while its notice is undecided.**
   Not chosen: B, a notice for information only, with an undo as a reviewed pull request.

## Considered options

- **The agent edits `workspace/instructions/` and the launcher keeps or puts back the edit.**
  Rejected: the agent could change its Instructions mid-run for every later session, and only a put-back after the fact would stand between a fetched post and its guidance.
- **Keep the example sets in `workspace/instructions/`, beside the Instructions, as the comparison suggested.**
  Rejected: the agent could weaken an example to pass it.
  They stay in `src/examples/`, and the boundary check names them.
- **Re-run each example's fixed candidate through the checks.**
  Rejected: a candidate written by hand does not change with the Instructions, so the re-run would pass every change and test nothing.
- **Write a brief for each example by hand and run only the session.**
  Rejected: a hand-written brief drifts from the one a weekly run writes, and the examples would test a session no weekly run starts.
- **Take one run's flip as worse.**
  Rejected after the first live gate: the agent's output varies from session to session, so a set of about thirty assertions will often see one flip under a change that made nothing worse.
- **Run the example again on both sides, and count it worse only when the same assertion does worse again.**
  Tried live and rejected: where the agent follows a change in one session of two, each failure it causes passes this rule about three times in four, as the change written to do harm passed it on the first example it failed.
- **Run every example several times on each side and compare how often each assertion holds.**
  Not chosen: it multiplies every change's sessions, where running again only the Instructions in force adds one session each time an assertion does worse.
- **Reuse a baseline measured in an earlier run while nothing it depends on changed.**
  Not chosen: it halves the sessions, but the two sides would then meet the model on different days, and a difference could be the model's and not the change's.
