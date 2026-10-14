# Weekly Read example set

The Weekly Read workflow's example set (US-ME12, F9): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/results/` holds two synthetic sets of the Founder's numbers, as the sitting page records them: one for a day-7 read and one for a day-14 read.
  Every number is invented, and no post, channel, or comment in them is real.
- `files/memos/` holds candidate memos: one that passes for each read, and one for each rule the launcher holds a memo to, broken.
- The calendar, Angle bank, and pairs the memos are checked against are the synthetic kit of [`post-drafts`](../post-drafts/README.md), with its synthetic `read-the-results.md`.
- The deterministic assertions run in the unit tests (`src/tests/test_weekly_read_examples.py`); the judged ones wait for US-ME16.
