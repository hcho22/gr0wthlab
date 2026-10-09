"""Dispatch requests the launcher files from reviewed text in src/dispatches/, each once.

A Dispatch request asks the Founder to approve a change to a Product; Mandu hands it to firstmate only once the Founder
approves it, and gr0wthlab never sends it anywhere itself. Each file in src/dispatches/ is one request in the Review
Queue item format, named <key>.md, and changes only through a reviewed pull request. The launcher queues it under an
identifier that never changes and marks its queue entry with the key, then, run after run:

- leaves it open while its text is unchanged, and files the new text in its place, superseding it, once a reviewed
  change alters the text;
- never files it again once the Founder approved it;
- never asks the Founder the same text again once decided, so after a rejection only a reviewed change that alters the
  text files it anew.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import exchange
from .areas import Store
from .queue import APPROVED, MAX_SLUG, OPEN, SUPERSEDED, Ledger

DISPATCHES = PurePosixPath("src/dispatches")
KIND = "dispatch-request"
ORIGIN = "dispatch"

FILED = "filed"
REPLACED = "replaced"
WAITING = "open"
DONE = "approved"
DECIDED = "decided"
ASKED = "asked"


@dataclass(frozen=True)
class Request:
    key: str
    path: str  # relative to the repository
    item: exchange.Item

    @property
    def origin(self) -> str:
        return f"{ORIGIN}/{self.key}"


@dataclass(frozen=True)
class Filing:
    """What became of one reviewed request this run; identifier is its current queue item, if it has one."""

    key: str
    status: str
    identifier: str | None
    replaced: str | None = None

    @property
    def acted(self) -> bool:
        return self.status in (FILED, REPLACED)

    def account(self) -> str:
        return {
            FILED: f"{self.key} filed as `{self.identifier}`",
            REPLACED: f"{self.key} filed as `{self.identifier}` in place of `{self.replaced}`, as its text changed",
            WAITING: f"{self.key} open as `{self.identifier}`",
            DONE: f"{self.key} approved as `{self.identifier}`; never filed again",
            DECIDED: f"{self.key} decided as `{self.identifier}`; not asked again unless its reviewed text changes",
            ASKED: f"{self.key} asks the same as `{self.identifier}`, already queued; not filed",
        }[self.status]


def load(repo_root: Path, products: Sequence[str]) -> tuple[list[Request], list[str]]:
    """Every reviewed request in src/dispatches/, and why any file there is not one."""
    folder = repo_root / DISPATCHES
    if not folder.is_dir():
        return [], []
    requests, problems = [], []
    for path in sorted(folder.iterdir()):
        if path.name.startswith("."):
            continue
        relative = f"{DISPATCHES}/{path.name}"
        key = path.name[: -len(".md")] if path.name.endswith(".md") else ""
        if not exchange.SLUG_PATTERN.fullmatch(key) or len(key) > MAX_SLUG or not path.is_file():
            problems.append(f"`{relative}` is not a Dispatch request: name each one <key>.md in lowercase-with-hyphens")
            continue
        try:
            check = exchange.check_item(path.read_text(encoding="utf-8"), products)
        except (OSError, UnicodeDecodeError) as error:
            problems.append(f"`{relative}` could not be read ({error}), so it was not filed")
            continue
        issues = list(check.problems)
        if check.item is not None and check.item.kind != KIND:
            issues.append(f"its kind must be {KIND}")
        if check.item is not None and (check.item.fields.get("supersedes") or check.item.fields.get("slot")):
            issues.append("the launcher alone decides what it supersedes, and only a post has a slot")
        if issues:
            problems.append(f"`{relative}` was not filed: {'; '.join(issues)}")
            continue
        requests.append(Request(key, relative, check.item))
    return requests, problems


def file(
    ledger: Ledger,
    store: Store,
    requests: Sequence[Request],
    hashes: Mapping[str, str],
    seen: dict[str, str],
    run_id: str,
    now: datetime,
) -> list[Filing]:
    """Queue each reviewed request that needs it, following the rules above.

    hashes maps each queued item to its fingerprint; seen maps each fingerprint to the item that first asked it, and
    gains every item filed here.
    """
    filings = []
    for request in requests:
        fingerprint = exchange.item_hash(request.item)
        mine = sorted(
            (entry for entry in ledger.entries.values() if entry.get("origin") == request.origin),
            key=lambda entry: (str(entry["published_at"]), str(entry["id"])),
        )
        approved = [entry for entry in mine if APPROVED in (entry["status"], entry.get("decided"))]
        current = next((entry for entry in mine if entry["status"] == OPEN), None)
        if approved:
            filings.append(Filing(request.key, DONE, str(approved[-1]["id"])))
            continue
        if current is not None and hashes.get(str(current["id"])) == fingerprint:
            filings.append(Filing(request.key, WAITING, str(current["id"])))
            continue
        if current is None:
            asked = next((entry for entry in reversed(mine) if hashes.get(str(entry["id"])) == fingerprint), None)
            if asked is not None:
                filings.append(Filing(request.key, DECIDED, str(asked["id"])))
                continue
            if fingerprint in seen:
                filings.append(Filing(request.key, ASKED, seen[fingerprint]))
                continue
        fields = dict(request.item.fields)
        if current is not None:
            fields["supersedes"] = str(current["id"])
        item = exchange.Item(fields, request.item.ask, request.item.body, request.item.touches, request.item.evidence)
        identifier = ledger.publish(store, item, request.key, run_id, now, origin=request.origin)
        seen.setdefault(fingerprint, identifier)
        if current is None:
            filings.append(Filing(request.key, FILED, identifier))
        else:
            ledger.close(current, SUPERSEDED, run_id, now, superseded_by=identifier)
            filings.append(Filing(request.key, REPLACED, identifier, str(current["id"])))
    return filings
