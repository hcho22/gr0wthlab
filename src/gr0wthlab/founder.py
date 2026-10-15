"""The Founder's records: every decision on a Review Queue item, and the records of what the Founder did.

They live in ledger/founder/, in gr0wthlab's own repository, since ADR 0002 moved them out of Mandu. Nothing reaches
the public unless the Founder approved it, so this module holds the one invariant the whole project guards, and is the
only place that enforces it:

1. Only the Founder-side command writes a Founder record. `gr0wthlab sitting` (sitting.py), which the Founder starts
   outside the sandbox, is the only code that makes a Writer, and it writes only when a request from its own page asks
   it to. The weekly run, the agent, and every other command only read: the launcher's own Store refuses every path in
   this area (areas.Store.path), and src/tests/test_founder.py and test_probe.py hold the first half by running a
   whole run, each check command, and the boundary check with the Writer replaced by a refusal.
2. A Founder record is a plain file with one link, directly inside one of the six folders named in KINDS, each a real
   folder under a real ledger/founder/. Nothing under workspace/ is ever read as one, whatever its name, location, or
   content: read() opens no path outside those six folders and follows no link, so a link in a record's place, a file
   that is also linked from somewhere else, and a record folder that is itself a link are all refused. check() stops a
   run, a boundary check, and a sitting before they start when a folder is missing or is not a real folder.
3. The sandboxed agent can read the records and can never write them. The area is inside ledger/, which is no writable
   area; the preflight before every session's agent tries to create a file in each folder from inside the sandbox
   (codex.preflight_targets) and the agent is started only when every try was refused, and the boundary check proves
   each folder on its own from the runtime's records (probe.PROBE_TARGETS).

The formats are the ones docs/mandu-exchange.md describes, parsed by exchange.py, which the page and the run share: the
page checks a record with the run's own parser before it writes it. A record that parser cannot use, as one changed by
hand or damaged can be, is not a record: the run names it with its problem and takes nothing from it. parse() is the
one way a record file becomes a record, for the run and for the page, and named() the one way a report names the file.

A decision can be changed or taken back on the page until a run has taken it in, and never after. A run takes it in
when it writes the decision's Evidence (taken_in); the page and the run hold locked() around a change and around the
taking in, so the two cannot cross.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO, TypeVar

from .areas import UnsafeFile, read_plain, write_whole
from .boundary import FOUNDER, FOUNDER_KINDS, ConfigError
from .waitlist import looks_like_address

# The six kinds of record, each in the folder of ledger/founder/ named for it. Every one of these folders is a
# forbidden target of the preflight before every session and of the boundary check.
KINDS = FOUNDER_KINDS
DECISIONS, SITTINGS, BETA_BUILDS, BETA_REPORTS, OUTREACH, RESULTS = KINDS
# Where a run keeps the Evidence of each decision it took in, under ledger/; the file's existence is the taking in.
TAKEN_IN = ("evidence", "decisions")
# The lock the page and a run share, beside the run lock in ledger/; never committed.
LOCK_FILE = "founder.lock"
# How long a run or the page waits for that lock, in seconds. Each holds it for a few file reads and one write.
LOCK_WAIT = 10.0
# A record's file name without .json: an item identifier, a date, a Product, or a Product and a date.
STEM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")
HOLDS_ADDRESS = "it holds something that looks like an email address, so nothing in it was read or kept"
# What a report says in place of a file name that looks like an address.
UNNAMED = "a file whose name is not repeated here"

Raw = tuple[str, Path, bytes]  # a record file: its name, its path, and its bytes
T = TypeVar("T")
# Why a file that is no record file is none: it is not a read that failed, so nothing it might hold is unknown.
STRAY = "only <name>.json record files belong here"


class Busy(Exception):
    """The lock the page and a run share was held for longer than either ever holds it."""


def root(ledger: Path) -> Path:
    return ledger / FOUNDER


def folders(ledger: Path) -> dict[str, Path]:
    """The six record folders, by kind."""
    return {kind: ledger / FOUNDER / kind for kind in KINDS}


def check(ledger: Path) -> None:
    """Fail closed: ledger/founder/ and each of its six folders is a real folder, reached through no link.

    A folder that is missing cannot be proven refused, and one that is a link could lead anywhere, into workspace/
    included, so either stops whatever was about to start.
    """
    for path in (root(ledger), *folders(ledger).values()):
        if not real_folder(path):
            # Named from the repository's root: a session's record, and from it a run report, can carry this line.
            raise ConfigError(
                f"the Founder's records folder {path.relative_to(ledger.parent)} must be a real folder that can be"
                " read, not missing and not a link; the repository holds it, so restore it from git"
            )


def real_folder(path: Path) -> bool:
    """Whether a path is a folder itself, reached through no link; one that cannot be examined is not."""
    try:
        return os.path.realpath(str(path)) == str(path) and stat.S_ISDIR(os.lstat(str(path)).st_mode)
    except OSError:
        return False


def nameable(name: str) -> bool:
    """Whether a report may repeat a file's name or path. Either can be typed by hand, so one that looks like an
    address is never repeated: UNNAMED stands in its place."""
    return not looks_like_address(name)


def named(kind: str, name: str) -> str:
    """One of the record files by its path under ledger/, the name a run reports and fingerprints it under."""
    return f"{FOUNDER}/{kind}/{name if nameable(name) else f'({UNNAMED})'}"


def shown(kind: str, name: str) -> str:
    """The same file as a sentence of a report or of the page names it."""
    return f"`{named(kind, name)}`"


def read(ledger: Path, kind: str) -> tuple[list[Raw], list[tuple[str, str]], str | None]:
    """Every record file of one kind as (name, path, bytes); each other file there, by name, with why it is no record;
    and why the folder could not be read, if it could not.

    Only a plain <name>.json file with one link, directly in the kind's own real folder, is a record file. Hidden
    files are a write's own temporaries and are skipped.
    """
    if kind not in KINDS:
        raise ConfigError(f"{kind!r} is not a kind of Founder record")
    folder = folders(ledger)[kind]
    found: list[Raw] = []
    others: list[tuple[str, str]] = []
    if not real_folder(folder):
        return found, others, "it is not a real folder that can be read"
    try:
        names = sorted(os.listdir(str(folder)))
    except OSError as error:
        return found, others, error.strerror or str(error)
    for name in names:
        if name.startswith("."):
            continue
        if not name.endswith(".json"):
            others.append((name, STRAY))
            continue
        try:
            found.append((name, folder / name, read_plain(folder / name)))
        except UnsafeFile as error:
            others.append((name, str(error)))
        except OSError as error:
            others.append((name, error.strerror or str(error)))
    return found, others, None


def holds_address(name: str, data: bytes) -> bool:
    """Whether a record file's name or anything in it looks like an email address, whatever its bytes; such a file is
    refused whole, so nothing it holds is ever read, kept, or repeated (FR-11)."""
    return looks_like_address(name) or looks_like_address(data.decode("utf-8", errors="replace"))


def parse(
    name: str, data: bytes, parser: Callable[[str, object], tuple[T | None, list[str]]]
) -> tuple[T | None, list[str]]:
    """One record file as the parser of its kind reads it: the record, or why the file is no record.

    The address check runs over the file's name and the whole file before anything in it is read, so a file that
    fails it is refused whole and nothing it holds is ever repeated (FR-11). Only then is it decoded and handed to
    the parser, under the name it has without .json.
    """
    if holds_address(name, data):
        return None, [HOLDS_ADDRESS]
    try:
        value = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return None, ["it is not UTF-8 text"]
    except ValueError as error:
        return None, [f"it is not JSON (line {getattr(error, 'lineno', '?')})"]
    return parser(name[: -len(".json")], value)


def taken_in(ledger: Path, item: str) -> bool:
    """Whether a run has taken in the Founder's decision on an item, after which that decision never changes."""
    return os.path.lexists(str(ledger.joinpath(*TAKEN_IN, f"{item}.json")))


