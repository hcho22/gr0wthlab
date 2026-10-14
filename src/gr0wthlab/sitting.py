"""A sitting: what the Founder is shown, one thing at a time, and what each of the Founder's acts on the page writes.

This is the logic of the Founder-side command, `gr0wthlab sitting`, with no HTTP and no HTML in it (serve.py, page.py).
It reads the Review Queue as the last run wrote it and the Founder's records, and it is the only code that makes a
founder.Writer. Each method that writes is one explicit act of the Founder's:

- decide and take_back: a decision on one open item, which can be changed or taken back until a run has taken it in;
- report_counts: the three Beta Cohort counts, where a count left blank is recorded as not reported, never as zero;
- record_sitting: how long the sitting took, which the page measured and the Founder can correct; it is the one
  way to end a sitting from the page, which then stops;
- record_sent: an approved message sent, a reply received, the wait before the one follow-up;
- record_beta_build and set_recruiting: a Beta Build approved, recruiting stopped or reopened.

What the Founder gave is what is written. A record is built only from the fields the Founder filled and the Mac's
clock, every limit is checked at entry and refused with a plain reason (Refused), and the record then goes through the
parser a run reads it with (exchange.py), so the page never writes a record a run cannot use. After a write the record
is read back from its file, and that is what the page shows as saved.

There is no model, no agent, and no network here. Nothing an item, a run report, or a record says is ever acted on: it
is text to show.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import exchange, founder
from .areas import UnsafeFile, read_plain
from .boundary import FOUNDER, LEDGER, PRODUCT_REGISTRY, ConfigError, canonical, load_json
from .messages import CREATOR
from .queue import APPROVED, OPEN, QUEUE_FILE, REVIEW_QUEUE
from .state import queued_item
from .waitlist import looks_like_address

# The lock one sitting page holds while it serves, beside the run lock in ledger/; never committed.
SERVING_LOCK = "sitting.lock"
ASSETS = "assets"
MAX_MINUTES = 600
ONE_LINE = "One line, and nothing about a person."
NO_PERSON = (
    "Every line you type is kept in a record: one line of at most 300 characters, with no email address, no name, and"
    " nothing else about a person. A person is only ever a Waitlist entry identifier."
)
HOLDS_ADDRESS = (
    "it holds something that looks like an email address; no record may hold an address or anything else about a person"
)
START, ITEM, COUNTS, END = "start", "item", "counts", "end"


class Refused(Exception):
    """An act of the Founder's that wrote nothing, with each reason in plain words."""

    def __init__(self, reasons: Sequence[str]):
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


@dataclass(frozen=True)
class Saved:
    """A record as it was read back from its file after it was written."""

    kind: str
    stem: str
    record: Mapping[str, object]

    @property
    def path(self) -> str:
        """The file's path under ledger/."""
        return f"{FOUNDER}/{self.kind}/{self.stem}.json"


@dataclass(frozen=True)
class Video:
    """A post's finished video, as the page may play it: the file, or why it cannot be shown."""

    path: Path | None
    problem: str = ""


@dataclass
class Entry:
    """One open Review Queue item as the page shows it."""

    entry: Mapping[str, object]
    item: exchange.Item | None = None
    problem: str = ""  # why its item file cannot be shown, when it cannot
    decision: exchange.Decision | None = None  # the Founder's record of a decision, when it can be used
    record_problem: str = ""  # why the record in its place cannot be used, when one cannot
    taken_in: bool = False  # a run has taken the decision in, so it can no longer be changed
    video: Video | None = None

    @property
    def id(self) -> str:
        return str(self.entry["id"])

    @property
    def kind(self) -> str:
        return str(self.entry["kind"])

    @property
    def decided(self) -> bool:
        return self.decision is not None

    def may_approve(self) -> str:
        """Why this item cannot be approved, or "" when it can."""
        if self.item is None:
            return f"this item's file cannot be shown ({self.problem}), so it cannot be decided"
        if self.video is not None and self.video.problem:
            return f"its video cannot be shown ({self.video.problem}), so the video and its copy cannot be approved"
        return ""


