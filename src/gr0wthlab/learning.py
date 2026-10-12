"""Learning from the Founder's rejections (F4, pulled forward from US-ME16): each one-line reason gets a code, and the
code decides where the reason may go.

The code list and its split live here, in launcher code (Guardrail G8), so no Instruction and no agent can move a
code from one side to the other:

- an execution code (tone, length, a factual slip, format) is about how a Draft was made, and may later refine the
  Marketing Engineer's Instructions;
- a strategy code (Fit, an Angle, a claim, positioning) is about the Go-To-Market Package, so it becomes a
  package-change proposal and can never refine Instructions.

The agent proposes a code for each rejection reason, as workspace/evidence/learning/<item id>.md; the launcher checks
it and writes it into the decision's own Evidence in ledger/evidence/decisions/, beside the Founder's words, which
stay as they were given. A launcher-owned learning ledger counts the codes for each workflow, always as "3 of 7" and
never as a percentage.

Until US-ME16 builds the refinement loop, no run may change workspace/instructions/ at all: the launcher keeps what
the folder held before the agent started and puts it back afterwards, so nothing a run read, a fetched post least of
all, can rewrite the agent's own guidance.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import evidence, exchange
from .areas import Areas, Store, UnsafeFile, read_plain
from .exchange import plural
from .queue import Ledger
from .state import Tally, queued_item
from .waitlist import looks_like_address

WORKFLOW = "learning"
EXECUTION = ("tone", "length", "factual-slip", "format")
STRATEGY = ("fit", "angle", "claim", "positioning")
CODES = EXECUTION + STRATEGY
MEANING = {
    "tone": "the voice or wording was off",
    "length": "too long or too short",
    "factual-slip": "a fact in the Draft was wrong",
    "format": "the shape or layout was wrong",
    "fit": "it speaks to the wrong person",
    "angle": "the Angle or its Hook is the problem",
    "claim": "a claim the package approves or forbids is the problem",
    "positioning": "it positions the Product wrongly",
}
TO_INSTRUCTIONS = "instructions"
TO_PROPOSAL = "proposal"
DECISIONS = ("evidence", "decisions")
FOLDER = ("evidence", "learning")
LEDGER_FILE = (*FOLDER, "ledger.json")
CODES_IN = ("learning",)  # under workspace/evidence/
FRONT_KEYS = ("item", "code")
FORMAT = 1
MAX_WHY = 300


def kind(code: str) -> str:
    return "execution" if code in EXECUTION else "strategy"


def route(code: str) -> str:
    """Where a coded reason may go: an execution code toward Instructions, a strategy code to a proposal."""
    if code not in CODES:
        raise ValueError(f"{code!r} is not a rejection code")
    return TO_INSTRUCTIONS if code in EXECUTION else TO_PROPOSAL


def may_refine_instructions(code: str) -> bool:
    """Whether a reason with this code may ever refine the agent's Instructions; never for a strategy code."""
    return code in EXECUTION


def of(count: int, total: int) -> str:
    """A count as F4 states it: "3 of 7", never a percentage."""
    return f"{count} of {total}"


def workflow_of(entry: Mapping[str, object]) -> str:
    """The workflow that produced a Review Queue item, by what its queue entry holds."""
    item_kind = str(entry.get("kind"))
    if item_kind == "post":
        return "post-drafts"
    if item_kind == "message":
        if entry.get("beta"):
            return "beta-recruiting"
        purpose = (entry.get("message") or {}).get("purpose")
        return "listening" if purpose == "reply" else "outreach"
    if item_kind == "package-change-proposal":
        return "listening" if entry.get("listening") else "package-review"
    return {
        "filming-plan": "filming",
        "dispatch-request": "dispatch-requests",
        "weekly-read-decision": "weekly-read",
    }.get(item_kind, "review-queue")


# The Founder's reasons, as the decisions' Evidence holds them.


