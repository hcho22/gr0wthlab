"""Per-workflow run state: what each workflow has already handled, so the launcher enforces what the agent would
otherwise have to remember: never re-ask a decided item, carry over an undecided one, follow up at most once and
only after a non-reply, and leave nothing unaccounted for.

State is a convenience, never the record.
The Review Queue ledger and Mandu's decision records say what was decided and who was contacted; each run checks
the state against them, repairs any difference in their favor, and says so in the run report.
Entries hold identifiers, dates, counts, and SHA-256 hashes only: never a URL, a name, or any personal data; a Waitlist
entry is held by its random entry identifier, which is never an address or an encoding of one.
The files live in ledger/run-reports/state/, which only the launcher writes and the agent can only read.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from . import exchange
from .areas import Store, UnsafeFile, read_plain
from .waitlist import ENTRY_PATTERN, encodes_address

STATE_FORMAT = 1
STATE_DIR = "state"
REVIEW_QUEUE = "review-queue"
LISTENING = "listening"
OUTREACH = "outreach"
BETA_RECRUITING = "beta-recruiting"
WORKFLOWS = (REVIEW_QUEUE, LISTENING, OUTREACH, BETA_RECRUITING)
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
CLOSED_OUTCOMES = ("approved", "rejected", "superseded")


class StateError(ValueError):
    """A state file that does not hold what its workflow expects."""


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def thread_key(url: str) -> str:
    """A Listening thread's key: its normalized address, hashed, so the state never holds the address itself."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise StateError(f"a thread is identified by its http(s) address, not {url!r}")
    return digest(f"{parts.netloc.lower()}{parts.path.rstrip('/')}")


def target_key(identifier: str) -> str:
    """An outreach target's key: its identifier (never a name or address) normalized and hashed."""
    normalized = " ".join(identifier.split()).casefold()
    if not normalized:
        raise StateError("an outreach target needs an identifier")
    return digest(normalized)


def day(value: object, name: str) -> date:
    if not isinstance(value, str) or not exchange.valid_date(value):
        raise StateError(f"{name} must be a YYYY-MM-DD date")
    return date.fromisoformat(value)


def hash_value(value: object, name: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise StateError(f"{name} must be a SHA-256 hash")
    return value


def entries(data: Mapping, key: str) -> dict[str, Mapping]:
    value = data.get(key, {})
    if not isinstance(value, dict) or not all(isinstance(entry, dict) for entry in value.values()):
        raise StateError(f"{key} must map keys to records")
    return value


# Review Queue: decided items, and items left undecided at a sitting with that sitting's date, by identifier and
# fingerprint; and the Mandu records already reported as unusable, by fingerprint, so each is reported once unless
# Mandu must replace it.


@dataclass
class ReviewQueueState:
    handled: dict[str, dict[str, str]] = field(default_factory=dict)
    carried: dict[str, dict[str, str]] = field(default_factory=dict)
    reported: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Mapping) -> ReviewQueueState:
        state = cls()
        reported = data.get("reported", [])
        if not isinstance(reported, list):
            raise StateError("reported must list SHA-256 hashes")
        state.reported = sorted({hash_value(value, "a reported record") for value in reported})
        for identifier, entry in entries(data, "handled").items():
            if not exchange.ID_PATTERN.fullmatch(identifier):
                raise StateError(f"handled item {identifier!r} is not an item identifier")
            if entry.get("outcome") not in CLOSED_OUTCOMES:
                raise StateError(f"handled item {identifier} has no outcome")
            outcome = str(entry["outcome"])
            state.handled[identifier] = {"outcome": outcome, "hash": hash_value(entry.get("hash"), identifier)}
        for identifier, entry in entries(data, "carried").items():
            if not exchange.ID_PATTERN.fullmatch(identifier) or identifier in state.handled:
                raise StateError(f"carried item {identifier!r} is not an open item identifier")
            state.carried[identifier] = {
                "hash": hash_value(entry.get("hash"), identifier),
                "carried_over_from": day(entry.get("carried_over_from"), f"{identifier} carried_over_from").isoformat(),
            }
        return state

    def as_json(self) -> dict[str, object]:
        return {
            "handled": dict(sorted(self.handled.items())),
            "carried": dict(sorted(self.carried.items())),
            "reported": self.reported,
        }


