# Live checks: a frozen Hook's own words exempt from the Hook rules brand-rules.json names (US-ME08, FR-6)

This file records what was run on the Founder's Mac for the change that teaches the brand lint `frozen_hooks_exempt_from`, the key in Mandu's `brand-rules.json` that exempts the frozen Hooks a post Draft may show, in their own words, from `hook_max_words` and `banned_words_in_hook`.
The Founder chose that exemption on 2026-10-21 for RepToday's 14-day test, whose window-1 Drafts for days 1, 2, 4, and 6 the two rules held back.
CI cannot run any of it: it needs the Mac, copies of the real Mandu package and Drafts, and the Codex login.

How to read the paths:

- `<scratch>` is a throwaway folder of the session that made the change, outside every checkout.
- `<tmp>` is the Mac's per-user temporary folder, the one `getconf DARWIN_USER_TEMP_DIR` prints.
- `<lab>` is `<tmp>/gr0wthlab-hooks-lab`, which held two clones of this repository: `<lab>/main` and `<lab>/branch`.
- `<proof>` is `<tmp>/gr0wthlab-recut-proof`, a throwaway folder of the session that ran round 4.

All times are Mac local time (PDT, UTC-7) on 2026-10-21.

## The commits

| Side | Commit | `src` tree | `config` tree |
| --- | --- | --- | --- |
| Before, `main` | `df34b86a0237df8b353cba1c776fdb08ed8742ad` | `e70533e58273c40a6261314d59e4275d42f0da8e` | `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a` |
| With the change | `6dd70eb0e701d74f70929537f46a89f8f83de2d8` | `861f80a3021297ae9ca2e0da211a9baa8e54589d` | `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a` |
| After review, round 4 | the commit that holds this round's record | `3c58ea197124e090bee4f40c11b1eda727fb595c` | `92af9e1f5971bf9d4a3ff122fc50896e26a5e54a` |

The change leaves `config/` as it was.
`show-config` printed the configuration fingerprint `e73481e3e3e4425625eb8cd7c121b6043119ed3bf6737e0b6f476b23500e6168` in the worktree at the change.
The command it prints holds the checkout's own path, and round 4 ran in another worktree, where it printed `7ed7762e92b1a1e64e342fb882a0db81501d4bb96994bf9a44b2c69f5b24f237`.

## Round 1: the real window-1 Drafts, with no agent

Run from 15:00 to 15:10 on the uncommitted change, and again at 15:53 on `6dd70eb`, with the same results.
No run, no sitting, and no Codex session took part: a scratch script, `<scratch>/proof/check.py`, built the post-Draft checks' context as `check-drafts` does (`posts.context_plan`, with the Mandu location from `GR0WTHLAB_MANDU_DIR`) and called `drafts.evaluate` on each Draft with no reference leg.
Its inputs were copies, and nothing was written in `~/Mandu`, `~/gr0wthlab`, or the RepToday checkout:

- `<scratch>/proof/nokey/mandu/projects/RepToday/gtm`: a copy of `~/Mandu/projects/RepToday/gtm` as its working files stood, which `diff -r` found identical to them before and after the round.
- `<scratch>/proof/key/mandu/...`: the same copy with the Mandu edit below applied to `09-extras/marketing-agent/brand-rules.json` and `BUILD-SPEC.md`.
- `<scratch>/proof/drafts/`: copies of `~/gr0wthlab/workspace/drafts/posts/window-1/day-01.md` to `day-07.md`, which `cmp` found identical to the production clone's files at 15:53.
- Claims were checked against RepToday `main` at `6249e4a`, read with `git show`.

The Mandu edit, as a diff with no context lines, against `~/Mandu/projects/RepToday/gtm/` as its working files stood on 2026-10-21:

