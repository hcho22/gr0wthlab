"""The Review Queue: every item ever queued, which are still open, and the order Mandu presents them in.

The ledger lives in workspace/review-queue/queue.json, which the launcher alone writes.
An item is queued once, under an identifier that never changes, and is closed by the Founder's decision (approved
or rejected) or by a newer item that supersedes it; a closed item never returns to the open list.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import exchange
from .areas import Areas, UnsafeFile, read_plain

OPEN = "open"
APPROVED = "approved"
REJECTED = "rejected"
SUPERSEDED = "superseded"
INCOMING = "incoming"
ITEMS = "items"
SET_ASIDE = "set-aside"
QUEUE_FILE = "queue.json"


class QueueError(Exception):
    """The ledger cannot be read, so the queue is left untouched this run."""


@dataclass(frozen=True)
class DecisionOutcome:
    """What became of one decision record Mandu holds."""

    decision: exchange.Decision
    source: str
    status: str  # taken, already-taken, conflict, unknown-item, item-withdrawn
    entry: Mapping[str, object] | None


@dataclass(frozen=True)
class SetAside:
    name: str
    moved_to: str
    problems: tuple[str, ...]


class Ledger:
    def __init__(self, entries: Sequence[Mapping[str, object]] = ()):
        self.entries: dict[str, dict[str, object]] = {str(entry["id"]): dict(entry) for entry in entries}

    @classmethod
    def load(cls, path: Path) -> Ledger:
        if not path.exists():
            return cls()
        try:
            data = json.loads(read_plain(path).decode("utf-8"))
        except (OSError, ValueError, UnsafeFile) as error:
            raise QueueError(f"cannot read {path.name}: {error}") from error
        if not isinstance(data, dict) or data.get("exchange") != exchange.EXCHANGE_VERSION:
            raise QueueError(f"{path.name} is not an exchange version {exchange.EXCHANGE_VERSION} queue")
        return cls(list(data.get("open", [])) + list(data.get("closed", [])))

    def open_entries(self) -> list[dict[str, object]]:
        return [entry for entry in self.entries.values() if entry["status"] == OPEN]

    def close(self, entry: dict[str, object], status: str, run_id: str, now: datetime, **details: object) -> None:
        entry.update(status=status, closed_by_run=run_id, closed_at=now.isoformat(), **details)
        entry.pop("carried_over", None)

    def take_decisions(
        self, decisions: Sequence[tuple[exchange.Decision, str]], run_id: str, now: datetime
    ) -> list[DecisionOutcome]:
        """Close each open item Mandu recorded a decision for; a decided item is never reopened or re-asked."""
        outcomes = []
        for decision, source in sorted(decisions, key=lambda pair: pair[0].item):
            entry = self.entries.get(decision.item)
            if entry is None:
                status = "unknown-item"
            elif entry["status"] == OPEN:
                closed = APPROVED if decision.decision == exchange.APPROVE else REJECTED
                self.close(entry, closed, run_id, now, decided_at=decision.decided_at)
                status = "taken"
            elif entry["status"] == SUPERSEDED:
                status = "item-withdrawn"
            elif (
                entry["status"] == (APPROVED if decision.decision == exchange.APPROVE else REJECTED)
                and entry.get("decided_at") == decision.decided_at
            ):
                status = "already-taken"
            else:
                status = "conflict"
            outcomes.append(DecisionOutcome(decision, source, status, entry))
        return outcomes

    def next_id(self, day: date, slug: str) -> str:
        base = exchange.item_id(day, slug)[: exchange.MAX_ID]
        candidate, number = base, 2
        while candidate in self.entries:
            candidate = f"{base}-{number}"
            number += 1
        return candidate

    def publish(
        self,
        areas: Areas,
        item: exchange.Item,
        slug: str,
        run_id: str,
        now: datetime,
        topic: str | None = None,
    ) -> str:
        """Queue an item under a new identifier, writing its canonical text to items/<id>.md."""
        # The identifier's date is the Mac's local date, the one the Founder sees on the run.
        identifier = self.next_id(now.astimezone().date(), slug)
        fields = dict(item.fields, exchange=str(exchange.EXCHANGE_VERSION), id=identifier)
        path = areas.path("review_queue", ITEMS, f"{identifier}.md")
        areas.write_text(path, exchange.render_item(fields, item.ask, item.body, item.touches, item.evidence))
        entry: dict[str, object] = {
            "id": identifier,
            "kind": item.kind,
            "ask": item.ask,
            "file": areas.relative(path),
            "published_at": now.isoformat(),
            "published_by_run": run_id,
            "status": OPEN,
        }
        for key in ("product", "slot", "supersedes"):
            if item.fields.get(key):
                entry[key] = item.fields[key]
        if topic:
            entry["topic"] = topic
        self.entries[identifier] = entry
        return identifier

    def take_incoming(
        self,
        areas: Areas,
        products: Sequence[str],
        run_id: str,
        now: datetime,
        seen: dict[str, str] | None = None,
    ) -> tuple[list[str], list[SetAside]]:
        """Queue every valid item the agent wrote to incoming/; set every other file aside with its problems.

        seen maps each queued item's fingerprint to its identifier; an item that asks the same thing as one already
        open or decided is set aside, so nothing decided is ever asked again under another name.
        """
        seen = {} if seen is None else seen
        incoming = areas.path("review_queue", INCOMING)
        published: list[str] = []
        set_aside: list[SetAside] = []
        superseding: list[tuple[str, str]] = []
        for path in list(areas.files(incoming)):
            name = areas.relative(path)[len("review-queue/incoming/") :]
            problems: list[str] = []
            item = None
            slug = path.name[: -len(".md")] if path.name.endswith(".md") else ""
            if "/" in name or not exchange.SLUG_PATTERN.fullmatch(slug) or len(slug) > 60:
                problems.append("name it <slug>.md directly in incoming/, the slug in lowercase-with-hyphens")
            try:
                text = read_plain(path).decode("utf-8")
            except (UnsafeFile, UnicodeDecodeError, OSError) as error:
                problems.append(f"unreadable: {error}")
                text = None
            if text is not None:
                check = exchange.check_item(text, products)
                problems += check.problems
                item = check.item
            if item is not None and item.fields.get("supersedes"):
                target = self.entries.get(item.fields["supersedes"])
                if target is None or target["status"] != OPEN:
                    problems.append(f"supersedes {item.fields['supersedes']}, which is not an open item")
            fingerprint = exchange.item_hash(item) if item is not None else None
            if fingerprint in seen:
                earlier = self.entries.get(seen[fingerprint], {})
                problems.append(f"asks the same as {seen[fingerprint]}, which is {earlier.get('status', 'queued')}")
            if problems or item is None:
                set_aside.append(self.set_aside(areas, path, name, run_id, problems))
                continue
            identifier = self.publish(areas, item, slug, run_id, now)
            areas.remove(path)
            published.append(identifier)
            seen[str(fingerprint)] = identifier
            if item.fields.get("supersedes"):
                superseding.append((item.fields["supersedes"], identifier))
        for directory in sorted((p for p in incoming.rglob("*") if p.is_dir() and not p.is_symlink()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
        for old, new in superseding:
            if self.entries[old]["status"] == OPEN:
                self.close(self.entries[old], SUPERSEDED, run_id, now, superseded_by=new)
        return published, set_aside

    def set_aside(self, areas: Areas, path: Path, name: str, run_id: str, problems: Sequence[str]) -> SetAside:
        """Move a file out of the agent's reach into set-aside/<run>/, keeping a plain file's text for the record."""
        target = areas.path("review_queue", SET_ASIDE, run_id, name.replace("/", "--"))
        try:
            areas.write_bytes(target, read_plain(path))
        except (UnsafeFile, OSError) as error:
            problems = list(problems) + [f"not kept: {error}"]
            target = None
        areas.remove(path)
        return SetAside(name, areas.relative(target) if target else "", tuple(problems))

    def ordered(self) -> list[dict[str, object]]:
        """Open items in presentation order: posts by nearest slot, then each kind in turn, oldest first."""
        kinds = list(exchange.KINDS)

        def key(entry: Mapping[str, object]) -> tuple:
            slot = exchange.parse_datetime(str(entry.get("slot", ""))) if entry["kind"] == "post" else None
            return (
                kinds.index(str(entry["kind"])),
                slot.timestamp() if slot else 0.0,
                str(entry["published_at"]),
                str(entry["id"]),
            )

        return sorted(self.open_entries(), key=key)

    def as_json(self, run_id: str, now: datetime, report: str) -> dict[str, object]:
        """queue.json: open items in order, each marked carried_over if an earlier run queued it."""
        opened = []
        for entry in self.ordered():
            entry["carried_over"] = entry["published_by_run"] != run_id
            opened.append(entry)
        closed = sorted(
            (entry for entry in self.entries.values() if entry["status"] != OPEN),
            key=lambda entry: (str(entry.get("closed_at", "")), str(entry["id"])),
        )
        return {
            "exchange": exchange.EXCHANGE_VERSION,
            "updated_by_run": run_id,
            "updated_at": now.isoformat(),
            "run_report": report,
            "paths": "Every path here is relative to the workspace/ directory that holds this file's folder.",
            "open": opened,
            "closed": closed,
        }
