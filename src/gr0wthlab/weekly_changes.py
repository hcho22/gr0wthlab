"""What an approved Weekly Read decision changes in the Go-To-Market Package: the one package-change proposal it owes,
with the exact edit, which the next run files for the Founder to approve and Mandu then applies like any approved
package change (the Founder's choice of 2026-10-15, "two approvals"). Approving a Weekly Read decision changes no
package file by itself, since Mandu acts only on an approved package-change proposal or Dispatch request
(docs/mandu-exchange.md).

The decisions that owe one, each by the memo line it came from (weekly_read.Line), once a run has taken in its
approval:

- an Angle's kill: the Angle's record in the creative log takes the status "killed" with the dates of the two Weekly
  Reads, as the package's own kill rule says;
- an Angle's change: a changed Hook, signal, or kill criterion enters only as a new Angle (FR-7), so the proposal adds
  one to the Angle bank under the next free number, with the changed Angle's pain and source as they are and its other
  cells in the words the Weekly Read session writes, and adds its record to the creative log in the shape of the
  changed Angle's record, so a later kill of the new Angle has its record to mark; the changed Angle stays as it is,
  since it did not meet its kill criterion;
- a resolved pair: one line at the end of the pair's section in the A/B pairs file says which leg's Hook leads;
- the flex slot, earned or not, while its window is the one in force: the calendar's flex row names the Angle that
  earned it, or the one Angle the row names for when none did, on that Angle's own platform in the Angle bank. Once
  another window is in force its day has passed: an approval found then files nothing, and the run says so once, and
  an open proposal for it is withdrawn before the run takes in any decision, so approving it never fills the flex slot
  of a window it was not filed for.

An Angle kept or tested, a pair to repost, and a result that bears on the product owe nothing, and neither does a
decision rejected, nor one given on an item a newer one had replaced. How a kill, a resolved pair, and a changed Angle
are marked is firstmate's decision of 2026-10-15: the package's own rule for a kill, and the smallest additive mark
where the package has none.

Every edit replaces a text that appears exactly once in the file as the run read it, so Mandu applies it with no
judgment, and a proposal is filed only when applying its edit to that text changes exactly what the decision fixes and
nothing else. A decision's proposal is filed once, under an origin that names the decision, and never again, whatever
the Founder decides of it. A decision whose edit cannot be made this run owes it still, and the Weekly Read row says
why; a new Angle the launcher refuses is removed from workspace/, and only its name and the launcher's reasons are
kept, in the run report.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from . import exchange, kit, lint, results, weekly_read
from .areas import Areas, Store, UnsafeFile, read_plain
from .queue import APPROVED, SUPERSEDED, Ledger
from .waitlist import looks_like_address

WORKFLOW = weekly_read.WORKFLOW
ORIGIN = "weekly-read"  # a filed proposal's origin is ORIGIN/<decision item>
FOLDER = "changes"  # under workspace/weekly-reads/: the new Angle the Weekly Read session writes for a change
KILL, CHANGE, PAIR, FLEX = "kill", "change", "pair", "flex"
# The Product registry's role for the creative log, under its package's weekly_read.
CREATIVE_LOG = "creative_log"
KILLED = "killed"
READS_FIELD = "killed_on_reads"
UNTESTED = "draft"  # the status the creative log gives an Angle no post has tested yet
# A new Angle's record in the creative log: each of these fields from the new row's cell of that column, and these
# from the changed Angle's record, the sourced pain the two carry.
RECORD_CELLS = {
    "hypothesis": "Hypothesis",
    "format": "Format",
    "preregistered_success_signal": "signal",
    "kill_criterion": "Kill",
}
RECORD_PAIN = ("pain_rank", "pain_state", "verbatim_quote", "pain_source_url")
# On an approved flex decision whose window passed before its proposal was filed: the window then in force.
PASSED = "flex_window_passed"
MAX_ROW = 3000
FENCE = "```"
BANK_COLUMNS = ("ID", "Angle", "pain", "Hook", "Format", "Platform", "signal", "Kill")
CALENDAR_COLUMNS = ("Day", "Asset", "Angle", "platform")
DECISIONS = ("evidence", "decisions")


def origin(decision: str) -> str:
    return f"{ORIGIN}/{decision}"


@dataclass(frozen=True)
class Edit:
    """One exact edit: the text at a place in a package file, found there exactly once, and the text to put there."""

    path: str  # inside the Mandu checkout
    line: int  # the line it starts on, counted from 1
    old: str
    new: str

    @property
    def last(self) -> int:
        return self.line + self.old.count("\n")


@dataclass
class Owed:
    """One approved Weekly Read decision that owes its package change, and what became of it this run."""

    item: str  # the decision item
    kind: str  # KILL, CHANGE, PAIR, or FLEX
    key: str  # the Angle, the pair, or "flex"
    ask: str
    window: int
    read: int
    read_date: date | None  # the read's own day
    leads: str = ""  # the leg whose Hook leads, for a resolved pair
    angle: str = ""  # the flex slot's Angle, or a change's new Angle number
    earned: bool = False  # whether an Angle earned the flex slot
    asked: bool = False  # whether the Weekly Read session was due to write its new Angle this run
    problem: str = ""  # why its proposal cannot be filed this run
    filed: str = ""  # the proposal filed for it this run
    already: str = ""  # why nothing is filed for it this run: the package already says what it would

    @property
    def label(self) -> str:
        return {
            KILL: f"the kill of {self.key}",
            CHANGE: f"the change of {self.key}",
            PAIR: f"{self.key} resolved",
            FLEX: "the flex slot",
        }[self.kind]


@dataclass
class Plan:
    """The package changes owed this run, and the package files they edit, as the run read them before the sessions."""

    product: str
    window: int  # the window in force
    paths: dict[str, str] = field(default_factory=dict)  # by role: calendar, angles, pairs, creative_log
    texts: dict[str, str] = field(default_factory=dict)
    owed: list[Owed] = field(default_factory=list)
    passed: list[Owed] = field(default_factory=list)  # approved flex decisions of another window, owed no more

    def words(self) -> list[Owed]:
        """The changes whose new Angle the Weekly Read session was due to write this run, as worked out before it."""
        return [found for found in self.owed if found.asked]


@dataclass
class Outcome:
    """What the take-in did: the proposals filed, by decision, and every new Angle file it refused."""

    filed: list[tuple[str, str]] = field(default_factory=list)
    set_aside: list[tuple[str, list[str]]] = field(default_factory=list)


@dataclass(frozen=True)
class Withdrawn:
    """An open flex-slot proposal taken off the queue, since its window is no longer the one in force."""

    proposal: str
    decision: str
    window: int  # the flex slot's window, as its decision item names it
    in_force: int


# Which decisions owe a change.


def kind_of(line: Mapping[str, object]) -> str | None:
    """The change a decision line owes once approved, or None when it owes none."""
    section, decision, result = line.get("section"), line.get("decision"), line.get("result")
    if section == weekly_read.ANGLE:
        return {"kill": KILL, "change": CHANGE}.get(str(decision))
    if section == weekly_read.PAIR:
        return PAIR if result == weekly_read.RESOLVED and line.get("leads") in ("A", "B") else None
    if section == weekly_read.FLEX:
        return FLEX
    return None


def owed(ledger: Ledger) -> list[Owed]:
    """Every approved Weekly Read decision that owes a package change and has none filed yet, oldest first, but a
    flex slot that a run already found its window passed for."""
    filed = {str(entry.get("origin")) for entry in ledger.entries.values() if entry.get("origin")}
    found = []
    for entry in sorted(ledger.entries.values(), key=lambda entry: str(entry["id"])):
        line = entry.get("line")
        if entry["kind"] != weekly_read.KIND or entry["status"] != APPROVED or not isinstance(line, dict):
            continue
        kind = kind_of(line)
        if kind is None or origin(str(entry["id"])) in filed or PASSED in entry:
            continue
        try:
            read_date = date.fromisoformat(str(entry.get("read_date")))
        except ValueError:
            read_date = None
        found.append(
            Owed(
                str(entry["id"]),
                kind,
                str(entry.get("line_key")),
                str(entry["ask"]),
                int(entry.get("window") or 0),
                int(entry.get("read") or 0),
                read_date,
                leads=str(line.get("leads") or ""),
                angle=str(line.get("earned_by") or ""),
                earned=bool(line.get("earned_by")),
            )
        )
    return found


def roles(registry: Mapping) -> tuple[str, dict[str, str]] | None:
    """The Product whose Weekly Read the run reads, and the package file of each part a change edits."""
    for product in registry.get("products", []):
        package = product.get("go_to_market_package") or {}
        drafts, read = package.get("post_drafts") or {}, package.get("weekly_read") or {}
        if product.get("status") == "active" and drafts:
            paths = {
                name: str(drafts[name]) for name in ("calendar", "angles", "pairs", "brand_rules") if drafts.get(name)
            }
            if isinstance(read.get(CREATIVE_LOG), str):
                paths[CREATIVE_LOG] = read[CREATIVE_LOG]
            return str(product["name"]), paths
    return None


NEEDS = {
    KILL: (CREATIVE_LOG,),
    CHANGE: ("angles", "pairs", "brand_rules", CREATIVE_LOG),
    PAIR: ("pairs",),
    FLEX: ("calendar", "angles"),
}
# What a proposal cites when it can be read, and does without otherwise: the calendar's own kill rule.
CITES = {KILL: ("calendar",)}


def read_text(mandu: Path, relative: str) -> tuple[str | None, str]:
    """A package file's text, or why it cannot be used for an exact edit."""
    try:
        text = read_plain(mandu / relative).decode("utf-8")
    except UnicodeDecodeError:
        return None, f"`{relative}` is not UTF-8 text"
    except (OSError, UnsafeFile) as error:
        return None, f"`{relative}` could not be read ({error})"
    if "\r" in text:
        return None, f"`{relative}` has carriage returns in its line ends, so no exact edit is made to it"
    return text, ""


