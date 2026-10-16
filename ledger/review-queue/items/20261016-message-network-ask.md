---
exchange: 8
id: 20261016-message-network-ask
kind: message
product: RepToday
---

# Approve personal-network ask: A personal note about Rep Today

## Draft

A message for you to send, in your own name, to people in your own network who fit; you choose who.
It carries the personal-network Source link `reptoday.app/network`, so each sign-up counts under that Source.
Do not send it until the RepToday Waitlist is live: the link does not work before then.

**Message** (50 words)

> I made Rep Today for people who want movement to fit the life they already have. When the Ready screen loads, it generates a workout for that day.
>
> Rep Today gives people who want movement to fit the life they already have a workout generated when the app opens: reptoday.app/network

**Notes for you, never sent**

> For people in the desk-bound 30s-40s profile. The link is the personal-network Source.

**Claims, checked against RepToday `main` at `8455108`**

- When the Ready screen loads, Rep Today generates a workout for that day. `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:197` shows `try await generate(user: user)`
Only the claims listed here were checked; anything else it says the app does is yours to judge.

**Checks**

- Brand lint (`brand-rules.json`, from Mandu) on the message: passed; rule types still waiting for their lists in Mandu, so yours to judge: stock phrases, capped words per paragraph, long sentences (warning), invented proof, fake scarcity, allowed phrases, loss framing.
- The Source link is `reptoday.app/network`, as `src/dispatches/reptoday-waitlist.md` defines it, and there is no other link: checked.
- No email address: checked.
- Pre-publication checklist (`projects/RepToday/gtm/08-redteam/pre-publication-checklist.md`): open lines 9, 10, 11, 12, 13, 17, 18, 22, 23, 24, 26, 30, 31, 35, 36, 37, 38; they gate what is public.

## Touches

- The personal-network ask, which only you send
- Its Draft: `drafts/messages/outreach/network-ask.md`, in gr0wthlab's workspace

## Evidence

- Angle P03, Forgiveness: mechanic as fact: `projects/RepToday/gtm/05-social-pmf/angles.md` line 25
- Sourced pain: Pain 2, streak relief: "Then after 200 days, I lost my streak and... breathed a sigh of relief" - https://hn.algolia.com/api/v1/items/38919053: `projects/RepToday/gtm/05-social-pmf/angles.md` line 25
- The personal-network Source link: `src/dispatches/reptoday-waitlist.md`
- The personal-network ask and its framing: `projects/RepToday/gtm/06-channels/channel-plan.md`

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
