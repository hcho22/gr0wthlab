---
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Approve package change: say that the 200-impression floor counts each platform's views

## Proposal

`read-the-results.md` sets a floor in impressions: "Any post under 200 impressions is unread, not failed."
The numbers `angles.md` lists as measurable at zero followers name views and no impressions on either platform, so the Weekly Read cannot tell which number the floor counts.
You decided on 2026-10-14 that the floor counts each platform's views for now, and every Weekly Read memo says so in one line.

Change line 15 of `projects/RepToday/gtm/05-social-pmf/read-the-results.md` from:

- Any post under 200 impressions is unread, not failed.

to:

- Any post under 200 impressions is unread, not failed; the floor counts each platform's views (TikTok Studio's video views, YouTube Studio's views).

To decide: whether views are the number you want the floor to count on each platform, and whether `angles.md` line 12 and `cadence-14-day.md` line 38, which state the same floor, should say it too.
Nothing else in the rules changes.

## Touches

- `projects/RepToday/gtm/05-social-pmf/read-the-results.md`

## Evidence

- The floor as written: `projects/RepToday/gtm/05-social-pmf/read-the-results.md` line 15
- What is measurable at zero followers names views and no impressions: `projects/RepToday/gtm/05-social-pmf/angles.md` line 14
- The Founder's decision of 2026-10-14 that the floor counts views: `docs/adr/0004-the-weekly-read-uses-no-youtube-connection.md`

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
