"""What one agent session did, as the launcher counts it.

Every count comes from Codex's event stream for the session, from the Draft files the run left in workspace/, or from
the Review Queue, never from the agent's words. The run report shows them beside the session's own closing line, so a
session that did little and says it finished does not read better than one that did more and says it stopped. Each is
of one session alone: a Draft or a proposal an earlier run left in workspace/, or another session of the same run
wrote, is not this session's work, so it is not counted as such. The counts inform the Founder: nothing is queued,
blocked, or marked incomplete because of them.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import exchange, posts
from .areas import Areas, UnsafeFile, read_plain
from .boundary import ConfigError
from .drafts import PostDraft, none
from .queue import INCOMING

# A line shorter than this is too common to show that one file's text came back.
TELLING_LINE = 24
# The report names the package files that were not read only when they are this few; the run's log record names all.
NAMED_AT_MOST = 6


@dataclass(frozen=True)
class Command:
    """One shell command that ran to its end, from Codex's event stream."""

    text: str
    shown: str  # its output as Codex shows it to the model


def shown_part(output: str, limit: int) -> str:
    """The part of one command's output Codex shows the model: all of it up to the limit, else its first and last
    halves of the limit, with the middle cut."""
    if len(output) <= limit:
        return output
    half = limit // 2
    return f"{output[:half]}\n{output[len(output) - half :]}"


def read_session(events: Path, shown_chars: int) -> list[Command] | None:
    """The shell commands Codex recorded in its event stream, or None when the agent left no stream to count from. A
    line that is not an event, as a stream cut off mid-line ends with, is passed over."""
    try:
        lines = events.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    commands = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") if isinstance(event, dict) and event.get("type") == "item.completed" else None
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        output = str(item.get("aggregated_output") or "")
        commands.append(Command(str(item.get("command") or ""), shown_part(output, shown_chars)))
    return commands


def telling_lines(text: str) -> set[str]:
    """The distinct lines long enough to show that a file's text came back."""
    return {line.strip() for line in text.splitlines() if len(line.strip()) >= TELLING_LINE}


def came_back(lines: set[str], shown: str) -> bool:
    """Whether at least half of a file's telling lines are in the output the model was shown, in any command and in
    any order, each whole: a search that returned a few of its lines does not count as reading it."""
    needed = (len(lines) + 1) // 2
    found = 0
    for seen, line in enumerate(lines, start=1):
        found += line in shown
        if found >= needed:
            return True
        if found + len(lines) - seen < needed:
            return False
    return False


def shown_whole(name: str, text: str, session: Sequence[Command]) -> bool:
    """Whether a command that names a file was shown its whole text. A file with no telling line is read only so: its
    short lines are in any output, and show nothing wherever else they came back."""
    return any(name in command.text and text in command.shown for command in session)


def files_read(session: Sequence[Command], files: Mapping[str, Path]) -> tuple[int, list[str]]:
    """How many of the package files the brief listed can be compared, and which of them did not come back in the
    output the model was shown. files gives each by its path in Mandu, which a command that names it holds. A file the
    launcher cannot read now, or one with no text, is left out of both."""
    shown = "\n".join(command.shown for command in session)
    compared, missing = 0, []
    for name, path in files.items():
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not text:
            continue
        compared += 1
        lines = telling_lines(text)
        if not (came_back(lines, shown) if lines else shown_whole(name, text, session)):
            missing.append(name)
    return compared, missing


@dataclass(frozen=True)
class Standing:
    """What stands in workspace/ that a session's Draft claims and proposals are counted from."""

    drafts: Mapping[int, PostDraft | None]  # each due day's Draft, None where there is none
    proposals: Mapping[str, str]  # each package-change proposal in incoming/, by its file's name: the file's SHA-256


