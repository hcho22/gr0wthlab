"""The footage place (US-ME09): the folder outside this repository where the Founder drops raw footage.

Raw footage is private and irreplaceable, so everything here only reads: a file is opened read-only, without
following a link, to fingerprint it, and handed to ffprobe to be measured. Nothing in gr0wthlab writes, renames, or
deletes anything in the footage place, and the sandboxed agent never opens it: the launcher tells the agent each
file's name and measured facts instead, since an agent cannot watch video.

The place holds one folder per 14-day window, window-<n>/, with each file named for the shot of the filming plan it
is footage of. A link, a folder, and a file that is not a video are named and left alone.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import shots, video
from .boundary import canonical, is_within
from .edits import Clip

VIDEO_SUFFIXES = (".mov", ".mp4", ".m4v")
READ = "read"
NOT_SET = "not set"
EMPTY = "nothing there yet"
FAILED = "failed"
CHUNK = 1 << 20


@dataclass
class Inventory:
    """What the footage place held for one window when the run looked, by each file's name inside the place."""

    place: Path | None
    folder: str  # window-1
    status: str
    detail: str = ""
    clips: dict[str, Clip] = field(default_factory=dict)
    ignored: list[tuple[str, str]] = field(default_factory=list)

    def path(self, clip: Clip) -> Path:
        """Where a clip's file is; only ever a name the inventory itself listed."""
        if self.place is None or clip.name not in self.clips:
            raise KeyError(clip.name)
        return self.place / clip.name

    def for_shot(self, shot: str, leg: str | None = None) -> list[Clip]:
        """The clips that are footage of a shot and that a leg may use: a take named for one leg is that leg's."""
        return [
            clip
            for clip in self.clips.values()
            if clip.shot == shot and not clip.problem and (clip.leg is None or leg is None or clip.leg == leg)
        ]

    def unmatched(self) -> list[Clip]:
        return [clip for clip in self.clips.values() if clip.shot is None]


def fingerprint(path: Path) -> tuple[str, int]:
    """A file's SHA-256 and size, read without following a link; anything but a plain file raises OSError."""
    descriptor = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError("not a plain file")
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest(), info.st_size


def read(
    place: Path | None,
    window: int,
    known: Collection[str],
    tooling: video.Tooling,
    env: Mapping[str, str],
) -> Inventory:
    """Every footage file of a window, fingerprinted and, when the tooling can be used, measured.

    known holds the shots of the filming plan; a file is footage of a shot only when its name starts with one.
    """
    folder = f"window-{window}"
    if place is None:
        return Inventory(None, folder, NOT_SET, "the footage place is not set in config/products.json")
    target = place / folder
    try:
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            return Inventory(place, folder, FAILED, f"`{target}` is not a real folder, so nothing in it was read")
        if not target.is_dir():
            return Inventory(place, folder, EMPTY, f"`{target}` does not exist yet")
        if not is_within(canonical(target), canonical(place)):
            return Inventory(place, folder, FAILED, f"`{target}` leads outside the footage place")
        entries = sorted(os.scandir(str(target)), key=lambda entry: entry.name)
    except OSError as error:
        return Inventory(place, folder, FAILED, f"`{target}` could not be read ({error.strerror or error})")
    found = Inventory(place, folder, READ)
    for entry in entries:
        name = f"{folder}/{entry.name}"
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_symlink():
                found.ignored.append((name, "a link, which is never followed"))
            elif entry.is_dir(follow_symlinks=False):
                found.ignored.append((name, f"a folder; footage files sit directly in {folder}/"))
            elif not entry.is_file(follow_symlinks=False):
                found.ignored.append((name, "not a plain file"))
            elif not entry.name.lower().endswith(VIDEO_SUFFIXES):
                found.ignored.append((name, f"not a {', '.join(VIDEO_SUFFIXES)} file"))
            else:
                found.clips[name] = clip(Path(entry.path), name, known, tooling, env)
        except OSError as error:
            found.ignored.append((name, f"could not be read ({error.strerror or error})"))
    found.detail = f"{len(found.clips)} footage file{'' if len(found.clips) == 1 else 's'} in `{target}`"
    return found


def clip(path: Path, name: str, known: Collection[str], tooling: video.Tooling, env: Mapping[str, str]) -> Clip:
    digest, size = fingerprint(path)
    named = shots.file_shot(Path(name).name)
    shot, leg = named if named and named[0] in known else (None, None)
    if named is None:
        problem = "its name starts with no shot, such as d01-s1"
    elif shot is None:
        problem = f"its name starts with {named[0]}, which is not a shot of the filming plan"
    else:
        problem = ""
    facts = None
    if tooling.ok:
        try:
            facts = video.probe(tooling, path, env)
        except video.VideoError as error:
            problem = problem or str(error)
    return Clip(name, size, digest, shot, leg, facts, problem)
