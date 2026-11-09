---
draft: message
product: RepToday
purpose: creator
to: hybrid-calisthenics
angle: P03
offer: early-access
---

# Early access to Rep Today

## Message

I'm the founder of Rep Today, a workout app. The Ready screen asks the workout engine to generate a workout for the day. I can offer early access to the free product. No reply or promotion is expected.

## Notes

The channel plan describes a shame-free philosophy and anti-selling stance, so this offers early access to the free product only. The Founder rejected the earlier message as unnecessary; this version asks for no promotion or reply. Check whether outreach still makes sense before sending.

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
