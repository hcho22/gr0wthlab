"""The Review Queue: every item ever queued, which are still open, and the order the sitting page presents them in.

The ledger lives in ledger/review-queue/queue.json, beside the published items; only the launcher writes there, and
the agent can only read it. The agent proposes items in workspace/review-queue/incoming/, which the launcher checks.
A file it sets aside from there is removed and copied nowhere: the run's set-aside record keeps its name and why,
and the reasons describe what is wrong without repeating the file's text.
An item is queued once, under an identifier that never changes, and is closed by the Founder's decision (approved
or rejected) or by a newer item that supersedes it; a closed item never returns to the open list. A decision the
Founder took on an item a newer one had already superseded is kept on that item, which stays superseded.
An open item is carried over once the Founder has left it undecided at a sitting.
A read that could not be made never closes or supersedes one: stands, below, is where each place that would have
taken an open item back, or asked it again, weighs it.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
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
# How a file in incoming/ that passed every check and could not be written to the queue is set aside.
NOT_QUEUED = "could not be queued"
# The kinds the launcher renders only from a Draft that passed its checks, each with the folders its Drafts are
# written in. No file of these kinds is taken from incoming/, and no item written there supersedes one.
FROM_DRAFT = {
    "post": "drafts/posts/",
    "message": "drafts/messages/ or drafts/beta-recruiting/",
    "weekly-read-decision": "weekly-reads/, the Weekly Read memo,",
}


class QueueError(Exception):
    """The ledger cannot be read, so the queue is left untouched this run."""


@dataclass(frozen=True)
class DecisionOutcome:
    """What became of one of the Founder's decision records."""

    decision: exchange.Decision
    status: str  # taken, already-taken, conflict, unknown-item
    entry: Mapping[str, object] | None


@dataclass(frozen=True)
class SetAside:
    """A file the launcher refused to queue from incoming/: all that is kept of it."""

    name: str
    problems: tuple[str, ...]


@dataclass(frozen=True)
class Stands:
    """An open item a run left exactly as it was, since a read its standing rests on could not be made."""

    item: str
    unread: tuple[str, ...]  # each source that could not be read, with the reason

    @property
    def detail(self) -> str:
        return f"not checked again, since {'; '.join(self.unread)}; the open item stands"


def stands(current: Mapping[str, object] | None, unread: Sequence[str]) -> Stands | None:
    """The one place a read that could not be made is weighed against an open item, wherever that read would
    otherwise have taken the item back or asked it again.

    Only what a record the launcher could read says ever withdraws, closes, or supersedes an open item. current is
    the open item a workflow is about to judge, and unread each source that judgment needs and that could not be
    read this run: a file that is missing where it must exist, unreadable, or not in its format, or a git read that
    failed. With both, the item stands under its identifier, not checked again, whatever else the check found, and
    the workflow reports each unread source as its gap; with either missing, the workflow goes on to its own
    decision, which then rests on readable records alone.

    The places that come here judge an open item: the check of an open post, message, reply, or recruiting item
    against its Draft and what that check reads; an open invitation or Waitlist ask while a report of the Founder's
    is unread; an open follow-up whose record of the first message is unread; the open filming plan while the kit
    is unread; a Dispatch request's open item whose item file is unread; and an item in incoming/ that supersedes
    an open item whose item file is unread. A step that did not run at all because its source could not be read
    judges no item and does not come here: recruiting without a usable Waitlist view or Beta Build record, a
    Dispatch request whose reviewed text is unread, post Drafts without the calendar, outreach without the channel
    plan or the kit, replies without the kit, and the video of a day whose copy is approved and whose Draft is
    unread. There the output always reads incomplete in the run report with the real reason, and no item of the
    step is touched or listed. The run's notice names the source only where its read failed as a source, where it was
    read and could not be used, as a calendar or channel plan that could not be parsed or decoded, or was recorded as
    a launcher problem, and in the line that says no video was cut for an approved day. While the window's filming
    plan is open, that plan also stands on a calendar that fails this way, as on any kit file, so the notice's list
    of open items not checked again names the plan with the kit file as its reason.
    """
    if current is None or not unread:
        return None
    return Stands(str(current["id"]), tuple(dict.fromkeys(unread)))


