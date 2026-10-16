---
exchange: 8
id: 20261016-prelaunch-paid-spend-conflict
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Resolve the pre-launch paid spend conflict

## Proposal

The channel plan’s verdict says “Run zero paid spend pre-launch,” but its budget section also permits an optional $50-100 pre-launch web-traffic test. The marketing-agent build spec says the no-spend guardrail is absolute. These directions cannot all govern the same pre-launch period. Change neither decision here; the Founder must decide whether pre-launch spend is prohibited or whether the one web-objective test is an exception. If the exception is chosen, state its conditions in the channel verdict and make the build spec’s boundary match. If no exception is chosen, remove the proposed smoke test from the budget list.

## Touches

- `gtm/06-channels/channel-plan.md`
- `gtm/09-extras/marketing-agent/BUILD-SPEC.md`

## Evidence

- Zero pre-launch spend verdict: `/Users/hcho/Mandu/projects/RepToday/gtm/06-channels/channel-plan.md` line 26
- Proposed $50-100 web-objective test: `/Users/hcho/Mandu/projects/RepToday/gtm/06-channels/channel-plan.md` line 105
- Absolute no-spend guardrail: `/Users/hcho/Mandu/projects/RepToday/gtm/09-extras/marketing-agent/BUILD-SPEC.md` line 5

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
