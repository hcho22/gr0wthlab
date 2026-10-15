# The weekly read uses no YouTube connection

gr0wthlab does not connect to YouTube.
In a read week the Founder gives YouTube Studio's numbers for the posts YouTube judges on the sitting page, beside the TikTok Studio numbers he gives for the posts TikTok judges, and the Weekly Read reads them all the same way.
The 200-impression floor counts each platform's views.

Decided by the Founder on 2026-10-14, in his words: "weekly read - no connection, views for the floor."

## Why

US-ME11 planned to read YouTube's numbers with a read-only grant to the Founder's channel (Guardrail G4).
Read live on 2026-10-14, YouTube's API terms and its APIs leave that grant little to do for the Weekly Read, at a real cost:

- The APIs lack the numbers the read rules judge most YouTube posts on.
  Neither the Data API nor the Analytics API gives the share of viewers who watched rather than swiped away, which P03, P11, and P13 adjudicate on, and the Analytics API has no impressions metric; the Reporting API's thumbnail impressions come only in bulk reports that need a reporting job created on the channel, which is a write.
  Of US-ME11's YouTube list they give views, average percentage viewed, likes, comment count, and comment text ([the metrics](https://developers.google.com/youtube/analytics/metrics), "Last updated 2026-09-14 UTC").
- The terms forbid ranking what they do give.
  The Developer Policies: "Your API Clients must not (i) replace API Data with similar, independently calculated data, or (ii) access or use API Data to create new or derived data or metrics"; their own example rules out "a score that factors in likes, total views, or any other API Data".
  `read-the-results.md` ranks every post within the Angle bank.
  The way around it is an audit YouTube runs on request ([additional policies for derived metrics](https://developers.google.com/youtube/terms/derived-metrics-policy)).
- Connecting has standing costs: "Each API Client will provide and adhere to a published privacy policy" (the Terms of Service, section 7); the Founder's explicit approval before the AI model that writes the memo may see the data, since Authorized Data may be shown only to "the authorizing user or agents expressly approved by that user"; and, after a revocation, "you and your API Clients must delete all Authorized Data ... within 7 calendar days" (the Developer Policies, "Revocation"), which numbers committed to git would make hard.

So even connected, the Founder would have typed YouTube Studio's numbers by hand for the posts YouTube judges, about two in the first read and four in the second.
Without a connection he types them for the same posts and nothing else is needed.

The floor counts impressions in `read-the-results.md`, while the numbers `angles.md` lists as measurable at zero followers name views and no impressions on either platform.
The floor counts each platform's views until `read-the-results.md` says which number counts.

## What follows

- No credential, client, or grant exists for YouTube, and the launcher's only way onto the network is still `src/gr0wthlab/fetch.py`, credential-free.
  Guardrail G4, that YouTube access is read-only, holds because there is no YouTube access at all.
- Before each read week's sitting, a notice in the Review Queue lists exactly which numbers and comments to give for which posts, each post on the platform the calendar names as the one that judges it, and only the numbers the pre-registered signals and kill criteria of the read's posts on that platform name, since `read-the-results.md` ranks each post against the others in the bank, with its views for the floor and its comments, since comment content is a first-class result.
  Nothing is asked of YouTube for a post TikTok judges, nor of TikTok for one YouTube judges.
- The sitting page asks for those numbers one post at a time.
  Each becomes a record of the Founder's in `ledger/founder/results/`, and the next run turns it into Evidence for that post, with the date he read them as its source.
  A number he leaves blank is not reported, never zero.
- The numbers the Founder copies are his own, not API Data, so the Weekly Read ranks and rates them under `read-the-results.md` like TikTok's.
- Every Weekly Read memo says in one line that the floor counts each platform's views.
  A package-change proposal asks Mandu to say so in `read-the-results.md` (`src/proposals/read-the-results-views-floor.md`), filed once through gr0wthlab's usual route.
- The PRD stays as written.
  US-ME11's first acceptance criterion, that YouTube results are read with read-only access to the Founder's channel, is not met as written, and its box stays open: YouTube's results reach the Weekly Read another way, as numbers the Founder gives.

## Considered Options

The Founder was given these on 2026-10-14.

- **Connect anyway, with a read-only grant**: a published privacy policy, the Founder's approval for the AI to see the data, deletion within 7 days of a revocation, and YouTube Studio numbers typed by hand for the posts YouTube judges all the same.
  Rejected ("weekly read - connect").
- **No connection: the Founder gives YouTube Studio's numbers for the posts YouTube judges on the sitting page, beside TikTok's.**
  Chosen.

For the floor, which `read-the-results.md` counts in impressions, a number neither platform gives for these posts in what `angles.md` lists:

- **Count views on each platform, and propose that `read-the-results.md` say so.**
  Chosen ("views for the floor").
