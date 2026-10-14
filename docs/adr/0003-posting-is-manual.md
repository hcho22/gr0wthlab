# Posting is manual, with no scheduling service

The Founder posts each approved post himself, on TikTok and YouTube Shorts, at the window's fixed slot.
gr0wthlab connects to no scheduling service: it loads no draft into one and reads nothing back from one.

Decided by the Founder on 2026-10-11, in his words: "gr0wthlab - lets do manual for now."

## Why

The PRD planned a scheduling service that would receive each approved post as a draft at the fixed slot, wait for the Founder to confirm it, and let a run read back what was scheduled (US-ME03, US-ME10).
The Founder chose to post by hand for now, so no service is connected, and none needs a credential, a cost, or a spike.

## What follows

- Every public act stays the Founder's, as [ADR 0001](0001-evidence-and-drafts-only.md) says: approving a post on the sitting page approves its copy and its video, and the Founder posts it.
- Nothing reads back what was posted or when.
  Which posts went out comes only from what the Founder gives on the sitting page in a read week: the numbers of each post, read from TikTok Studio or YouTube Studio ([ADR 0004](0004-the-weekly-read-uses-no-youtube-connection.md)).
  A post he gives nothing for is not reported, never taken to be not posted.
- The run report lists the scheduling service as not used, by the Founder's choice of 2026-10-11, and never as a source that failed to connect.
- US-ME03 and US-ME10 stay open and unbuilt: their acceptance criteria are about a service, and none is connected.
  Guardrail G3, that a scheduling service can receive drafts only, holds because no service can receive anything.
- The fixed evening slot (FR-8) is the Founder's to keep when he posts; `slot` in `config/run.json` still says what it is.

## Considered Options

- **A scheduling service, as the PRD planned (US-ME03, US-ME10).**
  Not now: the Founder chose to post by hand.
- **Posting by hand.**
  Chosen, for now.
