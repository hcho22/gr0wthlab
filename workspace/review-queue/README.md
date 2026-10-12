# Review Queue

Items awaiting the Founder's decision: posts, messages, package-change proposals, Dispatch requests, Weekly Read decisions, and notices.
The format, and what Mandu writes back: [the Mandu exchange](../../docs/mandu-exchange.md).

- `incoming/`: where the agent writes new items during a run; the launcher checks them, publishes the valid ones, sets the rest aside, and empties it.
  A post or a message never goes here: the launcher queues each from a Draft in [`drafts/`](../drafts/README.md) that passes its checks, and sets aside any post or message written here.

- `angles/`: where the agent proposes a new Angle or Hook, citing the Listening quotes it rests on.
  The launcher queues one as a package-change proposal only if every source it cites is kept Listening Evidence, and discards any other with a note.
  A package-change proposal in `incoming/` declares `new_angle`: one that declares `yes` is set aside unless its Evidence names the record of a quote the launcher already keeps.
  What is kept of the two differs today: a proposal discarded from `angles/` is removed and leaves only its file name and the launcher's reasons, while one set aside from `incoming/`, like every file set aside there, is copied whole to `ledger/review-queue/set-aside/<run id>/`.
  A message never goes in `incoming/` either: the launcher queues it from a Draft in [`drafts/messages/`](../drafts/README.md).

The published Review Queue (`queue.json`, each item, and what was set aside) is in [`ledger/review-queue/`](../../ledger/README.md), which only the launcher writes and Mandu reads.
