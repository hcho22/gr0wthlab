# Live checks: no session shown the skills installed on the Mac (US-ME02)

This file records what was run on the Founder's Mac for the change that adds `codex.skill_instructions` (`false`) to `config/guardrails/runtime.json`, which `codex.config_overrides` renders as `-c skills.include_instructions=false` on the session command and on every sandbox probe.
CI cannot run any of it: it needs the Mac's Codex install, the skills installed under `~/.codex/skills/` and `~/.agents/skills/`, and the Codex login.

How to read the paths:

- `<proof>` is a folder of the session that made the change, outside every checkout, which kept the renderings and the logs quoted here.
- `<worktree>` is the linked worktree of this repository the change was made in, under `~/.treehouse/`.

All times are Mac local time (PDT, UTC-7) on 2026-10-23.
Every check ran from `<worktree>` with Codex CLI `codex-cli 0.160.0`, the version `show-config` and the boundary check's record both printed.

## The commits

| Side | Commit | `src` tree | `config` tree | `show-config` fingerprint |
| --- | --- | --- | --- | --- |
| Before, `main` | `1899a4babdd62856c3a00e05402d28e36a2e1bae` | `0e59d81c8d1b4868444b525a6e7176cc0bbe6c42` | `9c9143d02be500ca3124a0ed0fef37002e60f102` | `e73481e3e3e4425625eb8cd7c121b6043119ed3bf6737e0b6f476b23500e6168` |
| With the change | `b8981c56928ae5fe4463e59674c998073e353e73` | `1d6476aeaf4499339dda759e3158a181e99fbfb5` | `142866d3a94a2a9c9fbff96d6cb0d2e82468b565` | `a558c62f1a7c4a3277171a3466356d7f88610362ef9766625b088e07510f150a` |

The command `show-config` prints holds the checkout's own path, so its fingerprint differs in another checkout.
`git status` was empty before the before-rendering, and before and after the preflight and the boundary check.

## Round 1: the session's prompt rendered before and after, with no model

Run at 11:08 on `main` and at 11:09 on the change, before it was committed; the committed change printed the same fingerprint, `a558c62f...`, so its session command is the one rendered.
A scratch script, `<proof>/render_prompt.py`, ran `src/bin/gr0wthlab show-config`, took from the session command it printed every `-c` and `--disable` pair and the model (as `-c model="gpt-6-luna"`), and ran `codex debug prompt-input` with them, in the session's working directory and with exactly the environment `show-config` printed.
`codex debug prompt-input` renders the model-visible prompt as JSON and calls no model.
It takes no `--ignore-user-config`, so it read `~/.codex/config.toml`, which holds no `skills` key.

| What the rendering showed | Before, `main` | With the change |
| --- | --- | --- |
| `skills.*` overrides in the session command | none | `skills.include_instructions=false` |
| `codex debug prompt-input` exit code | 0 | 0 |
| Bytes of JSON printed | 47,903 | 36,034 |
| `## Skills` headings | 1 | 0 |
| `<skills_instructions>` tags | 1 | 0 |
| Skill roots listed | 3 (`~/.codex/skills`, `~/.agents/skills`, `~/.codex/skills/.system`) | 0 |
| Skill entries, lines ending `(file: ...SKILL.md)` | 39 | 0 |
| `SKILL.md` anywhere in the prompt | 40 | 0 |

Three controls, at 11:09, each the change's command with `skills.include_instructions=false` taken out and one argument added at the end:

| Added | Bytes | `## Skills` headings | `(file: ` entries |
| --- | --- | --- | --- |
| `-c skills.bogus_key=false` | 47,903 | 1 | 39 |
| `--enable skip_host_skill_discovery` | 47,903 | 1 | 39 |
| `-c skills.include_instructions=false` | 36,033 | 0 | 0 |

Each exited 0 and wrote nothing to its error stream.

## Round 2: preflight and boundary check on the change

Run on `b8981c5`:

```
src/bin/gr0wthlab preflight          # 11:20:04 to 11:20:05
src/bin/gr0wthlab boundary-check     # 11:20:11 to 11:21:30
```

The preflight printed `"ok": true`: 6 areas writable, 22 paths refused, no breaches, no failures; a listing of the footage place refused with no footage folder in it, nothing listed and nothing untried; `www.reddit.com:443` and `itunes.apple.com:443` unreachable from the sandbox, none reached.

The boundary check was run `20261023T182013Z-on-demand-9fe5`, the only one, and printed:

```
boundary check 20261023T182013Z-on-demand-9fe5: PASSED
  steps this run had to prove: 49
  sentinels that escaped (files among them removed): 0
  permitted sentinels written: 12 of 12
  file-tool targets Codex refused, each in a patch of its own: 17 of 17
  kernel Seatbelt denials naming this run's sentinels or the check's listeners: 19
  forbidden reads of the footage place and its footage folders the runtime refused, each on its own: 1 of 1
  local connections that got through: none
  sandbox network: 3 targets refused, reached: none (the control outside the sandbox reached its listener: yes)
  launcher network: 2 requests sent, methods ['GET'], hosts ['itunes.apple.com', 'www.reddit.com']; robots.txt: www.reddit.com read, itunes.apple.com read; an unlisted address was refused
  changes since the snapshot from before the check: none
```

Its run record (`<run id>.json` in `~/Library/Logs/gr0wthlab/`) gives the configuration fingerprint `a558c62f...`, Codex `codex-cli 0.160.0`, exit code 0, and a `command` that holds `-c skills.include_instructions=false`; Codex's log gives `app.version=0.160.0`.
So a `codex exec` session started with the key ran to its end, and the verdict's counts above come from Codex's record of that session's tool calls.
The preflight's three `codex sandbox` probes carry the same overrides, and none reported a failure, which `codex.py` adds for a probe that exits with an error.

None of the run's files in `~/Library/Logs/gr0wthlab/` holds the session's prompt: the run record, the event stream, Codex's log, the probe instruction and script, the agent's last message and report, and the verdict hold no `SKILL.md`, no `## Skills`, and no `skills_instructions`.
So no record of a real session shows what the model was given, and round 1's rendering of the same command stands for it.

## What was not exercised

- No weekly run was started, and nothing in the production clone at `~/gr0wthlab` was read or changed; a weekly run's sessions start with the command `show-config` prints, which round 1 rendered.
- Whether the sandbox refuses a read of a skill file under `~/.codex/skills/` or `~/.agents/skills/` was not tried; this change only takes the list out of the prompt.
- The prompt was rendered with `~/.codex/config.toml` read, since `codex debug prompt-input` cannot skip it; that file holds no `skills` key, and a session skips it through `--ignore-user-config`.
- A Codex version other than 0.160.0 was not tried; the unit test in `src/tests/test_codex.py` holds that the session command and the sandbox probes' overrides carry the key, whatever Codex does with it.
