## This session: Beta Cohort recruiting

Your working guidance is `workspace/instructions/beta-recruiting.md`.
Before this session the launcher read the Founder's Beta Build record in Mandu, which is the Founder's word that a Beta Build passed Apple's review.
Only once that record exists does it choose who the next Beta Cohort invitations go to, from the view you cannot read; the brief's `## Beta Cohort recruiting` section never names anyone.
Once the last session has ended, the launcher checks every recruiting Draft and attaches the people it chose to the invitation.

Steps:

1. Write each recruiting Draft the brief's Beta Cohort recruiting table lists, except one it shows as open or approved with nothing to change, as "Writing a recruiting Draft" describes.
   A recruiting Draft is one short message and depends on nothing else in the run: write each one the table lists whatever another session did or left undone.
   The session is not finished until every recruiting Draft the table lists is written, or your summary says why it has none.
   Never judge for yourself whether a Beta Build is approved, and never choose, name, or look for who is invited.
2. Check your recruiting Drafts with the brief's check-beta-drafts command.

In your summary, say which Drafts you wrote and what check-beta-drafts said of each.

## Writing a recruiting Draft

Write each recruiting Draft as the file the brief's Beta Cohort recruiting table names, with your file-editing tool, holding exactly these parts in this order:

```markdown
---
draft: message
product: RepToday
purpose: beta-invitation
---

# <a few words naming the message for the Founder>

## Subject

<the subject, on one line>

## Message

<the message, in short paragraphs, the same words for everyone who gets it>

## Sources

- Quote: "<words copied exactly from one package line>"
  File: `<the file's path inside the Mandu checkout>` line <n>
```

- `purpose` is `beta-invitation` for the invitation and `waitlist-ask` for the Waitlist ask, as the brief's table says.
- The message goes to people the launcher chose, whom you never learn: write no name, no greeting by name, and no entry identifier.
- Write no email address anywhere in the file, not even one to reply to: the Founder resolves addresses and sends.
  The launcher removes a Draft that holds anything that looks like one.
- Write no link and no web address in the subject or the message.
  How the Founder invites, by a TestFlight public link or by individual email invitation, is the Founder's undecided call, so the message works either way and the Founder adds what the route needs.
- Each source quotes four or more words copied exactly from one line of a package file the brief lists as citable, with that line's number; quote only the words the message uses.
- Every figure the message states, in digits or as a word, must be in a line you cite.
  State no count of places, people, or days of your own, and nothing that presses for a quick answer.
- An invitation cites at least one line of the thesis's K8 files, says that the first session is recorded, and says how many minutes it takes, as a line you cite gives it.
- The subject and the message pass the brand lint, as post copy does; among other things, neither asks a question.
- Rewrite an open or approved Draft only to change it for a reason, such as a package change or the Founder's decision; a Draft the Founder rejected is not asked again until it changes, so rewrite it to answer the reason the brief gives.
- Write recruiting Drafts only as the files the brief names: the launcher queues a recruiting message only from a Draft that passes its checks, with the people it chose attached.