def prepare(ledger: Ledger, mandu: Path, registry: Mapping, window: int) -> Plan | None:
    """The package changes the Founder's approved Weekly Read decisions owe this run, with the package files they
    edit read once, before the sessions, and a change's new Angle numbered: the number after the highest in the Angle
    bank, the creative log, and every new Angle a change has proposed, so no two proposals add the same number. A flex
    slot is owed only while its window is the one in force: once another window's calendar is, its day has passed, and
    its decision is one of the plan's passed. None when no active Product has a 14-day kit."""
    found = roles(registry)
    if found is None:
        return None
    product, paths = found
    plan = Plan(product, window, paths)
    for decision in owed(ledger):
        (plan.passed if decision.kind == FLEX and decision.window != window else plan.owed).append(decision)
    unread: dict[str, str] = {}
    needed = {role for found in plan.owed for role in NEEDS[found.kind]}
    for role in sorted(needed | {role for found in plan.owed for role in CITES.get(found.kind, ())}):
        if role not in paths:
            unread[role] = f"the Product registry names no {role.replace('_', ' ')} for {product}"
            continue
        text, why = read_text(mandu, paths[role])
        if text is None:
            unread[role] = why
        else:
            plan.texts[role] = text
    claimed = [
        str(entry["weekly_change"].get("angle"))
        for entry in ledger.entries.values()
        if isinstance(entry.get("weekly_change"), dict) and entry["weekly_change"].get("angle")
    ]
    if "brand_rules" in plan.texts and brand_rules(plan.texts["brand_rules"]) is None:
        unread["brand_rules"] = f"`{paths['brand_rules']}` could not be used as the brand rules"
    bank: dict[str, kit.Angle] = {}
    if "angles" in plan.texts:
        try:
            bank = kit.parse_angles(plan.texts["angles"])
        except kit.KitError as error:
            unread["angles"] = f"`{paths['angles']}` could not be used ({error})"
    records: list = []
    if CREATIVE_LOG in plan.texts:
        _, records, why = log_records(paths[CREATIVE_LOG], plan.texts[CREATIVE_LOG])
        if why:
            unread[CREATIVE_LOG] = why
    for found in plan.owed:
        missing = [unread[role] for role in NEEDS[found.kind] if role in unread]
        if missing:
            found.problem = "; ".join(missing)
        elif found.read_date is None:
            found.problem = "its item's queue entry holds no date of its read"
        elif found.kind == CHANGE and found.key not in bank:
            found.problem = f"{found.key} is not in the Angle bank, `{paths['angles']}`"
        elif found.kind == CHANGE and len(matching(records, found.key)) != 1:
            found.problem = counted(paths[CREATIVE_LOG], found.key, len(matching(records, found.key)))
        elif found.kind == CHANGE:
            logged = [number_of(record) for record in records]
            found.angle, found.asked = next_number(list(bank) + claimed + logged), True
            claimed.append(found.angle)
    return plan


def next_number(taken: Sequence[str]) -> str:
    """The Angle number after the highest taken, as wide as the widest taken."""
    numbers = [identifier[1:] for identifier in taken if kit.ANGLE_ID.fullmatch(identifier)]
    width = max((len(number) for number in numbers), default=2)
    return f"P{max((int(number) for number in numbers), default=0) + 1:0{width}d}"


