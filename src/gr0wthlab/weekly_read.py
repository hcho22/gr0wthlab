"""The Weekly Read memo (US-ME12): the agent's judgment of each Angle under `read-the-results.md`, the launcher's checks
of it, the memo the Founder reads, and one Weekly Read decision item for each of its decision lines.

The rules are the package's: `read-the-results.md` is the only rule source, and the agent reads and applies it. The
launcher holds the agent to what it can check without restating a rule, from the PRD's own words, the kit, and the
Founder's numbers (results.py):

- every Angle with a post the read covers has exactly one line, every pair with both legs covered one at the day-14
  read, the day-7 read one line on the flex slot, and every line ends in keep, kill, change, or test;
- nothing is killed at day 7, and a kill needs the Angle at risk at the read before (two consecutive Weekly Reads);
- an Angle none of whose posts reached the floor on the platform that judges it is "insufficient data", never a pass
  or a fail; the floor is read-the-results.md's own figure, counted in views (results.FLOOR_COUNTS);
- the flex slot goes only to an Angle whose line says it cleared its signal, never to one that merely ranked first;
- a pair is resolved only when both legs reached the floor;
- every number the agent writes has its n beside it, every unread or at-risk Angle and every pair to repost says what
  would settle it at the next read, and every comment quoted is found word for word in what the Founder gave.

A memo that fails a check stays in workspace/ as the agent wrote it, like a Draft waiting for a fix, and nothing is
queued from it. One that passes becomes the memo the Founder reads (ledger/weekly-reads/), with the launcher's own
results tables, the line that says what the floor counts, what the read cannot tell, the Waitlist counts, and the
Founder's time that week; each of its decision lines becomes its own Weekly Read decision item.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from . import exchange, kit, results
from .areas import Areas, Store, UnsafeFile, read_plain
from .queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger

WORKFLOW = "weekly-read"
KIND = "weekly-read-decision"
FOLDER = "weekly-reads"  # in the agent's area and in ledger/
EVIDENCE = ("evidence", "weekly-reads")
DECISIONS = ("keep", "kill", "change", "test")
CLEARED, MISSED, AT_RISK, MET_KILL, INSUFFICIENT = (
    "cleared its signal",
    "missed its signal",
    "at risk",
    "met its kill criterion",
    "insufficient data",
)
ANGLE_RESULTS = (CLEARED, MISSED, AT_RISK, MET_KILL, INSUFFICIENT)
RESOLVED, REPOST = "resolved", "repost"
SETTLE = "What would settle it:"
NONE_LINE = "- None this read."
MAX_LINE = 1200
MAX_MEMO = 20000
ANGLE, PAIR, FLEX, PRODUCT = "Angles", "Pairs", "Flex slot", "Product"
DECISION = r" Decision: (keep|kill|change|test)"
ANGLE_LINE = re.compile(r"- (P\d+) \((days? [0-9][0-9, and]*)\): (" + "|".join(ANGLE_RESULTS) + r")\. (.+)" + DECISION)
PAIR_LINE = re.compile(r"- (AB-\d+) \((days? [0-9][0-9, and]*)\): (resolved|repost)\. (.+)" + DECISION)
FLEX_LINE = re.compile(r"- Flex slot: (earned by (P\d+)|not earned)\. (.+)" + DECISION)
PRODUCT_LINE = re.compile(r"- (.+)" + DECISION)
QUOTE_LINE = re.compile(r"  > day (\d+): \"(.+)\"")
# What a line may hold with a digit in it and no n beside it: an Angle, a pair, a day, a window, and the n itself.
IDENTIFIERS = re.compile(
    r"\bP\d+\b|\bAB-\d+\b|\b[Dd]ays? \d+(?:(?:, | and | to )\d+)*|\b[Dd]ay-\d+\b|\b[Ww]indow \d+\b"
)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
WITH_N = re.compile(r"%?(?: [A-Za-z][A-Za-z%-]*){0,4} \(n=#\)")
# The PRD's list of what is not readable by construction at this scale, which every memo restates in one line.
CANNOT_TELL = (
    "What this cannot tell you: which post drove a sign-up, since each platform allows one profile link and"
    " attribution stops at the Source; anything about installs, retention, or conversion, since no App Store listing"
    " exists; whether anyone will use the product, since resonance with scrollers is not use; and any verdict from a"
    " post under the floor."
)


def memo_name(read: results.Read) -> str:
    return f"window-{read.window}-read-{read.read:02d}.md"


def days_text(days: Sequence[int]) -> str:
    """Days as a memo line names them: day 3, days 3 and 10, days 1, 2 and 8."""
    days = sorted(days)
    if len(days) == 1:
        return f"day {days[0]}"
    return f"days {', '.join(str(day) for day in days[:-1])} and {days[-1]}"


@dataclass(frozen=True)
class Line:
    """One decision line of a memo, as the launcher parsed it."""

    section: str
    key: str  # the Angle, the pair, "flex", or "product-<n>"
    result: str
    decision: str
    text: str  # the line as the agent wrote it
    quotes: tuple[tuple[int, str], ...] = ()  # each comment quoted under it, with its day
    earned_by: str | None = None

    @property
    def ask(self) -> str:
        if self.section == FLEX:
            return f"flex slot {self.result}: {self.decision}"
        if self.section == PRODUCT:
            return f"a result that bears on the product: {self.decision}"
        return f"{self.key}, {self.result}: {self.decision}"


@dataclass
class Plan:
    """The Weekly Read this run: the read due, what the Founder gave for it, and whether its memo is due."""

    read: results.Read
    taken: results.Taken
    kit: kit.Kit | None
    paths: Mapping[str, str]  # package file paths by role: calendar, angles, pairs, read_the_results
    fingerprint: str
    why: str = ""  # why no memo is due this run, or "" when one is
    previous: dict[str, str] = field(default_factory=dict)  # the read before's result for each Angle
    open_items: list[dict] = field(default_factory=list)  # this read's open decision items

    @property
    def due(self) -> bool:
        return not self.why

    @property
    def memo(self) -> str:
        return memo_name(self.read)

    def angles(self) -> dict[str, list[int]]:
        """Each Angle with a post the read covers, and its days."""
        found: dict[str, list[int]] = {}
        for ask in self.read.asks:
            if ask.angle:
                found.setdefault(ask.angle, []).append(ask.day)
        return found

    def pairs(self) -> dict[str, list[int]]:
        """Each pair whose both legs the read covers, and its legs' days."""
        found: dict[str, list[int]] = {}
        for ask in self.read.asks:
            if ask.pair:
                found.setdefault(ask.pair, []).append(ask.day)
        return {pair: days for pair, days in found.items() if len(days) == 2}

    def readable(self, day: int) -> bool | None:
        ask = next((ask for ask in self.read.asks if ask.day == day), None)
        return results.readable(self.read, self.taken, ask) if ask else False

    def floor_state(self, day: int) -> str:
        """Whether a post is readable, and if not, why: its views under the floor, or not given. Empty when the floor
        itself is not known."""
        floor = self.readable(day)
        if floor is None:
            return ""
        if floor:
            return "readable"
        ask = next((ask for ask in self.read.asks if ask.day == day), None)
        given = self.taken.given.get((ask.platform, day)) if ask else None
        return "unread: under the floor" if given and given.value("views") is not None else "unread: views not given"

    def comments(self, day: int) -> list[str]:
        texts = []
        for (_, number), given in self.taken.given.items():
            if number == day and given.result.comments:
                texts += list(given.result.comments)
        return texts


