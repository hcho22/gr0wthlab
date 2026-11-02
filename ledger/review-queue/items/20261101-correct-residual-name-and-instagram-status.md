---
exchange: 8
id: 20261101-correct-residual-name-and-instagram-status
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Approve the remaining name and Instagram status corrections

## Proposal

The launch checklist records that the USPTO search and App Store name reservation were completed on 2026-08-07 and that `@reptoday` was claimed on Instagram. Four saved assets still say the search and reservation never happened: replace those lines in `gtm/02-brand/gate-test-asset.html`, `gtm/02-brand/gate-test-asset-v2.html`, `gtm/10-instagram/carousel-5-a-floor-and-a-wall/slide-07.html`, and `gtm/10-instagram/carousel-8-9pm-problem/slide-07.html` with: “Pre-launch. A USPTO search was completed and the App Store name was reserved on 2026-08-07. This does not state that a trademark was registered or legally cleared.” In `gtm/10-instagram/README.md`, remove the claim that the checklist still leaves Instagram handle availability open; update its checklist row to say that the `@reptoday` handle was claimed on 2026-08-07 and that confirming the Instagram account is created and usable remains open. The package record does not establish whether that profile is active.

## Touches

- `gtm/02-brand/gate-test-asset.html`
- `gtm/02-brand/gate-test-asset-v2.html`
- `gtm/10-instagram/carousel-5-a-floor-and-a-wall/slide-07.html`
- `gtm/10-instagram/carousel-8-9pm-problem/slide-07.html`
- `gtm/10-instagram/README.md`

## Evidence

- The completed USPTO search and App Store name reservation: `/Users/hcho/Mandu/projects/RepToday/02-marketing-launch-checklist_260807.md` line 24
- The Instagram handle claim: `/Users/hcho/Mandu/projects/RepToday/02-marketing-launch-checklist_260807.md` line 25
- Saved assets still say neither search nor reservation happened: `/Users/hcho/Mandu/projects/RepToday/gtm/02-brand/gate-test-asset.html` line 127; `/Users/hcho/Mandu/projects/RepToday/gtm/02-brand/gate-test-asset-v2.html` line 95; `/Users/hcho/Mandu/projects/RepToday/gtm/10-instagram/carousel-5-a-floor-and-a-wall/slide-07.html` line 28; `/Users/hcho/Mandu/projects/RepToday/gtm/10-instagram/carousel-8-9pm-problem/slide-07.html` line 28
- The Instagram guide says handle availability remains open: `/Users/hcho/Mandu/projects/RepToday/gtm/10-instagram/README.md` lines 10-11 and 245

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
