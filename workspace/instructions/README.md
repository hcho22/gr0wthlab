# Instructions changes

The Marketing Engineer's Instructions area (Guardrail G1): where the agent proposes a change to its own Instructions, never where they are kept.
The Instructions in force are in [`ledger/instructions/`](../../ledger/instructions/README.md), which the agent can read and never write.

Only the session that codes the Founder's rejection reasons may leave a file here: `<workflow>.md`, the whole proposed text of that workflow's Instructions, under front matter that names the workflow, the execution-coded rejection reasons it answers, and a one-line summary.
Once the last session has ended, the launcher checks it, re-runs that workflow's example set with the text in force and with the proposed text, and writes the proposed text into `ledger/instructions/` only when no example got worse ([ADR 0003](../../docs/adr/0003-instructions-change-only-through-their-example-set.md)).
It removes the file either way.
Anything else written here, and anything any other session writes here, is put back as it was after that session.