def fingerprint(read: results.Read, taken: results.Taken) -> str:
    """What a memo is written from: each record the Founder gave for the read, and the floor."""
    given = sorted((platform, day, found.sha256) for (platform, day), found in taken.given.items())
    data = json.dumps({"given": given, "floor": read.floor, "asks": read.as_json()["asks"]}, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def read_items(ledger: Ledger, read: results.Read) -> list[dict]:
    return [
        entry
        for entry in ledger.entries.values()
        if entry["kind"] == KIND and entry.get("window") == read.window and entry.get("read") == read.read
    ]


def kept(store: Store, window: int, read: int) -> dict | None:
    """The launcher's record of a read's memo, when one was composed and can be read."""
    try:
        data = json.loads(read_plain(store.path(*EVIDENCE, f"window-{window}-read-{read:02d}.json")).decode("utf-8"))
    except (OSError, UnsafeFile, ValueError):
        return None
    return data if isinstance(data, dict) else None


def plan(
    read: results.Read,
    taken: results.Taken,
    parsed: kit.Kit | None,
    paths: Mapping[str, str],
    store: Store,
    ledger: Ledger,
) -> Plan:
    """Whether the read's memo is due this run: the Founder has given numbers for it, the memo was not yet written
    from exactly those, and he has decided none of its items. The memo is written again when he gives more numbers
    or corrects one while its items are all still open."""
    found = Plan(read, taken, parsed, paths, fingerprint(read, taken))
    earlier = kept(store, read.window, min(results.READS)) if read.read != min(results.READS) else None
    if earlier:
        found.previous = {
            str(line.get("key")): str(line.get("result"))
            for line in earlier.get("lines") or []
            if isinstance(line, dict)
        }
    items = read_items(ledger, read)
    found.open_items = [entry for entry in items if entry["status"] == OPEN]
    decided = [entry for entry in items if entry["status"] in (APPROVED, REJECTED) or entry.get("decided")]
    record = kept(store, read.window, read.read)
    if taken.failure:
        found.why = f"the Founder's results could not be read ({taken.failure})"
    elif not read.asks:
        found.why = f"nothing could be asked for the {read.name}"
    elif not taken.given:
        found.why = f"no numbers have been given for the {read.name} yet; the Founder gives them on the sitting page"
    elif decided:
        found.why = f"the Founder has decided items of the {read.name}, so its memo stands as it is"
    elif record is not None and record.get("fingerprint") == found.fingerprint:
        found.why = f"the {read.name} memo was written from the numbers given so far"
    return found


# The memo's checks.


def bare_numbers(text: str) -> list[str]:
    """Each number in a line with no n beside it: a quote, an Angle, a pair, a day, and a window are not counted."""
    masked = re.sub(r'"[^"]*"', lambda match: '"' + "x" * (len(match.group(0)) - 2) + '"', text)
    masked = IDENTIFIERS.sub(lambda match: "x" * len(match.group(0)), masked)
    masked = re.sub(r"\(n=\d+\)", "(n=#)", masked)
    found = []
    for match in NUMBER.finditer(masked):
        if not WITH_N.match(masked, match.end()):
            found.append(match.group(0))
    return found


def parse(text: str, found: Plan) -> tuple[list[Line], list[str]]:
    """The memo's decision lines, and every problem with its shape, each naming a line by its section and place and
    never repeating what it says."""
    read = found.read
    problems: list[str] = []
    if len(text) > MAX_MEMO:
        problems.append(f"the memo is {len(text):,} characters long; it holds at most {MAX_MEMO:,}")
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    title = f"# Weekly Read, window {read.window}, day {read.read}"
    if not lines or lines[0].strip() != title:
        problems.append(f"the first line must be the title `{title}`")
        return [], problems
    sections = [ANGLE] + ([PAIR] if read.read == max(results.READS) else []) + ([FLEX] if read.read == 7 else [])
    sections.append(PRODUCT)
    headings = [line[3:].strip() for line in lines if line.startswith("## ")]
    if headings != sections:
        problems.append(f"the sections must be {', '.join(f'`## {name}`' for name in sections)}, in that order")
        return [], problems
    parsed: list[Line] = []
    section, place, product = "", 0, 0
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if raw.startswith("## "):
            section, place = raw[3:].strip(), 0
            continue
        quote = QUOTE_LINE.fullmatch(raw.rstrip())
        if quote:
            if not parsed or parsed[-1].section != ANGLE or section != ANGLE:
                problems.append(f"{section} has a quoted comment that is not under an Angle's line")
                continue
            last = parsed[-1]
            parsed[-1] = Line(
                last.section,
                last.key,
                last.result,
                last.decision,
                last.text,
                last.quotes + ((int(quote.group(1)), quote.group(2)),),
                last.earned_by,
            )
            continue
        place += 1
        where = f"{section} line {place}"
        line = raw.rstrip()
        if len(line) > MAX_LINE:
            problems.append(f"{where} is longer than {MAX_LINE} characters")
            continue
        if section == PRODUCT and line == NONE_LINE:
            continue
        if section == ANGLE:
            match = ANGLE_LINE.fullmatch(line)
            if not match:
                problems.append(
                    f"{where} does not read `- P<n> (day <n>): <result>. <why> Decision: <keep|kill|change|test>`,"
                    f" with the result one of: {', '.join(ANGLE_RESULTS)}"
                )
                continue
            parsed.append(Line(ANGLE, match.group(1), match.group(3), match.group(5), line))
            days = [int(day) for day in re.findall(r"\d+", match.group(2))]
            expected = found.angles().get(match.group(1))
            if expected is not None and sorted(days) != sorted(expected):
                problems.append(f"{where} ({match.group(1)}) must name {days_text(expected)}, its posts in this read")
        elif section == PAIR:
            match = PAIR_LINE.fullmatch(line)
            if not match:
                problems.append(
                    f"{where} does not read `- AB-<n> (days <n> and <n>): <resolved|repost>. <why> Decision: ...`"
                )
                continue
            parsed.append(Line(PAIR, match.group(1), match.group(3), match.group(5), line))
        elif section == FLEX:
            match = FLEX_LINE.fullmatch(line)
            if not match:
                problems.append(
                    f"{where} does not read `- Flex slot: <earned by P<n>|not earned>. <why> Decision: ...`"
                )
                continue
            result = "earned" if match.group(2) else "not earned"
            parsed.append(Line(FLEX, "flex", result, match.group(4), line, earned_by=match.group(2)))
        else:
            match = PRODUCT_LINE.fullmatch(line)
            if not match:
                problems.append(f"{where} does not end in `Decision: <keep|kill|change|test>`, nor read `{NONE_LINE}`")
                continue
            product += 1
            parsed.append(Line(PRODUCT, f"product-{product}", "observed", match.group(2), line))
    return parsed, problems


def check(text: str, found: Plan) -> tuple[list[Line], list[str]]:
    """Parse the memo and hold it to every rule the launcher can check; the lines, and every problem."""
    lines, problems = parse(text, found)
    if not lines and problems:
        return lines, problems
    read = found.read
    angles = found.angles()
    by_angle: dict[str, list[Line]] = {}
    for line in lines:
        if line.section == ANGLE:
            by_angle.setdefault(line.key, []).append(line)
    for angle in sorted(angles):
        if len(by_angle.get(angle, [])) != 1:
            problems.append(f"{angle} needs exactly one line under Angles; it has {len(by_angle.get(angle, []))}")
    for angle in sorted(set(by_angle) - set(angles)):
        problems.append(f"{angle} has no post this read covers, so it has no line here")
    for line in lines:
        name = line.key if line.section != PRODUCT else f"Product line {line.key.split('-')[1]}"
        if read.read == min(results.READS) and (line.decision == "kill" or line.result == MET_KILL):
            problems.append(f"{name}: nothing can be killed at day {read.read}; it may only be flagged at risk")
        if line.section == ANGLE:
            if line.decision == "kill" and line.result != MET_KILL:
                problems.append(f"{name}: a kill needs the result `{MET_KILL}`")
            if line.result == MET_KILL and read.read != min(results.READS):
                before = found.previous.get(line.key)
                if before != AT_RISK:
                    was = f"was `{before}`" if before else "had no line"
                    problems.append(
                        f"{name}: a kill needs two consecutive Weekly Reads at or under the criterion, and at the"
                        f" day-{min(results.READS)} read it {was}, not `{AT_RISK}`"
                    )
            days = angles.get(line.key, [])
            readable = [found.readable(day) for day in days]
            if read.floor is not None and days and not any(readable) and line.result != INSUFFICIENT:
                problems.append(
                    f"{name}: none of its posts reached the floor of {read.floor} views on the platform that judges it,"
                    f" so its result is `{INSUFFICIENT}`"
                )
            for day, quote in line.quotes:
                if day not in days:
                    problems.append(
                        f"{name}: a comment quoted under it is from day {day}, which is not one of its posts"
                    )
                elif not any(quote in comment for comment in found.comments(day)):
                    problems.append(
                        f"{name}: a comment quoted under it from day {day} is not, word for word, in what the Founder"
                        " gave for that post"
                    )
        if line.section == PAIR:
            legs = found.pairs().get(line.key)
            if legs is None:
                problems.append(f"{name} does not have both legs in this read, so it has no line here")
            elif line.result == RESOLVED and not all(found.readable(day) for day in legs):
                problems.append(
                    f"{name}: a pair resolves only when both legs were readable; repost it before any Hook is declared"
                    " the winner"
                )
        if line.section == FLEX and line.earned_by:
            earned = by_angle.get(line.earned_by, [])
            if not earned or earned[0].result != CLEARED:
                problems.append(
                    f"the flex slot goes to {line.earned_by} only if its line says it {CLEARED}, not merely that it"
                    " ranked first"
                )
        settles = line.result in (INSUFFICIENT, AT_RISK) or line.result == REPOST
        if settles and SETTLE not in line.text:
            problems.append(f"{name}: an unread, at-risk, or reposted line ends with `{SETTLE}` before its decision")
        bare = bare_numbers(line.text)
        if bare:
            problems.append(f"{name}: {exchange.plural(len(bare), 'number')} with no `(n=<posts>)` beside it")
    if read.read == max(results.READS):
        for pair in sorted(set(found.pairs()) - {line.key for line in lines if line.section == PAIR}):
            problems.append(f"{pair} has both legs in this read and needs a line under Pairs")
    if read.read == min(results.READS) and len([line for line in lines if line.section == FLEX]) != 1:
        problems.append("the day-7 memo states in exactly one line whether the day-14 flex slot is earned")
    return lines, problems


# The memo the Founder reads, and its items.


def number_text(value: float | int | None, number: str) -> str:
    if value is None:
        return "not reported"
    shown = f"{value:,}" if isinstance(value, int) else f"{value:g}"
    return f"{shown}{'%' if number.endswith('percent') or number == 'average_percentage_viewed' else ''} (n=1)"


def result_rows(found: Plan, days: Sequence[int]) -> list[str]:
    """The launcher's own table of the posts' numbers, from the Founder's records alone: the day each post went out
    is the one he gave, and not reported when he gave nothing for it."""
    rows = [
        "| Day | Angle | Judged on | Posted | Numbers | Comment text given | Read on |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for day in days:
        ask = next((ask for ask in found.read.asks if ask.day == day), None)
        if ask is None:
            continue
        given = found.taken.given.get((ask.platform, day))
        numbers = "; ".join(
            f"{results.LABELS[ask.platform][number]}: {number_text(given.value(number) if given else None, number)}"
            for number in ask.numbers
        )
        count = len(given.result.comments or ()) if given else 0
        comments = f"{count} comment{'s' if count != 1 else ''}" if count else "none given"
        angle = ask.angle or "none"
        if ask.pair:
            angle += f" ({ask.pair} leg {ask.leg})"
        state = found.floor_state(day) and f" ({found.floor_state(day)})"
        rows.append(
            f"| {day} | {angle} | {results.PLATFORM_NAMES[ask.platform]}{state} |"
            f" {given.result.posted_on if given else 'not reported'} | {numbers} | {comments} |"
            f" {given.result.read_on if given else 'nothing given'} |"
        )
    return rows


def compose(
    found: Plan,
    lines: Sequence[Line],
    run_id: str,
    waitlist: Sequence[str],
    time_lines: Sequence[str],
    items: Mapping[str, str],
) -> str:
    """The memo the Founder reads: the launcher's facts, then the agent's checked lines, each with its item."""
    read = found.read
    out = [
        f"# Weekly Read, window {read.window}, day {read.read}",
        "",
        f"Written by run {run_id} from `workspace/{FOLDER}/{found.memo}`, which the launcher checked; it covers days"
        f" {read.covered[0]} to {read.covered[-1]}.",
        "",
        f"- {results.FLOOR_COUNTS}" + (f" The floor is {read.floor} views." if read.floor is not None else ""),
        f"- {CANNOT_TELL}",
        "",
        "## Results",
        "",
        "Each number is one post's, as the Founder gave it from the platform's Studio, so its n is 1; a number he did"
        " not give is not reported, never zero.",
        "",
    ]
    out += result_rows(found, read.covered)
    for title, section in (("Angles", ANGLE), ("Pairs", PAIR), ("Flex slot", FLEX), ("Product", PRODUCT)):
        mine = [line for line in lines if line.section == section]
        if not mine and section != PRODUCT:
            continue
        out += ["", f"## {title}", ""]
        if not mine:
            out.append("None this read.")
        for line in mine:
            out.append(f"{line.text} (item `{items.get(line.key, 'not queued')}`)")
            for day, quote in line.quotes:
                out += exchange.third_party(f"Day {day}: {quote}", "  ")
    out += ["", "## Waitlist", ""] + list(waitlist)
    out += ["", "## The Founder's time this week", ""] + list(time_lines)
    return "\n".join(out) + "\n"


def item_for(found: Plan, line: Line, memo_path: str, product: str) -> exchange.Item:
    """One decision line as its own Weekly Read decision item."""
    read = found.read
    days = found.angles().get(line.key) or found.pairs().get(line.key) or []
    body = [line.text, ""]
    for day, quote in line.quotes:
        body += exchange.third_party(f"Day {day}: {quote}") + [""]
    if days:
        body += result_rows(found, days) + [""]
    body += [results.FLOOR_COUNTS, "", CANNOT_TELL]
    if line.section == ANGLE and line.decision in ("kill", "change"):
        touches = (
            f"- {line.key}'s row in `{found.paths.get('angles', 'angles.md')}`, which Mandu changes if you approve"
        )
    elif line.section == ANGLE:
        touches = f"- Nothing: approving keeps {line.key}'s row in `{found.paths.get('angles', 'angles.md')}` as it is"
    elif line.section == PAIR:
        touches = f"- {line.key} in `{found.paths.get('pairs', 'ab-pairs.md')}`"
    elif line.section == FLEX:
        touches = f"- Day 14 of the calendar, `{found.paths.get('calendar', 'cadence-14-day.md')}`"
    else:
        touches = "- Nothing is changed by this item; a product change would come to you as a Dispatch request"
    evidence = [f"- The memo: `{memo_path}`"]
    evidence += [f"- Day {day}'s numbers: `{found.taken.evidence[day]}`" for day in days if day in found.taken.evidence]
    evidence.append(f"- The rules applied: `{found.paths.get('read_the_results', 'read-the-results.md')}`")
    ask = f"Weekly Read day {read.read}: {line.ask}"
    fields = {"kind": KIND, "product": product, "window": str(read.window), "read": str(read.read)}
    return exchange.Item(fields, ask[: exchange.MAX_TITLE], "\n".join(body).strip(), touches, "\n".join(evidence))


@dataclass
class Outcome:
    """What the take-in did with the memo: its problems, the lines queued, and the memo composed."""

    problems: list[str] = field(default_factory=list)
    unread: str = ""  # why the memo could not be read
    lines: list[Line] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    composed: str = ""  # the memo the Founder reads, under ledger/


def read_memo(areas: Areas, found: Plan) -> tuple[str | None, str]:
    path = areas.path("weekly_reads", found.memo)
    try:
        return read_plain(path).decode("utf-8"), ""
    except FileNotFoundError:
        return None, f"no memo was written at `weekly-reads/{found.memo}`"
    except (OSError, UnsafeFile) as error:
        return None, f"`weekly-reads/{found.memo}` could not be read ({error})"
    except UnicodeDecodeError:
        return None, f"`weekly-reads/{found.memo}` is not UTF-8 text"


def take(
    found: Plan,
    areas: Areas,
    store: Store,
    ledger: Ledger,
    product: str,
    run_id: str,
    now: datetime,
    waitlist: Sequence[str],
    time_lines: Sequence[str],
) -> Outcome:
    """Check the memo the session wrote and, when it passes, compose the memo the Founder reads and queue one item for
    each decision line. Its items replace the read's open items, line for line, and an open item no line replaces is
    withdrawn, since the memo it came from was written again."""
    outcome = Outcome()
    text, why = read_memo(areas, found)
    if text is None:
        outcome.unread = why
        return outcome
    outcome.lines, outcome.problems = check(text, found)
    if outcome.problems:
        return outcome
    composed = store.path(FOLDER, found.memo)
    relative = store.relative(composed)
    old = {str(entry.get("line_key")): entry for entry in found.open_items}
    items: dict[str, str] = {}
    for line in outcome.lines:
        item = item_for(found, line, relative, product)
        earlier = old.pop(line.key, None)
        if earlier is not None:
            item = exchange.Item(
                dict(item.fields, supersedes=str(earlier["id"])), item.ask, item.body, item.touches, item.evidence
            )
        identifier = ledger.publish(
            store,
            item,
            f"weekly-read-{found.read.read:02d}-{line.key.lower()}",
            run_id,
            now,
            extra={"line_key": line.key},
        )
        if earlier is not None:
            ledger.close(earlier, SUPERSEDED, run_id, now, superseded_by=identifier)
            outcome.replaced.append(str(earlier["id"]))
        items[line.key] = identifier
        outcome.published.append(identifier)
    for entry in old.values():
        ledger.close(entry, SUPERSEDED, run_id, now, superseded_by=outcome.published[0], withdrawn=True)
        outcome.replaced.append(str(entry["id"]))
    store.write_text(composed, compose(found, outcome.lines, run_id, waitlist, time_lines, items))
    outcome.composed = relative
    store.write_json(
        store.path(*EVIDENCE, f"window-{found.read.window}-read-{found.read.read:02d}.json"),
        {
            "window": found.read.window,
            "read": found.read.read,
            "fingerprint": found.fingerprint,
            "memo": relative,
            "memo_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "lines": [
                {
                    "key": line.key,
                    "section": line.section,
                    "result": line.result,
                    "decision": line.decision,
                    "item": items.get(line.key),
                }
                for line in outcome.lines
            ],
            "written_by_run": run_id,
            "written_at": now.isoformat(),
        },
    )
    return outcome


def time_lines(store: Store, read: results.Read, read_day: date) -> list[str]:
    """The Founder's reported time in the week before the read: each sitting kept as Evidence in it, its minutes or
    that they were not recorded, never zero."""
    lines = []
    start = read_day - timedelta(days=7)
    folder = store.path("evidence", "sittings")
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            record = json.loads(read_plain(path).decode("utf-8"))
            day = date.fromisoformat(str(record["date"]))
        except (OSError, UnsafeFile, ValueError, KeyError, TypeError):
            lines.append(f"- `{store.relative(path)}` could not be read, so its time is not counted")
            continue
        if start <= day <= read_day:
            minutes = record.get("minutes")
            lines.append(
                f"- Sitting {day.isoformat()}: {minutes} minutes"
                if isinstance(minutes, int)
                else f"- Sitting {day.isoformat()}: its time was not recorded"
            )
    return lines or [f"- No sitting is recorded from {start.isoformat()} to {read_day.isoformat()}."]


# What the brief, the run report, and the notice say of the Weekly Read.


def gaps(found: Plan | None, outcome: Outcome | None, problem: str, session_gap: str) -> list[str]:
    """Why the Weekly Read memo is incomplete this run: it could not be prepared, its session fell short, its memo
    could not be read or fails a check, or the floor could not be read. A memo that is not due is no gap."""
    if found is None:
        return [problem] if problem else []
    found_gaps = []
    if found.due:
        if session_gap:
            found_gaps.append(session_gap)
        if outcome is None:
            if not session_gap:
                found_gaps.append(problem or "the memo was not taken in")
        elif outcome.unread:
            found_gaps.append(outcome.unread)
        elif outcome.problems:
            found_gaps.append(
                f"the memo fails {exchange.plural(len(outcome.problems), 'check')}, so nothing was queued"
            )
    if found.read.floor_problem:
        found_gaps.append(found.read.floor_problem)
    return found_gaps


def outcome_line(found: Plan, outcome: Outcome | None) -> str:
    if not found.due:
        return f"no memo this run: {found.why}"
    if outcome is None or outcome.unread or outcome.problems:
        return "no decision item queued"
    replaced = f", replacing {exchange.plural(len(outcome.replaced), 'open item')}" if outcome.replaced else ""
    return f"memo `{outcome.composed}`; {exchange.plural(len(outcome.published), 'decision item')} queued{replaced}"


def report_lines(
    found: Plan | None, outcome: Outcome | None, why: str, problem: str, filing: str, notice: str | None
) -> list[str]:
    """The run report's Weekly Read section."""
    lines = ["## Weekly Read", ""]
    if found is None:
        lines.append(f"No Weekly Read this run: {problem or why or 'none is due'}.")
    else:
        read = found.read
        given = len(found.taken.given)
        lines.append(
            f"The {read.name}, due from {read.on:%A %Y-%m-%d}, covers days {read.covered[0]} to {read.covered[-1]}"
            f" and asks for {exchange.plural(len(read.asks), 'post')}; the Founder has given {given}."
        )
        lines.append(f"- {results.FLOOR_COUNTS}" + (f" Floor: {read.floor} views." if read.floor is not None else ""))
        if read.floor_problem:
            lines.append(f"- {read.floor_problem[:1].upper()}{read.floor_problem[1:]}.")
        lines += [f"- Could not be asked: {problem_text}." for problem_text in read.problems]
        missing = found.taken.missing(read)
        if missing:
            lines.append("- Not given yet, so not reported: " + "; ".join(ask.label() for ask in missing) + ".")
        if notice:
            lines.append(f"- The notice that lists what to give: `{notice}`.")
        lines.append(f"- Memo: {outcome_line(found, outcome)}.")
        if outcome is not None and outcome.unread:
            lines.append(f"- {outcome.unread[:1].upper()}{outcome.unread[1:]}.")
        if outcome is not None and outcome.problems:
            lines.append(f"- `weekly-reads/{found.memo}` stays as the agent wrote it, and fails these checks:")
            lines += [f"  - {item}" for item in outcome.problems]
    if filing:
        lines.append(f"- Proposed floor wording: {filing}")
    return lines


def notice_section(found: Plan | None, outcome: Outcome | None, day: str) -> tuple[int, str, str] | None:
    """The notice's part for a memo that could not be queued: it was not written, could not be read, or fails a
    check, each reason in the launcher's own words."""
    if found is None or not found.due or outcome is None or not (outcome.unread or outcome.problems):
        return None
    reasons = [outcome.unread] if outcome.unread else outcome.problems
    text = (
        f"The memo for the {found.read.name} could not be queued, so it has no decision item yet; the next run checks"
        " it again:\n" + "\n".join(f"- {reason}" for reason in reasons)
    )
    return len(reasons), f"the {found.read.name} memo could not be queued on {day}", text


def brief_lines(found: Plan, workspace: Path, mandu: Path, check: str) -> list[str]:
    """The Weekly Read session's own section of its brief: the read, every post it covers with what the Founder
    gave, the read before's results, and where to write the memo."""
    read = found.read
    lines = [
        "## Weekly Read",
        "",
        f"The {read.name} is due: its day is {read.on:%A %Y-%m-%d}, and it covers days {read.covered[0]} to"
        f" {read.covered[-1]}.",
        f"Write the memo at `{workspace / FOLDER / found.memo}`, as your task definition describes"
        + (f", and check it with `{check}`." if check else "."),
        f"{results.FLOOR_COUNTS}"
        + (f" The floor is {read.floor} views on the platform that judges a post." if read.floor is not None else ""),
        "Each number below is one post's, as the Founder gave it from the platform's Studio on the date shown, so its"
        " n is 1; one he did not give is not reported, never zero.",
        "",
        "Rules files: "
        + ", ".join(
            f"`{mandu / found.paths[key]}`"
            for key in ("read_the_results", "angles", "calendar", "pairs")
            if key in found.paths
        )
        + ".",
        "",
        "### Angles and their posts",
        "",
    ]
    for angle, days in sorted(found.angles().items()):
        lines.append(f"- {angle} ({days_text(days)})")
    pairs = found.pairs()
    if read.read == max(results.READS):
        lines += ["", "### Pairs with both legs in this read", ""]
        lines += [f"- {pair} ({days_text(days)})" for pair, days in sorted(pairs.items())] or ["- None."]
    lines += ["", "### Each post", ""]
    for ask in read.asks:
        given = found.taken.given.get((ask.platform, ask.day))
        numbers = "; ".join(
            f"{results.LABELS[ask.platform][number]}: {number_text(given.value(number) if given else None, number)}"
            for number in ask.numbers
        )
        state = found.floor_state(ask.day) and f"; {found.floor_state(ask.day)}"
        planned = ask.planned.isoformat()
        if given is None:
            posted = f"planned for {planned}, nothing given"
        elif given.result.posted_on == planned:
            posted = f"posted {planned}, read on {given.result.read_on}"
        else:
            posted = f"posted {given.result.posted_on} (planned for {planned}), read on {given.result.read_on}"
        lines.append(f"- {ask.label()}, {posted}: {numbers}{state}.")
        if ask.why:
            lines.append(f"  Asked for: {ask.why}.")
        comments = given.result.comments if given else None
        if comments:
            lines.append(f"  Comments given ({len(comments)}):")
            lines += exchange.third_party("\n".join(comments), "  ")
        elif given:
            lines.append("  No comment text was given.")
    lines += ["", "### The read before", ""]
    if found.previous:
        lines += [f"- {key}: {result}" for key, result in sorted(found.previous.items())]
    else:
        lines.append("None: this is the window's first read, or its memo was not kept.")
    return lines


# The record of the plan the agent's own check reads.


def plan_record(found: Plan) -> dict[str, object]:
    """What the launcher worked out before the sessions, for check-work to check the memo against: the read and its
    asks, the floor, the read before's results, and each record the Founder gave, by its path and fingerprint, never
    its text."""
    read = found.read
    return {
        "read": read.as_json(),
        "floor": read.floor,
        "floor_problem": read.floor_problem,
        "problems": list(read.problems),
        "paths": dict(found.paths),
        "previous": dict(found.previous),
        "why": found.why,
        "fingerprint": found.fingerprint,
        "given": {
            f"{platform}-{day}": {"record": given.path, "sha256": given.sha256}
            for (platform, day), given in sorted(found.taken.given.items())
        },
        "evidence": {str(day): path for day, path in found.taken.evidence.items()},
    }


def restore(record: Mapping, ledger_root: Path) -> tuple[Plan, list[str]]:
    """The plan as the launcher recorded it, with each record the Founder gave read again from its file; a record
    whose file changed since is named, and checked as it stands now."""
    data = record["read"]
    read = results.Read(
        int(data["window"]), int(data["read"]), date.fromisoformat(str(data["date"])), tuple(data["days"])
    )
    for ask in data["asks"]:
        read.asks.append(
            results.Ask(
                str(ask["platform"]),
                int(ask["day"]),
                date.fromisoformat(str(ask["planned"])),
                ask.get("angle"),
                ask.get("pair"),
                ask.get("leg"),
                tuple(str(number) for number, _ in ask["numbers"]),
                why=str(ask.get("why", "")),
            )
        )
    read.floor, read.floor_problem, read.problems = (
        record.get("floor"),
        str(record.get("floor_problem", "")),
        list(record.get("problems", [])),
    )
    taken = results.Taken()
    notes = []
    for given in (record.get("given") or {}).values():
        path = ledger_root / str(given["record"])
        try:
            raw = read_plain(path)
        except (OSError, UnsafeFile) as error:
            notes.append(f"`{given['record']}` could not be read ({error})")
            continue
        result, problems = exchange.parse_result(path.stem, json.loads(raw.decode("utf-8")))
        if result is None:
            notes.append(f"`{given['record']}` cannot be used now: {'; '.join(problems)}")
            continue
        sha = hashlib.sha256(raw).hexdigest()
        if sha != given["sha256"]:
            notes.append(f"`{given['record']}` changed since the run read it; it is checked as it stands now")
        taken.given[(result.platform, result.day)] = results.Given(result, str(given["record"]), sha)
    taken.evidence = {int(day): str(path) for day, path in (record.get("evidence") or {}).items()}
    found = Plan(read, taken, None, record.get("paths") or {}, str(record.get("fingerprint", "")), str(record["why"]))
    found.previous = dict(record.get("previous") or {})
    return found, notes
