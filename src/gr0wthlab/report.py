"""What a run tells each agent session before it starts (its brief) and the Founder after the run ends (the run
report).

Both are rendered from the launcher's own state, never from anything an agent wrote, except each session's closing
summary, which the report quotes as that agent's account. The report sets each session's closing line beside what the
launcher counted of that session's work (work.py), and says which is which.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import (
    attempts,
    beta,
    exchange,
    filming,
    learning,
    listening,
    outreach,
    package,
    posts,
    process,
    schedule,
    sessions,
    waitlist,
    work,
)
from .attempts import ASLEEP_AT_LEAST, asleep_for
from .exchange import plural
from .package import SKIPPED
from .sessions import INCOMPLETE as SESSION_INCOMPLETE
from .sessions import Session
from .state import Tally, run_tally

COMPLETE = "complete"
INCOMPLETE = "incomplete"
NOT_BUILT = "not built yet"
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")
NOTICE_BODY_LIMIT = exchange.MAX_ITEM_CHARS // 2
__all__ = ["ASLEEP_AT_LEAST", "asleep_for"]


@dataclass
class SourceLine:
    name: str
    status: str
    detail: str = ""
    needed_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class Unusable:
    """A Mandu record the run could not use; its fingerprint changes whenever its name or content does.

    item is the item a decision record is named for, if any.
    """

    name: str
    problems: tuple[str, ...]
    fingerprint: str
    item: str = ""


@dataclass
class RunState:
    """Everything the launcher learned in one run, in the order it learned it."""

    run_id: str
    trigger: str
    started: datetime
    instruction: str
    due: datetime | None = None
    late_after: timedelta = timedelta(minutes=15)
    code: str = ""
    sync: Mapping[str, object] | None = None
    snapshot: list[package.SourceResult] = field(default_factory=list)
    snapshot_file: str = ""
    previous_snapshot: str | None = None
    mandu: str = ""
    sources: list[SourceLine] = field(default_factory=list)
    decisions: list = field(default_factory=list)  # queue.DecisionOutcome, taken in now or before
    unusable: list[Unusable] = field(default_factory=list)
    reported_before: set[str] = field(default_factory=set)  # fingerprints of the unusable records already reported
    sittings: list[exchange.Sitting] = field(default_factory=list)
    queue_before: list[Mapping[str, object]] = field(default_factory=list)
    replaced: dict[str, list[Mapping[str, object]]] = field(default_factory=dict)  # open id: decided items it replaced
    closed_proposals: list[Mapping[str, object]] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    set_aside: list = field(default_factory=list)  # queue.SetAside
    queue_after: list[Mapping[str, object]] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)  # one for each workflow, in the order a run starts them
    titles: Mapping[str, str] = field(default_factory=dict)  # each output of config/run.json: its title in the report
    run_limit: float = 0.0  # the bound on all of this run's sessions together, in seconds
    claims: work.Claims | None = None  # the Draft claims in the Drafts any session of this run wrote or changed
    proposals: work.Proposals | None = None  # the proposals queued from incoming/: the run's sessions', and the rest
    outputs: list[tuple[str, str, str]] = field(default_factory=list)  # title, status, detail
    problems: list[str] = field(default_factory=list)
    notice: str | None = None
    waitlist: waitlist.Reading | None = None
    waitlist_file: str = ""  # the Waitlist Evidence this run wrote, relative to ledger/
    breach_notice: str | None = None
    dispatches: list = field(default_factory=list)  # dispatch.Filing, one per reviewed Dispatch request
    dispatch_unread: list[str] = field(default_factory=list)  # each file a request's filing rests on that was unread
    queue_unread: list[str] = field(default_factory=list)  # each item file an item in incoming/ may repeat, unread
    # Each open item left as it was on a read that could not be made: (its output's title, queue.Stands).
    stood: list = field(default_factory=list)
    queue_title: str = ""  # the Review Queue output's title, which a Dispatch request's item counts under
    tallies: list[Tally] = field(default_factory=list)
    state_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    posts: posts.Plan | None = None
    post_outcome: posts.Outcome | None = None
    posts_problem: str = ""  # why the post Drafts were not prepared or not taken in, when they were not
    filing: str = ""  # where the proposed brand-rules lists stand
    filed: str | None = None  # the brand-rules proposal, when this run filed it
    filming: filming.Filming | None = None
    filming_problem: str = ""  # why filming was not planned, when a Product films and it was not
    beta: beta.Plan | None = None  # Beta Cohort recruiting: the gate, and once it is recorded, the run's plan
    beta_outcome: beta.Outcome | None = None
    beta_problem: str = ""  # why recruiting was not prepared or not taken in, when it was not
    snapshot_sources: str = ""  # this run's working snapshot of the network sources, relative to ledger/
    requests_file: str = ""  # this run's request log, relative to ledger/
    listening: listening.Plan | None = None
    listening_result: listening.Result | None = None
    listening_problem: str = ""  # why Listening was not prepared or not taken in, when it was not
    outreach: outreach.Plan | None = None
    outreach_result: outreach.Result | None = None
    outreach_problem: str = ""
    outreach_filing: str = ""  # where the proposed loss-framing and sponsorship lists stand
    reasons: list = field(default_factory=list)  # learning.Reason, every rejection reason kept before the agent started
    learning: learning.Result | None = None
    learning_problem: str = ""  # why the rejection reasons were not read or coded, when they were not
    guidance: learning.Guidance | None = None  # the agent's Instructions as they were before it started
    put_back: list[str] = field(default_factory=list)  # each change to them the launcher undid, and after which session
    # what a stopped boundary check had left in the areas, removed before the Instructions were remembered
    probe_files_removed: list[str] = field(default_factory=list)
    work_published: list[str] = field(default_factory=list)  # the items Listening and outreach queued this run
    check_work: str = ""  # the command the agent checks its Listening and outreach work with
    attempt: attempts.Attempt | None = None  # a weekly scheduled run: which attempt at the run due, and those before
    slept: float = 0.0  # about how many seconds the Mac was asleep from the run's start to its last session's end

    @property
    def lateness(self) -> timedelta | None:
        if self.due is None:
            return None
        return wall_clock(self.started) - self.due

    @property
    def late(self) -> bool:
        lateness = self.lateness
        return lateness is not None and lateness > self.late_after

    def failed_sources(self) -> list[SourceLine]:
        return [line for line in self.sources if line.status == package.FAILED]

    def session(self, key: str) -> Session | None:
        """One workflow's session, or None when this run planned none, as before its sessions are planned."""
        return next((session for session in self.sessions if session.key == key), None)

    @property
    def ran(self) -> list[Session]:
        """The sessions Codex was started for, in order."""
        return sessions.started(self.sessions)

    @property
    def short(self) -> list[Session]:
        """The sessions that fell short, in order: not started, stopped at a limit, or ended with an error."""
        return sessions.short(self.sessions)

    @property
    def timed_out(self) -> bool:
        """Whether the launcher stopped a session at its time limit, or the run's bound left one no time."""
        return any(session.shortfall == attempts.TIMED_OUT for session in self.sessions)

    @property
    def agent_seconds(self) -> float:
        """The time all of this run's sessions took together, as their limits count it."""
        return sum(session.seconds or 0.0 for session in self.sessions)

    @property
    def asleep(self) -> float:
        """About how many seconds of its sessions' time the Mac was asleep; 0 when none ran or the Mac stayed awake."""
        return sum(session.asleep for session in self.sessions)

    @property
    def usage(self) -> dict[str, int] | None:
        """Codex's token counts, summed over the sessions that reported any; None when none did."""
        reported = [session.usage for session in self.sessions if session.usage]
        return {key: sum(usage.get(key, 0) for usage in reported) for key in USAGE_FIELDS} if reported else None

    @property
    def cost(self) -> float | None:
        priced = [session.cost for session in self.sessions if session.cost is not None]
        return sum(priced) if priced else None

    @property
    def confirmed(self) -> bool:
        """Whether every session that ran ended its summary with the closing line that confirms its work."""
        return all(session.confirmed for session in self.ran)

    @property
    def ending(self) -> str:
        """How the run ended, as the record of the run due at its time keeps it: completed, or as the first session
        that fell short did. Only a weekly scheduled attempt is asked whether its sessions confirmed their work."""
        short = self.short
        confirmed = self.attempt is None or self.confirmed
        return attempts.ending(short[0].shortfall if short else None, self.slept, confirmed)

    @property
    def again(self) -> bool:
        """Whether a fresh run starts by itself after this one: only after a weekly scheduled attempt that the Mac's
        sleep cut short, and only while the run due then may take another."""
        attempt = self.attempt
        return attempt is not None and self.ending == attempts.SLEPT and attempt.number < attempt.limit

    def agent_gap(self, key: str) -> str:
        """Why every output that needs one workflow's session is incomplete this run, or "" when that session
        finished or the workflow had nothing due. One session's trouble is never another workflow's gap."""
        session = self.session(key)
        return session.gap() if session is not None else ""

    def review_gap(self) -> str:
        """Why the package review is incomplete, or "" when it finished or none was due: its session must end
        without an error and end its summary with the line `Session: complete`, so a summary that says otherwise, or
        says nothing, is not a finished review."""
        review = self.session(sessions.REVIEW)
        if review is None or not review.due:
            return ""
        if review.gap():
            return review.gap()
        if review.confirmed:
            return ""
        if review.closing.startswith(SESSION_INCOMPLETE):
            why = review.reason()
            return "the agent did not finish its review" + (f": {why}" if why else "")
        return "the agent did not confirm that it finished every pass"

    def open_item(self, record: Unusable) -> str:
        """The item a record is for when that item is still open as this run leaves the Review Queue, so Mandu must
        replace the record with a valid one; empty otherwise."""
        return record.item if any(entry["id"] == record.item for entry in self.queue_after) else ""

    def reports(self, record: Unusable) -> bool:
        """A record Mandu must replace is reported at every run until it does; any other record only once."""
        return bool(self.open_item(record)) or record.fingerprint not in self.reported_before

    def unusable_to_report(self) -> list[Unusable]:
        return [record for record in self.unusable if self.reports(record)]


