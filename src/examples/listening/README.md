# Listening example set

The Listening workflow's example set (US-ME13, F3, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/snapshot.json` is a synthetic snapshot in the format the launcher writes after reading its sources: invented threads, one invented review, and two subreddits' rules.
  A real snapshot is working data that the launcher removes when its run ends; this one is a fixture.
  No text in it was fetched from anywhere.
  One of its posts holds planted instructions, to show that fetched text stays data.
- `files/quotes/` holds candidate quote records, `files/angles/` proposed Angles and Hooks, and `files/replies/` reply Drafts.
- The Angle bank, brand rules, and code the candidates are checked against are the synthetic kit of [`post-drafts`](../post-drafts/README.md).
- The deterministic assertions of each example with a candidate run in the unit tests (`src/tests/test_example_sets.py`).
- `files/pages.json` is what the snapshot's sources answer, in their own formats, made from `files/snapshot.json`: a lab's run reads it through the launcher's own client, never the network, and fetches the same documents.
  `files/labs/rules-confirmed/` and `files/labs/rules-rejected/` hold the Founder's decision on r/fitness30plus's rules notice; `files/labs/app-store-page/` names the competitor's App Store page in the research, so its reviews are read.
- An example that carries `run` is re-run by the agent on every change to this workflow's Instructions (ADR 0003): the launcher runs the workflow's session in a throwaway lab built from the set's `lab` and the example's own settings, once with the Instructions in force and once with the change, and reads its deterministic assertions off what it took in; a change that makes any of them fail where it held before is not kept.
  `src/tests/test_example_runs.py` holds that each can hold: with a stand-in agent that writes a good output, every deterministic assertion does.
- A judged assertion is judged by nothing; the notice of an Instructions change lists it for the Founder.
