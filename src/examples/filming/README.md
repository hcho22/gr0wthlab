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
  The judged ones wait for US-ME16, which re-runs every example on each Instructions change and keeps no change that makes an example worse.
