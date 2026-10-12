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

# A line shorter than this is too common to show that one file's text came back, unless the file holds no longer one.
TELLING_LINE = 24
CHECKS = ("check-incoming", "check-drafts", "check-beta-drafts")
# The report names the package files that were not read only when they are this few; the run's log record names all.
NAMED_AT_MOST = 6


@dataclass(frozen=True)
class Session:
    """One agent session, from Codex's event stream: the shell commands and file edits that ran to their end."""

    commands: int = 0
    cut: int = 0  # commands that returned more output than Codex shows the model
    code_reads: int = 0  # commands that named the Product's code checkout
    checks: int = 0  # commands that ran one of the launcher's own checks
    edits: int = 0
    shown: str = ""  # every command's output as Codex shows it to the model, one after another


def shown_part(output: str, limit: int) -> str:
    """The part of one command's output Codex shows the model: all of it up to the limit, else its first and last
    halves of the limit, with the middle cut."""
    if len(output) <= limit:
        return output
    half = limit // 2
    return f"{output[:half]}\n{output[len(output) - half :]}"


def read_session(events: Path, shown_chars: int, code_checkout: Path | None = None) -> Session | None:
    """The session Codex recorded in its event stream, or None when the agent left no stream to count from. A line that
    is not an event, as a stream cut off mid-line ends with, is passed over."""
    try:
        lines = events.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    commands = cut = code_reads = checks = edits = 0
    shown = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") if isinstance(event, dict) and event.get("type") == "item.completed" else None
        if not isinstance(item, dict):
            continue
        if item.get("type") == "file_change":
            edits += 1
        if item.get("type") != "command_execution":
            continue
        command, output = str(item.get("command") or ""), str(item.get("aggregated_output") or "")
        commands += 1
        cut += len(output) > shown_chars
        code_reads += code_checkout is not None and str(code_checkout) in command
        checks += any(f"gr0wthlab {check}" in command for check in CHECKS)
        shown.append(shown_part(output, shown_chars))
    return Session(commands, cut, code_reads, checks, edits, "\n".join(shown))


def telling_lines(text: str) -> set[str]:
    """The distinct lines that show a file's text came back: its longer lines, or every line when it has none."""
    lines = {line.strip() for line in text.splitlines()} - {""}
    return {line for line in lines if len(line) >= TELLING_LINE} or lines


def came_back(text: str, shown: str) -> bool:
    """Whether at least half of a file's telling lines are in the output the model was shown, in any command and in
    any order, each whole: a search that returned a few of its lines does not count as reading it."""
    lines = telling_lines(text)
    needed = (len(lines) + 1) // 2
    found = 0
    for seen, line in enumerate(lines, start=1):
        found += line in shown
        if found >= needed:
            return True
        if found + len(lines) - seen < needed:
            return False
    return False


def files_read(session: Session, files: Mapping[str, Path]) -> tuple[int, list[str]]:
    """How many of the package files the brief listed can be compared, and which of them did not come back in the
    output the model was shown. A file the launcher cannot read now, or one with no text, is left out of both."""
    compared, missing = 0, []
    for name, path in files.items():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not telling_lines(text):
            continue
        compared += 1
        if not came_back(text, session.shown):
            missing.append(name)
    return compared, missing


def due_days(plan: posts.Plan) -> list[int]:
    """The calendar days the brief asks a Draft for: every day it lists that the Founder has not approved."""
    return [day_plan.day.day for day_plan in plan.days if not day_plan.approved]


def draft_marks(plan: posts.Plan | None, areas: Areas) -> dict[int, str | None]:
    """Each due day's Draft as it stands on disk, by its fingerprint, or None where there is none that can be read;
    taken before the agent starts and again after it, the difference is what this run wrote."""
    if plan is None:
        return {}
    marks = {}
    for number in due_days(plan):
        draft, _ = posts.read_draft(areas, plan.draft_path(number))
        marks[number] = draft.sha256 if draft is not None else None
    return marks


