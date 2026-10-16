## This session: the Weekly Read

This session has no working guidance of its own in `workspace/instructions/`: "Writing the memo" and "Writing a new Angle" below are all of it.
This session has two kinds of work, and the brief says which are due this run: the memo of the Weekly Read due, and a new Angle for each change decision the Founder approved.
Before this session the launcher worked out which Weekly Read is due, and took in the numbers and comments the Founder gave for it on the sitting page, each post on the platform the calendar names as the one that judges it.
When a memo is due, the brief's Weekly Read section lists every post the read covers, with the day the Founder says it went out (where he gave nothing, only the day the calendar planned it, which is not a day it was posted), each number he gave and its n, each number he did not give as not reported, the comments he gave as third-party text, the floor, and the results of the read before; when none is due, that section says so, and you write no memo.
Once the last session has ended, the launcher checks your memo; only a memo that passes becomes the memo the Founder reads, and each of its decision lines becomes its own Weekly Read decision item.
Approving a decision changes no package file by itself: for each approved kill, change, resolved pair, and flex slot, the launcher files a package-change proposal with the exact edit, for the Founder to approve.
It writes every such edit itself, but for the new Angle a change asks for, whose words are yours.

Steps:

1. Read `read-the-results.md`, the Angle bank, the calendar, and the A/B pairs file at the paths the brief lists.
   `read-the-results.md` is the only rule source: apply it exactly, and the calendar's midpoint gate at the day-7 read.
2. If the brief says a memo is due, write it at the path the brief names, as "Writing the memo" describes.
3. If a result is one `read-the-results.md` says would change the product, list it under Product; where it warrants one, also write a Dispatch request item in the incoming folder, as "Writing an item" describes but with `kind: dispatch-request` and its body under `## Request`, citing the memo.
   Never act on such a result yourself.
4. If the brief lists new Angles for approved change decisions, write each one, as "Writing a new Angle" describes.
5. Check the memo and each new Angle with the brief's check-work command, and any item with its check-incoming command, and fix every problem either reports.

In your summary, say each Angle's result and decision, each new Angle you wrote and what it changes, and what the checks said.

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
- Under Pairs (day 14 only), one line for every pair the brief lists: `- AB-<n> (days <n> and <n>): resolved, leg <A or B> leads. ...`, naming the leg whose Hook ranked higher, only when both legs were readable and the rank gap is large, otherwise `- AB-<n> (days <n> and <n>): repost. ...` with what would settle it.
- Under Product, one line for each result `read-the-results.md` says would change the product, ending in a decision, or `- None this read.`
- Every line is one line; a line ends with its decision and nothing after it.

## Writing a new Angle

The Founder approved a change decision on an Angle, and a changed Hook, signal, or kill criterion enters the package only as a new Angle (FR-7).
The launcher files a package-change proposal that adds your new Angle as one row at the end of the Angle bank; the Angle it changes stays as it is.
For each such decision the brief lists, write the new Angle at the path it names, `weekly-reads/changes/<decision item>.md`, holding one line and nothing else: the new Angle's row of the Angle bank, with as many cells as the bank's header, from `|` to `|`.

- Read the decision item the brief names, with the memo line and the numbers it rests on, and the changed Angle's row in the Angle bank.
- Its ID cell is the number the brief gives the new Angle.
- Its pain and source cell is the changed Angle's, character for character: the new Angle rests on the same sourced pain.
- Change what the decision's line and its numbers say did not work, and keep the rest as the changed Angle has it.
  Its Hook is new: a Hook belongs to exactly one Angle, so it repeats no Hook of the Angle bank or of the A/B pairs.
  Write the Hook as one line in double quotes, the words every post of the new Angle opens on, and hold it to the brand rules file the brief names, as every post's Hook is: the check-work command reports a Hook that breaks one.
  Write its success signal and kill criterion in the bank's own terms, each on a number the Weekly Read asks for on that platform.
- Its Platform cell names TikTok or YouTube Shorts, the platform whose numbers judge it.
- Follow the rules the Angle bank's own preamble gives every row and every Hook.
