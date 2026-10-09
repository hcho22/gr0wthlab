"""The Review Queue: every item ever queued, which are still open, and the order Mandu presents them in.

The ledger lives in ledger/review-queue/queue.json, beside the published items; only the launcher writes there, and
the agent can only read it. The agent proposes items in workspace/review-queue/incoming/, which the launcher checks.
An item is queued once, under an identifier that never changes, and is closed by the Founder's decision (approved
or rejected) or by a newer item that supersedes it; a closed item never returns to the open list.
An open item is carried over once the Founder has left it undecided at a sitting.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import exchange
from .areas import Areas, Store, UnsafeFile, read_plain
from .boundary import ConfigError

OPEN = "open"
APPROVED = "approved"
REJECTED = "rejected"
SUPERSEDED = "superseded"
REVIEW_QUEUE = "review-queue"
INCOMING = "incoming"
ITEMS = "items"
SET_ASIDE = "set-aside"
QUEUE_FILE = "queue.json"
MAX_SLUG = 60


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


def slug_of(name: str) -> str:
    return name[: -len(".md")] if name.endswith(".md") else ""


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
        problem = exchange.version_problem(data.get("exchange")) if isinstance(data, dict) else "not a JSON object"
        if problem:
            raise QueueError(f"cannot read {path.name}: {problem}")
        return cls(list(data.get("open", [])) + list(data.get("closed", [])))

    def open_entries(self) -> list[dict[str, object]]:
        return [entry for entry in self.entries.values() if entry["status"] == OPEN]

    def close(self, entry: dict[str, object], status: str, run_id: str, now: datetime, **details: object) -> None:
        entry.update(status=status, closed_by_run=run_id, closed_at=now.isoformat(), **details)
        entry.pop("carried_over", None)
        entry.pop("carried_over_from", None)

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

    def publish(self, store: Store, item: exchange.Item, slug: str, run_id: str, now: datetime) -> str:
        """Queue an item under a new identifier, writing its canonical text to review-queue/items/<id>.md."""
        # The identifier's date is the Mac's local date, the one the Founder sees on the run.
        identifier = self.next_id(now.astimezone().date(), slug)
        fields = dict(item.fields, exchange=str(exchange.EXCHANGE_VERSION), id=identifier)
        path = store.path(REVIEW_QUEUE, ITEMS, f"{identifier}.md")
        store.write_text(path, exchange.render_item(fields, item.ask, item.body, item.touches, item.evidence))
        entry: dict[str, object] = {
            "id": identifier,
            "kind": item.kind,
            "ask": item.ask,
            "file": store.relative(path),
            "published_at": now.isoformat(),
            "published_by_run": run_id,
            "status": OPEN,
        }
        for key in ("product", "slot", "supersedes"):
            if item.fields.get(key):
                entry[key] = item.fields[key]
        self.entries[identifier] = entry
        return identifier

    def take_incoming(
        self,
        areas: Areas,
        store: Store,
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
        areas.ensure_folder(incoming)
        published: list[str] = []
        set_aside: list[SetAside] = []
        superseding: list[tuple[str, str]] = []
        for path in list(areas.files(incoming)):
            name = areas.relative(path)[len("review-queue/incoming/") :]
            item, problems = self.check_incoming(path, name, products, seen)
            if item is None:
                set_aside.append(self.set_aside(areas, store, path, name, run_id, problems))
                continue
            try:
                identifier = self.publish(store, item, slug_of(name), run_id, now)
            except (OSError, ConfigError) as error:
                problem = f"could not be queued ({error})"
                set_aside.append(self.set_aside(areas, store, path, name, run_id, [problem]))
                continue
            areas.remove(path)
            published.append(identifier)
            seen[exchange.item_hash(item)] = identifier
            if item.fields.get("supersedes"):
                superseding.append((item.fields["supersedes"], identifier))
        areas.remove_empty_folders(incoming)
        for old, new in superseding:
            if self.entries[old]["status"] == OPEN:
                self.close(self.entries[old], SUPERSEDED, run_id, now, superseded_by=new)
        return published, set_aside

    def check_incoming(
        self, path: Path, name: str, products: Sequence[str], seen: Mapping[str, str]
    ) -> tuple[exchange.Item | None, list[str]]:
        """Every rule a file in incoming/ must pass to be queued, for the launcher and the agent's own check alike:
        its name, the item format, an open item to supersede, and no repeat of an item queued or decided.

        name is the file's path inside incoming/; seen maps each queued item's fingerprint to its identifier.
        The item comes back only when there is no problem.
        """
        problems: list[str] = []
        slug = slug_of(name)
        if "/" in name or not exchange.SLUG_PATTERN.fullmatch(slug) or len(slug) > MAX_SLUG:
            problems.append("name it <slug>.md directly in incoming/, the slug in lowercase-with-hyphens")
        try:
            check = exchange.check_item(read_plain(path).decode("utf-8"), products)
        except (UnsafeFile, UnicodeDecodeError, OSError) as error:
            return None, problems + [f"unreadable: {error}"]
        problems += check.problems
        item = check.item
        if item is None:
            return None, problems
        target = item.fields.get("supersedes")
        if target and self.entries.get(target, {}).get("status") != OPEN:
            problems.append(f"supersedes {target}, which is not an open item")
        fingerprint = exchange.item_hash(item)
        if fingerprint in seen:
            earlier = self.entries.get(seen[fingerprint])
            status = earlier["status"] if earlier else "also in incoming/"
            problems.append(f"asks the same as {seen[fingerprint]}, which is {status}")
        return (None if problems else item), problems

    def set_aside(
        self, areas: Areas, store: Store, path: Path, name: str, run_id: str, problems: Sequence[str]
    ) -> SetAside:
        """Take a file out of incoming/ into review-queue/set-aside/<run>/, keeping a plain file's text."""
        target = store.path(REVIEW_QUEUE, SET_ASIDE, run_id, name.replace("/", "--"))
        try:
            store.write_bytes(target, read_plain(path))
        except (UnsafeFile, OSError) as error:
            problems = list(problems) + [f"not kept: {error}"]
            target = None
        areas.remove(path)
        return SetAside(name, store.relative(target) if target else "", tuple(problems))

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

    def mark_carried_over(self, sittings: Mapping[str, str]) -> None:
        """Mark each open item the Founder left undecided at a sitting, with the date of the first such sitting.

        sittings maps each sitting's date to the run that first took in its record. An item was open at a sitting
        dated no earlier than the day it was queued whose record reached gr0wthlab only after the run that queued
        it; an item queued after a sitting, even on the same day, is not carried over from it.
        """
        for entry in self.open_entries():
            queued_on = datetime.fromisoformat(str(entry["published_at"])).astimezone().date().isoformat()
            undecided_at = sorted(
                day for day, run in sittings.items() if day >= queued_on and run > str(entry["published_by_run"])
            )
            entry["carried_over"] = bool(undecided_at)
            if undecided_at:
                entry["carried_over_from"] = undecided_at[0]
            else:
                entry.pop("carried_over_from", None)

    def as_json(self, run_id: str, now: datetime, report: str, next_run: datetime) -> dict[str, object]:
        """queue.json: when the next weekly run is due, the open items in presentation order, then every closed item."""
        closed = sorted(
            (entry for entry in self.entries.values() if entry["status"] != OPEN),
            key=lambda entry: (str(entry.get("closed_at", "")), str(entry["id"])),
        )
        return {
            "exchange": exchange.EXCHANGE_VERSION,
            "updated_by_run": run_id,
            "updated_at": now.isoformat(),
            "run_report": report,
            "next_run": next_run.isoformat(),
            "paths": "Every path here is relative to the ledger/ directory that holds this file's folder.",
            "open": self.ordered(),
            "closed": closed,
        }
