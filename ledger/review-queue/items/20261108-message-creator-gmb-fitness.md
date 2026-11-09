---
exchange: 8
id: 20261108-message-creator-gmb-fitness
kind: message
product: RepToday
---

# Approve message to GMB Fitness: Early access to Rep Today

## Draft

A message for you to send to GMB Fitness, in your own name; gr0wthlab sends nothing and holds no address.
It offers early access and asks for nothing: no sponsorship, no post, no reply owed.
One follow-up may be offered 7 days after you record this message as sent on the sitting page, only while no reply is recorded, and after it nothing more. Approving this item approves that waiting period; to set another, give it when you record the message as sent.
If GMB Fitness ever posts about RepToday after receiving early access, that is a material connection they must disclose.

**Message** (34 words)

> I'm the founder of Rep Today, a workout app. The Ready screen asks the workout engine to generate a workout for the day. I can offer early access. No reply or promotion is expected.

**Notes for you, never sent**

> The channel plan's cited fit is no-equipment training for busy adults. The Founder rejected the earlier message as unnecessary; this version makes the offer optional and asks for no promotion or reply. Check whether outreach to GMB Fitness still makes sense before sending.

**Claims, checked against RepToday `main` at `58f6dd4`**

- The Ready screen asks the workout engine to generate a workout using the selected duration, user profile, recent logs, session policy, and requested variation. `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:481-487` shows `let generated = try await workoutEngine.generateWorkout( requestedMinutes: requested, user: user, recentLogs: recentLogs, sessionPolicy: policy, variation: requestedVariation )`
Only the claims listed here were checked; anything else it says the app does is yours to judge.

**Checks**

- Brand lint (`brand-rules.json`, from Mandu) on the message: passed.
- No sponsorship ask the brand rules list: checked.
- No email address: checked.
- Pre-publication checklist (`projects/RepToday/gtm/08-redteam/pre-publication-checklist.md`): open lines 11, 12, 13, 17, 18, 22, 23, 24, 26, 30, 35, 36, 37, 38; they gate what is public.

## Touches

- The message to GMB Fitness, which only you send
- Its Draft: `drafts/messages/outreach/creator-gmb-fitness.md`, in gr0wthlab's workspace

## Evidence

- Angle P03, Forgiveness: mechanic as fact: `projects/RepToday/gtm/05-social-pmf/angles.md` line 25
- Sourced pain: Pain 2, streak relief: "Then after 200 days, I lost my streak and... breathed a sigh of relief" - https://hn.algolia.com/api/v1/items/38919053: `projects/RepToday/gtm/05-social-pmf/angles.md` line 25
- GMB Fitness, and what a message to a creator may offer: `projects/RepToday/gtm/06-channels/channel-plan.md`

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