def may_repeat(item: exchange.Item, entry: Mapping[str, object]) -> bool:
    """Whether an item may ask the same as a queued one whose item file could not be read. The ledger still holds
    that one's kind and ask, so only its Draft or proposal is unknown: the two share a fingerprint if it is this
    item's, and cannot share one otherwise."""
    alike = exchange.Item({"kind": str(entry["kind"])}, str(entry["ask"]), item.body, "", "")
    return exchange.item_hash(alike) == exchange.item_hash(item)


def declaration_problem(item: exchange.Item, kept: Collection[str]) -> str | None:
    """Why a package-change proposal's declaration keeps it off the queue, if it does. One that declares it adds or
    changes an Angle or Hook needs sourced pain: an Evidence line that names, exactly, the record of a Listening
    quote the launcher keeps. One that declares it does not is held to nothing more, whatever it touches or says:
    the declaration is on the item, and the Founder is the check on a wrong one."""
    if item.fields["new_angle"] == "yes" and exchange.references(item.evidence).isdisjoint(kept):
        return (
            "it declares new_angle: yes, and a proposal that adds or changes an Angle or Hook, any Hook, signal, or"
            " kill criterion included (FR-7), is queued only with sourced pain: no record its Evidence names is a"
            " Listening quote the launcher keeps. Name one exactly in an Evidence line, as"
            " `evidence/listening/quotes/<document id>.json`, or propose it in review-queue/angles/ with this run's"
            " quotes under ## Sourced pain"
        )
    return None


def record_set_aside(store: Store, set_aside: Sequence[SetAside], run_id: str) -> list[SetAside]:
    """Write the run's set-aside record, review-queue/set-aside/<run>.json: each file's name and why. A record that
    cannot be written is said in each file's reasons."""
    if not set_aside:
        return []
    items = [{"name": item.name, "reasons": list(item.problems)} for item in set_aside]
    try:
        store.write_json(store.path(REVIEW_QUEUE, SET_ASIDE, f"{run_id}.json"), {"run": run_id, "items": items})
    except (OSError, ConfigError) as error:
        problem = f"the set-aside record could not be written ({error})"
        return [SetAside(item.name, (*item.problems, problem)) for item in set_aside]
    return list(set_aside)


def slug_of(name: str) -> str:
    return name[: -len(".md")] if name.endswith(".md") else ""


