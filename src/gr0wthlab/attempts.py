"""Whether the week's scheduled run is still owed, told from the launcher's own records, never from memory.

Nothing holds the Mac awake for a run, so a run happens when the Mac is awake: at its scheduled time if the Mac is
fully awake then, and otherwise once it next is. The LaunchAgent starts the launcher at the weekly time and again
every few minutes the Mac is running, and each such start is first a check of ledger/run-reports/attempts/<due>.json,
the record of every run made since that time fell due: each scheduled attempt, noted before its agent starts, and each
run on demand or one-off scheduled run, noted as it ends. A run starts only while that record shows the run still
owed: none has completed, every scheduled attempt so far was cut short by the Mac's sleep, and fewer attempts were made
than config/run.json allows. Only sleep earns another attempt, wherever in the attempt it fell: an attempt that did not
complete with the Mac awake throughout, or that left no ending, waits for the Founder. An attempt the Mac slept during
completed only if its agent ended without an error and confirmed its review. A one-off scheduled run (--once) is no
part of this: it always runs, as a run on demand does, and is never an attempt.

A sleeping Mac wakes by itself every few minutes, for about a minute with its display off, to do its own housekeeping
(a dark wake), and launchd starts jobs then as at any other time. A run takes longer than a dark wake lasts, so one
started in it would be frozen again almost at once and use up an attempt. A scheduled start therefore also asks
whether the Mac is fully awake, and starts nothing when it is not. That question only reads the Mac's power state:
nothing in the launcher holds the Mac awake, wakes it, or schedules a wake.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import process
from .areas import Store, UnsafeFile, read_plain

FORMAT = 1
FOLDER = ("run-reports", "attempts")
SCHEDULED = "scheduled"
ON_DEMAND = "on-demand"
ONE_OFF = "one-off"

# How a run ended, as the record keeps it.
COMPLETED = "completed"
SLEPT = "cut-short-by-sleep"
TIMED_OUT = "timed-out"
FAILED = "agent-stopped-early"
NOT_STARTED = "agent-not-started"
REFUSED = "refused-to-start"
STOPPED = "stopped"
NO_REPORT = "no-report"
# Each ending as it reads after "this one" or "the attempt started <when>".
SAID = {
    COMPLETED: "completed",
    SLEPT: "was cut short by the Mac's sleep",
    TIMED_OUT: "timed out with the Mac awake",
    FAILED: "had a session stop early with the Mac awake",
    NOT_STARTED: "could not start one of its sessions",
    REFUSED: "was refused before it started",
    STOPPED: "stopped before it finished",
    NO_REPORT: "left no report",
}

# Fewer seconds than this between a wall-clock time and the awake time of the same span are the two clocks' own
# difference, not the Mac asleep.
ASLEEP_AT_LEAST = 5

PMSET = "/usr/bin/pmset"
# The capability a Mac has only when it is fully awake; a dark wake has the CPU and the network without it.
FULL_WAKE = "Graphics"


@dataclass(frozen=True)
class Attempt:
    """One scheduled attempt at the run due at one time, as its run report tells it: which attempt it is, how many the
    run may take, and when each earlier one started, every one of them cut short by the Mac's sleep."""

    due: datetime
    number: int
    limit: int
    earlier: tuple[datetime, ...] = ()


@dataclass
class Record:
    """Every run made since one due time, in the order noted. due is the Mac's local wall-clock time, as the schedule
    states it; problem is why the file could not be used, when it could not, and the record then counts as empty."""

    due: datetime
    runs: list[dict[str, object]] = field(default_factory=list)
    problem: str = ""

    @property
    def attempts(self) -> list[dict[str, object]]:
        """The scheduled attempts, in order; a run on demand or a one-off scheduled run is never one."""
        return [run for run in self.runs if run["trigger"] == SCHEDULED]


def path(store: Store, due: datetime) -> Path:
    return store.path(*FOLDER, f"{due:%Y%m%dT%H%M}.json")


def started(run: Mapping[str, object]) -> datetime:
    return datetime.fromisoformat(str(run["started_at"]))


