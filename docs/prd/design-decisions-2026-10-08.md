# Marketing Engineer design decisions (grilling session, 2026-10-08)

Source: the captain's grill-with-docs session in firstmate, based on an X thread and a YouTube summary about the "marketing engineer" role.
Glossary: `CONTEXT.md` at the repository root; first decision record: `docs/adr/0001-evidence-and-drafts-only.md`.
Both were drafted in firstmate's private records and committed with the repository's first change, alongside this file and the PRD beside it.

## Decisions, in the order they were made

1. Scope: a Marketing Engineer for the captain's own Products, RepToday first and Immerse later (captain: "i need a marketing engineer for my products such as reptoday and immerse").
2. First 30 days for RepToday: the marketing side of launch, meaning publishing the Waitlist, running the existing 14-day social test kit on real accounts with the captain approving every post, and recruiting the Beta Cohort.
3. Home: a standalone repository plus its own agent (captain: "a standalone repo plus an agent that can call other projects, such as RepToday or Immerse").
4. Products: the Marketing Engineer reads Product repositories freely and hands every Product change to firstmate as a Dispatch, through that Product's normal reviewed path.
5. Review: the captain reviews and decides everything through Mandu (captain: "through mandu").
6. Beta timing: Beta Cohort recruiting waits until a Beta Build has passed Apple's review; until then the Marketing Engineer runs the Waitlist and the social test kit only.
7. Waitlist: email, one Fit question (used to work out and lost the routine / work out regularly / never had a routine), and a beta-invitation opt-in; Source is captured from the link with no extra field.
8. Publishing: the captain approves each week's posts in one Mandu sitting; approved posts go into a scheduling service that TikTok and YouTube already allow to post publicly, the Marketing Engineer can only add drafts there, and the captain confirms the schedule.
9. Knowledge: each Product's Go-To-Market Package stays in Mandu as the single copy; the Marketing Engineer repository holds only Evidence, Drafts, and Review Queue items, and proposes package changes that Mandu applies after the captain approves.
   The stale "trademark unverified" notes across RepToday's package (cleared 2026-08-07) should be the Marketing Engineer's first proposed correction.
10. Results: YouTube results and comments are read automatically with read-only access; the captain exports TikTok Studio per-post numbers and comments into Mandu before each Weekly Read (day 7 and day 14 of the window).
11. Decision record: record decisions 3, 4, 5, and 9 as the repository's first ADR (done as a draft).
12. Builder: firstmate workers build and change the Marketing Engineer's code and Guardrails through reviewed pull requests; the running agent may refine only its own Instructions and examples, and each refinement is shown in the next weekly Mandu review.
13. Runtime: a local scheduled automation on the captain's Mac, in Codex or Claude Code (captain: "codex or claude code automation"); the build chooses whichever connects most cleanly; one run a week just before the captain's Mandu sitting, plus on-demand runs.
14. Privacy: the Marketing Engineer sees Waitlist sign-ups without email addresses (Source, Fit answer, opt-in, date); addresses are filled in only when the captain sends.
    The RepToday privacy policy needs a Waitlist section as part of the Waitlist Dispatch.
15. Immerse: joins listen-only after RepToday's first 14-day window has run cleanly, with nothing public until Immerse has a name; its Evidence feeds the naming decision and a Go-To-Market Package in Mandu.
16. Success bar at about day 30: about 50 or more good-fit, beta-opted-in Waitlist sign-ups (enough to fill a 20 to 50 person Beta Cohort), and the captain's weekly marketing time around one hour (one Mandu sitting plus the TikTok export; filming days counted separately).

## Facts established during the session

- The captain's stated goal is income by the end of 2026, with RepToday as the primary bet (Mandu `CLAUDE.md`).
- Gate 0 for public RepToday assets is clear except the Waitlist: name cleared and reserved 2026-08-07, `@reptoday` handles held on TikTok, YouTube, Instagram, and X, `reptoday.app` live (Mandu `projects/RepToday/02-marketing-launch-checklist_260807.md`).
- RepToday's deployable site source lives in the RepToday repository at `gtm/03-site/`; the rest of the go-to-market package lives in Mandu at `projects/RepToday/gtm/`.
- The 14-day kit posts one asset a day to both TikTok and YouTube Shorts at one fixed evening slot, with the founder on camera on days 2, 4, 6, and 12 (`gtm/05-social-pmf/cadence-14-day.md`).
- Unaudited TikTok and YouTube API clients can only post privately, so public posting needs the captain or an already-audited service.
- No paid spend is planned: RepToday's channel plan runs zero paid pre-launch, and the existing dry-run creative loop's publish and spend switch stays a founder decision.
- Mandu's weekday review runs as the Codex automation `mandu-weekday-project-review` on the captain's Mac.
