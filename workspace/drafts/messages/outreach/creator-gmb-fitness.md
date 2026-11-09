---
draft: message
product: RepToday
purpose: creator
to: gmb-fitness
angle: P03
offer: early-access
---

# Early access to Rep Today

## Message

I'm the founder of Rep Today, a workout app. The Ready screen asks the workout engine to generate a workout for the day. I can offer early access. No reply or promotion is expected.

## Notes

The channel plan's cited fit is no-equipment training for busy adults. The Founder rejected the earlier message as unnecessary; this version makes the offer optional and asks for no promotion or reply. Check whether outreach to GMB Fitness still makes sense before sending.

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
