"""Shot lists (US-ME09): what each asset of a 14-day window needs filmed, read from the kit in Mandu every run.

An Angle's Format cell in the Angle bank says what its asset is: its length, each recording it is made of, and what
the recording may not do. shot_list reads that cell into one beat-sheet shape per shot (what to record, on which
device, in real time or not, and whether it may be cut), keeping the cell's own words as what to record, so a shot
list never says more than the kit does: a fact the Format does not state is "not stated", never a guess. The
calendar's own checklist for every asset may add what holds for every screen recording.

requirements groups the calendar's days into filming jobs: the legs of an A/B pair are cut from one job's footage, so
the later leg films nothing. sittings then groups every shot into the fewest sittings the shot lists allow: shots that
state the same setup share one sitting, and nothing else in a shot list asks for another.

Nothing here is kept beyond the run, and nothing names a day, an Angle, or a device of its own: the kit decides.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from .kit import AssetCheck, Kit, KitDay, frozen_hook, recut_hooks

CAMERA = "camera"
DEVICE = "device"
UNSTATED = "not stated"
FOUNDER_ON_CAMERA = "founder on camera"
LENGTH = re.compile(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*s\b[\s:,]*")
# Where one recording may end and the next begin: "then", or "with" (as in "with a screen-record insert").
JOIN = re.compile(r"([\s,;]*\bthen\b\s*|\s+\bwith\b\s+)", re.IGNORECASE)
NO_CUTS = re.compile(r"\bno cuts?\b", re.IGNORECASE)
EVERY_TAKE = re.compile(r"\bno cuts?\b[^,;]*\beach\b", re.IGNORECASE)
REAL_TIME = re.compile(r"\breal[- ]time\b", re.IGNORECASE)
SCREEN_RECORDING = re.compile(r"\bscreen[- ]record(?:ing)?s?\b", re.IGNORECASE)
REAL_DEVICE = re.compile(r"\breal device\b", re.IGNORECASE)
CUTS_DECLARED = re.compile(r"\bcuts? only where\b", re.IGNORECASE)
# A footage file's name starts with its shot, then the leg whose opening it is, if any: d06-s1b-take-2.mov.
FILE_SHOT = re.compile(r"(d\d{2}-s\d+)([ab])?(?=$|[-_ .])", re.IGNORECASE)


@dataclass(frozen=True)
class Capture:
    """One way a Format names a recording: the words that name it, the setup it needs, and what the words themselves
    say about real time (a timelapse is never real time)."""

    kind: str
    pattern: re.Pattern
    setup: str
    needs: str
    real_time: bool | None = None


# In the order they are looked for in a clause; the first that matches names the clause's recording.
CAPTURES = (
    Capture(FOUNDER_ON_CAMERA, re.compile(r"\bfounder[- ]on[- ]camera\b", re.IGNORECASE), CAMERA, "the Founder"),
    Capture("screen recording", SCREEN_RECORDING, DEVICE, "a real device"),
    Capture("timelapse", re.compile(r"\btime-?lapse\b", re.IGNORECASE), CAMERA, "the Founder", False),
    Capture(
        "slow-motion capture",
        re.compile(r"\bslow[- ]motion\b|\bhigh-frame-rate\b", re.IGNORECASE),
        UNSTATED,
        "the Founder",
        False,
    ),
    Capture("device demo", re.compile(r"\bdemo\b", re.IGNORECASE), DEVICE, "a real device"),
    Capture("camera footage", re.compile(r"\bpan\b|\bvideo\b", re.IGNORECASE), CAMERA, "the Founder"),
)
SETUPS = {
    CAMERA: "On camera",
    DEVICE: "Device screen recordings",
    UNSTATED: "Setup not stated",
}


@dataclass(frozen=True)
class Shot:
    """One recording an asset is made of, as its Format states it; why says where a fact comes from."""

    id: str  # d01-s1: the job's first calendar day, then the shot's number
    number: int
    kind: str
    setup: str
    needs: str
    what: str  # the Format's own words for this recording
    real_time: bool | None  # None when neither the Format nor the calendar says
    real_time_why: str
    uncut: bool
    uncut_why: str
    real_device: bool = False

    def as_json(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Hook:
    """The frozen Hook a calendar day opens on, with where the kit freezes it."""

    day: int
    leg: str | None
    text: str
    source: str  # the kit role that holds it: pairs or angles
    line: int


@dataclass(frozen=True)
class Job:
    """The footage one or more calendar days are cut from: the legs of an A/B pair share one job."""

    key: str  # d01
    days: tuple[int, ...]  # the earliest films; each later one reuses its footage
    angle: str
    pair: str | None
    recut: bool
    format: str
    line: int  # the Angle's line in the Angle bank
    length: tuple[int, int] | None
    shots: tuple[Shot, ...]
    hooks: tuple[Hook, ...]

    @property
    def films(self) -> int:
        return self.days[0]

    @property
    def reuses(self) -> tuple[int, ...]:
        return self.days[1:]

    def on_camera(self) -> bool:
        return any(shot.kind == FOUNDER_ON_CAMERA for shot in self.shots)

    def digest(self) -> str:
        """A fingerprint of what this job must film: its days, its Format, its shots, and, when the Founder says
        them on camera, its Hooks. It changes only when the kit changes what must be filmed: where a shot's facts
        were read, and the launcher's words for that, are no part of it."""
        said = [(hook.day, hook.leg, hook.text) for hook in self.hooks] if self.on_camera() else []
        content = {
            "key": self.key,
            "days": list(self.days),
            "angle": self.angle,
            "pair": self.pair,
            "recut": self.recut,
            "format": self.format,
            "length": list(self.length) if self.length else None,
            "shots": [
                [
                    shot.id,
                    shot.number,
                    shot.kind,
                    shot.setup,
                    shot.needs,
                    shot.what,
                    shot.real_time,
                    shot.uncut,
                    shot.real_device,
                ]
                for shot in self.shots
            ],
            "hooks": said,
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Sitting:
    """Shots recorded in one go, because their shot lists state the same setup."""

    number: int
    setup: str
    shots: tuple[tuple[Job, Shot], ...]

    @property
    def label(self) -> str:
        return SETUPS[self.setup]

    def days(self) -> list[int]:
        return sorted({day for job, _ in self.shots for day in job.days})


@dataclass
class Requirements:
    """Everything a window must film, and each day the plan leaves out with the reason."""

    jobs: list[Job] = field(default_factory=list)
    unplanned: list[tuple[int, str]] = field(default_factory=list)

    def job_for(self, day: int) -> Job | None:
        return next((job for job in self.jobs if day in job.days), None)

    def shots(self) -> list[tuple[Job, Shot]]:
        return [(job, shot) for job in self.jobs for shot in job.shots]

    def on_camera_days(self) -> list[int]:
        """The days whose own footage puts the Founder on camera; a later leg reuses footage and films nothing."""
        return sorted(job.films for job in self.jobs if job.on_camera())

    def reuse_days(self) -> list[int]:
        return sorted(day for job in self.jobs for day in job.reuses)

    def digests(self) -> dict[str, str]:
        return {job.key: job.digest() for job in self.jobs}

    def fingerprint(self) -> str:
        """What must be filmed, as one fingerprint: every job, every day left out, and the sittings."""
        content = {
            "jobs": self.digests(),
            "unplanned": [day for day, _ in self.unplanned],
            "sittings": [[sitting.setup, [shot.id for _, shot in sitting.shots]] for sitting in sittings(self)],
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScreenRule:
    """What the calendar's own checklist for every asset says of every screen recording, with its line."""

    line: int
    real_device: bool
    real_time: bool
    cuts_declared_only: bool


def screen_rule(checks: Sequence[AssetCheck]) -> ScreenRule | None:
    for check in checks:
        if SCREEN_RECORDING.search(check.text):
            return ScreenRule(
                check.line,
                bool(REAL_DEVICE.search(check.text)),
                bool(REAL_TIME.search(check.text)),
                bool(CUTS_DECLARED.search(check.text)),
            )
    return None


def capture_of(clause: str) -> Capture | None:
    return next((capture for capture in CAPTURES if capture.pattern.search(clause)), None)


def clauses(text: str) -> list[str]:
    """A Format's recordings, in order and in its own words: a new one starts after "then" when what follows names
    a recording, or after "with" when both sides name one; anything else continues the recording before it."""
    pieces = JOIN.split(text)
    parts = [pieces[0]]
    for joint, piece in zip(pieces[1::2], pieces[2::2]):
        sequence = "then" in joint.casefold()
        if capture_of(piece) and (sequence or capture_of(parts[-1])):
            parts.append(piece)
        else:
            parts[-1] += joint + piece
    return [part.strip(" ,;") for part in parts if part.strip(" ,;")]


def shot_list(
    key: str, text: str, rule: ScreenRule | None = None, calendar: str = "the calendar"
) -> tuple[tuple[int, int] | None, tuple[Shot, ...]]:
    """An asset's length and its shots, read from its Angle's Format; no shot when the Format names no recording."""
    length = None
    match = LENGTH.match(text)
    if match:
        length = (int(match.group(1)), int(match.group(2) or match.group(1)))
        text = text[match.end() :]
    parts = clauses(text)
    every_take = any(EVERY_TAKE.search(part) for part in parts)
    found: list[Shot] = []
    for part in parts:
        capture = capture_of(part)
        if capture is None:
            continue
        number = len(found) + 1
        screen = capture.setup == DEVICE and rule is not None
        where = f"{calendar} line {rule.line}" if screen else ""
        if capture.real_time is False:
            real_time, real_time_why = False, f"the Format: {capture.kind}"
        elif REAL_TIME.search(part):
            real_time, real_time_why = True, "the Format: real time"
        elif screen and rule.real_time:
            real_time, real_time_why = True, f"{where}: screen recordings are real time"
        else:
            real_time, real_time_why = None, ""
        if NO_CUTS.search(part) or every_take:
            uncut, uncut_why = True, "the Format: no cuts"
        elif screen and rule.cuts_declared_only:
            uncut = True
            uncut_why = f"{where}: a screen recording is cut only where its shot list says, and it names no cut"
        else:
            uncut, uncut_why = False, ""
        found.append(
            Shot(
                f"{key}-s{number}",
                number,
                capture.kind,
                capture.setup,
                capture.needs,
                part,
                real_time,
                real_time_why,
                uncut,
                uncut_why,
                bool(screen and rule.real_device),
            )
        )
    return length, tuple(found)


def job_key(day: int) -> str:
    return f"d{day:02d}"


def requirements(kit: Kit, calendar: str = "the calendar") -> Requirements:
    """Every filming job of the window the calendar holds, earliest day first, and the days it cannot plan."""
    found = Requirements()
    rule = screen_rule(kit.asset_checks)
    groups: dict[object, list[KitDay]] = {}
    for number in sorted(kit.days):
        day = kit.days[number]
        if day.angle is None:
            found.unplanned.append((number, f"the calendar decides its Angle later ({day.cell})"))
            continue
        groups.setdefault(day.pair or ("day", number), []).append(day)
    for days in sorted(groups.values(), key=lambda days: days[0].day):
        first = days[0]
        angle = kit.angles.get(first.angle or "")
        if angle is None:
            found.unplanned += [(day.day, f"Angle {day.angle} is not in the Angle bank") for day in days]
            continue
        if any(day.angle != first.angle for day in days):
            found.unplanned += [(day.day, f"the legs of {first.pair} do not share one Angle") for day in days]
            continue
        key = job_key(first.day)
        length, shots = shot_list(key, angle.format, rule, calendar)
        if not shots:
            why = f"Angle {angle.id}'s Format names no recording the plan can read ({angle.format!r})"
            found.unplanned += [(day.day, why) for day in days]
            continue
        hooks = []
        for day in days:
            hook, _ = frozen_hook(day, kit)
            if hook is not None:
                hooks.append(Hook(day.day, day.leg, hook.text, hook.source, hook.line))
        found.jobs.append(
            Job(
                key,
                tuple(day.day for day in days),
                angle.id,
                first.pair,
                bool(first.pair and recut_hooks(first, kit)),
                angle.format,
                angle.line,
                length,
                shots,
                tuple(hooks),
            )
        )
    found.unplanned.sort()
    return found


def sittings(found: Requirements) -> list[Sitting]:
    """The fewest sittings the shot lists allow: two shots share a sitting unless their shot lists state different
    setups, so there is one sitting per setup, in the order of the first day each serves."""
    groups: dict[str, list[tuple[Job, Shot]]] = {}
    for job, shot in found.shots():
        groups.setdefault(shot.setup, []).append((job, shot))
    return [Sitting(number, setup, tuple(shots)) for number, (setup, shots) in enumerate(groups.items(), start=1)]


def file_shot(name: str) -> tuple[str, str | None] | None:
    """The shot a footage file's name starts with, lowercased, and the leg whose opening it is, if it names one."""
    match = FILE_SHOT.match(name.rsplit(".", 1)[0])
    if match is None:
        return None
    return match.group(1).lower(), (match.group(2).upper() if match.group(2) else None)