# Exact edits.


def lines_of(text: str) -> list[str]:
    return text.split("\n")


def apply(text: str, edits: Sequence[Edit]) -> str:
    for edit in edits:
        text = text.replace(edit.old, edit.new, 1)
    return text


def edit_problems(text: str, edits: Sequence[Edit]) -> list[str]:
    """Why edits cannot be filed as exact edits of this text: a text to replace that is not in it exactly once, or a
    text that would end the proposal's own section or code block."""
    problems = []
    for edit in edits:
        where = f"line {edit.line} of `{edit.path}`"
        count = text.count(edit.old)
        if count != 1:
            problems.append(f"the text at {where} appears {count} times in the file, not exactly once")
        if any(line.startswith("#") for line in lines_of(edit.old) + lines_of(edit.new)):
            problems.append(
                f"the edit at {where} holds a line that starts with #, which would end its proposal's section"
            )
        if FENCE in edit.old or FENCE in edit.new:
            problems.append(f"the edit at {where} holds {FENCE}, which would end its block in the proposal")
    return problems


def anchored(path: str, text: str, end: int, added: Sequence[str]) -> Edit | None:
    """An edit that adds lines after line `end`, counted from 0: it replaces the shortest run of lines ending there
    that appears exactly once in the file, never one holding a heading, with that run and the added lines."""
    lines = lines_of(text)
    for start in range(end, -1, -1):
        if lines[start].startswith("#"):
            return None
        old = "\n".join(lines[start : end + 1])
        if old.strip() and text.count(old) == 1:
            return Edit(path, start + 1, old, "\n".join(lines[start : end + 1] + list(added)))
    return None


def row_text(cells: Sequence[str]) -> str:
    """A table row from its cells, written as the package writes one: an empty cell is `| |`."""
    return "|" + "|".join(f" {cell.replace('|', chr(92) + '|')} " if cell else " " for cell in cells) + "|"


def log_records(path: str, text: str) -> tuple[object, list, str]:
    """The creative log's data and its list of Angle records, or why it holds none."""
    try:
        data = json.loads(text)
    except ValueError as error:
        return None, [], f"`{path}` is not JSON ({error})"
    records = data.get("angles") if isinstance(data, dict) else data
    if not isinstance(records, list):
        return None, [], f"`{path}` holds no list of Angle records"
    return data, records, ""


def number_of(record: object) -> str:
    """The Angle a creative-log record is of: its angle_id up to the first hyphen."""
    return str(record.get("angle_id", "")).split("-", 1)[0] if isinstance(record, dict) else ""


def matching(records: Sequence[object], angle: str) -> list[int]:
    """The index of each record of an Angle: its angle_id is the Angle's number, or starts with it and a hyphen."""
    return [
        index
        for index, record in enumerate(records)
        if isinstance(record, dict)
        and (record.get("angle_id") == angle or str(record.get("angle_id", "")).startswith(f"{angle}-"))
    ]


def counted(path: str, angle: str, count: int) -> str:
    return f"`{path}` has {count} records whose angle_id is {angle} or starts with {angle}-"


def id_lines(lines: Sequence[str], angle_id: object) -> list[int]:
    """Each line of the creative log, counted from 0, that is exactly a record's angle_id line for this angle_id."""
    named = re.compile(r'\s*"angle_id"\s*:\s*' + re.escape(json.dumps(angle_id)) + r"\s*,?\s*")
    return [index for index, line in enumerate(lines) if named.fullmatch(line)]


def compose_kill(path: str, text: str, angle: str, reads: Sequence[str]) -> tuple[Edit | None, str, str]:
    """The kill's edit to the creative log: from its Angle's angle_id line to its status line, the status "killed"
    and the dates of the two reads added after it. Returns the edit, or why there is none: a problem, or that the
    record already says it."""
    data, records, problem = log_records(path, text)
    if problem:
        return None, problem, ""
    matches = matching(records, angle)
    if len(matches) != 1:
        return None, counted(path, angle, len(matches)), ""
    record = records[matches[0]]
    if record.get("status") == KILLED and record.get(READS_FIELD) == list(reads):
        return None, "", f"`{path}` already marks {angle} killed on the reads of {' and '.join(reads)}"
    if READS_FIELD in record:
        return None, f"{angle}'s record in `{path}` already holds `{READS_FIELD}`", ""
    lines = lines_of(text)
    starts = id_lines(lines, record["angle_id"])
    status = re.compile(r'(\s*)"status"(\s*:\s*)"[^"\\]*"(,?)\s*')
    found = None
    if len(starts) == 1:
        found = next((index for index in range(starts[0], len(lines)) if status.fullmatch(lines[index])), None)
    if found is None:
        return None, f"{angle}'s record in `{path}` has no angle_id line followed by a status line", ""
    indent, colon, comma = status.fullmatch(lines[found]).groups()
    dates = json.dumps(list(reads))
    new = lines[starts[0] : found] + [
        f'{indent}"status"{colon}"{KILLED}",',
        f'{indent}"{READS_FIELD}"{colon}{dates}{comma}',
    ]
    edit = Edit(path, starts[0] + 1, "\n".join(lines[starts[0] : found + 1]), "\n".join(new))
    problems = edit_problems(text, [edit])
    if problems:
        return None, "; ".join(problems), ""
    expected = copy.deepcopy(data)
    target = expected["angles"] if isinstance(expected, dict) else expected
    target[matches[0]] = dict(target[matches[0]], status=KILLED, **{READS_FIELD: list(reads)})
    try:
        changed = json.loads(apply(text, [edit]))
    except ValueError:
        changed = None
    if changed != expected:
        return None, f"no exact edit of `{path}` marks {angle} killed and changes nothing else", ""
    return edit, "", ""


def brand_rules(text: str) -> lint.Rules | None:
    try:
        return lint.Rules(json.loads(text))
    except (ValueError, lint.RulesError):
        return None


