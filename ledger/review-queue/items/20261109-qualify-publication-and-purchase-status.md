---
exchange: 8
id: 20261109-qualify-publication-and-purchase-status
kind: package-change-proposal
product: RepToday
new_angle: no
supersedes: 20261109-qualify-purchase-and-deployment-status
---

# Approve package change: qualify publication and purchase status

## Proposal

The launch checklist and recap say nothing in the package is published, deployed, or purchased, while the current record says `reptoday.app` is registered and serves the privacy policy. In `02-marketing-launch-checklist_260807.md`, replace “Nothing there is published, deployed, or purchased.” with: “The landing site is not deployed; `reptoday.app` is registered and serves the hosted privacy policy at `reptoday.app/privacy`.” In `gtm/recap.html`, replace “Everything here is local and static: nothing is published, deployed, posted, or purchased.” with: “The landing site is not deployed. The `reptoday.app` domain is registered and its privacy policy is hosted separately at `reptoday.app/privacy`.” Also replace “Nothing is published or spent: no post is live, no ad account exists, no domain was purchased, no dollar moved.” with: “No post is live, no ad account exists, and no dollar has moved. The `reptoday.app` domain is registered; the landing site is not deployed.”

## Touches

- `projects/RepToday/02-marketing-launch-checklist_260807.md`
- `projects/RepToday/gtm/recap.html`

## Evidence

- The checklist's source-of-truth note says nothing was published, deployed, or purchased: `projects/RepToday/02-marketing-launch-checklist_260807.md` line 4
- The recap repeats that claim: `projects/RepToday/gtm/recap.html` line 83
- The recap also says no domain was purchased: `projects/RepToday/gtm/recap.html` line 250
- The domain is registered and the privacy policy is hosted: `projects/RepToday/02-marketing-launch-checklist_260807.md` line 26
- The recap distinguishes the hosted waitlist form from the landing site, which is not published: `projects/RepToday/gtm/recap.html` line 253

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
