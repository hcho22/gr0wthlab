"""An edit record (US-ME09): the file the agent writes to say which stretches of the Founder's footage make up one
calendar day's video, and every deterministic check it must pass before anything is rendered from it.

The agent cannot watch video, so an edit record holds only what it can know: for each piece of the timeline, the shot
of the day's shot list it shows, the footage file it comes from, and where in that file it starts and ends. The
words drawn over the video are not in it; they come from the day's post Draft, which has its own checks.

The checks follow the shot list the launcher read from the kit: every source is a file of the footage place, named
for the shot it is used as; a shot that may not be cut appears as one unbroken source range, with no other shot
between its pieces; nothing runs at another speed unless its shot list says it is not real time; every shot of the
list has footage; the length is the one the Format gives and the one the Draft's beats add up to; and a leg of an A/B
pair uses takes both legs can use after its opening, while a leg whose Hook the Founder says on camera opens on a take
of its own. A record that fails any of them renders nothing: no footage is ever substituted for a shot.

Whether the two legs of a pair show the same footage is not a check of one record: it is judged on the two finished
videos, from what each one's own record in the ledger holds of the footage it was cut from (unlike).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import groupby

from . import shots as shot_lists
from .drafts import PostDraft, none, norm
from .lint import Finding
from .video import Canvas, Facts, Overlay

EDIT_FORMAT = 1
TOP_KEYS = ("edit", "product", "window", "day", "segments")
SEGMENT_KEYS = ("shot", "source", "in", "out")
OPTIONAL_KEYS = ("speed",)
# Times in an edit record are the agent's own decimals, so they are compared to the millisecond.
EPSILON = 0.001
# How far an edit's length may sit from the length its Draft's beats give: within one frame of a 30 fps asset.
LENGTH_TOLERANCE = 0.04
MAX_SPEED = 100.0
MAX_SEGMENTS = 60
UNDRAWABLE = "{}\\"


@dataclass(frozen=True)
class Segment:
    """One piece of the timeline: a source range of one footage file, shown as one shot of the shot list."""

    shot: str
    source: str  # the file's name inside the footage place, such as window-1/d01-s1.mov
    start: float
    end: float
    speed: float = 1.0

    @property
    def length(self) -> float:
        return (self.end - self.start) / self.speed

    def as_json(self) -> dict[str, object]:
        return {
            "shot": self.shot,
            "source": self.source,
            "in": self.start,
            "out": self.end,
            "speed": self.speed,
        }


@dataclass
class Edit:
    path: str
    sha256: str  # of its content once it follows the format, so the same cut saved in other bytes is the same record
    product: str = ""
    window: int | None = None
    day: int | None = None
    segments: list[Segment] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def length(self) -> float:
        return sum(segment.length for segment in self.segments)

    def as_json(self) -> dict[str, object]:
        return {
            "edit": EDIT_FORMAT,
            "product": self.product,
            "window": self.window,
            "day": self.day,
            "segments": [segment.as_json() for segment in self.segments],
        }


@dataclass(frozen=True)
class Clip:
    """One footage file as the launcher's inventory holds it: its name inside the footage place, the shot and leg
    its name gives, and what was measured of it."""

    name: str
    bytes: int
    sha256: str
    shot: str | None
    leg: str | None
    facts: Facts | None
    problem: str = ""

    def as_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "shot": self.shot,
            "leg": self.leg,
            "facts": self.facts.as_json() if self.facts else None,
            "problem": self.problem,
        }

    @classmethod
    def from_json(cls, data: Mapping) -> Clip:
        facts = Facts.from_json(data["facts"]) if data.get("facts") else None
        return cls(
            str(data["name"]),
            int(data["bytes"]),
            str(data["sha256"]),
            data.get("shot"),
            data.get("leg"),
            facts,
            str(data.get("problem") or ""),
        )


@dataclass(frozen=True)
class DaySpec:
    """What one calendar day's edit must follow: its filming job's shots and length, and, for an A/B pair leg, its
    other leg and whether the kit marks the pair's opening as re-cut."""

    product: str
    window: int
    day: int
    job: str
    leg: str | None
    pair: str | None
    recut: bool
    other: int | None
    length: tuple[int, int] | None
    shots: tuple[shot_lists.Shot, ...]
    hooks: tuple[str, ...]  # both frozen Hooks of a re-cut pair, which mark the beats of its opening

    def shot(self, identifier: str) -> shot_lists.Shot | None:
        return next((shot for shot in self.shots if shot.id == identifier), None)

    def as_json(self) -> dict[str, object]:
        return dict(
            self.__dict__,
            length=list(self.length) if self.length else None,
            shots=[shot.as_json() for shot in self.shots],
            hooks=list(self.hooks),
        )

    @classmethod
    def from_json(cls, data: Mapping) -> DaySpec:
        return cls(
            str(data["product"]),
            int(data["window"]),
            int(data["day"]),
            str(data["job"]),
            data.get("leg"),
            data.get("pair"),
            data["recut"] is True,
            data.get("other"),
            tuple(data["length"]) if data.get("length") else None,
            tuple(shot_lists.Shot(**shot) for shot in data["shots"]),
            tuple(data.get("hooks") or ()),
        )


