---
draft: post
product: RepToday
window: 1
day: 5
angle: P11
---

# Airplane-mode demo

## Hook

Airplane mode on. The session still builds.

## Beats

### Beat 1 (hook): 0-3s

- Visual action: In one continuous real-device recording, open Control Center and turn airplane mode on.
- Spoken line: none
- On-screen text: Airplane mode on. The session still builds.

### Beat 2: 3-9s

- Visual action: Return to the app and open its home screen to the ready session, with no cuts.
- Spoken line: none
- On-screen text: none

### Beat 3: 9-12s

- Visual action: Hold on the generated session with airplane mode still on.
- Spoken line: none
- On-screen text: none

## TikTok

### Caption

Airplane mode on. The session still builds.
A continuous screen recording shows airplane mode enabled before the session appears. Not released yet.

### Hashtags

#RepToday

### Alt text

A phone switches on airplane mode, then shows a ready workout session.

## YouTube Shorts

### Title

Airplane mode on. The session still builds.

### Description

Airplane mode on. The session still builds.
A continuous screen recording shows airplane mode enabled before the session appears. Not released yet.

### Hashtags

#RepToday

### Alt text

A phone switches on airplane mode, then shows a ready workout session.

## Claims

- Claim: The app generates a ready session while the phone is offline.
  Code: `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:422-435`
  Shows: `let generated = try await workoutEngine.generateWorkout(`
