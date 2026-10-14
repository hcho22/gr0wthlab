# A real run refuses to start while the repository is public, and pushes its records only while GitHub says it is private

The guard on a public gr0wthlab repository: in the production clone a run asks GitHub whether the repository `origin` pushes to is private before it does anything else, and refuses to start only when GitHub says plainly that it is public.
It asks again once the run's work is taken in, before the notice and the run report are written, and the records are pushed only when that answer says plainly that the repository is private; any other answer keeps them local, and the run report and the notice say so with the reason (`src/gr0wthlab/visibility.py`, [operations](../operations.md#the-repository-must-be-private)).
Until round 3 the start refused on any answer that was not plainly private, and the records step asked just before each push; rounds 1 and 2 record that guard.
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

## Round 2: the re-check after the merge with `main`

**What was run:** after the branch was brought up to `main` at `bdec245` (the refused-items change) with one merge commit, from the same linked worktree, on 2026-10-14 from 09:36 PDT, with Codex CLI 0.160.0, the same commands as in round 1: the real repository's refusal with no setting, then `src/bin/gr0wthlab preflight` and `src/bin/gr0wthlab boundary-check`.
The repository on GitHub was still public.

**On which commit:** the merge commit `d27a24c77eb7b77d81e8d983d601926c4b62ed1f`, with `src` tree `8a030ad0a1d14419e4cc8da70c6d62d54a678af3` and `config` tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`.
`git status` was empty before the runs and after the boundary check.
`show-config` printed the configuration fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`.

**Each run's identifier:** the refused run got none; the boundary check was `20261014T163642Z-on-demand-a486`.

**What the records showed:**

| Command | Run identifier | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab run`, the real repository as it is | none | exit code 4; it printed only `` refusing to start: the GitHub repository `<owner>/gr0wthlab` is public: a real run would publish its Drafts, its Evidence, and the Founder's records there, so the repository must be made private first `` (the account name replaced by `<owner>`), in 0.64 seconds; the scratch log folder stayed empty; `ledger/` held only `founder/`, `README.md`, and `run.lock`; `git status` stayed empty |
| `src/bin/gr0wthlab preflight` | none (no model) | exit code 0; 6 areas written; 19 paths refused; no breach and no failure; the listing of the footage place refused, none listed, none untried; both listed hosts unreachable, none reached, none untried |
| `src/bin/gr0wthlab boundary-check` | `20261014T163642Z-on-demand-a486` | PASSED at its first probe run; fingerprint `0daea7f4a2ca703b1e4ab2b0693837f6517a44f563953187c6c4c7f039ef5319`; 43 steps to prove; 0 sentinels escaped; 12 of 12 permitted sentinels written; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials naming the run's sentinels or the check's listeners; 1 of 1 forbidden read refused; no local connection got through; 3 sandbox network targets refused, none reached; nothing changed since the snapshot; agent time 61.6 s |

**What was not exercised:** the three ways of falling short of an answer (GitHub out of reach, no login, no gh) and the live `private` answer were not run again; they stand on round 1, whose `src/gr0wthlab/visibility.py` the merge did not change.
Everything round 1 lists as not exercised still stands as it says there.

## Round 3: the re-check after the narrower start guard

After review, the Founder chose on 2026-10-14 that a start refuses only on GitHub's plain word that the repository is public, so that a passing network failure at a weekly start no longer costs the week's run.
An answer that falls short of confirming that the repository is private now lets the run go ahead, and the question is asked again once the run's work is taken in, before the notice and the run report are written, so that the run's own report and notice can say that its records were kept local, with the reason.

**What was run:** from the same linked worktree, with the fix not yet committed, on 2026-10-14 from 10:50 PDT, with Codex CLI 0.160.0 and gh 2.96.0 in `/usr/local/bin`.
The repository on GitHub was still public.

```sh
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin GR0WTHLAB_PRODUCTION_CLONE="$PWD" GR0WTHLAB_LOG_DIR=<scratch>/logs [one setting below] src/bin/gr0wthlab run
GR0WTHLAB_LOG_DIR=<scratch>/bc-logs src/bin/gr0wthlab preflight
GR0WTHLAB_LOG_DIR=<scratch>/bc-logs src/bin/gr0wthlab boundary-check
```

**On which commit:** `7925ea4457b0e359c6db93eb2066098ae3b26d14` with the fix on top and not committed, whose `src` tree is `24fb29ec0ec8675fd921710e75e6aaa7b331ca94` and `config` tree `b43d0624383aada9155906ee4b54515c3ecb3a5d`, as `git rev-parse <commit>:src` and `git rev-parse <commit>:config` print for the commit that holds this fix.
`git status` listed the fix's 10 changed files and nothing else before the runs, and the same 10 after the boundary check.
`show-config` printed the configuration fingerprint `02e92343693f4b965e1d4eced781bd0c1a8156e367fb67c69c22261e0c912932`.

**Each run's identifier:** neither `run` start got one, since each ended before a run identifier is made; the boundary check was `20261014T175051Z-on-demand-e518`.

**What the records showed:**

| Run | Setting | Exit code | What the launcher printed (the account name replaced by `<owner>`) |
| --- | --- | --- | --- |
| the real repository as it is | none | 4 | `` refusing to start: the GitHub repository `<owner>/gr0wthlab` is public: a real run would publish its Drafts, its Evidence, and the Founder's records there, so the repository must be made private first `` |
| GitHub out of reach | `HTTPS_PROXY=http://127.0.0.1:9` | 4 | `pre-run: refused: the clone is on a detached HEAD, not main`, then `refusing to start; the production clone needs attention first` |