def wall_clock(moment: datetime) -> datetime:
    """The Mac's local wall-clock time, the clock launchd schedules by."""
    return moment.astimezone().replace(tzinfo=None)


def due_time(started: datetime, weekly: tuple[str, str], once: str | None = None) -> datetime:
    """When a scheduled run was due: the latest weekly time at or before its start, or the one-off time."""
    local = wall_clock(started)
    if once:
        return datetime.strptime(once, "%Y-%m-%dT%H:%M")
    calendar = schedule.weekly(*weekly)
    python_weekday = (calendar["Weekday"] - 1) % 7
    due = local.replace(hour=calendar["Hour"], minute=calendar["Minute"], second=0, microsecond=0)
    due -= timedelta(days=(local.weekday() - python_weekday) % 7)
    if due > local:
        due -= timedelta(days=7)
    return due


def next_due(after: datetime, weekly: tuple[str, str]) -> datetime:
    """The first weekly time after a moment, in the Mac's local time with its UTC offset."""
    return (due_time(after, weekly) + timedelta(days=7)).astimezone()


def duration(span: timedelta) -> str:
    minutes = int(span.total_seconds() // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = [f"{days} d"] * bool(days) + [f"{hours} h"] * bool(hours) + [f"{minutes} min"]
    return " ".join(parts)


def token_usage(events: Path) -> dict[str, int] | None:
    """Codex's token counts, summed over every turn.completed event of the run."""
    if not events.is_file():
        return None
    totals = dict.fromkeys(USAGE_FIELDS, 0)
    found = False
    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        usage = event.get("usage") if isinstance(event, dict) and event.get("type") == "turn.completed" else None
        if isinstance(usage, dict):
            found = True
            for key in USAGE_FIELDS:
                value = usage.get(key)
                totals[key] += value if isinstance(value, int) else 0
    return totals if found else None


def cost(usage: Mapping[str, int], prices: Mapping[str, float]) -> float:
    """Approximate US dollars at API prices; cached and cache-write tokens are counted within input tokens, and
    reasoning tokens within output tokens."""
    cached = usage.get("cached_input_tokens", 0)
    written = usage.get("cache_write_input_tokens", 0)
    fresh = max(usage.get("input_tokens", 0) - cached - written, 0)
    total = (
        fresh * prices.get("input", 0)
        + cached * prices.get("cached_input", 0)
        + written * prices.get("cache_write_input", prices.get("input", 0))
        + usage.get("output_tokens", 0) * prices.get("output", 0)
    )
    return total / 1_000_000


def moment(when: datetime) -> str:
    """A time on the Mac's wall clock, as every report line states one."""
    return f"{when:%A %Y-%m-%d %H:%M}"


def earlier_attempts(state: RunState) -> str:
    """For a weekly scheduled run that is not the first attempt at the run due then: which attempt it is, and that
    each earlier one was cut short by the Mac's sleep, since only that earns another."""
    attempt = state.attempt
    if attempt is None or not attempt.earlier:
        return ""
    starts = [moment(wall_clock(start)) for start in attempt.earlier]
    if len(starts) == 1:
        were = f"the attempt started {starts[0]} was"
    else:
        were = f"the attempts started {', '.join(starts[:-1])} and {starts[-1]} were"
    return f" This is attempt {attempt.number} of at most {attempt.limit}: {were} cut short by the Mac's sleep."


def start_line(state: RunState) -> str:
    started = moment(wall_clock(state.started))
    if state.trigger != "scheduled":
        return f"On demand, started {started} (Mac local time)."
    due = moment(state.due)
    earlier = earlier_attempts(state)
    if state.late:
        why = earlier or " The Mac was probably asleep or off when it was due."
        return f"Started late: due {due}, started {started}, {duration(state.lateness)} after its time.{why}"
    return f"Scheduled for {due}; started on time at {started}.{earlier}"


def what_follows(state: RunState) -> str:
    """For a weekly scheduled run that did not complete: whether a fresh run starts by itself, and what to do when
    none does. Only the Mac's sleep earns another attempt, and only up to the limit; "" for any other run, a one-off
    scheduled run included."""
    attempt, ending = state.attempt, state.ending
    if attempt is None or ending == attempts.COMPLETED:
        return ""
    if state.again:
        return (
            f"The Mac's sleep cut this run short, so it does not count as the run due {moment(attempt.due)}: a fresh,"
            " whole run starts by itself once the Mac is awake, and nothing is needed from you."
        )
    if ending == attempts.SLEPT:
        return (
            f"The Mac's sleep cut this run short, and it was attempt {attempt.number} of at most {attempt.limit} at the"
            f" run due {moment(attempt.due)}, so no further attempt starts by itself: start a run on demand while the"
            " Mac stays awake (`src/bin/gr0wthlab run`). The limit is `schedule.attempts_per_week` in"
            " `config/run.json`."
        )
    return (
        "No run starts by itself after this one: only a run cut short by the Mac's sleep is run again, and this one"
        f" {attempts.SAID[ending]}. Start one on demand once that is dealt with (`src/bin/gr0wthlab run`)."
    )


def tokens_text(usage: Mapping[str, int]) -> str:
    return (
        f"{usage['input_tokens']:,} input tokens ({usage['cached_input_tokens']:,} cached) "
        f"and {usage['output_tokens']:,} output tokens"
    )


def amount(cost: float) -> str:
    return f"${cost:.2f}" if cost >= 0.1 else f"${cost:.3f}"


def session_cost(session: Session) -> str:
    """One session's approximate cost in a few words, or that there is none to state: Codex reports token counts as
    each turn ends, so a session stopped at its limit leaves at most a part of them, never a zero."""
    if not session.started:
        return "-"
    if not session.usage:
        return "not available" if session.timed_out else "unknown"
    return f"{'at least' if session.timed_out else 'about'} {amount(session.cost)}"


def cost_line(state: RunState) -> str:
    """The run's approximate cost, from the token counts Codex reported for each of its sessions, or that there is
    none to state. A session stopped at its time limit leaves at most a part of its counts, and one that reported
    none leaves nothing to add, so the sum is then a floor, never a zero for work that was done."""
    ran = state.ran
    if not ran:
        return "Approximate cost: none; no agent session was started."
    usage = state.usage
    stopped = [session for session in ran if session.timed_out]
    silent = [session for session in ran if not session.usage]
    if not usage:
        if stopped:
            return "Approximate cost: not available; the agent was stopped before it reported any token counts."
        return "Approximate cost: unknown; the agent reported no token counts."
    over = f", over its {len(ran)} sessions" if len(ran) > 1 else ""
    if stopped or silent:
        missing = [session.title for session in ran if session in stopped or session in silent]
        return (
            f"Approximate cost: at least {amount(state.cost)} at API prices, for the {tokens_text(usage)} that Codex"
            f" reported{over}; what the {' and '.join(missing)} session{'s' if len(missing) > 1 else ''} used beyond"
            " that is not available."
        )
    return f"Approximate cost: about {amount(state.cost)} at API prices, for {tokens_text(usage)}{over}."


def span_text(seconds: float) -> str:
    """How long something took, in hours, minutes, and seconds."""
    minutes, rest = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return " ".join([f"{hours} h"] * bool(hours) + [f"{minutes} min"] * bool(hours or minutes) + [f"{rest} s"])


def probe_files_removed(state: RunState) -> list[str]:
    """What a stopped boundary check had left in the areas and this run removed, as paths from the repository: the
    production clone's pre-run step removes it before its records step can commit it, and every run before it
    remembers the agent's Instructions and again before each session's preflight."""
    before_records = (state.sync or {}).get("probe_files_removed") or []
    by_sessions = [path for session in state.sessions for path in session.record.get("probe_files_removed") or []]
    return [*before_records, *state.probe_files_removed, *by_sessions]


def left_running(session: Session) -> str | None:
    """The launcher problem a stop leaves when it could not show that none of the processes it found is still running;
    the process ids stay in the run report's Sessions section, so the same problem reads the same at every run."""
    stop = session.stop
    if stop.left:
        count = "1 process" if len(stop.left) == 1 else f"{len(stop.left)} processes"
        return (
            f"{count} the {session.title} session started could not be stopped and may still be running; the run"
            " report's Sessions section names each"
        )
    if not stop.proven:
        return (
            f"the process table could not be read after the {session.title} session was stopped, so nothing shows"
            " whether a process it started is still running"
        )
    return None


def file_line(file: package.FileResult) -> str:
    """What happened to one package file this run, after its read, changed, or failed status."""
    if file.status == package.FAILED:
        return f"{file.reason}."
    return {
        "changed": "its fingerprint changed since the previous snapshot",
        "added": "new since the previous snapshot",
        "first read": "first snapshot of this file",
    }.get(str(file.change), "unchanged since the previous snapshot")


def package_changes(state: RunState, only: set[str] | None = None) -> list[str]:
    """What changed in the package since the previous snapshot; with only, among those files alone, as a session's
    brief that lists a part of the package tells it."""
    if state.previous_snapshot is None:
        return ["First snapshot; there is no earlier run to compare with."]
    lines = []
    for result in state.snapshot:
        for file in result.files:
            if file.change in ("changed", "added") and (only is None or file.path in only):
                lines.append(f"- {file.change}: `{file.path}`")
        if only is None:
            lines += [f"- removed: `{path}`" for path in result.removed]
    if only is not None and not lines:
        return [f"None of the files listed above changed since run {state.previous_snapshot}."]
    return lines or [f"Nothing changed since run {state.previous_snapshot}."]


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    return lines + ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]