# Reading an edit record.


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def parse(text: str, path: str) -> Edit:
    """An edit record, or one whose problems say what does not follow the format."""
    edit = Edit(path, hashlib.sha256(text.encode("utf-8")).hexdigest())
    problems = edit.problems
    try:
        data = json.loads(text)
    except ValueError as error:
        problems.append(f"it is not JSON ({error})")
        return edit
    if not isinstance(data, dict) or sorted(data) != sorted(TOP_KEYS):
        problems.append(f"it holds exactly the keys {', '.join(TOP_KEYS)}")
        return edit
    if data["edit"] != EDIT_FORMAT:
        problems.append(f"edit must be {EDIT_FORMAT}, the format this launcher reads")
    edit.product = data["product"] if isinstance(data["product"], str) else ""
    for key in ("window", "day"):
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            problems.append(f"{key} must be a whole number from 1")
        else:
            setattr(edit, key, value)
    segments = data["segments"]
    if not isinstance(segments, list) or not segments:
        problems.append("segments must list at least one piece of the timeline")
        return edit
    if len(segments) > MAX_SEGMENTS:
        problems.append(f"segments holds {len(segments)} pieces; an edit has at most {MAX_SEGMENTS}")
        return edit
    for index, entry in enumerate(segments, start=1):
        where = f"segment {index}"
        if not isinstance(entry, dict) or not set(SEGMENT_KEYS) <= set(entry) <= set(SEGMENT_KEYS + OPTIONAL_KEYS):
            problems.append(f"{where} holds the keys {', '.join(SEGMENT_KEYS)}, and may add {', '.join(OPTIONAL_KEYS)}")
            continue
        start, end, speed = number(entry["in"]), number(entry["out"]), number(entry.get("speed", 1))
        if not isinstance(entry["shot"], str) or not isinstance(entry["source"], str):
            problems.append(f"{where}: shot and source are text")
        elif start is None or end is None or speed is None:
            problems.append(f"{where}: in, out, and speed are numbers, in seconds")
        elif not 0 < speed <= MAX_SPEED:
            problems.append(f"{where}: speed is above 0 and at most {MAX_SPEED:g}")
        else:
            edit.segments.append(Segment(entry["shot"], entry["source"], start, end, speed))
    if not problems:
        edit.sha256 = hashlib.sha256(json.dumps(edit.as_json(), sort_keys=True).encode("utf-8")).hexdigest()
    return edit


# Checking an edit record.


def inside(source: str) -> bool:
    """Whether a source is written as a plain name inside the footage place: relative, with no step out of it."""
    parts = source.split("/")
    return (
        bool(source)
        and not source.startswith(("/", "~"))
        and "\\" not in source
        and "\0" not in source
        and all(part not in ("", ".", "..") for part in parts)
    )


