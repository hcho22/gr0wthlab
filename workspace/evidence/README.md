# Evidence

What the Marketing Engineer has gathered or observed, each with its source and the date gathered: Listening quotes, post results, Waitlist counts, and the Founder's rejection reasons.
Evidence never holds an email address, and it can support a package-change proposal but never changes the Go-To-Market Package by itself.
Formats: US-ME06, US-ME11, US-ME13, US-ME16.

- `package-snapshots/<run id>.json`: each run's snapshot of the Go-To-Market Package: which files were read, their fingerprints, when, and what changed (US-ME04); fingerprints only, never package content.
- `decisions/<item id>.json`: each Founder decision taken in from Mandu, with its reason or note and its Mandu source (US-ME07).
- `sittings/<date>.json`: how long each sitting took, from Mandu, and the run that first took it in.

The launcher alone writes these three folders.
