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

I'm the founder of Rep Today. It builds a complete workout on your device from your selected time and training history. I can offer early access, with no expectation of a reply or promotion.

## Notes

The channel plan cites GMB Fitness for no-equipment training and busy-adult positioning. The Founder rejected an earlier message as unnecessary. Check whether this outreach still makes sense before sending.

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
