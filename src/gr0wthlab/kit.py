"""The 14-day test kit as a run reads it from Mandu: the calendar, the Angle bank, the A/B pairs, the two test
platforms, the pre-publication checklist, and the competitors the package's research names.

Each parser reads one package file's text and returns the facts the post-Draft checks need, each with the line it
came from, so a Draft and its Review Queue item can cite the package by reference. Nothing here is kept beyond the
run: the package stays in Mandu. A part that does not parse is a problem that names the file and why, never a guess.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

ANGLE_ID = re.compile(r"P\d+")
PAIR_LEG = re.compile(r"\b(AB-\d+) leg ([AB])\b")
QUOTED = re.compile(r"\"([^\"]+)\"")
URL = re.compile(r"https?://[^\s)\]]+")
CHECKBOX = re.compile(r"- \[([ xX])\] (.*)")
BLOCKING = re.compile(r"\(blocking: ([^)]*)\)")
NAMED_CLAIM = re.compile(r"the \"([^\"]+)\" claim")
RECUT = re.compile(r"\bre-?cut\b", re.IGNORECASE)
# Blocking scopes that cover a social post; any other scope (site, video, submission...) gates other assets.
SOCIAL_SCOPES = ("everything public", "social")
NAME_ENDS = (" (", ": ", " - ", " | ", "! ")


class KitError(ValueError):
    """A kit file that does not hold what the post-Draft checks need."""


@dataclass(frozen=True)
class KitDay:
    """One calendar day; angle is None when the calendar decides the day's Angle later (the flex slot)."""

    day: int
    asset: str
    angle: str | None
    pair: str | None
    leg: str | None
    primary: str
    line: int
    cell: str
    row: str


@dataclass(frozen=True)
class Angle:
    id: str
    name: str
    pain: str
    pain_urls: tuple[str, ...]
    hook_cell: str
    hook: str | None  # the frozen Hook when the cell is exactly one quoted line
    format: str
    platform: str
    signal: str
    kill: str
    line: int
    row: str


@dataclass(frozen=True)
class Leg:
    pair: str
    leg: str
    hook: str | None  # the first quoted text on the leg's line
    line: int
    text: str


@dataclass(frozen=True)
class Pair:
    id: str
    angle: str
    platform: str
    legs: Mapping[str, Leg]
    line: int
    text: str


@dataclass(frozen=True)
class ChecklistItem:
    """One pre-publication checklist line: whether it is done, its title, and which assets it blocks.

    scope is None when the item names no blocking scope; claim is the quoted claim an item about one claim names.
    """

    line: int
    section: str
    checked: bool
    title: str
    scope: tuple[str, ...] | None
    claim: str | None
    text: str

    @property
    def gates_social(self) -> bool:
        return any(token.startswith(SOCIAL_SCOPES) for token in self.scope or ())


@dataclass(frozen=True)
class AssetCheck:
    """One line of the calendar's own checklist for every asset; it holds no state a check could read."""

    line: int
    text: str


@dataclass(frozen=True)
class Competitor:
    name: str
    source: str
    line: int


@dataclass
class Kit:
    """Everything parsed from the kit, and why each part that could not be parsed failed, by role."""

    days: dict[int, KitDay] = field(default_factory=dict)
    angles: dict[str, Angle] = field(default_factory=dict)
    pairs: dict[str, Pair] = field(default_factory=dict)
    platforms: tuple[str, ...] = ()
    checklist: tuple[ChecklistItem, ...] = ()
    asset_checks: tuple[AssetCheck, ...] = ()
    competitors: tuple[Competitor, ...] = ()
    problems: dict[str, str] = field(default_factory=dict)


# Tables.


