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

from . import exchange, package, schedule
from .state import Tally, run_tally

SKIPPED = "skipped"
COMPLETE = "complete"
INCOMPLETE = "incomplete"
NOT_BUILT = "not built yet"
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")


@dataclass
class SourceLine:
    name: str
    status: str
    detail: str = ""
    needed_by: tuple[str, ...] = ()


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
    decisions: list = field(default_factory=list)  # queue.DecisionOutcome
    decision_problems: list[tuple[str, list[str]]] = field(default_factory=list)
    sittings: list[exchange.Sitting] = field(default_factory=list)
    queue_before: list[Mapping[str, object]] = field(default_factory=list)
    closed_proposals: list[Mapping[str, object]] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    set_aside: list = field(default_factory=list)  # queue.SetAside
    restored: list[str] = field(default_factory=list)
    queue_after: list[Mapping[str, object]] = field(default_factory=list)
    agent: Mapping[str, object] = field(default_factory=dict)
    agent_summary: str = ""
    usage: Mapping[str, int] | None = None
    cost: float | None = None
    outputs: list[tuple[str, str, str]] = field(default_factory=list)  # title, status, detail
    problems: list[str] = field(default_factory=list)
    notice: str | None = None
    tallies: list[Tally] = field(default_factory=list)
    state_notes: list[str] = field(default_factory=list)
    carried_runs: dict[str, int] = field(default_factory=dict)

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


def wall_clock(moment: datetime) -> datetime:
    """The Mac's local wall-clock time, the clock launchd schedules by."""
    return moment.astimezone().replace(tzinfo=None)


def due_time(started: datetime, weekly: tuple[str, str] | None = None, once: str | None = None) -> datetime | None:
    """When a scheduled run was due: the latest weekly time at or before its start, or the one-off time."""
    local = wall_clock(started)
    if once:
        return datetime.strptime(once, "%Y-%m-%dT%H:%M")
    if not weekly:
        return None
    calendar = schedule.weekly(*weekly)
    python_weekday = (calendar["Weekday"] - 1) % 7
    due = local.replace(hour=calendar["Hour"], minute=calendar["Minute"], second=0, microsecond=0)
    due -= timedelta(days=(local.weekday() - python_weekday) % 7)
    if due > local:
        due -= timedelta(days=7)
    return due


def local_date(moment: str) -> str:
    """The Mac's local date of a recorded time, as the Founder reads it."""
    return wall_clock(datetime.fromisoformat(moment)).strftime("%Y-%m-%d")


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
    if state.due is None:
        return f"Scheduled, started {started}; its due time is unknown, so lateness was not checked."
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
    lines = []
    for outcome in state.decisions:
        decision, entry = outcome.decision, outcome.entry or {}
        ask = entry.get("ask", "")
        if outcome.status == "taken":
            if decision.decision == exchange.APPROVE:
                note = f" Note: {decision.note}" if decision.note else ""
                lines.append(f"- Approved `{decision.item}`: {ask}.{note}")
            else:
                lines.append(f"- Rejected `{decision.item}`: {ask}. Reason: {decision.reason}")
        elif not taken_only and outcome.status != "already-taken":
            lines.append(f"- Not used, `{decision.item}`: {outcome_text(outcome.status)} ({outcome.source})")
    if not taken_only:
        for name, problems in state.decision_problems:
            lines.append(f"- Could not read `{name}`: {'; '.join(problems)}")
    return lines


def outcome_text(status: str) -> str:
    return {
        "unknown-item": "no queued item has this identifier",
        "item-withdrawn": "the item had already been withdrawn by a newer one",
        "conflict": "it differs from the decision already taken for this item, which stands",
    }.get(status, status)


