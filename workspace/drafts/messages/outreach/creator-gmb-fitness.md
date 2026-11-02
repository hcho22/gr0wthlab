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

I'm the founder of Rep Today. When the Ready screen loads, it generates a workout for that day. I can offer early access to the free product, with no promotion expected.

## Notes

The channel plan names GMB Fitness for its no-equipment and busy-adult positioning. The Founder rejected the earlier message because there is no need to contact GMB Fitness. Do not send this unless the Founder decides to reopen outreach.

## Claims

- Claim: The Ready screen's generation function asks the workout engine for a workout using the selected duration, user profile, recent logs, and session policy.
  Code: `ios/RepToday/RepToday/ViewModels/ReadyViewModel.swift:431-436`
  Shows: `let generated = try await workoutEngine.generateWorkout(
            requestedMinutes: requested,
            user: user,
            recentLogs: recentLogs,
            sessionPolicy: policy
        )`
