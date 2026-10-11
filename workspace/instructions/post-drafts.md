<!-- The AI-tell patterns below are adapted from skills/copywriting/references/ai-tells.md and skills/copy-editing/SKILL.md of github.com/coreyhaines31/marketingskills at commit 1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff (MIT; see THIRD_PARTY_NOTICES.md). -->
# Post Drafts

How to turn one calendar day of the 14-day kit into a post Draft the Founder can judge on taste and accuracy alone.
This is the Marketing Engineer's own working guidance; it holds no package content, which stays in Mandu.
The Draft's format is in the task definition, and the launcher's checks decide whether it is offered; this page is about the judgment the checks cannot make.

## Before you write

- Read the day's row in the calendar, its Angle's row in the Angle bank (the sourced pain, the hypothesis, the Format, the signal, and the kill criterion), its pair section when it is a pair leg, and the brand guidelines.
- Take the Hook from the brief, word for word.
  It is frozen: you never change it, reorder it, or fix its punctuation, even when a check fails on it.
- The Angle's Format column sets what the video is: screen record or founder on camera, its length, whether it is cut, and whether it runs in real time.
  Plan only what that Format allows; never plan footage the Founder has not been asked to record, and never an AI-generated person, voice, or scene.

## The beats

- Beat 1 is the hook, the first 3 seconds.
  It has three channels: what the viewer sees happen, what is said, and the on-screen text, which is the Hook.
  Let them work together without repeating each other: the visual action shows the mechanic, the on-screen text states the Hook, and a spoken line, when the Format has one, adds what the text does not say.
  A silent screen record has no spoken line; write none.
- Each later beat names one visual action and at most one short on-screen line.
- Show only what the product visibly does on screen; an on-screen number must be one the screen itself shows.
- A first-person line ("I built...") is spoken by the founder on camera, so it belongs only in an Angle whose Format puts the founder on camera.

## The captions

- The first line is the Hook.
- Then one or two short lines of plain fact about what the video shows, and the pre-launch status in words the brand guidelines allow, such as "Not released yet."
- No call to action, link, or download line: the product has no listing, and the Waitlist is not live.
- The other platform carries the same text, hashtags, and alt text; only the YouTube title differs, and it is the Hook.
- Use at most one hashtag unless the kit asks for more.
- The brand lint reads a hashtag as words run together: a word or phrase a brand rule lists blocks the Draft anywhere inside a hashtag, run together or joined by underscores, even as part of a longer word, and so does a number or quantity before an invented-proof term.
  That is stricter than in every other field, where a listed phrase matches only as whole words, whatever joins them (spaces, hyphens, dashes, or underscores).
  When a hashtag is blocked this way, choose another one.
- Alt text says plainly what is on screen, for someone who cannot see it.

## Claims

- A behavioral claim is anything the copy or the video says the app does: what it shows when it opens, what a missed day does to the score, that it works offline.
- Find the code that does it at the commit the brief gives, with `git grep -n` and `git show` on that commit, and cite the lines that show it, copying the code exactly into Shows.
- If no code supports a claim, cut the claim; never soften it into a vaguer one.
- Never state a speed, a number of users, downloads, ratings, reviews, or results, and never what the app records or sends beyond the shipped mechanic.

## Voice

Follow the brand guidelines' voice and claims-hygiene rules; the brand lint catches some of them, and the rest are yours to keep.
These AI tells make copy read as machine-written; avoid each one, and never stack two:

- The contrast reveal: setting up a belief nobody stated in order to deny it ("Not X. Y.", "It's not X, it's Y").
  State the true thing directly.
- The negation list: defining the product by three absences ("No X, no Y, no Z").
  Say what does happen; one absence that matters may stay.
- The trailing pile-on: a complete claim, then a comma and a run of add-ons.
  End the sentence at the claim.
- A question you answer yourself ("The result?"), and the colon reveal ("The best part: it learns.").
- A drumbeat of fragments ("Simple. Fast. Done."), and everything in threes.
- Hype words and empty intensifiers; replace each with the fact it stands for.

Leave alone: a single absence next to the point it supports, a list of three when there really are three things, and a clause after a comma that adds a new fact.

## When the package blocks a Draft

- If the frozen Hook fails a brand rule, or an open checklist line blocks every post, write the Draft as the kit requires anyway and let the launcher block it, naming the rule.
- Then write one package-change proposal that cites both sides (the Hook or checklist line, and the rule or record it conflicts with), unless one is already open or decided in the brief; the Founder decides which side changes.
- A changed Hook, signal, or kill criterion is never an edit: it enters only as a new Angle through a package-change proposal.

## Pair legs and re-drafts

- For an A/B leg whose other leg already has an open or approved post, copy that leg's Draft and change only the Hook's lines: the hook beat's on-screen text, the first caption line, and the YouTube title.
  The hook beat's visual action and spoken line may change with them; every later beat, the rest of each caption, the hashtags, and the alt text stay word for word, beat for beat, and every beat keeps its time.
- When both legs are due in one run, write the earlier day first and copy it for the later day.
- A re-cut pair is one the kit marks as a re-cut, in its section of the A/B pairs or in either leg's calendar row.
  Plan its opening for both legs before you write either: each leg opens on its own Hook in the hook beat, and the pair's other Hook, where the opening order calls for it, sits in one later beat as its on-screen text or spoken line.
  Write every other beat once and use it in both legs unchanged, in the same order and for the same length of time; the re-cut may move when those beats start, and never changes what one says or shows.
- When a brand rule fails text the two legs share, do not reword one leg alone to pass.
  If the other leg is not approved and the brief lists both days, reword both Drafts together, word for word the same beyond the Hook.
  If the other leg is approved, its text is settled: leave yours as that leg has it, let the launcher block it naming the rule, and say so in your summary.
  Only a package change or a re-cut of both legs, which is the Founder's call, lets that pair pass.
- A day with an open item keeps it; rewrite its Draft only when the package or the Founder's decision gives a reason, and say why in your summary.
- A day the Founder approved is never drafted again.
