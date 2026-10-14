"""The Marketing Engineer's Instructions: the ones in force, and how a change to them is proposed, gated, kept, shown,
and undone (US-ME16, FR-14, ADR 0003).

The Instructions in force are ledger/instructions/<workflow>.md, which every session reads and the sandbox can never
write. Only the session that codes the Founder's rejection reasons may propose a change, as the whole proposed text in
workspace/instructions/<workflow>.md, citing reasons coded as execution: a strategy reason becomes a package-change
proposal and can never be cited (learning.py). Once the last session has ended, the launcher checks the proposal,
re-runs the workflow's example set with the text in force and with the proposed text (examples.py), and writes the
proposed text here only when no example got worse. A kept change is shown to the Founder as a notice; rejecting that
notice undoes the change at the next run, and no other change to that workflow is tried while its notice is undecided.

A run tries at most one change: the workflow of the oldest rejection reason that may still lead to one goes first, and
the others wait for a later run. Each reason is offered once: what became of it is written into its decision's
Evidence (answer), and a reason the gate could not judge, as when its bound ran out, is offered again.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import evidence, examples, exchange, learning, sessions
from .areas import Areas, Store, UnsafeFile, read_plain
from .exchange import plural
from .queue import Ledger
from .waitlist import looks_like_address

# The workflows whose Instructions may change: each has its file in ledger/instructions/ and an example set in
# src/examples/ whose examples the agent re-runs.
WORKFLOWS = ("package-review", "post-drafts", "filming", "beta-recruiting", "listening", "outreach")
FOLDER = "instructions"  # the Instructions in force in ledger/, and the agent's Instructions area in workspace/
RECORDS = ("evidence", "instructions")
README = "README.md"
FRONT_KEYS = ("workflow", "reasons", "summary")
MAX_TEXT = 32_000
MAX_SUMMARY = 300
# A passage of a package file at least this long, a line or a table cell, found in a line a change adds, is package
# content, which never enters gr0wthlab (ADR 0001).
PACKAGE_LINE = 24
# How many changed lines the notice shows, and how much of each.
SHOWN_LINES = 40
SHOWN_CHARACTERS = 200
# What became of a change, and of each reason it cites.
KEPT = examples.KEPT
NOT_KEPT = examples.NOT_KEPT
NOT_COMPARED = examples.NOT_COMPARED
NONE_PROPOSED = "none proposed"
UNDONE = "undone"


def title(workflow: str) -> str:
    return sessions.workflow(workflow).title


def file_of(store: Store, workflow: str) -> Path:
    """A workflow's Instructions in force."""
    return store.path(FOLDER, f"{workflow}.md")


def relative(workflow: str) -> str:
    """A workflow's Instructions in force, from the repository's root."""
    return f"ledger/{FOLDER}/{workflow}.md"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return read_plain(path).decode("utf-8")


# Which reasons may lead to a change, and which workflow this run offers.


def answerable(reason: learning.Reason) -> bool:
    """Whether a rejection reason may still lead to a change to its workflow's Instructions: its workflow has them,
    nothing has answered it yet, and it carries an execution code or no code yet. A strategy reason never may."""
    code = reason.code
    return reason.workflow in WORKFLOWS and not reason.instructions and (not code or code in learning.EXECUTION)


def open_notice(ledger: Ledger, workflow: str) -> str | None:
    """The open notice of a kept change to a workflow's Instructions, which holds back every other change to them
    until the Founder decides it."""
    return next((str(entry["id"]) for entry in ledger.open_entries() if entry.get("instructions") == workflow), None)


@dataclass(frozen=True)
class Offer:
    """The one workflow whose Instructions this run's rejection reasons' session may propose a change to, and its
    reasons that may lead to one, oldest first: each coded as execution, or not coded yet."""

    workflow: str
    reasons: tuple[str, ...]

    def coded(self, found: Sequence[learning.Reason]) -> list[learning.Reason]:
        """The offered reasons that carry an execution code now."""
        return [reason for reason in found if reason.item in self.reasons and reason.code in learning.EXECUTION]


