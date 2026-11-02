---
exchange: 8
id: 20261101-substantiate-p11-airplane-mode-hook
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Resolve the P11 airplane-mode claim against the Product code

## Proposal

The P11 Hook says “Airplane mode on. The session still builds.” The pinned Product code exposes workout generation through `WorkoutEngineProtocol`, and its only conforming implementation at this commit is `MockWorkoutEngine`; those sources do not establish that the shipped app builds a session in airplane mode. The day-5 Draft therefore keeps the frozen Hook and is blocked with the claim unsupported. Resolve this by adding Product implementation and verification that substantiate the airplane-mode behavior, or by changing the P11 Hook and its Angle in a later package decision if the behavior is not supported. This proposal supplies no replacement Hook; the Founder decides which side changes.

## Touches

- `projects/RepToday/gtm/05-social-pmf/angles.md`

## Evidence

- P11 frozen Hook and offline Format: `/Users/hcho/Mandu/projects/RepToday/gtm/05-social-pmf/angles.md` line 33
- Product generation is an injected protocol; it does not state offline behavior: `/Users/hcho/Developer/FM_Private/firstmate-private/projects/RepToday/ios/RepToday/RepToday/Services/Protocols/ServiceProtocols.swift` lines 33-44
- The only implementation found at the brief's pinned commit is a mock: `/Users/hcho/Developer/FM_Private/firstmate-private/projects/RepToday/ios/RepToday/RepToday/Services/Mock/MockServices.swift` lines 13-47

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
