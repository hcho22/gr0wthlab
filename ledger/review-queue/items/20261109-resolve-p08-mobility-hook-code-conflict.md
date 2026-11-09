---
exchange: 8
id: 20261109-resolve-p08-mobility-hook-code-conflict
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Resolve P08's mobility hook against the shipped session structure

## Proposal

P08 says that half a session can be mobility and describes mobility blocks as co-equal with strength. The Product code at the fixed commit says strength is the primary pillar, mobility is limited to warm-up and cooldown bookends, and the mobility training block is retired. Decide which side should change: revise the package's P08 claim and format to fit the shipped session structure, or change the Product so sessions can contain the mobility training blocks P08 describes. The current Draft preserves the frozen Hook and is blocked because the fixed code does not support it.

## Touches

- `projects/RepToday/gtm/05-social-pmf/angles.md`

## Evidence

- P08's frozen Hook and format describe half-session mobility and mobility blocks co-equal with strength: `projects/RepToday/gtm/05-social-pmf/angles.md` line 30
- The Product code says strength is primary; mobility is warm-up and cooldown only, never a training block, and its training block is retired: `ios/RepToday/RepToday/Models/Enums.swift` lines 23-26 at commit `58f6dd48629fd237602bac30230a6943d2e2e002`

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