def offer(found: Sequence[learning.Reason], ledger: Ledger, store: Store, repo_root: Path) -> tuple[Offer | None, str]:
    """The workflow of the oldest reason that may lead to a change, unless a kept change's notice to it is undecided,
    it has no Instructions in force, or no example set that can gate a change, with all its reasons that may; or None
    and why no change is offered."""
    waiting = sorted((reason for reason in found if answerable(reason)), key=lambda r: (r.decided_at, r.item))
    if not waiting:
        return None, "no rejection reason may lead to one"
    held: list[str] = []
    for reason in waiting:
        workflow = reason.workflow
        notice = open_notice(ledger, workflow)
        if notice:
            held.append(f"the {title(workflow)} Instructions wait on the notice `{notice}` of their last change")
            continue
        try:
            read_text(file_of(store, workflow))
        except (OSError, UnsafeFile, UnicodeDecodeError) as error:
            held.append(f"`{relative(workflow)}` could not be read ({error})")
            continue
        try:
            examples.load(repo_root, workflow)
        except examples.SetError as error:
            held.append(f"no example set can gate a change to the {title(workflow)} Instructions: {error}")
            continue
        return Offer(workflow, tuple(other.item for other in waiting if other.workflow == workflow)), ""
    return None, "; ".join(dict.fromkeys(held))


def brief_lines(
    chosen: Offer | None, why: str, found: Sequence[learning.Reason], workspace: Path, repo_root: Path, check: str
) -> list[str]:
    """What the rejection reasons' session is told about an Instructions change it may propose this run."""
    lines = ["## Instructions change", ""]
    if chosen is None:
        return lines + [f"Propose no change to your Instructions this run: {why}."]
    by_item = {reason.item: reason for reason in found}
    workflow = chosen.workflow
    lines += [
        f"You may propose one change to the {title(workflow)} Instructions, `{repo_root / relative(workflow)}`, from"
        " the reasons below that carry an execution code, the codes you give in this session among them.",
        "A reason you code as strategy never changes your Instructions, and no other workflow's Instructions may"
        " change this run.",
        "",
    ]
    for item in chosen.reasons:
        reason = by_item[item]
        state = f"coded `{reason.code}`" if reason.code else "not coded yet"
        lines.append(f'- `{item}` ({state}): "{reason.words}"')
    lines += [
        "",
        f"Propose a change only where a change to how you work would have avoided what the Founder rejected: write the"
        f' whole new text as `{workspace / FOLDER / workflow}.md`, as "Proposing an Instructions change" describes.',
        f"The launcher re-runs the {title(workflow)} example set with the Instructions in force and with your text,"
        " and keeps your text only if no example does worse.",
    ]
    if check:
        lines.append(f"Check it before you finish: `{check}`.")
    return lines


# The agent's proposal.


def proposal_names(areas: Areas) -> tuple[str, ...]:
    """The files the rejection reasons' session may leave in the agent's Instructions area, by their path from
    workspace/: one proposed change for each workflow whose Instructions may change."""
    folder = areas.relative(areas.paths[FOLDER])
    return tuple(f"{folder}/{workflow}.md" for workflow in WORKFLOWS)


def clear_stale(areas: Areas) -> list[str]:
    """Remove each proposed change an earlier run left in the agent's Instructions area, before this run notes it: a
    run takes in only what its own rejection reasons' session wrote, and removes that once read."""
    removed = []
    for name in proposal_names(areas):
        path = areas.workspace / name
        if path.is_symlink() or path.exists():
            areas.remove(path)
            removed.append(name)
    return removed


@dataclass
class Proposal:
    name: str
    workflow: str
    reasons: tuple[str, ...]
    summary: str
    text: str


def parse(text: str, name: str) -> tuple[Proposal | None, list[str]]:
    """A proposed change as its file holds it: front matter, then the whole proposed text."""
    problems: list[str] = []
    lines = text.splitlines()
    fields, start = evidence.front_matter(lines, FRONT_KEYS, problems)
    if problems:
        return None, problems
    missing = [key for key in FRONT_KEYS if not fields.get(key)]
    if missing:
        return None, [f"the front matter needs {', '.join(f'`{key}:`' for key in missing)}"]
    body = "\n".join(lines[start:]).strip("\n")
    reasons = tuple(dict.fromkeys(part for part in fields["reasons"].replace(",", " ").split() if part))
    return Proposal(name, fields["workflow"], reasons, fields["summary"], body + "\n" if body else ""), []


def normalized(line: str) -> str:
    return " ".join(line.split())