def pieces(segments: Sequence[Segment], opening: Sequence[tuple[float, float]] = ()) -> list[tuple]:
    """The source ranges a timeline shows outside its opening, in order, with neighbours that run on from each other
    joined: (source, start, end, speed), each time to the millisecond."""
    found: list[list] = []
    clock = 0.0
    for segment in segments:
        begins, ends = clock, clock + segment.length
        clock = ends
        kept = [(begins, ends)]
        for start, end in opening:
            kept = [
                part
                for low, high in kept
                for part in ((low, min(high, start)), (max(low, end), high))
                if part[1] - part[0] > EPSILON
            ]
        for low, high in kept:
            start = segment.start + (low - begins) * segment.speed
            end = segment.start + (high - begins) * segment.speed
            last = found[-1] if found else None
            same = last is not None and (last[0], last[3]) == (segment.source, segment.speed)
            if same and abs(last[2] - start) <= EPSILON:
                last[2] = end
            else:
                found.append([segment.source, start, end, segment.speed])
    return [(source, round(start, 3), round(end, 3), speed) for source, start, end, speed in found]


def under(segments: Sequence[Segment], opening: Sequence[tuple[float, float]]) -> list[Segment]:
    """The pieces of a timeline that play, in whole or in part, under its opening."""
    found = []
    clock = 0.0
    for segment in segments:
        begins, clock = clock, clock + segment.length
        if any(min(clock, end) - max(begins, start) > EPSILON for start, end in opening):
            found.append(segment)
    return found


def own_opening(shots: Sequence[shot_lists.Shot], leg: str | None, recut: bool) -> shot_lists.Shot | None:
    """The shot a pair leg must open on a take of its own, or None: the first shot of a re-cut pair when the Founder
    is on camera in it, since each leg's Hook is then said to the camera, not only drawn over footage both share."""
    first = shots[0] if shots else None
    if recut and leg and first is not None and first.kind == shot_lists.FOUNDER_ON_CAMERA:
        return first
    return None


def own_take(shot: str, leg: str) -> str:
    """What a leg's own take of a shot is named for: the shot, then the leg's letter, as in d02-s1b."""
    return f"{shot}{leg.lower()}"


def opening_windows(draft: PostDraft, hooks: Collection[str]) -> list[tuple[float, float]]:
    """The stretches of a re-cut leg's video that are its opening: the hook beat, and any later beat that shows or
    says one of the pair's Hooks, as the post-Draft checks read them. hooks is empty for any other pair, whose legs
    share every frame of footage, so nothing is opening."""
    folded = [norm(hook).casefold() for hook in hooks]
    if not folded:
        return []
    windows = []
    for index, beat in enumerate(draft.beats):
        shows = any(hook in norm(text).casefold() for hook in folded for text in (beat.spoken, beat.on_screen))
        if index == 0 or shows:
            windows.append((beat.start, beat.end))
    return windows


def overlays(draft: PostDraft) -> list[Overlay]:
    """The text drawn over a day's video, straight from its post Draft: each beat's on-screen text for the beat's
    time, and its spoken line as a caption unless the on-screen text already says the same words."""
    found = []
    for beat in draft.beats:
        if not none(beat.on_screen):
            found.append(Overlay(beat.start, beat.end, beat.on_screen))
        if not none(beat.spoken) and norm(beat.spoken).casefold() != norm(beat.on_screen).casefold():
            found.append(Overlay(beat.start, beat.end, beat.spoken, caption=True))
    return found