@contextmanager
def locked(ledger: Path, wait: float | None = None) -> Iterator[None]:
    """Hold the lock the page and a run share: the page around looking whether a decision was taken in and changing
    it, a run around reading the decisions and taking them in. Without it, a change made in the very moment a run
    read the old record would be shown to the Founder as saved and never take effect.

    Nothing here waits forever: a lock still held after `wait` seconds, LOCK_WAIT unless given, raises Busy.
    """
    wait = LOCK_WAIT if wait is None else wait
    handle: TextIO = (ledger / LOCK_FILE).open("a")
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Busy(f"the Founder's records were locked for {wait:g} seconds") from None
                time.sleep(0.05)
        yield
    finally:
        handle.close()


class Writer:
    """The only writer of the Founder's records.

    Only sitting.py makes one, for the Founder-side command, and each write is one explicit act of the Founder's on its
    page. It writes each record whole, through a temporary file in the same folder, and only into one of the six real
    folders; it never follows a link and never writes anywhere else.
    """

    def __init__(self, ledger: Path):
        check(ledger)
        self.ledger = ledger

    def path(self, kind: str, stem: str) -> Path:
        if kind not in KINDS:
            raise ConfigError(f"{kind!r} is not a kind of Founder record")
        if not STEM.fullmatch(stem) or looks_like_address(stem):
            raise ConfigError(f"{stem!r} cannot name a Founder record")
        check(self.ledger)
        return folders(self.ledger)[kind] / f"{stem}.json"

    def write(self, kind: str, stem: str, record: Mapping[str, object]) -> Path:
        """Write one record, whole, and return its path."""
        path = self.path(kind, stem)
        data = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
        if holds_address(path.name, data.encode("utf-8")):
            raise ConfigError("a Founder record never holds anything that looks like an email address")
        write_whole(path, data.encode("utf-8"))
        return path

    def remove(self, kind: str, stem: str) -> None:
        """Remove one record, as when the Founder takes a decision back; a link in its place is removed, never
        followed, and a record that is not there is no error."""
        path = self.path(kind, stem)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
