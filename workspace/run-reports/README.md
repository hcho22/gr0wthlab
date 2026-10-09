# Run reports

One report per run: every source checked with its result, every failure and skip with its reason, whether a scheduled run started late, and the run's approximate cost (US-ME17).

- `<run id>.md`: the run report, written by the launcher after the agent finishes.
- `<run id>.brief.md`: the facts the launcher gave the agent before it started.
- `state/<workflow>.json`: each workflow's run state - Review Queue items decided, and those carried over with the sitting they were left undecided at, Listening threads already read, outreach targets and their follow-up waits - by identifier and hash only, never a name, address, or URL.
  The launcher checks it every run against the Review Queue and Mandu's decision records, which win any disagreement, and every report's first line counts what the run checked and acted on (`checked=N acted=N note=...`).

The launcher alone writes here.
