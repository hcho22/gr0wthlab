# Drafts

Posts and messages the Marketing Engineer has prepared that no one outside can see.
A Draft cites its Angle, sourced pain, signal, and kill criterion by reference to Mandu rather than copying them, and becomes public only through the Founder.
Formats: US-ME08, US-ME09, US-ME14, US-ME15.

- `posts/window-<n>/day-<nn>.md`: one post Draft per calendar day of a 14-day window, in the format of the run's task definition ([`src/instructions/weekly-run.md`](../../src/instructions/weekly-run.md)).
  After each run the launcher checks every Draft due that run and queues a post item only for one that passes; every check of every Draft is in `ledger/evidence/post-drafts/<run id>.json`.
- `beta-recruiting/<Product>/invitation.md` and `waitlist-ask.md`: the two recruiting Drafts of Beta Cohort recruiting, written only when the run's brief asks for them, in the format of the run's task definition.
  Each is one message, the same words for everyone, with no email address, no link, and no figure a cited package line does not hold; the launcher chooses who an invitation goes to and attaches them to the item, never to the Draft.
  The launcher queues a message item only for a Draft that passes its checks, and removes a Draft that holds anything that looks like an email address; every check is in `ledger/evidence/beta-recruiting/<run id>.json`.
- `messages/outreach/`: the personal-network ask (`network-ask.md`), one message for each creator the plan names (`creator-<key>.md`), and at most one follow-up each (`follow-up-<key>.md`).
- `messages/replies/<document id>.md`: a reply to a thread, named for the Listening Evidence it answers.
  The launcher queues a message item only from a Draft that passes every check; the Founder alone sends or posts it, and no Draft ever holds an email address.
