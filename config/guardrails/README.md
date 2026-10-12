# Guardrail configuration

Configuration that enforces Guardrails G1 to G8 through the tools the Marketing Engineer works through, starting with the runtime's write boundary in US-ME02.
It changes only through firstmate's reviewed pull requests, and the Marketing Engineer cannot change it.
The PRD's Guardrails section lists each Guardrail and what enforces it.

- [`runtime.json`](runtime.json): the runtime and its write boundary (G1, G2, G8): the six writable areas, read grants, network, and the Codex settings the launcher pins, among them the model and the reasoning effort the agent runs at (`codex.reasoning_effort`, with its why beside it).
  Re-run `src/bin/gr0wthlab boundary-check` after any change to it.
