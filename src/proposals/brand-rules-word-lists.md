<!-- Adapted from skills/copywriting/references/ai-tells.md, skills/copy-editing/SKILL.md, skills/seo-audit/references/ai-writing-detection.md, and skills/offers/references/scarcity-urgency.md of github.com/coreyhaines31/marketingskills at commit 1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff (MIT; see THIRD_PARTY_NOTICES.md). -->
---
kind: package-change-proposal
product: RepToday
---

# Approve package change: add AI-tell, invented-proof, and scarcity lists to the brand lint

## Proposal

The brand lint in `brand-rules.json` holds banned words, social proof, and character rules, written for Hooks.
The Marketing Engineer now runs every one of its rules on every field of a Draft (Hooks, spoken lines, on-screen text, captions, titles, hashtags, alt text, and later messages), and has new rule types that read their lists from this same file, so banned language stays in the Go-To-Market Package.
Until the lists below are in the file, those rule types check nothing, and every run report says they are pending.

Add these keys to `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json`:

```json
{
  "stock_phrases": ["say goodbye to", "say hello to", "unlock the power of", "unleash the power of", "reimagined", "redefined", "to the next level", "transform the way you", "the future of", "everything you need to", "all-in-one", "effortless", "in just a few clicks", "join thousands of", "happy customers", "game-changer", "this changes everything", "in today's fast-paced world", "whether you're", "imagine never", "when it comes to", "here's the thing", "the truth is", "let me be clear", "here's what nobody tells you", "let's dive in", "in conclusion", "at the end of the day", "it's worth noting", "moreover", "additionally", "experts agree", "studies show", "trusted by", "marks a pivotal moment", "redefines the category", "great question", "let's be honest", "we get it", "level up", "delve", "tapestry", "testament to", "realm", "embark", "beacon", "multifaceted", "paradigm", "synergy", "myriad", "plethora", "meticulous", "intricate", "utilize", "leverage", "supercharge", "turbocharge", "ever-evolving landscape", "plays a crucial role"],
  "capped_words": ["seamless", "robust", "streamline", "empower", "elevate", "unlock", "unleash", "harness", "foster", "enhance", "optimize", "cutting-edge", "innovative", "transformative", "holistic", "comprehensive", "pivotal", "crucial", "vital", "powerful", "next-level", "world-class", "best-in-class", "landscape", "navigate", "ecosystem", "journey", "truly", "genuinely", "incredibly", "deeply", "fundamentally", "significantly", "simply", "actually", "literally", "quietly", "very", "really", "extremely", "basically", "just", "in order to", "things", "stuff"],
  "capped_words_per_paragraph": 1,
  "long_sentence_words": 20,
  "long_sentence_commas": 2,
  "invented_proof_terms": ["user", "download", "install", "customer", "member", "subscriber", "follower", "people", "review", "rating", "star", "testimonial", "athlete", "trainer", "expert", "coach", "result"],
  "fake_scarcity": ["limited spots", "spots left", "only {n} left", "only {n} spots", "only {n} testers", "last chance", "while supplies last", "ends tonight", "ends soon", "act now", "hurry", "don't miss out", "before it's gone", "selling fast", "final hours", "limited time", "today only", "countdown"],
  "lint_allow_phrases": ["no card required"]
}
```

What each does, on every field a viewer reads: a stock phrase blocks the Draft; more than one capped word in a paragraph blocks it; a sentence over 20 words or over 2 commas is shown as a warning, never a block; a number or quantity next to an invented-proof term ("10,000 users", "thousands of reviews"), any percentage, and any multiplier ("3x") block it, and a Draft never fills in a missing source but leaves `[NEED: source]`, which also blocks it; a scarcity or urgency phrase blocks it (`{n}` is any number); and an allowed phrase is never counted by the other rules.

Append to the file's `comment`: " The lists stock_phrases, capped_words, invented_proof_terms, fake_scarcity, and lint_allow_phrases, and the sentence caps, are adapted from marketingskills (https://github.com/coreyhaines31/marketingskills, commit 1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff, skills/copywriting/references/ai-tells.md, skills/copy-editing/SKILL.md, skills/seo-audit/references/ai-writing-detection.md, skills/offers/references/scarcity-urgency.md). MIT License. Copyright (c) 2025 Corey Haines. Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."

To decide: whether every word belongs in Rep Today's voice (for example "just", "simply", and "quietly" are capped, not banned, so one per paragraph still passes), and whether the invented-proof terms cover every claim the brand forbids.
Any list can be trimmed or extended before Mandu applies it; the lint reads only what this file holds.

## Touches

- `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json`

## Evidence

- The lint is a machine-checkable subset of the brand guidelines and today checks Hooks only: `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json` line 2
- No invented stats, ratings, or testimonials may appear anywhere: `projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json` line 48
- "Plain, declarative, short. No hype stacking": `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 143
- "the product has zero users, downloads, ratings, or testimonials. Never invent or imply any": `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 158
- "never advertise scarcity (\"limited spots\", \"only 100 testers\")": `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 226
- "Never fabricates social proof": `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 260
- "Never uses urgency mechanics": `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 262
- The AI-tell Ban and Cap lists, the 20-word and two-comma sentence checks, and `[NEED: proof]` instead of invented proof: https://github.com/coreyhaines31/marketingskills/blob/1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff/skills/copywriting/references/ai-tells.md
- The cut list and the leave-alone allowlist: https://github.com/coreyhaines31/marketingskills/blob/1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff/skills/copy-editing/SKILL.md
- Overused words and stock phrases: https://github.com/coreyhaines31/marketingskills/blob/1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff/skills/seo-audit/references/ai-writing-detection.md
- Fake scarcity to avoid: https://github.com/coreyhaines31/marketingskills/blob/1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff/skills/offers/references/scarcity-urgency.md

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
