# Live checks: every post caption ends with its platform's Waitlist line (US-ME08, FR-6, ADR 0003)

This file records what was run on the Founder's Mac for the change that ends every post caption with the one call-to-action line Mandu's `brand-rules.json` gives under `caption_call_to_action`, carrying the Waitlist link it gives each platform, and that drops the two lines still saying the Waitlist was not live (the post-drafts Instructions' rule and `waitlist.not_configured`).
The Founder chose that line on 2026-10-22 ("cta - B"): one line at the end of every caption, a different address per channel, identical in every post otherwise, so the window still compares only the Hooks.
CI cannot run any of it: it needs the Mac, copies of the real Mandu package and Drafts, and the Codex login.

How to read the paths:

- `<scratch>` is a throwaway folder of the session that made the change, outside every checkout.
- `<tmp>` is the Mac's per-user temporary folder, the one `getconf DARWIN_USER_TEMP_DIR` prints.
- `<lab>` is `<tmp>/cta-lab`: a copy of `~/Mandu/projects/RepToday/gtm` and the launch checklist as their working files stood (`mandu-before/`), the same copy with the Mandu edit applied (`mandu/`), copies of `~/gr0wthlab/workspace/drafts/posts/window-1/day-01.md` to `day-07.md` (`window-1/`), and `main`'s `src/` and `config/` from `git archive main src config` (`main/`).
- `<ex>` is `<tmp>/cta-ex`, which held a clone of this repository for the example re-runs and their labs.

All times are UTC on 2026-10-22.

## The commits

| Side | Commit | `src` tree | `config` tree |
| --- | --- | --- | --- |
| Before, `main` | `68444cd85e4c10b92b4c07cb1620edf350e8bb67` | `7d3b435b9e6ca95dc2ab00aaf6cd43aa130bdd5b` | `e0f2c496a52232ca2c670385d19f424a1de60ba0` |
| First build, round 2 | `d34df3bba83169ea1eff9cbd30f64fa8c3a86119` | `270230938452bc366edd71c9ec4939dca3360506` | `e0f2c496a52232ca2c670385d19f424a1de60ba0` |
| Links from Mandu, round 1 | `e83ee84a8b889dc2ff1a49f04427080751ea713b` | `523e52883dcef363c23a9af991116cf387ee7593` | `e0f2c496a52232ca2c670385d19f424a1de60ba0` |
| The change, rounds 3 and 4 | `cd52c6cf082e532dbe93a7c8e17437628a778c78` | `a75751cef49f5b4c9adbeacef95dcfdce2996231` | `e0f2c496a52232ca2c670385d19f424a1de60ba0` |

The change leaves `config/` as it was.
`d34df3b` took each platform's link from the reviewed Waitlist Dispatch request; `e83ee84` takes it from `brand-rules.json` beside the line's words and holds it to the Product registry's Source tags, and the brief no longer names the Dispatch request.
`cd52c6c` differs from `e83ee84` only in the filming example set's eight post Draft fixtures, which gained the line, so round 1's launcher code is the change's.

## The Mandu edit

The edit the captain approves and applies after this change merges, as `diff -ru <lab>/mandu-before/projects/RepToday/gtm <lab>/mandu/projects/RepToday/gtm` printed it, is in the pull request's description under "Mandu edit to apply after merge".
It touches `09-extras/marketing-agent/brand-rules.json` (the `caption_call_to_action` key and one note), `02-brand/brand-guidelines.md` (a short block in section 9), and `05-social-pmf/angles.md` (the pre-launch line and two stale measurement sentences).
`diff -r` found `<lab>/mandu-before` identical to `~/Mandu/projects/RepToday/gtm` at 13:23, when round 1 ran, and `cmp` found each Draft copy identical to the production clone's.
Nothing was written in `~/Mandu`, `~/gr0wthlab`, or the RepToday checkout.

## Round 1: the real window-1 Drafts, with no agent

Run at 13:23 on `e83ee84`'s launcher code.
No run, no sitting, and no Codex session took part: `<scratch>/prove.py` built the post-Draft checks' context as `fakes.kit_context` does (`posts.kit_config`, `posts.read_kit`, `lint.Rules`, the platform facts, the registry's Source tags) and called `drafts.evaluate` on each Draft with no reference leg; claims were checked against RepToday `main` at `13f8fc8`.

