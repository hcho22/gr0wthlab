# workspace

The Marketing Engineer's only writable tree (Guardrail G1).
Every run writes here and nowhere else; the runtime enforces that boundary (US-ME02).
The launcher's own records, such as the published Review Queue and the run reports, are in [`ledger/`](../ledger/README.md), which a run can read and never write.

Each area below holds one kind of record.
Record formats are defined by the stories that first produce them, not here.
No reference copy of any Go-To-Market Package lives in this tree, and Instructions point to Mandu instead of restating package content.
A record (a Draft, proposal, Evidence, or memo) may quote only the specific package text it uses or proposes, citing its Mandu source.
