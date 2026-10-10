"""The Waitlist's anonymous view, read by the launcher alone: the address check over every value first, then the view's
format, then counts by Source, Fit answer, and opt-in, per week and cumulative, and progress toward the Beta Cohort bar.

The view is RepToday's: one JSON file on the Founder's Mac, outside everything the sandbox can read, in the format the
Waitlist Dispatch request specifies (src/dispatches/reptoday-waitlist.md). The agent never reads it.
Guardrail G6 says no email address is ever readable: if anything in the file looks like one, or an entry identifier
holds one in an encoding, the whole read is discarded, nothing from it is kept, and the run reports a breach to the
Founder.
No message, report, or record ever repeats what the view holds, except entry identifiers, dates, and the approved
Source tags and Fit answers; Waitlist Evidence holds entry identifiers and counts only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

from . import exchange
from .package import FAILED, READ
from .settings import UNKNOWN, Waitlist

SOURCE_NAME = "Waitlist anonymous view"
SKIPPED = "skipped"  # as report.SKIPPED
REFUSED = "refused"
VIEW_FORMAT = 1
EVIDENCE_FORMAT = 1
MAX_VIEW_BYTES = 10_000_000
TOP_KEYS = ("view", "generated_at", "entries")
ENTRY_KEYS = ("entry", "source", "fit", "beta_opt_in", "signed_up_on")
ENTRY_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
MAX_LISTED = 5
COUNTS = ("sign_ups", "good_fit", "opted_in", "good_fit_opt_ins")

# A value looks like an email address when anything but a space or a delimiter stands on both sides of an @.
ADDRESS = re.compile(r"[^\s@\"'<>()\[\]{},;:\\]@[^\s@\"'<>()\[\]{},;:\\]")
# An identifier decoded from base64 or hex counts only when it holds a whole address, so a random identifier never does.
ENCODED_ADDRESS = re.compile(r"[A-Za-z0-9._%+-]@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


# The address check.


def looks_like_address(text: str) -> bool:
    """Whether anything in the text looks like an email address."""
    return ADDRESS.search(text) is not None


def decoded(identifier: str) -> Iterator[str]:
    """The printable text an entry identifier holds when it is read as base64, in either alphabet, or as hex."""
    candidates = []
    plain = identifier.rstrip("=").replace("-", "+").replace("_", "/")
    try:
        candidates.append(base64.b64decode(plain + "=" * (-len(plain) % 4), validate=True))
    except ValueError:
        pass
    try:
        candidates.append(bytes.fromhex(identifier))
    except ValueError:
        pass
    for data in candidates:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if text.isprintable():
            yield text


def encodes_address(identifier: str) -> bool:
    """Whether an entry identifier is an email address in percent-encoding, base64, or hex. The identifier is the
    view's one free-form value; every other value must be one the format lists, so it is checked as written."""
    return looks_like_address(unquote(identifier)) or any(ENCODED_ADDRESS.search(text) for text in decoded(identifier))


def address_places(value: object) -> list[str]:
    """Where in the parsed view a key or value looks like an email address, named by position and by the format's own
    field names, never by anything the view holds."""
    places: list[str] = []

    def field_name(key: object, known: Sequence[str]) -> str:
        return f"`{key}`" if key in known else "a field outside the format"

    def check(item: object, where: str, identifier: bool = False) -> None:
        if isinstance(item, str):
            if looks_like_address(item) or (identifier and encodes_address(item)):
                places.append(where)
        elif isinstance(item, dict):
            for key, inner in item.items():
                if looks_like_address(str(key)):
                    places.append(f"{where}, a field name")
                check(inner, where)
        elif isinstance(item, list):
            for inner in item:
                check(inner, where)

    if not isinstance(value, dict):
        check(value, "the file")
        return places
    for key, inner in value.items():
        if looks_like_address(str(key)):
            places.append("the top of the file, a field name")
        if key == "entries" and isinstance(inner, list):
            for number, entry in enumerate(inner, 1):
                if not isinstance(entry, dict):
                    check(entry, f"entry {number}")
                    continue
                for entry_key, entry_value in entry.items():
                    where = f"entry {number}, {field_name(entry_key, ENTRY_KEYS)}"
                    if looks_like_address(str(entry_key)):
                        places.append(f"entry {number}, a field name")
                    check(entry_value, where, entry_key == "entry")
        else:
            check(inner, f"the top of the file, {field_name(key, TOP_KEYS)}")
    return places


# The view's format.


@dataclass(frozen=True)
class Entry:
    entry: str
    source: str
    fit: str  # UNKNOWN when the person gave no answer, never "not a fit"
    opted_in: bool
    day: date


@dataclass(frozen=True)
class View:
    generated_at: datetime
    entries: tuple[Entry, ...]


