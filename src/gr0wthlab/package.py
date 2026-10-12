"""Snapshot each Product's Go-To-Market Package in Mandu: which files were read, their content fingerprints, when,
and what changed since the previous snapshot.

Mandu is only ever opened for reading, and the snapshot keeps no package content: a record may quote only the text
it uses, so the fingerprint is what lets a run state exactly which files changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .areas import UnsafeFile, read_plain
from .boundary import ConfigError

SNAPSHOT_FORMAT = 1
READ = "read"
CHANGED = "changed"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass(frozen=True)
class Source:
    """One configured package source: a Mandu-relative file, or a directory ending in / that covers its files, or
    only those whose names start with prefix."""

    product: str
    path: str
    needed_by: tuple[str, ...]
    prefix: str = ""

    @property
    def is_directory(self) -> bool:
        return self.path.endswith("/")

    def covers(self, relative: str) -> bool:
        """Whether a Mandu-relative file is one this source reads."""
        if not self.is_directory:
            return relative == self.path
        return relative.startswith(self.path) and Path(relative).name.startswith(self.prefix)


@dataclass
class FileResult:
    path: str
    source: str
    status: str
    sha256: str | None = None
    bytes: int | None = None
    read_at: str | None = None
    previous_sha256: str | None = None
    change: str | None = None
    reason: str | None = None

    def as_json(self) -> dict[str, object]:
        return {key: value for key, value in self.__dict__.items() if value is not None}


@dataclass
class SourceResult:
    """One source's read; carried keeps the last fingerprints of the files of a directory that could not be read."""

    source: Source
    files: list[FileResult] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    reason: str | None = None
    carried: list[FileResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.reason or any(f.status == FAILED for f in self.files):
            return FAILED
        if any(f.status == CHANGED for f in self.files) or self.removed:
            return CHANGED
        return READ

    def failure(self) -> str | None:
        if self.reason:
            return self.reason
        failed = [f"{Path(f.path).name}: {f.reason}" for f in self.files if f.status == FAILED]
        return "; ".join(failed) or None


def package_sources(registry: Mapping) -> list[Source]:
    """Every configured package source of every active Product, validated as Mandu-relative paths."""
    sources = []
    for product in registry.get("products", []):
        package = product.get("go_to_market_package")
        if product.get("status") != "active" or not package:
            continue
        for entry in package.get("sources") or ():
            path = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
                raise ConfigError(f"{product['name']} package source {path!r} must be a Mandu-relative path")
            prefix = entry.get("files_starting_with", "")
            if not isinstance(prefix, str) or "/" in prefix or (prefix and not path.endswith("/")):
                raise ConfigError(
                    f"{product['name']} package source {path!r}: files_starting_with names a folder's files"
                )
            sources.append(Source(product["name"], path, tuple(entry.get("needed_by") or ()), prefix))
    return sources


def fingerprint(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def file_type(path: Path) -> int | None:
    """What a path names, following links, as a stat.S_IFMT value, or None when nothing is there. A path that cannot
    be examined, such as one in a folder that cannot be searched, raises with its reason: from Python 3.14 on,
    Path.exists() and is_dir() say False for it, which would report it as missing."""
    try:
        return stat.S_IFMT(os.stat(str(path)).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return None


def raise_error(error: OSError) -> None:
    raise error


def directory_files(root: Path, relative: str, prefix: str = "") -> list[str]:
    """Mandu-relative paths of every regular file under a directory whose name starts with prefix, skipping hidden
    files such as .DS_Store.

    A folder that cannot be listed raises, so the source fails with the real reason.
    """
    found = []
    for directory, subdirs, files in os.walk(str(root / relative), onerror=raise_error):
        subdirs[:] = sorted(name for name in subdirs if not name.startswith("."))
        for name in sorted(files):
            if not name.startswith(".") and name.startswith(prefix):
                found.append(str(Path(directory, name).relative_to(root)))
    return found


def read_file(
    mandu: Path, relative: str, source: str, previous: Mapping[str, str], clock: Callable[[], str]
) -> FileResult:
    path = mandu / relative
    result = FileResult(relative, source, FAILED, previous_sha256=previous.get(relative) or None)
    try:
        kind = file_type(path)
        if kind is None:
            result.reason = "missing"
            return result
        if kind != stat.S_IFREG:
            result.reason = "not a file"
            return result
        result.sha256, result.bytes = fingerprint(path)
    except OSError as error:
        result.reason = error.strerror or str(error)
        return result
    result.read_at = clock()
    if result.previous_sha256 is None:
        # A file no earlier snapshot listed is a change to the package; on the first snapshot nothing is.
        added = bool(previous) and relative not in previous
        result.status = CHANGED if added else READ
        result.change = "added" if added else "first read"
    elif result.previous_sha256 != result.sha256:
        result.status = CHANGED
        result.change = "changed"
    else:
        result.status = READ
    return result


def take(
    mandu: Path, sources: Sequence[Source], previous: Mapping[str, str], clock: Callable[[], str]
) -> list[SourceResult]:
    """Read every source; previous maps each Mandu-relative file to its last known fingerprint. A source that cannot
    be found, listed, or read fails on its own, with the reason."""
    results = []
    for source in sources:
        result = SourceResult(source)
        if source.is_directory:
            root = mandu / source.path
            names: list[str] = []
            try:
                kind = file_type(root)
                if kind != stat.S_IFDIR:
                    result.reason = "missing" if kind is None else "not a directory"
                else:
                    names = directory_files(mandu, source.path, source.prefix)
                    what = f"files starting with {source.prefix}" if source.prefix else "files"
                    result.reason = None if names else f"holds no {what}"
            except OSError as error:
                result.reason = error.strerror or str(error)
            known = sorted(name for name in previous if source.covers(name))
            if result.reason:
                result.carried = [
                    FileResult(name, source.path, FAILED, previous_sha256=previous[name] or None, reason=result.reason)
                    for name in known
                ]
            else:
                result.files = [read_file(mandu, name, source.path, previous, clock) for name in names]
                listed = set(names)
                result.removed = [name for name in known if name not in listed]
        else:
            result.files = [read_file(mandu, source.path, source.path, previous, clock)]
        results.append(result)
    return results


def last_known(snapshot: Mapping | None) -> dict[str, str]:
    """Each file the snapshot listed, with its most recent fingerprint, carried through snapshots in which it
    could not be read; an empty string marks a file that has never been read."""
    known: dict[str, str] = {}
    for product in (snapshot or {}).get("products", {}).values():
        for entry in product.get("files", []):
            known[entry["path"]] = entry.get("sha256") or entry.get("previous_sha256") or ""
    return known


def latest_snapshot(directory: Path, before_run: str) -> tuple[str, dict] | None:
    """The newest snapshot record older than this run; run ids start with their UTC start time, so names sort."""
    if not directory.is_dir():
        return None
    names = sorted(
        name for name in os.listdir(str(directory)) if name.endswith(".json") and name[: -len(".json")] < before_run
    )
    for name in reversed(names):
        try:
            return name[: -len(".json")], json.loads(read_plain(directory / name).decode("utf-8"))
        except (UnsafeFile, ValueError):
            continue
    return None


def record(
    run_id: str, taken_at: datetime, mandu: Path, results: Sequence[SourceResult], previous_run: str | None
) -> dict[str, object]:
    products: dict[str, dict[str, object]] = {}
    for result in results:
        product = products.setdefault(
            result.source.product, {"sources": [], "files": [], "changes": {"added": [], "changed": [], "removed": []}}
        )
        product["sources"].append(
            {
                "path": result.source.path,
                **({"files_starting_with": result.source.prefix} if result.source.prefix else {}),
                "needed_by": list(result.source.needed_by),
                "status": result.status,
                **({"reason": result.failure()} if result.status == FAILED else {}),
            }
        )
        product["files"] += [file.as_json() for file in result.files + result.carried]
        if previous_run is not None:
            changes = product["changes"]
            changes["added"] += [f.path for f in result.files if f.change == "added"]
            changes["changed"] += [f.path for f in result.files if f.change == "changed"]
            changes["removed"] += result.removed
    return {
        "format": SNAPSHOT_FORMAT,
        "run": run_id,
        "taken_at": taken_at.isoformat(),
        "mandu": str(mandu),
        "previous_run": previous_run,
        "note": "Fingerprints only; the package itself stays in Mandu.",
        "products": products,
    }
