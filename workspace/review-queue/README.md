# Review Queue

Items awaiting the Founder's decision: posts, messages, package-change proposals, Dispatch requests, Weekly Read decisions, and notices.
Mandu reads items from here and records the Founder's decisions in its own records; nothing here is a decision.
The format, and what Mandu writes back: [the Mandu exchange](../../docs/mandu-exchange.md).

- `queue.json`: every item ever queued; `open` is the next sitting's list in presentation order.
- `items/<id>.md`: each queued item, under an identifier that never changes.
- `incoming/`: where the agent writes new items during a run; the launcher checks and queues them, then empties it.
- `set-aside/<run id>/`: what the launcher refused to queue that run, kept for the record and named in that run's notice.

The launcher alone writes everything here except `incoming/`.
