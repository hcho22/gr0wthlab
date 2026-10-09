"""The Mandu exchange formats in docs/mandu-exchange.md: the Review Queue items gr0wthlab writes, and the decision
and sitting records Mandu writes for gr0wthlab to read.

Everything here is pure parsing and rendering, so the agent's own check (check-incoming) and the launcher's
post-run validation apply exactly the same rules.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

EXCHANGE_VERSION = 1

# Each kind's body heading, in the order a week's non-post items are presented; posts come first by nearest slot.
KINDS = {
    "post": "Draft",
    "message": "Draft",
    "weekly-read-decision": "Recommendation",
    "dispatch-request": "Request",
    "package-change-proposal": "Proposal",
    "notice": "Notice",
}
APPROVE = "approve"
REJECT = "reject"
OPTIONS = {
    "notice": ("Acknowledge, optionally with a note", "Reject, with a one-line reason"),
    "default": ("Approve, optionally with a note", "Reject, with a one-line reason"),
}
ITEM_KEYS = ("exchange", "id", "kind", "product", "slot", "supersedes")
ID_PATTERN = re.compile(r"\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*")
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_ID = 80
MAX_TITLE = 120
MAX_ITEM_CHARS = 12000
MAX_LINE = 300
# An Evidence line names its source as a URL or as a path in backticks.
SOURCE_PATTERN = re.compile(r"https?://\S+|`[^`\s]*[/.][^`]*`")


def options(kind: str) -> tuple[str, str]:
    return OPTIONS["notice"] if kind == "notice" else OPTIONS["default"]


def item_id(day: date, slug: str) -> str:
    return f"{day:%Y%m%d}-{slug}"


@dataclass(frozen=True)
class Item:
    """A Review Queue item: front matter, the one-line ask, and the four sections."""

    fields: Mapping[str, str]
    ask: str
    body: str
    touches: str
    evidence: str

    @property
    def kind(self) -> str:
        return self.fields["kind"]


@dataclass
class ItemCheck:
    item: Item | None = None
    problems: list[str] = field(default_factory=list)


def parse_datetime(text: str) -> datetime | None:
    """An ISO 8601 date and time that states its UTC offset."""
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def front_matter(lines: list[str], problems: list[str]) -> tuple[dict[str, str], int]:
    """The key: value lines between the opening and closing --- lines, and the index after them."""
    if not lines or lines[0].strip() != "---":
        problems.append("the item must start with a --- front matter line")
        return {}, 0
    fields: dict[str, str] = {}
    for index in range(1, len(lines)):
        line = lines[index].strip()
        if line == "---":
            return fields, index + 1
        key, colon, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not colon or key not in ITEM_KEYS:
            problems.append(f"front matter line {line!r} is not one of: {', '.join(ITEM_KEYS)}")
        elif key in fields:
            problems.append(f"front matter names {key} twice")
        else:
            fields[key] = value
    problems.append("the front matter has no closing --- line")
    return fields, len(lines)


def check_fields(fields: Mapping[str, str], products: Sequence[str], published: bool, problems: list[str]) -> None:
    kind = fields.get("kind", "")
    if kind not in KINDS:
        problems.append(f"kind must be one of: {', '.join(KINDS)}")
    if published:
        if fields.get("exchange") != str(EXCHANGE_VERSION):
            problems.append(f"exchange must be {EXCHANGE_VERSION}")
        if not ID_PATTERN.fullmatch(fields.get("id", "")):
            problems.append("id is missing or malformed")
    else:
        if "id" in fields:
            problems.append("leave out id; gr0wthlab assigns it when the item is queued")
        if fields.get("exchange", str(EXCHANGE_VERSION)) != str(EXCHANGE_VERSION):
            problems.append(f"exchange must be {EXCHANGE_VERSION} or left out")
    product = fields.get("product")
    if product is not None and product not in products:
        problems.append(f"product must be one of: {', '.join(products)}")
    slot = fields.get("slot")
    if kind == "post":
        if slot is None or parse_datetime(slot) is None:
            problems.append("a post needs slot: its publishing time, such as 2026-10-14T19:00-07:00")
    elif slot is not None:
        problems.append("only a post has a slot")
    supersedes = fields.get("supersedes")
    if supersedes is not None and not ID_PATTERN.fullmatch(supersedes):
        problems.append("supersedes must name an item id")


def sections(lines: list[str], problems: list[str]) -> tuple[str, list[tuple[str, str]]]:
    """The # title line, then each ## section with its text; anything else is a problem."""
    title = ""
    found: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith("## "):
            found.append((line[3:].strip(), []))
        elif line.startswith("# "):
            if title or found:
                problems.append("the item has more than one # title line")
            title = line[2:].strip()
        elif found:
            found[-1][1].append(line)
        elif line.strip():
            problems.append("nothing may come between the front matter, the # title line, and the first section")
    return title, [(heading, "\n".join(body).strip()) for heading, body in found]


