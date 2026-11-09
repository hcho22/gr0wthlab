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

I'm the founder of Rep Today, a workout app. The Ready screen asks the workout engine to generate a workout for the day. I can offer story material about how the engine was built. No coverage or reply is expected.

## Notes

The channel plan identifies The Bioneer as a video essay channel and suggests the engine story as relevant material. The Founder rejected the earlier message as unnecessary; this version asks for no coverage or reply. Check whether outreach still makes sense before sending.

## Claims

- Claim: The Ready screen asks the workout engine to generate a workout using the selected duration, user profile, recent logs, session policy, and requested variation.
  Code: `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:481-487`
  Shows: `let generated = try await workoutEngine.generateWorkout(
            requestedMinutes: requested,
            user: user,
            recentLogs: recentLogs,
            sessionPolicy: policy,
            variation: requestedVariation
        )`