def reconcile(
    previous: ReviewQueueState,
    ledger_entries: Mapping[str, Mapping[str, object]],
    hashes: Mapping[str, str],
) -> tuple[ReviewQueueState, list[str]]:
    """The Review Queue state as the ledger says it is now, and every way the previous state disagreed.

    The ledger wins every disagreement; an open item is carried over from the sitting the ledger marks it with.
    The records already reported stay as the run left them.
    """
    current = ReviewQueueState(reported=previous.reported)
    differences = []
    for identifier, entry in ledger_entries.items():
        status = str(entry["status"])
        fingerprint = hashes.get(identifier)
        if status != "open":
            if fingerprint:
                current.handled[identifier] = {"outcome": status, "hash": fingerprint}
            before = previous.handled.get(identifier)
            if before and before["outcome"] != status:
                differences.append(f"state had `{identifier}` {before['outcome']}; the Review Queue has it {status}")
        else:
            before = previous.handled.get(identifier)
            if before:
                differences.append(f"state had `{identifier}` {before['outcome']}; the Review Queue has it open")
            if entry.get("carried_over_from") and fingerprint:
                current.carried[identifier] = {
                    "hash": fingerprint,
                    "carried_over_from": str(entry["carried_over_from"]),
                }
        before_hash = (previous.handled.get(identifier) or previous.carried.get(identifier) or {}).get("hash")
        if before_hash and fingerprint and before_hash != fingerprint:
            differences.append(f"state had another fingerprint for `{identifier}`; the item file wins")
    for identifier in sorted(set(previous.handled) | set(previous.carried)):
        if identifier not in ledger_entries:
            differences.append(f"state named `{identifier}`, which the Review Queue does not hold; dropped")
    return current, differences


# Listening: threads already read, by hashed address.


@dataclass
class ListeningState:
    read: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Mapping) -> ListeningState:
        state = cls()
        for key, entry in entries(data, "read").items():
            hash_value(key, "a thread key")
            first = day(entry.get("first_read"), "first_read")
            last = day(entry.get("last_read"), "last_read")
            if last < first:
                raise StateError("last_read cannot come before first_read")
            state.read[key] = {"first_read": first.isoformat(), "last_read": last.isoformat()}
        return state

    def as_json(self) -> dict[str, object]:
        return {"read": dict(sorted(self.read.items()))}

    def seen(self, url: str) -> bool:
        return thread_key(url) in self.read

    def mark(self, url: str, on: date) -> bool:
        """Record a thread as read; True the first time, so a thread's quotes are taken once."""
        key = thread_key(url)
        entry = self.read.get(key)
        if entry:
            entry["last_read"] = max(entry["last_read"], on.isoformat())
            return False
        self.read[key] = {"first_read": on.isoformat(), "last_read": on.isoformat()}
        return True


# Outreach: who was contacted, by hashed identifier, and when a single follow-up may go.


