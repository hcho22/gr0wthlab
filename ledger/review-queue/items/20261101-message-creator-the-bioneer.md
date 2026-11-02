---
exchange: 8
id: 20261101-message-creator-the-bioneer
kind: message
product: RepToday
supersedes: 20261016-message-creator-the-bioneer
---

# Approve message to The Bioneer: A story about ready workouts

## Draft

A message for you to send to The Bioneer, in your own name; gr0wthlab sends nothing and holds no address.
It offers story material and asks for nothing: no sponsorship, no post, no reply owed.
One follow-up may be offered 7 days after you record this message as sent on the sitting page, only while no reply is recorded, and after it nothing more. Approving this item approves that waiting period; to set another, give it when you record the message as sent.
If The Bioneer ever posts about RepToday after receiving early access, that is a material connection they must disclose.

**Message** (30 words)

> I'm the founder of Rep Today. When the Ready screen loads, it generates a workout for that day. I can offer story material about how the workout engine was built.

**Notes for you, never sent**

> The channel plan identifies The Bioneer as a video essay channel and recommends pitching the workout engine as story material. Check that this remains useful before sending.

**Claims, checked against RepToday `main` at `138a203`**

- The Ready screen's generation function asks the workout engine for a workout using the selected duration, user profile, recent logs, and session policy. `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:431-436` shows `let generated = try await workoutEngine.generateWorkout( requestedMinutes: requested, user: user, recentLogs: recentLogs, sessionPolicy: policy )`
Only the claims listed here were checked; anything else it says the app does is yours to judge.

**Checks**

- Brand lint (`brand-rules.json`, from Mandu) on the message: passed.
- No sponsorship ask the brand rules list: checked.
- No email address: checked.
- Pre-publication checklist (`projects/RepToday/gtm/08-redteam/pre-publication-checklist.md`): open lines 11, 12, 13, 17, 18, 22, 23, 24, 26, 30, 35, 36, 37, 38; they gate what is public.

## Touches

- The message to The Bioneer, which only you send
- Its Draft: `drafts/messages/outreach/creator-the-bioneer.md`, in gr0wthlab's workspace

## Evidence

- Angle P03, Forgiveness: mechanic as fact: `projects/RepToday/gtm/05-social-pmf/angles.md` line 25
- Sourced pain: Pain 2, streak relief: "Then after 200 days, I lost my streak and... breathed a sigh of relief" - https://hn.algolia.com/api/v1/items/38919053: `projects/RepToday/gtm/05-social-pmf/angles.md` line 25
- The Bioneer, and what a message to a creator may offer: `projects/RepToday/gtm/06-channels/channel-plan.md`

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
