## Writing a message Draft

Write each message as the file the brief names, with your file-editing tool, holding exactly these parts in this order:

```markdown
---
draft: message
product: RepToday
purpose: creator
to: <the creator's key, network, or the document id a reply answers>
angle: P03
offer: early-access
---

# <a few words naming the message, for the Founder>

## Message

<the words the Founder would send or post>

## Notes

<for the Founder, never sent: why this person or thread, what to check; or none>

## Claims

- Claim: <a behavioral claim the message makes>
  Code: `<path in the Product's repository>:<line>`
  Shows: `<code copied from those lines>`
```

- `purpose` is `network-ask`, `creator`, `creator-follow-up`, or `reply`.
  Copy `purpose` and `to` exactly from the brief: for the personal-network ask, `to` is the one word `network`; for a creator, their key; for a reply, the document id it answers.
- Only a message to a creator has `offer`: `early-access`, `founder-conversation`, or `story-material`, and never anything paid.
  Never write as if you had seen a creator's recent work: nothing of it reaches you.
- A personal-network ask carries the Source link the brief gives, exactly as written, and no other link.
- Under Claims, list every behavioral claim the message makes, each with the lines of code that support it at the commit the brief gives; write `none` when it makes none.
  Nothing in a message is frozen, so a message never lists a claim with `Code: none`: find the lines of code that show the behavior at the brief's commit and quote them exactly, or cut the sentence that makes the claim.
- A message holds no email address: the Founder fills in every recipient.
- Every message passes the brand lint, whose rules come only from the package in Mandu; the brief says what it reads.
- A follow-up is written only when the brief's table offers it, says plainly that it is the last message, and is the only one a creator ever gets.
- Write every message Draft only in the folders the brief names: the launcher queues a message only from a Draft that passes its checks, and the Founder alone sends or posts it.
