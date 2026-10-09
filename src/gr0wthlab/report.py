"""What a run tells the agent before it starts (the brief) and the Founder after it ends (the run report).

Both are rendered from the launcher's own state, never from anything the agent wrote, except the agent's closing
summary, which the report quotes as the agent's account.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import exchange, package, schedule, waitlist
from .state import Tally, run_tally

SKIPPED = "skipped"
COMPLETE = "complete"
INCOMPLETE = "incomplete"
NOT_BUILT = "not built yet"
# The line the agent's summary ends with: its own account of whether it finished every pass of its review.
REVIEW_COMPLETE = "Review: complete"
REVIEW_INCOMPLETE = "Review: incomplete"
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")
NOTICE_BODY_LIMIT = exchange.MAX_ITEM_CHARS // 2


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
    tallies: list[Tally] = field(default_factory=list)
    state_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

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

    def review_gap(self) -> str:
        """Why the agent's package review is incomplete, or "" when it finished: it must stop with exit code 0 and end
        its summary with the line `Review: complete`, so a summary that says otherwise, or says nothing, is not."""
        if self.agent.get("exit_code") != 0:
            return "the agent did not finish"
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
    """Approximate US dollars at API prices; cached and cache-write tokens are counted within input tokens."""
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


def start_line(state: RunState) -> str:
    started = wall_clock(state.started).strftime("%A %Y-%m-%d %H:%M")
    if state.trigger != "scheduled":
        return f"On demand, started {started} (Mac local time)."
    due = state.due.strftime("%A %Y-%m-%d %H:%M")
    if state.late:
        return (
            f"Started late: due {due}, started {started}, {duration(state.lateness)} after its time. "
            "The Mac was probably asleep or off when it was due."
        )
    return f"Scheduled for {due}; started on time at {started}."


def cost_line(state: RunState) -> str:
    if not state.usage:
        return "Approximate cost: unknown; the agent reported no token counts."
    usage = state.usage
    tokens = (
        f"{usage['input_tokens']:,} input tokens ({usage['cached_input_tokens']:,} cached) "
        f"and {usage['output_tokens']:,} output tokens"
    )
    amount = f"{state.cost:.2f}" if state.cost >= 0.1 else f"{state.cost:.3f}"
    return f"Approximate cost: about ${amount} at API prices, for {tokens}."


def file_line(file: package.FileResult) -> str:
    """What happened to one package file this run, after its read, changed, or failed status."""
    if file.status == package.FAILED:
        return f"{file.reason}."
    return {
        "changed": "its fingerprint changed since the previous snapshot",
        "added": "new since the previous snapshot",
        "first read": "first snapshot of this file",
    }.get(str(file.change), "unchanged since the previous snapshot")


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


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
    failed = state.failed_sources()
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
        lines.append("Do not queue these again; to change one, write a new item with `supersedes: <id>`.")
        for entry in state.queue_before:
            line = f"- `{entry['id']}` ({entry['kind']}): {entry['ask']}"
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
    lines += [
        "",
        "## Where to write",
        "",
        f"- New items: `{workspace / 'review-queue' / 'incoming'}/<slug>.md`, written with your file-editing tool"
        " (apply_patch): a shell here-document (`<<`) fails here, as the sandbox has no writable temporary folder.",
        f"- The launcher's records, which you can read and never write: `{ledger}`.",
        f"- Their format: `{repo_root / 'docs' / 'mandu-exchange.md'}`.",
        f"- Check them before you finish: `/usr/bin/python3 {repo_root / 'src/bin/gr0wthlab'} check-incoming`.",
        "",
    ]
    return "\n".join(lines)


def summary_lines(state: RunState) -> list[str]:
    failed = state.failed_sources()
    open_items = state.queue_after
    carried = sum(1 for entry in open_items if entry.get("carried_over"))
    agent = state.agent.get("exit_code")
    lines = [f"- {run_tally(state.tallies).line()}", f"- {start_line(state)}"]
    lines += [f"- {line}" for line in state.notes]
    if agent == 0:
        lines.append("- The run finished.")
    elif not state.agent.get("agent_started"):
        lines.append("- The agent did not start; see Agent below. Everything the launcher does alone still ran.")
    else:
        lines.append(f"- The agent stopped with exit code {agent}; its work this run may be incomplete.")
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
    if state.notice:
        lines.append(f"- Problems this run are listed in the notice `{state.notice}`.")
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
    lines += ["", "## Run state", ""]
    lines += [f"- {tally.workflow}: {tally.line()}" for tally in state.tallies]
    if state.state_notes:
        lines += ["", "The run state disagreed with the Review Queue, which wins; the state was repaired:", ""]
        lines += [f"- {note}" for note in state.state_notes]
    lines += ["", "## Outputs", ""] + table(["Output", "Status", "Detail"], state.outputs)
    lines += ["", "## Agent", ""]
    preflight = state.agent.get("preflight") or {}
    if preflight:
        lines.append(
            f"- Boundary preflight: {'passed' if preflight.get('ok') else 'FAILED'}, refused "
            f"{len(preflight.get('refused', []))} paths and allowed {len(preflight.get('writable', []))} areas."
        )
    if state.agent.get("fingerprint"):
        lines.append(f"- Configuration fingerprint: `{state.agent['fingerprint']}`")
    if state.agent.get("error"):
        lines.append(f"- Did not start: {state.agent['error']}")
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
    if not state.agent.get("agent_started"):
        error = state.agent.get("error") or "see the run report"
        sections.append((1, f"the agent did not start on {day}", f"The agent did not start: {error}."))
    elif agent != 0:
        sections.append(
            (
                1,
                f"the agent stopped early on {day}",
                f"The agent stopped with exit code {agent}, so this run's review may be incomplete.",
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
                " again.",
            )
        )
    elif state.review_gap():
        sections.append(
            (
                1,
                f"the package review was not confirmed finished on {day}",
                "The Marketing Engineer did not confirm that it finished every pass of its review of the Go-To-Market"
                " Package, so a contradiction it did not reach may not be in the Review Queue yet; the next run reviews"
                " it again.",
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
    if not sections:
        return None
    title = (
        f"Notice: {sections[0][1]}"
        if len(sections) == 1
        else f"Notice: the run on {day} had {plural(sum(count for count, _, _ in sections), 'problem')}"
    )
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
    """Good-Fit opt-ins against the Beta Cohort bar of about 50 sign-ups."""
    bar = reading.rules.bar
    have = reading.good_fit_opt_ins
    where = "the bar is reached" if have >= bar else f"{round(100 * have / bar)}% of the way"
    return f"{plural(have, 'good-Fit opt-in')} of about {bar}, {where}"


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
        f"Read the view generated {reading.generated_at.isoformat()}; Waitlist Evidence: `{evidence_file}`.",
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
