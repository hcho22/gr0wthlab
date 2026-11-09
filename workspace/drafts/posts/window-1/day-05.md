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

- Visual action: The real device shows Airplane Mode enabled in Control Center, then the recording returns to the app.
- Spoken line: none
- On-screen text: Airplane mode on. The session still builds.

### Beat 2: 3-12s

- Visual action: In the same uninterrupted screen recording, the app opens to the ready session and its workout details.
- Spoken line: none
- On-screen text: none

## YouTube Shorts

### Title

Airplane mode on. The session still builds.

### Description

Airplane mode on. The session still builds.

The app opens to a ready session while Airplane Mode is on.
Not released yet.
Join the waitlist: reptoday.app/youtube

### Hashtags

#offlineworkout

### Alt text

A phone shows Airplane Mode enabled, then opens Rep Today to a ready workout session.

## TikTok

### Caption

Airplane mode on. The session still builds.

The app opens to a ready session while Airplane Mode is on.
Not released yet.
Join the waitlist: reptoday.app/tiktok

### Hashtags

#offlineworkout

### Alt text

A phone shows Airplane Mode enabled, then opens Rep Today to a ready workout session.

## Claims

- Claim: The session builds while Airplane Mode is on.
  Code: `ios/RepToday/RepToday/Services/Engine/OnDeviceWorkoutEngine.swift:3-10`
  Shows: `/// The production workout engine: the one `WorkoutEngineProtocol` conformer, wired by both
  /// `ServiceContainer.live(...)` (the shipped app) and `ServiceContainer.mock()` (previews and tests).
  ///
  /// It is a thin adapter over the deterministic pipeline, not a stand-in for one. Generation runs
  /// `SessionAssembly.assemble` and a swap runs `ExerciseSwap.swap`, both pure on-device Swift over the
  /// bundled, load-validated exercise library. Nothing here reaches the network, a server, or an LLM,
  /// so a session builds the same in airplane mode as online - `OfflineSessionGenerationTests` guards`
