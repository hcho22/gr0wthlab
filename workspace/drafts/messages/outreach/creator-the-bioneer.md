---
draft: message
product: RepToday
purpose: creator
to: the-bioneer
angle: P03
offer: story-material
---

# A story about ready workouts

## Message

I'm the founder of Rep Today. When the Ready screen loads, it generates a workout for that day. I can offer story material about how the workout engine was built.

## Notes

The channel plan identifies The Bioneer as a video essay channel and recommends pitching the workout engine as story material. Check that this remains useful before sending.

## Claims

- Claim: The Ready screen's generation function asks the workout engine for a workout using the selected duration, user profile, recent logs, and session policy.
  Code: `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:431-436`
  Shows: `let generated = try await workoutEngine.generateWorkout(
            requestedMinutes: requested,
            user: user,
            recentLogs: recentLogs,
            sessionPolicy: policy
        )`
