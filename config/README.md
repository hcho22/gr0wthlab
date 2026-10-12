# config

Configuration the Marketing Engineer reads but cannot write (Guardrail G8).

- [`products.json`](products.json): the Product registry - each Product's status, gate, and the read-only locations of its repository and Go-To-Market Package.
  It records where strategy lives, never the strategy itself.
  It also says where RepToday's anonymous Waitlist view is, once its build lands, and how the run counts it, including the good-Fit definition the Founder approves.
  It names which package file plays each part in the post-Draft checks (`post_drafts`), which one defines Fit for Listening (`listening`), and which one names the outreach (`outreach`), each one of the package sources every run snapshots.
  It names the thesis folder every Beta Cohort invitation cites, the brand rules its lint reads, and the cohort's size (`beta_recruiting`); a recruiting Draft may cite only the package sources that `beta-recruiting` needs.
  It says where RepToday's raw footage is (`filming.footage`), unset until the Founder sets it: a folder outside this repository that the launcher only ever reads.
- [`run.json`](run.json): how each run works around the agent - its task definition, weekly schedule (with how often a start of that schedule checks whether the week's run is still owed and how many attempts that run may take when the Mac's sleep cuts it short; [operations](../docs/operations.md#a-run-happens-when-the-mac-is-awake)), the agent's time limit (`agent.time_limit_seconds`: an agent still running after it is stopped and the run finishes as timed out; [operations](../docs/operations.md#when-a-run-times-out)), how much of one command's output Codex shows the model (`work_counts`, which the run report's counts of the agent's work are made with; [operations](../docs/operations.md#reading-the-agents-work)), the 14-day window (its first sitting, which day 1 follows, and its posting slot, set only by the Founder), the date the Waitlist went live (unset until a reviewed change sets it; nothing is publishable before), how many Waitlist entries one Beta Cohort invitation batch offers (the Founder's call), the outreach messages it prepares (the Source whose link the personal-network ask carries, the creators a run may write to, and the wait before a follow-up), the outputs and sources its run report accounts for, the records step that saves `workspace/` and `ledger/` to `main`, and the prices behind its approximate cost.
- [`platforms.json`](platforms.json): platform facts the post-Draft lint checks - each test platform's Draft fields, character limits, and hashtag limits - and the shape every finished video is rendered at and measured against (`video`): 1080x1920 at 30 frames a second, with the safe zone its text is drawn in.
  Facts about the platforms, not strategy; the brand rules themselves are read from Mandu.
- [`sources.json`](sources.json): the fixed list of sources the launcher reads over the network at each run - the three subreddits' newest threads and their rules, and App Store reviews.
  Addresses only, which are platform facts; which competitors' reviews are read comes from the package's research in Mandu.
  Every address is on a host listed in [`guardrails/fetch.json`](guardrails/fetch.json), and is read only where that host's `robots.txt` allows it.
- [`guardrails/`](guardrails/): Guardrail configuration.
