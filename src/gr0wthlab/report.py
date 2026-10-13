"""What a run tells the agent before it starts (the brief) and the Founder after it ends (the run report).

Both are rendered from the launcher's own state, never from anything the agent wrote, except the agent's closing
summary, which the report quotes as the agent's account. The report sets that account's `Review:` line beside what the
launcher counted of the session's work (work.py), and says which is which.
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
    waitlist,
    work,
)
from .exchange import plural
from .package import SKIPPED
from .state import Tally, run_tally

COMPLETE = "complete"
INCOMPLETE = "incomplete"
NOT_BUILT = "not built yet"
# The line the agent's summary ends with: its own account of whether it finished every pass of its review.
REVIEW_COMPLETE = "Review: complete"
REVIEW_INCOMPLETE = "Review: incomplete"
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")
NOTICE_BODY_LIMIT = exchange.MAX_ITEM_CHARS // 2
# Fewer seconds than this between a wall-clock time and the awake time of the same span are the two clocks' own
# difference, not the Mac asleep.
ASLEEP_AT_LEAST = 5
# How much of the agent's closing line the report quotes as its word.
REVIEW_WORD_LIMIT = 300


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
    agent: Mapping[str, object] = field(default_factory=dict)
    agent_incomplete: tuple[str, ...] = ()  # the titles of the outputs the agent's not finishing leaves incomplete
    agent_summary: str = ""
    review: str = ""  # the last line of the agent's whole summary
    usage: Mapping[str, int] | None = None
    cost: float | None = None
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
    put_back: list[str] = field(default_factory=list)  # each change to them the launcher undid
    # what a stopped boundary check had left in the areas, removed before the Instructions were remembered
    probe_files_removed: list[str] = field(default_factory=list)
    work_published: list[str] = field(default_factory=list)  # the items Listening and outreach queued this run
    check_work: str = ""  # the command the agent checks its Listening and outreach work with
    attempt: attempts.Attempt | None = None  # a weekly scheduled run: which attempt at the run due, and those before
    slept: float = 0.0  # about how many seconds the Mac was asleep from the run's start to its agent's end
    work: work.Work | None = None  # what the launcher counted of the agent's session, once the agent has ended

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

    @property
    def timed_out(self) -> bool:
        """Whether the launcher stopped the agent at its time limit."""
        return bool(self.agent.get("timed_out"))

    @property
    def time_limit(self) -> str:
        """The agent's time limit in words."""
        return process.limit_text(float(self.agent.get("time_limit_seconds") or 0))

    @property
    def asleep(self) -> float:
        """About how many seconds of the agent's time the Mac was asleep, its wall-clock time less its awake time; 0
        when the agent did not run or the Mac stayed awake."""
        agent = self.agent
        return asleep_for(float(agent.get("agent_seconds") or 0), float(agent.get("agent_awake_seconds") or 0))

    @property
    def stop(self) -> process.Stop:
        """What stopping a timed-out agent took, as the launcher's run record keeps it."""
        return process.Stop.from_json(self.agent.get("stopped") or {})

    @property
    def ending(self) -> str:
        """How the run ended, as the record of the run due at its time keeps it. Only a weekly scheduled attempt is
        asked whether its agent confirmed its review."""
        return attempts.ending(self.agent, self.slept, self.attempt is None or self.review == REVIEW_COMPLETE)

    @property
    def again(self) -> bool:
        """Whether a fresh run starts by itself after this one: only after a weekly scheduled attempt that the Mac's
        sleep cut short, and only while the run due then may take another."""
        attempt = self.attempt
        return attempt is not None and self.ending == attempts.SLEPT and attempt.number < attempt.limit

    def agent_gap(self) -> str:
        """Why every output that needs the agent is incomplete this run, or "" when the agent finished."""
        if self.timed_out:
            return f"the agent was stopped at its {self.time_limit} time limit"
        return "" if self.agent.get("exit_code") == 0 else "the agent did not finish"

    def review_gap(self) -> str:
        """Why the agent's package review is incomplete, or "" when it finished: it must stop with exit code 0 and end
        its summary with the line `Review: complete`, so a summary that says otherwise, or says nothing, is not."""
        if self.agent_gap():
            return self.agent_gap()
        if self.review == REVIEW_COMPLETE:
            return ""
        if self.review.startswith(REVIEW_INCOMPLETE):
            why = self.review_reason()
            return "the agent did not finish its review" + (f": {why}" if why else "")
        return "the agent did not confirm that it finished every pass"

    def review_reason(self) -> str:
        """The agent's own reason after `Review: incomplete:`, without the closing punctuation that would clash with
        the sentence it is quoted in."""
        return self.review[len(REVIEW_INCOMPLETE) :].lstrip(":").strip().rstrip(".!;:, ")

    def open_item(self, record: Unusable) -> str:
        """The item a record is for when that item is still open as this run leaves the Review Queue, so Mandu must
        replace the record with a valid one; empty otherwise."""
        return record.item if any(entry["id"] == record.item for entry in self.queue_after) else ""

    def reports(self, record: Unusable) -> bool:
        """A record Mandu must replace is reported at every run until it does; any other record only once."""
        return bool(self.open_item(record)) or record.fingerprint not in self.reported_before

    def unusable_to_report(self) -> list[Unusable]:
        return [record for record in self.unusable if self.reports(record)]


