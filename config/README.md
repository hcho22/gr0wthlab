# config

Configuration the Marketing Engineer reads but cannot write (Guardrail G8).

- [`products.json`](products.json): the Product registry - each Product's status, gate, and the read-only locations of its repository and Go-To-Market Package.
  It records where strategy lives, never the strategy itself.
  It also says where RepToday's anonymous Waitlist view is, once its build lands, and how the run counts it, including the good-Fit definition the Founder approves.
- [`run.json`](run.json): how each run works around the agent - its task definition, weekly schedule, the outputs and sources its run report accounts for, the records step that saves `workspace/` and `ledger/` to `main`, and the prices behind its approximate cost.
- [`guardrails/`](guardrails/): Guardrail configuration.
