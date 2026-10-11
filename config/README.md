# config

Configuration the Marketing Engineer reads but cannot write (Guardrail G8).

- [`products.json`](products.json): the Product registry - each Product's status, gate, and the read-only locations of its repository and Go-To-Market Package.
  It records where strategy lives, never the strategy itself.
  It also says where RepToday's anonymous Waitlist view is, once its build lands, and how the run counts it, including the good-Fit definition the Founder approves.
  It names which package file plays each part in the post-Draft checks (`post_drafts`), which one defines Fit for Listening (`listening`), and which one names the outreach (`outreach`), each one of the package sources every run snapshots.
- [`run.json`](run.json): how each run works around the agent - its task definition, weekly schedule, the 14-day window (its first sitting, which day 1 follows, and its posting slot, set only by the Founder), the date the Waitlist went live (unset until a reviewed change sets it; nothing is publishable before), the outreach messages it prepares (the Source whose link the personal-network ask carries, the wait before a follow-up, and a message's word limit), the outputs and sources its run report accounts for, the records step that saves `workspace/` and `ledger/` to `main`, and the prices behind its approximate cost.
- [`platforms.json`](platforms.json): platform facts the post-Draft lint checks - each test platform's Draft fields, character limits, and hashtag limits.
  Facts about the platforms, not strategy; the brand rules themselves are read from Mandu.
- [`sources.json`](sources.json): the fixed list of sources the launcher reads over the network at each run - the three subreddits' newest threads and their rules, App Store reviews, and the three creators' own feeds.
  Addresses only, which are platform facts; which competitors' reviews are read comes from the package's research in Mandu.
  Every address is on a host listed in [`guardrails/fetch.json`](guardrails/fetch.json), and is read only where that host's `robots.txt` allows it.
- [`guardrails/`](guardrails/): Guardrail configuration.
