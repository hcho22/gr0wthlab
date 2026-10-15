# Filming example set

The filming workflow's example set (US-ME09, F5): [`evals.json`](evals.json), in the marketingskills `evals.json` shape (`{id, prompt, expected_output, assertions[], files[]}`), with each assertion marked deterministic or judged.
It lives in `src/`, out of the agent's reach, and changes only through a reviewed pull request.

- `files/mandu/` is a synthetic calendar, Angle bank, and A/B pairs file, laid over the post-Draft example set's kit, so the examples copy no Product's strategy.
  It adds what filming needs: Formats that name each recording, a founder-on-camera pair whose opening is re-cut, and the calendar's rule for every screen recording.
- `files/footage.json` stands in for the launcher's inventory of a footage place: names, shots, and measured facts of footage that was never filmed.
  No media file is in this repository.
- `files/edits/` holds each example's candidate edit record, `files/drafts/` the post Drafts whose beats they follow, and `files/assets/` the facts measured of a rendered asset.
- The deterministic assertions run in the unit tests (`src/tests/test_filming_examples.py`).
  The two that render video make their own test clips from ffmpeg's test pattern, and are skipped with that reason where ffmpeg is not installed.
- `files/labs/plan-approved/ledger/` is a lab's Review Queue with the filming plan the launcher files from this kit, approved by the Founder and taken in; `files/labs/day-<nn>-draft/` puts a day's post Draft in a lab's workspace, and `files/labs/stale-edit/` an earlier run's edit record that no longer passes.
  A re-run example's footage is made in its lab with ffmpeg's test pattern, to the facts `files/footage.json` gives each file it names; no media file is in this repository.
- An example that carries `run` is re-run by the agent on every change to this workflow's Instructions (ADR 0003): the launcher runs the workflow's session in a throwaway lab built from the set's `lab` and the example's own settings, once with the Instructions in force and once with the change, and reads its deterministic assertions off what it took in; a change that makes any of them fail where it held before is not kept.
  `src/tests/test_example_runs.py` holds that each can hold: with a stand-in agent that writes a good output, every deterministic assertion does.
- A judged assertion is judged by nothing; the notice of an Instructions change lists it for the Founder.
