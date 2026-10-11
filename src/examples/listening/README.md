# Listening example set

The Listening workflow's example set (US-ME13, F3, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/snapshot.json` is a synthetic snapshot in the format the launcher writes after reading its sources: invented threads, one invented review, two subreddits' rules, and one creator's feed.
  No text in it was fetched from anywhere.
  One of its posts holds planted instructions, to show that fetched text stays data.
- `files/quotes/` holds candidate quote records, `files/angles/` proposed Angles and Hooks, and `files/replies/` reply Drafts.
- The Angle bank, brand rules, and code the candidates are checked against are the synthetic kit of [`post-drafts`](../post-drafts/README.md).
- The deterministic assertions run in the unit tests (`src/tests/test_example_sets.py`); the judged ones wait for US-ME16.
