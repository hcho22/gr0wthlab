# Post-Draft example set

The post-Draft workflow's example set (US-ME08, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/mandu/` is a synthetic kit in the formats of a real Go-To-Market Package, so the examples copy no Product's strategy; `files/code/` stands in for a Product's code, committed to a throwaway git repository when the examples run.
- `files/drafts/` holds each example's candidate Draft.
- The deterministic assertions run in the unit tests (`src/tests/test_examples.py`); the judged ones wait for US-ME16, which re-runs every example on each Instructions change and keeps no change that makes an example worse.