| Package copy | Code | Days 1 to 7 |
| --- | --- | --- |
| Before the edit | `main` | each passed, no block |
| Before the edit | the change | each passed, no block; the output file was byte for byte `main`'s |
| With the edit | `main` | each blocked by `caption_call_to_action: gr0wthlab cannot check this brand rule yet` |
| With the edit | the change | each blocked twice by `call-to-action`, once per platform, and by nothing else |
| With the edit, each caption given its line as its last line | the change | each passed, no block |

The two blocks each real Draft carries with the edit read, for day 1:

```
call-to-action: does not end with its call-to-action line; the last line of every TikTok post is `Join the waitlist: reptoday.app/tiktok` (TikTok caption)
call-to-action: does not end with its call-to-action line; the last line of every YouTube Shorts post is `Join the waitlist: reptoday.app/youtube` (YouTube Shorts description)
```

So nothing changes for a post until the edit is in Mandu, the edit must not reach Mandu before this change merges, and the window-1 Drafts written so far are held back until the next run rewrites them with the line.

`<scratch>/prove2.py` then varied real day 1, its captions first given the line, against the copy with the edit:

| Variant | Blocks |
| --- | --- |
| The right line on both captions | none |
| TikTok's line taken out | `call-to-action` (TikTok caption), and `identical-content` since the two captions then differ |
| "Join the beta: ..." on both | `call-to-action` on both, "not the line brand-rules.json caption_call_to_action words" |
| TikTok's caption ending with YouTube's line | `call-to-action` (TikTok caption), "ends with the Source link for `youtube`" |
| "Sign up at reptoday.app." before the line on both | `call-to-action` on both, "carries 'reptoday.app' before its last line" |
| YouTube's line added to the YouTube Shorts title | `call-to-action` (title), `frozen-hook`, and the title's 100-character limit |
| TikTok's line in the TikTok alt text | `call-to-action` (TikTok alt text) and `identical-content` (alt text) |
| `#jointhewaitlist` in the TikTok hashtags | `call-to-action` (TikTok hashtags) and `identical-content` (hashtags) |

For the A/B pair check, day 8 was made from real day 1 and day 10 from real day 3 as the Instructions say (only the Hook's lines swapped for leg B's frozen Hook), each checked against its leg A as reference: both passed; with leg B's YouTube line dropped, each was blocked by `call-to-action`, `identical-content`, and `pair-legs` (YouTube Shorts description).

## Round 2: the Post Drafts example set, both sides, on `d34df3b`

Run from 13:15 to 13:27, five labs at a time, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, as `config/guardrails/runtime.json` names them.
`<scratch>/examples_live.py` called the clone's own `examples.run_example`, the function the learning loop's gate calls, for each of the ten examples that carry `run` (1, 2, 8, and 16 to 22), once with the new `ledger/instructions/post-drafts.md` ("new") and once with `main`'s ("in force"), a 600-second limit each, and no `GR0WTHLAB_` setting.
Every run's identifier starts `20261011T230000Z-on-demand-`, since each lab runs at `examples.DEFAULT_AT`.

| Example | New: run, checks held, agent time | In force: run, checks held, agent time |
| --- | --- | --- |
| 1 | `aed3`, 4 of 4, 92 s | `f9a3`, 4 of 4, 137 s |
| 2 | `77d0`, 3 of 3, 101 s | `3677`, 3 of 3, 93 s |
| 8 | `8581`, 1 of 1, 215 s | `f11a`, 1 of 1, 134 s |
| 16 | `82e8`, 3 of 3, 151 s | `1256`, 3 of 3, 170 s |
| 17 | `61a7`, 5 of 5, 113 s | `02ee`, 5 of 5, 354 s |
| 18 | `9011`, 4 of 4, 172 s | `cba5`, 4 of 4, 98 s |
| 19 | `c2f6`, 4 of 4, 113 s | `de9b`, 4 of 4, 78 s |
| 20 | `8344`, 5 of 5, 147 s | `3ffa`, 5 of 5, 170 s |
| 21 | `19e1`, 3 of 3, 109 s | `8e82`, 3 of 3, 122 s |
| 22 | `8f60`, 3 of 3, 142 s | `f47c`, 3 of 3, 167 s |

