# src

The Marketing Engineer's code.
It changes only through firstmate's reviewed pull requests (Guardrail G8) and is outside the agent's writable tree.
US-ME02 chose Codex as the runtime and Python 3.9 or newer, standard library only, as the language; the launcher runs under the Mac's `/usr/bin/python3`.
Why, and the boundary the launcher enforces: [the US-ME02 spike note](../docs/spikes/us-me02-runtime-boundary.md).

- [`bin/gr0wthlab`](bin/gr0wthlab): the launcher, the one entry point for scheduled and on-demand runs (`run`, `show-config`, `preflight`, `launch-agent`, `boundary-check`).
- [`gr0wthlab/`](gr0wthlab/): the launcher's package.
- [`checks/`](checks/): instructions for live checks, such as the US-ME02 boundary probe.
- [`tests/`](tests/): unit tests, run with `/usr/bin/python3 -m unittest discover -s src/tests -t src`.
