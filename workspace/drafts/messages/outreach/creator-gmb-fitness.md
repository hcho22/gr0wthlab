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

I'm the founder of Rep Today. It builds a workout around the time you have and your recent training. Your focus on no-equipment training for busy adults is why I'm reaching out. I can offer early access, with no request to promote it.

## Notes

The channel plan names GMB Fitness for no-equipment training and busy-adult positioning. Confirm a working early-access route is ready before sending.

## Claims

- Claim: Rep Today builds a complete workout on the device using the requested time and recent training history.
  Code: `ios/RepToday/RepToday/Services/Engine/OnDeviceWorkoutEngine.swift:39-48`
  Shows: `let library = try await exerciseService.exercises()
        return SessionAssembly.assemble(
            requestedMinutes: requestedMinutes,
            user: user,
            library: library,
            recentLogs: recentLogs,
            sessionPolicy: sessionPolicy,
            variation: variation,
            asOf: now()
        )`
