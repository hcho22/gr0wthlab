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

I'm the founder of Rep Today. It builds a complete workout on your device from your selected time and training history. I can offer story material about how its workout engine was built, with no expectation of coverage or a reply.

## Notes

The channel plan identifies The Bioneer as a video essay channel and suggests the engine story as relevant material. The Founder rejected an earlier message as unnecessary. Check whether this outreach still makes sense before sending.

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
