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

I'm the founder of Rep Today. It builds a workout around the time you have and your recent training. The channel plan points to the workout engine as a story about deterministic design. I can offer story material, with no request for coverage.

## Notes

The channel plan identifies The Bioneer as a video essay channel and suggests the workout engine as story material. Have a concise explanation of the engine ready if you send this.

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