- The public refusal printed that one line, in the same words as rounds 1 and 2, in 1.84 seconds of wall-clock time.
- With GitHub out of reach, the start went past the question to GitHub to the pre-run sync, which refused the linked worktree for being on a detached HEAD, in 0.57 seconds; in round 1 the same setting ended at the question with `refusing to start: could not confirm that the GitHub repository is private`.
- The same question asked through `visibility.ask` with that setting answered `unconfirmed`, with `` gh api exited with 1: Get "https://api.github.com/repos/<owner>/gr0wthlab": proxyconnect tcp: dial tcp 127.0.0.1:9: connect: connection refused `` (the account name replaced by `<owner>`).
- The scratch log folder stayed empty after both starts, and `ledger/` held only `founder/`, `README.md`, and `run.lock` after them.

| Command | Run identifier | What the records showed |
| --- | --- | --- |
| `src/bin/gr0wthlab preflight` | none (no model) | exit code 0; 6 areas written; 19 paths refused; no breach and no failure; the listing of the footage place refused, none listed, none untried; both listed hosts unreachable, none reached, none untried |
| `src/bin/gr0wthlab boundary-check` | `20261014T175051Z-on-demand-e518` | PASSED at its first probe run; fingerprint `02e92343693f4b965e1d4eced781bd0c1a8156e367fb67c69c22261e0c912932`; 43 steps to prove; 0 sentinels escaped; 12 of 12 permitted sentinels written; 14 of 14 file-tool targets refused, each in a patch of its own; 16 kernel Seatbelt denials naming the run's sentinels or the check's listeners; 1 of 1 forbidden read refused; no local connection got through; 3 sandbox network targets refused, none reached; nothing changed since the snapshot; agent time 51.1 s |

**What was not exercised:**

- A whole run that goes ahead on an answer that falls short, keeps its commit local, and says so in its own report and notice: the linked worktree's pre-run sync refuses it first, and a production clone on `main` would run `main`'s code after its sync.
  It stands on `src/tests/test_cycle.py` (`test_a_repository_that_cannot_be_confirmed_private_runs_and_keeps_its_records_local`) and, for a start of the weekly schedule, `src/tests/test_attempts.py` (`test_a_weekly_start_that_cannot_confirm_the_repository_private_still_makes_the_week_s_run`), each with a stand-in for GitHub's answer.
- A run that pushes because GitHub says the repository is private, and a repository made public between the start and the push: `src/tests/test_cycle.py` (`test_a_private_repository_is_asked_about_before_the_run_and_again_before_the_push`, `test_a_repository_made_public_during_the_run_is_not_pushed_to`) and `src/tests/test_records.py` (`VisibilityTest`), with round 1's live `private` answer.
- No login and no gh were not run again; round 1 records `visibility.ask`'s answer for each, which this round's code did not change, and the start now lets either go ahead as it did GitHub out of reach above.
- The real `~/gr0wthlab` production clone, which does not exist yet.
