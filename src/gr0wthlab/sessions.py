"""The weekly run's sessions: one sandboxed agent session for each workflow that has work due, in a fixed order.

A run used to be one session that did every workflow's work, so each workflow added to it made that session longer
for every other. Now the launcher starts a fresh Codex process for each workflow, one after another, each with the
same command, permission profile, and closed network, each with its own task definition, brief, and time limit, and
takes in what they all wrote once the last has ended. Nothing passes from one session to the next but the files in
workspace/.

The order is fixed here, not in configuration, because it follows from what each session needs: the package review
first, so every later session can read what it proposed; the Weekly Read next, so the post Drafts session can read its
memo; the post Drafts before filming, since an edit record runs
exactly as long as its day's Draft; the rejection reasons last, so their proposals can take account of every proposal
the run already holds. A workflow with nothing due starts no session, and which sessions a run starts is decided once,
before the first.

A task definition is put together here from reviewed files under src/instructions/weekly-run/: the part every session
shares, then the shared parts a workflow uses, then the workflow's own. A rule that binds every session is therefore
written once.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from . import attempts, codex, process
from .boundary import ConfigError

if TYPE_CHECKING:
    from . import work

# Where the reviewed task definitions are, from the repository root.
FOLDER = PurePosixPath("src/instructions/weekly-run")
COMMON = "common"
# The shared parts a workflow's definition can carry besides the common one, and what each is for.
ITEMS = "items"  # writing a package-change proposal to review-queue/incoming/
MESSAGES = "messages"  # writing a message Draft
SHARED = (ITEMS, MESSAGES)
# The line every session's summary ends with: its own account of whether it finished its steps.
COMPLETE = "Session: complete"
INCOMPLETE = "Session: incomplete"
# How much of a session's closing line the report quotes.
WORD_LIMIT = 300
# What the model's provider says when it will not serve a request now, in Codex's last reported error.
PROVIDER_REFUSAL = re.compile(r"\b429\b|too many requests|rate limit|usage limit", re.IGNORECASE)
# The launcher's own words for an error it recognizes that way, and for one it does not: neither repeats the error.
# The class is of the error alone: it says nothing of what the agent did before it, which the launcher counts and
# takes in as it does any session's.
REFUSED = "an error the launcher recognizes as the model's provider refusing or limiting the request"
REPORTED = "an error Codex reported"
# Where the error itself is: the run's record in the log folder, which is never committed and never sent to Mandu.
UNQUOTED = "whose own text is only in the run's local log"


# Which package files a session's brief lists, and so which the launcher counts as read or not read by it.
ALL = "all"  # every file of the snapshot
NEEDED = "needed"  # the files of the sources the Product registry says its workflow's output needs
NONE = "none"  # none: its brief holds everything it works from


@dataclass(frozen=True)
class Workflow:
    """One workflow that needs the agent. key names its session in records, logs, and configuration; title is how the
    brief and the run report name it; output is the output in config/run.json that its session's trouble leaves
    incomplete; files says which package files its brief lists; shared are the shared parts its task definition
    carries."""

    key: str
    title: str
    output: str
    files: str = NEEDED
    shared: tuple[str, ...] = ()

    @property
    def writes_items(self) -> bool:
        return ITEMS in self.shared


# In the order a run starts them.
WORKFLOWS = (
    Workflow("package-review", "Package review", "package-review", ALL, (ITEMS,)),
    Workflow("weekly-read", "Weekly Read", "weekly-read", NEEDED, (ITEMS,)),
    Workflow("post-drafts", "Post Drafts", "post-drafts", NEEDED, (ITEMS,)),
    Workflow("filming", "Filming", "filming-plan", NONE),
    Workflow("beta-recruiting", "Beta Cohort recruiting", "beta-recruiting", NEEDED),
    Workflow("listening", "Listening", "listening", NEEDED, (MESSAGES,)),
    Workflow("outreach", "Outreach", "outreach-drafts", NEEDED, (MESSAGES,)),
    Workflow("learning", "Rejection reasons", "rejection-codes", NONE, (ITEMS,)),
)
KEYS = tuple(workflow.key for workflow in WORKFLOWS)
# The one workflow whose output the agent's closing line decides: nothing else can tell whether a review was finished.
REVIEW = "package-review"
# The one workflow whose session writes post Drafts, so the one a count of no Draft written says something of.
POSTS = "post-drafts"


def workflow(key: str) -> Workflow:
    return next(found for found in WORKFLOWS if found.key == key)


def parts(found: Workflow) -> tuple[str, ...]:
    """The files a workflow's task definition is put together from, in order, by their names without `.md`."""
    return (COMMON, *found.shared, found.key)


