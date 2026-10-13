"""Dispatch requests the launcher files from reviewed text in src/dispatches/, each once.

A Dispatch request asks the Founder to approve a change to a Product; Mandu hands it to firstmate only once the Founder
approves it, and gr0wthlab never sends it anywhere itself. Each file in src/dispatches/ is one request in the Review
Queue item format, named <key>.md, and changes only through a reviewed pull request. The launcher queues it under an
identifier that never changes and marks its queue entry with the key, then, run after run:

- leaves it open while its whole text is unchanged, and files the new text in its place, superseding it, once a
  reviewed change alters any of it; no item the agent writes can supersede it (queue.check_incoming), so it stays
  open until the Founder decides it;
- never files it again once the Founder approved it;
- never asks the Founder the same whole text again once the Founder rejected it, so after a rejection only a reviewed
  change that alters the text files it anew; a text replaced before the Founder decided it was never decided, and is
  filed again if a reviewed change brings it back.

The whole text is the ask and all four sections, Touches and Evidence included: the Founder approves exactly the text
firstmate receives.

Two exceptions, both only after a reviewed change to the request's text while an item of it is open, which is
firstmate's own reviewed act:

- the rejected-text rule applies only while nothing is open, so a reviewed change that brings back a text the Founder
  rejected, while another text is open, files the rejected text again in that open item's place;
- an approval the Founder gave an item that a reviewed change had already replaced still counts as the request's
  approval, though Mandu hands no superseded item to firstmate: the replacement stays open for the Founder to decide,
  no reviewed change replaces it any more, and nothing is filed after it.

A request is compared with its open item by reading that item's file. When the file cannot be read, nothing shows
the reviewed text changed, so the item stays open as it is (queue.stands), and the run reports the file.

A request with no open item is compared with each item of it the Founder rejected in the same way. When a rejected
item's file cannot be read, the fingerprint the run state holds for that item stands in for it: the request's own
fingerprint means the Founder rejected this ask, and another means that item asked something else. Where the run
state holds none, nothing shows whether the Founder rejected this text, so the request is held: nothing is filed, and
the run reports the file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import exchange
from .areas import Store, UnsafeFile
from .queue import APPROVED, MAX_SLUG, OPEN, REJECTED, SUPERSEDED, Ledger, stands
from .state import queued_item

DISPATCHES = PurePosixPath("src/dispatches")
KIND = "dispatch-request"
ORIGIN = "dispatch"

FILED = "filed"
REPLACED = "replaced"
WAITING = "open"
DONE = "approved"
DECIDED = "decided"
ASKED = "asked"
UNREAD = "unread"
HELD = "held"
COULD_NOT_BE_READ = "could not be read"  # how a problem reads when a file is there and the read failed


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
    """What became of one reviewed request this run; identifier is its current queue item, if it has one, and
    still_open is the replacement an approval of an already replaced item left open."""

    key: str
    status: str
    identifier: str | None
    replaced: str | None = None
    still_open: str | None = None
    unread: str = ""  # the queued item's file, and why it could not be read, when the request waits on that alone

    @property
    def acted(self) -> bool:
        return self.status in (FILED, REPLACED)

    def account(self) -> str:
        done = f"{self.key} approved as `{self.identifier}`; never filed again"
        if self.still_open:
            done += (
                f"; `{self.still_open}`, filed in its place before that approval was taken in, stays open, and no"
                " reviewed change replaces it"
            )
        return {
            FILED: f"{self.key} filed as `{self.identifier}`",
            REPLACED: f"{self.key} filed as `{self.identifier}` in place of `{self.replaced}`, as its reviewed text"
            " changed",
            WAITING: f"{self.key} open as `{self.identifier}`",
            DONE: done,
            DECIDED: f"{self.key} rejected as `{self.identifier}`; not asked again unless any part of its reviewed"
            " text changes",
            ASKED: f"{self.key} asks the same as `{self.identifier}`, already queued; not filed",
            UNREAD: f"{self.key} open as `{self.identifier}`, left as it is, since {self.unread}",
            HELD: f"{self.key} not filed, since {self.unread}, so nothing shows whether the Founder rejected this"
            " text; the next run compares them again",
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
            problems.append(f"`{relative}` {COULD_NOT_BE_READ} ({error}), so it was not filed")
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


def whole_text(item: exchange.Item) -> str:
    """Everything the Founder reads in an item: its ask and all four sections."""
    return exchange.render_content(item.kind, item.ask, item.body, item.touches, item.evidence)


def queued_text(store: Store, entry: Mapping[str, object], products: Sequence[str]) -> tuple[str | None, str]:
    """The whole text of a queued item, or None, with the reason, when its item file cannot be read as one."""
    try:
        return whole_text(queued_item(store.root, entry, products)), ""
    except (OSError, ValueError, UnsafeFile) as error:
        why = getattr(error, "strerror", None) or str(error)
        return None, f"`{entry['file']}`, the item file of `{entry['id']}`, {COULD_NOT_BE_READ} ({why})"


def rejected_text(
    store: Store,
    mine: Sequence[Mapping[str, object]],
    request: Request,
    products: Sequence[str],
    fingerprints: Mapping[str, str],
) -> tuple[Mapping[str, object] | None, list[str]]:
    """The newest of a request's items in which the Founder rejected its whole text, or None, and with None each
    rejected item nothing readable tells from that text, as its file and why it could not be read.

    A rejected item is known by its file, or, when that cannot be read, by the fingerprint the run holds for it:
    the request's own means the Founder rejected this ask, and another that the item asked something else.
    """
    text, fingerprint = whole_text(request.item), exchange.item_hash(request.item)
    unsettled = []
    for entry in reversed(mine):
        if REJECTED not in (entry["status"], entry.get("decided")):
            continue
        queued, lost = queued_text(store, entry, products)
        known = fingerprints.get(str(entry["id"])) if lost else None
        if queued == text or known == fingerprint:
            return entry, []
        if lost and known is None:
            unsettled.append(lost)
    return None, unsettled


def unread(problems: Sequence[str], filings: Sequence[Filing]) -> list[str]:
    """Each file a run could not read that a request's filing rests on: a reviewed text, or a queued item's file."""
    return [problem for problem in problems if COULD_NOT_BE_READ in problem] + [
        filing.unread for filing in filings if filing.unread
    ]


def file(
    ledger: Ledger,
    store: Store,
    requests: Sequence[Request],
    products: Sequence[str],
    seen: dict[str, str],
    run_id: str,
    now: datetime,
    fingerprints: Mapping[str, str] | None = None,
) -> list[Filing]:
    """Queue each reviewed request that needs it, following the rules above.

    A request is compared with its own queued items by whole text; seen maps each fingerprint to an item that asks
    it, which stops a request another item already asks, and comes to name every item filed here. fingerprints
    maps each queued item to its fingerprint as the run knows it (state.item_hashes): read from its item file, or
    kept by the run state where that file cannot be read.
    """
    filings = []
    for request in requests:
        text = whole_text(request.item)
        fingerprint = exchange.item_hash(request.item)
        mine = sorted(
            (entry for entry in ledger.entries.values() if entry.get("origin") == request.origin),
            key=lambda entry: (str(entry["published_at"]), str(entry["id"])),
        )
        approved = [entry for entry in mine if APPROVED in (entry["status"], entry.get("decided"))]
        current = next((entry for entry in mine if entry["status"] == OPEN), None)
        if approved:
            still_open = str(current["id"]) if current is not None else None
            filings.append(Filing(request.key, DONE, str(approved[-1]["id"]), still_open=still_open))
            continue
        queued, lost = queued_text(store, current, products) if current is not None else (None, "")
        kept = stands(current, [lost] if lost else [])
        if kept:
            # Nothing shows the reviewed text changed, so the open item is not replaced.
            filings.append(Filing(request.key, UNREAD, kept.item, unread=lost))
            continue
        if current is not None and queued == text:
            filings.append(Filing(request.key, WAITING, str(current["id"])))
            continue
        if current is None:
            asked, unsettled = rejected_text(store, mine, request, products, fingerprints or {})
            if asked is not None:
                filings.append(Filing(request.key, DECIDED, str(asked["id"])))
                continue
            if unsettled:
                filings.append(Filing(request.key, HELD, None, unread="; ".join(unsettled)))
                continue
            asker = seen.get(fingerprint)
            if asker is not None and ledger.entries.get(asker, {}).get("origin") != request.origin:
                filings.append(Filing(request.key, ASKED, asker))
                continue
        fields = dict(request.item.fields)
        if current is not None:
            fields["supersedes"] = str(current["id"])
        item = exchange.Item(fields, request.item.ask, request.item.body, request.item.touches, request.item.evidence)
        identifier = ledger.publish(store, item, request.key, run_id, now, origin=request.origin)
        seen[fingerprint] = identifier
        if current is None:
            filings.append(Filing(request.key, FILED, identifier))
        else:
            ledger.close(current, SUPERSEDED, run_id, now, superseded_by=identifier)
            filings.append(Filing(request.key, REPLACED, identifier, str(current["id"])))
    return filings
