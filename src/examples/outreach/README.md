# Outreach example set

The outreach workflow's example set (US-ME14, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/drafts/` holds each example's candidate Draft: the personal-network ask, a message to a creator, or a follow-up.
- `files/records/` holds the Founder's record of what was sent and answered, as the sitting page would write it in `ledger/founder/outreach/`, with the day the run happens; a follow-up is offered or not from it.
- The channel plan, Angle bank, brand rules, and code are the synthetic kit of [`post-drafts`](../post-drafts/README.md), whose channel plan names three invented creators.
- The personal-network Source link is the one the reviewed Waitlist Dispatch request in `src/dispatches/` defines.
- The deterministic assertions of each example with a candidate run in the unit tests (`src/tests/test_example_sets.py`).
- `files/labs/<name>/ledger/` holds a lab's Review Queue and the Founder's records for a creator's first message: sent with no reply, sent with a longer wait the Founder set, or rejected with a reason.
- An example that carries `run` is re-run by the agent on every change to this workflow's Instructions (ADR 0003): the launcher runs the workflow's session in a throwaway lab built from the set's `lab` and the example's own settings, once with the Instructions in force and once with the change, and reads its deterministic assertions off what it took in; a change that makes any of them fail where it held before is not kept.
  `src/tests/test_example_runs.py` holds that each can hold: with a stand-in agent that writes a good output, every deterministic assertion does.
- A judged assertion is judged by nothing; the notice of an Instructions change lists it for the Founder.
  How long a message runs, and whether an ask closes on a line a friend can forward, are judged assertions: the launcher blocks no Draft on either.
