---
kind: package-change-proposal
product: RepToday
new_angle: no
---

# Approve package change: add loss-framing and sponsorship-ask lists to the brand lint

## Proposal

The Marketing Engineer now drafts messages for you to send: the personal-network ask, one message to each creator the channel plan names, and replies in threads.
The package says two things about them that the brand lint in `brand-rules.json` cannot check yet, because it holds no list for either: copy is never loss-framed, and a message to a creator is never a sponsorship request.
Until the lists below are in the file, both stay a matter of judgment, the Marketing Engineer's and then yours, and every message item and run report says the two rule types are pending.

Add these keys to `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json`:

```json
{
  "loss_framing": ["don't break your", "don't lose your", "before it's too late", "you'll regret", "falling behind", "stop wasting", "don't let yourself down", "you're missing out", "can't afford to", "you owe it to yourself", "what's your excuse", "no more excuses"],
  "sponsorship_asks": ["sponsor", "sponsored", "sponsorship", "paid partnership", "paid promotion", "brand deal", "rate card", "your rates", "media kit", "affiliate", "promo code", "discount code", "commission", "shoutout", "shout-out", "in exchange for a post", "in exchange for a mention", "in return for a post"]
}
```

What each does: a `loss_framing` phrase blocks a Draft in every field of copy, a post's as well as a message's; a `sponsorship_asks` phrase blocks only a message to a creator, and no post is read for it.
A phrase matches as whole words in any letter case, however its apostrophe is typed, and a single word also matches its plural.

To decide: whether each phrase is one Rep Today would never say, and what is missing.
The lists are the Marketing Engineer's own first wording, taken from no other source, so trim or extend them freely before Mandu applies them; the lint reads only what this file holds.
Leave out any phrase a frozen Hook or an approved line already uses, since a listed phrase blocks that copy too.

## Touches

- `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json`

## Evidence

- "Identity-framed, never loss-framed": `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 142
- The personal-network ask is identity-framed, "never loss-framed": `projects/RepToday/gtm/06-channels/channel-plan.md` line 80
- What a message to a creator may offer, "never a sponsorship": `projects/RepToday/gtm/06-channels/channel-plan.md` line 88
- The lint is a machine-checkable subset of the brand guidelines: `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json` line 2
- What the stories ask of these messages (US-ME13, US-ME14): `docs/prd/prd-marketing-engineer-v1_261008.md` in gr0wthlab

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