def check(
    edit: Edit,
    spec: DaySpec,
    clips: Mapping[str, Clip],
    draft: PostDraft | None,
    canvas: Canvas,
) -> list[Finding]:
    """Every deterministic check of one day's edit record against its shot list, the footage place's inventory, and
    its post Draft; nothing is rendered unless the list comes back empty."""
    found: list[Finding] = []

    def block(rule: str, detail: str, where: str = "") -> None:
        found.append(Finding(rule, where, detail))

    if edit.problems:
        for problem in edit.problems:
            block("edit-format", problem)
        return found
    if (edit.product, edit.window, edit.day) != (spec.product, spec.window, spec.day):
        block("edit-day", f"this is the edit record of {spec.product} window {spec.window} day {spec.day}")
    for index, segment in enumerate(edit.segments, start=1):
        where = f"segment {index}"
        shot = spec.shot(segment.shot)
        if shot is None:
            listed = ", ".join(shot.id for shot in spec.shots)
            block("shot-list", f"{segment.shot!r} is not a shot of day {spec.day}'s shot list ({listed})", where)
        if not inside(segment.source):
            block("footage-place", f"{segment.source!r} names a source outside the footage place", where)
            continue
        clip = clips.get(segment.source)
        if clip is None:
            block("footage-place", f"the footage place holds no file {segment.source!r}", where)
            continue
        if clip.problem or clip.facts is None:
            block("footage", f"`{clip.name}` cannot be used: {clip.problem or 'it was not measured'}", where)
            continue
        if shot is not None:
            if clip.shot != shot.id:
                whose = f"footage of shot {clip.shot}" if clip.shot else "named for no shot"
                block("shot-list", f"`{clip.name}` is {whose}, so it cannot be used as {shot.id}", where)
            if clip.leg and spec.leg and clip.leg != spec.leg:
                block(
                    "shot-list", f"`{clip.name}` is leg {clip.leg}'s take, and day {spec.day} is leg {spec.leg}", where
                )
            if segment.speed != 1 and shot.real_time is not False:
                why = (
                    f"its shot list says real time ({shot.real_time_why})"
                    if shot.real_time
                    else "its shot list does not say it may run at another speed"
                )
                block("real-time", f"{shot.id} plays at {segment.speed:g}x, and {why}", where)
        if segment.start < 0 or segment.end - segment.start < 1 / canvas.fps - EPSILON:
            block("source-range", "in must be 0 or later, and out at least one frame after it", where)
        elif segment.end > clip.facts.duration + EPSILON:
            block(
                "source-range",
                f"out is {segment.end:g}s, past the end of `{clip.name}`, which measures {clip.facts.duration:.2f}s",
                where,
            )
    runs = [(name, list(run)) for name, run in groupby(edit.segments, key=lambda segment: segment.shot)]
    for shot in spec.shots:
        ranges = [piece for name, run in runs if name == shot.id for piece in pieces(run)]
        if not ranges:
            block("missing-shot", f"shot {shot.id} ({shot.what}) has no footage in this edit, so there is no asset")
        if shot.uncut and len(ranges) > 1:
            block(
                "no-cut",
                f"shot {shot.id} may not be cut ({shot.uncut_why}), and this edit shows it as {len(ranges)} source"
                " ranges, not one unbroken range",
            )
    if any(finding.rule in ("source-range", "edit-format") for finding in found):
        return found
    length = edit.length
    if spec.length and not spec.length[0] - LENGTH_TOLERANCE <= length <= spec.length[1] + LENGTH_TOLERANCE:
        low, high = spec.length
        asked = f"{low}s" if low == high else f"{low} to {high}s"
        block("length", f"the edit runs {length:.2f}s, and the Format gives {asked}")
    if draft is not None and draft.beats:
        end = draft.beats[-1].end
        if abs(length - end) > LENGTH_TOLERANCE:
            block(
                "length",
                f"the edit runs {length:.2f}s, and the beats of `{draft.path}` end at {end:g}s; the two must agree,"
                " since each beat's text is drawn for the beat's time",
            )
        for overlay in overlays(draft):
            kind = "caption" if overlay.caption else "on-screen text"
            if any(character in overlay.text for character in UNDRAWABLE):
                block(
                    "overlay-text",
                    f"the {kind} at {overlay.start:g}s holds a brace or a backslash, which cannot be drawn",
                )
            elif len(overlay.text) > canvas.max_chars:
                block(
                    "overlay-text",
                    f"the {kind} at {overlay.start:g}s is {len(overlay.text)} characters, more than the"
                    f" {canvas.max_chars} that fit the safe zone",
                )
        if spec.other is not None:
            where = "after the opening" if spec.recut else "from the first frame"
            shared = {source for source, *_ in pieces(edit.segments, opening_windows(draft, spec.hooks))}
            for clip in (clips[source] for source in sorted(shared) if source in clips):
                if clip.leg == spec.leg:
                    block(
                        "pair-legs",
                        f"`{clip.name}` is leg {clip.leg}'s own take, and {where} the legs of {spec.pair} share their"
                        " footage; use a take named without a leg letter there",
                    )
        first = own_opening(spec.shots, spec.leg, spec.recut)
        if first is not None:
            opened = [
                clips[segment.source]
                for segment in under(edit.segments, opening_windows(draft, spec.hooks))
                if segment.shot == first.id and segment.source in clips
            ]
            if not opened or any(clip.leg != spec.leg for clip in opened):
                others = sorted({f"`{clip.name}`" for clip in opened if clip.leg != spec.leg})
                block(
                    "pair-legs",
                    f"the Founder is on camera in shot {first.id}, where each leg of {spec.pair} opens on its own"
                    f" Hook, so under its opening leg {spec.leg} shows that shot only from its own take, a file named"
                    f" `{own_take(first.id, spec.leg)}`; this edit shows {', '.join(others) or 'no take of it'} there",
                )
    return found


