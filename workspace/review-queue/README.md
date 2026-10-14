# Review Queue

Items awaiting the Founder's decision.
Their kinds and format, and the records the Founder makes of each decision: [the Mandu exchange](../../docs/mandu-exchange.md).
Nothing in this area is ever a decision of the Founder's: the Founder decides on the sitting page, which writes to `ledger/founder/`, and the launcher reads decisions from there and from nowhere else.

- `incoming/`: where the agent writes new items during a run; the launcher checks them, publishes the valid ones, sets the rest aside, and empties it.
  A post or a message never goes here: the launcher queues each from a Draft in [`drafts/`](../drafts/README.md) that passes its checks, and sets aside any post or message written here.

- `angles/`: where the agent proposes a new Angle or Hook, citing the Listening quotes it rests on.
  The launcher queues one as a package-change proposal only if every source it cites is kept Listening Evidence, and discards any other with a note.
  A package-change proposal in `incoming/` declares `new_angle`: one that declares `yes` is set aside unless its Evidence names the record of a quote the launcher already keeps.
  Neither is kept: a proposal discarded from `angles/`, like every file set aside from `incoming/`, is removed and leaves only its file name and the launcher's reasons.
  A message never goes in `incoming/` either: the launcher queues it from a Draft in [`drafts/messages/`](../drafts/README.md).

The published Review Queue (`queue.json`, each item, and what was set aside) is in [`ledger/review-queue/`](../../ledger/README.md), which only the launcher writes; the sitting page shows it to the Founder, and Mandu may read it.