def cells(line: str) -> list[str]:
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table(text: str, wanted: Sequence[str]) -> tuple[list[str], list[tuple[int, list[str]]]]:
    """The first Markdown table whose header names every wanted column, and its rows with their line numbers."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|") or index + 1 >= len(lines):
            continue
        header = cells(line)
        if not all(column_index(header, name) is not None for name in wanted):
            continue
        if not re.fullmatch(r"\|?(\s*:?-+:?\s*\|)+\s*:?-*:?\s*\|?", lines[index + 1].strip()):
            continue
        rows = []
        for number in range(index + 2, len(lines)):
            if not lines[number].lstrip().startswith("|"):
                break
            rows.append((number + 1, cells(lines[number])))
        return header, rows
    raise KitError(f"no table with the columns {', '.join(wanted)}")


def column_index(header: Sequence[str], name: str) -> int | None:
    """A column by its exact name, else by the first header that starts with it, else that contains it."""
    folded = [cell.casefold() for cell in header]
    key = name.casefold()
    for test in (str.__eq__, str.startswith, str.__contains__):
        for index, cell in enumerate(folded):
            if test(cell, key):
                return index
    return None


def cell(row: Sequence[str], header: Sequence[str], name: str) -> str:
    index = column_index(header, name)
    return row[index] if index is not None and index < len(row) else ""


def urls(text: str) -> tuple[str, ...]:
    """Each link in a text, without the punctuation that ends its sentence."""
    return tuple(url.rstrip(".,;") for url in URL.findall(text))


def one_quote(text: str) -> str | None:
    """The text inside the quotes when a cell is exactly one quoted line."""
    match = re.fullmatch(r"\"([^\"]+)\"", text.strip())
    return match.group(1) if match else None


# The calendar.


def parse_calendar(text: str) -> dict[int, KitDay]:
    header, rows = table(text, ("Day", "Asset", "Angle", "platform"))
    days: dict[int, KitDay] = {}
    lines = text.splitlines()
    for line, row in rows:
        if len(row) != len(header):
            raise KitError(f"calendar line {line} has {len(row)} cells; the header has {len(header)}")
        day_text = cell(row, header, "Day")
        if not re.fullmatch(r"[0-9]+", day_text):
            raise KitError(f"calendar line {line}: day {day_text!r} is not a number")
        day = int(day_text)
        if day in days:
            raise KitError(f"calendar line {line}: day {day} appears twice")
        angle_cell = cell(row, header, "Angle")
        start = re.match(r"(P\d+)\b", angle_cell)
        leg = PAIR_LEG.search(angle_cell) if start else None
        days[day] = KitDay(
            day,
            cell(row, header, "Asset"),
            start.group(1) if start else None,
            leg.group(1) if leg else None,
            leg.group(2) if leg else None,
            cell(row, header, "platform"),
            line,
            angle_cell,
            lines[line - 1],
        )
    if not days:
        raise KitError("the calendar has no days")
    return days


def parse_asset_checks(text: str) -> tuple[AssetCheck, ...]:
    """The list items under the calendar's own checklist section, if it has one."""
    checks: list[AssetCheck] = []
    inside = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            inside = "checklist" in line.casefold()
        elif inside and line.startswith("- "):
            checks.append(AssetCheck(number, line[2:].strip()))
    return tuple(checks)


# The Angle bank.


def parse_angles(text: str) -> dict[str, Angle]:
    columns = ("ID", "Angle", "pain", "Hook", "Format", "Platform", "signal", "Kill")
    header, rows = table(text, columns)
    angles: dict[str, Angle] = {}
    lines = text.splitlines()
    for line, row in rows:
        identifier = cell(row, header, "ID")
        if not ANGLE_ID.fullmatch(identifier):
            continue
        if len(row) != len(header):
            raise KitError(f"Angle bank line {line} has {len(row)} cells; the header has {len(header)}")
        pain = cell(row, header, "pain")
        hook_cell = cell(row, header, "Hook")
        angles[identifier] = Angle(
            identifier,
            cell(row, header, "Angle"),
            pain,
            urls(pain),
            hook_cell,
            one_quote(hook_cell),
            cell(row, header, "Format"),
            cell(row, header, "Platform"),
            cell(row, header, "signal"),
            cell(row, header, "Kill"),
            line,
            lines[line - 1],
        )
    if not angles:
        raise KitError("the Angle bank has no rows with an ID such as P01")
    return angles


# The A/B pairs.


def parse_pairs(text: str) -> dict[str, Pair]:
    pairs: dict[str, Pair] = {}
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"## AB-\d+\b", line)]
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        for index in range(start + 1, end):
            if lines[index].startswith("## "):
                end = index
                break
        heading = lines[start]
        identifier = re.match(r"## (AB-\d+)", heading).group(1)
        angle = re.search(r"\bangle (P\d+)", heading)
        detail = re.search(r"\(([^)]*)\)\s*$", heading)
        parts = [part.strip() for part in detail.group(1).split(",")] if detail else []
        if not angle or len(parts) < 2:
            raise KitError(f"pair {identifier} (line {start + 1}) does not name its angle and platform")
        legs = {}
        for index in range(start + 1, end):
            match = re.match(r"- Leg ([AB]) hook: (.*)", lines[index])
            if match:
                quoted = QUOTED.search(match.group(2))
                legs[match.group(1)] = Leg(
                    identifier, match.group(1), quoted.group(1) if quoted else None, index + 1, lines[index]
                )
        if set(legs) != {"A", "B"}:
            raise KitError(f"pair {identifier} (line {start + 1}) does not have a leg A and a leg B hook")
        pairs[identifier] = Pair(identifier, angle.group(1), parts[1], legs, start + 1, "\n".join(lines[start:end]))
    if not pairs:
        raise KitError("no A/B pair sections (## AB-n) were found")
    return pairs


# The test platforms.


def parse_platforms(text: str) -> tuple[str, ...]:
    """The platforms named under the section on the test platforms, in order."""
    names: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = "test platforms" in line.casefold()
            continue
        match = re.match(r"### \d+\. (.+?)(?: \([^)]*\))?\s*$", line) if inside else None
        if match:
            names.append(match.group(1).strip())
    if len(names) < 1:
        raise KitError("no platforms were found under a section on the test platforms")
    return tuple(names)


# The pre-publication checklist.