@dataclass
class Reason:
    item: str
    workflow: str
    words: str  # the Founder's own words, never altered
    decided_at: str
    code: str = ""
    why: str = ""
    coded_by_run: str = ""
    proposal: str = ""  # the package-change proposal that answers a strategy reason, once one is queued

    def as_json(self) -> dict[str, object]:
        data: dict[str, object] = {
            "item": self.item,
            "workflow": self.workflow,
            "reason": self.words,
            "decided_at": self.decided_at,
            "code": self.code or None,
        }
        if self.code:
            data.update(kind=kind(self.code), route=route(self.code), why=self.why, coded_by_run=self.coded_by_run)
        if self.code in STRATEGY:
            data["proposal"] = self.proposal or None
        return data


def decision_file(store: Store, item: str) -> Path:
    return store.path(*DECISIONS, f"{item}.json")


def reasons(store: Store, ledger: Ledger) -> tuple[list[Reason], list[str]]:
    """Every rejection reason the launcher has kept, oldest first, with its code if it has one."""
    found: list[Reason] = []
    problems: list[str] = []
    folder = store.path(*DECISIONS)
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(read_plain(path).decode("utf-8"))
            if data.get("decision") != exchange.REJECT or not data.get("reason"):
                continue
            item = str(data["item"])
            coded = data.get("code") if isinstance(data.get("code"), dict) else {}
            code = str(coded.get("code") or "")
            found.append(
                Reason(
                    item,
                    workflow_of(ledger.entries.get(item) or {"kind": data.get("kind")}),
                    str(data["reason"]),
                    str(data.get("decided_at") or ""),
                    code if code in CODES else "",
                    str(coded.get("why") or ""),
                    str(coded.get("coded_by_run") or ""),
                )
            )
        except (OSError, UnsafeFile, ValueError, KeyError, TypeError, AttributeError) as error:
            problems.append(f"`{store.relative(path)}` could not be read for its rejection reason ({error})")
    return sorted(found, key=lambda reason: (reason.decided_at, reason.item)), problems


def answered(store: Store, ledger: Ledger, products: Sequence[str], found: Sequence[Reason]) -> None:
    """Mark each strategy reason that a queued package-change proposal answers: one whose Evidence cites the
    reason's own decision record."""
    proposals = []
    for entry in ledger.entries.values():
        if entry["kind"] != "package-change-proposal":
            continue
        try:
            proposals.append((str(entry["id"]), queued_item(store.root, entry, products).evidence))
        except (OSError, ValueError, UnsafeFile):
            continue
    for reason in found:
        if reason.code in STRATEGY:
            cited = "/".join((*DECISIONS, f"{reason.item}.json"))
            reason.proposal = next((identifier for identifier, text in proposals if cited in text), "")


# Taking in the agent's proposed codes.


