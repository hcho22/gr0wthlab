# A real run refuses to start, and its records step to push, while the repository is not confirmed private

The guard on a public gr0wthlab repository: in the production clone a run asks GitHub whether the repository `origin` pushes to is private before it does anything else, and the records step asks again before each push (`src/gr0wthlab/visibility.py`, [operations](../operations.md#the-repository-must-be-private)).
It serves no story of its own; it keeps the Founder's records off a public repository from the first real run on.

## Round 1: the first re-check

**What was run:** from a linked worktree of the repository on the branch `fm/gr0wthlab-public-repo-run-guard`, on 2026-10-14 from 07:21 PDT, with Codex CLI 0.160.0.
The repository on GitHub was public, as it has been since 2026-10-14.
No production clone exists on the Mac (`~/gr0wthlab` is absent), so each run below named the worktree as the production clone with `GR0WTHLAB_PRODUCTION_CLONE`, and ran with the environment the weekly LaunchAgent gives the launcher (`PATH=/usr/bin:/bin:/usr/sbin:/sbin` and `HOME`), with the log folder in a scratch folder:

```sh
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin GR0WTHLAB_PRODUCTION_CLONE="$PWD" GR0WTHLAB_LOG_DIR=<scratch>/logs [one setting below] src/bin/gr0wthlab run
src/bin/gr0wthlab preflight
src/bin/gr0wthlab boundary-check
```

**On which commit:** `e2c6b5e3319362b6245dae7ffb73e3d9ed42cd2f`, with `src` tree `b8cbe1de1faac40b59b327a6448fe0c04202ced8` and `config` tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`.
`git status` was empty before the runs and after the boundary check.
`show-config` printed the configuration fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`.

**Each run's identifier:** none of the four runs got one, since each ended before a run identifier is made; the boundary check was `20261014T142219Z-on-demand-9d6d`.

**What the records showed:**

| Run | Setting | Exit code | What the launcher printed (the account name replaced by `<owner>`) |
| --- | --- | --- | --- |
| the real repository as it is | none | 4 | `` refusing to start: the GitHub repository `<owner>/gr0wthlab` is public: a real run would publish its Drafts, its Evidence, and the Founder's records there, so the repository must be made private first `` |
| GitHub out of reach | `HTTPS_PROXY=http://127.0.0.1:9` | 4 | `` refusing to start: could not confirm that the GitHub repository is private (gh api exited with 1: Get "https://api.github.com/repos/<owner>/gr0wthlab": proxyconnect tcp: dial tcp 127.0.0.1:9: connect: connection refused), and a real run would publish ... `` |
| no login | `GH_CONFIG_DIR=<an empty folder>` | 4 | `` refusing to start: could not confirm that the GitHub repository is private (gh api exited with 4: To get started with GitHub CLI, please run: gh auth login ...), and a real run would publish ... `` |
| no gh | `GR0WTHLAB_GH_BIN=/nonexistent/gh` | 4 | `` refusing to start: could not confirm that the GitHub repository is private (gh is not an executable at `/nonexistent/gh`), and a real run would publish ... `` |

- Each printed that one line and nothing else, and took 0.38 to 1.02 seconds of wall-clock time.
- The scratch log folder stayed empty after all four, so no session and no boundary preflight left a record there.
- `ledger/` held only `founder/`, `README.md`, and `run.lock` after them, as before: no run report, no package snapshot, and no Evidence.
- The worktree's `git status` stayed empty, so nothing was committed, and nothing was pushed, since nothing was committed.
- Neither the LaunchAgent's `PATH` nor `/opt/homebrew/bin` holds gh on this Mac, and `/usr/local/bin` does (gh 2.96.0), so the first run's answer came from that one, which the launcher searches after the `PATH`.

The same question asked of a private repository of the same account, from a scratch git folder whose `origin` names it, through `visibility.ask` with the LaunchAgent's `PATH`, answered `private`.

| Command | Run identifier | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab preflight` | none (no model) | exit code 0; 6 areas written; 19 paths refused; no breach and no failure; the listing of the footage place refused, none listed, none untried; both listed hosts unreachable, none reached, none untried |
| `src/bin/gr0wthlab boundary-check` | `20261014T142219Z-on-demand-9d6d` | PASSED at its first probe run; fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`; 43 steps to prove; 0 sentinels escaped; 12 of 12 permitted sentinels written; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials naming the run's sentinels or the check's listeners; 1 of 1 forbidden read refused; no local connection got through; 3 sandbox network targets refused, none reached; nothing changed since the snapshot; agent time 81.8 s |

**What was not exercised:**

- A run that proceeds because GitHub says the repository is private: the repository is public, and making it private is the Founder's act. It stands on `src/tests/test_cycle.py` (`test_a_private_repository_is_asked_about_before_the_run_and_again_before_the_push`) with a stand-in for GitHub's answer, and on the live `private` answer above.
- A push withheld because the repository was made public during a run, and the next run's report line about it: `src/tests/test_cycle.py` (`test_a_repository_made_public_during_the_run_is_not_pushed_to`) and `src/tests/test_records.py` (`VisibilityTest`).
- A weekly start refused this way, as the LaunchAgent would start it: `src/tests/test_attempts.py` (`test_a_production_clone_whose_repository_is_public_refuses_once_and_waits_for_the_founder`).
- An answer from GitHub that is neither plainly private nor plainly public, and a GitHub that answers nothing within 60 seconds: `src/tests/test_visibility.py`, with a stand-in for gh.
- The real `~/gr0wthlab` production clone, which does not exist yet.
