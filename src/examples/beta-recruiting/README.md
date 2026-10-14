# Beta Cohort recruiting example set

The Beta Cohort recruiting workflow's example set (US-ME15, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/mandu/` is a synthetic thesis, K8 rubric, channel plan, and brand guidelines in the place a real Go-To-Market Package keeps them, so the examples copy no Product's strategy; the brand rules are the post-Draft example set's synthetic `brand-rules.json`.
- `files/drafts/` holds each Draft example's candidate invitation or Waitlist ask.
- `files/waitlist-view.json` is the seeded anonymous view of US-ME06: twelve synthetic sign-ups, with no address.
- `files/scenarios/` holds each workflow example's synthetic Beta Build record, Founder reports, and batches already queued.
- The deterministic assertions of each example with a candidate or a scenario run in the unit tests (`src/tests/test_beta_examples.py`).
- `files/labs/approved/ledger/` holds the Founder's synthetic Beta Build record for a lab; `files/waitlist-view-full.json` is a second synthetic view, of 24 opted-in sign-ups, enough to fill the cohort; the other `files/labs/` folders change one package file for one example.
- An example that carries `run` is re-run by the agent on every change to this workflow's Instructions (ADR 0003): the launcher runs the workflow's session in a throwaway lab built from the set's `lab` and the example's own settings, once with the Instructions in force and once with the change, and reads its deterministic assertions off what it took in; a change that makes any of them fail where it held before is not kept.
  `src/tests/test_example_runs.py` holds that each can hold: with a stand-in agent that writes a good output, every deterministic assertion does.
- A judged assertion is judged by nothing; the notice of an Instructions change lists it for the Founder.