def render_brief(state: RunState, repo_root: Path, workspace: Path) -> str:
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
        f"- Package snapshot: `{workspace / state.snapshot_file}`"
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
        lines += [f"- `{entry['id']}` ({entry['kind']}): {entry['ask']}" for entry in state.queue_before]
    else:
        lines.append("None.")
    lines += ["", "## Package-change proposals already decided or withdrawn", ""]
    if state.closed_proposals:
        lines.append("Do not propose these again unless new Evidence answers the reason.")
        for entry in state.closed_proposals:
            reason = f" Reason: {entry['reason']}" if entry.get("reason") else ""
            lines.append(f"- `{entry['id']}` {entry['status']}: {entry['ask']}.{reason}")
    else:
        lines.append("None.")
    lines += [
        "",
        "## Where to write",
        "",
        f"- New items: `{workspace / 'review-queue' / 'incoming'}/<slug>.md`.",
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
    if agent == 0:
        lines.append("- The run finished.")
    elif not state.agent.get("agent_started"):
        lines.append("- The agent did not start; see Agent below. Everything the launcher does alone still ran.")
    else:
        lines.append(f"- The agent stopped with exit code {agent}; its work this run may be incomplete.")
    lines.append(
        f"- Sources: {len(failed)} failed"
        + (f" ({', '.join(line.name for line in failed)})" if failed else "")
        + f", {sum(1 for line in state.sources if line.status == package.CHANGED)} changed,"
        + f" {sum(1 for line in state.sources if line.status == package.READ)} read,"
        + f" {sum(1 for line in state.sources if line.status == SKIPPED)} skipped."
    )
    taken = [outcome for outcome in state.decisions if outcome.status == "taken"]
    lines.append(
        f"- Review Queue: {plural(len(open_items), 'item')} open for the next sitting ({len(state.published)} new"
        f" this run, {carried} carried over); {plural(len(taken), 'Founder decision')} taken in."
    )
    if state.problems or state.set_aside or state.restored or failed:
        lines.append(f"- Problems this run are listed in the notice `{state.notice}`." if state.notice else "")
    lines.append(f"- {cost_line(state)}")
    return [line for line in lines if line]


def render_report(state: RunState) -> str:
    lines = [f"# Run report: {state.run_id}", "", "## Summary", ""] + summary_lines(state)
    lines += ["", "## Sources", ""]
    lines += table(["Source", "Result", "Detail"], [[line.name, line.status, line.detail] for line in state.sources])
    lines += ["", "## Package changes since the previous run", ""] + package_changes(state)
    lines += ["", "## Founder decisions", ""] + (decision_lines(state) or ["No new decisions."])
    if state.sittings:
        lines += [""] + [f"- Sitting {sitting.day}: {sitting.minutes} minutes." for sitting in state.sittings]
    lines += ["", "## Review Queue", ""]
    if state.queue_after:
        for number, entry in enumerate(state.queue_after, 1):
            slot = f", slot {entry['slot']}" if entry.get("slot") else ""
            queued = local_date(str(entry["published_at"]))
            runs = state.carried_runs.get(str(entry["id"]), 1)
            carried = f", carried over from {queued}, {plural(runs, 'run')}" if entry.get("carried_over") else ""
            lines.append(f"{number}. `{entry['id']}` ({entry['kind']}{slot}{carried}): {entry['ask']}")
    else:
        lines.append("Nothing is waiting for the Founder.")
    for item in state.set_aside:
        lines.append(f"- Set aside, not queued: `{item.name}`: {'; '.join(item.problems)}")
    for path in state.restored:
        lines.append(f"- Undone: {path}")
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


def problems_notice(state: RunState, report_path: str) -> tuple[str, str, str, str] | None:
    """One notice for the Founder per run with problems, in plain outcome language; None if there were none.

    A notice about one problem says what it is in its title; a notice about several counts them.
    """
    day = wall_clock(state.started).strftime("%Y-%m-%d")
    sections: list[tuple[str, str]] = []
    failed = state.failed_sources()
    if failed:
        lines = ["These sources could not be read, so the work that needs them is incomplete this run:"]
        for line in failed:
            needs = ", ".join(line.needed_by) or "nothing else"
            lines.append(f"- {line.name}: {line.detail} Incomplete: {needs}.")
        sections.append((f"{plural(len(failed), 'source')} could not be read on {day}", "\n".join(lines)))
    taken_problems = [line[2:] for line in decision_lines(state) if line.startswith(("- Not used", "- Could not"))]
    if taken_problems:
        sections.append(
            (
                f"{plural(len(taken_problems), 'Mandu record')} could not be used on {day}",
                "Some records in Mandu could not be used, so the items they name are still open:\n"
                + "\n".join(f"- {line}" for line in taken_problems),
            )
        )
    if state.set_aside:
        sections.append(
            (
                f"{plural(len(state.set_aside), 'prepared item')} not queued on {day}",
                "Some items the Marketing Engineer prepared were not queued, because they did not meet the item format"
                " or asked the same as an item already queued or decided:\n"
                + "\n".join(f"- `{item.name}`: {'; '.join(item.problems)}" for item in state.set_aside),
            )
        )
    if state.restored:
        sections.append(
            (
                f"the launcher undid {plural(len(state.restored), 'change')} by the agent on {day}",
                "The agent changed records only the launcher writes; the launcher undid it:\n"
                + "\n".join(f"- {path}" for path in state.restored),
            )
        )
    agent = state.agent.get("exit_code")
    if not state.agent.get("agent_started"):
        error = state.agent.get("error") or "see the run report"
        sections.append((f"the agent did not start on {day}", f"The agent did not start: {error}."))
    elif agent != 0:
        sections.append(
            (
                f"the agent stopped early on {day}",
                f"The agent stopped with exit code {agent}, so this run's review may be incomplete.",
            )
        )
    if state.problems:
        sections.append(
            (
                f"the launcher hit {plural(len(state.problems), 'problem')} on {day}",
                "The launcher hit problems:\n" + "\n".join(f"- {problem}" for problem in state.problems),
            )
        )
    if not sections:
        return None
    title = (
        f"Notice: {sections[0][0]}" if len(sections) == 1 else f"Notice: the run on {day} had {len(sections)} problems"
    )
    body = (
        "\n\n".join(text for _, text in sections)
        + "\n\nEverything else in this run finished; the run report has the details."
    )
    touches = "- Nothing changes; this notice is for your information."
    evidence = f"- The run report: `{report_path}`"
    return title, body, touches, evidence
