# Post-Draft example set

The post-Draft workflow's example set (US-ME08, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/mandu/` is a synthetic kit in the formats of a real Go-To-Market Package, so the examples copy no Product's strategy; `files/code/` stands in for a Product's code, committed to a throwaway git repository when the examples run.
- `files/drafts/` holds each example's candidate Draft.
- The deterministic assertions of each example with a candidate Draft run in the unit tests (`src/tests/test_examples.py`).
- `files/labs/<name>/mandu/` holds an example's overlay of the kit: a brand rule that bans a word a frozen Hook holds, and a checklist line left open.
- An example that carries `run` is re-run by the agent on every change to this workflow's Instructions (ADR 0003): the launcher runs the workflow's session in a throwaway lab built from the set's `lab` and the example's own settings, once with the Instructions in force and once with the change, and reads its deterministic assertions off what it took in; a change that makes any of them fail where it held before is not kept.
  `src/tests/test_example_runs.py` holds that each can hold: with a stand-in agent that writes a good output, every deterministic assertion does.
- A judged assertion is judged by nothing; the notice of an Instructions change lists it for the Founder.