def check_row(
    text: str,
    bank_text: str,
    old: str,
    number: str,
    hooks: Sequence[str],
    rules: lint.Rules | None = None,
    rules_path: str = "brand-rules.json",
) -> tuple[list[str], list[str]]:
    """The new Angle the Weekly Read session wrote for a change, as the cells of one row of the Angle bank, and every
    problem with it, each in the launcher's own words and never repeating what the file says. Its Hook is one quoted
    line that passes the brand lint, since every post of the Angle opens on it and is held to that lint."""
    rows = [line.strip() for line in text.split("\n") if line.strip()]
    if len(rows) != 1 or not rows[0].startswith("|") or not rows[0].endswith("|"):
        return [], ["the file holds exactly one line: the new Angle's row of the Angle bank, from | to |"]
    row = rows[0]
    problems = []
    if len(row) > MAX_ROW:
        problems.append(f"the row is {len(row):,} characters long; it holds at most {MAX_ROW:,}")
    if looks_like_address(row):
        problems.append("the row holds something that looks like an email address")
    if FENCE in row:
        problems.append(f"the row holds {FENCE}")
    header, rows_found = kit.table(bank_text, BANK_COLUMNS)
    cells = kit.cells(row)
    if len(cells) != len(header):
        return [], problems + [f"the row has {len(cells)} cells; the Angle bank's header has {len(header)}"]
    old_cells = next((found for _, found in rows_found if kit.cell(found, header, "ID") == old), None)
    if old_cells is None:
        return [], problems + [f"{old}, the Angle it changes, is no longer in the Angle bank"]
    for index, name in enumerate(header):
        if not cells[index]:
            problems.append(f"its {name} cell is empty")
    if kit.cell(cells, header, "ID") != number:
        problems.append(f"its ID cell must be {number}, the number the brief gives the new Angle")
    if kit.cell(cells, header, "pain") != kit.cell(old_cells, header, "pain"):
        problems.append(
            f"its pain and source cell must be {old}'s exactly as the Angle bank has it: the new Angle carries the same"
            " sourced pain"
        )
    hook_cell = kit.cell(cells, header, "Hook")
    frozen = kit.one_quote(hook_cell)
    if hook_cell and frozen is None:
        problems.append("its Hook cell must be one quoted line, the words every post of the new Angle opens on")
    if frozen and rules is not None:
        broken = sorted({found.rule for found in rules.check_one(lint.Copy("Hook", frozen, hook=True)) if found.blocks})
        problems += [f"its Hook breaks the brand rule `{rule}` of `{rules_path}`" for rule in broken]
    hook = folded(hook_cell)
    if hook and hook in {folded(found) for found in hooks}:
        problems.append(
            "its Hook is one the Angle bank or the A/B pairs already hold; a Hook belongs to exactly one Angle, so the"
            " new Angle needs a Hook of its own"
        )
    if results.platform_of(kit.cell(cells, header, "Platform")) is None:
        problems.append("its Platform cell must name TikTok or YouTube Shorts, the platform whose numbers judge it")
    return cells, problems


def folded(text: str) -> str:
    """A Hook as compared with others: without its quote marks, its case, or its spacing."""
    return " ".join(text.replace('"', " ").replace("\u201c", " ").replace("\u201d", " ").split()).casefold()


def known_hooks(bank: Mapping[str, kit.Angle], pairs: Mapping[str, kit.Pair]) -> list[str]:
    found = [angle.hook_cell for angle in bank.values()]
    found += [leg.hook for pair in pairs.values() for leg in pair.legs.values() if leg.hook]
    return found


def compose_change(path: str, text: str, cells: Sequence[str]) -> tuple[Edit | None, str]:
    """The change's edit to the Angle bank: the new Angle's row added after the bank's last row."""
    header, rows = kit.table(text, BANK_COLUMNS)
    if not rows:
        return None, f"`{path}` has no row to add the new Angle after"
    edit = anchored(path, text, rows[-1][0] - 1, [row_text(cells)])
    if edit is None:
        return None, f"no line of `{path}` that ends its Angle bank appears exactly once"
    problems = edit_problems(text, [edit])
    if problems:
        return None, "; ".join(problems)
    before, after = kit.parse_angles(text), kit.parse_angles(apply(text, [edit]))
    number = kit.cell(cells, header, "ID")
    added = after.pop(number, None)
    if after != before or added is None or kit.cells(added.row) != list(cells):
        return None, f"no exact edit of `{path}` adds {number} and changes nothing else"
    return edit, ""


def platform_name(records: Sequence[object], bank: Mapping[str, kit.Angle], platform: str) -> str | None:
    """The creative log's own name for a platform: the one its records give every Angle the bank puts on it."""
    wanted = results.platform_of(platform)
    names = {
        record["platform"]
        for record in records
        if number_of(record) in bank
        and results.platform_of(bank[number_of(record)].platform) == wanted
        and isinstance(record.get("platform"), str)
    }
    return names.pop() if len(names) == 1 else None


def compose_record(
    path: str, text: str, old: str, cells: Sequence[str], header: Sequence[str], bank: Mapping[str, kit.Angle]
) -> tuple[Edit | None, str]:
    """The change's edit to the creative log: the new Angle's record added after the last one, in the shape of the
    changed Angle's record, so a later kill of the new Angle has its record to mark. It has the changed Angle's
    record's fields in their order: its angle_id names the new Angle, its Hook and the RECORD_CELLS fields are the new
    row's, its platform is the row's as the log names it, its sourced pain is the changed Angle's as its record has
    it, and it is in no A/B pair, has no results, and has the status of an Angle no post has tested yet."""
    data, records, problem = log_records(path, text)
    if problem:
        return None, problem
    number = kit.cell(cells, header, "ID")
    matches = matching(records, old)
    if len(matches) != 1:
        return None, counted(path, old, len(matches))
    if matching(records, number):
        return None, counted(path, number, len(matching(records, number))) + ", where the new Angle needs none"
    platform = platform_name(records, bank, kit.cell(cells, header, "Platform"))
    if platform is None:
        return None, (
            f"the records of `{path}` do not name the new Angle's platform one way for the Angles the bank puts on it,"
            " so its record cannot name it"
        )
    name = re.sub(r"[^a-z0-9]+", "-", kit.cell(cells, header, "Angle").lower()).strip("-")
    record: dict[str, object] = {}
    problems = []
    for key, value in records[matches[0]].items():
        if key == "angle_id":
            record[key] = f"{number}-{name}" if value != old and name else number
        elif key == "hook":
            record[key] = kit.one_quote(kit.cell(cells, header, "Hook"))
        elif key == "platform":
            record[key] = platform
        elif key in RECORD_CELLS and kit.column_index(header, RECORD_CELLS[key]) is not None:
            record[key] = kit.cell(cells, header, RECORD_CELLS[key])
        elif key in RECORD_PAIN:
            record[key] = value
        elif key in ("ab_pair", "results"):
            record[key] = None
        elif key == "status":
            record[key] = UNTESTED
        else:
            problems.append(f"{old}'s record in `{path}` holds `{key}`, which no cell of the new Angle's row gives")
    if problems:
        return None, "; ".join(problems)
    expected = copy.deepcopy(data)
    (expected["angles"] if isinstance(expected, dict) else expected).append(record)
    lines = lines_of(text)
    for end in range(len(lines) - 1, 1, -1):
        if lines[end].strip() not in ("]", "],") or lines[end - 1].strip() != "}":
            continue
        brace, inner = lines[end - 1], lines[end - 2]
        indent = brace[: len(brace) - len(brace.lstrip())]
        step = max(len(inner) - len(inner.lstrip()) - len(indent), 1)
        added = [indent + line for line in json.dumps(record, indent=step, ensure_ascii=False).split("\n")]
        edit = Edit(path, end, "\n".join(lines[end - 1 : end + 1]), "\n".join([brace + ","] + added + [lines[end]]))
        if edit_problems(text, [edit]):
            continue
        try:
            changed = json.loads(apply(text, [edit]))
        except ValueError:
            continue
        if changed == expected:
            return edit, ""
    return None, f"no exact edit of `{path}` adds {number}'s record after the last one and changes nothing else"