def asleep_for(seconds: float, awake: float) -> float:
    """About how many of a span's seconds the Mac was asleep, its wall-clock time less its awake time; 0 when the Mac
    stayed awake."""
    gap = seconds - awake
    return gap if gap >= ASLEEP_AT_LEAST else 0.0


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


def cost_line(state: RunState) -> str:
    """The run's approximate cost from the token counts Codex reported, or that there is none to state: Codex reports
    them as each turn ends, so an agent stopped at its time limit leaves at most a part of them, never a zero."""
    if not state.usage:
        if state.timed_out:
            return "Approximate cost: not available; the agent was stopped before it reported any token counts."
        return "Approximate cost: unknown; the agent reported no token counts."
    usage = state.usage
    tokens = (
        f"{usage['input_tokens']:,} input tokens ({usage['cached_input_tokens']:,} cached) "
        f"and {usage['output_tokens']:,} output tokens"
    )
    amount = f"{state.cost:.2f}" if state.cost >= 0.1 else f"{state.cost:.3f}"
    if state.timed_out:
        return (
            f"Approximate cost: at least ${amount} at API prices, for the {tokens} reported before the agent was"
            " stopped; what its unfinished turn used is not available."
        )
    return f"Approximate cost: about ${amount} at API prices, for {tokens}."


def span_text(seconds: float) -> str:
    """How long something took, in hours, minutes, and seconds."""
    minutes, rest = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return " ".join([f"{hours} h"] * bool(hours) + [f"{minutes} min"] * bool(hours or minutes) + [f"{rest} s"])


def probe_files_removed(state: RunState) -> list[str]:
    """What a stopped boundary check had left in the areas and this run removed, as paths from the repository: the
    production clone's pre-run step removes it before its records step can commit it, and every run before it
    remembers the agent's Instructions and again before its preflight."""
    before_records = (state.sync or {}).get("probe_files_removed") or []
    return [*before_records, *state.probe_files_removed, *(state.agent.get("probe_files_removed") or [])]


