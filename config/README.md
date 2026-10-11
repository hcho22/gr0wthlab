# config

Configuration the Marketing Engineer reads but cannot write (Guardrail G8).

- [`products.json`](products.json): the Product registry - each Product's status, gate, and the read-only locations of its repository and Go-To-Market Package.
  It records where strategy lives, never the strategy itself.
  It also says where RepToday's anonymous Waitlist view is, once its build lands, and how the run counts it, including the good-Fit definition the Founder approves.
  It names which package file plays each part in the post-Draft checks (`post_drafts`), each one of the package sources every run snapshots.
  It names the thesis folder every Beta Cohort invitation cites, the brand rules its lint reads, and the cohort's size (`beta_recruiting`); a recruiting Draft may cite only the package sources that `beta-recruiting` needs.
- [`run.json`](run.json): how each run works around the agent - its task definition, weekly schedule, the 14-day window (its first sitting, which day 1 follows, and its posting slot, set only by the Founder), the date the Waitlist went live (unset until a reviewed change sets it; nothing is publishable before), how many Waitlist entries one Beta Cohort invitation batch offers (the Founder's call), the outputs and sources its run report accounts for, the records step that saves `workspace/` and `ledger/` to `main`, and the prices behind its approximate cost.
- [`platforms.json`](platforms.json): platform facts the post-Draft lint checks - each test platform's Draft fields, character limits, and hashtag limits.
  Facts about the platforms, not strategy; the brand rules themselves are read from Mandu.
- [`guardrails/`](guardrails/): Guardrail configuration.