def resolved_line(found: Owed) -> str:
    when = found.read_date.isoformat() if found.read_date else "date not known"
    read = f"the window {found.window} day-{found.read} Weekly Read ({when})"
    return f"- Resolved at {read}: leg {found.leads}'s Hook leads."


def compose_pair(path: str, text: str, found: Owed) -> tuple[Edit | None, str, str]:
    """The resolved pair's edit to the A/B pairs file: one line added at the end of the pair's section."""
    try:
        pairs = kit.parse_pairs(text)
    except kit.KitError as error:
        return None, f"`{path}` could not be used ({error})", ""
    pair = pairs.get(found.key)
    if pair is None:
        return None, f"`{path}` has no section for {found.key}", ""
    added = resolved_line(found)
    section = pair.text.split("\n")
    if added in section:
        return None, "", f"`{path}` already says {found.key} resolved at that read"
    end = pair.line - 1 + max(index for index, line in enumerate(section) if line.strip())
    edit = anchored(path, text, end, [added])
    if edit is None:
        return None, f"no line that ends {found.key}'s section in `{path}` appears exactly once", ""
    problems = edit_problems(text, [edit])
    if problems:
        return None, "; ".join(problems), ""
    after = kit.parse_pairs(apply(text, [edit]))
    expected = {key: pair.text for key, pair in pairs.items()}
    expected[found.key] = "\n".join(section[: end - pair.line + 2] + [added] + section[end - pair.line + 2 :])
    # Every section reads as it did, the pair's own with the line added; a line added moves the later ones down.
    if {key: (shape(pair), pair.text) for key, pair in after.items()} != {
        key: (shape(pair), expected[key]) for key, pair in pairs.items()
    }:
        return None, f"no exact edit of `{path}` adds that line to {found.key}'s section and changes nothing else", ""
    return edit, "", ""


def shape(pair: kit.Pair) -> tuple:
    """What a pair's section says, wherever in the file it is: its Angle, platform, and each leg's Hook line."""
    return pair.angle, pair.platform, tuple((leg, found.hook, found.text) for leg, found in sorted(pair.legs.items()))


def flex_cell(found: Owed, angle: str) -> str:
    if found.earned:
        return f"{angle} (flex slot: earned at the window {found.window} day-7 Weekly Read; a double-down re-cut)"
    return f"{angle} (flex slot: not earned at the window {found.window} day-7 Weekly Read, so the row's own Angle)"


def compose_flex(
    path: str, text: str, found: Owed, bank: Mapping[str, kit.Angle], angles_path: str
) -> tuple[Edit | None, str, str]:
    """The flex slot's edit to the calendar: its row names the Angle that earned it, or the one Angle the row names
    for when none did, on that Angle's own platform in the Angle bank. Returns the edit and the Angle, or why there is
    no edit."""
    try:
        days = kit.parse_calendar(text)
        header, rows = kit.table(text, CALENDAR_COLUMNS)
    except kit.KitError as error:
        return None, "", f"`{path}` could not be used ({error})"
    open_days = [day for day in days.values() if day.angle is None]
    if len(open_days) != 1:
        return None, "", f"`{path}` has {len(open_days)} rows whose Angle the calendar decides later, not one"
    day = open_days[0]
    named = sorted(set(re.findall(r"\bP\d+\b", day.cell)))
    angle = found.angle if found.earned else named[0] if len(named) == 1 else ""
    if not angle:
        return None, "", f"day {day.day}'s row in `{path}` names {len(named)} Angles for when none earns it, not one"
    if angle not in bank:
        return None, angle, f"{angle} is not in the Angle bank, `{angles_path}`, so its platform is not known"
    cells = list(next(found_cells for line, found_cells in rows if line == day.line))
    cells[kit.column_index(header, "Angle")] = flex_cell(found, angle)
    cells[kit.column_index(header, "platform")] = bank[angle].platform
    edit = Edit(path, day.line, day.row, row_text(cells))
    problems = edit_problems(text, [edit])
    if problems:
        return None, angle, "; ".join(problems)
    after = kit.parse_calendar(apply(text, [edit]))
    moved = after.pop(day.day, None)
    kept = {number: other for number, other in days.items() if number != day.day}
    if (
        after != kept
        or moved is None
        or (moved.angle, moved.pair, moved.primary) != (angle, None, bank[angle].platform)
    ):
        return None, angle, f"no exact edit of `{path}` puts {angle} in day {day.day} and changes nothing else"
    return edit, angle, ""


# The proposal.


def render_edit(edit: Edit) -> list[str]:
    where = f"line {edit.line} is" if edit.last == edit.line else f"lines {edit.line} to {edit.last} are"
    return [
        f"In `{edit.path}`, {where} this text, which appears exactly once in the file:",
        "",
        FENCE,
        edit.old,
        FENCE,
        "",
        "Replace it with this text:",
        "",
        FENCE,
        edit.new,
        FENCE,
    ]


def decided_line(found: Owed) -> str:
    return f'You approved `{found.item}`, "{found.ask}".'


def evidence_lines(found: Owed, memo: str) -> list[str]:
    return [
        f"- Your approved decision: `{'/'.join(DECISIONS)}/{found.item}.json`",
        f"- Its Weekly Read decision item: `review-queue/items/{found.item}.md`",
        f"- The memo it came from: `{memo}`",
    ]


def memo_of(found: Owed) -> str:
    return f"{weekly_read.FOLDER}/window-{found.window}-read-{found.read:02d}.md"


def rule_line(text: str) -> int | None:
    """The line of the calendar that says a killed Angle's status flips in the creative log, when it has one."""
    for number, line in enumerate(text.split("\n"), start=1):
        lowered = line.lower()
        if "creative-log.json" in lowered and "killed" in lowered:
            return number
    return None