def definition_files(repo_root: Path, found: Workflow) -> list[Path]:
    return [repo_root / FOLDER / f"{name}.md" for name in parts(found)]


def compose(repo_root: Path, found: Workflow) -> str:
    """One session's task definition: the common part, the shared parts its workflow uses, then its own. A part that
    cannot be read stops the run before any session starts."""
    texts = []
    for path in definition_files(repo_root, found):
        try:
            texts.append(path.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeDecodeError) as error:
            raise ConfigError(f"the task definition part {path} could not be read: {error}") from error
        if not texts[-1]:
            raise ConfigError(f"the task definition part {path} is empty")
    return "\n\n".join(texts) + "\n"


def definitions(repo_root: Path) -> dict[str, str]:
    """Every workflow's task definition, by its key, read before a run starts its first session."""
    return {found.key: compose(repo_root, found) for found in WORKFLOWS}


def last_error(events: Path) -> str:
    """The last error Codex reported in a session's event stream, as codex.last_error reads it, or "" when it reported
    none or the stream cannot be read. It is text Codex or the model's provider wrote, so it goes to the run's record
    in the log folder and nowhere else: the launcher reads it only to class it (Session.failure)."""
    try:
        return codex.last_error(events.read_text(encoding="utf-8", errors="replace")) or ""
    except OSError:
        return ""


