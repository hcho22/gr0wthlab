---
exchange: 7
id: 20261004-reptoday-waitlist
kind: dispatch-request
product: RepToday
---

# Approve Dispatch: build RepToday's Waitlist on reptoday.app, the last Gate 0 item

## Request

Build RepToday's Waitlist: a sign-up on `reptoday.app` that records where each person came from and how well they fit, and a copy of the sign-ups without email addresses for the Marketing Engineer to count.
Once you approve and ask Mandu for it, Mandu gives you a ready message to pass to firstmate, which builds it in RepToday through RepToday's normal reviewed path; the Marketing Engineer never changes RepToday.
Every quoted wording is for your approval, and an approval note can change any of it.

### The sign-up

- Exactly one low-pressure call to action, keeping the page's words: "Join the waitlist" and "Add your email and we'll tell you the day it ships."
  The page asks for nothing else, no download, follow, or share; where the form appears more than once, it is the same form.
- Three fields and no others:
  1. Email, required.
  2. One Fit question, "Which sounds most like you?", with no answer pre-selected: "I used to work out and lost the routine" (`lost-the-routine`), "I work out regularly" (`exercises-regularly`), or "I've never had a routine" (`never-had-a-routine`).
     An answer is required to sign up.
  3. A box, unticked until the person ticks it: "Invite me to the beta before launch".
- The page now promises "one message"; since an opted-in person may also get a beta invitation, it should say "one launch email, plus a beta invitation only if you ask for one".
- No "how did you hear about us" field: the Source comes from the link.

### Source, from the link

- One link per Source: `reptoday.app/tiktok`, `reptoday.app/youtube`, `reptoday.app/reddit`, and `reptoday.app/network` (your personal network).
  Each opens the sign-up page, and the word after the slash is that Source's lowercase tag.
  TikTok may not give a new account a clickable profile link, so each link is short enough to say aloud, type, or put in a profile.
- A sign-up keeps the Source of the link its visitor arrived by, even after they look around the site.
  A sign-up reached any other way, such as by plain `reptoday.app`, is Source `unknown`; the links work in any letter case.
- A new Source later is a new Dispatch request plus a reviewed gr0wthlab change.

### Web events

Emit `landing_page_view` when the landing page loads and `waitlist_signup` when an email is submitted, each with `referrer_source`, as RepToday's event schema defines them; `referrer_source` is the visit's tag, or `none`.
Neither event carries the email address or the entry identifier.

### Privacy policy

`reptoday.app/privacy` gains a Waitlist section, in place of the waitlist sentences in section 10, that says in the policy's plain voice:

- What is collected: the email address; the answer to the routine question; whether you asked for a beta invitation; which Rep Today link brought you, if any; and the sign-up date.
- Why: to email you when Rep Today launches; to invite you to the beta, only if you asked; and to count, without your address, which links and which routines bring people.
- How long it is kept: until 30 days after the launch email goes out, or until you ask to be removed, whichever comes first.
- How to be removed: the unsubscribe link in any waitlist email, or a message to reptoday.app@gmail.com; your sign-up and answers are then deleted within 7 days.
- Who sees your address: only the founder, when sending a waitlist email, and the service that stores it for Rep Today; it is never sold or shared.

### The anonymous view gr0wthlab reads

- RepToday keeps one file on your Mac that gr0wthlab's launcher reads, read-only, at each weekly run, with no network.
- The file sits outside the gr0wthlab, Mandu, and RepToday checkouts, where the sandboxed Marketing Engineer can never open it; once the build lands, a reviewed gr0wthlab change records its path.
- It is UTF-8 JSON in exactly this shape:

```json
{"view": 1, "generated_at": "2026-10-11T22:00:00+00:00", "entries": [
  {"entry": "k3P9xQ2m", "source": "tiktok", "fit": "lost-the-routine", "beta_opt_in": true, "signed_up_on": "2026-10-05"}
]}
```

- `entry`: a random identifier of 1 to 64 letters, digits, `-` or `_`; unique; stable while the sign-up exists; never derived from the address, so never a hash or an encoding of it.
- `source`: `tiktok`, `youtube`, `reddit`, `network`, or `unknown`.
- `fit`: `lost-the-routine`, `exercises-regularly`, or `never-had-a-routine`; `null` only for a sign-up that holds no answer, which gr0wthlab counts as unknown Fit, never as not a fit.
- `beta_opt_in`: `true` or `false`.
- `signed_up_on`: the sign-up's date in UTC, `YYYY-MM-DD`.
- `generated_at`: when the file was written, with its UTC offset; each run report says how long before the run that was.
- Nothing else: no address, name, or other field. A removed sign-up leaves the file.

If any value in the file looks like an email address, gr0wthlab discards the whole read, records no Waitlist Evidence that week, and reports a Guardrail breach to you.

### Addresses stay on your side

- Addresses are resolved only on your side, at send time: you turn an entry identifier into its address in RepToday's storage or your email tool when you send.
- No email-service credential, such as the account behind today's Kit form, and no export that holds addresses is ever placed where the Marketing Engineer reads: the gr0wthlab, Mandu, and RepToday checkouts.
  One such credential would expose every address.

### Left to RepToday

Storage (including whether Kit stays), hosting, how a link's Source reaches its sign-up, how and how often the view is produced, whether sign-ups confirm their email, and every other implementation choice are RepToday's design under firstmate.

## Touches

- RepToday `gtm/03-site/index.html`, and `gtm/03-site/index-b.html` while it is served: the form, the Source links, and web events
- RepToday `gtm/03-site/privacy.html`: the Waitlist section
- RepToday: the anonymous view and the send-time lookup, wherever RepToday's design puts them
- gr0wthlab `config/products.json`: the view's path, in a reviewed change once the build lands

## Evidence

- Gate 0's last open item is the Waitlist, which "needs exactly **one** low-pressure CTA (email capture)": `projects/RepToday/02-marketing-launch-checklist_260807.md` in Mandu
- The landing page asks only for an email, through a Kit form (`rep-today.kit.com`) shown twice: `gtm/03-site/index.html` in RepToday
- The privacy page says Kit stores the waitlist email, but not how long it is kept or how to be removed: `gtm/03-site/privacy.html` section 10 in RepToday
- `landing_page_view` and `waitlist_signup` carry `referrer_source` "(utm or none)": `projects/RepToday/gtm/06-channels/event-metric-schema.md` in Mandu
- TikTok gates clickable bio links behind requirements a new account may not meet: `projects/RepToday/gtm/05-social-pmf/angles.md` in Mandu
- The Waitlist's fields and Fit answers, Source from the link, and no addresses for the Marketing Engineer (decisions 7 and 14): `docs/prd/design-decisions-2026-10-08.md` in gr0wthlab
- What this request specifies (US-ME05), and the counts gr0wthlab keeps from the view (US-ME06): `docs/prd/prd-marketing-engineer-v1_261008.md` in gr0wthlab

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