def decision_lines(state: RunState, taken_only: bool = False) -> list[str]:
    """The decisions taken in this run, then, unless taken_only, each Mandu record this run reports unusable."""
    lines = []
    for outcome in state.decisions:
        decision, entry = outcome.decision, outcome.entry
        if outcome.status != "taken":
            continue
        replaced = (
            f", which `{entry['superseded_by']}` replaced before this decision was taken in"
            if entry.get("superseded_by")
            else ""
        )
        if decision.decision == exchange.APPROVE:
            note = f" Note: {decision.note}" if decision.note else ""
            lines.append(f"- Approved `{decision.item}`{replaced}: {entry['ask']}.{note}")
        else:
            lines.append(f"- Rejected `{decision.item}`{replaced}: {entry['ask']}. Reason: {decision.reason}")
    if not taken_only:
        listed = state.unusable_to_report()
        for record in listed:
            item = state.open_item(record)
            fix = (
                f". Mandu must replace it with a valid record of the decision on `{item}`, which stays undecided until"
                " then"
                if item
                else ""
            )
            lines.append(f"- Could not use `{record.name}`: {'; '.join(record.problems)}{fix}")
        quiet = len(state.unusable) - len(listed)
        if quiet:
            lines.append(
                f"- Not listed again: {plural(quiet, 'record')} that could not be used, reported by an earlier run"
                " and unchanged since."
            )
    return lines


def outcome_text(status: str) -> str:
    return {
        "unknown-item": "no queued item has this identifier",
        "conflict": "it differs from the decision already taken for this item, which stands",
    }[status]


def founder_words(entry: Mapping[str, object]) -> str:
    return "".join(
        f" {label}: {entry[key]}" for key, label in (("reason", "Reason"), ("note", "Note")) if entry.get(key)
    )


def brief_files(state: RunState, session: Session) -> list[package.FileResult]:
    """The package files one session's brief lists, which are also the ones the launcher counts as read or not read
    by it: every file for the package review, the files of the sources the Product registry says its workflow's
    output needs for most, and none where the brief itself holds everything the session works from."""
    which = session.workflow.files
    if which == sessions.NONE:
        return []
    return [
        file
        for result in state.snapshot
        for file in result.files
        if which == sessions.ALL or session.workflow.output in result.source.needed_by
    ]


def failed_for(state: RunState, session: Session) -> list[SourceLine]:
    """The failed sources one session's brief names: the ones its workflow's output needs, so a session is told of
    nothing that blocks another workflow's work alone. A source the launcher alone reads is never named."""
    title = state.titles.get(session.workflow.output, session.workflow.output)
    return [
        line for line in state.failed_sources() if title in line.needed_by and line.name not in beta.LAUNCHER_SOURCES
    ]


def session_rows(state: RunState, current: Session) -> list[list[str]]:
    """The sessions this run starts, as a brief tells them: this one, and each other with whether it comes before
    or after. A workflow with nothing due is not named: a brief holds its own session's work and no word of work
    that has not begun, such as recruiting before the Founder's gate."""
    rows = []
    due = sessions.due(state.sessions)
    for session in due:
        if session is current:
            said = "this session"
        else:
            said = f"its own session, {'before' if due.index(session) < due.index(current) else 'after'} this one"
        rows.append([session.title, said])
    return rows


