"""What the agent's session did, as the launcher counts it.

Every count comes from Codex's event stream for the session, from the Draft files the run left in workspace/, or from
the Review Queue, never from the agent's words. The run report shows them beside the agent's own `Review:` line, so a
session that did little and says it finished does not read better than one that did more and says it stopped. Each is
of this session alone: a Draft an earlier run left is not this session's work, so its claims are not counted again.
The counts inform the Founder: nothing is queued, blocked, or marked incomplete because of them.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import posts
from .areas import Areas
from .boundary import ConfigError
from .drafts import PostDraft, none

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


def due_drafts(plan: posts.Plan | None, areas: Areas) -> dict[int, PostDraft | None]:
    """The Draft of each calendar day the brief asks one for, every day it lists that the Founder has not approved, as
    it stands on disk, or None where there is none. One that is there and cannot be read raises, as does a folder that
    cannot be searched: nothing then says whether a session wrote or changed it."""
    found: dict[int, PostDraft | None] = {}
    for day_plan in plan.days if plan is not None else []:
        if day_plan.approved:
            continue
        path = plan.draft_path(day_plan.day.day)
        try:
            os.lstat(path)
        except FileNotFoundError:
            found[day_plan.day.day] = None
            continue
        draft, problem = posts.read_draft(areas, path)
        if problem:
            raise ConfigError(problem)
        found[day_plan.day.day] = draft
    return found


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


def count_claims(before: Mapping[int, PostDraft | None], after: Mapping[int, PostDraft | None]) -> Claims:
    """The claims of the Drafts this session wrote or changed. before and after are due_drafts as it was before the
    agent started and once it has ended: a Draft is the session's when it is new or its fingerprint differs, so one an
    earlier run left is not counted again. A claim item that cannot be read names no code location."""
    marks = {day: draft.sha256 for day, draft in before.items() if draft is not None}
    written = [draft for day, draft in after.items() if draft is not None and draft.sha256 != marks.get(day)]
    listed = sum(len(draft.claims) + draft.unread_claims for draft in written)
    cited = sum(not none(claim.location) for draft in written for claim in draft.claims)
    return Claims(len(after), len(written), listed, cited)


@dataclass(frozen=True)
class Work:
    """One run's counts. files_not_read is None when the agent left no event stream, and claims is None when a Draft
    due could not be read before the agent started or once it had ended; nothing is then said of the one or the
    other."""

    files_listed: int = 0
    files_not_read: tuple[str, ...] | None = None
    claims: Claims | None = None
    proposals: int = 0  # package-change proposals the agent wrote that the launcher queued

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
            "proposals_queued": self.proposals,
        }


def measure(events: Path, shown_chars: int, files: Mapping[str, Path], claims: Claims | None, proposals: int) -> Work:
    """Count one run's work once the agent has ended and its items are taken in. files are the package files the brief
    listed, by their paths in Mandu; claims are the session's Draft claims, or None when they could not be counted;
    proposals is how many package-change proposals the agent wrote that the launcher queued."""
    session = read_session(events, shown_chars)
    listed, missing = files_read(session, files) if session is not None else (len(files), None)
    return Work(listed, None if missing is None else tuple(missing), claims, proposals)


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def names(count: int) -> str:
    return f"{count} name" + ("s" if count == 1 else "")


def claim_line(claims: Claims | None) -> str:
    """The Draft claims count, saying which Drafts it is of, or why there is none."""
    if claims is None:
        return "Draft claims: not counted; the launcher problems say why"
    if not claims.due:
        return "Draft claims: none to count; no post Draft was due"
    if not claims.written:
        return (
            f"Draft claims: this session wrote or changed none of the {plural(claims.due, 'Draft')} due, so it has no"
            " Draft claims to count"
        )
    return (
        f"Draft claims in the {claims.written} of {plural(claims.due, 'due Draft')} this session wrote or changed:"
        f" {claims.listed} listed, {names(claims.cited)} a code location and {names(claims.uncited)} none"
    )


def count_lines(work: Work) -> list[str]:
    """The launcher's counts, one to a line, each saying what it counts."""
    if work.files_not_read is None:
        files = "Package files read: not counted; the agent left no record of a session to count from"
    else:
        files = (
            f"Package files read: {work.files_read} of the {work.files_listed} the brief listed, counting a file as"
            " read when at least half of its lines came back in output the model was shown"
        )
        if 0 < len(work.files_not_read) <= NAMED_AT_MOST:
            files += f". Not read: {', '.join(f'`{name}`' for name in work.files_not_read)}"
    proposals = f"Proposals queued: {plural(work.proposals, 'package-change proposal')} the agent wrote"
    return [f"{files}.", f"{claim_line(work.claims)}.", f"{proposals}."]


def summary(work: Work) -> str:
    """The counts in one sentence, for the top of the run report."""
    parts = []
    if work.files_not_read is not None:
        parts.append(f"{work.files_read} of {plural(work.files_listed, 'package file')} read")
    claims = work.claims
    if claims is None:
        parts.append("Draft claims not counted")
    elif claims.written:
        parts.append(
            f"{claims.cited} of {plural(claims.listed, 'Draft claim')} with a code location in the {claims.written} of"
            f" {plural(claims.due, 'due Draft')} this session wrote or changed"
        )
    elif claims.due:
        parts.append(f"none of the {plural(claims.due, 'Draft')} due written or changed")
    parts.append(f"{plural(work.proposals, 'proposal')} queued")
    return ", ".join(parts)
