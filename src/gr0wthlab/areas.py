"""The launcher's own files: its reads and removals in workspace/, and its records in ledger/.

The agent writes only in the six workspace areas; the launcher reads from them only what it must, the incoming
Review Queue items, and only a plain file with one link, so a symbolic or hard link the agent planted can never carry
content from outside the areas into a record. The launcher's records live in ledger/, which the run can read and
never write, so nothing the agent does can change them.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Collection, Iterator, Mapping
from pathlib import Path

from .boundary import Boundary, ConfigError, is_within

# How every name starts that the boundary check puts at the top of an area, or has its agent put there.
PROBE_PREFIX = "gr0wthlab-boundary-probe-"


class UnsafeFile(Exception):
    """A path that is not a plain, singly linked file."""


def clear_probe_files(boundary: Boundary, keep: str = "", runs: Collection[str] | None = None) -> list[str]:
    """Remove what a boundary check left at the top of the areas, and return it as paths from the repository.

    A check removes its own files once it has judged a run. One stopped before that, by an interrupt or a kill, leaves
    them, and nothing else would take them away: a later run's agent would find a stale script in its Instructions
    area, and the production clone would commit it with the run's records. So every run clears them before its agent
    starts, and a check before it looks at the checkout and again when it ends, however it ends.
    keep is the identifier of the run in progress, whose own files stay. runs limits the removal to those runs' files,
    which is how a check that is ending takes only its own. A file or a link is removed, never followed, and never a
    folder.
    """
    removed = []
    mine = None if runs is None else tuple(PROBE_PREFIX + run_id for run_id in runs)
    for _, area in boundary.areas:
        try:
            names = sorted(os.listdir(str(area)))
        except OSError:
            continue
        for name in names:
            if not name.startswith(PROBE_PREFIX) or (keep and name.startswith(PROBE_PREFIX + keep)):
                continue
            if mine is not None and not name.startswith(mine):
                continue
            path = area / name
            try:
                if path.is_symlink() or not path.is_dir():
                    path.unlink()
                    removed.append(str(path.relative_to(boundary.repo_root)))
            except OSError:
                continue
    return removed


class Areas:
    """The six workspace areas the agent writes, as the launcher reads them and removes what it has taken in."""

    def __init__(self, boundary: Boundary):
        self.workspace = boundary.repo_root / "workspace"
        self.paths = dict(boundary.areas)
        self.problems: list[str] = []

    def path(self, key: str, *parts: str) -> Path:
        return self.check(self.paths[key].joinpath(*parts))

    def check(self, path: Path, area_itself: bool = False) -> Path:
        """A path inside one of the areas, compared without following links below the area itself; an area's own
        directory passes only when area_itself is set, for listing."""
        absolute = Path(os.path.abspath(str(path)))
        if not any(is_within(absolute, area) and (area_itself or absolute != area) for area in self.paths.values()):
            raise ConfigError(f"refusing to touch {absolute}: it is outside the writable areas")
        return absolute

    def relative(self, path: Path) -> str:
        """A path relative to workspace/."""
        return str(Path(os.path.abspath(str(path))).relative_to(self.workspace))

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

    def ensure_folder(self, folder: Path) -> None:
        """Make a folder inside a real area folder a real folder: a link or file the agent left in its place is noted
        in problems and removed, so nothing behind it is ever read and the folder can be made again."""
        folder = self.check(folder)
        if not self.real_folder(folder.parent):
            return
        try:
            if folder.is_symlink() or (os.path.lexists(str(folder)) and not folder.is_dir()):
                self.problems.append(
                    f"`{self.relative(folder)}` was not a folder, so what stood in its place was removed, not taken in"
                )
                self.remove(folder)
            folder.mkdir(exist_ok=True)
        except OSError as error:
            self.problems.append(f"could not make `{self.relative(folder)}` a folder again ({error})")

    def files(self, directory: Path) -> Iterator[Path]:
        """Every non-directory entry under a real folder inside an area, without following links; a folder that is not
        a real folder, or that cannot be listed, is noted in problems, since nothing in it was read."""
        directory = self.check(directory, area_itself=True)
        if not self.real_folder(directory):
            self.problems.append(f"`{self.relative(directory)}` is not a real folder, so nothing in it was read")
            return

        def unreadable(error: OSError) -> None:
            folder = self.relative(Path(str(error.filename)))
            self.problems.append(f"`{folder}` could not be read ({error.strerror or error}), so nothing in it was read")

        for root, subdirs, names in os.walk(str(directory), onerror=unreadable):
            for name in list(subdirs):
                try:
                    linked = Path(root, name).is_symlink()
                except OSError as error:
                    unreadable(error)
                    subdirs.remove(name)
                    continue
                if linked:
                    names.append(name)
                    subdirs.remove(name)
            for name in sorted(names):
                yield Path(root, name)

    def remove(self, path: Path) -> None:
        """Remove a file, link, or special file the launcher has taken in; a removal that fails is noted in problems
        instead of stopping the run."""
        path = self.check(path)
        try:
            if path.is_symlink() or (os.path.lexists(str(path)) and not path.is_dir()):
                path.unlink()
        except OSError as error:
            self.problems.append(f"could not remove `{self.relative(path)}` ({error})")

    def remove_empty_folders(self, directory: Path) -> None:
        """Remove every empty real folder below a real folder in the areas, deepest first; a folder that cannot be
        removed is noted in problems instead of stopping the run."""
        if not self.real_folder(self.check(directory, area_itself=True)):
            return
        for root, subdirs, _ in os.walk(str(directory), topdown=False):
            for name in subdirs:
                folder = self.check(Path(root, name))
                try:
                    if not folder.is_symlink() and folder.is_dir() and not any(folder.iterdir()):
                        folder.rmdir()
                except OSError as error:
                    self.problems.append(f"could not remove `{self.relative(folder)}` ({error})")


class Store:
    """The launcher's records in ledger/: the Review Queue, the launcher's own Evidence, run reports and briefs, run
    state, and notes for the next report. The run can read them and never write them."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, *parts: str) -> Path:
        path = Path(os.path.abspath(str(self.root.joinpath(*parts))))
        if not is_within(path, self.root) or path == self.root:
            raise ConfigError(f"refusing to touch {path}: it is outside {self.root}")
        return path

    def relative(self, path: Path) -> str:
        """A path relative to ledger/, the form records use to point at each other."""
        return str(Path(os.path.abspath(str(path))).relative_to(self.root))

    def write_text(self, path: Path, text: str) -> None:
        self.write_bytes(path, text.encode("utf-8"))

    def write_json(self, path: Path, data: Mapping) -> None:
        self.write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def write_bytes(self, path: Path, data: bytes) -> None:
        """Write atomically, so a reader such as Mandu never sees half a file, through a temporary with a fresh,
        unpredictable name that is created only if nothing stands there, never through a link."""
        path = self.path(self.relative(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                os.fchmod(handle.fileno(), 0o644)
                handle.write(data)
            os.replace(temporary, str(path))
        except BaseException:
            if os.path.lexists(temporary):
                os.unlink(temporary)
            raise

    def move(self, path: Path, target: Path) -> None:
        """Move one of the records to another place among them."""
        target = self.path(self.relative(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(self.path(self.relative(path))), str(target))


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