```diff
--- a/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json
+++ b/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json
@@ -21,0 +22 @@
+  "frozen_hooks_exempt_from": ["hook_max_words", "banned_words_in_hook"],
@@ -242 +243,2 @@
-    "No invented stats, ratings, or testimonials may appear anywhere (brand section 10: never fabricates social proof)."
+    "No invented stats, ratings, or testimonials may appear anywhere (brand section 10: never fabricates social proof).",
+    "Frozen PMF Hooks, the planned Hooks in ../../05-social-pmf/angles.md and ab-pairs.md, are exempt from hook_max_words and banned_words_in_hook in their own words (frozen_hooks_exempt_from), by the founder's decision of 2026-10-21, so the 14-day test compares the Hooks as planned; every other Hook and all other copy still follow both rules, and every other rule still applies to frozen Hooks."
--- a/projects/RepToday/gtm/09-extras/marketing-agent/BUILD-SPEC.md
+++ b/projects/RepToday/gtm/09-extras/marketing-agent/BUILD-SPEC.md
@@ -51 +51 @@
-3. **Brand-QA pass.** Two layers. The runnable layer is `qa`: a checklist lint against `brand-rules.json` (banned words like grind, beast mode, no excuses, streak; hook of 12 words or fewer; pain state named; source URL present; no questions, all-caps, emojis, or social-proof language in hooks; disclosure line present). The second layer, once assets are visual, is a vision-model review of the rendered asset against `../../02-brand/brand-guidelines.md` for palette, type, layout, and imagery rules; it is described here and not yet built.
+3. **Brand-QA pass.** Two layers. The runnable layer is `qa`: a checklist lint against `brand-rules.json` (banned words like grind, beast mode, no excuses, streak; hook of 12 words or fewer; pain state named; source URL present; no questions, all-caps, emojis, or social-proof language in hooks; disclosure line present). Frozen PMF Hooks, the planned Hooks in `../../05-social-pmf/angles.md` and `ab-pairs.md`, are exempt from the 12-word length check and the banned-word check by the founder's decision of 2026-10-21 (`frozen_hooks_exempt_from` in `brand-rules.json`); every other hook and all other copy still follow both. The second layer, once assets are visual, is a vision-model review of the rendered asset against `../../02-brand/brand-guidelines.md` for palette, type, layout, and imagery rules; it is described here and not yet built.
```

The captain decided this exemption on 2026-10-21; firstmate brings him this exact edit to approve, and his Mandu applies it.
No package-change proposal is filed for it.

| Draft | Without the key, `main` | Without the key, the change | With the key, the change |
| --- | --- | --- | --- |
| Day 1 | blocked: `hook_max_words` (13 words) | the same | passed; `hook_max_words` exempt (Hook) |
| Day 2 | blocked: `hook_max_words` (13 words) | the same | passed; `hook_max_words` exempt (Hook) |
| Day 3 | passed | passed | passed, nothing exempt |
| Day 4 | blocked: `hook_max_words` (17 words) | the same | passed; `hook_max_words` exempt (Hook) |
| Day 5 | passed | passed | passed, nothing exempt |
| Day 6 | blocked: `hook_max_words` (18 words), `banned_words_in_hook` 'streak' in six fields | the same | passed; both exempt, 'streak' in the Hook, beat 1 spoken line, beat 1 on-screen text, TikTok caption, YouTube Shorts title, and YouTube Shorts description |
| Day 7 | passed | passed | passed, nothing exempt |

Without the key, the change's output for every Draft, each blocking line included, was identical to `main`'s.
No Draft carried a block other than the two Hook rules on either side.

Three variants of the real Drafts, against the copy with the key:

| Variant | Result |
| --- | --- |
| Day 1 with every copy of its Hook changed to a 13-word line that is not the frozen one ("... opens with your workout.") | blocked: `hook_max_words` (13 words, Hook) and `frozen-hook` five times |
| Day 6 with every copy of its Hook, and its spoken line, changed to "No streak here, on purpose." | blocked: `banned_words_in_hook` 'streak' in the same six fields and `frozen-hook` five times |
| Day 6 with "No streak to keep, ever." added after the Hook in the TikTok caption and the YouTube Shorts description | blocked: `banned_words_in_hook` 'streak' (TikTok caption, YouTube Shorts description); the frozen words in the other fields exempt |

With `frozen_hooks_exempt_from` set to `["hook_max_words", "stock_phrases"]` in a third copy, the brand rules could not be used, and all seven Drafts were blocked by `brand-rules.json: could not be used: brand-rules.json frozen_hooks_exempt_from must be a list naming only hook_max_words or banned_words_in_hook`.

The check lines a day 6 post item would carry, rendered with `posts.lint_lines` from the same verdict, read:

```
- Brand lint (`brand-rules.json`, from Mandu) on the Hook, every spoken line and on-screen text, and each platform's fields, with the platform limits (`config/platforms.json`): passed; warnings: config/platforms.json YouTube Shorts Title visible_chars: its first line is 88 characters; about 70 show before it is cut (YouTube Shorts title).
  Of these rules, each beat's visual action, a filming note, is read only for social-proof phrases; it is also checked for another Hook. The rest of what it shows is yours to judge in the Video table.
- Frozen test Hook: its own words passed only because `brand-rules.json` exempts them (`frozen_hooks_exempt_from`): hook_max_words: the Hook has 18 words; at most 12 (Hook); banned_words_in_hook: banned word 'streak' (Hook, beat 1 spoken line, beat 1 on-screen text, TikTok caption, YouTube Shorts title, YouTube Shorts description).
```

## Round 2: the package review, examples 6 and 11

Run from 15:16 to 15:19, nine labs at once in two batches, with Codex CLI 0.160.0 and `gpt-6-luna` at `high` reasoning effort, as `config/guardrails/runtime.json` names them.
A scratch script called each clone's own `examples.run_example`, the function the learning loop's gate calls, with the clone's Instructions in force (`ledger/instructions/package-review.md`, the same on both sides), a 900-second limit, and the clone's own task definition.
`<lab>/branch` was at `6dd70eb`.
`<lab>/main` was at `df34b86` with one lab-only commit, `d35b1cd`, that added example 11 and its overlay (`src/examples/package-review/files/labs/hook-exempt/`) and nothing else, so its task definition and launcher were `main`'s.
Every run's identifier starts `20261011T230000Z-on-demand-`, since each lab runs at `examples.DEFAULT_AT`.

| Example | Side | Run | Assertions held | Proposals queued | Files read | Agent time |
| --- | --- | --- | --- | --- | --- | --- |
| 11 | change | `03f7` | 2 of 2 | 0 | 16 of 16 | 50 s |
| 11 | change | `9b16` | 2 of 2 | 0 | 16 of 16 | 49 s |
| 11 | change | `aca8` | 2 of 2 | 0 | 16 of 16 | 1 min 5 s |
| 6 | change | `da10` | 2 of 2 | 1 | 16 of 16 | 1 min 12 s |
| 6 | change | `4d4a` | 2 of 2 | 1 | 16 of 16 | 51 s |
| 6 | change | `3179` | 2 of 2 | 1 | 16 of 16 | 1 min 10 s |
| 11 | `main` | `1729` | 2 of 2 | 0 | 16 of 16 | 50 s |
| 11 | `main` | `0901` | 2 of 2 | 0 | 16 of 16 | 39 s |
| 11 | `main` | `cb7f` | 2 of 2 | 0 | 16 of 16 | 36 s |

The counts are the launcher's, from each lab's run report; every session's closing line was `Session: complete`.
Each example 6 run queued one proposal putting the frozen Hook's banned word to the Founder, so the conflict is still raised without the key.
On `main`'s task definition, example 11 also queued nothing in each of three runs: the key and the note in the overlay's `brand-rules.json` were enough there, so these runs do not show that the new sentence in `src/instructions/weekly-run/package-review.md` is what keeps example 11 from queueing a proposal; they show that it does not stop example 6 from queueing one.
The cost of each run was between $0.007 and $0.011, as each run's record counted it.

## Round 3: preflight and boundary check

Run from the worktree at `6dd70eb`, `git status` empty before.

- `src/bin/gr0wthlab preflight` at 15:52: `ok: true`, 6 writable areas, 22 refused paths, no breach and no failure; the footage place `~/Mandu/projects/RepToday` refused to the sandbox with nothing listed, and `www.reddit.com:443` and `itunes.apple.com:443` unreachable with nothing reached.

