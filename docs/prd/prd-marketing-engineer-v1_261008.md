# PRD: Marketing Engineer v1 - RepToday Launch Marketing

**Status:** In progress (2026-10-08); each story's acceptance-criteria checkboxes record what has landed.
Written from the Founder's design session in firstmate on 2026-10-08; every decision it rests on is listed, in order, in `design-decisions-2026-10-08.md` beside this file.
The Marketing Engineer's repository is gr0wthlab (`hcho22/gr0wthlab`, public since 2026-10-12), and this PRD lives in it at `docs/prd/`.
On 2026-10-12 the Founder moved where the Founder decides, from Mandu to a page gr0wthlab serves; `docs/adr/0002-the-founder-decides-in-gr0wthlab.md` records it, and this PRD says what is true since.
This PRD, the glossary (`CONTEXT.md`, at the repository root), and the first decision record (`docs/adr/0001-evidence-and-drafts-only.md`) moved into it with its first change.
**Story prefix:** `US-ME##`.
**Vocabulary:** capitalized terms (Founder, Product, Marketing Engineer, Mandu, Dispatch, Draft, Evidence, Go-To-Market Package, Review Queue, Weekly Read, Instructions, Guardrail, Waitlist, Fit, Source, Angle, Hook, Listening, Beta Build, Beta Cohort) are defined in `CONTEXT.md` and are used only in those senses.
**Depends on:** the RepToday Waitlist (US-ME05) before any public post, because it is the last open Gate 0 item; a Beta Build approved for external testing before Beta Cohort recruiting (US-ME15).