def item_for(found: Owed, plan: Plan, edits: Sequence[Edit], extra: Sequence[str] = ()) -> exchange.Item:
    """The package-change proposal one decision owes, with its exact edits: one, or a change's two."""
    paths, edit = plan.paths, edits[0]
    lead = [decided_line(found)]
    evidence = evidence_lines(found, memo_of(found))
    new_angle = "no"
    if found.kind == KILL:
        first, second = reads_of(found)
        title = f"Approve package change: mark {found.key} killed in the creative log"
        lead.append(
            f"This marks {found.key} killed in `{paths[CREATIVE_LOG]}`, as the package's own kill rule says, with the"
            f" dates of the two Weekly Reads at or under its kill criterion: the window {found.window} day-7 read,"
            f" {first}, and its day-14 read, {second}."
        )
        lead.append(f"{found.key}'s row in `{paths.get('angles', 'the Angle bank')}` is not changed.")
        if "calendar" in plan.texts and rule_line(plan.texts["calendar"]):
            evidence.append(
                f"- The package's rule for a kill: `{paths['calendar']}` line {rule_line(plan.texts['calendar'])}"
            )
        evidence.append(f"- {found.key}'s record: `{paths[CREATIVE_LOG]}` line {edit.line}")
    elif found.kind == CHANGE:
        title = f"Approve package change: add {found.angle}, a new Angle in place of {found.key}"
        new_angle = "yes"
        lead.append(
            "A changed Hook, signal, or kill criterion enters only as a new Angle (FR-7), so this adds"
            f" {found.angle} to the Angle bank after its last row, with {found.key}'s pain and source as they are;"
            " its other cells are the Weekly Read session's words."
        )
        lead += list(extra)
        lead.append(
            f"It also adds {found.angle}'s record to `{paths[CREATIVE_LOG]}` after the last one, in the shape of"
            f" {found.key}'s record: {found.key}'s pain as its record has it, {found.angle}'s own cells, no A/B pair,"
            f' no results, and the status "{UNTESTED}", so a later kill of {found.angle} has its record to mark.'
            " Approving this applies both edits."
        )
        lead.append(
            f"{found.key} stays as it is: it did not meet its kill criterion, so it is not killed."
            " Which Angle a later window tests is for that window's calendar to say."
        )
        evidence.append(
            f"- {found.key}'s row, whose pain and source {found.angle} carries: `{paths['angles']}` line"
            f" {kit.parse_angles(plan.texts['angles'])[found.key].line}"
        )
        _, records, _ = log_records(paths[CREATIVE_LOG], plan.texts[CREATIVE_LOG])
        (index,) = matching(records, found.key)
        starts = id_lines(lines_of(plan.texts[CREATIVE_LOG]), records[index]["angle_id"])
        where = f" line {starts[0] + 1}" if len(starts) == 1 else ""
        evidence.append(f"- {found.key}'s record, whose shape {found.angle}'s takes: `{paths[CREATIVE_LOG]}`{where}")
    elif found.kind == PAIR:
        title = f"Approve package change: record {found.key} as resolved, leg {found.leads}'s Hook leading"
        lead.append(
            f"This adds one line at the end of {found.key}'s section in `{paths['pairs']}`, saying that leg"
            f" {found.leads}'s Hook leads."
        )
        lead.append(
            "No Hook changes, in the A/B pairs file or the Angle bank: a changed Hook would be a new Angle (FR-7)."
        )
        pair = kit.parse_pairs(plan.texts["pairs"])[found.key]
        evidence.append(f"- {found.key}'s section: `{paths['pairs']}` line {pair.line}")
    else:
        bank = kit.parse_angles(plan.texts["angles"])
        title = f"Approve package change: put {found.angle} in the calendar's flex slot"
        how = (
            f"The day-7 Weekly Read gave the flex slot to {found.angle}, which cleared its signal."
            if found.earned
            else f"No Angle earned the flex slot at the day-7 Weekly Read, so this puts in it {found.angle}, the Angle"
            " its row names for that case."
        )
        lead.append(how)
        lead.append(
            f"This puts {found.angle} in the flex slot's row of `{paths['calendar']}`, on {found.angle}'s own"
            f" platform in the Angle bank, {bank[found.angle].platform}; until the row names an Angle, gr0wthlab"
            " prepares no Draft for that day."
        )
        evidence.append(f"- The flex slot's row: `{paths['calendar']}` line {edit.line}")
        evidence.append(f"- {found.angle}'s row, for its platform: `{paths['angles']}` line {bank[found.angle].line}")
    body = list(lead)
    for one in edits:
        body += [""] + render_edit(one)
    fields = {"kind": "package-change-proposal", "product": plan.product, "new_angle": new_angle}
    touches = "\n".join(f"- `{one.path}`" for one in edits)
    return exchange.Item(fields, title[: exchange.MAX_TITLE], "\n".join(body), touches, "\n".join(evidence))


def reads_of(found: Owed) -> tuple[str, str]:
    """The dates of the two Weekly Reads of a kill: the window's day-7 read and the day-14 read it was decided at."""
    day_14 = found.read_date or date.min
    return (day_14 - timedelta(days=max(results.READS) - min(results.READS))).isoformat(), day_14.isoformat()


# Taking in, and filing.


def changed_cells(old: Sequence[str], new: Sequence[str], header: Sequence[str]) -> list[str]:
    """The cells of the new Angle that differ from the Angle it changes, by their column names; its number always
    does."""
    return [name for index, name in enumerate(header) if name != "ID" and old[index] != new[index]]