@dataclass
class Session:
    """What one run knows of one workflow's session: whether it had work due, and once it was started, the launcher's
    record of it and what the launcher read and counted of it."""

    workflow: Workflow
    due: bool = False
    why: str = ""  # why it has no session, when nothing was due
    limit: float = 0.0  # a session's time limit in seconds, from config/run.json
    record: Mapping[str, object] = field(default_factory=dict)  # the launcher's record of it; empty until it is tried
    brief: str = ""  # its brief, relative to ledger/
    summary: str = ""  # the agent's closing summary, cut to what the report quotes
    closing: str = ""  # the last line of the agent's whole summary
    error: str = ""  # Codex's last reported error, when it reported one: for the log folder, never for a report
    usage: Mapping[str, int] | None = None
    cost: float | None = None
    work: work.Work | None = None  # what the launcher counted of it, once it has ended
    incomplete: tuple[str, ...] = ()  # the titles of the outputs its falling short leaves incomplete

    @property
    def key(self) -> str:
        return self.workflow.key

    @property
    def title(self) -> str:
        return self.workflow.title

    @property
    def tried(self) -> bool:
        """Whether the run came to this session, started or not."""
        return bool(self.record)

    @property
    def started(self) -> bool:
        """Whether Codex itself was started for it, after the preflight passed."""
        return bool(self.record.get("agent_started"))

    @property
    def timed_out(self) -> bool:
        return bool(self.record.get("timed_out"))

    @property
    def out_of_time(self) -> bool:
        """Whether it was not started because the run's bound on all its sessions together left it no time."""
        return bool(self.record.get("out_of_time"))

    @property
    def exit_code(self) -> object:
        return self.record.get("exit_code")

    @property
    def finished(self) -> bool:
        """Whether its agent ended by itself without an error."""
        return self.started and not self.timed_out and self.exit_code == 0

    @property
    def confirmed(self) -> bool:
        return self.closing == COMPLETE

    @property
    def seconds(self) -> float | None:
        value = self.record.get("agent_seconds")
        return None if value is None else float(value)

    @property
    def asleep(self) -> float:
        """About how many seconds of its time the Mac was asleep; 0 when it did not run or the Mac stayed awake."""
        record = self.record
        return attempts.asleep_for(
            float(record.get("agent_seconds") or 0), float(record.get("agent_awake_seconds") or 0)
        )

    @property
    def given(self) -> float:
        """The limit it ran with: a session's, or what the run's bound on all sessions left, when that was less."""
        return float(self.record.get("time_limit_seconds") or self.limit)

    @property
    def limit_text(self) -> str:
        return process.limit_text(self.given)

    @property
    def stop(self) -> process.Stop:
        """What stopping it at its limit took, as the launcher's record keeps it."""
        return process.Stop.from_json(self.record.get("stopped") or {})

    @property
    def shortfall(self) -> str | None:
        """How it fell short, as the record of the week's run names an ending, or None when it did not: it had no work
        due, or its agent ended by itself without an error."""
        if not self.due or self.finished:
            return None
        if not self.started:
            return attempts.TIMED_OUT if self.out_of_time else attempts.NOT_STARTED
        return attempts.TIMED_OUT if self.timed_out else attempts.FAILED

    def cut(self) -> str:
        """What a limit shorter than a session's says of itself, or ""."""
        return " (what the run's bound on all its sessions left it)" if self.given < self.limit else ""

    def failure(self) -> str:
        """What a session whose agent ended with an error ended with, in the launcher's own words, for every place
        that tells it: its exit code, and where Codex reported an error, the launcher's class of that error and where
        the error is. The error is never quoted."""
        code = f"exit code {self.exit_code}"
        if not self.error:
            return code
        return f"{code} and {REFUSED if PROVIDER_REFUSAL.search(self.error) else REPORTED}, {UNQUOTED}"

    def gap(self) -> str:
        """Why every output that needed this session is incomplete, in the real terms, or "" when it had no work due
        or its agent finished."""
        if not self.due or self.finished:
            return ""
        if not self.tried:
            return "its session was not reached"
        if not self.started:
            return f"its session did not start: {self.record.get('error') or 'see Sessions in the run report'}"
        if self.timed_out:
            return f"its session was stopped at its {self.limit_text} time limit{self.cut()}"
        return f"its session ended with {self.failure()}"

    def ended(self) -> str:
        """How it ended, for the report's table."""
        if not self.due:
            return f"no session: {self.why}"
        if not self.tried:
            return "not reached"
        if not self.started:
            return f"did not start: {self.record.get('error') or 'see below'}"
        if self.timed_out:
            return f"stopped at its {self.limit_text} time limit{self.cut()}"
        if self.exit_code != 0:
            return f"ended with {self.failure()}"
        return "ended by itself, exit code 0"

    def word(self) -> str:
        """The agent's own closing line, quoted as its word, or that it left none. A line that is neither closing
        line, as one wrapped in backticks is not, is quoted as it stands, since the launcher reads it as no
        confirmation."""
        if not self.summary.strip():
            return "none; the agent left no summary"
        line = " ".join(self.closing.split())
        shown = line if len(line) <= WORD_LIMIT else line[:WORD_LIMIT].rstrip() + "..."
        if self.closing == COMPLETE or self.closing.startswith(INCOMPLETE):
            return f'"{shown}"'
        return (
            f'its last line, "{shown}", is neither of the closing lines the launcher accepts, the plain text'
            f" `{COMPLETE}` or `{INCOMPLETE}: ...`"
        )

    def reason(self) -> str:
        """The agent's own reason after `Session: incomplete:`, without the closing punctuation that would clash with
        the sentence it is quoted in."""
        return self.closing[len(INCOMPLETE) :].lstrip(":").strip().rstrip(".!;:, ")


def started(sessions: Sequence[Session]) -> list[Session]:
    return [session for session in sessions if session.started]


def due(sessions: Sequence[Session]) -> list[Session]:
    return [session for session in sessions if session.due]


def short(sessions: Sequence[Session]) -> list[Session]:
    """The sessions that fell short, in the order the run came to them."""
    return [session for session in sessions if session.shortfall]


def header(sessions: Sequence[Session], session: Session) -> str:
    """The line of a session's prompt that names it among the sessions this run starts."""
    keys = [found.key for found in due(sessions)]
    return (
        f"Session: {session.key}, the {session.title} session, {keys.index(session.key) + 1} of the"
        f" {len(keys)} this run starts ({', '.join(keys)})."
    )
