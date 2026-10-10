---
draft: post
product: RepToday
window: 1
day: 3
angle: P03
pair: AB-2
leg: A
---

# Score dip demo

## Hook

Skip a day and the score dips. It never resets.

## Beats

### Beat 1 (hook): 0-3s

- Visual action: The history view with yesterday unmarked; the score ticks down a few points.
- Spoken line: none
- On-screen text: Skip a day and the score dips. It never resets.

### Beat 2: 3-9s

- Visual action: Scroll back through a month with three gaps; the line dips at each one and climbs again.
- Spoken line: none
- On-screen text: Three gaps this month. Still climbing.

### Beat 3: 9-12s

- Visual action: Open today's session and tap Start.
- Spoken line: none
- On-screen text: Real phone, real time.

## TikTok

### Caption

Skip a day and the score dips. It never resets.
This is the history view after three missed days this month, and the line dips at each gap, climbs back, and keeps going after every one of them.
Built by one person. Not released yet.

### Hashtags

#buildinpublic

### Alt text

Screen recording of a workout app's history view: each missed day lowers a consistency score a little, and the score climbs again after every gap.

## YouTube Shorts

### Title

Skip a day and the score dips. It never resets.

### Description

Skip a day and the score dips. It never resets.
This is the history view after three missed days this month, and the line dips at each gap, climbs back, and keeps going after every one of them.
Built by one person. Not released yet.

### Hashtags

#buildinpublic

### Alt text

Screen recording of a workout app's history view: each missed day lowers a consistency score a little, and the score climbs again after every gap.

## Claims

- Claim: A missed day lowers the score, and nothing resets it to zero.
  Code: `Engine/ConsistencyScore.swift:6-7`
  Shows: `value = max(floorValue, value - missPenalty)`