def render_brief(
    state: RunState,
    session: Session,
    repo_root: Path,
    workspace: Path,
    ledger: Path,
    files: Sequence[package.FileResult] = (),
    standing: Sequence[tuple[str, str]] = (),
    drafts: Sequence[tuple[int, str]] = (),
) -> str:
    """The facts one session works from, written just before it starts: what every session of the run is told, then
    its own workflow's section and nothing of another's. files are the package files it lists, standing is what stands
    in incoming/ now, each file with its ask or why it has none, and drafts is each ready filming day with where its
    post Draft stands."""
    key = session.key
    whole = session.workflow.files == sessions.ALL
    lines = [
        f"# Brief for run {state.run_id}: the {session.title} session",
        "",
        "The launcher wrote this just before you started.",
        "Every Go-To-Market Package file is in the Mandu checkout, at the absolute path listed below;",
        "a Product's own repository holds its code, never its package.",
    ]
    if session.workflow.writes_items:
        lines.append(
            "In the items you write, cite a package file by its path inside the Mandu checkout"
            + (", as in the Changes list." if files else ".")
        )
    lines += [
        "The paths the header lists of the Mandu checkout and every other read-only location in it are readable,",
        "even inside a folder the sandbox otherwise denies, such as /private/tmp.",
        "",
        f"- {start_line(state)}",
        f"- Mandu checkout: `{state.mandu}`",
        f"- Package snapshot: `{ledger / state.snapshot_file}`"
        + (f" (previous: run {state.previous_snapshot})" if state.previous_snapshot else " (the first one)"),
        "",
        "## This run's sessions",
        "",
        "Each workflow with work due this run has a session of its own, in this order; do this session's work and no"
        " other's.",
        "",
    ]
    lines += table(["Workflow", "This run"], session_rows(state, session))
    lines += ["", "## Package files", ""]
    rows = []
    mandu = Path(state.mandu)
    listed = {file.path for file in files}
    if whole:
        for result in state.snapshot:
            if result.reason:
                rows.append([f"`{mandu / result.source.path}`", f"failed: {result.reason}"])
            rows += [[f"`{mandu / file.path}`", f"{file.status}: {file_line(file)}"] for file in result.files]
    else:
        rows = [[f"`{mandu / file.path}`", f"{file.status}: {file_line(file)}"] for file in files]
    if rows:
        if not whole:
            lines += [
                "The package files this session's work needs; read each one, and any other your work turns on.",
                "",
            ]
        lines += table(["File", "This run"], rows)
        lines += ["", "## Changes since the previous snapshot", ""]
        lines += package_changes(state, None if whole else listed)
    else:
        lines.append("This session's own section below holds what it works from; it lists no package file to read.")
    lines += ["", "## Failed sources", ""]
    failed = failed_for(state, session)
    if failed:
        lines.append(
            "A failed source blocks only the work that needs it: never guess what it says, and do everything else."
        )
        if whole:
            lines.append(
                "Review every other package file as usual; only contradictions that involve a failed file go unchecked."
            )
        lines.append("")
        lines += [
            f"- {line.name}: {line.detail} Incomplete without it: {', '.join(line.needed_by) or 'nothing else'}."
            for line in failed
        ]
    else:
        lines.append("None that this session's work needs." if state.failed_sources() else "None.")
    lines += ["", "## Founder decisions taken in this run", ""]
    lines += decision_lines(state, taken_only=True) or ["None."]
    if session.workflow.writes_items:
        lines += [""] + item_lines(state, standing)
    if key == sessions.REVIEW:
        lines += ["", "## Waitlist", ""]
        if state.waitlist is not None:
            evidence = ledger / state.waitlist_file if state.waitlist_file else None
            lines += waitlist_brief(state.waitlist, evidence)
    check = f"{state.check_work} --part {key}" if state.check_work else ""
    context = state.posts.context if state.posts is not None else None
    if key == sessions.POSTS and state.posts is not None:
        lines += [""] + posts.brief_lines(state.posts, repo_root)[:-1] + kept_video_lines(state.filming)
    if key == "filming" and state.filming is not None:
        lines += [""] + filming.brief_lines(state.filming, repo_root)[:-1]
        lines += [""] + draft_lines(state.filming, drafts)
    if key == beta.WORKFLOW and state.beta is not None and not state.beta_problem:
        recruiting = beta.brief_lines(state.beta, repo_root)
        lines += [""] * bool(recruiting) + recruiting[:-1]
    if key == listening.WORKFLOW and state.listening is not None:
        lines += [""] + listening.brief_lines(state.listening, workspace, ledger, mandu, check)
    if key == outreach.WORKFLOW and state.outreach is not None:
        lines += [""] + outreach.brief_lines(state.outreach, context, mandu, check)
    if key == learning.WORKFLOW:
        lines += [""] + learning.brief_lines(state.reasons, workspace)
    lines += ["", "## Where to write", ""]
    if session.workflow.writes_items:
        lines += [
            f"- New items: `{workspace / 'review-queue' / 'incoming'}/<slug>.md`, written with your file-editing tool"
            " (apply_patch): a shell here-document (`<<`) fails here, as the sandbox has no writable temporary folder.",
            f"- Their format: `{repo_root / 'docs' / 'mandu-exchange.md'}`.",
            f"- Check them before you finish: `/usr/bin/python3 {repo_root / 'src/bin/gr0wthlab'} check-incoming`.",
        ]
    else:
        lines.append("- This session's own section above names every file it writes; it writes no item.")
    if key == learning.WORKFLOW and check:
        lines.append(f"- Check your rejection codes: `{check}`.")
    lines += [f"- The launcher's records, which you can read and never write: `{ledger}`.", ""]
    return "\n".join(lines)


def item_lines(state: RunState, standing: Sequence[tuple[str, str]]) -> list[str]:
    """What a session that may write items is told of the Review Queue: what is open, what was decided, and what
    stands in incoming/ that the launcher has not taken in yet."""
    lines = ["## Open Review Queue items", ""]
    if state.queue_before:
        lines += [
            "Do not queue these again; to change one, write a new item with `supersedes: <id>`.",
            "An item filed by the launcher changes only through a reviewed change to its source text, and a post or a"
            " message only through its Draft, so an item that supersedes any of them is refused.",
        ]
        for entry in state.queue_before:
            filed = ", filed by the launcher" if entry.get("origin") else ""
            line = f"- `{entry['id']}` ({entry['kind']}{filed}): {entry['ask']}"
            for earlier in state.replaced.get(str(entry["id"]), ()):
                line += (
                    f". It replaces `{earlier['id']}`, which the Founder {earlier['decided']}: {earlier['ask']}."
                    f"{founder_words(earlier)}"
                )
            lines.append(line)
    else:
        lines.append("None.")
    lines += ["", "## Package-change proposals already decided or withdrawn", ""]
    if state.closed_proposals:
        lines.append("Do not propose these again unless new Evidence answers the reason.")
        for entry in state.closed_proposals:
            status = entry["status"] + (f" and {entry['decided']}" if entry.get("decided") else "")
            lines.append(f"- `{entry['id']}` {status}: {entry['ask']}.{founder_words(entry)}")
    else:
        lines.append("None.")
    lines += ["", "## Items waiting in the incoming folder", ""]
    if standing:
        lines += [
            "An earlier session of this run, or an earlier run, left these there; the launcher takes them in once the"
            " last session has ended.",
            "Read each one that touches a file your work uses, write nothing that asks the same, and leave these files"
            " as they are.",
        ]
        lines += [f"- `{name}`: {said}" for name, said in standing]
    else:
        lines.append("None.")
    return lines


def kept_video_lines(found: filming.Filming | None) -> list[str]:
    """What the post Drafts session is told of each day whose open post names a video that cannot be cut again this
    run. Where the finished file is intact the post keeps that video, and only while its Draft is the one it was
    queued from; otherwise the line says where the file stands, in the words filming.kept gives the Filming table,
    and never that the post keeps it. The Filming table says so to the session that writes edit records, which is no
    longer the one that writes the Drafts."""
    if found is None:
        return []
    lines = []
    for number, day in sorted(found.days.items()):
        if not found.waits(number):
            continue
        said = (
            f"{filming.KEEPS} only while its Draft stays as it is, so rewrite that Draft only when it must change."
            if found.intact(number)
            else f"{found.kept(number)}; rewrite that Draft only when it must change."
        )
        lines.append(f"- Day {number}'s open post names a video that cannot be cut again this run ({day.why}): {said}")
    return lines


def draft_lines(found: filming.Filming, drafts: Sequence[tuple[int, str]]) -> list[str]:
    """What the Filming session is told of the post Drafts its edit records are cut to, as the post Drafts session
    of this run, or an earlier run, left them."""
    lines = [
        "## Post Drafts in place",
        "",
        f"An edit record runs exactly as long as its day's post Draft, `{found.drafts}/day-NN.md`, and the launcher"
        " cuts a video only from a Draft that passes its checks. Read a Draft for its beats and their times, and"
        " change nothing in it.",
        "",
    ]
    lines += [f"- Day {number}: {said}" for number, said in drafts] or ["- No day is ready for an edit record."]
    return lines