@dataclass
class Result:
    reasons: list[Reason] = field(default_factory=list)
    coded: list[tuple[str, str]] = field(default_factory=list)  # item and code taken in this run
    set_aside: list[tuple[str, list[str]]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    record: str | None = None

    def uncoded(self) -> list[Reason]:
        return [reason for reason in self.reasons if not reason.code]

    def owed(self) -> list[Reason]:
        return [reason for reason in self.reasons if reason.code in STRATEGY and not reason.proposal]


def check_code(
    text: str, name: str, open_reasons: Mapping[str, Reason]
) -> tuple[tuple[str, str, str] | None, list[str]]:
    """One proposed code: the item, the code, and the line that says why, or what is wrong with the file."""
    problems: list[str] = []
    lines = text.splitlines()
    fields, start = evidence.front_matter(lines, FRONT_KEYS, problems)
    why = " ".join(" ".join(lines[start:]).split()) if start else ""
    item, code = fields.get("item", ""), fields.get("code", "")
    if problems:
        return None, problems
    if name != f"{item}.md":
        problems.append("name the file <item id>.md, after the rejected item it codes")
    if code not in CODES:
        problems.append(f"code must be one of: {', '.join(CODES)}")
    if item not in open_reasons:
        problems.append("its item: names no rejected item whose reason still needs a code")
    if not why or len(why) > MAX_WHY:
        problems.append(f"after the front matter, say in one line of at most {MAX_WHY} characters why the code fits")
    if looks_like_address(why):
        problems.append("the line holds something that looks like an email address")
    return (None, problems) if problems else ((item, code, why), [])


def take(
    areas: Areas,
    store: Store,
    ledger: Ledger,
    products: Sequence[str],
    run_id: str,
    now: datetime,
    publish: bool = True,
) -> Result:
    """Take in each code the agent proposed, write it into its decision's Evidence, and rebuild the learning ledger.
    A proposed code that fails its check is set aside: its file is removed, and nothing of it is kept but its name
    and the reasons. With publish off nothing is written, and the result says what a run would do."""
    result = Result()
    result.reasons, result.problems = reasons(store, ledger)
    waiting = {reason.item: reason for reason in result.reasons if not reason.code}
    folder = areas.path("evidence", *CODES_IN)
    areas.ensure_folder(folder)
    prefix = areas.relative(folder) + "/"
    for path in list(areas.files(folder)):
        name = areas.relative(path)[len(prefix) :]
        try:
            proposed, problems = check_code(read_plain(path).decode("utf-8"), name, waiting)
        except (UnsafeFile, OSError, UnicodeDecodeError) as error:
            proposed, problems = None, [f"unreadable: {error}"]
        if proposed is None:
            result.set_aside.append((name, problems))
            if publish:
                areas.remove(path)
            continue
        item, code, why = proposed
        reason = waiting.pop(item)
        reason.code, reason.why, reason.coded_by_run = code, why, run_id
        result.coded.append((item, code))
        if publish:
            record = json.loads(read_plain(decision_file(store, item)).decode("utf-8"))
            record["code"] = {
                "code": code,
                "kind": kind(code),
                "route": route(code),
                "why": why,
                "coded_by_run": run_id,
                "coded_at": now.isoformat(),
            }
            store.write_json(decision_file(store, item), record)
            areas.remove(path)
    answered(store, ledger, products, result.reasons)
    if publish:
        areas.remove_empty_folders(folder)
        path = store.path(*LEDGER_FILE)
        store.write_json(path, ledger_record(result.reasons, run_id, now))
        result.record = store.relative(path)
    return result


def counts(found: Sequence[Reason]) -> dict[str, dict[str, object]]:
    """For each workflow: its rejections, how many are coded, and each code's count among them."""
    workflows: dict[str, dict[str, object]] = {}
    for reason in found:
        row = workflows.setdefault(
            reason.workflow, {"rejections": 0, "coded": 0, "execution": 0, "strategy": 0, "codes": {}}
        )
        row["rejections"] += 1
        if reason.code:
            row["coded"] += 1
            row[kind(reason.code)] += 1
            row["codes"][reason.code] = row["codes"].get(reason.code, 0) + 1
    return dict(sorted(workflows.items()))


def ledger_record(found: Sequence[Reason], run_id: str, now: datetime) -> dict[str, object]:
    """The learning ledger: every rejection reason with its code, and the counts for each workflow."""
    return {
        "format": FORMAT,
        "updated_by_run": run_id,
        "updated_at": now.isoformat(),
        "note": "Each reason is the Founder's own words, kept in its decision's Evidence. A count reads as n of m"
        " rejections of its workflow, never as a percentage. An execution code may later refine Instructions"
        " (US-ME16); a strategy code becomes a package-change proposal and never does.",
        "codes": {"execution": list(EXECUTION), "strategy": list(STRATEGY)},
        "workflows": counts(found),
        "reasons": [reason.as_json() for reason in found],
    }


def count_lines(found: Sequence[Reason]) -> list[str]:
    """One line for each workflow with a rejection: its codes as "3 of 7", and what is still uncoded."""
    lines = []
    for workflow, row in counts(found).items():
        total = int(row["rejections"])
        codes = ", ".join(f"{code} {of(count, total)}" for code, count in sorted(row["codes"].items()))
        line = f"{workflow}: {plural(total, 'rejection')}, {of(int(row['coded']), total)} coded"
        if codes:
            line += (
                f" ({codes}); execution {of(int(row['execution']), total)}, strategy {of(int(row['strategy']), total)}"
            )
        lines.append(line)
    return lines


def gaps(result: Result | None, problem: str, agent_gap: str) -> list[str]:
    """Why the coding of rejection reasons is incomplete this run: the reasons could not be read, or a reason the
    brief listed ends the run with no accepted code, whether the agent left it uncoded, was stopped first, or
    proposed a code the launcher set aside. A reason left without a code is asked for again at the next run."""
    if result is None:
        return [problem or "the rejection reasons were not read"]
    found = list(result.problems)
    waiting = result.uncoded()
    if waiting:
        found.append(f"no accepted code for {', '.join(f'`{reason.item}`' for reason in waiting)}")
        if agent_gap:
            found.append(agent_gap)
    return found


def tally(result: Result | None, problem: str, agent_gap: str) -> Tally:
    incomplete = "; ".join(gaps(result, problem, agent_gap))
    if result is None:
        return Tally(WORKFLOW, 0, 0, "no rejection reason was coded", incomplete)
    waiting, owed = len(result.uncoded()), len(result.owed())
    total = len(result.reasons)
    note = f"{plural(total, 'rejection reason')}, {of(total - waiting, total)} coded" if total else "no rejection yet"
    if result.coded:
        note += f"; {len(result.coded)} coded this run"
    if owed:
        note += f"; {plural(owed, 'strategy reason')} still without a package-change proposal"
    return Tally(WORKFLOW, len(result.coded) + len(result.set_aside), len(result.coded), note, incomplete)


# What the agent and the Founder are told.


def brief_lines(found: Sequence[Reason], workspace: Path) -> list[str]:
    """The reasons that still need a code, and the strategy reasons that still need their proposal."""
    lines = ["## Rejection reasons", ""]
    waiting = [reason for reason in found if not reason.code]
    owed = [reason for reason in found if reason.code in STRATEGY and not reason.proposal]
    if not waiting and not owed:
        return lines + ["Every rejection reason has its code, and every strategy reason its proposal."]
    if waiting:
        lines += [
            f"Give each reason below one code, as the file `{workspace / 'evidence' / CODES_IN[0]}/<item id>.md`:"
            " front matter `item:` and `code:`, then one line saying why the code fits. Never change the Founder's"
            " words.",
            "Execution codes: " + "; ".join(f"`{code}` ({MEANING[code]})" for code in EXECUTION) + ".",
            "Strategy codes: " + "; ".join(f"`{code}` ({MEANING[code]})" for code in STRATEGY) + ".",
            "",
        ]
        lines += [f'- `{reason.item}` ({reason.workflow}): "{reason.words}"' for reason in waiting]
    if owed:
        lines += [
            "",
            "These reasons carry a strategy code, so each becomes a package-change proposal, never a change to your"
            " Instructions. Write the proposal that answers it, citing the decision record in its Evidence:",
            "",
        ]
        lines += [
            f'- `{reason.item}` ({reason.code}): "{reason.words}": cite `{"/".join((*DECISIONS, reason.item))}.json`'
            for reason in owed
        ]
    return lines


def report_lines(result: Result | None, put_back: Sequence[str]) -> list[str]:
    lines = ["## Learning", ""]
    if result is None:
        return lines + ["The rejection reasons were not read this run."]
    if not result.reasons:
        lines.append("No rejection reason has been taken in yet.")
    else:
        lines.append("Rejection reasons, each the Founder's own words in its decision's Evidence, by workflow:")
        lines += [""] + [f"- {line}." for line in count_lines(result.reasons)]
        if result.record:
            lines.append(f"- The learning ledger: `{result.record}`.")
    for item, code in result.coded:
        where = (
            "it may later refine Instructions (US-ME16)"
            if may_refine_instructions(code)
            else "it becomes a package-change proposal and never changes Instructions"
        )
        lines.append(f"- Coded this run: `{item}` as `{code}`, {kind(code)}: {where}.")
    for reason in result.reasons:
        if reason.code in STRATEGY:
            state = f"answered by `{reason.proposal}`" if reason.proposal else "no proposal queued yet"
            lines.append(f"- Strategy reason `{reason.item}` ({reason.code}): {state}.")
    waiting = result.uncoded()
    if waiting:
        lines.append(f"- Not coded yet: {', '.join(f'`{reason.item}`' for reason in waiting)}.")
    for name, problems in result.set_aside:
        lines.append(f"- Proposed code set aside: `{name}`: {'; '.join(problems)}")
    lines += [f"- {problem}." for problem in result.problems]
    if put_back:
        lines.append("- Instructions were changed during the run and put back:")
        lines += [f"  - {line}" for line in put_back]
    else:
        lines.append("- Instructions (`workspace/instructions/`) are as they were before the run.")
    return lines


def notice_section(result: Result | None, day_text: str) -> tuple[int, str, str] | None:
    if result is None or not result.set_aside:
        return None
    lines = ["These proposed codes for rejection reasons were not taken in:"]
    lines += [f"- `{name}`: {'; '.join(problems)}" for name, problems in result.set_aside]
    count = len(result.set_aside)
    return count, f"{plural(count, 'proposed rejection code')} not taken in on {day_text}", "\n".join(lines)


# The guard on the agent's Instructions.


@dataclass
class Guidance:
    """What workspace/instructions/ held before the agent started: each plain file's content, by its path there, and
    the path of each entry that could not be read, which is not guarded."""

    files: dict[str, bytes] = field(default_factory=dict)
    unread: set[str] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)