def take(
    plan: Plan,
    areas: Areas,
    store: Store,
    ledger: Ledger,
    products: Sequence[str],
    run_id: str,
    now: datetime,
    seen: dict[str, str],
    publish: bool = True,
) -> Outcome:
    """File the proposal each owed decision's edit makes this run, once the last session has ended; a change's new
    Angle is the file the Weekly Read session wrote for it, checked here. Every file in the changes folder is removed
    once read, and one that is refused leaves only its name and the reasons. Each approved flex decision whose window
    passed is marked so, so no later run reports it again. With publish off nothing is written or removed, and the
    outcome says what a run would do."""
    outcome = Outcome()
    folder = areas.path("weekly_reads", FOLDER)
    words = {found.item: found for found in plan.words()}
    files: dict[str, Path] = {}
    if areas.real_folder(folder):
        for path in list(areas.files(folder)):
            name = areas.relative(path)[len(f"weekly-reads/{FOLDER}/") :]
            decision = name[: -len(".md")] if name.endswith(".md") and "/" not in name else ""
            if decision in words:
                files[decision] = path
                continue
            outcome.set_aside.append(
                (name, ["it names no change decision the brief asked a new Angle for; name it <decision item>.md"])
            )
            if publish:
                areas.remove(path)
    for found in plan.passed:
        if publish:
            ledger.entries[found.item][PASSED] = plan.window
    for found in plan.owed:
        if found.problem:
            continue
        edit, problem, already, extra = None, "", "", []
        if found.kind == KILL:
            edit, problem, already = compose_kill(
                plan.paths[CREATIVE_LOG], plan.texts[CREATIVE_LOG], found.key, reads_of(found)
            )
            edits = [edit] if edit else []
        elif found.kind == PAIR:
            edit, problem, already = compose_pair(plan.paths["pairs"], plan.texts["pairs"], found)
            edits = [edit] if edit else []
        elif found.kind == FLEX:
            bank = kit.parse_angles(plan.texts["angles"])
            edit, found.angle, problem = compose_flex(
                plan.paths["calendar"], plan.texts["calendar"], found, bank, plan.paths["angles"]
            )
            edits = [edit] if edit else []
        else:
            edits, problem, extra = take_change(found, plan, areas, files.get(found.item), outcome, publish)
        if already:
            found.already = already
            continue
        if not edits:
            found.problem = problem
            continue
        item = item_for(found, plan, edits, extra)
        check = exchange.check_item(
            exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence), products
        )
        if check.item is None:
            found.problem = f"its proposal is not a valid item ({'; '.join(check.problems)})"
            continue
        fingerprint = exchange.item_hash(check.item)
        if fingerprint in seen:
            found.problem = f"its proposal would ask the same as `{seen[fingerprint]}`"
            continue
        identifier = f"{found.kind}-{found.key.lower()}"
        if publish:
            mark = {"decision": found.item, "kind": found.kind}
            if found.kind == CHANGE:
                mark["angle"] = found.angle
            identifier = ledger.publish(
                store,
                check.item,
                f"weekly-read-{found.kind}" + ("" if found.kind == FLEX else f"-{found.key.lower()}"),
                run_id,
                now,
                extra={"weekly_change": mark},
                origin=origin(found.item),
            )
        seen[fingerprint] = identifier
        found.filed = identifier
        outcome.filed.append((found.item, identifier))
    if publish and areas.real_folder(folder):
        areas.remove_empty_folders(folder)
    return outcome


def take_change(
    found: Owed, plan: Plan, areas: Areas, path: Path | None, outcome: Outcome, publish: bool
) -> tuple[list[Edit], str, list[str]]:
    """The change's two edits, to the Angle bank and the creative log, from the new Angle the Weekly Read session
    wrote, which is removed once read."""
    name = f"{found.item}.md"
    if path is None:
        return [], f"no new Angle was written for it at `weekly-reads/{FOLDER}/{name}`", []
    try:
        text = read_plain(path).decode("utf-8")
    except (OSError, UnsafeFile, UnicodeDecodeError) as error:
        text, unreadable = None, f"unreadable: {error}"
    if publish:
        areas.remove(path)
    if text is None:
        outcome.set_aside.append((name, [unreadable]))
        return [], f"its new Angle, `weekly-reads/{FOLDER}/{name}`, was set aside", []
    bank_text = plan.texts["angles"]
    bank = kit.parse_angles(bank_text)
    try:
        pairs = kit.parse_pairs(plan.texts["pairs"])
    except kit.KitError:
        pairs = {}
    rules = brand_rules(plan.texts.get("brand_rules", ""))
    hooks = known_hooks(bank, pairs)
    cells, problems = check_row(
        text, bank_text, found.key, found.angle, hooks, rules, plan.paths.get("brand_rules", "")
    )
    header, _ = kit.table(bank_text, BANK_COLUMNS)
    edits: list[Edit] = []
    if not problems:
        edit, problem = compose_change(plan.paths["angles"], bank_text, cells)
        problems += [problem] if problem else []
        edits += [edit] if edit else []
    if not problems:
        edit, problem = compose_record(
            plan.paths[CREATIVE_LOG], plan.texts[CREATIVE_LOG], found.key, cells, header, bank
        )
        problems += [problem] if problem else []
        edits += [edit] if edit else []
    if problems:
        outcome.set_aside.append((name, problems))
        return [], f"its new Angle, `weekly-reads/{FOLDER}/{name}`, was set aside", []
    changed = changed_cells(kit.cells(bank[found.key].row), cells, header)
    return edits, "", [f"Its cells that differ from {found.key}'s: {', '.join(changed)}."] if changed else []


def withdraw(ledger: Ledger, window: int, run_id: str, now: datetime) -> list[Withdrawn]:
    """Before the run takes in the Founder's decisions: take off the queue each open flex-slot proposal whose window,
    the one its decision item names, is no longer the window in force, since its flex slot's day has passed and its
    edit would fill another window's. A decision on it, given before or after, is kept on it as on any superseded
    item, and Mandu never acts on it; superseded_by names the run's notice, which says why, once that is queued
    (name_notice). A proposal whose decision item is not in the queue stands."""
    found = []
    for entry in sorted(ledger.open_entries(), key=lambda entry: str(entry["id"])):
        mark = entry.get("weekly_change")
        if entry["kind"] != "package-change-proposal" or not isinstance(mark, dict) or mark.get("kind") != FLEX:
            continue
        decision = ledger.entries.get(str(mark.get("decision")))
        if decision is None or not isinstance(decision.get("window"), int) or decision["window"] == window:
            continue
        ledger.close(entry, SUPERSEDED, run_id, now, superseded_by="", withdrawn=True)
        found.append(Withdrawn(str(entry["id"]), str(decision["id"]), int(decision["window"]), window))
    return found


def name_notice(ledger: Ledger, withdrawn: Sequence[Withdrawn], notice: str | None) -> None:
    """Name the run's notice as what replaced each flex-slot proposal the run withdrew."""
    for found in withdrawn:
        ledger.entries[found.proposal]["superseded_by"] = notice or ""


# What the brief, the run report, and the Weekly Read row say.


def gaps(plan: Plan | None, problem: str, session_gap: str) -> list[str]:
    """Why the package changes owed are not all filed this run: each one's own reason, and the Weekly Read session's
    falling short while it was due for a new Angle, whatever it had written by then."""
    if plan is None:
        return [problem] if problem else []
    found_gaps = [session_gap] if session_gap and plan.words() else []
    found_gaps += [
        f"no package-change proposal for {found.label} (`{found.item}`): {found.problem}"
        for found in plan.owed
        if found.problem
    ]
    return found_gaps


def summary(plan: Plan | None) -> str:
    if plan is None or not plan.owed:
        return ""
    filed = sum(1 for found in plan.owed if found.filed)
    return f"package-change proposals owed by approved decisions: {filed} of {len(plan.owed)} filed"