def model_setting(session: Session) -> str:
    """The model and reasoning effort a session ran with, as its record keeps them."""
    model, effort = session.record.get("model"), session.record.get("reasoning_effort")
    return f"`{model}` at `{effort}` reasoning effort" if model and effort else ""


def session_summary(session: Session) -> str:
    """One session in one line for the top of the report: the launcher's counts, then the agent's word, each named
    for what it is."""
    took = f" in {span_text(session.seconds)} of agent time" if session.seconds is not None else ""
    if session.work is None:
        return (
            f"The {session.title} session{took}: the launcher counted nothing of it. Its agent's own word:"
            f" {session.word()}."
        )
    key = session.key
    counted = work.summary(session.work, key == sessions.POSTS, session.workflow.writes_items)
    return (
        f"The {session.title} session's work, as the launcher counted it: {counted or 'nothing it counts'}"
        f"{',' if took else ''}{took}. Its agent's own word: {session.word()}."
    )


def session_lines(state: RunState, session: Session) -> list[str]:
    """One session's part of the report: how it ended, its time against its limit, its cost, what the launcher
    counted of it, and the agent's own word, each named for what it is."""
    lines = [f"### {session.title}", ""]
    record = session.record
    if not session.started:
        lines.append(f"- Did not start: {record.get('error') or 'the run did not reach it'}.")
        if record.get("fingerprint"):
            lines.append(f"- Configuration fingerprint: `{record['fingerprint']}`")
        lines.append("- The launcher counted nothing: no agent ran.")
        return lines
    if session.timed_out:
        lines.append(f"- Timed out: {session.stop.describe()}.")
        lines.append(f"- Exit code: {session.exit_code}, the launcher's own for a session stopped at its limit")
    elif session.exit_code != 0:
        lines.append(f"- Ended with {session.failure()}.")
    else:
        lines.append("- Ended by itself with exit code 0.")
    if session.seconds is not None:
        asleep = f", about {span_text(session.asleep)} of it with the Mac asleep" if session.asleep else ""
        setting = model_setting(session)
        lines.append(
            f"- Agent time: {span_text(session.seconds)} of its {session.limit_text} limit{session.cut()}{asleep}"
            + (f", with {setting}." if setting else ".")
        )
    lines.append(f"- Approximate cost: {session_cost(session)}" + (" at API prices." if session.usage else "."))
    if session.work is None:
        lines.append("- The launcher counted nothing: this session's work could not be counted.")
    else:
        lines += [f"- {line}" for line in work.count_lines(session.work)]
    lines.append(f"- The agent's own word, which the launcher does not check: {session.word()}")
    if session.brief:
        lines.append(f"- Brief: `{session.brief}`")
    if session.summary.strip():
        lines += ["", "The agent's own summary:", ""]
        lines += ["> " + line if line else ">" for line in session.summary.strip().splitlines()]
    return lines


def sessions_lines(state: RunState) -> list[str]:
    """The run report's account of every session: one row each, then each session that was tried, then the run's
    totals."""
    lines = [
        "One sandboxed agent session for each workflow that had work due, in the order the run started them. What the"
        " launcher counted comes from Codex's record of each session, the Draft files the run left, and the Review"
        " Queue: none of it comes from what an agent says of itself, and none changes what is queued, blocked, or"
        " marked incomplete. The last column is each agent's own closing line, which the launcher does not check.",
        "",
    ]
    rows = []
    for session in state.sessions:
        took = span_text(session.seconds) if session.seconds is not None else "-"
        limit = session.limit_text if session.tried and not session.out_of_time else "-"
        word = session.word() if session.started else "-"
        rows.append([session.title, session.ended(), took, limit, session_cost(session), word])
    ran, due = state.ran, sessions.due(state.sessions)
    total = state.cost
    rows.append(
        [
            "All sessions",
            f"{len(ran)} ran of the {len(due)} with work due",
            span_text(state.agent_seconds) if ran else "-",
            f"{process.limit_text(state.run_limit)} for the run",
            ("at least " if any(s.timed_out or not s.usage for s in ran) else "about ") + amount(total)
            if total is not None
            else "-",
            "",
        ]
    )
    lines += table(["Session", "How it ended", "Agent time", "Limit", "Cost", "The agent's own word"], rows)
    for session in state.sessions:
        if session.due:
            lines += [""] + session_lines(state, session)
    lines += ["", "### The run's totals", ""]
    nothing = [session.title for session in state.sessions if not session.due]
    lines.append(
        f"- Sessions: {len(ran)} ran of the {len(due)} with work due"
        + (f"; nothing was due for {', '.join(nothing)}." if nothing else ".")
    )
    lines.append(
        f"- Agent time: {span_text(state.agent_seconds)} of the {process.limit_text(state.run_limit)} that bounds all"
        " of a run's sessions together."
    )
    lines.append(f"- {cost_line(state)}")
    if ran:
        lines.append(f"- {work.claim_line(state.claims, whole_run=True)}.")
        lines.append(f"- {work.proposal_line(state.proposals, whole_run=True)}.")
    return lines


def outcome_lines(state: RunState) -> list[str]:
    """How the run's sessions ended, for the top of the report: that the run finished, or one line for each session
    that fell short, whatever else went well."""
    short = state.short
    ran, nothing = state.ran, [session.title for session in state.sessions if not session.due]
    lines = []
    if not short and state.ending == attempts.COMPLETED:
        lines.append("The run finished.")
    elif not short:
        silent = [session.title for session in ran if not session.confirmed]
        lines.append(
            "Every session ended without an error, but the Mac slept during the run and the"
            f" {' and '.join(silent)} session{'s' if len(silent) > 1 else ''} did not confirm that"
            f" {'they' if len(silent) > 1 else 'it'} finished, so this run's work may be incomplete."
        )
    for session in short:
        if session.timed_out:
            lines.append(
                f"The {session.title} session timed out: its agent was still running at its {session.limit_text}"
                f" time limit{session.cut()}, so the launcher stopped it and went on with the run. What it had written"
                " was checked as always, and each output that needed it is incomplete; see Outputs and Sessions"
                " below."
            )
        elif session.out_of_time:
            lines.append(
                f"The {session.title} session did not start: the {process.limit_text(state.run_limit)} that bounds all"
                " of a run's sessions together was used up before its turn, so each output that needed it is"
                " incomplete; see Outputs and Sessions below."
            )
        elif not session.started:
            lines.append(
                f"The {session.title} session did not start; see Sessions below. Everything the launcher does alone"
                " still ran."
            )
        else:
            lines.append(
                f"The {session.title} session stopped with {session.failure()}; its work this run may be incomplete."
            )
    if not state.sessions:
        return lines
    if not ran and not short:
        lines.append("Sessions: none was started, since no workflow had work for the agent this run.")
    else:
        started = f"{len(ran)} ran ({', '.join(session.title for session in ran)})" if ran else "none ran"
        lines.append(f"Sessions: {started}" + (f"; nothing was due for {', '.join(nothing)}." if nothing else "."))
    return lines