**Sources this PRD reads but does not restate** (all in Mandu, all part of RepToday's Go-To-Market Package unless noted):

- `~/Mandu/projects/RepToday/gtm/05-social-pmf/cadence-14-day.md` - the 14-day calendar, the posting-slot rule, and the day-7 midpoint gate.
- `~/Mandu/projects/RepToday/gtm/05-social-pmf/angles.md` - every Angle, its sourced pain, Hook, format, pre-registered success signal, and kill criterion.
- `~/Mandu/projects/RepToday/gtm/05-social-pmf/ab-pairs.md` and `platform-assignment.md` - pair legs and per-platform rules.
- `~/Mandu/projects/RepToday/gtm/05-social-pmf/read-the-results.md` - the binding rules for reading results.
- `~/Mandu/projects/RepToday/gtm/02-brand/brand-guidelines.md` and `~/Mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json` - brand rules, including the machine-checkable lint.
- `~/Mandu/projects/RepToday/gtm/08-redteam/pre-publication-checklist.md` - the per-asset publication gate.
- `~/Mandu/projects/RepToday/gtm/06-channels/` - the channel plan and `event-metric-schema.md` (`landing_page_view`, `waitlist_signup` with `referrer_source`).
- `~/Mandu/projects/RepToday/gtm/07-thesis/` - the investment thesis, kill criteria, and the K8 first-run rubric that the Beta Cohort feeds.
- `~/Mandu/projects/RepToday/02-marketing-launch-checklist_260807.md` - Gate 0 and the launch tracks this PRD executes.
- `~/Mandu/projects/RepToday/gtm/09-extras/marketing-agent/BUILD-SPEC.md` - the earlier dry-run creative loop, whose honesty rules this PRD inherits.

---

## Introduction / Overview

RepToday has a complete, sourced, red-teamed go-to-market package and has published nothing.
Gate 0 is clear except the Waitlist: the name cleared trademark search and was reserved on 2026-08-07, `@reptoday` is held on TikTok, YouTube, Instagram, and X, and `reptoday.app` is live.
The 14-day social test kit is specified day by day, with pre-registered signals and kill criteria for every Angle.
The Founder's goal is income by the end of 2026, with RepToday as the primary bet, which leaves about twelve weeks.
The bottleneck is not ideas; it is the steady weekly execution that a solo founder building the product cannot sustain alongside development.

The Marketing Engineer is a standalone agent with its own repository that runs once a week on the Founder's Mac.
It turns the Go-To-Market Package into the week's Drafts, gathers Evidence, reads results against the pre-registered rules, and puts everything that needs a decision into one Review Queue the Founder clears in about an hour, at a weekly sitting on a page gr0wthlab serves on the Founder's Mac.
It never publishes, sends, or spends; every public act is the Founder's.
It never changes the Go-To-Market Package, Mandu, or any Product repository; it proposes, and the owner of each applies what the Founder approves.

v1 serves RepToday only, for its pre-launch phase: the Waitlist, the 14-day test kit, Listening, outreach Drafts, and Beta Cohort recruiting once a Beta Build exists.
Immerse joins as Listening only, after RepToday's first 14-day window has run cleanly (US-ME18).

### Who does what

| Actor | Owns | Never does |
| --- | --- | --- |
| Founder | Every approval, every public act (posting, sending, confirming a publishing schedule), filming, and the weekly TikTok export | - |
| Marketing Engineer | Evidence, Drafts, Review Queue items, Weekly Read memos, run reports, and its own Instructions; its repository also serves the Founder's sitting page and keeps the Founder's decisions | Publish, send, spend, see email addresses, write to Mandu or a Product repository, write or change a decision of the Founder's, or change its own code or Guardrails |
| Mandu | Each Product's Go-To-Market Package, applying approved package changes, handing approved Dispatch requests to firstmate, showing the Founder the Marketing Engineer's status, and receiving the TikTok export | Build the Marketing Engineer, record a decision of the Founder's, or write anything the Marketing Engineer reads but the Go-To-Market Package |
| firstmate | Building and changing the Marketing Engineer's code and Guardrails through reviewed pull requests, and carrying out approved Dispatches in Product repositories | Act on a Dispatch the Founder has not approved |
| Scheduling service | Publishing approved posts at the fixed slot after the Founder confirms the schedule | - |

### The weekly cycle

1. **Run.** Shortly before the Founder's weekly sitting, the Marketing Engineer reads the Go-To-Market Package from Mandu, the Founder's recorded decisions from its own repository, RepToday's repository, the anonymous Waitlist view, YouTube results, and any TikTok export the Founder has sent.
   It performs Listening, writes the Weekly Read memo on read weeks, prepares the next week's Drafts, proposals, and Dispatch requests, and writes a run report.
2. **Sitting.** On read weeks the Founder first exports TikTok Studio's per-post numbers and comments into Mandu.
   The Founder then decides every Review Queue item on the sitting page, one at a time: approve, or reject with a one-line reason.
   What the Founder clicks is what is saved, with no AI between the answer and the record.
3. **Publish.** Approved posts are loaded into the scheduling service as drafts at the fixed slot, and the Founder confirms the schedule there.
   Approved messages are sent by the Founder, who fills in recipients.
4. **Learn.** The next run reads the decisions, records every rejection reason as Evidence, refines Instructions where the reason is about execution, and proposes package changes where the reason is about strategy.

### v1 timeline

- **Setup week:** repository and spikes (US-ME01 to US-ME03), the package snapshot, the Review Queue, and the sitting (US-ME04, US-ME07), the Waitlist Dispatch (US-ME05, US-ME06), the first batch and filming plan (US-ME08, US-ME09), and the scheduler connection (US-ME10).
- **Window 1 (days 1 to 14):** the 14-day kit runs; Weekly Reads on day 7 and day 14 (US-ME11, US-ME12); Listening and outreach weekly (US-ME13, US-ME14).
- **After window 1:** the Immerse Listening gate (US-ME18) and the window-2 plan from the day-14 read.
- **Whenever a Beta Build is approved:** Beta Cohort recruiting (US-ME15).

---

## Goals

- Put RepToday's Waitlist live and run the 14-day test kit exactly as specified: one asset a day to both TikTok and YouTube Shorts at one fixed evening slot, with nothing public that the Founder has not confirmed.
- Build a Waitlist pool of about 50 or more good-Fit sign-ups who opted in to a Beta Build invitation by about day 30, enough to fill a 20 to 50 person Beta Cohort.
- Keep the Founder's weekly marketing time around one hour: one sitting plus the TikTok export, with filming days counted separately.
- Make every Draft traceable to its Angle and that Angle's sourced pain, and make every result reading honest: floors respected, "insufficient data" stated as its own result, never a zero.
- Learn every week: every rejection reason is kept, Instructions improve, and a per-workflow example set catches regressions.
- Recruit the Beta Cohort from the Waitlist as soon as a Beta Build passes Apple's review for external testing.
- Start Immerse Listening once window 1 has run cleanly, publishing nothing about Immerse.

---

## User Stories

> Stories are ordered dependency-first: prove the runtime boundary and the scheduler, connect the sources, put the Waitlist live, then run the kit, read it, and learn from it.
> Gated stories (US-ME15, US-ME18) come last and do nothing until their gate is met.
> As each story lands and its Validation Test passes, flip its acceptance-criteria checkboxes so this PRD doubles as a progress tracker.

---

### US-ME01: Create the repository and its foundation

**Description:** As the Founder, I want the Marketing Engineer to have its own private repository with its glossary, decision record, and boundaries written down, so that every later story builds on agreed language and a reader can see at once why the repository holds no strategy.

**Acceptance Criteria:**

- [x] A private repository exists under the Founder's GitHub account (final name confirmed by the Founder: gr0wthlab) and is registered as a firstmate project with the Founder's chosen review posture.
- [x] `CONTEXT.md` and `docs/adr/0001-evidence-and-drafts-only.md` are committed from firstmate's drafts with no change in meaning.
- [x] A README states the purpose, the actor table, the weekly cycle, and the Guardrails list from this PRD, and points to the Go-To-Market Package in Mandu rather than copying any of it.
- [x] The repository has distinct areas for Evidence, Drafts, Review Queue items, Weekly Read memos, run reports, and Instructions, and a separate area for code and Guardrail configuration.
- [x] A Product registry names RepToday as active and Immerse as Listening-only pending US-ME18, each with the read-only location of its repository and its Go-To-Market Package.
- [x] No positioning, Fit definition, claim, brand rule, or Angle is copied into the repository.

**Validation Test:**

- **Setup:** A fresh clone of the new repository.
- **Steps:**
  1. Read the README, `CONTEXT.md`, and the decision record.
  2. Search the repository for any positioning statement, Angle table, or brand rule.
- **Expected Result:** The documents exist and agree with this PRD; the search finds only references to Mandu, never copies.
- **Failure Indicator:** Strategy content is duplicated into the repository, or the actor boundaries are missing from the README.

---

### US-ME02: Spike - the runtime enforces the write boundary

**Description:** As the Founder, I want to prove before anything else is built that the scheduled agent physically cannot write outside its own working areas, so that the boundary in ADR 0001 is a Guardrail and not a sentence in a prompt.

**Acceptance Criteria:**

- [x] The runtime is chosen between a Codex automation and a Claude Code scheduled task on the Founder's Mac, recording why, and that choice is the only one the build relies on.
- [x] A scheduled weekly run and an on-demand run both start the agent with the same configuration.
- [x] During a run, the agent can write to its Evidence, Drafts, Review Queue, Weekly Read, run report, and Instructions areas.
- [x] During a run, writes to the repository's code and Guardrail configuration area, to anywhere in Mandu, and to any Product repository are refused by the runtime itself, not by the agent's choice.
- [x] A spike note records the runtime, its configuration, the refused-write evidence, and a go or no-go.
- [x] Time-box: about half a day; if neither runtime can enforce the boundary, stop and record the blocker for the Founder.

**Validation Test:**

- **Setup:** The repository from US-ME01, the chosen runtime, and a throwaway instruction that tries each forbidden write.
- **Steps:**
  1. Run the throwaway instruction on demand.
  2. Inspect Mandu, a Product repository, and the code area for changes.
- **Expected Result:** Every forbidden write fails with a runtime refusal, nothing outside the permitted areas changed, and the permitted write succeeded.
- **Failure Indicator:** Any forbidden write lands, or a refusal depends on the agent's own instruction rather than the runtime.

---

### US-ME03: Spike - a scheduling service accepts drafts for TikTok and YouTube Shorts

**Description:** As the Founder, I want to confirm one scheduling service can receive Drafts for both platforms without the Marketing Engineer being able to schedule or publish, so that the fixed evening slot is kept and every public post still waits on my confirmation.

**Acceptance Criteria:**

- [ ] A scheduling service is identified that TikTok and YouTube already allow to publish publicly and that supports YouTube Shorts and TikTok video posts at a chosen time.
- [ ] The service offers a way for the Marketing Engineer to create an unscheduled draft with the video, caption, and per-platform fields, and the integration built on it exposes no call that schedules or publishes.
- [ ] The cost at v1 volume (about 28 posts in 14 days across two platforms) is recorded, with the free tier's limits.
- [ ] One test draft is created on each platform from a throwaway asset and is visible to the Founder in the service, unscheduled and unpublished.
- [ ] A spike note records the service, the draft path, the absence of a publish path, the cost, and a go or no-go.
- [ ] If no service qualifies, the spike stops and the fallback (the Founder posting by hand from Mandu-delivered packages) is raised to the Founder as a decision rather than adopted silently.

**Validation Test:**

- **Setup:** A throwaway 9:16 video and caption; the Founder's TikTok and YouTube accounts connected to the chosen service by the Founder.
- **Steps:**
  1. Create one draft per platform through the integration.
  2. Inspect the service and both platforms.
- **Expected Result:** Two drafts exist in the service, neither is scheduled, and nothing appears on either platform.
- **Failure Indicator:** A draft cannot carry a video, a post becomes visible on a platform, or the integration can schedule or publish.

---

### US-ME04: Read the Go-To-Market Package from Mandu and the Founder's decisions from gr0wthlab

**Description:** As the Marketing Engineer, I want a read-only, dated snapshot of RepToday's Go-To-Market Package and the Founder's recorded decisions at the start of every run, so that every Draft rests on the current approved package and I can show what changed since the last run.

**Acceptance Criteria:**

- [x] Each run reads the package sources listed at the top of this PRD from Mandu, read-only, and records which files were read with a content fingerprint and the read time.
- [x] A source that is missing or unreadable is named in the run report and blocks only the work that depends on it.
- [x] The run lists what changed in the package since the previous run.
- [x] Contradictions inside the package are surfaced as package-change proposals that cite both sides.
  The first expected proposal: about a dozen files still say trademark clearance for "Rep Today" is unverified, while the launch checklist records it cleared and reserved on 2026-08-07.
- [x] The run reads every decision the Founder has recorded on the sitting page since the previous run, from `ledger/founder/` in its own repository, and matches each to its Review Queue item.

**Validation Test:**

- **Setup:** Mandu as it is today.
- **Steps:**
  1. Run on demand.
  2. Read the run report and the Review Queue.
- **Expected Result:** The snapshot lists the package files, the trademark contradiction appears as one package-change proposal with both sources cited, and Mandu is unchanged.
- **Failure Indicator:** The contradiction is missed, Mandu is modified, or a missing source fails the whole run.

---

### US-ME05: Dispatch the RepToday Waitlist

**Description:** As the Founder, I want the Marketing Engineer to file one complete request for RepToday's Waitlist that I approve and firstmate builds through RepToday's normal reviewed path, so that the last Gate 0 item closes without the Marketing Engineer ever touching the Product.

**Acceptance Criteria:**

- [ ] The Dispatch request is a Review Queue item and reaches firstmate only after the Founder approves it.
- [ ] The request specifies a sign-up on `reptoday.app` with exactly one low-pressure call to action and three fields: email, one Fit question, and an opt-in to a Beta Build invitation.
- [ ] The Fit question offers three answers, worded for Founder approval in the request: used to exercise and lost the routine; exercises regularly; never had a routine.
- [ ] Source is captured from the link with no extra field, using one link per Source (at least TikTok, YouTube, Reddit, and the Founder's personal network), with a sign-up reached without a tagged link recorded as unknown Source.
- [ ] The web events `landing_page_view` and `waitlist_signup` with `referrer_source` are emitted as defined in `gtm/06-channels/event-metric-schema.md`.
- [ ] The privacy policy at `reptoday.app/privacy` gains a Waitlist section covering what is collected, why, how long it is kept, and how to be removed.
- [ ] The Marketing Engineer gets a read-only, anonymous view of sign-ups (entry identifier, Source, Fit answer, opt-in, sign-up date) that contains no email address.
- [ ] Email addresses can be resolved only on the Founder's side, at send time.
- [ ] The request leaves storage, hosting, and implementation choices to RepToday's own design under firstmate.

gr0wthlab's side is in place, with the request filed from `src/dispatches/reptoday-waitlist.md`; every box waits for the approved RepToday build to land and pass this story's Validation Test.

**Validation Test:**

- **Setup:** The Waitlist deployed to `reptoday.app` after firstmate's reviewed change lands.
- **Steps:**
  1. The Founder signs up once through the TikTok Source link and once with no tag.
  2. Read the anonymous view.
  3. Open `reptoday.app/privacy`.
- **Expected Result:** Two entries appear with Sources TikTok and unknown, the Fit answers and opt-ins as entered, and no address; both page views and sign-ups are counted; the privacy page has the Waitlist section.
- **Failure Indicator:** An address appears in the view, a Source is lost, or the privacy page is unchanged.

---

### US-ME06: Read the Waitlist without addresses

**Description:** As the Marketing Engineer, I want weekly Waitlist counts by Source, Fit, and opt-in, so that the Weekly Read can show which channels bring good-Fit people and how far the pool is from the Beta Cohort bar.

**Acceptance Criteria:**

- [x] Each run reads the anonymous view from US-ME05 and records counts by Source, Fit answer, and opt-in, per week and cumulative.
- [x] Each run reports progress toward the bar of about 50 good-Fit opt-ins, where good Fit means the "used to exercise and lost the routine" answer unless the Founder approves a different definition.
- [x] If any value read from the view looks like an email address, the run discards the read, records no Waitlist Evidence that week, and reports a Guardrail breach to the Founder.
- [x] Waitlist Evidence stores entry identifiers and counts only.

**Validation Test:**

- **Setup:** A test copy of the view seeded with twelve entries across Sources and Fit answers, and one variant with an address-bearing field.
- **Steps:**
  1. Run against the clean seed.
  2. Run against the address-bearing variant.
- **Expected Result:** The first run reports correct counts and progress; the second refuses the read and reports the breach.
- **Failure Indicator:** Counts are wrong, or any address is stored or shown.

---

### US-ME07: Queue Review Queue items and take the Founder's decisions on the sitting page

**Description:** As the Founder, I want every item that needs me to arrive on one page in one consistent shape I can decide in under a minute, and my decisions and reasons to be kept where the Marketing Engineer reads them and can never write them, so that one weekly sitting runs the whole machine.

**Acceptance Criteria:**

- [x] Every item has a stable identifier, a kind, a one-line ask, the Draft or proposal itself, what it affects, the Evidence behind it with sources, and the decision options.
- [x] Item kinds are: post, message, package-change proposal, Dispatch request, Weekly Read decision, and notice (informational, such as an Instructions refinement or a failed source).
- [x] A rejection requires a one-line reason; an approval may carry an optional note.
- [x] The Marketing Engineer writes items only in its own repository.
  The Founder decides each on a page that `src/bin/gr0wthlab sitting` serves on the Founder's Mac, which asks one thing at a time and saves exactly what the Founder clicks, with no AI between the answer and the record.
  The decisions are kept in the same repository, in `ledger/founder/`, where the sandboxed agent can read and never write, and Mandu only reads.
- [x] An item is never re-asked once decided; an undecided item carries over to the next sitting and is marked as carried over.
- [x] A week's items are ordered so posts with the nearest slot come first.

**Validation Test:**

- **Setup:** The sitting page, served by `src/bin/gr0wthlab sitting`.
- **Steps:**
  1. Produce one item of each kind.
  2. On the page, the Founder approves two, rejects two with reasons, and leaves two undecided.
  3. Run again.
- **Expected Result:** Each decision is matched to its item, reasons are kept as Evidence, the undecided items carry over marked as such, and no decided item reappears.
- **Failure Indicator:** A decision is lost or mismatched, a rejection has no reason, or a decided item is asked again.

---

### US-ME08: Prepare each week's post Drafts from the 14-day kit

**Description:** As the Founder, I want each week's posts prepared exactly as the kit specifies, with the brand lint and publication checklist already applied, so that my sitting is a judgment of taste and accuracy, not a production job.

**Acceptance Criteria:**

- [x] Drafts follow `cadence-14-day.md` day by day: the Angle, the pair leg, the primary platform, and identical content on both platforms per `platform-assignment.md`.
- [x] Each post Draft includes the per-platform caption, on-screen text, hashtags, and alt text, and cites its Angle, its sourced pain, and its pre-registered signal and kill criterion by reference.
- [x] Hooks are used exactly as frozen in `ab-pairs.md` and `angles.md`; A/B legs differ only in the Hook; a changed signal is never an edit and enters only as a new Angle through a package-change proposal.
- [x] Every Draft passes the `brand-rules.json` lint, and a lint failure blocks the Draft from the Review Queue with the failing rule named.
- [x] Every Draft shows its status against `pre-publication-checklist.md`, and a Draft that fails the checklist is not offered for approval.
- [x] Every behavioral claim in a Draft is checked against RepToday's current code and shows the code location that supports it; an Angle that depends on the unsubstantiated "under 100 ms" claim stays blocked until the real-device measurement exists.
- [ ] No Draft implies users, downloads, ratings, reviews, testimonials, or results that do not exist, and none names a competitor.
  Waiting on Mandu: competitor names are checked, but the invented-proof list reaches the lint only once Mandu applies the brand-rules proposal (`src/proposals/brand-rules-word-lists.md`).

**Validation Test:**

- **Setup:** The current package; RepToday's repository at its current head.
- **Steps:**
  1. Generate the Drafts for days 1 to 7.
  2. Insert a banned word into one caption and regenerate.
- **Expected Result:** Seven post Drafts match the calendar, each cites its Angle and source, the lint passes, and the modified Draft is blocked naming the banned-word rule.
- **Failure Indicator:** A Draft departs from the calendar, a Hook differs from its frozen text, or the banned word reaches the Review Queue.

---

### US-ME09: Plan filming and turn footage into finished posts

**Description:** As the Founder, I want shot lists and script cards that batch my filming into as few sittings as possible, and finished edits made from my raw footage, so that being on camera on four days costs me one or two sessions rather than four evenings.

**Acceptance Criteria:**

- [x] A filming plan covers every asset in window 1 that needs the Founder or a real device: the founder-on-camera days (2, 4, 6, and 12) and the device demos, grouped into the fewest sittings the shot lists allow.
- [x] Each shot list states what to record, on which device, in real time or not, and what may not be cut, copied from the Angle's format in `angles.md`.
- [x] The filming plan is one Review Queue item, approved before filming.
- [ ] Raw footage the Founder drops in an agreed place is edited into 9:16 assets per the shot list, with on-screen text and captions applied, and the re-cut pair legs (days 8, 9, 10, and 13) reuse their footage with only the opening changed.
  Waiting on the Founder's real footage: the agreed place is unset until the Founder sets it (`config/products.json`), and nothing is filmed yet, so this is proven live only on stand-in test footage for days 1 and 8.
- [x] Finished assets become post Drafts in US-ME08's shape.
- [x] No asset uses an AI-generated person, voice, or scene presented as real, and nothing invents footage the Founder did not record.

The plan is the Review Queue's `filming-plan` kind, which the Founder approves on the sitting page like any item; nothing is cut from a shot's footage until a plan that holds the shot is approved.
Day 14 joins the plan once the calendar decides its Angle, and the script card of each day is the Video table of its post item.

**Validation Test:**

- **Setup:** Sample raw footage for the day 1 cold-open demo.
- **Steps:**
  1. Produce the day 1 and day 8 assets.
  2. Compare them.
- **Expected Result:** Both are 9:16, follow the shot list, and differ only in the Hook.
- **Failure Indicator:** The legs differ beyond the Hook, a no-cut rule is broken, or generated imagery stands in for real footage.

---

### US-ME10: Load approved posts into the scheduling service as drafts

**Description:** As the Founder, I want every post I approve to appear as a draft at the fixed evening slot on both platforms, waiting only for my confirmation, so that the slot never drifts and nothing goes public without me.

**Acceptance Criteria:**

- [ ] After the Founder approves a post, the next run creates its drafts in the scheduling service for both platforms, set to the window's fixed slot on the calendar day.
- [ ] The Marketing Engineer never schedules, confirms, or publishes; the Founder confirms the schedule in the service.
- [ ] The run reads the service back and reports any confirmed post whose time differs from the fixed slot, and any calendar day with no confirmed post by the day before it.
- [ ] A rejected or undecided post never reaches the service.

**Validation Test:**

- **Setup:** The service connected in US-ME03; two approved post Drafts and one rejected.
- **Steps:**
  1. Run.
  2. The Founder confirms one post's schedule and leaves the other.
  3. Run again.
- **Expected Result:** Four drafts exist (two posts on two platforms); the confirmed one shows the fixed slot; the second run reports the unconfirmed day; the rejected post is absent.
- **Failure Indicator:** The integration schedules or publishes anything, a draft has the wrong time, or a rejected post appears.

---

### US-ME11: Collect results from YouTube and the Founder's TikTok export

**Description:** As the Marketing Engineer, I want each post's results gathered from YouTube automatically and from the Founder's weekly TikTok export, so that the Weekly Read judges every Angle on its own pre-registered signal.

**Acceptance Criteria:**

- [ ] YouTube results are read with read-only access to the Founder's channel: per post, views, the share viewed rather than swiped away, average percentage viewed, likes, comment count, and comment text.
- [ ] Before each read week's sitting, the Review Queue carries a notice listing exactly which TikTok Studio numbers and comments to export for which posts (views or impressions, average watch time, watched-full rate, likes, comments, shares, saves, profile visits, and comment text).
- [ ] The Founder's export, received through Mandu as screenshots or a file, is turned into Evidence per post with the export date as its source.
- [ ] A number that was not reported is recorded as not reported, never as zero, and never estimated.
- [ ] Follower counts and other numbers without a pre-registered use are not stored.

**Validation Test:**

- **Setup:** A recorded YouTube response for two posts and a sample TikTok Studio screenshot set missing one post.
- **Steps:**
  1. Run the collection.
  2. Inspect the Evidence.
- **Expected Result:** Both YouTube posts and the exported TikTok posts have Evidence with sources; the missing TikTok post is marked not reported.
- **Failure Indicator:** A missing value becomes zero, a number is inferred, or a vanity number is stored.

---

### US-ME12: Write the Weekly Read memo

**Description:** As the Founder, I want a short memo on each read week that applies the kit's binding read rules and ends every line in a decision, so that I decide keep, kill, change, or test in minutes and nothing is judged on noise.

**Acceptance Criteria:**

- [ ] The memo applies `read-the-results.md` exactly: the 200-impression floor (below it a post is unread, not failed), relative rank within the Angle bank once at least ten posts are readable, and kills only after two consecutive Weekly Reads.
- [ ] The day-7 memo covers days 1 to 5 only, may flag an Angle at risk but never kill it, and states whether the day-14 flex slot is earned per the cadence rules.
- [ ] The day-14 memo resolves A/B pairs only where both legs were readable and the rank gap is large, and otherwise recommends reposting.
- [ ] Comment content is reported as a first-class result, quoting comments that describe the pains the Angles target.
- [ ] Results that `read-the-results.md` says would change the product are listed as Evidence and, if warranted, as a Dispatch request for the Founder, never acted on.
- [ ] The memo includes Waitlist counts by Source and Fit, progress toward the opt-in bar, and the Founder's reported time that week.
- [ ] Every line ends in keep, kill, change, or test, and "insufficient data" is stated as its own result.
- [ ] Each decision line is its own Weekly Read decision item in the Review Queue.

**Validation Test:**

- **Setup:** A synthetic result set for days 1 to 7 with one post under the floor, one top-ranked post that missed its threshold, and one that cleared it.
- **Steps:**
  1. Produce the day-7 memo.
- **Expected Result:** The under-floor post is unread, nothing is killed, at-risk flags follow the rules, and the flex slot goes only to the Angle that cleared its threshold.
- **Failure Indicator:** A kill at day 7, a ranked under-floor post, or a flex slot awarded on rank alone.

---

### US-ME13: Listen weekly for RepToday

**Description:** As the Founder, I want a weekly read of what busy adults say about exercise, routines, and competing apps, in their own words, so that new Angles and Hooks come from real people rather than guesses.

**Acceptance Criteria:**

- [ ] Each run reads, without posting, r/fitness30plus, r/bodyweightfitness, r/getdisciplined, and recent App Store reviews of the competitors named in the package's research.
  The Founder decided on 2026-10-11 that each host's `robots.txt` is binding for now, while the owners' terms are read first-hand: each run asks for these sources and reports every one, but each host's `robots.txt` disallows the path a credential-free reader would need, so none is requested while that decision stands.
- [ ] Each finding is Evidence with the verbatim quote, the link, and the date read.
  Waiting on a readable source: the Evidence record and its validator are in place and pass on synthetic fixtures, and no real finding exists yet.
- [ ] A proposed new Angle or Hook enters only as a package-change proposal that cites at least one sourced pain; anything without a source is discarded by the Marketing Engineer's own check.
  Waiting on the Validation Test: the check is in place and passes on synthetic fixtures, and a story's boxes flip only when its Validation Test passes, which needs a readable source.
- [ ] Where RepToday genuinely answers a thread, the Marketing Engineer may draft a reply as a message Draft with no link of any kind, for the Founder to post personally.
  Waiting on a readable source: the reply Draft and its no-link check are in place, and no thread can be read yet.
- [ ] Each subreddit's self-promotion rules are summarized for the Founder the first time it is used, and the Founder confirms before any reply Draft for that subreddit is offered.
  Waiting on a readable source: the rules notice and the confirmation gate are in place, and no rule list can be read yet.

The launcher reads the sources itself, outside the sandbox, through one credential-free read-only client whose host list is reviewed configuration; the agent has no network (`config/guardrails/fetch.json`, `src/gr0wthlab/fetch.py`).

**Validation Test:**

- **Setup:** Network access to the named sources.
- **Steps:**
  1. Run Listening once.
  2. Feed it a proposed Angle with no source.
- **Expected Result:** Quotes with working links and dates are recorded; the unsourced Angle is discarded with a note.
- **Failure Indicator:** A quote lacks a link, a reply Draft carries a link, or an unsourced Angle is proposed.

---

### US-ME14: Draft personal-network asks and three creator messages

**Description:** As the Founder, I want ready-to-send messages for my own network and the three creators the plan names, so that the Waitlist's first sign-ups come from people I can reach today.

**Acceptance Criteria:**

- [ ] Personal-network asks are identity-framed ("movement that fits the life you already have"), never loss-framed, and carry the personal-network Source link.
  Waiting on Mandu: the Source link is checked, but the loss-framing list reaches the lint only once Mandu applies the proposal (`src/proposals/outreach-word-lists.md`).
- [ ] Three creator messages are drafted, one each for GMB Fitness, Hybrid Calisthenics, and The Bioneer: ask-free (early access, a founder conversation, or story material), never a sponsorship request.
  Waiting on Mandu: the offer is checked, but the sponsorship-ask list reaches the lint only once Mandu applies the same proposal.
- [x] Each creator gets at most one follow-up Draft, offered only after a waiting period the Founder approves, and then no further contact.
- [x] Every message passes the brand lint and is sent by the Founder.

What was sent and who replied reaches gr0wthlab only as the Founder's outreach record, made on the sitting page (`docs/mandu-exchange.md`); until the Founder records a message as sent, no follow-up is offered.

**Validation Test:**

- **Setup:** The current package.
- **Steps:**
  1. Produce the outreach Drafts.
  2. Simulate one creator reply and one non-reply past the waiting period.
- **Expected Result:** Identity-framed asks with the right Source link; three creator Drafts; a single follow-up offered for the non-reply only.
- **Failure Indicator:** A loss-framed line, a sponsorship ask, a second follow-up, or a follow-up to someone who replied.

---

### US-ME15: Recruit the Beta Cohort once a Beta Build is approved

**Description:** As the Founder, I want the Marketing Engineer to start recruiting the Beta Cohort from the Waitlist the moment I record that a Beta Build passed Apple's review, so that the first real customer evidence starts flowing without delay.

**Acceptance Criteria:**

- [x] The gate is a Beta Build approval the Founder records on the sitting page; before it, this story does nothing.
- [x] Candidates are chosen by entry identifier from the anonymous Waitlist view, opted-in good-Fit entries first.
- [x] Invitation Drafts are identity-framed, explain the recorded 30-minute first session the thesis's K8 rubric needs, and contain no address; the Founder resolves addresses and sends.
- [x] Only counts of invitations sent, accepted, and sessions booked are kept as Evidence, from what the Founder reports.
- [x] Recruiting continues weekly until the Beta Cohort reaches 20 to 50 people or the Founder stops it, and a pool too small to reach 20 is reported with the recruiting Drafts needed to close the gap.

Since 2026-10-12 the Founder records the approval, the counts, and a stop on the sitting page, in gr0wthlab's own `ledger/founder/` (ADR 0002), so no box waits on Mandu.
This story's Validation Test passed through that page on 2026-10-12, with the real agent in a throwaway lab on a synthetic package and a seeded view: nothing was queued before the approval, and the run after it queued one batch of eight entry identifiers with an invitation Draft that holds no address.
The counts given on the page were kept as Evidence with the two left blank as not reported, the too-small pool was reported with a Waitlist ask, and a stop on the page withdrew the open recruiting item ([the record](../live-checks/20261013-gr0wthlab-decisions-in-gr0wthlab.md)).
A cohort that reaches 20 to 50 was not reached there; that end of recruiting stands on `src/tests/test_beta_cycle.py`.

**Validation Test:**

- **Setup:** The seeded anonymous view from US-ME06; a Beta Build approval recorded on the sitting page.
- **Steps:**
  1. Run before the approval.
  2. Record the approval and run again.
- **Expected Result:** Nothing happens before; after, a candidate list of entry identifiers and invitation Drafts without addresses.
- **Failure Indicator:** Recruiting before the gate, or an address anywhere in the output.

---

### US-ME16: Learn from every decision

**Description:** As the Founder, I want every rejection to make the next week better and every change to the Marketing Engineer's Instructions to be visible to me, so that the system improves without drifting where I cannot see.

**Acceptance Criteria:**

- [ ] Every rejection reason is kept as Evidence linked to its item.
- [ ] A reason about execution (tone, length, a factual slip) may refine the Marketing Engineer's Instructions; a reason about strategy (Fit, an Angle, a claim, positioning) becomes a package-change proposal instead.
- [ ] Each workflow has a set of about ten example inputs with their expected outputs, re-run on every Instructions change, and a change that makes any example worse is not kept.
- [ ] Every kept Instructions change appears as a notice at the next sitting, with the reason that prompted it and the example results.

Rejection-reason coding landed early, with US-ME13 and US-ME14: each reason gets a code from a fixed list split into execution and strategy, a strategy reason is routed to a package-change proposal, and no run can change Instructions yet (`src/gr0wthlab/learning.py`).
The refinement loop and the example re-run are still this story's to build, so its boxes stay open.

**Validation Test:**

- **Setup:** One post Draft and its workflow's example set.
- **Steps:**
  1. Reject the Draft with an execution reason, and another with a strategy reason.
  2. Run again.
- **Expected Result:** One Instructions change with a passing example re-run and a notice; one package-change proposal; no Instructions change from the strategy reason.
- **Failure Indicator:** A strategy reason edits Instructions, an Instructions change skips the example re-run, or no notice appears.

---

### US-ME17: Run on schedule and report honestly

**Description:** As the Founder, I want each run to finish with a short report of what it checked, what failed, and what it skipped, so that I can trust a quiet week and never miss a broken source.

**Acceptance Criteria:**

- [ ] The weekly run is scheduled shortly before the Founder's sitting, and an on-demand run is available.
- [x] A run that starts late, for example because the Mac was asleep, says so.
- [x] The run report lists every source with its result: read, changed, failed with the reason, or skipped with the reason; there are no silent skips.
- [x] A failed source becomes a notice in the Review Queue, and every output that depended on it is marked incomplete.
- [x] The run report records the run's approximate cost.

**Validation Test:**

- **Setup:** Revoke the YouTube read access.
- **Steps:**
  1. Run on demand.
- **Expected Result:** The run completes, the report names YouTube as failed with the reason, a notice is queued, and the memo marks YouTube results missing.
- **Failure Indicator:** The run fails entirely, or YouTube results appear as zeros.

---

### US-ME18: Start Immerse Listening after window 1 (gated)

**Description:** As the Founder, I want Immerse Evidence gathered once RepToday's first window has run cleanly, publishing nothing, so that Immerse's naming decision and future Go-To-Market Package start from what real film-photography people say.

**Acceptance Criteria:**

- [ ] The gate is met only when window 1 ran cleanly (all 14 posts went out at the fixed slot and both Weekly Reads were delivered) and the Founder confirms in Mandu; before it, nothing runs for Immerse.
- [ ] Listening covers film-photography communities and reviews of film-camera and Hipstamatic-type apps, and reads Immerse's own market research in its repository, read-only.
- [ ] Output is Evidence only, with verbatim quotes, links, and dates; proposals for Immerse's naming decision and future Go-To-Market Package go to Mandu as package-change proposals.
- [ ] Nothing about Immerse is drafted for public posting, and no Immerse handle, page, or Waitlist is proposed until Immerse has a name.

**Validation Test:**

- **Setup:** Window 1 complete; the Founder's confirmation recorded in Mandu.
- **Steps:**
  1. Run before the confirmation.
  2. Run after it.
- **Expected Result:** Nothing for Immerse before; after, a first Evidence set with sources and no public Drafts.
- **Failure Indicator:** Immerse work before the gate, or any public Immerse Draft.

---

## Functional Requirements

- **FR-1:** The Marketing Engineer must only ever produce Drafts; posting, sending, and confirming a publishing schedule are the Founder's alone.
- **FR-2:** The Marketing Engineer must read the Go-To-Market Package from Mandu, read-only, at the start of every run, and must never copy strategy into its own repository.
- **FR-3:** The Marketing Engineer must never write to Mandu or to any Product repository; a Product change is a Dispatch request that reaches firstmate only after the Founder approves it.
- **FR-4:** Every Review Queue item must be decidable in under a minute and must show the ask, the Draft or proposal, what it affects, and its sourced Evidence.
- **FR-5:** A rejection must carry a one-line reason, which is kept as Evidence.
- **FR-6:** Every Draft must cite its Angle and that Angle's sourced pain, pass the brand lint, pass the pre-publication checklist, and have every behavioral claim supported by RepToday's current code.
- **FR-7:** Pre-registered Hooks, signals, and kill criteria must be used exactly as recorded; a change to any of them enters only as a new Angle through a package-change proposal.
- **FR-8:** The 14-day window must post one asset a day to both TikTok and YouTube Shorts at one fixed evening slot that never varies during the window.
- **FR-9:** No public post may go out before the Waitlist is live, because the Waitlist is the last Gate 0 item.
- **FR-10:** Results must be judged only at Weekly Reads and only under `read-the-results.md`; a missing number is "not reported", never zero.
- **FR-11:** The Marketing Engineer must never see, store, or send an email address.
- **FR-12:** Every Evidence record must carry its source (a link, or the Founder export and its date) and the date it was gathered.
- **FR-13:** Every run must report every source it checked and every failure; no source may be skipped silently.
- **FR-14:** Instructions changes must re-run the workflow's example set and be shown to the Founder at the next sitting.
- **FR-15:** Beta Cohort recruiting must not start until the Founder records an approved Beta Build on the sitting page.
- **FR-16:** Immerse work must not start until the US-ME18 gate is met, and must publish nothing.

---

## Guardrails

Each Guardrail is enforced by the tools the Marketing Engineer works through, not by its Instructions, and the Marketing Engineer cannot change any of them (ADR 0001; decision 12).

| ID | Guardrail | Enforced by |
| --- | --- | --- |
| G1 | Writes are possible only in the Evidence, Drafts, Review Queue, Weekly Read, run report, and Instructions areas | The runtime's write restrictions (US-ME02) |
| G2 | No writes to Mandu or any Product repository | The runtime's write restrictions (US-ME02) |
| G3 | The scheduling service can receive drafts only | An integration with no schedule or publish call (US-ME03, US-ME10) |
| G4 | YouTube access is read-only | Read-only access granted by the Founder |
| G5 | No TikTok, Instagram, X, Reddit, or email sending credentials exist | None are provisioned |
| G6 | No email address is ever readable | The anonymous Waitlist view (US-ME05), plus the breach check (US-ME06) |
| G7 | No spend is possible | No advertising account or payment credential is provisioned |
| G8 | Code and Guardrail configuration change only through firstmate's reviewed pull requests | The runtime's write restrictions (US-ME02) |

The Founder's decisions and the records of what the Founder did are in `ledger/founder/`, outside every area G1 names.
So G1 is also what keeps the Marketing Engineer from writing an approval: every run's preflight tries each folder of those records, and the boundary check proves each one refused on its own (ADR 0002).

---

## Non-Goals (Out of Scope)

- **No paid advertising and no spend of any kind.** RepToday's channel plan runs zero paid spend pre-launch, and the dry-run creative loop's publish and spend switch remains a separate Founder decision.
- **No autonomous publishing, sending, or replying**, on any channel, at any time.
- **No direct posting through the TikTok or YouTube APIs.** Apps those platforms have not reviewed can post only privately.
- **No Instagram or X posting in v1.** Those handles are held defensively, and the 14-day kit posts to TikTok and YouTube Shorts.
- **No changes to the Go-To-Market Package by the Marketing Engineer**, only proposals.
- **No Product changes by the Marketing Engineer**, only Dispatch requests.
- **No email addresses or other personal data** in the Marketing Engineer's reach.
- **No AI-generated people, voices, or scenes presented as real**, consistent with the package's honesty rules.
- **No fabricated users, downloads, ratings, testimonials, or results** in any Draft or memo.
- **No Purvia work** and no Immerse public presence.
- **No dashboards**; the Weekly Read memo and run reports are the only reporting surfaces.
- **No always-on agent and no daily runs**; one weekly run plus on-demand runs.

---

## Design Considerations

- **Review Queue item shape.** A title line naming the ask ("Approve day 3 post: missed-day score record"), the Draft itself, a "touches" line (which posts, messages, or package files change), the Evidence lines with links, and the options; nothing else.
- **Weekly Read memo shape.** One short section per readable Angle, then unread Angles in one line, then the Waitlist and time lines; every line ends in keep, kill, change, or test.
- **Voice.** Every Draft follows `brand-guidelines.md`; the memo and notices use plain outcome language for the Founder.
- **Founder time.** The sitting page measures how long each sitting took, and the Founder can correct it in one field; the TikTok export notice states which posts to capture so the export takes minutes.
- **The sitting page.** One thing in front of the Founder at a time, in the Review Queue's order, with the answer beside it: approve, reject with a reason, or leave for later; everything an item says is shown as text.

---

## Technical Considerations

- **Runtime.** A local scheduled automation on the Founder's Mac, in Codex or Claude Code, chosen in US-ME02 by which enforces G1, G2, and G8 most cleanly; Mandu's own weekday review already runs as a Codex automation, `mandu-weekday-project-review`.
- **Reading Mandu.** Read-only from the local Mandu checkout; the content fingerprint per file in US-ME04 is what lets a run state exactly what changed.
- **Reading RepToday.** Read-only from a local RepToday checkout at the default branch, for claim checks and screenshots.
- **The sitting, and the Mandu exchange.** The Marketing Engineer writes Review Queue items in its own repository, and the Founder decides them on a page that `src/bin/gr0wthlab sitting` serves on the Founder's Mac.
  That page writes each decision, and each record of what the Founder did, into the same repository, in `ledger/founder/`, where the sandboxed agent can read and never write (ADR 0002).
  Mandu writes nothing the Marketing Engineer reads except the Go-To-Market Package: it reads the Review Queue, the run reports, and the Founder's records to show status and to act on an approved package change or Dispatch request (`docs/mandu-exchange.md`).
  The TikTok export (US-ME11) and the US-ME18 confirmation are the two inputs this PRD still routes through Mandu; neither story is built, and where each goes is the Founder's to decide when it is.
- **Waitlist.** The deployable site source is in RepToday's repository (`gtm/03-site/`), served at `reptoday.app`, which also serves the privacy policy the app links to; storage and the anonymous view are RepToday's design under firstmate (US-ME05).
- **Scheduling service.** Chosen in US-ME03; the integration exposes a create-draft call and nothing else.
- **YouTube.** Read-only access to the Founder's own channel for analytics and comments.
- **TikTok.** No credentials; results arrive only through the Founder's export via Mandu.
- **Reuse.** The brand lint rules and the creative-log fields of the dry-run creative loop in `gtm/09-extras/marketing-agent/` are the starting point; the code is re-implemented in the Marketing Engineer's repository, and results live there as Evidence rather than in Mandu's copy of the creative log.
- **Video editing.** Local tooling on the Founder's Mac, as the package's launch-video build already uses.

### Mandu-side requirements (owned by Mandu, outside this repository)

Mandu is a reader since 2026-10-12 (ADR 0002): it records no decision, and writes nothing the Marketing Engineer reads except the Go-To-Market Package.
Nobody has built Mandu's read-only side yet, and the Founder's sitting does not wait for it.

- Read the Marketing Engineer's Review Queue, run reports, and the Founder's records from gr0wthlab, to show the Founder status.
- Apply package-change proposals the Founder approved to the Go-To-Market Package, reading each approval from gr0wthlab once a run has taken it in, starting with the stale trademark notes.
- Hand approved Dispatch requests to firstmate under Mandu's existing Dispatch arrangement, reading each approval the same way.
- Receive the Founder's weekly TikTok export and keep it where the Marketing Engineer can read it.
- Record the US-ME18 confirmation.

### firstmate-side requirements

- Create and register the repository on the Founder's word (US-ME01).
- Build and change the Marketing Engineer's code and Guardrails only through reviewed pull requests.
- Carry out approved Dispatches, starting with the Waitlist, through each Product's normal reviewed path.

---

## Success Metrics

Judged at about day 30, against the Founder's bar (decision 16).

- **Pool:** about 50 or more good-Fit Waitlist sign-ups who opted in to a Beta Build invitation, enough to fill a 20 to 50 person Beta Cohort.
  Missing it means changing channels or Angles, not producing more of the same.
- **Founder time:** about one hour a week of marketing time (one sitting plus the TikTok export), with filming days counted separately.
  Missing it means the machine costs more than it saves.
- **Execution (supporting, not the bar):** the Waitlist live before the first post, all 14 window-1 posts out at the fixed slot, both Weekly Reads delivered, and zero Guardrail breaches.

### What is readable at day 30, and what is not

- **Readable:** Waitlist sign-ups by Source and Fit; per-post platform signals for posts above the 200-impression floor; comment content; the Founder's time.
- **Not readable, by construction:** which individual post drove a sign-up, because each platform allows one profile link, so attribution stops at the Source; anything about installs, retention, or conversion, because no App Store listing exists; and any verdict from posts under the floor.

---

## Open Questions

- **Repository name and review posture.** Answered 2026-10-08: the working name `MarketingEngineer` became gr0wthlab; product-facing work goes through the full no-mistakes pipeline, internal tooling by direct pull request, and the Founder approves every merge.
- **Scheduling service.** Which service qualifies under US-ME03, at what cost, and what the Founder wants if none does.
- **Clickable link on TikTok.** The package's research notes that TikTok may not offer a new account a clickable profile link; until it does, TikTok viewers can reach the Waitlist only by typing the address, so a short, speakable Source path (for example one per Source on `reptoday.app`) may be needed, and the kit's "no URL on slides" rule may need a package change now that the domain is decided.
- **Waitlist details on RepToday's side.** Storage, whether sign-ups confirm their email, retention period, and how the Founder resolves addresses from entry identifiers at send time.
- **Beta invitations.** Whether the Founder invites by TestFlight public link or by individual email invitation, and therefore what the Founder's send step needs.
- **Sitting day and window start.** Which weekday the Founder's sitting falls on, which sets the run time and day 1 of window 1.
- **TikTok export form.** Whether TikTok Studio offers a file export at this account size or screenshots are the only route.
- **Founder time measurement.** Answered 2026-10-12: the sitting page times each sitting, and the Founder can correct the minutes before they are recorded.
- **Owner slots outside this PRD.** The thesis still needs a named non-founder to code K8 first runs and an outside person to hold the walk-away call; the Beta Cohort's value depends on both, and neither is the Marketing Engineer's to fill.
- **Window 2.** Whether a second 14-day window runs with the queued pairs and Angles, decided from the day-14 Weekly Read.