def evidence_problems(text: str) -> list[str]:
    entries: list[str] = []
    problems = []
    for line in text.splitlines():
        if line.startswith("- "):
            entries.append(line)
        elif line.strip() and line.startswith((" ", "\t")) and entries:
            entries[-1] += " " + line.strip()
        elif line.strip():
            problems.append("Evidence holds only list items (- ...)")
    if not entries:
        problems.append("Evidence needs at least one list item")
    for entry in entries:
        if not SOURCE_PATTERN.search(entry):
            problems.append(f"Evidence line has no source (a URL or a `path`): {entry[:80]!r}")
    return problems


def check_item(text: str, products: Sequence[str], published: bool = False) -> ItemCheck:
    """Validate an item; published items carry exchange and id, items the agent writes leave both out."""
    problems: list[str] = []
    lines = text.splitlines()
    fields, start = front_matter(lines, problems)
    check_fields(fields, products, published, problems)
    title, found = sections(lines[start:], problems)
    if not title:
        problems.append("the item needs a # title line naming the ask")
    elif len(title) > MAX_TITLE:
        problems.append(f"the title is {len(title)} characters; the ask fits on one line of at most {MAX_TITLE}")
    kind = fields.get("kind", "")
    expected = [KINDS.get(kind, "Draft"), "Touches", "Evidence", "Options"]
    headings = [heading for heading, _ in found]
    if headings != expected:
        problems.append(f"sections must be exactly: {', '.join('## ' + h for h in expected)}; found {headings}")
        return ItemCheck(None, problems)
    content = dict(found)
    for heading in expected[:2]:
        if not content[heading]:
            problems.append(f"## {heading} is empty")
    problems += evidence_problems(content["Evidence"])
    listed = [line[2:].strip() for line in content["Options"].splitlines() if line.strip()]
    wanted = list(options(kind))
    if listed != wanted or any(not line.startswith("- ") for line in content["Options"].splitlines() if line.strip()):
        problems.append("## Options must be exactly: " + "; ".join(f"- {option}" for option in wanted))
    if problems:
        return ItemCheck(None, problems)
    item = Item(dict(fields), title, content[expected[0]], content["Touches"], content["Evidence"])
    length = len(render_content(kind, item.ask, item.body, item.touches, item.evidence))
    if length > MAX_ITEM_CHARS:
        problem = f"the item is {length} characters; keep it under {MAX_ITEM_CHARS} so it can be decided fast"
        return ItemCheck(None, [problem])
    return ItemCheck(item, [])