def parse_checklist(text: str) -> tuple[ChecklistItem, ...]:
    items: list[ChecklistItem] = []
    section = ""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("## "):
            section = line[3:].strip()
        match = CHECKBOX.match(line)
        if not match:
            index += 1
            continue
        body = [match.group(2)]
        number = index + 1
        index += 1
        while index < len(lines) and lines[index].startswith("  ") and lines[index].strip():
            body.append(lines[index].strip())
            index += 1
        full = " ".join(body)
        bold = re.search(r"\*\*(.+?)\*\*", full)
        title = (bold.group(1) if bold else re.split(r"(?<=[.:;])\s", full, maxsplit=1)[0]).strip()
        scopes = BLOCKING.findall(full)
        scope = (
            tuple(token.strip().casefold() for token in re.split(r"[,;]", scopes[-1]) if token.strip())
            if scopes
            else None
        )
        claim = NAMED_CLAIM.search(title)
        items.append(
            ChecklistItem(
                number,
                section,
                match.group(1) != " ",
                title,
                scope,
                claim.group(1) if claim else None,
                full,
            )
        )
    if not items:
        raise KitError("the checklist has no - [ ] items")
    return tuple(items)


# Competitors named in the research.


def competitor_name(text: str) -> list[str]:
    """A competitor's name from a heading, cut before its description, with a trailing " App" also dropped."""
    name = text.strip()
    for end in NAME_ENDS:
        name = name.split(end, 1)[0]
    name = name.rstrip("!:").strip()
    names = [name] if len(name) >= 3 else []
    if name.endswith(" App") and len(name) > 7:
        names.append(name[: -len(" App")])
    return names


def parse_competitors(files: Mapping[str, str]) -> tuple[Competitor, ...]:
    """Every competitor the research names, by three rules on the competitor files:

    - a teardown titled `# Competitor Teardown: <name> ...`;
    - a numbered `## <n>. <name> ...` section whose first line is its `Source:`;
    - the last parenthesized, comma-separated list on a `Scope:` line, such as the competitors already covered.
    """
    found: dict[str, Competitor] = {}

    def add(names: list[str], source: str, line: int) -> None:
        for name in names:
            found.setdefault(name, Competitor(name, source, line))

    for source, text in sorted(files.items()):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            title = re.match(r"# Competitor Teardown: (.+)", line)
            if title:
                add(competitor_name(title.group(1)), source, index + 1)
            section = re.match(r"## \d+\. (.+)", line)
            if section:
                following = next((later for later in lines[index + 1 :] if later.strip()), "")
                if following.startswith("Source:"):
                    add(competitor_name(section.group(1)), source, index + 1)
            if line.startswith("Scope:"):
                lists = re.findall(r"\(([^()]*)\)", line)
                if lists:
                    for name in lists[-1].split(","):
                        add([name.strip()] if len(name.strip()) >= 3 else [], source, index + 1)
    if not found:
        raise KitError("no competitor names could be read from the research")
    return tuple(found.values())


# The Hook a day must use.


@dataclass(frozen=True)
class FrozenHook:
    text: str
    source: str  # "pairs" or "angles"
    line: int


def frozen_hook(day: KitDay, kit: Kit) -> tuple[FrozenHook | None, str]:
    """The Hook frozen for a calendar day: its pair leg's in the A/B pairs, otherwise its Angle's in the bank."""
    if day.angle is None:
        return None, f"the calendar decides day {day.day}'s Angle later ({day.cell})"
    if day.pair:
        pair = kit.pairs.get(day.pair)
        if pair is None:
            return None, f"pair {day.pair} is not in the A/B pairs"
        if pair.angle != day.angle:
            return None, f"pair {day.pair} tests Angle {pair.angle}, not {day.angle}"
        leg = pair.legs[day.leg or ""] if day.leg in pair.legs else None
        if leg is None or not leg.hook:
            return None, f"{day.pair} leg {day.leg} has no quoted Hook"
        return FrozenHook(leg.hook, "pairs", leg.line), ""
    angle = kit.angles.get(day.angle)
    if angle is None:
        return None, f"Angle {day.angle} is not in the Angle bank"
    if not angle.hook:
        return None, f"Angle {day.angle}'s Hook cell is not one quoted line, so its frozen text cannot be read"
    return FrozenHook(angle.hook, "angles", angle.line), ""


def recut_hooks(day: KitDay, kit: Kit) -> tuple[str, ...]:
    """Both frozen Hooks of a day's A/B pair when the kit marks the pair as a re-cut, in the pair's own section of
    the A/B pairs or in the calendar row of either leg; none for any other day. The legs of a re-cut pair open on
    one Hook each and may show the other in a later beat, so their openings differ by more than the Hook's text."""
    pair = kit.pairs.get(day.pair or "")
    if pair is None:
        return ()
    marks = [pair.text] + [other.row for other in kit.days.values() if other.pair == pair.id]
    if not any(RECUT.search(mark) for mark in marks):
        return ()
    return tuple(leg.hook for leg in pair.legs.values() if leg.hook)


def all_hooks(kit: Kit) -> list[tuple[str, str]]:
    """Every frozen Hook in the kit with the Angle it belongs to."""
    hooks = [(angle.hook, angle.id) for angle in kit.angles.values() if angle.hook]
    for pair in kit.pairs.values():
        hooks += [(leg.hook, pair.angle) for leg in pair.legs.values() if leg.hook]
    return hooks
