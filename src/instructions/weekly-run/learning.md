## This session: the rejection reasons

This session has no working guidance of its own in `ledger/instructions/`: "Coding a rejection reason" and "Proposing an Instructions change" below are all of it.
Before this session the launcher took in the Founder's decisions and kept each rejection reason, in the Founder's own words, as Evidence.
Once the last session has ended, it writes each code it accepts beside the Founder's words and rebuilds the learning ledger.

Steps:

1. Give each rejection reason the brief lists one code, as "Coding a rejection reason" describes.
2. Write the package-change proposal each strategy reason the brief lists still needs, as "Writing an item" describes, unless an earlier session of this run already wrote it.
3. Where the brief's "Instructions change" section offers one, decide whether a change to the Instructions it names would have avoided what the Founder rejected, and if so, propose it, as "Proposing an Instructions change" describes.
4. Check your codes and your proposed change with the brief's check-work command, and your items with its check-incoming command.

In your summary, say which code you gave each reason, which proposals you wrote, and which Instructions change you proposed and why, or why you proposed none.

## Coding a rejection reason

For each reason the brief lists, write the file `<item id>.md` in the learning folder it names:

```markdown
---
item: 20261011-post-w1-day-03
code: tone
---

<one line: why this code fits the Founder's words>
```

- The codes are fixed, and the brief lists them: the execution codes `tone`, `length`, `factual-slip`, and `format`, and the strategy codes `fit`, `angle`, `claim`, and `positioning`.
- Never change, shorten, or restate the Founder's words; the launcher keeps them as they were given.
- A strategy code means the reason is about the Go-To-Market Package: write the package-change proposal that answers it, as an item in the incoming folder, and cite the decision record the brief names in its Evidence.
  It declares `new_angle: no` unless the change it proposes adds or changes an Angle or Hook.
  A strategy reason never changes your Instructions.

## Proposing an Instructions change

Your Instructions are your own working guidance for each workflow, in `ledger/instructions/`, which you can read and never write.
A change to them is made by the launcher, never by you: you propose the whole new text, and the launcher re-runs that workflow's example set with the text in force and with yours, and keeps yours only if no example does worse.
A kept change is shown to the Founder at the next sitting, with the reasons you cite.

- Propose a change only for the one workflow the brief's "Instructions change" section offers, and only from reasons that carry an execution code, the ones you code as execution in this session among them.
  Never cite a reason you coded as strategy: it becomes a package-change proposal instead.
- Change only what the cited reasons show was wrong in how the work was done, such as a tone, a length, a factual slip, or a format.
  Keep every other line as it is, the comment lines at the top most of all, and never add a positioning, a Fit, a claim, an Angle, a Hook, or any other text of the Go-To-Market Package: your Instructions point to Mandu instead of restating it, and the launcher refuses a change that copies a line of a package file.
- Write the file `<workflow>.md` in the Instructions area the brief names, `workspace/instructions/`, with your file-editing tool (apply_patch):

```markdown
---
workflow: post-drafts
reasons: 20261011-post-w1-day-03
summary: <one line of at most 300 characters: what the change does, and which reason it answers>
---

<the whole text of ledger/instructions/post-drafts.md as it should read, every unchanged line included>
```

- `reasons:` lists the item identifiers of the reasons it answers, separated by commas.
- Write at most one such file in a run, and nothing else in that folder.
- If no change to how you work would have avoided what the Founder rejected, propose none, and say why in your summary.