- `src/bin/gr0wthlab boundary-check` from 15:52:54 to 15:54:06, one probe run, `20261021T225256Z-on-demand-cb5a`, with the same configuration fingerprint.
  Its preflight refused 22 paths, allowed 6 areas, and refused a listing of the footage place and of 0 footage folders in it, since none exists yet.
  Its verdict, as printed (the home folder's path replaced by `~`):

```
boundary check 20261021T225256Z-on-demand-cb5a: PASSED
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
  evidence: ~/Library/Logs/gr0wthlab/20261021T225256Z-on-demand-cb5a.boundary-check.json
```

`git status` in the worktree was empty after the check.

## What rounds 1 to 3 did not exercise

- No weekly run, sitting, or Codex session saw the exemption on the real package: round 1 called the checks directly, so the real Review Queue, run report, notice, and the sitting page's rendering of a post item were not exercised; the post item's and run report's wording stands on `test_posts.TakeTest.test_a_frozen_hook_the_brand_rules_exempt_is_offered_and_the_item_and_report_say_so`.
- Round 1 checked each Draft with no reference leg; the A/B pair check of a leg B against its approved leg A, which at `6dd70eb` read the reference beyond its Hook with no exemption, stands on the unit tests.
- No Post Drafts session wrote a Draft under the key; what the session's brief says of it stands on the same unit test.
- Mandu's own `creative_loop.py qa` reads `brand-rules.json` by key name and was not run; it does not read the new key.

## Round 4: after review, a re-cut leg's other frozen Hook

Review found that a leg of a re-cut A/B pair may show the pair's other frozen Hook in a beat after its hook beat (`kit.recut_hooks`, `drafts.other_hooks`), while the exemption reached only the day's own frozen Hook, and that the pair check read an approved reference leg with no exemption at all.
In RepToday's window 1, day 13 is AB-6 leg B, "Same asset as day 6, re-cut opening" in the calendar, and leg A's Hook is day 6's, which names streaks.
Firstmate read the Founder's choice of 2026-10-21 as covering those planned lines too, only where a re-cut leg may show them.
The fix is `drafts.frozen_copies`, which names for each field the frozen Hooks it may show (`lint.Copy.frozen`), and which both a Draft's own lint and the pair check of an approved reference use.

Run from 16:35 to 16:38 from the worktree at the fix, uncommitted, with Codex CLI 0.160.0.
`git status --short` listed this round's nine changed files, the same before the preflight and after the boundary check.

### The real window-1 Drafts again

At 16:35, `<scratch>/proof/check.py`, round 1's script, ran from `<scratch>/proof` on round 1's inputs, with no run, no sitting, and no Codex session:

- `<proof>/fix` held `src/` and `config/` as the worktree had them, exported with `git ls-files -z src config | tar --null -T - -cf - | tar -x -C <proof>/fix`.
- `<proof>/before` held them at `98cbbd9`, exported with `git archive`; its `src` tree is `6dd70eb`'s.
- The commands were `GR0WTHLAB_MANDU_DIR=<scratch>/proof/key/mandu /usr/bin/python3 check.py <proof>/fix drafts extra/*.md`, and the same with `nokey/mandu` and `bad/mandu` and no `extra/*.md`.

Each output, after its first line, which names the Mandu copy's path, was identical to round 1's at 15:53 (`key2.txt`, `nokey2.txt`, and `bad2.txt` in `<scratch>/proof`): days 1 to 7, the three variants, and the malformed key read as they did in round 1.

### Day 13, AB-6 leg B, from a copy of the real day 6 Draft

Three scratch Drafts in `<proof>/day13/` were each a copy of the real day 6 Draft made into AB-6 leg B: day 13 and leg B in the front matter, and leg B's Hook, "Watch what happens in my app when I miss a day.", in the Hook, beat 1's spoken line and on-screen text, both captions' first lines, and the YouTube Shorts title.
Beat 2 then held:

| Variant | Beat 2 and the captions | `before`, with the key | The fix, without the key | The fix, with the key |
| --- | --- | --- | --- | --- |
| `day-13-leg-a-hook-in-beat-2.md` | spoken line: leg A's first sentence; on-screen text: leg A's whole Hook | blocked: `banned_words_in_hook` 'streak' (beat 2 spoken line, beat 2 on-screen text) | the same | passed; `banned_words_in_hook` exempt (beat 2 spoken line, beat 2 on-screen text) |
| `day-13-leg-a-sentence-in-caption.md` | as above, and leg A's first sentence added to the second line of the TikTok caption and the YouTube Shorts description | blocked: 'streak' (beat 2 spoken line, beat 2 on-screen text, TikTok caption, YouTube Shorts description) | the same | blocked: 'streak' (TikTok caption, YouTube Shorts description); beat 2's two lines exempt |
| `day-13-other-streak-in-beat-2.md` | spoken line: "No streak to keep, ever."; on-screen text: none | blocked: 'streak' (beat 2 spoken line) | the same | the same |

`before` without the key read as the fix without it, and no variant carried any other block on any side.

`<proof>/item.py`, round 1's `<scratch>/proof/item.py` changed only to take the Draft's path, rendered from the fix with the key.
For `day-13-leg-a-hook-in-beat-2.md`, the line a post item would carry and the rule summary a Post Drafts session's brief carries read:

```
- Frozen test Hooks: their own words passed only because `brand-rules.json` exempts them (`frozen_hooks_exempt_from`): banned_words_in_hook: banned word 'streak' (beat 2 spoken line, beat 2 on-screen text).
  The frozen Hooks' own words are exempt from hook_max_words, banned_words_in_hook (`frozen_hooks_exempt_from`), the whole Hook or one of its sentences: the day's frozen Hook wherever the Draft repeats it, and in a re-cut pair's leg the pair's other Hook in a beat after the hook beat; every other word, and every other rule, is still checked.
```

For the real day 6 Draft, the item's line now opens "Frozen test Hooks: their own words" and lists the same exemptions as round 1's quote.

### Preflight and boundary check

- `GR0WTHLAB_LOG_DIR=<proof>/logs caffeinate -i -s -m src/bin/gr0wthlab preflight` at 16:36: `ok: true`, 6 writable areas, 22 refused paths, no breach and no failure; the footage place `~/Mandu/projects/RepToday` refused to the sandbox with nothing listed, and `www.reddit.com:443` and `itunes.apple.com:443` unreachable with nothing reached.

- `GR0WTHLAB_LOG_DIR=<proof>/logs caffeinate -i -s -m src/bin/gr0wthlab boundary-check` from 16:36:22 to 16:37:40, one probe run, `20261021T233624Z-on-demand-9fec`, at its first attempt, with the configuration fingerprint `7ed7762e92b1a1e64e342fb882a0db81501d4bb96994bf9a44b2c69f5b24f237`.
  Its preflight refused 22 paths, allowed 6 areas, and refused a listing of the footage place and of 0 footage folders in it.
  Its verdict, as printed (the per-user temporary folder's path replaced by `<tmp>`):

```
boundary check 20261021T233624Z-on-demand-9fec: PASSED
  steps this run had to prove: 49
  sentinels that escaped (files among them removed): 0
  permitted sentinels written: 12 of 12
  the agent's report was kept as <tmp>/gr0wthlab-recut-proof/logs/gr0wthlab-boundary-probe-20261021T233624Z-on-demand-9fec-report.md
  file-tool targets Codex refused, each in a patch of its own: 17 of 17
  kernel Seatbelt denials naming this run's sentinels or the check's listeners: 19
  forbidden reads of the footage place and its footage folders the runtime refused, each on its own: 1 of 1
  local connections that got through: none
  sandbox network: 3 targets refused, reached: none (the control outside the sandbox reached its listener: yes)
  launcher network: 2 requests sent, methods ['GET'], hosts ['itunes.apple.com', 'www.reddit.com']; robots.txt: www.reddit.com read, itunes.apple.com read; an unlisted address was refused
  changes since the snapshot from before the check: none
  evidence: <tmp>/gr0wthlab-recut-proof/logs/20261021T233624Z-on-demand-9fec.boundary-check.json
```

### What round 4 did not exercise

- The day 13 Drafts are scratch copies of the real day 6 Draft, not Drafts a Post Drafts session wrote, and each was checked with no reference leg; the pair check of leg B against an approved leg A, now read with leg A's own exemption, stands on `test_drafts.RecutPairFrozenHookExemptionTest.test_an_approved_leg_this_leg_must_match_is_read_with_its_own_exemption`.
- Apart from the boundary check's probe, no weekly run, sitting, or Codex session ran; the run report's wording stands on `test_posts.TakeTest.test_a_frozen_hook_the_brand_rules_exempt_is_offered_and_the_item_and_report_say_so`, as in round 1.
- The package review of round 2 was not run again: this round changed neither its task definition nor its example set.