def passed_why(found: Owed, in_force: int) -> str:
    return (
        f"window {found.window} is no longer the window in force (window {in_force} is), so its flex slot's day has"
        " passed"
    )


def withdrawn_why(found: Withdrawn) -> str:
    return (
        f"window {found.window} is no longer the window in force (window {found.in_force} is), so its flex slot's day"
        " has passed and approving it would fill another window's"
    )


def report_lines(
    plan: Plan | None, outcome: Outcome | None, problem: str, withdrawn: Sequence[Withdrawn] = ()
) -> list[str]:
    """The run report's lines on the package changes the Founder's approved Weekly Read decisions owe, and on the
    flex-slot decisions and proposals whose window passed."""
    lines = [f"- Package changes from approved decisions: not worked out: {problem}."] if problem else []
    owing = plan.owed if plan is not None and not problem else []
    passed = plan.passed if plan is not None and not problem else []
    set_aside = outcome.set_aside if outcome is not None and not problem else []
    if not owing and not passed and not set_aside and not withdrawn:
        return lines
    lines.append(
        "- Package changes from approved decisions, each a package-change proposal for the Founder to approve:"
    )
    for found in owing:
        if found.filed:
            state = f"filed as `{found.filed}`"
        elif found.already:
            state = f"nothing to file: {found.already}"
        else:
            state = f"not filed this run: {found.problem}"
        lines.append(f"  - {found.label}, `{found.item}`: {state}.")
    for found in passed:
        why = passed_why(found, plan.window)
        lines.append(f"  - {found.label}, `{found.item}`: nothing filed, now or later: {why}.")
    for gone in withdrawn:
        why = withdrawn_why(gone)
        lines.append(f"  - the flex slot, `{gone.decision}`: its proposal `{gone.proposal}` was withdrawn: {why}.")
    for name, reasons in set_aside:
        lines.append(f"  - `weekly-reads/{FOLDER}/{name}` was set aside, and removed: {'; '.join(reasons)}.")
    return lines


def notice_section(
    plan: Plan | None, outcome: Outcome | None, day: str, withdrawn: Sequence[Withdrawn] = ()
) -> tuple[int, str, str] | None:
    """The notice's part for an approved decision whose package change could not be filed this run, a flex-slot
    decision or proposal whose window passed, and a new Angle the launcher refused, each in the launcher's own
    words."""
    missing = [found for found in plan.owed if found.problem] if plan is not None else []
    passed = plan.passed if plan is not None else []
    refused = outcome.set_aside if outcome is not None else []
    if not missing and not passed and not refused and not withdrawn:
        return None
    lines = []
    if missing:
        lines.append(
            "Approving these Weekly Read decisions changes no package file by itself; the package-change proposal each"
            " owes, with its exact edit, could not be filed this run, and the next run tries again:"
        )
        lines += [f"- {found.label}, `{found.item}`: {found.problem}" for found in missing]
    if passed:
        lines.append(
            "These approved flex-slot decisions file no package-change proposal, now or at a later run, and the"
            " calendar is not changed for them:"
        )
        lines += [f"- {found.label}, `{found.item}`: {passed_why(found, plan.window)}" for found in passed]
    if withdrawn:
        lines.append(
            "These open flex-slot proposals were withdrawn, so approving one changes nothing, and Mandu never applies"
            " it:"
        )
        lines += [f"- `{gone.proposal}`, for `{gone.decision}`: {withdrawn_why(gone)}" for gone in withdrawn]
    if refused:
        lines.append("These new Angles the Weekly Read session wrote were set aside and removed, so none was filed:")
        lines += [f"- `weekly-reads/{FOLDER}/{name}`: {'; '.join(reasons)}" for name, reasons in refused]
    owing = {f"{found.item}.md" for found in missing}
    count = len(missing) + len(passed) + len(withdrawn) + sum(1 for name, _ in refused if name not in owing)
    return count, f"package changes from approved Weekly Read decisions not filed on {day}", "\n".join(lines)


def brief_lines(plan: Plan, workspace: Path, mandu: Path, ledger: Path, check: str) -> list[str]:
    """The Weekly Read session's section on the new Angles its approved change decisions ask for."""
    lines = [
        "## New Angles for approved change decisions",
        "",
        "The Founder approved these change decisions.",
        "A changed Hook, signal, or kill criterion enters only as a new Angle (FR-7), so write each new Angle as one"
        ' row of the Angle bank, as "Writing a new Angle" in your task definition describes.',
        f"The Angle bank: `{mandu / plan.paths['angles']}`; the A/B pairs: `{mandu / plan.paths['pairs']}`; the brand"
        f" rules every post's Hook is held to: `{mandu / plan.paths['brand_rules']}`.",
        "",
    ]
    bank = kit.parse_angles(plan.texts["angles"])
    for found in plan.words():
        lines.append(
            f"- `{found.item}`, {found.ask}: the decision item is"
            f" `{ledger / 'review-queue' / 'items' / found.item}.md`."
            f" {found.key} is line {bank[found.key].line} of the Angle bank."
            f" Write the new Angle as {found.angle} in `{workspace / 'weekly-reads' / FOLDER / found.item}.md`."
        )
    if check:
        lines += ["", f"Check each with `{check}`."]
    return lines


def plan_record(plan: Plan) -> dict[str, object]:
    """What the launcher worked out before the sessions, for check-work: each change owed a new Angle, and its
    number."""
    return {
        "product": plan.product,
        "window": plan.window,
        "paths": dict(plan.paths),
        "words": [
            {"item": found.item, "key": found.key, "angle": found.angle, "ask": found.ask} for found in plan.words()
        ],
    }


def restore(record: Mapping, mandu: Path) -> tuple[Plan, list[str]]:
    """The plan as the launcher recorded it, with the package files a change edits or is checked against read
    again."""
    plan = Plan(str(record.get("product", "")), int(record.get("window") or 0), dict(record.get("paths") or {}))
    notes = []
    for role in NEEDS[CHANGE]:
        if role not in plan.paths:
            continue
        text, why = read_text(mandu, plan.paths[role])
        if text is None:
            notes.append(why)
        else:
            plan.texts[role] = text
    for word in record.get("words") or []:
        plan.owed.append(
            Owed(
                str(word["item"]),
                CHANGE,
                str(word["key"]),
                str(word.get("ask", "")),
                0,
                0,
                None,
                angle=str(word["angle"]),
                asked=True,
            )
        )
        if notes:
            plan.owed[-1].problem = "; ".join(notes)
    return plan, notes
