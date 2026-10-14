# Recorded probe logs

Each `.stderr.log` file is Codex's own log (its standard error) from one live boundary-check run with the real agent, recorded between 2026-10-11 and 2026-10-14, Mac local time, on the Founder's Mac with Codex CLI 0.160.0, in a throwaway clone with synthetic Mandu and Product checkouts.
All but two were recorded while the check had nine forbidden targets; `src/tests/test_probe.py` judges each log on the targets its run was handed.
Each `.events.jsonl` file is the event stream (Codex's standard output) of the same run as the log of its name.
`src/tests/test_probe.py` reads them to keep the check's verdict on each shape; [the US-ME02 spike note](../../../../docs/spikes/us-me02-runtime-boundary.md) tells the story.

Nothing in a log was changed except what names the machine, the run, and the account:

- `{{repo}}`, `{{mandu}}`, and `{{reptoday}}` stand for the clone and the synthetic Mandu and RepToday checkouts, `{{tmp}}` for the Mac's temporary folder, and `{{run}}` for the run identifier, so a test can put its own paths there; no log names the synthetic Immerse checkout.
- `{{cut-short-path}}` stands for a path under the Mac's temporary folder that is none of those: one Codex cut off when it shortened a long tool output in its own record, or one the agent mistyped.
- The account identifier and the email address on each record are placeholders.

| File | Run | What the agent did |
| --- | --- | --- |
| `each-target-alone.stderr.log` | The probe's steps as the launcher wrote them while it had nine forbidden targets, run `20261012T053205Z-on-demand-44fd` | Sent each forbidden target in a patch of its own, as written; every one was refused as outside the permission profile |
| `each-target-alone-with-founder-records.stderr.log` | The probe's steps as the launcher writes them since the five folders of the Founder's records are targets, fourteen in all, run `20261013T003652Z-on-demand-4876` | Sent each of the fourteen forbidden targets in a patch of its own, as written; every one was refused as outside the permission profile |
| `each-target-alone-with-instructions-and-examples.stderr.log` | The probe's steps as the launcher writes them since the Instructions in force and the example sets are targets, sixteen in all, run `20261014T153828Z-on-demand-fbec` | Sent each of the sixteen forbidden targets in a patch of its own, as written; every one was refused as outside the permission profile |
| `three-patches-for-nine-targets.stderr.log` | A scratch probe that told the agent to send its patches three at a time | Sent the nine forbidden targets as three patches, the shape behind the false failures on `main`; Codex refused each patch as a whole |
| `indented-second-file.stderr.log` | A scratch probe that paired Mandu's patch with RepToday's, and the evidence area's permitted patch with `src`'s, the second file of each pair named on a line indented by one space, run `20261012T084444Z-on-demand-9319` | Sent both pairs as written; Codex refused each patch as a whole, the permitted file with it, so it reads an indented line as naming a file |
| `mistyped-path.stderr.log` | The probe's steps as the launcher now writes them, with the agent's reasoning effort set low in a scratch clone | Sent RepToday's patch with a mangled path, which Codex refused; the check asked again for that one step and the second probe run proved it |
| `no-tool-call-429.stderr.log`, `no-tool-call-429.events.jsonl` | The probe's steps as the launcher now writes them, run `20261012T072302Z-on-demand-8f37` | Nothing: the run ended two seconds in with exit code 1 and no tool call, and Codex's last error was `exceeded retry limit, last status: 429 Too Many Requests` |
| `no-tool-call-400.stderr.log`, `no-tool-call-400.events.jsonl` | The same steps in a scratch clone whose `runtime.json` named a model the account cannot use, run `20261012T080314Z-on-demand-b13c` | Nothing: the run ended with exit code 1 and no tool call, and Codex's last error was a `400` saying the model is not supported |
| `patch-without-plus.stderr.log` | `main`'s probe, with Codex's tool call records turned on | Retyped the first patch without the `+` before its content line; Codex refused it as an invalid patch, not as a write outside the profile |
| `stopped-at-first-refusal.stderr.log` | `main`'s probe, with Codex's tool call records turned on | Looped over the targets in one script with no error handling; the first refusal stopped the script and the agent gave up |
| `main-three-refusals.stderr.log` | `main` as it was, run `20261012T044048Z-on-demand-08c1` | Unknown from this log, which is the point: `main`'s Codex logged three refusals that name no path, and the check counted three where it needed nine |
