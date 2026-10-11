# Evidence

What the Marketing Engineer has gathered or observed, each with its source and the date gathered: Listening quotes, post results, and the Founder's rejection reasons.
Evidence never holds an email address, and it can support a package-change proposal but never changes the Go-To-Market Package by itself.
Formats: US-ME11, US-ME13, US-ME16.

- `listening/<document id>.md`: a quote record the agent writes during a run, in the format of the run's task definition ([`src/instructions/weekly-run.md`](../../src/instructions/weekly-run.md)).
  The launcher keeps it only if its quote stands word for word in the text it fetched from that link, moves it into `ledger/evidence/listening/quotes/`, and empties this folder; a record it refuses is set aside and named in the run report.
- `learning/<item id>.md`: the code the agent proposes for one rejection reason; the launcher checks it against its fixed code list and writes it into that decision's Evidence.

The launcher's own Evidence (each run's package snapshot, the Founder's decisions, the sittings taken in from Mandu, the Waitlist counts, what it fetched over the network, and the Listening quotes it kept) is in [`ledger/evidence/`](../../ledger/README.md), which the agent can read and never write.
