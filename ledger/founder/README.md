# ledger/founder

The Founder's own records: every decision on a Review Queue item, and what the Founder did.
Only `src/bin/gr0wthlab sitting` writes here, on the Founder's act on the page it serves; a run reads these records and never writes one, and the sandboxed agent can read them and can never write them ([ADR 0002](../../docs/adr/0002-the-founder-decides-in-gr0wthlab.md)).
Each run's records step commits this folder with the rest of `ledger/`.

- `decisions/<item id>.json`: the Founder's approval or rejection of one item, with the reason for a rejection.
- `sittings/<date>.json`: how long a sitting took.
- `beta-builds/<Product>.json`: the Founder's word that a Beta Build passed Apple's review, and whether recruiting is open.
- `beta-reports/<Product>-<date>.json`: the three Beta Cohort counts the Founder gave on that date.
- `outreach/<item id>.json`: when the Founder sent an approved message, and when a reply came.

Never edit a file here by hand: a record that does not follow its format is not a record, and the next run reports it and takes nothing from it.
The five folders must stay real folders; the `.gitkeep` in each keeps it in a fresh clone, and a run refuses to start without them.
The formats, and the rules for correcting a record: [the Mandu exchange](../../docs/mandu-exchange.md).