def summary_lines(state: RunState) -> list[str]:
    failed = state.failed_sources()
    open_items = state.queue_after
    carried = sum(1 for entry in open_items if entry.get("carried_over"))
    lines = [f"- {run_tally(state.tallies).line()}", f"- {start_line(state)}"]
    lines += [f"- {line}" for line in state.notes]
    lines += [f"- {line}" for line in outcome_lines(state)]
    if state.asleep:
        lines.append(
            f"- The Mac was asleep for about {span_text(state.asleep)} while a session ran, which counts toward that"
            " session's time limit and toward the bound on all of the run's sessions together."
        )
    elsewhere = state.slept - state.asleep
    if state.attempt is not None and elsewhere >= ASLEEP_AT_LEAST:
        lines.append(f"- The Mac was asleep for about {span_text(elsewhere)} of this run outside its sessions' time.")
    lines.append(f"- {what_follows(state)}" if what_follows(state) else "")
    refused = sum(1 for line in state.sources if line.status == waitlist.REFUSED)
    lines.append(
        f"- Sources: {len(failed)} failed"
        + (f" ({', '.join(line.name for line in failed)})" if failed else "")
        + f", {sum(1 for line in state.sources if line.status == package.CHANGED)} changed,"
        + f" {sum(1 for line in state.sources if line.status == package.READ)} read,"
        + f" {sum(1 for line in state.sources if line.status == SKIPPED)} skipped"
        + (f", {refused} refused." if refused else ".")
    )
    if state.waitlist is not None:
        lines.append(f"- {waitlist_summary(state.waitlist, state.breach_notice)}")
    taken = [outcome for outcome in state.decisions if outcome.status == "taken"]
    lines.append(
        f"- Review Queue: {plural(len(open_items), 'item')} open for the next sitting ({len(state.published)} new"
        f" this run, {carried} carried over); {plural(len(taken), 'Founder decision')} taken in."
    )
    outcome = state.post_outcome
    if outcome is not None:
        counts = outcome.counts()
        lines.append(f"- Post Drafts: {', '.join(counts) or 'no calendar day was due'}.")
    elif state.posts_problem:
        lines.append(f"- Post Drafts: {state.posts_problem}")
    if state.filming is not None or state.filming_problem:
        gap = state.agent_gap("filming")
        lines.append(f"- Filming: {state.filming_problem or filming.tally(state.filming, gap).note}.")
    recruiting = beta.summary(state.beta, state.beta_outcome, state.beta_problem)
    if recruiting:
        lines.append(f"- {recruiting}")
    for workflow, title, active in (
        (listening.WORKFLOW, "Listening", state.listening is not None and bool(state.listening.snapshot.readings)),
        (outreach.WORKFLOW, "Outreach", state.outreach is not None and bool(state.outreach.slots)),
    ):
        tally = next((tally for tally in state.tallies if tally.workflow == workflow), None)
        if active and tally is not None:
            lines.append(f"- {title}: {tally.account()}.")
    if state.notice:
        lines.append(f"- Problems this run are listed in the notice `{state.notice}`.")
    lines += [f"- {session_summary(session)}" for session in state.ran]
    lines.append(f"- {cost_line(state)}")
    return [line for line in lines if line]


def render_report(state: RunState) -> str:
    lines = [f"# Run report: {state.run_id}", "", "## Summary", ""] + summary_lines(state)
    lines += ["", "## Sources", ""]
    lines += table(["Source", "Result", "Detail"], [[line.name, line.status, line.detail] for line in state.sources])
    lines += ["", "## Package changes since the previous run", ""] + package_changes(state)
    if state.waitlist is not None:
        lines += ["", "## Waitlist", ""] + waitlist_lines(state.waitlist, state.waitlist_file, state.breach_notice)
    lines += ["", "## Founder decisions", ""] + (decision_lines(state) or ["No new decisions."])
    if state.sittings:
        lines += [""] + [f"- Sitting {sitting.day}: {sitting.minutes} minutes." for sitting in state.sittings]
    lines += ["", "## Review Queue", ""]
    if state.queue_after:
        for number, entry in enumerate(state.queue_after, 1):
            slot = f", slot {entry['slot']}" if entry.get("slot") else ""
            carried = (
                f", carried over from the sitting on {entry['carried_over_from']}" if entry.get("carried_over") else ""
            )
            lines.append(f"{number}. `{entry['id']}` ({entry['kind']}{slot}{carried}): {entry['ask']}")
    else:
        lines.append("Nothing is waiting for the Founder.")
    for item in state.set_aside:
        lines.append(f"- Set aside, not queued: `{item.name}`: {'; '.join(item.problems)}")
    lines += [""] + posts.report_lines(state.posts, state.post_outcome, state.filing, state.posts_problem)
    if state.filming is not None or state.filming_problem:
        lines += [""] + filming.report_lines(state.filming, state.filming_problem)
    recruiting = beta.report_lines(state.beta, state.beta_outcome, state.beta_problem)
    lines += [""] * bool(recruiting) + recruiting
    lines += [""] + listening.report_lines(
        state.listening, state.listening_result, state.requests_file, state.listening_problem
    )
    lines += [""] + outreach.report_lines(
        state.outreach, state.outreach_result, state.outreach_filing, state.outreach_problem
    )
    lines += [""] + learning.report_lines(state.learning, state.put_back)
    lines += ["", "## Run state", ""]
    lines += [f"- {tally.workflow}: {tally.line()}" for tally in state.tallies]
    if state.state_notes:
        lines += ["", "The run state disagreed with the Review Queue, which wins; the state was repaired:", ""]
        lines += [f"- {note}" for note in state.state_notes]
    lines += ["", "## Outputs", ""] + table(["Output", "Status", "Detail"], state.outputs)
    lines += ["", "## Sessions", ""] + sessions_lines(state)
    lines += ["", "## Agent", ""] + agent_lines(state)
    if state.problems:
        lines += ["", "## Launcher problems", ""] + [f"- {problem}" for problem in state.problems]
    return "\n".join(lines) + "\n"


def probe_scope(tried: Sequence[Session], probe: str, every: str) -> tuple[str, str]:
    """Before which of the sessions whose preflight ran one of its no-model probes, the listing of the footage folders
    or the network probe, tried every target it had, as each session's own record shows, and what the probe's line
    then says of every other session. every is the wording for all of them. A record that left a target untried
    names it, and a session has no record of the probe where the probe never ran, since a proof before it did not
    pass."""
    whole, short = 0, []
    for session in tried:
        found = session.record["preflight"].get(probe)
        if not found:
            short.append(f"nothing tried before the {session.title} session")
        elif found.get("untried"):
            names = ", ".join(f"`{target}`" for target in found["untried"])
            short.append(f"not tried before the {session.title} session: {names}")
        else:
            whole += 1
    if not short:
        return every, ""
    return f"{whole} of {plural(len(tried), 'session')}", "".join(f"; {gap}" for gap in short)


def agent_lines(state: RunState) -> list[str]:
    """What every session of the run was started with: the boundary each was proved against before its agent
    started, the configuration fingerprint, the code, and where the task definitions are."""
    lines = []
    removed = probe_files_removed(state)
    if removed:
        lines.append(
            "- Removed boundary probe files left in the areas, before any agent could find them: "
            + ", ".join(f"`{path}`" for path in removed)
        )
    tried = [session for session in state.sessions if session.record.get("preflight")]
    failed = [session.title for session in tried if not (session.record["preflight"] or {}).get("ok")]
    if tried:
        preflight = tried[0].record["preflight"]
        every = "its session" if len(tried) == 1 else f"each of {len(tried)} sessions"
        lines.append(
            f"- Boundary preflight: {'FAILED before the ' + ', '.join(failed) + ' session' if failed else 'passed'},"
            f" run before {every}; it refused {len(preflight.get('refused', []))} paths and allowed"
            f" {len(preflight.get('writable', []))} areas."
        )
        footage = [session.record["preflight"].get("footage") or {} for session in tried]
        refused = {str(entry["target"]) for found in footage for entry in found.get("refused", [])}
        listed = sorted({str(path) for found in footage for path in found.get("listed", [])})
        folders = refused | set(listed) | {str(path) for found in footage for path in found.get("untried", [])}
        if folders:
            before, short = probe_scope(tried, "footage", every)
            lines.append(
                f"- Sandbox footage: the footage place and {plural(len(folders) - 1, 'footage folder')} in it tried"
                f" from inside the sandbox before {before}, each once it existed, listed:"
                f" {', '.join(f'`{path}`' for path in listed) or 'none'}{short}."
            )
        network = [session.record["preflight"].get("network") or {} for session in tried]
        if any(network):
            hosts = {
                target
                for found in network
                for key in ("unreachable", "reached", "untried")
                for target in found.get(key, [])
            }
            reached = sorted({target for found in network for target in found.get("reached", [])})
            before, short = probe_scope(tried, "network", every)
            lines.append(
                f"- Sandbox network: {len(hosts)} listed hosts tried from inside the sandbox before {before}, reached:"
                f" {', '.join(reached) or 'none'}{short}."
            )
    prints = sorted(
        {str(session.record["fingerprint"]) for session in state.sessions if session.record.get("fingerprint")}
    )
    if len(prints) == 1:
        same = ", the same for every session" if len(tried) > 1 else ""
        lines.append(f"- Configuration fingerprint: `{prints[0]}`{same}")
    elif prints:
        lines.append(
            "- Configuration fingerprints, which differ between sessions: "
            + "; ".join(
                f"{session.title} `{session.record['fingerprint']}`"
                for session in state.sessions
                if session.record.get("fingerprint")
            )
        )
    lines.append(f"- Code: {state.code}" + (f"; {state.sync['detail']}" if state.sync else ""))
    lines.append(
        f"- Task definitions: `{state.instruction}/`, the part every session shares and each session's own part"
    )
    return lines