def footage(video: Mapping) -> list[tuple]:
    """What a finished video shows, cut by cut, read from the video's own record: the file each cut was made from,
    known by the fingerprint the record holds for it and never by its name, with the range and the speed."""
    return [(cut["sha256"], cut["in"], cut["out"], cut["speed"]) for cut in video["cuts"]]


def outside(video: Mapping) -> list[tuple]:
    """The source ranges a finished video shows outside its opening, each of a file known by its fingerprint."""
    segments = [Segment("", *cut) for cut in footage(video)]
    return pieces(segments, [tuple(window) for window in video["opening"]])


def unlike(one: Mapping, two: Mapping) -> str:
    """How the videos of the two legs of an A/B pair differ outside each one's opening, or "" when both show the same
    source ranges in the same order there; judged from the two videos' own records alone. In a pair the kit does not
    mark as a re-cut neither video has an opening: the legs share every source range, and only the Hook drawn over
    them differs.

    A file is the same footage only when it is the same file: one renamed is still the footage it was, and another
    put in its place under its name is not. File names are for the wording alone."""
    files = outside(one), outside(two)
    if files[0] == files[1]:
        return ""
    told = []
    for video, ranges in zip((one, two), files):
        names = {cut["sha256"]: cut["source"] for cut in video["cuts"]}
        told.append([(names[file], *shown) for file, *shown in ranges])
    ours, theirs = told
    if ours != theirs:
        return f"day {one['day']}'s shows {describe(ours)}, and day {two['day']}'s shows {describe(theirs)}"
    replaced = sorted({f"`{name}`" for (name, *_), mine, other in zip(ours, *files) if mine[0] != other[0]})
    many = len(replaced) > 1
    return (
        f"both show {describe(ours)}, but {' and '.join(replaced)} {'are' if many else 'is'} no longer the"
        f" file{'s' if many else ''} day {two['day']}'s video was cut from"
    )


def describe(ranges: Sequence[tuple]) -> str:
    """Source ranges in a few words, for a finding."""
    if not ranges:
        return "nothing"
    return ", ".join(
        f"`{source}` {start:g}-{end:g}s" + (f" at {speed:g}x" if speed != 1 else "")
        for source, start, end, speed in ranges[:4]
    ) + (f" and {len(ranges) - 4} more" if len(ranges) > 4 else "")
