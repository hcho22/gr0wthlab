"""Render the LaunchAgent that starts scheduled runs through the same launcher as on-demand runs.

The launcher only prints the plist; installing it in ~/Library/LaunchAgents is a deliberate step outside the repository.
The weekly LaunchAgent starts the launcher at the weekly time and again at an interval, and every such start is the
owed-run check of attempts.py, which ends at once when nothing is owed. A one-off LaunchAgent starts the launcher
once, at its time, and that start always runs. Nothing in the plist holds the Mac awake, wakes it, or keeps a process
running.
"""

from __future__ import annotations

import plistlib
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from .codex import SYSTEM_PATH

WEEKDAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
DEFAULT_LABEL = "gr0wthlab.weekly-run"


class ScheduleError(ValueError):
    pass


def weekday(day: str) -> int:
    """A day's number as datetime counts weekdays, Monday 0."""
    return (WEEKDAYS.index(day.lower()) - 1) % 7


def parse_time(text: str) -> dict[str, int]:
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text)
    if not match:
        raise ScheduleError(f"time must be HH:MM, got {text!r}")
    return {"Hour": int(match.group(1)), "Minute": int(match.group(2))}


def weekly(day: str, time: str) -> dict[str, int]:
    """launchd.plist(5) says a calendar job the Mac slept through is started once, the next time the Mac wakes, and
    a dark wake is a wake; it says nothing of a Mac that was switched off. The weekly LaunchAgent's interval covers
    both, since every start it makes is a check of whether the run is still owed."""
    if day.lower() not in WEEKDAYS:
        raise ScheduleError(f"day must be one of {', '.join(WEEKDAYS)}")
    return dict(parse_time(time), Weekday=WEEKDAYS.index(day.lower()))


def once(moment: str) -> dict[str, int]:
    try:
        when = datetime.strptime(moment, "%Y-%m-%dT%H:%M")
    except ValueError as error:
        raise ScheduleError(f"moment must be YYYY-MM-DDTHH:MM, got {moment!r}") from error
    return {"Month": when.month, "Day": when.day, "Hour": when.hour, "Minute": when.minute}


def run_arguments(entry: Path, instruction: Path, once_at: str | None) -> list[str]:
    """The scheduled run's command line; a weekly run takes its schedule from config/run.json, as the LaunchAgent does,
    and a one-off run names its time, so either can tell whether it started late."""
    arguments = [str(entry), "run", "--trigger", "scheduled", "--instruction", str(instruction)]
    if once_at:
        arguments += ["--once", once_at]
    return arguments


def boundary_check_arguments(entry: Path) -> list[str]:
    """A one-off scheduled boundary check, which repeats the US-ME02 check on the scheduled path."""
    return [str(entry), "boundary-check", "--trigger", "scheduled"]


def launch_agent(
    label: str,
    arguments: Sequence[str],
    repo_root: Path,
    calendar: Mapping[str, int],
    overrides: Mapping[str, str],
    log_dir: Path,
    check_every_seconds: int | None = None,
) -> bytes:
    """check_every_seconds is how often launchd starts the job again besides its calendar time, counted while the Mac
    is running; launchd never starts a job that is still running, so the two never start it twice at once."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", label):
        raise ScheduleError(f"label must be a reverse-DNS style name, got {label!r}")
    environment = {"PATH": ":".join(SYSTEM_PATH)}
    environment.update({key: value for key, value in overrides.items() if key.startswith("GR0WTHLAB_")})
    agent = {
        "Label": label,
        "ProgramArguments": list(arguments),
        "WorkingDirectory": str(repo_root),
        "EnvironmentVariables": environment,
        "StartCalendarInterval": dict(calendar),
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": str(log_dir / f"{label}.out.log"),
        "StandardErrorPath": str(log_dir / f"{label}.err.log"),
    }
    if check_every_seconds is not None:
        agent["StartInterval"] = check_every_seconds
    return plistlib.dumps(agent, sort_keys=True)