@dataclass(frozen=True)
class Work:
    """One run's counts. session is None when the agent left no event stream, and then nothing is said of it."""

    session: Session | None = None
    files_listed: int = 0
    files_not_read: tuple[str, ...] = ()
    days_due: int = 0
    drafts_present: int = 0
    drafts_written: int = 0
    claims: int = 0
    claims_cited: int = 0  # claims that name a code location
    claims_found: int = 0  # of those, the ones whose quoted code the launcher found at that location
    queued: int = 0  # items the agent wrote that the launcher queued
    proposals: int = 0  # of those, package-change proposals
    set_aside: int = 0
    shown_chars: int = 0

    @property
    def files_read(self) -> int:
        return self.files_listed - len(self.files_not_read)

    @property
    def claims_uncited(self) -> int:
        return self.claims - self.claims_cited

    def as_json(self) -> dict[str, object]:
        session = self.session
        return {
            "commands": session.commands if session else None,
            "commands_output_cut": session.cut if session else None,
            "commands_reading_product_code": session.code_reads if session else None,
            "commands_running_checks": session.checks if session else None,
            "file_edits": session.edits if session else None,
            "package_files_listed": self.files_listed,
            "package_files_read": self.files_read if session else None,
            "package_files_not_read": list(self.files_not_read) if session else None,
            "draft_days_due": self.days_due,
            "drafts_present": self.drafts_present,
            "drafts_written": self.drafts_written,
            "claims": self.claims,
            "claims_with_code_location": self.claims_cited,
            "claims_without_code_location": self.claims_uncited,
            "claims_found_at_location": self.claims_found,
            "items_queued": self.queued,
            "proposals_queued": self.proposals,
            "items_set_aside": self.set_aside,
        }


def measure(
    events: Path,
    shown_chars: int,
    files: Mapping[str, Path],
    plan: posts.Plan | None,
    before: Mapping[int, str | None],
    areas: Areas,
    kinds: Sequence[str],
    set_aside: int,
) -> Work:
    """Count one run's work once the agent has ended and its items are taken in. files are the package files the brief
    listed, by the name the report gives each; before is draft_marks as it was before the agent started; kinds are the
    kinds of the items the agent wrote that the launcher queued."""
    checkout = plan.code.checkout if plan is not None else None
    session = read_session(events, shown_chars, checkout)
    listed, missing = files_read(session, files) if session else (len(files), [])
    present = written = claims = cited = found = 0
    days = due_days(plan) if plan is not None else []
    for number in days:
        draft, _ = posts.read_draft(areas, plan.draft_path(number))
        if draft is None:
            continue
        present += 1
        written += draft.sha256 != before.get(number)
        for claim in draft.claims:
            claims += 1
            if not none(claim.location):
                cited += 1
                found += plan.code.verify(claim.location, claim.excerpt) is None
    return Work(
        session,
        listed,
        tuple(missing),
        len(days),
        present,
        written,
        claims,
        cited,
        found,
        len(kinds),
        sum(1 for kind in kinds if kind == "package-change-proposal"),
        set_aside,
        shown_chars,
    )


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def count_lines(work: Work) -> list[str]:
    """The launcher's counts, one to a line, each saying what it counts."""
    session = work.session
    if session is None:
        lines = ["Commands run: none recorded; the agent left no record of a session to count from."]
    else:
        commands = f"Commands run: {session.commands}"
        if session.commands:
            commands += (
                f"; {session.code_reads} of them read the Product's code, {session.checks} ran one of the launcher's"
                f" checks, and {session.cut} returned more than the {work.shown_chars:,} characters Codex shows the"
                " model of one command's output, so the middle of that output was cut"
            )
        files = (
            f"Package files read: {work.files_read} of the {work.files_listed} the brief listed, counting a file as"
            " read when at least half of its lines came back in output the model was shown"
        )
        if 0 < len(work.files_not_read) <= NAMED_AT_MOST:
            files += f". Not read: {', '.join(f'`{name}`' for name in work.files_not_read)}"
        lines = [f"{commands}.", f"{files}.", f"File edits: {session.edits}."]
    if work.days_due:
        lines.append(
            f"Post Drafts: {work.drafts_present} of the {plural(work.days_due, 'day')} due have a Draft;"
            f" {work.drafts_written} written or changed this run."
        )
    else:
        lines.append("Post Drafts: no calendar day was due.")
    if work.claims:
        lines.append(
            f"Draft claims: {work.claims} listed; {work.claims_cited} name a code location, where the launcher found"
            f" the quoted code for {work.claims_found}; {work.claims_uncited} name none."
        )
    elif work.drafts_present:
        lines.append("Draft claims: none listed.")
    lines.append(
        f"Review Queue items the agent wrote: {work.queued} queued, {plural(work.proposals, 'package-change proposal')}"
        f" among them; {work.set_aside} set aside."
    )
    return lines


def summary(work: Work) -> str:
    """The counts in one sentence, for the top of the run report."""
    parts = []
    if work.session is not None:
        parts.append(plural(work.session.commands, "command"))
        parts.append(f"{work.files_read} of {plural(work.files_listed, 'package file')} read")
    if work.days_due:
        parts.append(f"{work.drafts_written} of {plural(work.days_due, 'due Draft')} written")
    if work.claims:
        parts.append(f"{work.claims_cited} of {plural(work.claims, 'Draft claim')} with a code location")
    parts.append(f"{plural(work.proposals, 'proposal')} queued")
    return ", ".join(parts)