def bullet(text: str) -> str:
    """A notice's list line, on one line whatever the text it quotes holds."""
    return "- " + " ".join(text.split())


def problems_notice(state: RunState, report_path: str) -> tuple[str, str, str, str] | None:
    """One notice for the Founder per run with problems, in plain outcome language; None if there were none.

    A notice about one kind of problem says what it is in its title; a notice about several counts every problem.
    A session that timed out is named first, in the notice's title and its text, whatever else went wrong; every
    session that fell short has its own part, so one workflow's trouble is never told as another's.
    A weekly scheduled run that the Mac's sleep cut short queues no notice for that alone while a fresh run follows
    by itself, and its notice then leaves out the work its agents did not reach, which that run does again and
    reports on itself; once the run due then has no attempt left, the notice lists everything and says so in its
    title. Such a run always has a part that says it was cut short and what follows: one for each session that fell
    short, and one for each session that ended without an error and did not confirm its work, the package review's
    being the part it has in any run.
    """
    day = wall_clock(state.started).strftime("%Y-%m-%d")
    sections: list[tuple[int, str, str]] = []  # how many problems, the title, the text
    failed = state.failed_sources()
    if failed:
        lines = ["These sources could not be read, so the work that needs them is incomplete this run:"]
        for line in failed:
            needs = ", ".join(line.needed_by) or "nothing else"
            lines.append(bullet(f"{line.name}: {line.detail} Incomplete: {needs}."))
        sections.append((len(failed), f"{plural(len(failed), 'source')} could not be read on {day}", "\n".join(lines)))
    unusable = state.unusable_to_report()
    to_replace = [record for record in unusable if state.open_item(record)]
    if to_replace:
        sections.append(
            (
                len(to_replace),
                f"{plural(len(to_replace), 'decision')} in Mandu could not be taken in on {day}",
                "These decision records in Mandu could not be used, so the decisions in them were not taken in and"
                " their items stay undecided. Mandu must replace each with a valid record of the same decision, in the"
                " format of the Mandu exchange; until it does, this notice comes back at every run while the item is"
                " open:\n"
                + "\n".join(
                    bullet(f"`{record.name}`, for `{record.item}`: {'; '.join(record.problems)}")
                    for record in to_replace
                ),
            )
        )
    others = [record for record in unusable if not state.open_item(record)]
    if others:
        sections.append(
            (
                len(others),
                f"{plural(len(others), 'Mandu record')} could not be used on {day}",
                "Some records in Mandu could not be used, so nothing was taken from them; a decision already taken"
                " stands, and Mandu need not change them. Each is reported once, and again only if it changes:\n"
                + "\n".join(bullet(f"`{record.name}`: {'; '.join(record.problems)}") for record in others),
            )
        )
    if state.stood:
        count = len(state.stood)
        sections.append(
            (
                count,
                f"{plural(count, 'open item')} not checked again on {day}",
                "Something the check of these open items needs could not be read this run, so each was left exactly"
                " as it is: nothing was withdrawn or replaced on that account, each keeps its identifier, and the next"
                " run checks it again:\n"
                + "\n".join(
                    bullet(f"`{kept.item}` ({title}): {'; '.join(kept.unread)}") for title, kept in state.stood
                ),
            )
        )
    blocked = posts.notice_section(state.post_outcome, day, state.again)
    if blocked:
        sections.append(blocked)
    unfilmed = filming.notice_section(state.filming, day)
    if unfilmed:
        sections.append(unfilmed)
    recruiting = beta.notice_section(state.beta_outcome, day, state.again)
    if recruiting:
        sections.append(recruiting)
    for section in (
        listening.notice_section(state.listening, state.listening_result, day),
        outreach.notice_section(state.outreach, state.outreach_result, day, state.again),
        learning.notice_section(state.learning, day),
    ):
        if section:
            sections.append(section)
    if state.set_aside:
        sections.append(
            (
                len(state.set_aside),
                f"{plural(len(state.set_aside), 'prepared item')} not queued on {day}",
                "Some items the Marketing Engineer prepared were not queued, because they did not meet the item format"
                " or asked the same as an item already queued or decided:\n"
                + "\n".join(bullet(f"`{item.name}`: {'; '.join(item.problems)}") for item in state.set_aside),
            )
        )
    follows = f" {what_follows(state)}" if what_follows(state) else ""
    # A weekly scheduled run the Mac's sleep cut short needs no higher limit, so its notice does not point at one.
    slept = state.attempt is not None and state.ending == attempts.SLEPT
    told = []  # the parts that only say how a session ended, each with what follows said once, in the first
    late = []  # the timed-out sessions' parts, which lead the notice
    for session in state.short:
        needs = ", ".join(session.incomplete)
        said = "" if told or late else follows
        if session.timed_out:
            limit = (
                ""
                if slept
                else " The next run does this work again; if sessions keep timing out, a session's limit is"
                " `agent.time_limit_seconds` in `config/run.json`."
            )
            late.append(
                (
                    1,
                    f"the {session.title} session timed out on {day}",
                    f"The {session.title} session was still running at its {session.limit_text} time limit"
                    f"{session.cut()}, so the launcher stopped it and went on with the run. What it had written by"
                    " then was checked as always: anything queued from it passed every check, and anything unfinished"
                    f" was set aside or blocked. Incomplete this run: {needs}.{limit}{said}",
                )
            )
        elif session.out_of_time:
            limit = (
                ""
                if slept
                else " The next run does this work again; if runs keep reaching that bound, it is"
                " `agent.run_time_limit_seconds` in `config/run.json`."
            )
            late.append(
                (
                    1,
                    f"the {session.title} session had no time left on {day}",
                    f"The {session.title} session did not start: the {process.limit_text(state.run_limit)} that bounds"
                    " all of a run's sessions together was used up before its turn. Incomplete this run:"
                    f" {needs}.{limit}{said}",
                )
            )
        elif not session.started:
            error = session.record.get("error") or "see the run report"
            told.append(
                (
                    1,
                    f"the {session.title} session did not start on {day}",
                    f"The {session.title} session did not start: {error}. Incomplete this run: {needs}.{said}",
                )
            )
        else:
            told.append(
                (
                    1,
                    f"the {session.title} session stopped early on {day}",
                    f"The {session.title} session stopped with {session.failure()}, so its work this run may be"
                    f" incomplete: {needs}. What it had written was checked as always, and the run report's Sessions"
                    f" section says what the launcher counted of it.{said}",
                )
            )
    review = state.session(sessions.REVIEW)
    if review is not None and review.finished and review.closing.startswith(SESSION_INCOMPLETE):
        why = review.reason()
        told.append(
            (
                1,
                f"the package review was not finished on {day}",
                "The Marketing Engineer did not finish reviewing the Go-To-Market Package"
                + (f" ({why})" if why else "")
                + ", so a contradiction it did not reach is not in the Review Queue yet; the next run reviews it"
                f" again.{'' if told or late else follows}",
            )
        )
    elif review is not None and review.finished and state.review_gap():
        told.append(
            (
                1,
                f"the package review was not confirmed finished on {day}",
                "The Marketing Engineer did not confirm that it finished every pass of its review of the Go-To-Market"
                " Package, so a contradiction it did not reach may not be in the Review Queue yet; the next run reviews"
                f" it again.{'' if told or late else follows}",
            )
        )
    for session in state.ran if slept else ():
        if session.finished and not session.confirmed and session is not review:
            told.append(
                (
                    1,
                    f"the {session.title} session did not confirm that it finished on {day}",
                    f"The {session.title} session ended without an error, but the Mac slept during the run and its"
                    " summary did not confirm that it finished, so its work this run may be incomplete; the run"
                    f" report's Sessions section has its own word.{'' if told or late else follows}",
                )
            )
    sections = late + sections + told
    if state.problems:
        sections.append(
            (
                len(state.problems),
                f"the launcher hit {plural(len(state.problems), 'problem')} on {day}",
                "The launcher hit problems:\n" + "\n".join(bullet(problem) for problem in state.problems),
            )
        )
    if not sections or (state.again and len(sections) == len(late) + len(told)):
        # A run the Mac's sleep cut short, with nothing else wrong, needs no notice while a fresh run follows by
        # itself: its own report says how each session ended, and the fresh run does the work again.
        return None
    total = sum(count for count, _, _ in sections)
    if state.attempt is not None and state.ending == attempts.SLEPT and not state.again:
        title = f"Notice: the Mac's sleep cut short every attempt at the run due {state.attempt.due:%Y-%m-%d}"
    elif len(sections) == 1:
        title = f"Notice: {sections[0][1]}"
    elif late:
        title = f"Notice: {late[0][1]}, and the run had {plural(total - 1, 'other problem')}"
    else:
        title = f"Notice: the run on {day} had {plural(total, 'problem')}"
    body = "\n\n".join(text for _, _, text in sections)
    if len(body) > NOTICE_BODY_LIMIT:
        cut = body.rfind("\n", 0, NOTICE_BODY_LIMIT)
        body = body[: cut if cut > 0 else NOTICE_BODY_LIMIT] + "\n- And more: the run report lists every problem."
    body += "\n\nEverything else in this run finished; the run report has the details."
    touches = "- Nothing changes; this notice is for your information."
    evidence = f"- The run report: `{report_path}`"
    return title, body, touches, evidence