def left_running(stop: process.Stop) -> str | None:
    """The launcher problem a stop leaves when it could not show that none of the processes it found is still running;
    the process ids stay in the run report's Agent section, so the same problem reads the same at every run."""
    if stop.left:
        count = "1 process" if len(stop.left) == 1 else f"{len(stop.left)} processes"
        return (
            f"{count} the agent started could not be stopped and may still be running; the run report's Agent section"
            " names each"
        )
    if not stop.proven:
        return (
            "the process table could not be read after the agent was stopped, so nothing shows whether a process it"
            " started is still running"
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


def package_changes(state: RunState) -> list[str]:
    if state.previous_snapshot is None:
        return ["First snapshot; there is no earlier run to compare with."]
    lines = []
    for result in state.snapshot:
        for file in result.files:
            if file.change in ("changed", "added"):
                lines.append(f"- {file.change}: `{file.path}`")
        lines += [f"- removed: `{path}`" for path in result.removed]
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


def render_brief(state: RunState, repo_root: Path, workspace: Path, ledger: Path) -> str:
    """The facts the agent works from, written before it starts."""
    lines = [
        f"# Brief for run {state.run_id}",
        "",
        "The launcher wrote this before you started.",
        "Every Go-To-Market Package file is in the Mandu checkout, at the absolute path listed below;",
        "a Product's own repository holds its code, never its package.",
        "In the items you write, cite a package file by its path inside the Mandu checkout, as in the Changes list.",
        "The Mandu checkout and every read-only location in the header are readable, even inside a folder the",
        "sandbox otherwise denies, such as /private/tmp.",
        "",
        f"- {start_line(state)}",
        f"- Mandu checkout: `{state.mandu}`",
        f"- Package snapshot: `{ledger / state.snapshot_file}`"
        + (f" (previous: run {state.previous_snapshot})" if state.previous_snapshot else " (the first one)"),
        "",
        "## Package files",
        "",
    ]
    rows = []
    mandu = Path(state.mandu)
    for result in state.snapshot:
        if result.reason:
            rows.append([f"`{mandu / result.source.path}`", f"failed: {result.reason}"])
        rows += [[f"`{mandu / file.path}`", f"{file.status}: {file_line(file)}"] for file in result.files]
    lines += table(["File", "This run"], rows) + ["", "## Changes since the previous snapshot", ""]
    lines += package_changes(state)
    lines += ["", "## Failed sources", ""]
    failed = [line for line in state.failed_sources() if line.name not in beta.LAUNCHER_SOURCES]
    if failed:
        lines += [
            "A failed source blocks only the work that needs it: never guess what it says, and do everything else.",
            "Review every other package file as usual; only contradictions that involve a failed file go unchecked.",
            "",
        ]
        lines += [
            f"- {line.name}: {line.detail} Incomplete without it: {', '.join(line.needed_by) or 'nothing else'}."
            for line in failed
        ]
    else:
        lines.append("None.")
    lines += ["", "## Founder decisions taken in this run", ""]
    lines += decision_lines(state, taken_only=True) or ["None."]
    lines += ["", "## Open Review Queue items", ""]
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
    lines += ["", "## Waitlist", ""]
    if state.waitlist is not None:
        evidence = ledger / state.waitlist_file if state.waitlist_file else None
        lines += waitlist_brief(state.waitlist, evidence)
    if state.posts is not None:
        lines += [""] + posts.brief_lines(state.posts, repo_root)[:-1]
    if state.filming is not None:
        lines += [""] + filming.brief_lines(state.filming, repo_root)[:-1]
    if state.beta is not None and not state.beta_problem:
        recruiting = beta.brief_lines(state.beta, repo_root)
        lines += [""] * bool(recruiting) + recruiting[:-1]
    context = state.posts.context if state.posts is not None else None
    if state.listening is not None or state.listening_problem:
        lines += [""] + (
            listening.brief_lines(state.listening, workspace, ledger, mandu, state.check_work)
            if state.listening is not None
            else ["## Listening", "", f"Listening was {state.listening_problem}; record nothing from memory."]
        )
    if state.outreach is not None or state.outreach_problem:
        lines += [""] + (
            outreach.brief_lines(state.outreach, context, mandu, state.check_work)
            if state.outreach is not None
            else ["## Outreach", "", f"Outreach was {state.outreach_problem}; write no outreach Draft this run."]
        )
    lines += [""] + learning.brief_lines(state.reasons, workspace)
    lines += [
        "",
        "## Where to write",
        "",
        f"- New items: `{workspace / 'review-queue' / 'incoming'}/<slug>.md`, written with your file-editing tool"
        " (apply_patch): a shell here-document (`<<`) fails here, as the sandbox has no writable temporary folder.",
        f"- The launcher's records, which you can read and never write: `{ledger}`.",
        f"- Their format: `{repo_root / 'docs' / 'mandu-exchange.md'}`.",
        f"- Check them before you finish: `/usr/bin/python3 {repo_root / 'src/bin/gr0wthlab'} check-incoming`.",
        f"- Check your quote records, Angle and Hook proposals, messages, and rejection codes: `{state.check_work}`.",
        "",
    ]
    return "\n".join(lines)


def review_word(state: RunState) -> str:
    """The agent's own closing line, quoted as its word, or that it left none. A line that is neither closing line,
    as one wrapped in backticks is not, is quoted as it stands, since the launcher reads it as no confirmation."""
    if not state.agent_summary.strip():
        return "none; the agent left no summary"
    line = " ".join(state.review.split())
    shown = line if len(line) <= REVIEW_WORD_LIMIT else line[:REVIEW_WORD_LIMIT].rstrip() + "..."
    if state.review == REVIEW_COMPLETE or state.review.startswith(REVIEW_INCOMPLETE):
        return f'"{shown}"'
    return (
        f'its last line, "{shown}", is neither of the closing lines the launcher accepts, the plain text'
        f" `{REVIEW_COMPLETE}` or `{REVIEW_INCOMPLETE}: ...`"
    )


def agent_setting(state: RunState) -> str:
    """The model and reasoning effort the agent ran with, as the run record keeps them."""
    model, effort = state.agent.get("model"), state.agent.get("reasoning_effort")
    return f"`{model}` at `{effort}` reasoning effort" if model and effort else ""


def work_summary(state: RunState) -> str:
    """One line for the top of the report: the launcher's counts, then the agent's word, each named for what it is."""
    if state.work is None:
        return ""
    seconds = state.agent.get("agent_seconds")
    took = f", in {span_text(float(seconds))} of agent time" if seconds is not None else ""
    return (
        f"The agent's work, as the launcher counted it: {work.summary(state.work)}{took}. The agent's own word:"
        f" {review_word(state)}."
    )


def work_lines(state: RunState) -> list[str]:
    """The run report's account of the agent's work: the launcher's counts first, then the agent's own word, each
    named for what it is."""
    if state.work is None:
        return ["The launcher counted nothing: the agent did not start, or its work could not be counted."]
    lines = [
        "Counted by the launcher from Codex's record of the session, the Draft files the run left, and the Review"
        " Queue. None of these comes from what the agent says of itself, and none changes what is queued, blocked, or"
        " marked incomplete:",
        "",
    ]
    seconds = state.agent.get("agent_seconds")
    if seconds is not None:
        setting = agent_setting(state)
        lines.append(
            f"- Agent time: {span_text(float(seconds))} of its {state.time_limit} limit"
            + (f", with {setting}." if setting else ".")
        )
    lines += [f"- {line}" for line in work.count_lines(state.work)]
    lines += ["", "The agent's own word, which the launcher does not check:", "", f"- {review_word(state)}"]
    return lines


def summary_lines(state: RunState) -> list[str]:
    failed = state.failed_sources()
    open_items = state.queue_after
    carried = sum(1 for entry in open_items if entry.get("carried_over"))
    agent = state.agent.get("exit_code")
    lines = [f"- {run_tally(state.tallies).line()}", f"- {start_line(state)}"]
    lines += [f"- {line}" for line in state.notes]
    if agent == 0 and state.ending == attempts.COMPLETED:
        lines.append("- The run finished.")
    elif agent == 0:
        lines.append(
            f"- The agent ended without an error, but the Mac slept during the run and {state.review_gap()}, so its"
            " work this run may be incomplete."
        )
    elif state.timed_out:
        lines.append(
            f"- The run timed out: the agent was still running at its {state.time_limit} time limit, so the launcher"
            " stopped it and finished the run without it. What the agent had written was checked as always, and each"
            " output that needed the agent this run is incomplete; see Outputs and Agent below."
        )
    elif not state.agent.get("agent_started"):
        lines.append("- The agent did not start; see Agent below. Everything the launcher does alone still ran.")
    else:
        lines.append(f"- The agent stopped with exit code {agent}; its work this run may be incomplete.")
    if state.asleep:
        lines.append(
            f"- The Mac was asleep for about {span_text(state.asleep)} while the agent ran, which counts toward the"
            " agent's time limit."
        )
    elsewhere = state.slept - state.asleep
    if state.attempt is not None and elsewhere >= ASLEEP_AT_LEAST:
        lines.append(f"- The Mac was asleep for about {span_text(elsewhere)} of this run outside the agent's time.")
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
        lines.append(f"- Filming: {state.filming_problem or filming.tally(state.filming, state.agent_gap()).note}.")
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
    counted = work_summary(state)
    if counted:
        lines.append(f"- {counted}")
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
    lines += ["", "## Agent's work", ""] + work_lines(state)
    lines += ["", "## Agent", ""]
    removed = probe_files_removed(state)
    if removed:
        lines.append(
            "- Removed boundary probe files left in the areas, before the agent started: "
            + ", ".join(f"`{path}`" for path in removed)
        )
    preflight = state.agent.get("preflight") or {}
    if preflight:
        lines.append(
            f"- Boundary preflight: {'passed' if preflight.get('ok') else 'FAILED'}, refused "
            f"{len(preflight.get('refused', []))} paths and allowed {len(preflight.get('writable', []))} areas."
        )
        network = preflight.get("network")
        if network:
            reached = network.get("reached", [])
            lines.append(
                f"- Sandbox network: {len(network.get('unreachable', [])) + len(reached)} listed hosts tried from"
                f" inside the sandbox, reached: {', '.join(reached) or 'none'}."
            )
    if state.agent.get("fingerprint"):
        lines.append(f"- Configuration fingerprint: `{state.agent['fingerprint']}`")
    if state.agent.get("error"):
        lines.append(f"- Did not start: {state.agent['error']}")
    if state.agent.get("agent_seconds") is not None:
        took = span_text(float(state.agent["agent_seconds"]))
        asleep = f", about {span_text(state.asleep)} of it with the Mac asleep" if state.asleep else ""
        lines.append(f"- Agent time: {took}{asleep}; time limit {state.time_limit}.")
    if state.timed_out:
        lines.append(f"- Timed out: {state.stop.describe()}.")
        lines.append(f"- Exit code: {state.agent.get('exit_code')}, the run's own for an agent stopped at its limit")
    else:
        lines.append(f"- Exit code: {state.agent.get('exit_code', 'none')}")
    lines.append(f"- Code: {state.code}" + (f"; {state.sync['detail']}" if state.sync else ""))
    lines.append(f"- Task definition: `{state.instruction}`")
    if state.agent_summary.strip():
        lines += ["", "The agent's own summary:", ""]
        lines += ["> " + line if line else ">" for line in state.agent_summary.strip().splitlines()]
    if state.problems:
        lines += ["", "## Launcher problems", ""] + [f"- {problem}" for problem in state.problems]
    return "\n".join(lines) + "\n"


def bullet(text: str) -> str:
    """A notice's list line, on one line whatever the text it quotes holds."""
    return "- " + " ".join(text.split())


def problems_notice(state: RunState, report_path: str) -> tuple[str, str, str, str] | None:
    """One notice for the Founder per run with problems, in plain outcome language; None if there were none.

    A notice about one kind of problem says what it is in its title; a notice about several counts every problem.
    A run that timed out says so first, in its title and its text, whatever else went wrong.
    A weekly scheduled run that the Mac's sleep cut short queues no notice for that alone while a fresh run follows
    by itself, and its notice then leaves out the work its agent did not reach, which that run does again and reports
    on itself; once the run due then has no attempt left, the notice lists everything and says so in its title.
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
    agent = state.agent.get("exit_code")
    follows = f" {what_follows(state)}" if what_follows(state) else ""
    if not state.agent.get("agent_started"):
        error = state.agent.get("error") or "see the run report"
        sections.append((1, f"the agent did not start on {day}", f"The agent did not start: {error}.{follows}"))
    elif state.timed_out:
        needs = ", ".join(state.agent_incomplete) or "nothing"
        # A weekly scheduled run the Mac's sleep cut short needs no higher limit, so its notice does not point at one.
        slept = state.attempt is not None and state.ending == attempts.SLEPT
        limit = (
            ""
            if slept
            else " The next run does this work again; if runs keep timing out, the limit is"
            " `agent.time_limit_seconds` in `config/run.json`."
        )
        sections.insert(
            0,
            (
                1,
                f"the run timed out on {day}",
                f"The agent was still running at its {state.time_limit} time limit, so the launcher stopped it and"
                " finished the run without it. What the agent had written by then was checked as always: anything"
                " queued from it passed every check, and anything unfinished was set aside or blocked. Incomplete this"
                f" run: {needs}.{limit}{follows}",
            ),
        )
    elif agent != 0:
        sections.append(
            (
                1,
                f"the agent stopped early on {day}",
                f"The agent stopped with exit code {agent}, so this run's review may be incomplete.{follows}",
            )
        )
    elif state.review.startswith(REVIEW_INCOMPLETE):
        why = state.review_reason()
        sections.append(
            (
                1,
                f"the package review was not finished on {day}",
                "The Marketing Engineer did not finish reviewing the Go-To-Market Package"
                + (f" ({why})" if why else "")
                + ", so a contradiction it did not reach is not in the Review Queue yet; the next run reviews it"
                f" again.{follows}",
            )
        )
    elif state.review_gap():
        sections.append(
            (
                1,
                f"the package review was not confirmed finished on {day}",
                "The Marketing Engineer did not confirm that it finished every pass of its review of the Go-To-Market"
                " Package, so a contradiction it did not reach may not be in the Review Queue yet; the next run reviews"
                f" it again.{follows}",
            )
        )
    if state.problems:
        sections.append(
            (
                len(state.problems),
                f"the launcher hit {plural(len(state.problems), 'problem')} on {day}",
                "The launcher hit problems:\n" + "\n".join(bullet(problem) for problem in state.problems),
            )
        )
    if not sections or (state.again and len(sections) == 1):
        # A run the Mac's sleep cut short, with nothing else wrong, needs no notice while a fresh run follows by
        # itself: its own report says what happened, and the fresh run does the work again.
        return None
    total = sum(count for count, _, _ in sections)
    if state.attempt is not None and state.ending == attempts.SLEPT and not state.again:
        title = f"Notice: the Mac's sleep cut short every attempt at the run due {state.attempt.due:%Y-%m-%d}"
    elif len(sections) == 1:
        title = f"Notice: {sections[0][1]}"
    elif state.timed_out:
        title = f"Notice: the run timed out on {day} and had {plural(total - 1, 'other problem')}"
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
