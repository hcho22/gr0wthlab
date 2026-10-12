---
draft: message
product: RepToday
purpose: network-ask
to: network
angle: P03
---

# An app I have been building

## Message

I have been building Rep Today for people who want movement to fit the life they already have.
A missed day lowers a score a little, and nothing ever resets it.
Rep Today is a workout app for people whose routine fell apart: reptoday.app/network

## Notes

none

## Claims

- Claim: A missed day lowers the score, and nothing resets it to zero.
  Code: `Engine/ConsistencyScore.swift:6-7`
  Shows: `value = max(floorValue, value - missPenalty)`