# The Waitlist.


def waitlist_progress(reading: waitlist.Reading) -> str:
    """Good-Fit opt-ins against the Product's Beta Cohort bar."""
    bar = reading.rules.bar
    have = reading.good_fit_opt_ins
    where = "the bar is reached" if have >= bar else f"{round(100 * have / bar)}% of the way"
    return f"{plural(have, 'good-Fit opt-in')} of about {bar}, {where}"


def waitlist_age(reading: waitlist.Reading) -> str:
    """How old the view was when the run started, so counts from a copy that stopped changing never pass for a quiet
    week."""
    if reading.age < timedelta(0):
        return "after this run started"
    return f"{duration(reading.age)} before this run started"


def waitlist_outcome(reading: waitlist.Reading, notice: str | None) -> str:
    """What became of the view this run, in one sentence that opens with its status unless it was read."""
    if reading.status == package.READ:
        week = reading.this_week
        return (
            f"{plural(int(reading.cumulative['sign_ups']), 'sign-up')}, {week['sign_ups']} of them in the week of"
            f" {week['week_of']}; {waitlist_progress(reading)}."
        )
    if reading.status == waitlist.REFUSED:
        return (
            "refused, a Guardrail breach (G6): the view held something that looks like an email address, so the whole"
            " read was discarded and nothing from it was kept; this run recorded no Waitlist Evidence"
            + (f"; see the notice `{notice}`." if notice else ".")
        )
    return f"{reading.status}: {reading.detail.rstrip('.')}."


def waitlist_summary(reading: waitlist.Reading, notice: str | None) -> str:
    separator = ": " if reading.status == package.READ else " "
    return f"Waitlist{separator}{waitlist_outcome(reading, notice)}"


def waitlist_lines(reading: waitlist.Reading, evidence_file: str, notice: str | None) -> list[str]:
    """The run report's Waitlist section: progress, then counts by week, by Source, and by Fit answer."""
    if reading.status != package.READ:
        outcome = waitlist_outcome(reading, notice)
        return [outcome[:1].upper() + outcome[1:]]
    counts = waitlist.COUNTS
    week = reading.this_week
    good_fit = " or ".join(f"`{answer}`" for answer in reading.rules.good_fit)
    lines = [
        f"Read the view generated {reading.generated_at.isoformat()}, {waitlist_age(reading)}; Waitlist Evidence:"
        f" `{evidence_file}`.",
        f"Progress toward the Beta Cohort bar: {waitlist_progress(reading)}; good Fit is the {good_fit} answer.",
        "",
    ]
    lines += table(
        ["Week of", "Sign-ups", "Good Fit", "Opted in", "Good-Fit opt-ins"],
        [[str(row["week_of"]), *(str(row[key]) for key in counts)] for row in reading.weeks]
        + [["All weeks", *(str(reading.cumulative[key]) for key in counts)]],
    )
    lines += [""] + table(
        ["Source", f"Week of {week['week_of']}", "All weeks", "Good Fit", "Opted in", "Good-Fit opt-ins"],
        [
            [tag, str(week["by_source"][tag]["sign_ups"]), *(str(row[key]) for key in counts)]
            for tag, row in reading.cumulative["by_source"].items()
        ],
    )
    lines += [""] + table(
        ["Fit answer", f"Week of {week['week_of']}", "All weeks", "Opted in"],
        [
            [answer, str(week["by_fit"][answer]["sign_ups"]), str(row["sign_ups"]), str(row["opted_in"])]
            for answer, row in reading.cumulative["by_fit"].items()
        ],
    )
    unknown = waitlist.UNKNOWN
    lines += [
        "",
        f"An `{unknown}` Source is a sign-up that arrived without a listed tag; an `{unknown}` Fit answer is a sign-up"
        " that gave none, never one that is not a fit.",
    ]
    return lines


def waitlist_brief(reading: waitlist.Reading, evidence: Path | None) -> list[str]:
    """What the agent learns about the Waitlist: where the counts are; the view itself is beyond the sandbox's reach."""
    if reading.status == package.READ:
        return [
            f"- Read: the view {reading.detail}.",
            "- Counts by Source, Fit answer, and opt-in, per week and cumulative, with the entry identifiers:"
            f" `{evidence}`.",
            "- The view itself is outside what the sandbox can read; work only from these counts.",
        ]
    if reading.status == waitlist.REFUSED:
        return ["- Refused: the view held something that looks like an email address, so there are no counts."]
    if reading.status == package.FAILED:
        return ["- Failed: the view could not be used this run, so there are no counts; never guess them."]
    return [f"- Skipped: {reading.detail}; there are no counts yet."]


def breach_notice(state: RunState, report_path: str) -> tuple[str, str, str, str]:
    """The Guardrail breach notice, in plain outcome language: what happened, that nothing was kept, where in the view
    it was found without ever repeating it, and what fixes it."""
    reading = state.waitlist
    day = wall_clock(state.started).strftime("%Y-%m-%d")
    places = list(reading.places)
    shown = [bullet(place) for place in places[: waitlist.MAX_LISTED]]
    if len(places) > waitlist.MAX_LISTED:
        shown.append(bullet(f"and {len(places) - waitlist.MAX_LISTED} more"))
    body = "\n".join(
        [
            "The Waitlist's anonymous view must never hold an email address (Guardrail G6), and this run found"
            " something in it that looks like one.",
            "The run discarded the whole read: it recorded no Waitlist count or other Waitlist Evidence, and no address"
            " was stored or shown anywhere.",
            "",
            "Where it was found, without the values:",
            *shown,
            "",
            "Each run refuses the view the same way until it holds no address; fixing how RepToday produces it is a"
            " change in RepToday, through firstmate.",
        ]
    )
    title = f"Notice: Guardrail breach, the Waitlist view held an email address on {day}"
    touches = f"- {reading.rules.product}'s Waitlist anonymous view, which its Waitlist build produces"
    return title, body, touches, f"- The run report: `{report_path}`"