def same(one: str, other: str) -> bool:
    """Whether two texts are the same but for blank lines at either end and spaces at the end of a line."""
    return [line.rstrip() for line in one.strip("\n").splitlines()] == [
        line.rstrip() for line in other.strip("\n").splitlines()
    ]


def passages(line: str) -> list[str]:
    """The pieces of package text one line holds, each in lowercase with its spacing made single: a table row's
    cells, or the line itself, without list, quote, or emphasis marks around it."""
    parts = line.strip().strip("|").split("|") if line.strip().startswith("|") else [line]
    found = []
    for part in parts:
        words = normalized(part).lstrip("-*>#0123456789. ").strip("\"'*_`“”‘’ ").casefold()
        if len(words) >= PACKAGE_LINE:
            found.append(words)
    return found


def package_lines(mandu: Path, paths: Sequence[str]) -> dict[str, str]:
    """Every passage of at least PACKAGE_LINE characters in the package files a run read, with the file it is in,
    from the Mandu checkout: each line, or each cell of a table row, in lowercase with its spacing made single. A file
    that cannot be read now adds none; one that is not valid text, which the run counts as a failed source, still adds
    every line that decodes, since the agent could copy those."""
    found: dict[str, str] = {}
    for relative_path in paths:
        try:
            text = (mandu / relative_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            for passage in passages(line):
                found.setdefault(passage, relative_path)
    return found


def check(
    proposal: Proposal,
    chosen: Offer | None,
    why: str,
    found: Sequence[learning.Reason],
    in_force: str | None,
    package: Mapping[str, str],
) -> list[str]:
    """Why a proposed change is refused, or nothing when it may go to its workflow's example set (ADR 0003). A reason
    names a line by its number and never repeats what the proposal says (docs/operations.md, where the agent's own
    words are kept)."""
    problems: list[str] = []
    workflow = proposal.workflow
    if workflow not in WORKFLOWS:
        return [f"`workflow:` must name one workflow whose Instructions may change: {', '.join(WORKFLOWS)}"]
    if proposal.name != f"{workflow}.md":
        problems.append(f"name the file `{workflow}.md`, after the workflow whose Instructions it changes")
    if chosen is None:
        return problems + [f"this run offers no change to any Instructions: {why}"]
    if workflow != chosen.workflow:
        return problems + [f"this run offers a change to the {title(chosen.workflow)} Instructions only"]
    by_item = {reason.item: reason for reason in found}
    unknown = [item for item in proposal.reasons if item not in by_item]
    if unknown:
        problems.append(f"`reasons:` names {plural(len(unknown), 'item')} that no rejection reason belongs to")
    for item in proposal.reasons:
        reason = by_item.get(item)
        if reason is None:
            continue
        if item not in chosen.reasons:
            problems.append(f"`{item}` is no rejection reason this run offers for a change")
        elif reason.code in learning.STRATEGY:
            problems.append(f"`{item}` is coded `{reason.code}`, a strategy code, which never changes Instructions")
        elif reason.code not in learning.EXECUTION:
            problems.append(f"`{item}` has no accepted execution code")
    summary = proposal.summary
    if "\n" in summary or len(summary) > MAX_SUMMARY:
        problems.append(f"`summary:` must be one line of at most {MAX_SUMMARY} characters")
    if looks_like_address(summary) or looks_like_address(proposal.text):
        problems.append("it holds something that looks like an email address")
    text = proposal.text
    if not text.strip():
        problems.append("after the front matter, give the whole proposed text of the Instructions")
    elif len(text) > MAX_TEXT:
        problems.append(f"the proposed text is {len(text)} characters; at most {MAX_TEXT}")
    if in_force is None:
        return problems + [f"`{relative(workflow)}` could not be read, so nothing can be compared with it"]
    if same(text, in_force):
        problems.append("the proposed text is the text in force")
    kept = set(text.splitlines())
    for number, line in enumerate(in_force.splitlines(), 1):
        if line.strip().startswith("<!--") and line not in kept:
            problems.append(f"keep every comment line of the text in force as it is, line {number} of it among them")
            break
    before = {normalized(line) for line in in_force.splitlines()}
    for number, line in enumerate(text.splitlines(), 1):
        words = normalized(line)
        if not words or words in before:
            continue
        folded = words.casefold()
        source = next((path for passage, path in package.items() if passage in folded), None)
        if source:
            problems.append(
                f"line {number} of the proposed text holds text of the Go-To-Market Package file `{source}`"
            )
            break
    return problems


@dataclass
class Taken:
    """What the launcher took from the agent's Instructions area once the last session ended: at most one proposal
    for this run's offer, and every file it refused, by name, with why."""

    proposal: Proposal | None = None
    refused: list[tuple[str, list[str]]] = field(default_factory=list)
    names: list[str] = field(default_factory=list)  # every file the area held but its README


def take(
    areas: Areas,
    store: Store,
    chosen: Offer | None,
    why: str,
    found: Sequence[learning.Reason],
    package: Mapping[str, str],
    publish: bool = True,
) -> Taken:
    """Read and check each proposed change the rejection reasons' session left; with publish, remove every one of
    them, kept or not, so none is read again. found is every rejection reason with the codes taken in this run."""
    taken = Taken()
    folder = areas.paths[FOLDER]
    prefix = areas.relative(folder) + "/"
    in_force: dict[str, str | None] = {}
    for path in list(areas.files(folder)):
        name = areas.relative(path)[len(prefix) :]
        if name == README:
            continue
        taken.names.append(name)
        try:
            proposal, problems = parse(read_text(path), name)
        except (UnsafeFile, OSError, UnicodeDecodeError) as error:
            proposal, problems = None, [f"unreadable: {error}"]
        if proposal is not None:
            if proposal.workflow in WORKFLOWS and proposal.workflow not in in_force:
                try:
                    in_force[proposal.workflow] = read_text(file_of(store, proposal.workflow))
                except (OSError, UnsafeFile, UnicodeDecodeError):
                    in_force[proposal.workflow] = None
            problems = check(proposal, chosen, why, found, in_force.get(proposal.workflow), package)
            if not problems and taken.proposal is not None:
                problems = ["a run takes one proposed change, and this run already took one"]
        if problems or proposal is None:
            taken.refused.append((name, problems))
        else:
            taken.proposal = proposal
        if publish:
            areas.remove(path)
    if publish:
        areas.remove_empty_folders(folder)
    return taken


# A change, from the gate to the Founder.


@dataclass
class Change:
    id: str
    proposal: Proposal
    reasons: list[learning.Reason]
    before: str
    gate: examples.Gate | None = None
    notice: str | None = None
    record: str | None = None

    @property
    def workflow(self) -> str:
        return self.proposal.workflow

    @property
    def outcome(self) -> str:
        return self.gate.outcome if self.gate else NOT_COMPARED

    @property
    def why(self) -> str:
        return self.gate.why if self.gate else "its example set was not run"


def change_id(store: Store, day: datetime, workflow: str) -> str:
    base = f"{day:%Y%m%d}-{workflow}"
    candidate, number = base, 2
    while store.path(*RECORDS, f"{candidate}.json").exists():
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def changed_lines(before: str, after: str) -> list[tuple[str, int, str]]:
    """Each line the change removes from the text in force or adds to it: removed or added, the line's number in
    the text it belongs to, and the line."""
    old, new = before.splitlines(), after.splitlines()
    found: list[tuple[str, int, str]] = []
    for tag, first, last, start, end in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            found += [("removed", number + 1, old[number]) for number in range(first, last)]
        if tag in ("replace", "insert"):
            found += [("added", number + 1, new[number]) for number in range(start, end)]
    return found


def record(store: Store, change: Change, run_id: str, now: datetime) -> str:
    """Write the change's record. A kept change keeps the text in force before it and the text proposed beside it, and
    the agent's summary; a change not kept is refused, so it leaves none of the agent's text, only each changed line by
    its number, the two texts' fingerprints, and the launcher's reasons (docs/operations.md, where the agent's own words
    are kept)."""
    kept = change.outcome == KEPT
    folder = (*RECORDS, change.id)
    texts = {"before": change.before, "proposed": change.proposal.text}
    if kept:
        for name, text in texts.items():
            store.write_text(store.path(*folder, f"{name}.md"), text)
    path = store.path(*RECORDS, f"{change.id}.json")
    data = {
        "id": change.id,
        "workflow": change.workflow,
        "instructions": relative(change.workflow),
        "proposed_by_run": run_id,
        "proposed_at": now.isoformat(),
        "summary": change.proposal.summary if kept else None,
        "reasons": [
            {
                "item": reason.item,
                "reason": reason.words,
                "code": reason.code,
                "kind": learning.kind(reason.code),
                "why": reason.why,
                "evidence": "/".join((*learning.DECISIONS, f"{reason.item}.json")),
            }
            for reason in change.reasons
        ],
        **{
            name: {"path": store.relative(store.path(*folder, f"{name}.md")) if kept else None, "sha256": sha256(text)}
            for name, text in texts.items()
        },
        "changed_lines": [
            {"change": what, "line": number, **({"text": text} if kept else {})}
            for what, number, text in changed_lines(change.before, change.proposal.text)
        ],
        "outcome": change.outcome,
        "why": change.why,
        "gate": change.gate.as_json() if change.gate else None,
        "notice": change.notice,
    }
    store.write_json(path, data)
    change.record = store.relative(path)
    return change.record


def apply(store: Store, change: Change) -> None:
    """Write the proposed text as the workflow's Instructions in force: only for a change its example set passed."""
    if change.outcome != KEPT:
        raise ValueError(f"a change whose outcome is {change.outcome!r} is never written")
    store.write_text(file_of(store, change.workflow), change.proposal.text)


def answer(
    store: Store,
    items: Sequence[str],
    outcome: str,
    change: str | None,
    run_id: str,
    now: datetime,
    found: Sequence[learning.Reason] = (),
) -> list[str]:
    """Write into each reason's decision Evidence what became of it as a change to its Instructions, so it is not
    offered again, and into its reason among `found`, from which the learning ledger is written; and return each that
    could not be written, with why."""
    problems = []
    by_item = {reason.item: reason for reason in found}
    for item in items:
        path = learning.decision_file(store, item)
        answered = {"outcome": outcome, "change": change, "by_run": run_id, "at": now.isoformat()}
        try:
            data = json.loads(read_text(path))
            data["instructions"] = answered
            store.write_json(path, data)
        except (OSError, UnsafeFile, ValueError) as error:
            problems.append(f"`{store.relative(path)}` could not record what became of its reason ({error})")
        else:
            if item in by_item:
                by_item[item].instructions = answered
    return problems


def notice(change: Change, report_path: str) -> tuple[str, str, str, str]:
    """The notice of a kept change, for the next sitting: the reasons that prompted it, the change line by line, and
    every example's result before and after it."""
    workflow = change.workflow
    lines = [
        f"The launcher changed the Marketing Engineer's {title(workflow)} Instructions, `{relative(workflow)}`, once"
        f" the workflow's example set showed no example doing worse with the change than without it.",
        "Acknowledge to keep the change. Reject, with your reason, and the next run puts the Instructions back as they"
        " were before it; until you decide, no other change to them is tried.",
        "",
        "**Why**",
        "",
    ]
    for reason in change.reasons:
        lines.append(f'- Your reason for rejecting `{reason.item}`: "{reason.words}"')
        lines.append(f"  The agent coded it `{reason.code}`, an execution code: {reason.why}")
    lines += ["", "**The change, in the agent's words**", "", change.proposal.summary, "", "**Line by line**", ""]
    shown = changed_lines(change.before, change.proposal.text)
    for what, number, text in shown[:SHOWN_LINES]:
        cut = text if len(text) <= SHOWN_CHARACTERS else text[:SHOWN_CHARACTERS].rstrip() + "..."
        shown_text = f'"{cut}"' if cut.strip() else "(an empty line)"
        lines.append(f"- Line {number}, {what}: {shown_text}")
    if len(shown) > SHOWN_LINES:
        lines.append(f"- And {plural(len(shown) - SHOWN_LINES, 'more changed line')}: the record has the whole text.")
    lines += ["", "**The example set**", ""]
    lines += examples.result_lines(change.gate) if change.gate else ["It was not run."]
    touches = f"- `{relative(workflow)}`: the {title(workflow)} Instructions every later session of it reads."
    evidence_lines = [
        f"- The change, with the text before it and the text proposed: `{change.record}`",
        *(f"- Your reason: `{'/'.join((*learning.DECISIONS, reason.item))}.json`" for reason in change.reasons),
        f"- The run report: `{report_path}`",
    ]
    ask = f"Notice: the {title(workflow)} Instructions changed"
    return ask, "\n".join(lines), touches, "\n".join(evidence_lines)


# Undoing a change whose notice the Founder rejected.


@dataclass
class Undo:
    """What a run did with the Founder's answer to the notice of a kept change: an undo, made or not, for a
    rejection, and for an acknowledgement only a record that could not be written."""

    change: str
    workflow: str
    notice: str
    reason: str
    rejected: bool
    done: bool = False
    why: str = ""


def undo(store: Store, outcomes: Sequence, run_id: str, now: datetime) -> list[Undo]:
    """For each notice of a kept change the Founder decided, as this run took the decision in: record the decision in
    the change's record, and where it is a rejection, put the workflow's Instructions back to the text they had
    before the change. A text that no longer is the one the change wrote, as after a reviewed change to it, is left
    as it is, and the run report says so; so is a record that could not be used."""
    found = []
    for outcome in outcomes:
        entry, decision = outcome.entry, outcome.decision
        if outcome.status != "taken" or not entry.get("instructions") or not entry.get("change"):
            continue
        identifier, workflow = str(entry["change"]), str(entry["instructions"])
        rejected = decision.decision == exchange.REJECT
        result = Undo(identifier, workflow, str(entry["id"]), decision.reason or "", rejected)
        path = store.path(*RECORDS, f"{identifier}.json")
        try:
            data = json.loads(read_text(path))
            data["decided"] = {"decision": decision.decision, "by_run": run_id, "notice": result.notice}
            if rejected:
                current = read_text(file_of(store, workflow))
                if sha256(current) != data["proposed"]["sha256"]:
                    result.why = f"`{relative(workflow)}` is no longer the text the change wrote"
                else:
                    before = read_text(store.path(*Path(data["before"]["path"]).parts))
                    if sha256(before) != data["before"]["sha256"]:
                        raise ValueError("the text before the change is not the one the record names")
                    store.write_text(file_of(store, workflow), before)
                    data["undone"] = {"by_run": run_id, "at": now.isoformat(), "reason": decision.reason}
                    result.done = True
            store.write_json(path, data)
        except (OSError, UnsafeFile, ValueError, KeyError, TypeError) as error:
            result.why = f"its record `{store.relative(path)}` could not be used ({error})"
        if rejected or result.why:
            found.append(result)
    return found


# What the run report says.


@dataclass
class Outcome:
    """Everything this run did about the Instructions: the offer, what was taken, the change and its gate, and each
    undo."""

    offer: Offer | None = None
    offer_why: str = ""
    taken: Taken | None = None
    change: Change | None = None
    undone: list[Undo] = field(default_factory=list)
    answered: list[str] = field(default_factory=list)  # reasons answered with no change proposed
    coded: list[str] = field(default_factory=list)  # the offered reasons that carry an execution code once taken in
    problems: list[str] = field(default_factory=list)


def report_lines(outcome: Outcome | None) -> list[str]:
    lines = ["## Instructions", ""]
    if outcome is None:
        return lines + ["- No Instructions change was offered or taken in this run."]
    for undo_ in outcome.undone:
        if undo_.done:
            lines.append(
                f"- The {title(undo_.workflow)} Instructions were put back as they were before change `{undo_.change}`,"
                f' since the Founder rejected its notice `{undo_.notice}`: "{undo_.reason}".'
            )
        elif undo_.rejected:
            lines.append(
                f"- Change `{undo_.change}` was not undone though the Founder rejected its notice `{undo_.notice}`:"
                f" {undo_.why}."
            )
        else:
            lines.append(
                f"- The Founder acknowledged the notice `{undo_.notice}` of change `{undo_.change}`, and that could not"
                f" be recorded with the change: {undo_.why}."
            )
    if outcome.offer is None:
        lines.append(f"- No change to any Instructions was offered: {outcome.offer_why}.")
    elif outcome.coded:
        lines.append(
            f"- Offered: a change to the {title(outcome.offer.workflow)} Instructions, from its workflow's reasons"
            f" coded as execution: {', '.join(f'`{item}`' for item in outcome.coded)}."
        )
    else:
        lines.append(
            f"- Offered: a change to the {title(outcome.offer.workflow)} Instructions; none of the reasons offered,"
            f" {', '.join(f'`{item}`' for item in outcome.offer.reasons)}, carries an execution code, so none could"
            " lead to one."
        )
    if outcome.answered:
        lines.append(
            f"- No change was proposed for {', '.join(f'`{item}`' for item in outcome.answered)}, so"
            f" {'it is' if len(outcome.answered) == 1 else 'they are'} not offered again."
        )
    taken = outcome.taken
    for name, problems in taken.refused if taken else []:
        lines.append(f"- Proposed change refused: `{name}`: {'; '.join(problems)}.")
    change = outcome.change
    if change is not None:
        cited = ", ".join(f"`{reason.item}`" for reason in change.reasons)
        lines.append(
            f"- Change `{change.id}` to the {title(change.workflow)} Instructions, from {cited}: {change.outcome}:"
            f" {change.why}."
        )
        if change.outcome == KEPT:
            lines.append(f"  The notice `{change.notice}` shows it at the next sitting.")
        elif change.outcome == NOT_KEPT:
            lines.append("  The Instructions are as they were; the reasons it cites are not offered again.")
        else:
            lines.append("  The Instructions are as they were; the reasons it cites are offered again at the next run.")
        if change.gate is not None:
            lines.append(f"  {change.gate.cost_line()}")
        if change.record:
            lines.append(f"  The record: `{change.record}`.")
    lines += [f"- {problem}." for problem in outcome.problems]
    return lines


def summary_lines(outcome: Outcome | None) -> list[str]:
    """What the run report's summary, which the sitting page shows first, says of an Instructions change tried or
    undone this run; nothing when there was none."""
    if outcome is None:
        return []
    lines = []
    for undo_ in outcome.undone:
        if undo_.done:
            lines.append(f"Instructions: change `{undo_.change}` undone, as the Founder rejected its notice.")
    change = outcome.change
    if change is not None:
        said = f"change `{change.id}` to the {title(change.workflow)} Instructions {change.outcome}"
        lines.append(f"Instructions: {said}: {change.why}.")
    return lines


def status(outcome: Outcome | None) -> str:
    """What became of this run's Instructions change, in a few words, for the report's row of outputs."""
    if outcome is None:
        return "no Instructions change was offered"
    undone = [f"change `{undo_.change}` undone" for undo_ in outcome.undone if undo_.done]
    if outcome.change is not None:
        change = outcome.change
        said = f"change `{change.id}` to the {title(change.workflow)} Instructions {change.outcome}"
    elif outcome.offer is None:
        said = f"no change offered: {outcome.offer_why}"
    else:
        said = f"a change to the {title(outcome.offer.workflow)} Instructions offered, none taken in"
    return "; ".join(undone + [said])


def gaps(outcome: Outcome | None) -> list[str]:
    """Why this run's work on the Instructions is incomplete: a proposal refused, a change the gate could not judge,
    an undo that could not be made, or a reason's answer that could not be recorded."""
    if outcome is None:
        return []
    refused = outcome.taken.refused if outcome.taken else []
    found = [f"the proposed change `{name}` was refused" for name, _ in refused]
    if outcome.change is not None and outcome.change.outcome == NOT_COMPARED:
        found.append(f"change `{outcome.change.id}` could not be judged: {outcome.change.why}")
    for undo_ in outcome.undone:
        if not undo_.done:
            found.append(f"change `{undo_.change}`{' was not undone' if undo_.rejected else ''}: {undo_.why}")
    return found + list(outcome.problems)


def notice_section(outcome: Outcome | None, day_text: str) -> tuple[int, str, str] | None:
    """The part of the run's problems notice for proposed changes refused and undos not made."""
    if outcome is None:
        return None
    lines = []
    for name, problems in outcome.taken.refused if outcome.taken else []:
        lines.append(f"- The proposed change `{name}` was refused: {'; '.join(problems)}")
    for undo_ in outcome.undone:
        if not undo_.done and undo_.rejected:
            lines.append(f"- Change `{undo_.change}` was not undone though you rejected its notice: {undo_.why}")
    if not lines:
        return None
    count = len(lines)
    return (
        count,
        f"{plural(count, 'Instructions problem')} on {day_text}",
        "\n".join(["These changes to the Marketing Engineer's Instructions did not go as asked:"] + lines),
    )
