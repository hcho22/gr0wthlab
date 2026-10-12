"""What the agent's session did, as the launcher counts it.

Every count comes from Codex's event stream for the session, from the Draft files the run left in workspace/, or from
the Review Queue, never from the agent's words. The run report shows them beside the agent's own `Review:` line, so a
session that did little and says it finished does not read better than one that did more and says it stopped. The
counts inform the Founder: nothing is queued, blocked, or marked incomplete because of them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import posts
from .areas import Areas
from .drafts import none

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
class Work:
    """One run's counts. files_not_read is None when the agent left no event stream, and then nothing is said of the
    package files."""

    files_listed: int = 0
    files_not_read: tuple[str, ...] | None = None
    claims: int = 0
    claims_cited: int = 0  # claims that name a code location
    proposals: int = 0  # package-change proposals the agent wrote that the launcher queued

    @property
    def files_read(self) -> int | None:
        return None if self.files_not_read is None else self.files_listed - len(self.files_not_read)

    @property
    def claims_uncited(self) -> int:
        return self.claims - self.claims_cited

    def as_json(self) -> dict[str, object]:
        return {
            "package_files_listed": self.files_listed,
            "package_files_read": self.files_read,
            "package_files_not_read": None if self.files_not_read is None else list(self.files_not_read),
            "claims_with_code_location": self.claims_cited,
            "claims_without_code_location": self.claims_uncited,
            "proposals_queued": self.proposals,
        }


def measure(
    events: Path, shown_chars: int, files: Mapping[str, Path], plan: posts.Plan | None, areas: Areas, proposals: int
) -> Work:
    """Count one run's work once the agent has ended and its items are taken in. files are the package files the brief
    listed, by their paths in Mandu; the claims are those of the post Drafts for the days the brief asks a Draft for,
    every day it lists that the Founder has not approved; proposals is how many package-change proposals the agent
    wrote that the launcher queued."""
    session = read_session(events, shown_chars)
    listed, missing = files_read(session, files) if session is not None else (len(files), None)
    claims = cited = 0
    for day_plan in plan.days if plan is not None else []:
        if day_plan.approved:
            continue
        draft, _ = posts.read_draft(areas, plan.draft_path(day_plan.day.day))
        for claim in draft.claims if draft is not None else []:
            claims += 1
            cited += not none(claim.location)
    return Work(listed, None if missing is None else tuple(missing), claims, cited, proposals)


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


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
    if work.claims:
        claims = (
            f"Draft claims: {work.claims} listed; {work.claims_cited} name a code location and {work.claims_uncited}"
            " name none"
        )
    else:
        claims = "Draft claims: none listed"
    proposals = f"Proposals queued: {plural(work.proposals, 'package-change proposal')} the agent wrote"
    return [f"{files}.", f"{claims}.", f"{proposals}."]


def summary(work: Work) -> str:
    """The counts in one sentence, for the top of the run report."""
    parts = []
    if work.files_not_read is not None:
        parts.append(f"{work.files_read} of {plural(work.files_listed, 'package file')} read")
    if work.claims:
        parts.append(f"{work.claims_cited} of {plural(work.claims, 'Draft claim')} with a code location")
    parts.append(f"{plural(work.proposals, 'proposal')} queued")
    return ", ".join(parts)
