# Package review example set

The package review's example set (US-ME04, US-ME16, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/mandu/` is a small synthetic Go-To-Market Package in the formats of a real one, whose files all agree, so the examples copy no Product's strategy.
- `files/labs/<name>/mandu/` holds each example's overlay: one file changed so that the package holds one stale fact, two facts that should agree and do not, or a plan that breaks a rule; one overlay keeps an earlier version marked as history, and one bans a word a frozen Hook holds while exempting frozen Hooks from the banned words, and neither is a contradiction.
- Every example carries `run`: on each change to the package-review Instructions, the agent reviews the whole package with the example's overlay in a throwaway lab, and the launcher reads its assertions off the proposals it queued (ADR 0003).
  `src/tests/test_example_runs.py` holds that each can: with a stand-in agent that writes a good output, every deterministic assertion holds.
- A judged assertion is judged by nothing; the notice of an Instructions change lists it for the Founder.
