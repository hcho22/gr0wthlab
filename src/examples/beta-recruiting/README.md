# Beta Cohort recruiting example set

The Beta Cohort recruiting workflow's example set (US-ME15, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/mandu/` is a synthetic thesis, K8 rubric, channel plan, and brand guidelines in the place a real Go-To-Market Package keeps them, so the examples copy no Product's strategy; the brand rules are the post-Draft example set's synthetic `brand-rules.json`.
- `files/drafts/` holds each Draft example's candidate invitation or Waitlist ask.
- `files/waitlist-view.json` is the seeded anonymous view of US-ME06: twelve synthetic sign-ups, with no address.
- `files/scenarios/` holds each workflow example's synthetic Beta Build record, Founder reports, and batches already queued.
- The deterministic assertions run in the unit tests (`src/tests/test_beta_examples.py`); the judged ones wait for US-ME16, which re-runs every example on each Instructions change and keeps no change that makes an example worse.
