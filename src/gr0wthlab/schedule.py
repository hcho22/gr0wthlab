"""Render the LaunchAgent that starts scheduled runs through the same launcher as on-demand runs.

The launcher only prints the plist; installing it in ~/Library/LaunchAgents is a deliberate step outside the repository.
"""

from __future__ import annotations

import plistlib
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from .codex import SYSTEM_PATH

WEEKDAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
DEFAULT_LABEL = "gr0wthlab.weekly-run"


class ScheduleError(ValueError):
    pass


def parse_time(text: str) -> dict[str, int]:
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text)
    if not match:
        raise ScheduleError(f"time must be HH:MM, got {text!r}")
    return {"Hour": int(match.group(1)), "Minute": int(match.group(2))}


def weekly(day: str, time: str) -> dict[str, int]:
    """A missed calendar job runs once when the Mac wakes, so a sleeping Mac delays the run instead of skipping it."""
    if day.lower() not in WEEKDAYS:
        raise ScheduleError(f"day must be one of {', '.join(WEEKDAYS)}")
    return dict(parse_time(time), Weekday=WEEKDAYS.index(day.lower()))


def once(moment: str) -> dict[str, int]:
    try:
        when = datetime.strptime(moment, "%Y-%m-%dT%H:%M")
    except ValueError as error:
        raise ScheduleError(f"moment must be YYYY-MM-DDTHH:MM, got {moment!r}") from error
    return {"Month": when.month, "Day": when.day, "Hour": when.hour, "Minute": when.minute}


def launch_agent(
    label: str,
    entry: Path,
    repo_root: Path,
    instruction: Path,
    calendar: Mapping[str, int],
    overrides: Mapping[str, str],
    log_dir: Path,
) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", label):
        raise ScheduleError(f"label must be a reverse-DNS style name, got {label!r}")
    environment = {"PATH": ":".join(SYSTEM_PATH)}
    environment.update({key: value for key, value in overrides.items() if key.startswith("GR0WTHLAB_")})
    return plistlib.dumps(
        {
            "Label": label,
            "ProgramArguments": [str(entry), "run", "--trigger", "scheduled", "--instruction", str(instruction)],
            "WorkingDirectory": str(repo_root),
            "EnvironmentVariables": environment,
            "StartCalendarInterval": dict(calendar),
            "RunAtLoad": False,
            "ProcessType": "Background",
            "StandardOutPath": str(log_dir / f"{label}.out.log"),
            "StandardErrorPath": str(log_dir / f"{label}.err.log"),
        },
        sort_keys=True,
    )