class Ledger:
    def __init__(self, entries: Sequence[Mapping[str, object]] = ()):
        self.entries: dict[str, dict[str, object]] = {str(entry["id"]): dict(entry) for entry in entries}
        self.stood: list[Stands] = []  # each open item the take-in left as it was on a read that could not be made
        self.unsettled: list[str] = []  # each item file, unread, that an item set aside from incoming/ may repeat

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
        self, decisions: Sequence[exchange.Decision], run_id: str, now: datetime
    ) -> list[DecisionOutcome]:
        """Close each open item the Founder decided; a decided item is never reopened or re-asked."""
        outcomes = []
        for decision in sorted(decisions, key=lambda decision: decision.item):
            entry = self.entries.get(decision.item)
            decided = APPROVED if decision.decision == exchange.APPROVE else REJECTED
            if entry is None:
                status = "unknown-item"
            elif entry["status"] == OPEN:
                self.close(entry, decided, run_id, now, decided_at=decision.decided_at)
                status = "taken"
            elif entry["status"] == SUPERSEDED and "decided_at" not in entry:
                entry.update(decided=decided, decided_at=decision.decided_at)
                status = "taken"
            elif entry.get("decided", entry["status"]) == decided and entry.get("decided_at") == decision.decided_at:
                status = "already-taken"
            else:
                status = "conflict"
            outcomes.append(DecisionOutcome(decision, status, entry))
        return outcomes

    def decided_replaced(self, entry: Mapping[str, object]) -> list[dict[str, object]]:
        """Each item this one replaced, directly or through the items it replaced, that the Founder then decided."""
        decided, seen = [], set()
        target = entry.get("supersedes")
        while target in self.entries and target not in seen:
            seen.add(target)
            earlier = self.entries[str(target)]
            if earlier.get("decided"):
                decided.append(earlier)
            target = earlier.get("supersedes")
        return decided

    def next_id(self, day: date, slug: str) -> str:
        base = exchange.item_id(day, slug)[: exchange.MAX_ID]
        candidate, number = base, 2
        while candidate in self.entries:
            candidate = f"{base}-{number}"
            number += 1
        return candidate

    def publish(
        self,
        store: Store,
        item: exchange.Item,
        slug: str,
        run_id: str,
        now: datetime,
        extra: Mapping[str, object] | None = None,
        origin: str | None = None,
    ) -> str:
        """Queue an item under a new identifier, writing its canonical text to review-queue/items/<id>.md; extra holds
        the launcher's own fields for the ledger entry, such as a post's Draft.

        origin marks an item the launcher files from reviewed text, such as a Dispatch request, so later runs find it.
        """
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
        for key in ("product", "new_angle", "slot", "asset", "supersedes"):
            if item.fields.get(key):
                entry[key] = item.fields[key]
        for key in ("window", "day", "read"):
            if item.fields.get(key):
                entry[key] = int(item.fields[key])
        entry.update(extra or {})
        if origin:
            entry["origin"] = origin
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
        kept: Collection[str] = (),
        unread: Mapping[str, str] | None = None,
    ) -> tuple[list[str], list[SetAside]]:
        """Queue every valid item the agent wrote to incoming/; set every other file aside with its problems.

        seen maps each queued item's fingerprint to its identifier; an item that asks the same thing as one already
        open or decided is set aside, so nothing decided is ever asked again under another name. kept holds the
        record of each Listening quote the launcher keeps, as a path in ledger/. unread holds each queued item whose
        fingerprint is not in seen, since its item file could not be read, with the reason; unsettled comes to hold
        the reason for each of those an item here was set aside as a possible repeat of.
        """
        seen = {} if seen is None else seen
        incoming = areas.path("review_queue", INCOMING)
        areas.ensure_folder(incoming)
        published: list[str] = []
        set_aside: list[SetAside] = []
        superseding: list[tuple[str, str]] = []
        for path in list(areas.files(incoming)):
            name = areas.relative(path)[len("review-queue/incoming/") :]
            item, problems = self.check_incoming(path, name, products, seen, kept, unread or {})
            if item is None:
                set_aside.append(self.set_aside(areas, path, name, problems))
                continue
            try:
                identifier = self.publish(store, item, slug_of(name), run_id, now)
            except (OSError, ConfigError) as error:
                problem = f"{NOT_QUEUED} ({error})"
                set_aside.append(self.set_aside(areas, path, name, [problem]))
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
        return published, record_set_aside(store, set_aside, run_id)

    def check_incoming(
        self,
        path: Path,
        name: str,
        products: Sequence[str],
        seen: Mapping[str, str],
        kept: Collection[str] = (),
        unread: Mapping[str, str] | None = None,
    ) -> tuple[exchange.Item | None, list[str]]:
        """Every rule a file in incoming/ must pass to be queued, for the launcher and the agent's own check alike:
        its name, the item format, a kind the launcher does not render from a Draft, sourced pain behind a proposal
        that declares it adds or changes an Angle or Hook, an open item to supersede that the launcher neither filed
        from reviewed text nor queued from a Draft, and no repeat of an item queued or decided.

        name is the file's path inside incoming/; seen maps each queued item's fingerprint to its identifier, and
        kept holds the record of each Listening quote the launcher keeps. unread holds each queued item whose item
        file could not be read, so that seen lacks its fingerprint: an open one of them stands, and no item that
        supersedes it takes its place in this run, and nothing shows an item with the kind and ask of one of them,
        open or decided, is not a repeat of it, so that item is not queued. The item comes back only when there is
        no problem.
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
        if item.kind in FROM_DRAFT:
            problems.append(
                f"a {item.kind} is queued only from its Draft in {FROM_DRAFT[item.kind]}, after the launcher's checks;"
                " never write one here"
            )
        if item.kind == "filming-plan":
            problems.append("the filming plan is filed only by the launcher, from the kit; never write one here")
        problem = declaration_problem(item, kept) if item.kind == "package-change-proposal" else None
        if problem:
            problems.append(problem)
        target = item.fields.get("supersedes")
        replaced = self.entries.get(target, {}) if target else {}
        if target and not replaced:
            problems.append("supersedes names no item in the Review Queue; name an open item by its identifier")
        elif target and replaced.get("status") != OPEN:
            problems.append(f"supersedes {target}, which is not an open item")
        elif replaced.get("origin"):
            problems.append(
                f"supersedes {target}, which the launcher filed from reviewed text; only a reviewed change to that"
                " text replaces it"
            )
        elif replaced.get("instructions"):
            problems.append(
                f"supersedes {target}, the notice of a change to the Instructions, which only the Founder's decision"
                " closes"
            )
        elif replaced.get("kind") in FROM_DRAFT:
            kind = replaced["kind"]
            problems.append(
                f"supersedes {target}, a {kind} the launcher queued from its Draft; only a change to that Draft in"
                f" {FROM_DRAFT[kind]} replaces it"
            )
        else:
            lost = (unread or {}).get(target or "")
            stood = stands(replaced or None, [lost] if lost else [])
            if stood:
                if stood not in self.stood:
                    self.stood.append(stood)
                problems.append(
                    f"supersedes {target}: {lost}, so the open item stands and nothing replaces it in this run"
                )
        fingerprint = exchange.item_hash(item)
        if fingerprint in seen:
            earlier = self.entries.get(seen[fingerprint])
            status = earlier["status"] if earlier else "also in incoming/"
            problems.append(f"asks the same as {seen[fingerprint]}, which is {status}")
        else:
            for identifier, lost in (unread or {}).items():
                earlier = self.entries[identifier]
                # The item this one supersedes is weighed above, on its own.
                if identifier != target and may_repeat(item, earlier):
                    self.unsettled.append(lost)
                    problems.append(
                        f"has the kind and ask of {identifier}, which is {earlier['status']}: {lost}, so nothing shows"
                        " this item asks anything else"
                    )
        return (None if problems else item), problems

    def set_aside(self, areas: Areas, path: Path, name: str, problems: Sequence[str]) -> SetAside:
        """Remove a file from incoming/, keeping its name and the reasons, and nothing of its text."""
        areas.remove(path)
        return SetAside(name, tuple(problems))

    def ordered(self) -> list[dict[str, object]]:
        """Open items in presentation order: posts by nearest slot, then posts with no slot yet by window and day, then
        each other kind in turn, oldest first."""
        kinds = list(exchange.KINDS)

        def key(entry: Mapping[str, object]) -> tuple:
            post = entry["kind"] == "post"
            slot = exchange.parse_datetime(str(entry.get("slot", ""))) if post else None
            return (
                kinds.index(str(entry["kind"])),
                slot.timestamp() if slot else float("inf") if post else 0.0,
                int(entry.get("window") or 0),
                int(entry.get("day") or 0),
                str(entry["published_at"]),
                str(entry["id"]),
            )

        return sorted(self.open_entries(), key=key)

    def mark_carried_over(self, sittings: Mapping[str, str]) -> None:
        """Mark each open item the Founder left undecided at a sitting, with the date of the first such sitting.

        sittings maps each sitting's date to the run that first took in a record of it: its sitting record, or a
        decision given at it. An item was open at a sitting dated no earlier than the day it was queued whose first
        record reached gr0wthlab only after the run that queued it; an item queued after a sitting, even on the same
        day, is not carried over from it.
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

    def as_json(
        self, run_id: str, now: datetime, report: str, next_run: datetime, results: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        """queue.json: when the next weekly run is due, what the Weekly Read due asks the Founder to give on the
        sitting page, if one is due, the open items in presentation order, then every closed item."""
        closed = sorted(
            (entry for entry in self.entries.values() if entry["status"] != OPEN),
            key=lambda entry: (str(entry.get("closed_at", "")), str(entry["id"])),
        )
        found: dict[str, object] = {
            "exchange": exchange.EXCHANGE_VERSION,
            "updated_by_run": run_id,
            "updated_at": now.isoformat(),
            "run_report": report,
            "next_run": next_run.isoformat(),
            "paths": "Every path here is relative to the ledger/ directory that holds this file's folder.",
        }
        if results:
            found["results"] = dict(results)
        found.update(open=self.ordered(), closed=closed)
        return found
