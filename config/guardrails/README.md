# Guardrail configuration

Configuration that enforces Guardrails G1 to G8 through the tools the Marketing Engineer works through, starting with the runtime's write boundary in US-ME02.
It changes only through firstmate's reviewed pull requests, and the Marketing Engineer cannot change it.
The PRD's Guardrails section lists each Guardrail and what enforces it.

- [`runtime.json`](runtime.json): the runtime and its write boundary (G1, G2, G8): the six writable areas, read grants, network, and the Codex settings the launcher pins.
  The sandboxed agent's network is off, and stays off.
  Re-run `src/bin/gr0wthlab boundary-check` after any change to it.
- [`fetch.json`](fetch.json): the launcher's own outbound reads (G5, G8), made outside the sandbox before the agent starts: the hosts it may read, the User-Agent it sends, and its limits.
  Every request is a credential-free GET over HTTPS to a listed host, each host's `robots.txt` is binding, and nothing here can add a credential, a method, or an exception.
  The client is [`src/gr0wthlab/fetch.py`](../../src/gr0wthlab/fetch.py); every run's preflight proves the sandbox reaches none of these hosts, and the boundary check proves both sides.
  Re-run `src/bin/gr0wthlab boundary-check` after any change to it.