def check_view(data: object, rules: Waitlist) -> tuple[View | None, list[str]]:
    """The view's entries, or every way the file departs from its format, without repeating a value it holds."""
    if not isinstance(data, dict):
        return None, ["the file is not a JSON object"]
    problems: list[str] = []
    if sorted(data) != sorted(TOP_KEYS):
        problems.append(f"the file must hold exactly {', '.join(TOP_KEYS)} at its top")
    version = data.get("view")
    if isinstance(version, int) and not isinstance(version, bool) and version > VIEW_FORMAT:
        return None, [f"view format {version} is newer than gr0wthlab reads (up to {VIEW_FORMAT})"]
    if version != VIEW_FORMAT or isinstance(version, bool):
        problems.append(f"view must be {VIEW_FORMAT}")
    generated = data.get("generated_at")
    generated_at = exchange.parse_datetime(generated) if isinstance(generated, str) else None
    if generated_at is None:
        problems.append("generated_at must be an ISO 8601 time with its UTC offset")
    raw = data.get("entries")
    if not isinstance(raw, list):
        return None, problems + ["entries must be a list"]
    entries: list[Entry] = []
    seen: set[str] = set()
    sources = (*rules.source_tags, UNKNOWN)
    for number, item in enumerate(raw, 1):
        where = f"entry {number}"
        if not isinstance(item, dict):
            problems.append(f"{where} is not a JSON object")
            continue
        if sorted(item) != sorted(ENTRY_KEYS):
            problems.append(f"{where} must hold exactly {', '.join(ENTRY_KEYS)}")
            continue
        identifier, source, fit, opted_in, day = (item[key] for key in ENTRY_KEYS)
        before = len(problems)
        if not isinstance(identifier, str) or not ENTRY_PATTERN.fullmatch(identifier):
            problems.append(f"{where}: entry must be 1 to 64 letters, digits, - or _")
        elif identifier in seen:
            problems.append(f"{where}: entry repeats an earlier entry's identifier")
        if source not in sources:
            problems.append(f"{where}: source is not one of {', '.join(sources)}")
        if fit is not None and fit not in rules.fit_answers:
            problems.append(f"{where}: fit is not one of {', '.join(rules.fit_answers)}, or null")
        if not isinstance(opted_in, bool):
            problems.append(f"{where}: beta_opt_in must be true or false")
        if not isinstance(day, str) or not exchange.valid_date(day):
            problems.append(f"{where}: signed_up_on must be a YYYY-MM-DD date")
        elif generated_at and date.fromisoformat(day) > generated_at.astimezone(timezone.utc).date():
            problems.append(f"{where}: signed_up_on is after the day the view was generated")
        if len(problems) == before:
            seen.add(identifier)
            entries.append(Entry(identifier, source, fit or UNKNOWN, opted_in, date.fromisoformat(day)))
    if problems:
        return None, problems
    return View(generated_at, tuple(entries)), []


# Counts.


def week_of(day: date) -> date:
    """The Monday that starts a day's week; day 1 of a 14-day window is the Monday after the Sunday sitting."""
    return day - timedelta(days=day.weekday())


def count(entries: Sequence[Entry], rules: Waitlist) -> dict[str, object]:
    """Sign-ups, good Fit, opt-ins, and good-Fit opt-ins, overall, by Source, and by Fit answer; a sign-up with no Fit
    answer counts under unknown, never as not a fit."""

    def zero() -> dict[str, int]:
        return dict.fromkeys(COUNTS, 0)

    totals = zero()
    by_source = {tag: zero() for tag in (*rules.source_tags, UNKNOWN)}
    by_fit = {answer: {"sign_ups": 0, "opted_in": 0} for answer in (*rules.fit_answers, UNKNOWN)}
    for entry in entries:
        good = entry.fit in rules.good_fit
        row = {"sign_ups": 1, "good_fit": int(good), "opted_in": int(entry.opted_in)}
        row["good_fit_opt_ins"] = int(good and entry.opted_in)
        for target in (totals, by_source[entry.source]):
            for key, value in row.items():
                target[key] += value
        by_fit[entry.fit]["sign_ups"] += 1
        by_fit[entry.fit]["opted_in"] += int(entry.opted_in)
    return {**totals, "by_source": by_source, "by_fit": by_fit}


def weekly(entries: Sequence[Entry], rules: Waitlist, run_week: date) -> list[dict[str, object]]:
    """Counts for every week from the first sign-up's through the run's own, empty weeks too. A sign-up dated after
    the run's week, as its UTC date is late on a Sunday evening on the Mac, adds a week and never moves the run's."""
    by_week: dict[date, list[Entry]] = {run_week: []}
    for entry in entries:
        by_week.setdefault(week_of(entry.day), []).append(entry)
    week, last = min(by_week), max(by_week)
    weeks = []
    while week <= last:
        weeks.append({"week_of": week.isoformat(), **count(by_week.get(week, ()), rules)})
        week += timedelta(days=7)
    return weeks


# One read.