@dataclass
class OutreachState:
    targets: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Mapping) -> OutreachState:
        state = cls()
        for key, entry in entries(data, "targets").items():
            hash_value(key, "a target key")
            contacted = day(entry.get("contacted_on"), "contacted_on")
            after = day(entry.get("follow_up_after"), "follow_up_after")
            follow_ups = entry.get("follow_ups")
            if after < contacted:
                raise StateError("follow_up_after cannot come before contacted_on")
            if follow_ups not in (0, 1) or isinstance(follow_ups, bool):
                raise StateError("follow_ups must be 0 or 1; there is never a second follow-up")
            if not isinstance(entry.get("replied"), bool):
                raise StateError("replied must be true or false")
            state.targets[key] = {
                "contacted_on": contacted.isoformat(),
                "follow_up_after": after.isoformat(),
                "follow_ups": follow_ups,
                "replied": entry["replied"],
            }
        return state

    def as_json(self) -> dict[str, object]:
        return {"targets": dict(sorted(self.targets.items()))}

    def may_contact(self, identifier: str) -> tuple[bool, str]:
        if target_key(identifier) in self.targets:
            return False, "already contacted; only a follow-up can follow"
        return True, "never contacted"

    def may_follow_up(self, identifier: str, today: date) -> tuple[bool, str]:
        entry = self.targets.get(target_key(identifier))
        if entry is None:
            return False, "never contacted"
        if entry["replied"]:
            return False, "replied; a follow-up goes only to a non-reply"
        if entry["follow_ups"]:
            return False, "already followed up once; no further contact"
        if today < date.fromisoformat(str(entry["follow_up_after"])):
            return False, f"waiting until {entry['follow_up_after']}"
        return True, "no reply after the waiting period"

    def record_contact(self, identifier: str, on: date, wait_days: int) -> None:
        allowed, reason = self.may_contact(identifier)
        if not allowed:
            raise StateError(reason)
        self.targets[target_key(identifier)] = {
            "contacted_on": on.isoformat(),
            "follow_up_after": (on + timedelta(days=wait_days)).isoformat(),
            "follow_ups": 0,
            "replied": False,
        }

    def record_reply(self, identifier: str) -> None:
        entry = self.targets.get(target_key(identifier))
        if entry is None:
            raise StateError("a reply from someone never contacted")
        entry["replied"] = True

    def record_follow_up(self, identifier: str, on: date) -> None:
        allowed, reason = self.may_follow_up(identifier, on)
        if not allowed:
            raise StateError(reason)
        self.targets[target_key(identifier)]["follow_ups"] = 1


# Beta Cohort recruiting: each Waitlist entry an invitation batch holds, by entry identifier, with the batch item and
# whether the Founder approved it (invited) or has yet to decide (offered); an invited entry is never offered again.

INVITED = "invited"
OFFERED = "offered"


@dataclass
class BetaRecruitingState:
    entries: dict[str, dict[str, str]] = field(default_factory=dict)
    build: str = ""  # the fingerprint of the Beta Build record last read, so a changed record is reported as changed

    @classmethod
    def from_json(cls, data: Mapping) -> BetaRecruitingState:
        state = cls()
        build = data.get("build", "")
        state.build = hash_value(build, "the Beta Build record") if build else ""
        for identifier, entry in entries(data, "entries").items():
            if not ENTRY_PATTERN.fullmatch(identifier) or encodes_address(identifier):
                raise StateError("an entry is not a Waitlist entry identifier")
            if entry.get("status") not in (INVITED, OFFERED):
                raise StateError(f"entry {identifier} is neither {INVITED} nor {OFFERED}")
            item = entry.get("item")
            if not isinstance(item, str) or not exchange.ID_PATTERN.fullmatch(item):
                raise StateError(f"entry {identifier} names no batch item")
            state.entries[identifier] = {"status": str(entry["status"]), "item": item}
        return state

    def as_json(self) -> dict[str, object]:
        return {"entries": dict(sorted(self.entries.items())), "build": self.build}

    @property
    def unused(self) -> bool:
        """Nothing to keep yet: recruiting never started, so no file is written for it."""
        return not self.entries and not self.build


# The files.


@dataclass
class States:
    review_queue: ReviewQueueState = field(default_factory=ReviewQueueState)
    listening: ListeningState = field(default_factory=ListeningState)
    outreach: OutreachState = field(default_factory=OutreachState)
    beta_recruiting: BetaRecruitingState = field(default_factory=BetaRecruitingState)

    def by_workflow(self) -> dict[str, ReviewQueueState | ListeningState | OutreachState | BetaRecruitingState]:
        return {
            REVIEW_QUEUE: self.review_queue,
            LISTENING: self.listening,
            OUTREACH: self.outreach,
            BETA_RECRUITING: self.beta_recruiting,
        }


