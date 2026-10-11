# Third-party notices

gr0wthlab adapts text from the open-source marketingskills library.
Each adapted file opens with a one-line header naming its source paths and commit.

## marketingskills

- Source: https://github.com/coreyhaines31/marketingskills
- Commit: `1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff`
- License: MIT, Copyright (c) 2025 Corey Haines (full text below)

| File in gr0wthlab | Adapted from, at that commit |
| --- | --- |
| [`config/platforms.json`](config/platforms.json) | `skills/social/references/platform-limits.md`; its `video` block (the 9:16 canvas, the cross-platform safe zone, and the caption style): `skills/ad-creative/references/short-form-video-specs.md` |
| [`src/proposals/brand-rules-word-lists.md`](src/proposals/brand-rules-word-lists.md) | `skills/copywriting/references/ai-tells.md`, `skills/copy-editing/SKILL.md`, `skills/seo-audit/references/ai-writing-detection.md`, `skills/offers/references/scarcity-urgency.md` |
| [`src/examples/post-drafts/files/mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json`](src/examples/post-drafts/files/mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json) | a subset of the same lists, for the tests and the example set: `skills/copywriting/references/ai-tells.md`, `skills/copy-editing/SKILL.md`, `skills/seo-audit/references/ai-writing-detection.md`, `skills/offers/references/scarcity-urgency.md` |
| [`workspace/instructions/post-drafts.md`](workspace/instructions/post-drafts.md) | `skills/copywriting/references/ai-tells.md`, `skills/copy-editing/SKILL.md` |
| [`src/examples/post-drafts/evals.json`](src/examples/post-drafts/evals.json) | the shape of the library's `skills/*/evals/evals.json` (`{id, prompt, expected_output, assertions[], files[]}`) |
| [`src/examples/filming/evals.json`](src/examples/filming/evals.json) | the same `evals.json` shape |
| [`workspace/instructions/filming.md`](workspace/instructions/filming.md) | the review-once gate of `skills/video/references/edit-anatomy.md` (approve the plan before any edit), and the notes on fitting footage to the 9:16 frame of `skills/ad-creative/references/short-form-video-specs.md` |
| [`src/gr0wthlab/filming.py`](src/gr0wthlab/filming.py) | the beat-sheet shape of `skills/video/references/edit-anatomy.md`: one row per shot, with its time, on-screen text, and caption, to which the filming plan adds the device, real time, and what may not be cut |

The library's advice on rewriting hooks during a test is not adopted: a Hook is frozen in Mandu.

The word lists in `src/proposals/brand-rules-word-lists.md` are proposed for RepToday's `brand-rules.json` in Mandu, carrying the same notice in that file's `comment` field; gr0wthlab's lint reads the lists only from Mandu.

```text
MIT License

Copyright (c) 2025 Corey Haines

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
