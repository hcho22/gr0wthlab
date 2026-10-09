"""The launcher's own reads and writes in workspace/, confined to the six writable areas.

The launcher runs outside the sandbox, so this module is what keeps its writes inside the areas: every path is
checked against them, and a file the agent wrote is read only if it is a plain file with one link, so a symbolic or
hard link the agent planted can never carry content from outside the areas into a record.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator, Mapping
from pathlib import Path

from .boundary import Boundary, ConfigError, is_within


class UnsafeFile(Exception):
    """A path in an area that is not a plain, singly linked file."""


class Areas:
    def __init__(self, boundary: Boundary):
        self.workspace = boundary.repo_root / "workspace"
        self.paths = dict(boundary.areas)

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
        """Write atomically: a reader such as Mandu never sees half a file."""
        path = self.check(path)
        self.check_parents(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            path.unlink()
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temporary.write_text(text, encoding="utf-8")
        os.replace(str(temporary), str(path))

    def write_json(self, path: Path, data: Mapping) -> None:
        self.write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def write_bytes(self, path: Path, data: bytes) -> None:
        path = self.check(path)
        self.check_parents(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            path.unlink()
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temporary.write_bytes(data)
        os.replace(str(temporary), str(path))

    def check_parents(self, path: Path) -> None:
        """Every folder from the path's parent up to and including its area is a real folder or not there yet, so a
        write cannot leave the area through a link."""
        for parent in path.parents:
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ConfigError(f"refusing to write {path}: {parent} is not a real folder")
            if parent in self.paths.values():
                return

    def remove(self, path: Path) -> None:
        """Remove anything but a real directory: a file, a link, or a special file such as a named pipe."""
        path = self.check(path, area_itself=True)
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            path.unlink()

    def real_folder(self, path: Path) -> bool:
        """Whether a path, and every folder above it up to and including its area, is a real folder."""
        for folder in (path, *path.parents):
            if folder.is_symlink() or not folder.is_dir():
                return False
            if folder in self.paths.values():
                return True
        return False

    def make_accessible(self, folder: Path) -> None:
        """Give the owner back read, write, and search on a real folder in the areas, which the agent may have taken."""
        mode = os.lstat(str(self.check(folder, area_itself=True))).st_mode
        if stat.S_ISDIR(mode) and mode & 0o700 != 0o700:
            os.chmod(str(folder), stat.S_IMODE(mode) | 0o700)

    def files(self, directory: Path) -> Iterator[Path]:
        """Every non-directory entry under a directory inside an area, without following links; every folder on the
        way is made accessible first, so nothing the agent made unreadable stays hidden."""
        directory = self.check(directory, area_itself=True)
        if not self.real_folder(directory):
            return
        self.make_accessible(directory)
        for root, subdirs, names in os.walk(str(directory)):
            for name in list(subdirs):
                if Path(root, name).is_symlink():
                    names.append(name)
                    subdirs.remove(name)
                else:
                    self.make_accessible(Path(root, name))
            for name in sorted(names):
                yield Path(root, name)

    def remove_empty_folders(self, directory: Path) -> list[Path]:
        """Remove every empty real folder below a directory in the areas, deepest first, and return them."""
        removed: list[Path] = []
        if not self.real_folder(self.check(directory, area_itself=True)):
            return removed
        for root, subdirs, _ in os.walk(str(directory), topdown=False):
            for name in subdirs:
                folder = Path(root, name)
                if not folder.is_symlink() and folder.is_dir() and not any(folder.iterdir()):
                    self.check(folder).rmdir()
                    removed.append(folder)
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