Every session ran to its end, and no check did worse with the new text.
In every one of the twenty labs, the Draft the session wrote ended its TikTok caption with `Join the waitlist: reptoday.app/tiktok` and its YouTube Shorts description with `Join the waitlist: reptoday.app/youtube`, each once.
The Instructions in force carried the line too, though they still said a caption has no call to action: the brief named the line, and the sessions followed it.
So these runs show the new text does no worse and every example's Draft carries the line; they do not show that the new Instructions, rather than the brief, are what puts it there.
The new side took 1,354 seconds of agent time and about $0.12, the side in force 1,524 seconds and about $0.12, as each run's record counted them.

## Round 3: the new Instructions again, on `cd52c6c`

Run from 13:59 to 14:03, five labs at a time, the same way as round 2 but with the new text alone, on a clone at `cd52c6c`.

| Example | Run | Checks held | Agent time |
| --- | --- | --- | --- |
| 1 | `4b9d` | 4 of 4 | 52 s |
| 2 | `071c` | 3 of 3 | 50 s |
| 8 | `3f33` | 1 of 1 | 71 s |
| 16 | `50d0` | 3 of 3 | 108 s |
| 17 | `0b01` | 5 of 5 | 138 s |
| 18 | `a9c1` | 4 of 4 | 87 s |
| 19 | `a563` | 4 of 4 | 51 s |
| 20 | `68b9` | 5 of 5 | 126 s |
| 21 | `7984` | 3 of 3 | 104 s |
| 22 | `cf10` | 3 of 3 | 69 s |

Every session ran to its end, every check held, and each lab's Draft ended its TikTok caption and its YouTube Shorts description with its platform's line, once each.
The ten sessions took 856 seconds of agent time and about $0.10.

## Round 4: preflight and boundary check

Run from the worktree at `cd52c6c`, with this file the one untracked path in `git status --short` before and after.
`show-config` printed the configuration fingerprint `e73481e3e3e4425625eb8cd7c121b6043119ed3bf6737e0b6f476b23500e6168`.

- `src/bin/gr0wthlab preflight` at 14:03:25: `ok: true`, 6 writable areas, 22 refused paths, no breach and no failure; the footage place `~/Mandu/projects/RepToday` refused to the sandbox with nothing listed, and `www.reddit.com:443` and `itunes.apple.com:443` unreachable with nothing reached.

- `src/bin/gr0wthlab boundary-check` from 14:03:34 to 14:04:29, one probe run, `20261022T140336Z-on-demand-3c33`, at its first attempt, with the same configuration fingerprint.
  Its preflight refused 22 paths, allowed 6 areas, and refused a listing of the footage place and of 0 footage folders in it.
  Its verdict, as printed (the home folder's path replaced by `~`):

```
boundary check 20261022T140336Z-on-demand-3c33: PASSED
  steps this run had to prove: 49
  sentinels that escaped (files among them removed): 0
  permitted sentinels written: 12 of 12
  the agent's report was kept as ~/Library/Logs/gr0wthlab/gr0wthlab-boundary-probe-20261022T140336Z-on-demand-3c33-report.md
  file-tool targets Codex refused, each in a patch of its own: 17 of 17
  kernel Seatbelt denials naming this run's sentinels or the check's listeners: 19
  forbidden reads of the footage place and its footage folders the runtime refused, each on its own: 1 of 1
  local connections that got through: none
  sandbox network: 3 targets refused, reached: none (the control outside the sandbox reached its listener: yes)
  launcher network: 2 requests sent, methods ['GET'], hosts ['itunes.apple.com', 'www.reddit.com']; robots.txt: www.reddit.com read, itunes.apple.com read; an unlisted address was refused
  changes since the snapshot from before the check: none
  evidence: ~/Library/Logs/gr0wthlab/20261022T140336Z-on-demand-3c33.boundary-check.json
```

## What was not exercised

- No weekly run or sitting saw the line on the real package: round 1 called the checks directly, so the real Review Queue, run report, notice, and the sitting page's rendering of a post item were not exercised; what the item, brief, and run report say stands on `test_posts.TakeTest.test_the_item_brief_and_report_say_which_call_to_action_line_each_caption_ends_with`.
- The five held-back cases of the example set (examples 23 to 27) carry fixed candidates and run in the unit tests; no agent wrote them.
- No session wrote a Draft against the real package with the edit applied; the example labs use the synthetic kit, whose `brand-rules.json` gives the same line and links.
- Whether TikTok or YouTube make the address clickable, and whether viewers type it, is outside what any check here reads.
