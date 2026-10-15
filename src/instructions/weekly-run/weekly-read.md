## This session: the Weekly Read

This session has no working guidance of its own in `workspace/instructions/`: "Writing the memo" below is all of it.
Before this session the launcher worked out which Weekly Read is due, and took in the numbers and comments the Founder gave for it on the sitting page, each post on the platform the calendar names as the one that judges it.
The brief's Weekly Read section lists every post the read covers, with the day the Founder says it went out (where he gave nothing, only the day the calendar planned it, which is not a day it was posted), each number he gave and its n, each number he did not give as not reported, the comments he gave as third-party text, the floor, and the results of the read before.
Once the last session has ended, the launcher checks your memo; only a memo that passes becomes the memo the Founder reads, and each of its decision lines becomes its own Weekly Read decision item.

Steps:

1. Read `read-the-results.md`, the Angle bank, the calendar, and the A/B pairs file at the paths the brief lists.
   `read-the-results.md` is the only rule source: apply it exactly, and the calendar's midpoint gate at the day-7 read.
2. Write the memo at the path the brief names, as "Writing the memo" describes.
3. If a result is one `read-the-results.md` says would change the product, list it under Product; where it warrants one, also write a Dispatch request item in the incoming folder, as "Writing an item" describes but with `kind: dispatch-request` and its body under `## Request`, citing the memo.
   Never act on such a result yourself.
4. Check the memo with the brief's check-work command, and any item with its check-incoming command, and fix every problem either reports.

In your summary, say each Angle's result and decision, and what the checks said.

## Writing the memo

The memo is one Markdown file with exactly these parts, in this order:

```markdown
# Weekly Read, window 1, day 7

## Angles

- P03 (day 3): cleared its signal. <why, from the numbers and the rule>. Decision: keep
  > day 3: "<a comment, word for word as the Founder gave it>"
- P01 (day 1): insufficient data. <why>. What would settle it: <the evidence at the next read>. Decision: test

## Flex slot

- Flex slot: earned by P03. <why>. Decision: test

## Product

- None this read.
```

- At the day-7 read the sections are Angles, Flex slot, and Product; at the day-14 read they are Angles, Pairs, and Product.
- Write one line under Angles for every Angle the brief lists, and no other, naming its days exactly as the brief does, such as `(days 3 and 10)`.
  Each line's result is one of `cleared its signal`, `missed its signal`, `at risk`, `met its kill criterion`, and `insufficient data`, and it ends in `Decision: keep`, `kill`, `change`, or `test`.
- `insufficient data` is its own result, never a fail: use it for every Angle none of whose posts reached the floor on the platform that judges it, and wherever the rules leave too few readable posts to judge.
  A number the Founder did not give is not reported: never treat it as zero, and never estimate it.
  Where judging an Angle needs a number or comment text the Founder did not give, its result is `insufficient data`, never `at risk` or `missed its signal`, and what would settle it is that number or text.
  A result that rests on a rank needs as many readable posts as the rules ask before posts are ranked: `read-the-results.md`, and at the day-7 read the calendar's midpoint gate.
  With fewer, that result is `insufficient data`, and its line says how many posts were readable.
- At the day-7 read nothing is killed: flag an Angle `at risk` instead.
  At the day-14 read, `met its kill criterion` and `Decision: kill` are only for an Angle the day-7 memo flagged at risk, since a kill needs two consecutive Weekly Reads.
- Every `insufficient data` or `at risk` line, and every pair to repost, says `What would settle it:` and what evidence at the next read would.
- Put `(n=<posts>)` right after every number you write, with at most four words between them, such as `412 views (n=1)` or `ranked first of 3 readable posts (n=3)`; a day, an Angle, or a pair is not a number here.
  Do not write the floor's figure: the memo the Founder reads states it.
- Quote comments that describe the pains the Angles target, each on its own line under its Angle's line, as `  > day <n>: "<words>"`, word for word from the comments the brief gives for that day; quote none of anyone's name.
  Quote nowhere else: a decision line holds no quotation marks.
- Under Flex slot (day 7 only), one line: `- Flex slot: earned by P<n>. ...` only when that Angle's line says it cleared its signal, never because it merely ranked first among weak posts; otherwise `- Flex slot: not earned. ...`.
- Under Pairs (day 14 only), one line for every pair the brief lists: `- AB-<n> (days <n> and <n>): resolved. ...` only when both legs were readable and the rank gap is large, otherwise `repost` with what would settle it.
- Under Product, one line for each result `read-the-results.md` says would change the product, ending in a decision, or `- None this read.`
- Every line is one line; a line ends with its decision and nothing after it.
