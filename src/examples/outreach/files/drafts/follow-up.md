---
draft: message
product: RepToday
purpose: creator-follow-up
to: slow-strength
angle: P03
offer: early-access
---

# One last note

## Message

Hello again. I wrote two weeks ago about Rep Today, a small workout app for people who lost their routine.
The offer of early access stands, with nothing asked in return, and I will not write again.

## Notes

none

## Claims

- Claim: A missed day lowers the score, and nothing resets it to zero.
  Code: `Engine/ConsistencyScore.swift:6-7`
  Shows: `value = max(floorValue, value - missPenalty)`
