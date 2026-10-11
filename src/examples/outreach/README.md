# Outreach example set

The outreach workflow's example set (US-ME14, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/drafts/` holds each example's candidate Draft: the personal-network ask, a message to a creator, or a follow-up.
- `files/records/` holds the Founder's record of what was sent and answered, as Mandu would hold it, with the day the run happens; a follow-up is offered or not from it.
- The channel plan, Angle bank, brand rules, and code are the synthetic kit of [`post-drafts`](../post-drafts/README.md), whose channel plan names three invented creators; the one creator feed is in the [Listening set's](../listening/README.md) snapshot.
- The personal-network Source link is the one the reviewed Waitlist Dispatch request in `src/dispatches/` defines.
- The deterministic assertions run in the unit tests (`src/tests/test_example_sets.py`); the judged ones wait for US-ME16.
