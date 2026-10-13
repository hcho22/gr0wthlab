# Evidence

What the Marketing Engineer has gathered or observed, each with its source and the date gathered: Listening quotes, post results, and the Founder's rejection reasons.
Evidence never holds an email address, and it can support a package-change proposal but never changes the Go-To-Market Package by itself.
Formats: US-ME11, US-ME13, US-ME16.

- `listening/<document id>.md`: a quote record the agent writes in a run's Listening session, in the format of that session's task definition ([`src/instructions/weekly-run/listening.md`](../../src/instructions/weekly-run/listening.md)).
  The launcher keeps it only if its quote stands word for word in the text it fetched from that link, moves it into `ledger/evidence/listening/quotes/`, and empties this folder; a record it refuses is removed, and the run report names it with the reasons.
  What it fetched is working data in `ledger/working/`, removed when the run ends: a quote in a kept record is all the launcher keeps of it as Evidence.
- `learning/<item id>.md`: the code the agent proposes for one rejection reason; the launcher checks it against its fixed code list and writes it into that decision's Evidence.

The launcher's own Evidence (each run's package snapshot, the Founder's decisions, the sittings taken in from Mandu, the Waitlist counts, the Listening quotes it kept, and, once a Beta Build is approved, the invitation batches by entry identifier and the counts the Founder reports) is in [`ledger/evidence/`](../../ledger/README.md), which the agent can read and never write.
