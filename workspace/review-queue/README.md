# Review Queue

Items awaiting the Founder's decision: posts, messages, package-change proposals, Dispatch requests, Weekly Read decisions, and notices.
The format, and what Mandu writes back: [the Mandu exchange](../../docs/mandu-exchange.md).

- `incoming/`: where the agent writes new items during a run; the launcher checks them, publishes the valid ones, sets the rest aside, and empties it.
  A post or a message never goes here: the launcher queues each from a Draft in [`drafts/`](../drafts/README.md) that passes its checks, and sets aside any post or message written here.

The published Review Queue (`queue.json`, each item, and what was set aside) is in [`ledger/review-queue/`](../../ledger/README.md), which only the launcher writes and Mandu reads.