@dataclass
class Message:
    """An approved message, and what the Founder's outreach record says of it."""

    entry: Mapping[str, object]
    record: exchange.Outreach | None = None
    record_problem: str = ""

    @property
    def id(self) -> str:
        return str(self.entry["id"])

    @property
    def followed_up(self) -> bool:
        """Whether a follow-up can come after this message: only a creator's first message has one, so only its
        record has a wait to set."""
        about = self.entry.get("message")
        return isinstance(about, Mapping) and about.get("purpose") == CREATOR


@dataclass
class Recruiting:
    """A Product whose Beta Cohort can be recruited, and what the Founder's records say of it."""

    product: str
    build: exchange.BetaBuild | None = None
    build_problem: str = ""  # why the Beta Build record in place cannot be used, when one cannot
    today: exchange.BetaReport | None = None  # the counts already given on the sitting's date
    latest: exchange.BetaReport | None = None

    @property
    def open(self) -> bool:
        return self.build is not None and self.build.recruiting == exchange.RECRUITING_OPEN


@dataclass
class View:
    """Everything one page of the sitting is drawn from, read fresh for each request."""

    queue_problem: str = ""  # why there is no Review Queue to show
    run: str = ""
    updated_at: str = ""
    next_run: str = ""
    overdue: bool = False  # the weekly run due has not finished
    changed: bool = False  # a run wrote the Review Queue since this sitting began
    report: str = ""  # the run report's path under ledger/
    summary: list[str] = field(default_factory=list)
    summary_problem: str = ""
    entries: list[Entry] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    recruiting: list[Recruiting] = field(default_factory=list)
    sitting: exchange.Sitting | None = None
    stray: list[tuple[str, str]] = field(default_factory=list)  # each record file that is no record, with why

    def find(self, item: str) -> Entry | None:
        return next((entry for entry in self.entries if entry.id == item), None)

    def product(self, name: str) -> Recruiting | None:
        return next((found for found in self.recruiting if found.product == name), None)

    def steps(self) -> list[tuple[str, str]]:
        """The walk, in order: the start, each open item as the Review Queue lists them, the counts of each Product
        whose Beta Cohort is being recruited, and the end."""
        steps = [(START, "")] + [(ITEM, entry.id) for entry in self.entries]
        steps += [(COUNTS, found.product) for found in self.recruiting if found.open]
        return steps + [(END, "")]

    def after(self, step: tuple[str, str]) -> tuple[str, str]:
        steps = self.steps()
        index = steps.index(step) if step in steps else 0
        return steps[min(index + 1, len(steps) - 1)]

    def before(self, step: tuple[str, str]) -> tuple[str, str]:
        steps = self.steps()
        index = steps.index(step) if step in steps else 0
        return steps[max(index - 1, 0)]


def one_line(value: str, name: str, required: bool, reasons: list[str]) -> str | None:
    """A line the Founder typed, without the spaces around it, or None when it was left blank."""
    text = value.strip()
    if "\n" in text or "\r" in text:
        reasons.append(f"{name} must be one line")
        return None
    if not text:
        if required:
            reasons.append(f"{name} is needed, in one line")
        return None
    if len(text) > exchange.MAX_LINE:
        reasons.append(f"{name} is {len(text)} characters long; one line holds at most {exchange.MAX_LINE}")
    if looks_like_address(text):
        reasons.append(f"{name} was refused: {HOLDS_ADDRESS}")
    return text


def a_day(value: str, name: str, today: date, required: bool, reasons: list[str]) -> str | None:
    """A date the Founder gave as YYYY-MM-DD, never one still ahead; None when it was left blank."""
    text = value.strip()
    if not text:
        if required:
            reasons.append(f"{name} is needed, as a date such as {today.isoformat()}")
        return None
    if not exchange.valid_date(text):
        reasons.append(f"{name} must be a real date written as YYYY-MM-DD, such as {today.isoformat()}")
        return None
    if text > today.isoformat():
        reasons.append(f"{name} is {text}, which has not come yet")
        return None
    return text


