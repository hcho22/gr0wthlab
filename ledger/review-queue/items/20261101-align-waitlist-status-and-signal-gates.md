---
exchange: 8
id: 20261101-align-waitlist-status-and-signal-gates
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Approve the waitlist status and signal-gate corrections

## Proposal

The waitlist is live since 2026-10-21, and both landing-page variants have a live Kit signup form, but the launch checklist still says the waitlist does not exist and a saved launch asset says there is no waitlist. In `02-marketing-launch-checklist_260807.md`, replace the status summary's “Remaining Gate 0: stand up the waitlist” with “The waitlist is live; per-source/UTM tagging remains a Kit-dashboard follow-up,” and replace the unchecked “Stand up the waitlist” item with the recorded completion and remaining tagging follow-up. In `gtm/02-brand/gate-test-asset.html`, replace “No waitlist, nothing to reserve” with a short accurate statement that the waitlist is live and the landing page is not yet published. In `gtm/06-channels/channel-plan.md` and `gtm/07-thesis/investment-thesis.md`, replace the claim that waitlist-tap quantities are excluded only until a waitlist exists with: “No waitlist-tap quantity enters this criterion while profile-link taps remain unreliable at zero followers.” This preserves the existing measurement limit while removing the expired waitlist-existence condition.

## Touches

- `02-marketing-launch-checklist_260807.md`
- `gtm/02-brand/gate-test-asset.html`
- `gtm/06-channels/channel-plan.md`
- `gtm/07-thesis/investment-thesis.md`

## Evidence

- Waitlist live since 2026-10-21: `/Users/hcho/Mandu/projects/RepToday/gtm/05-social-pmf/angles.md` line 17
- Both landing-page variants contain a live Kit waitlist form: `/Users/hcho/Mandu/projects/RepToday/gtm/08-redteam/pre-publication-checklist.md` line 25
- Checklist still says the waitlist does not exist and remains to be stood up: `/Users/hcho/Mandu/projects/RepToday/02-marketing-launch-checklist_260807.md` lines 7 and 27
- Saved asset says “No waitlist”: `/Users/hcho/Mandu/projects/RepToday/gtm/02-brand/gate-test-asset.html` line 115
- Channel plan makes waitlist-tap exclusion conditional only on the waitlist not existing: `/Users/hcho/Mandu/projects/RepToday/gtm/06-channels/channel-plan.md` lines 52 and 57
- Thesis uses the same expired waitlist-existence gate: `/Users/hcho/Mandu/projects/RepToday/gtm/07-thesis/investment-thesis.md` line 219
- Profile-link taps remain unreliable at zero followers: `/Users/hcho/Mandu/projects/RepToday/gtm/05-social-pmf/angles.md` line 15

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