def standing(plan: posts.Plan | None, areas: Areas, products: Sequence[str]) -> Standing:
    """What stands in workspace/ as it is now: the Draft of each calendar day the brief asks one for, every day it
    lists that the Founder has not approved, and each package-change proposal in review-queue/incoming/. A Draft or a
    file in incoming/ that is there and cannot be read raises, as does a folder that cannot be searched or listed:
    nothing then says whether a session wrote or changed what is in it. Anything else in incoming/ is passed over,
    since the launcher queues no proposal from it."""
    drafts: dict[int, PostDraft | None] = {}
    for day_plan in plan.days if plan is not None else []:
        if day_plan.approved:
            continue
        path = plan.draft_path(day_plan.day.day)
        try:
            os.lstat(path)
        except FileNotFoundError:
            drafts[day_plan.day.day] = None
            continue
        draft, problem = posts.read_draft(areas, path)
        if problem:
            raise ConfigError(problem)
        drafts[day_plan.day.day] = draft
    incoming = areas.path("review_queue", INCOMING)
    if not areas.real_folder(incoming):
        raise ConfigError(f"`{areas.relative(incoming)}` is not a real folder")
    proposals = {}
    for name in sorted(os.listdir(incoming)):
        path = incoming / name
        if not stat.S_ISREG(os.lstat(path).st_mode):
            continue
        try:
            data = read_plain(path)
        except UnsafeFile as error:
            raise ConfigError(f"`{areas.relative(path)}` could not be read ({error})") from error
        try:
            item = exchange.check_item(data.decode("utf-8"), products).item
        except UnicodeDecodeError:
            continue
        if item is not None and item.kind == "package-change-proposal":
            proposals[name] = hashlib.sha256(data).hexdigest()
    return Standing(drafts, proposals)


@dataclass(frozen=True)
class Claims:
    """The claims of the Drafts one session wrote or changed, out of the Drafts due."""

    due: int = 0
    written: int = 0  # Drafts due that are new, or differ from what stood before the agent started
    listed: int = 0
    cited: int = 0  # claims that name a code location

    @property
    def uncited(self) -> int:
        return self.listed - self.cited


@dataclass(frozen=True)
class Proposals:
    """The package-change proposals a run queued from incoming/, as one session's count or as the whole run's."""

    written: int = 0  # those the session wrote or changed; for a run, those any of its sessions did
    left: int = 0  # for a run alone: those an earlier run left there


@dataclass(frozen=True)
class Written:
    """What one session wrote or changed, of what stands in workspace/ once the agent has ended."""

    claims: Claims
    proposals: Mapping[str, bool]  # each proposal in incoming/, by its file's name: whether it is this session's


def written(before: Standing, after: Standing) -> Written:
    """What this session wrote or changed. before and after are standing as it was before the agent started and once
    it has ended: a Draft or a proposal is the session's when it is new or its fingerprint differs, so one an earlier
    run left is not counted as its work. A claim item that cannot be read names no code location."""
    marks = {day: draft.sha256 for day, draft in before.drafts.items() if draft is not None}
    drafts = [draft for day, draft in after.drafts.items() if draft is not None and draft.sha256 != marks.get(day)]
    listed = sum(len(draft.claims) + draft.unread_claims for draft in drafts)
    cited = sum(not none(claim.location) for draft in drafts for claim in draft.claims)
    proposals = {name: mark != before.proposals.get(name) for name, mark in after.proposals.items()}
    return Written(Claims(len(after.drafts), len(drafts), listed, cited), proposals)


def count_proposals(proposals: Mapping[str, bool], queued: Collection[str], whole_run: bool = False) -> Proposals:
    """The proposals the launcher queued from incoming/, told apart by who wrote them. proposals is Written.proposals
    and queued are the names of the files there that the launcher queued. For one session of a run, only its own are
    counted: what else was queued is another session's or an earlier run's. For the whole run, read from before its
    first session to after its last, the rest are the ones an earlier run left."""
    own = [session_s for name, session_s in proposals.items() if name in queued]
    return Proposals(sum(own), len(own) - sum(own) if whole_run else 0)


@dataclass(frozen=True)
class Work:
    """One session's counts. files_not_read is None when the agent left no event stream, and claims and proposals are
    None when what stood in workspace/ could not be read before the session started or once it had ended; nothing is
    then said of them."""

    files_listed: int = 0
    files_not_read: tuple[str, ...] | None = None
    claims: Claims | None = None
    proposals: Proposals | None = None

    @property
    def files_read(self) -> int | None:
        return None if self.files_not_read is None else self.files_listed - len(self.files_not_read)

    def as_json(self) -> dict[str, object]:
        return {
            "package_files_listed": self.files_listed,
            "package_files_read": self.files_read,
            "package_files_not_read": None if self.files_not_read is None else list(self.files_not_read),
            "claims_with_code_location": None if self.claims is None else self.claims.cited,
            "claims_without_code_location": None if self.claims is None else self.claims.uncited,
            "proposals_queued": None if self.proposals is None else self.proposals.written,
        }