PARSERS = {
    REVIEW_QUEUE: ReviewQueueState,
    LISTENING: ListeningState,
    OUTREACH: OutreachState,
    BETA_RECRUITING: BetaRecruitingState,
}


def state_path(store: Store, workflow: str) -> Path:
    return store.path("run-reports", STATE_DIR, f"{workflow}.json")


def load(store: Store) -> tuple[States, list[tuple[str, Path, str]]]:
    """Every workflow's state; a missing file is an empty state, and an invalid one is returned with its reason."""
    states = States()
    invalid = []
    for workflow, parser in PARSERS.items():
        path = state_path(store, workflow)
        if not path.exists() and not path.is_symlink():
            continue
        try:
            data = json.loads(read_plain(path).decode("utf-8"))
            if not isinstance(data, dict):
                raise StateError("it is not a JSON object")
            if data.get("format") != STATE_FORMAT or data.get("workflow") != workflow:
                raise StateError(f"it is not a format {STATE_FORMAT} {workflow} state")
            setattr(states, workflow.replace("-", "_"), parser.from_json(data))
        except (OSError, ValueError, UnsafeFile) as error:
            invalid.append((workflow, path, str(error)))
    return states, invalid


def save(store: Store, states: States, run_id: str, at: str) -> None:
    """Write every workflow's state; one that has never held anything, as Beta Cohort recruiting before the Founder's
    gate, writes no file until it does."""
    for workflow, state in states.by_workflow().items():
        if getattr(state, "unused", False) and not state_path(store, workflow).exists():
            continue
        record = {"format": STATE_FORMAT, "workflow": workflow, "updated_by_run": run_id, "updated_at": at}
        record.update(state.as_json())
        store.write_json(state_path(store, workflow), record)


def queued_item(root: Path, entry: Mapping[str, object], products: Sequence[str]) -> exchange.Item:
    """A queued item, read from its item file; a file that cannot be read as one raises."""
    relative = Path(str(entry["file"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise StateError(f"its path leaves {root.name}/")
    check = exchange.check_item(read_plain(root / relative).decode("utf-8"), products, published=True)
    if check.item is None:
        raise StateError("; ".join(check.problems))
    return check.item


def item_hashes(
    root: Path,
    ledger_entries: Mapping[str, Mapping[str, object]],
    products: Sequence[str],
    previous: ReviewQueueState,
) -> tuple[dict[str, str], list[str]]:
    """Each queued item's fingerprint, read from its item file; the previous state fills in an unreadable file."""
    hashes, problems = {}, []
    for identifier, entry in ledger_entries.items():
        try:
            hashes[identifier] = exchange.item_hash(queued_item(root, entry, products))
        except (OSError, ValueError, UnsafeFile) as error:
            known = (previous.handled.get(identifier) or previous.carried.get(identifier) or {}).get("hash")
            if known:
                hashes[identifier] = str(known)
            problems.append(f"`{entry['file']}` could not be read for its fingerprint ({error})")
    return hashes, problems


# The one-line account every run report carries.


@dataclass(frozen=True)
class Tally:
    workflow: str
    checked: int
    acted: int
    note: str
    incomplete: str = ""  # why this workflow's work is incomplete this run, if it is

    def account(self) -> str:
        return self.note + (f"; incomplete: {self.incomplete}" if self.incomplete else "")

    def line(self) -> str:
        return f"checked={self.checked} acted={self.acted} note={self.account()}"


def run_tally(tallies: Sequence[Tally]) -> Tally:
    """The run's own line: everything checked and acted on, and what acted or is incomplete, or that nothing needed
    to, so a run that fell short is never a quiet one."""
    named = [f"{tally.workflow} {tally.account()}" for tally in tallies if tally.acted or tally.incomplete]
    note = "; ".join(named) if named else "nothing new needed action"
    return Tally("run", sum(t.checked for t in tallies), sum(t.acted for t in tallies), note)
