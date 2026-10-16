---
exchange: 8
id: 20261016-pmf-hook-qa-conflicts
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Resolve PMF hooks that conflict with the brand QA rule

## Proposal

`BUILD-SPEC.md` and `brand-rules.json` require hooks of 12 words or fewer and prohibit “streak” in hooks. The frozen PMF bank includes longer hooks for P02, P07, P09, P14, and P16; P09 also uses the prohibited word. Keep those hooks unchanged in this proposal. The Founder must decide whether the frozen PMF hooks are exempt from this agent lint or should be replaced in later proposals; changing any frozen hook creates a new Angle and requires a kept quote record as sourced pain. No such record is named in this run’s brief. If the linter is meant to bind these hooks, update the PMF plan’s pre-publication QA step to surface these five exceptions for Founder review before they are used.

## Touches

- `gtm/05-social-pmf/angles.md`
- `gtm/05-social-pmf/creative-log.json`
- `gtm/05-social-pmf/cadence-14-day.md`
- `gtm/09-extras/marketing-agent/BUILD-SPEC.md`
- `gtm/09-extras/marketing-agent/brand-rules.json`

## Evidence

- The PMF bank’s hooks, including P02, P07, P09, P14, and P16: `/Users/hcho/Mandu/projects/RepToday/gtm/05-social-pmf/angles.md` lines 24, 29, 31, 36, 38
- The same hooks are recorded in the creative log, for example P09: `/Users/hcho/Mandu/projects/RepToday/gtm/05-social-pmf/creative-log.json` line 139
- The hook length requirement: `/Users/hcho/Mandu/projects/RepToday/gtm/09-extras/marketing-agent/BUILD-SPEC.md` line 51
- The machine rule and prohibited word: `/Users/hcho/Mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json` lines 3-10

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
