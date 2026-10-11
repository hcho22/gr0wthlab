# Review Queue

Items awaiting the Founder's decision: posts, messages, package-change proposals, Dispatch requests, Weekly Read decisions, and notices.
The format, and what Mandu writes back: [the Mandu exchange](../../docs/mandu-exchange.md).

- `incoming/`: where the agent writes new items during a run; the launcher checks them, publishes the valid ones, sets the rest aside, and empties it.
  A post never goes here: the launcher queues it from a Draft in [`drafts/posts/`](../drafts/README.md) that passes its checks, and sets aside any post written here.

- `angles/`: where the agent proposes a new Angle or Hook, citing the Listening quotes it rests on.
  The launcher queues one as a package-change proposal only if every source it cites is kept Listening Evidence, and discards any other with a note.
  A message never goes in `incoming/` either: the launcher queues it from a Draft in [`drafts/messages/`](../drafts/README.md).

The published Review Queue (`queue.json`, each item, and what was set aside) is in [`ledger/review-queue/`](../../ledger/README.md), which only the launcher writes and Mandu reads.