def whole_number(value: str, name: str, least: int, most: int | None, reasons: list[str]) -> int | None:
    """A whole number the Founder typed, or None when the field was left blank: a blank is never a zero."""
    text = value.strip()
    if not text:
        return None
    if not text.isascii() or not text.isdigit() or len(text) > 9:
        reasons.append(f"{name} must be a whole number, written in digits")
        return None
    number = int(text)
    if number < least or (most is not None and number > most):
        span = f"from {least} to {most}" if most is not None else f"from {least}"
        reasons.append(f"{name} must be a whole number {span}")
        return None
    return number


class Sitting:
    """One sitting in one checkout, from the first page shown to the last record written."""

    def __init__(
        self,
        repo_root: Path,
        clock: Callable[[], datetime] | None = None,
        elapsed: Callable[[], float] = time.monotonic,
    ):
        self.ledger = canonical(repo_root) / LEDGER
        registry = load_json(repo_root / PRODUCT_REGISTRY)
        self.products = [str(product["name"]) for product in registry.get("products", [])]
        self.recruits = [
            str(product["name"])
            for product in registry.get("products", [])
            if product.get("status") == "active" and product.get("beta_recruiting")
        ]
        self.writer = founder.Writer(self.ledger)
        self.clock = clock or (lambda: datetime.now().astimezone())
        self.elapsed = elapsed
        self.began: float | None = None  # when the first page was shown, on the clock that only runs forward
        self.earlier = 0  # the minutes the date's sitting record held then, from an earlier sitting of the same date
        self.day = self.now().date().isoformat()  # the sitting's date
        self.first_run: str | None = None  # the run whose Review Queue the sitting began with
        self.hashes: dict[tuple[str, int, int], str] = {}

    def now(self) -> datetime:
        return self.clock().astimezone().replace(microsecond=0)

    def today(self) -> date:
        return self.now().date()

    def begin(self) -> None:
        """Start the sitting's clock, the first time a page is shown, and note the minutes an earlier sitting of the
        same date recorded. They are read here, once, before this sitting can write that record itself, so the
        minutes this sitting measures are only ever added to another sitting's and never to its own."""
        if self.began is None:
            self.began = self.elapsed()
            before = self.records(founder.SITTINGS, exchange.parse_sitting, View()).get(self.day, (None, ""))[0]
            self.earlier = before.minutes if before else 0

    def minutes(self) -> int:
        """How long the sitting has taken so far, in whole minutes, as the page measured it."""
        if self.began is None:
            return 1
        return max(1, min(MAX_MINUTES, math.ceil((self.elapsed() - self.began) / 60)))

    # Reading.

    def records(self, kind: str, parser, view: View) -> dict[str, tuple[object | None, str]]:
        """Each record file of one kind by its name without .json: the record when it can be used, else why it cannot.
        A file that is no record at all goes to view.stray."""
        found, others, failure = founder.read(self.ledger, kind)
        if failure:
            view.stray.append((f"{FOUNDER}/{kind}/", failure))
        view.stray += [(founder.shown(kind, name), why) for name, why in others]
        records: dict[str, tuple[object | None, str]] = {}
        for name, _, data in found:
            record, problems = founder.parse(name, data, parser)
            records[name[: -len(".json")]] = (record, "; ".join(problems))
        return records

    def video(self, entry: Mapping[str, object]) -> Video | None:
        """The finished video a post shows, checked against the fingerprint the Review Queue holds for it, so the
        file the Founder watches is the file the run measured."""
        asset = entry.get("asset")
        if entry.get("kind") != "post" or not asset:
            return None
        relative = str(asset)
        if not exchange.ASSET_PATTERN.fullmatch(relative):
            return Video(None, "the Review Queue names no file of the finished videos for it")
        path = self.ledger / relative
        try:
            if os.path.realpath(str(path)) != str(path):
                return Video(None, "its file is not a plain file in the finished videos")
            info = os.lstat(str(path))
            key = (relative, info.st_size, info.st_mtime_ns)
            if key not in self.hashes:
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(block)
                self.hashes[key] = digest.hexdigest()
        except OSError as error:
            return Video(None, f"`{relative}` could not be read: {error.strerror or error}")
        if self.hashes[key] != entry.get("asset_sha256"):
            return Video(None, f"`{relative}` is not the file this post was queued with")
        return Video(path)

    def look(self) -> View:
        """Read everything a page is drawn from: the Review Queue, each open item, and the Founder's records."""
        view = View()
        decisions = self.records(founder.DECISIONS, exchange.parse_decision, view)
        sittings = self.records(founder.SITTINGS, exchange.parse_sitting, view)
        view.sitting = sittings.get(self.day, (None, ""))[0]
        outreach = self.records(founder.OUTREACH, exchange.parse_outreach, view)
        builds = self.records(founder.BETA_BUILDS, exchange.parse_beta_build, view)
        reports = self.records(founder.BETA_REPORTS, exchange.parse_beta_report, view)
        for product in self.recruits:
            build, problem = builds.get(product, (None, ""))
            mine = sorted(
                (report for report, _ in reports.values() if report is not None and report.product == product),
                key=lambda report: report.day,
            )
            today = next((report for report in mine if report.day == self.day), None)
            view.recruiting.append(Recruiting(product, build, problem, today, mine[-1] if mine else None))

        path = self.ledger / REVIEW_QUEUE / QUEUE_FILE
        if not os.path.lexists(str(path)):
            view.queue_problem = "no run has written a Review Queue in this checkout yet"
            return view
        try:
            queue = json.loads(read_plain(path).decode("utf-8"))
            problem = exchange.version_problem(queue.get("exchange")) if isinstance(queue, dict) else "not a queue"
            if problem:
                raise ValueError(problem)
            opened, closed = list(queue["open"]), list(queue.get("closed", []))
        except (OSError, UnsafeFile, ValueError, KeyError, TypeError) as error:
            view.queue_problem = f"the Review Queue could not be read ({error})"
            return view
        view.run, view.updated_at = str(queue.get("updated_by_run", "")), str(queue.get("updated_at", ""))
        view.next_run, view.report = str(queue.get("next_run", "")), str(queue.get("run_report", ""))
        due = exchange.parse_datetime(view.next_run)
        view.overdue = due is not None and self.now() > due
        if self.first_run is None:
            self.first_run = view.run
        view.changed = view.run != self.first_run
        view.summary, view.summary_problem = self.summary(view.report)

        for entry in opened:
            shown = Entry(entry, taken_in=founder.taken_in(self.ledger, str(entry["id"])), video=self.video(entry))
            try:
                shown.item = queued_item(self.ledger, entry, self.products)
            except (OSError, ValueError, UnsafeFile) as error:
                shown.problem = str(error)
            record, problem = decisions.get(shown.id, (None, ""))
            shown.decision, shown.record_problem = record, problem
            view.entries.append(shown)

        approved_now = {entry.id for entry in view.entries if entry.decision and entry.decision.decision == "approve"}
        for entry in opened + closed:
            if entry.get("kind") != "message":
                continue
            approved = APPROVED in (entry.get("status"), entry.get("decided"))
            if approved or (entry.get("status") == OPEN and entry["id"] in approved_now):
                record, problem = outreach.get(str(entry["id"]), (None, ""))
                view.messages.append(Message(entry, record, problem))
        view.messages.sort(key=lambda message: (message.record is not None, str(message.entry.get("published_at"))))
        return view

    def summary(self, report: str) -> tuple[list[str], str]:
        """The lines of the run report's Summary, as text to show, or why they cannot be shown."""
        relative = Path(report)
        if not report or relative.is_absolute() or ".." in relative.parts:
            return [], "the Review Queue names no run report"
        try:
            text = read_plain(self.ledger / relative).decode("utf-8", errors="replace")
        except (OSError, UnsafeFile) as error:
            return [], f"`{report}` could not be read ({error})"
        lines, inside = [], False
        for line in text.splitlines():
            if line.startswith("## "):
                if inside:
                    break
                inside = line.strip() == "## Summary"
            elif inside and line.strip():
                lines.append(line[2:] if line.startswith("- ") else line)
        return lines, "" if lines else f"`{report}` has no Summary"

    def saved(self, kind: str, stem: str) -> Saved:
        """A record just written, read back from its file: what the page shows as saved."""
        path = founder.folders(self.ledger)[kind] / f"{stem}.json"
        record = json.loads(read_plain(path).decode("utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"{founder.shown(kind, path.name)} is not a JSON object")
        return Saved(kind, stem, record)

    # Writing: each method below is one explicit act of the Founder's on the page.

    def write(self, kind: str, stem: str, record: Mapping[str, object], parser, reasons: list[str]) -> Saved:
        """Check a record with the parser a run reads it with, then write it whole and read it back; anything the
        parser cannot use is refused, and nothing is written."""
        if not reasons:
            reasons += parser(stem, json.loads(json.dumps(record)))[1]
        if reasons:
            raise Refused(reasons)
        try:
            self.writer.write(kind, stem, record)
        except (ConfigError, OSError) as error:
            raise Refused([f"the record could not be written ({error})"]) from error
        return self.saved(kind, stem)

    def changeable(self, item: str) -> Entry:
        """An open item whose decision may still be given, changed, or taken back; the caller holds founder.locked."""
        entry = self.look().find(item)
        if entry is None:
            raise Refused(["this item is not open in the Review Queue any more, so nothing was saved"])
        if entry.taken_in:
            raise Refused(["a run has already taken in your decision on this item, so it can no longer be changed"])
        return entry

    def decide(self, item: str, decision: str, line: str) -> Saved:
        """Approve an open item, with an optional one-line note, or reject it, with a one-line reason."""
        if decision not in (exchange.APPROVE, exchange.REJECT):
            raise Refused(["choose approve or reject"])
        try:
            with founder.locked(self.ledger):
                entry = self.changeable(item)
                reasons: list[str] = []
                if entry.item is None:
                    reasons.append(entry.may_approve())
                elif decision == exchange.APPROVE and entry.may_approve():
                    reasons.append(entry.may_approve())
                rejecting = decision == exchange.REJECT
                text = one_line(line, "The reason" if rejecting else "The note", rejecting, reasons)
                record = {
                    "exchange": exchange.EXCHANGE_VERSION,
                    "item": item,
                    "decision": decision,
                    "reason": text if rejecting else None,
                    "note": None if rejecting else text,
                    "decided_at": self.now().isoformat(),
                    "sitting": self.day,
                }
                return self.write(founder.DECISIONS, item, record, exchange.parse_decision, reasons)
        except founder.Busy as error:
            raise Refused([f"{error}, so nothing was saved; try again"]) from error

    def take_back(self, item: str) -> None:
        """Take a decision back, which leaves the item undecided, while no run has taken it in."""
        try:
            with founder.locked(self.ledger):
                self.changeable(item)
                self.writer.remove(founder.DECISIONS, item)
        except founder.Busy as error:
            raise Refused([f"{error}, so nothing was changed; try again"]) from error
        except (ConfigError, OSError) as error:
            raise Refused([f"the record could not be removed ({error})"]) from error

    def report_counts(self, product: str, given: Mapping[str, str]) -> Saved:
        """The three Beta Cohort counts for the sitting's date, each a total to date; a count left blank is written as
        null, which is not reported and never zero. Giving them again on the same date writes the report again."""
        found = self.look().product(product)
        if found is None or found.build is None:
            raise Refused([f"no Beta Build is recorded for {product}, so there is no Beta Cohort to count"])
        reasons: list[str] = []
        labels = {"invitations_sent": "Invitations sent", "accepted": "Accepted", "sessions_booked": "Sessions booked"}
        counts = {key: whole_number(given.get(key, ""), labels[key], 0, None, reasons) for key in exchange.BETA_COUNTS}
        if not reasons and all(value is None for value in counts.values()):
            reasons.append("give at least one count; a count you leave blank is recorded as not reported, never zero")
        record = {
            "exchange": exchange.EXCHANGE_VERSION,
            "product": product,
            "date": self.day,
            **counts,
            "recorded_at": self.now().isoformat(),
        }
        return self.write(founder.BETA_REPORTS, f"{product}-{self.day}", record, exchange.parse_beta_report, reasons)

    def record_sitting(self, minutes: str, note: str) -> Saved:
        """How long the sitting took, in minutes, with an optional one-line note: the record that ends a sitting.
        A later sitting of the same date writes it again, whole, with the minutes of both."""
        reasons: list[str] = []
        number = whole_number(minutes, "The minutes", 1, MAX_MINUTES, reasons)
        if number is None and not reasons:
            reasons.append(f"the minutes are needed, as a whole number from 1 to {MAX_MINUTES}")
        record = {
            "exchange": exchange.EXCHANGE_VERSION,
            "date": self.day,
            "minutes": number,
            "note": one_line(note, "The note", False, reasons),
        }
        return self.write(founder.SITTINGS, self.day, record, exchange.parse_sitting, reasons)

    def record_sent(self, item: str, sent_on: str, replied_on: str, wait_days: str, note: str) -> Saved:
        """An approved message as the Founder sent it: the day it went, the day a reply came, if one has, and the wait
        before the one follow-up, if the Founder wants another than the item stated."""
        found = next((message for message in self.look().messages if message.id == item), None)
        if found is None:
            raise Refused(["this is not a message you approved, so nothing was saved"])
        reasons: list[str] = []
        if wait_days.strip() and not found.followed_up:
            reasons.append("no follow-up comes after this message, so it has no wait to set")
        today = self.today()
        sent = a_day(sent_on, "The day it was sent", today, True, reasons)
        replied = a_day(replied_on, "The day a reply came", today, False, reasons)
        if sent and replied and replied < sent:
            reasons.append("a reply cannot come before the message was sent")
        record = {
            "exchange": exchange.EXCHANGE_VERSION,
            "item": item,
            "sent_on": sent,
            "replied_on": replied,
            "follow_up_wait_days": whole_number(
                wait_days, "The wait before a follow-up", 1, exchange.MAX_WAIT_DAYS, reasons
            ),
            "note": one_line(note, "The note", False, reasons),
        }
        return self.write(founder.OUTREACH, item, record, exchange.parse_outreach, reasons)

    def record_beta_build(self, product: str, approved_on: str, build: str) -> Saved:
        """The Founder's word that a Beta Build of a Product passed Apple's review for external testing: the gate
        Beta Cohort recruiting waits for. It is written once; recruiting is then stopped or reopened."""
        found = self.look().product(product)
        if found is None:
            raise Refused([f"{product} is not a Product whose Beta Cohort gr0wthlab recruits"])
        if found.build is not None:
            raise Refused([f"a Beta Build is already recorded for {product}; stop or reopen recruiting instead"])
        reasons: list[str] = []
        record = {
            "exchange": exchange.EXCHANGE_VERSION,
            "product": product,
            "approved_on": a_day(approved_on, "The day Apple approved it", self.today(), True, reasons),
            "build": one_line(build, "The build's label", False, reasons),
            "recruiting": exchange.RECRUITING_OPEN,
            "stopped_on": None,
            "recorded_at": self.now().isoformat(),
        }
        return self.write(founder.BETA_BUILDS, product, record, exchange.parse_beta_build, reasons)

    def set_recruiting(self, product: str, stop: bool, stopped_on: str = "") -> Saved:
        """Stop a Product's Beta Cohort recruiting, or reopen it; the approval itself stays as it was given."""
        found = self.look().product(product)
        if found is None or found.build is None:
            raise Refused([f"no Beta Build is recorded for {product}, so there is no recruiting to stop or reopen"])
        build, reasons = found.build, []
        day = a_day(stopped_on, "The day recruiting stopped", self.today(), True, reasons) if stop else None
        if day and day < build.approved_on:
            reasons.append("recruiting cannot have stopped before the Beta Build was approved")
        record = {
            "exchange": exchange.EXCHANGE_VERSION,
            "product": product,
            "approved_on": build.approved_on,
            "build": build.build,
            "recruiting": exchange.RECRUITING_STOPPED if stop else exchange.RECRUITING_OPEN,
            "stopped_on": day,
            "recorded_at": self.now().isoformat(),
        }
        return self.write(founder.BETA_BUILDS, product, record, exchange.parse_beta_build, reasons)