def measure(
    events: Path, shown_chars: int, files: Mapping[str, Path], claims: Claims | None, proposals: Proposals | None
) -> Work:
    """Count one session's work once every session has ended and the run's items are taken in. files are the package
    files the session's brief listed, by their paths in Mandu; claims and proposals are the session's Draft claims
    and the proposals of its own that were queued, or None when they could not be counted."""
    session = read_session(events, shown_chars)
    listed, missing = files_read(session, files) if session is not None else (len(files), None)
    return Work(listed, None if missing is None else tuple(missing), claims, proposals)


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def names(count: int) -> str:
    return f"{count} name" + ("s" if count == 1 else "")


def claim_line(claims: Claims | None, whole_run: bool = False) -> str:
    """The Draft claims count, saying which Drafts it is of, or why there is none: one session's, or with whole_run
    the run's sessions' together."""
    who, has = ("the sessions of this run", "they have") if whole_run else ("this session", "it has")
    if claims is None:
        return "Draft claims: not counted; the launcher problems say why"
    if not claims.due:
        return "Draft claims: none to count; no post Draft was due"
    if not claims.written:
        return (
            f"Draft claims: {who} wrote or changed none of the {plural(claims.due, 'Draft')} due, so {has} no Draft"
            " claims to count"
        )
    return (
        f"Draft claims in the {claims.written} of {plural(claims.due, 'due Draft')} {who} wrote or changed:"
        f" {claims.listed} listed, {names(claims.cited)} a code location and {names(claims.uncited)} none"
    )


def proposal_line(proposals: Proposals | None, whole_run: bool = False) -> str:
    """The proposals count: one session's own, or with whole_run the run's sessions' own and beside it any an earlier
    run left that this run queued. It is of the package-change proposals in review-queue/incoming/ and says so: an
    Angle or a Hook a session proposes from Listening goes through review-queue/angles/ and is accounted for under
    Listening in the report."""
    who = "the sessions of this run" if whole_run else "this session"
    if proposals is None:
        return f"Proposals {who} wrote to incoming/: not counted; the launcher problems say why"
    line = f"Proposals {who} wrote to incoming/: {proposals.written} queued"
    if proposals.left:
        were = "was" if proposals.left == 1 else "were"
        line += f"; {proposals.left} more queued in this run {were} left by an earlier run"
    return line


def file_line(work: Work) -> str:
    """The package files count: how many of the files the session's brief listed came back to the model."""
    if work.files_not_read is None:
        return "Package files read: not counted; the agent left no record of a session to count from"
    if not work.files_listed:
        return "Package files read: none to count; this session's brief listed no package file"
    files = (
        f"Package files read: {work.files_read} of the {work.files_listed} the brief listed, counting a file as"
        " read when at least half of its lines came back in output the model was shown"
    )
    if 0 < len(work.files_not_read) <= NAMED_AT_MOST:
        files += f". Not read: {', '.join(f'`{name}`' for name in work.files_not_read)}"
    return files


def count_lines(work: Work) -> list[str]:
    """The launcher's counts of one session, one to a line, each saying what it counts."""
    return [f"{file_line(work)}.", f"{claim_line(work.claims)}.", f"{proposal_line(work.proposals)}."]


def summary(work: Work, drafts: bool = True, items: bool = True) -> str:
    """One session's counts in one sentence, for the top of the run report. A count the session was not asked for
    is left out while it has nothing to say: drafts says whether it is the session that writes post Drafts, and items
    whether it may write proposals to incoming/."""
    parts = []
    if work.files_not_read is not None and work.files_listed:
        parts.append(f"{work.files_read} of {plural(work.files_listed, 'package file')} read")
    claims = work.claims
    if claims is None:
        parts.append("Draft claims not counted")
    elif claims.written:
        parts.append(
            f"{claims.cited} of {plural(claims.listed, 'Draft claim')} with a code location in the {claims.written} of"
            f" {plural(claims.due, 'due Draft')} this session wrote or changed"
        )
    elif claims.due and drafts:
        parts.append(f"none of the {plural(claims.due, 'Draft')} due written or changed")
    if work.proposals is None:
        parts.append("proposals not counted")
    elif work.proposals.written or items:
        parts.append(f"{plural(work.proposals.written, 'proposal')} this session wrote to incoming/ queued")
    return ", ".join(parts)
