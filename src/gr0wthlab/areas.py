"""The launcher's own reads and writes in workspace/, confined to the six writable areas.

The launcher runs outside the sandbox, so this module is what keeps its writes inside the areas: every path is
checked against them, and a file the agent wrote is read only if it is a plain file with one link, so a symbolic or
hard link the agent planted can never carry content from outside the areas into a record.
Before it writes or removes anything, the launcher takes back the owner's control of what it touches, so nothing the
agent set on an entry (a flag, an ACL, or a mode) can block it; a removal that still fails is noted, never fatal.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

from .boundary import Boundary, ConfigError, is_within


class UnsafeFile(Exception):
    """A path in an area that is not a plain, singly linked file."""


class Areas:
    def __init__(self, boundary: Boundary):
        self.workspace = boundary.repo_root / "workspace"
        self.paths = dict(boundary.areas)
        self.problems: list[str] = []

    def path(self, key: str, *parts: str) -> Path:
        return self.check(self.paths[key].joinpath(*parts))

    def check(self, path: Path, area_itself: bool = False) -> Path:
        """A path inside one of the areas, compared without following links below the area itself.

        An area's own directory passes only when area_itself is set: to list it, or to remove what stands in its place.
        """
        absolute = Path(os.path.abspath(str(path)))
        if not any(is_within(absolute, area) and (area_itself or absolute != area) for area in self.paths.values()):
            raise ConfigError(f"refusing to touch {absolute}: it is outside the writable areas")
        return absolute

    def relative(self, path: Path) -> str:
        """A path relative to workspace/, the form records use to point at each other."""
        return str(Path(os.path.abspath(str(path))).relative_to(self.workspace))

    def write_text(self, path: Path, text: str) -> None:
        self.write_bytes(path, text.encode("utf-8"))

    def write_json(self, path: Path, data: Mapping) -> None:
        self.write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def write_bytes(self, path: Path, data: bytes) -> None:
        """Write atomically, so a reader such as Mandu never sees half a file, over whatever stands at the path."""
        path = self.check(path)
        self.check_parents(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.is_dir():
            self.remove(path)
        else:
            self.reclaim(path)
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temporary.write_bytes(data)
        os.replace(str(temporary), str(path))

    def check_parents(self, path: Path) -> None:
        """Every folder from its area down to the path's parent is a real folder or not there yet, so a write cannot
        leave the area through a link; each one there is reclaimed, outermost first."""
        chain = [parent for parent in path.parents if any(is_within(parent, area) for area in self.paths.values())]
        for parent in reversed(chain):
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ConfigError(f"refusing to write {path}: {parent} is not a real folder")
            if parent.exists():
                self.reclaim(parent)

    def reclaim(self, path: Path) -> None:
        """Give the owner back full control of one entry in the areas, whatever the agent set on it: no BSD flags, no
        ACL (stripped with chmod -N on macOS, as the standard library has none), and owner read, write, and search on a
        folder. It does its best; an operation that still fails afterwards says why."""
        path = self.check(path, area_itself=True)
        try:
            info = os.lstat(str(path))
            if getattr(info, "st_flags", 0):
                os.chflags(str(path), 0, follow_symlinks=False)
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                return
            if sys.platform == "darwin":
                subprocess.run(["/bin/chmod", "-N", str(path)], capture_output=True, check=False)
            if stat.S_ISDIR(info.st_mode) and info.st_mode & 0o700 != 0o700:
                os.chmod(str(path), stat.S_IMODE(info.st_mode) | 0o700)
        except OSError:
            return

    def remove(self, path: Path) -> bool:
        """Remove whatever stands at a path in the areas, a folder with everything in it, reclaiming each entry first;
        a removal that still fails is noted in problems instead of stopping the run."""
        path = self.check(path, area_itself=True)
        try:
            self.check_parents(path)
            self.remove_entry(path)
        except (OSError, ConfigError) as error:
            self.problems.append(f"could not remove `{self.relative(path)}` ({error})")
            return False
        return True

    def remove_entry(self, path: Path) -> None:
        self.reclaim(path)
        if path.is_dir() and not path.is_symlink():
            for child in path.iterdir():
                self.remove_entry(child)
            path.rmdir()
        elif os.path.lexists(str(path)):
            path.unlink()

    def real_folder(self, path: Path) -> bool:
        """Whether a path, and every folder above it up to and including its area, is a real folder."""
        try:
            for folder in (path, *path.parents):
                if folder.is_symlink() or not folder.is_dir():
                    return False
                if folder in self.paths.values():
                    return True
        except OSError:
            return False
        return False

    def files(self, directory: Path) -> Iterator[Path]:
        """Every non-directory entry under a directory inside an area, without following links; every folder on the
        way is made accessible first, so nothing the agent made unreadable stays hidden."""
        directory = self.check(directory, area_itself=True)
        if not self.real_folder(directory):
            return
        self.reclaim(directory)
        for root, subdirs, names in os.walk(str(directory)):
            for name in list(subdirs):
                if Path(root, name).is_symlink():
                    names.append(name)
                    subdirs.remove(name)
                else:
                    self.reclaim(Path(root, name))
            for name in sorted(names):
                yield Path(root, name)

    def remove_empty_folders(self, directory: Path) -> list[Path]:
        """Remove every empty real folder below a directory in the areas, deepest first, and return them; a folder
        that cannot be removed is noted in problems instead of stopping the run."""
        removed: list[Path] = []
        if not self.real_folder(self.check(directory, area_itself=True)):
            return removed
        for root, subdirs, _ in os.walk(str(directory), topdown=False):
            for name in subdirs:
                folder = self.check(Path(root, name))
                try:
                    self.reclaim(folder)
                    if not folder.is_symlink() and folder.is_dir() and not any(folder.iterdir()):
                        folder.rmdir()
                        removed.append(folder)
                except OSError as error:
                    self.problems.append(f"could not remove `{self.relative(folder)}` ({error})")
        return removed


def read_plain(path: Path) -> bytes:
    """The bytes of a plain file with exactly one link; anything else raises UnsafeFile."""
    try:
        descriptor = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise UnsafeFile(f"cannot open without following links: {error.strerror}") from error
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise UnsafeFile("not a plain file")
        if info.st_nlink != 1:
            raise UnsafeFile(f"has {info.st_nlink} hard links")
        return handle.read()