@dataclass
class Reading:
    """What one run learned from the view: its status and the plain-language detail for the run report, and, when the
    view was read, its counts; places says where address-like values were, never what they were.

    this_week is the run's own week, the one that ends at the Founder's Sunday sitting; age is how long before the run
    started the view was generated."""

    status: str
    detail: str
    rules: Waitlist | None = None
    view: Path | None = None
    sha256: str | None = None
    generated_at: datetime | None = None
    entries: tuple[str, ...] = ()
    weeks: list[dict[str, object]] = field(default_factory=list)
    cumulative: dict[str, object] = field(default_factory=dict)
    places: tuple[str, ...] = ()
    this_week: dict[str, object] = field(default_factory=dict)
    age: timedelta | None = None

    @property
    def good_fit_opt_ins(self) -> int:
        return int(self.cumulative.get("good_fit_opt_ins", 0))


def listed(items: Sequence[str]) -> str:
    shown = "; ".join(items[:MAX_LISTED])
    return shown + (f"; and {len(items) - MAX_LISTED} more" if len(items) > MAX_LISTED else "")


def not_configured(rules: Waitlist | None) -> Reading:
    if rules is None:
        return Reading(SKIPPED, "no Product has a Waitlist in the Product registry")
    return Reading(
        SKIPPED,
        f"{rules.product}'s Waitlist build has not landed, so no view location is configured yet (US-ME05)",
        rules,
    )


def read(rules: Waitlist | None, started: datetime) -> Reading:
    """Read the view once, for the run that started then. The address check runs over the whole file and every value
    in it before anything else, and a hit discards the read; then the format; then the counts."""
    if rules is None or rules.view is None:
        return not_configured(rules)
    path = rules.view

    def failed(reason: str) -> Reading:
        return Reading(FAILED, f"`{path}` {reason}.", rules, path)

    try:
        with open(str(path), "rb") as handle:  # outside the sandbox and every area, so no link here is the agent's
            data = handle.read(MAX_VIEW_BYTES + 1)
    except FileNotFoundError:
        return failed("is configured but does not exist")
    except IsADirectoryError:
        return failed("is a folder, not the view's file")
    except OSError as error:
        return failed(f"could not be read: {error.strerror or error}")

    text = data.decode("utf-8", errors="replace")
    whole_file = looks_like_address(text)
    parsed: object = None
    places: list[str] = []
    problem = None
    if len(data) > MAX_VIEW_BYTES:
        problem = f"is larger than {MAX_VIEW_BYTES // 1_000_000} MB"
    else:
        try:
            parsed = json.loads(data.decode("utf-8"))
            places = address_places(parsed)
        except UnicodeDecodeError:
            problem = "is not UTF-8 text"
        except RecursionError:
            problem = "is nested too deeply to be the view"
        except ValueError as error:
            problem = f"is not valid JSON (line {getattr(error, 'lineno', '?')})"
    if whole_file or places:
        where = places or ["the file's text, outside any value the format names"]
        return Reading(
            REFUSED,
            f"something in the view looked like an email address ({listed(where)}); the whole read was discarded and"
            " nothing from it was kept",
            rules,
            path,
            places=tuple(where),
        )
    if problem:
        return failed(problem)
    view, problems = check_view(parsed, rules)
    if view is None:
        return failed(f"does not follow the view's format: {listed(problems)}")
    entries = view.entries
    cumulative = count(entries, rules)
    run_week = week_of(started.astimezone().date())
    weeks = weekly(entries, rules, run_week)
    return Reading(
        READ,
        f"generated {view.generated_at.isoformat()}: sign-ups {len(entries)}, good-Fit opt-ins"
        f" {cumulative['good_fit_opt_ins']} of about {rules.bar}",
        rules,
        path,
        hashlib.sha256(data).hexdigest(),
        view.generated_at,
        tuple(sorted(entry.entry for entry in entries)),
        weeks,
        cumulative,
        this_week=next(week for week in weeks if week["week_of"] == run_week.isoformat()),
        age=started - view.generated_at,
    )


def evidence(reading: Reading, run_id: str, read_at: datetime) -> dict[str, object]:
    """Waitlist Evidence: where and when the counts came from, the entry identifiers, and the counts; nothing else."""
    rules = reading.rules
    return {
        "format": EVIDENCE_FORMAT,
        "run": run_id,
        "product": rules.product,
        "read_at": read_at.isoformat(),
        "source": {
            "view": str(reading.view),
            "generated_at": reading.generated_at.isoformat(),
            "sha256": reading.sha256,
        },
        "good_fit": list(rules.good_fit),
        "beta_cohort_bar": rules.bar,
        "progress": {"good_fit_opt_ins": reading.good_fit_opt_ins, "bar": rules.bar},
        "entries": list(reading.entries),
        "weeks": reading.weeks,
        "cumulative": reading.cumulative,
        "note": "Entry identifiers and counts only; no email address or anything else a sign-up wrote is ever kept.",
    }