def parse(data: object, due: datetime) -> list[dict[str, object]]:
    """The runs a record file holds; anything that is not such a record raises ValueError."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"it is not a format {FORMAT} record of attempts")
    if data.get("due") != due.isoformat(timespec="minutes"):
        raise ValueError(f"it is not the record of the run due {due.isoformat(timespec='minutes')}")
    runs = data.get("runs")
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise ValueError("runs must list records")
    for run in runs:
        if run.get("trigger") not in (SCHEDULED, ON_DEMAND, ONE_OFF):
            raise ValueError("a run is not a scheduled attempt, a run on demand, or a one-off run")
        if run.get("ending") is not None and run["ending"] not in SAID:
            raise ValueError(f"a run has the unknown ending {run['ending']!r}")
        if started(run).tzinfo is None:
            raise ValueError("a run's started_at carries no UTC offset")
    return runs


def load(store: Store, due: datetime) -> Record:
    """The record of the run due at one time; a missing file is a run nobody has attempted yet."""
    file = path(store, due)
    if not os.path.lexists(str(file)):
        return Record(due)
    try:
        return Record(due, parse(json.loads(read_plain(file).decode("utf-8")), due))
    except (OSError, ValueError, TypeError, KeyError, UnsafeFile) as error:
        return Record(due, problem=str(error))


def load_to_write(store: Store, due: datetime) -> Record:
    """The record, about to be written again: a file that could not be used is first set aside beside it, never
    overwritten, and problem still says why."""
    record = load(store, due)
    if record.problem:
        file = path(store, due)
        store.move(file, file.with_suffix(".unreadable"))
    return record


def save(store: Store, record: Record) -> None:
    data = {"format": FORMAT, "due": record.due.isoformat(timespec="minutes"), "runs": record.runs}
    store.write_json(path(store, record.due), data)


def waiting(record: Record, limit: int) -> str:
    """Why no scheduled run starts by itself for this due time, or "" while one is owed. Only an attempt cut short by
    sleep leaves the run owed, and only while attempts remain."""
    done = next((run for run in record.runs if run.get("ending") == COMPLETED), None)
    if done:
        return f"the run due {record.due:%A %Y-%m-%d %H:%M} completed as run {done.get('run')}"
    tried = record.attempts
    for number, run in enumerate(tried, 1):
        ending = run.get("ending")
        if ending is None:
            return f"attempt {number} is in progress, or was stopped before it could note how it ended"
        if ending != SLEPT:
            return (
                f"attempt {number} {SAID[str(ending)]}, and only an attempt cut short by the Mac's sleep is run again"
            )
    if len(tried) >= limit:
        return f"the Mac's sleep cut short all of the {limit} attempts this run may take"
    return ""


def claim(store: Store, record: Record, limit: int, at: datetime) -> Attempt:
    """Note a scheduled attempt in the record before it does anything else, so one that never ends still counts
    toward the limit. Called under the run lock, and only while waiting() says the run is owed, so every earlier
    attempt was cut short by sleep."""
    earlier = tuple(started(run) for run in record.attempts)
    record.runs.append({"trigger": SCHEDULED, "attempt": len(earlier) + 1, "started_at": at.isoformat()})
    save(store, record)
    return Attempt(record.due, len(earlier) + 1, limit, earlier)


def finish(
    store: Store,
    due: datetime,
    trigger: str,
    at: datetime,
    run_id: str | None,
    ending: str,
    ended: datetime,
    asleep: float = 0.0,
) -> None:
    """Note how a run ended, under the run lock: a scheduled attempt in the entry it claimed, and a run on demand, a
    one-off scheduled run, or a scheduled start that never came to claim an attempt, in an entry of its own. asleep is
    about how many seconds the Mac slept during the run."""
    record = load_to_write(store, due)
    entry = next((run for run in record.attempts if run.get("ending") is None), None) if trigger == SCHEDULED else None
    if entry is None:
        entry = {"trigger": trigger, "started_at": at.isoformat()}
        if trigger == SCHEDULED:
            entry["attempt"] = len(record.attempts) + 1
        record.runs.append(entry)
    entry.update(run=run_id, ended_at=ended.isoformat(), ending=ending)
    if asleep:
        entry["asleep_seconds"] = round(asleep)
    save(store, record)


def left_without_ending(store: Store) -> list[tuple[str, str]]:
    """Close every scheduled attempt whose record still has no ending, and say so in one line each, with a name for
    that line. Called under the run lock, when no run is in progress: such an attempt was stopped before it could
    write its report, for example by a restart of the Mac, and it does not earn another attempt."""
    folder = store.path(*FOLDER)
    lines = []
    for file in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            record = load(store, datetime.strptime(file.stem, "%Y%m%dT%H%M"))
        except ValueError:
            continue
        left = [run for run in record.attempts if run.get("ending") is None]
        for run in left:
            run["ending"] = NO_REPORT
            line = (
                f"The scheduled run started {started(run).astimezone():%A %Y-%m-%d %H:%M}, attempt {run.get('attempt')}"
                f" at the run due {record.due:%A %Y-%m-%d %H:%M}, left no report: it was stopped before it could write"
                " one, for example by a restart of the Mac. No run started by itself after it."
            )
            lines.append((f"{file.stem}-attempt-{run.get('attempt')}", line))
        if left:
            save(store, record)
    return lines


def asleep_for(seconds: float, awake: float) -> float:
    """About how many of a span's seconds the Mac was asleep, its wall-clock time less its awake time; 0 when the Mac
    stayed awake."""
    gap = seconds - awake
    return gap if gap >= ASLEEP_AT_LEAST else 0.0


def ending(shortfall: str | None, asleep: float, confirmed: bool = True) -> str:
    """How a run that reached its report ended, from how its sessions ended and the seconds the Mac slept from the
    run's start to its last session's end. shortfall is None when every session the run had work for started and
    ended without an error, and otherwise how the first one that fell short did: NOT_STARTED, TIMED_OUT, or FAILED. A
    run with a session that fell short counts as cut short by sleep whenever the Mac slept in that time, wherever the
    sleep fell and whichever session it froze. confirmed is False only for a scheduled attempt in which a session's
    summary did not confirm its work: an agent that sleep froze in the middle of its work can end without an error
    and with the work unfinished, so such an attempt completed only if the Mac stayed awake, and was cut short by
    sleep otherwise."""
    if shortfall is None and (confirmed or not asleep):
        return COMPLETED
    if asleep:
        return SLEPT
    return shortfall or COMPLETED


def fully_awake() -> bool | None:
    """Whether the Mac is fully awake, as when someone has woken it, and not in a dark wake; None when the Mac did not
    say. This reads the power state and changes nothing about it."""
    try:
        asked = process.run([PMSET, "-g", "systemstate"], process.QUICK)
    except OSError:
        return None
    said = re.search(r"^Current System Capabilities are:(.*)$", asked.stdout, re.MULTILINE) if asked.ok else None
    return FULL_WAKE in said.group(1).split() if said else None
