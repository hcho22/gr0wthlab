# src

The Marketing Engineer's code.
It changes only through firstmate's reviewed pull requests (Guardrail G8) and is outside the agent's writable tree.
US-ME02 chose Codex as the runtime and Python 3.9 or newer, standard library only, as the language; the launcher runs under the Mac's `/usr/bin/python3`.
Why, and the boundary the launcher enforces: [the US-ME02 spike note](../docs/spikes/us-me02-runtime-boundary.md).

- [`bin/gr0wthlab`](bin/gr0wthlab): the launcher, the one entry point for scheduled and on-demand runs (`run`, `show-config`, `preflight`, `check-incoming`, `check-drafts`, `check-beta-drafts`, `launch-agent`, `boundary-check`).
- [`gr0wthlab/`](gr0wthlab/): the launcher's package; [`cycle.py`](gr0wthlab/cycle.py) is one run from start to saved records, [`launcher.py`](gr0wthlab/launcher.py) starts the agent inside the boundary, [`process.py`](gr0wthlab/process.py) is where every process the launcher waits for starts, each with a time limit, and [`attempts.py`](gr0wthlab/attempts.py) tells from the launcher's records whether the week's run is still owed, which every scheduled start checks first.
- [`instructions/`](instructions/): the run's fixed task definition, which only a reviewed pull request changes; the agent's refinable guidance lives in `workspace/instructions/`.
- [`gr0wthlab/posts.py`](gr0wthlab/posts.py): the post-Draft workflow (US-ME08): which calendar days a run prepares, and which Drafts become post items; the checks themselves are in `drafts.py`, `kit.py`, `lint.py`, and `codebase.py`.
- [`gr0wthlab/beta.py`](gr0wthlab/beta.py): Beta Cohort recruiting (US-ME15): the Founder's gate, the next invitation batch by entry identifier, the counts the Founder reports, and which recruiting Drafts become message items; the Draft's checks are in `beta_drafts.py`, and the order invitations go out in is in `waitlist.py`, the view's one reader.
- [`dispatches/`](dispatches/): Dispatch requests in the Review Queue item format, which the launcher files for the Founder's approval, each once ([`dispatch.py`](gr0wthlab/dispatch.py)); the first is RepToday's Waitlist, whose anonymous view [`waitlist.py`](gr0wthlab/waitlist.py) reads.
- [`proposals/`](proposals/): package-change proposals the launcher files once each, such as the brand lint's word lists; no check ever reads them.
- [`examples/`](examples/): each workflow's example set, out of the agent's reach, [`post-drafts`](examples/post-drafts/README.md) and [`beta-recruiting`](examples/beta-recruiting/README.md).
- [`checks/`](checks/): instructions for live checks, such as the US-ME02 boundary probe.
- [`tests/`](tests/): unit tests, run with `/usr/bin/python3 -m unittest discover -s src/tests -t src`.