def remember(areas: Areas) -> Guidance:
    """Read every plain file of the agent's Instructions, before it starts."""
    guidance = Guidance()
    folder = areas.paths["instructions"]
    for path in list(areas.files(folder)):
        name = areas.relative(path)
        try:
            guidance.files[name] = read_plain(path)
        except (UnsafeFile, OSError) as error:
            guidance.unread.add(name)
            guidance.problems.append(f"`{name}` could not be read before the run ({error}), so it is not guarded")
    return guidance


def write_back(areas: Areas, path: Path, data: bytes) -> None:
    """Write one file of the agent's Instructions as it was: only into a real folder, only as a new plain file, and
    never through a link, whatever the agent left in its place."""
    folders = [folder for folder in reversed(path.parents) if folder not in areas.paths["instructions"].parents]
    for folder in folders[1:]:
        areas.ensure_folder(folder)
    if not areas.real_folder(path.parent):
        raise OSError("its folder is not a real folder")
    areas.remove(path)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def put_back(guidance: Guidance, areas: Areas) -> list[str]:
    """Undo every change the run made to the agent's Instructions, and say what was undone. No run may change its
    Instructions until US-ME16 builds the reviewed way to; a strategy reason never may. An entry that could not be
    read before the run is left exactly as it is."""
    lines = []
    folder = areas.paths["instructions"]
    now: dict[str, Path] = {areas.relative(path): path for path in list(areas.files(folder))}
    for name, path in sorted(now.items()):
        if name not in guidance.files and name not in guidance.unread:
            areas.remove(path)
            lines.append(f"`{name}` was added during the run and removed")
    areas.remove_empty_folders(folder)
    for name, data in sorted(guidance.files.items()):
        path = areas.workspace / name
        try:
            unchanged = name in now and read_plain(path) == data
        except (UnsafeFile, OSError):
            unchanged = False
        if unchanged:
            continue
        what = "changed" if name in now else "removed"
        try:
            write_back(areas, areas.check(path), data)
            lines.append(f"`{name}` was {what} during the run and put back as it was")
        except OSError as error:
            lines.append(f"`{name}` was {what} during the run and could not be put back ({error.strerror or error})")
    areas.remove_empty_folders(folder)
    return lines