def item_hash(item: Item) -> str:
    """A fingerprint of what an item asks: its kind, ask, and Draft or proposal, ignoring case and spacing.

    Two items with the same fingerprint ask the Founder the same thing, whatever their Evidence or file name.
    """
    normalized = "\n".join(" ".join(text.split()).casefold() for text in (item.kind, item.ask, item.body))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def render_content(kind: str, ask: str, body: str, touches: str, evidence: str) -> str:
    """The canonical title and four sections of an item: everything the Founder reads."""
    lines = [f"# {ask}", "", f"## {KINDS[kind]}", "", body.strip(), "", "## Touches", "", touches.strip(), ""]
    lines += ["## Evidence", "", evidence.strip(), "", "## Options", ""]
    lines += [f"- {option}" for option in options(kind)]
    return "\n".join(lines) + "\n"


def render_item(fields: Mapping[str, str], ask: str, body: str, touches: str, evidence: str) -> str:
    """The canonical text of an item; publication writes every item through here."""
    ordered = [(key, fields[key]) for key in ITEM_KEYS if fields.get(key) is not None]
    front = ["---"] + [f"{key}: {value}" for key, value in ordered] + ["---", ""]
    return "\n".join(front) + "\n" + render_content(fields["kind"], ask, body, touches, evidence)


# Records Mandu writes.


@dataclass(frozen=True)
class Decision:
    item: str
    decision: str
    reason: str | None
    note: str | None
    decided_at: str
    sitting: str | None


@dataclass(frozen=True)
class Sitting:
    day: str
    minutes: int
    note: str | None


def one_line(value: object, name: str, problems: list[str], required: bool) -> str | None:
    if value is not None and (not isinstance(value, str) or "\n" in value or "\r" in value):
        problems.append(f"{name} must be one line of text")
        return None
    text = (value or "").strip()
    if not text:
        if required:
            problems.append(f"{name} is required")
        return None
    if len(text) > MAX_LINE:
        problems.append(f"{name} must be at most {MAX_LINE} characters")
    return text


def check_version(data: Mapping, problems: list[str]) -> None:
    if data.get("exchange") != EXCHANGE_VERSION:
        problems.append(f"exchange must be {EXCHANGE_VERSION}; got {data.get('exchange')!r}")


def parse_decision(stem: str, data: object) -> tuple[Decision | None, list[str]]:
    """A decision record from decisions/<item id>.json; other fields are Mandu's own and are ignored."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return None, ["the record must be a JSON object"]
    check_version(data, problems)
    item = data.get("item")
    if item != stem:
        problems.append(f"item must equal the file name {stem!r}; got {item!r}")
    decision = data.get("decision")
    if decision not in (APPROVE, REJECT):
        problems.append(f"decision must be {APPROVE!r} or {REJECT!r}")
    reason = one_line(data.get("reason"), "reason", problems, required=decision == REJECT)
    if decision == APPROVE and reason:
        problems.append("an approval has no reason; use note")
    note = one_line(data.get("note"), "note", problems, required=False)
    decided_at = data.get("decided_at")
    if not isinstance(decided_at, str) or parse_datetime(decided_at) is None:
        problems.append("decided_at must be an ISO 8601 time with its UTC offset")
    sitting = data.get("sitting")
    if sitting is not None and not (isinstance(sitting, str) and valid_date(sitting)):
        problems.append("sitting must be a YYYY-MM-DD date")
    if problems:
        return None, problems
    return Decision(stem, decision, reason, note, decided_at, sitting), []


def valid_date(text: str) -> bool:
    try:
        return date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False


def parse_sitting(stem: str, data: object) -> tuple[Sitting | None, list[str]]:
    """A sitting record from sittings/<YYYY-MM-DD>.json."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return None, ["the record must be a JSON object"]
    check_version(data, problems)
    day = data.get("date")
    if day != stem or not valid_date(stem):
        problems.append(f"date must be a YYYY-MM-DD date equal to the file name {stem!r}")
    minutes = data.get("minutes")
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 0 < minutes <= 600:
        problems.append("minutes must be a whole number from 1 to 600")
    note = one_line(data.get("note"), "note", problems, required=False)
    if problems:
        return None, problems
    return Sitting(stem, minutes, note), []
