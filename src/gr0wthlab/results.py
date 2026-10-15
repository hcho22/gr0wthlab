"""The results a Weekly Read judges (US-ME11): the numbers and comments the Founder gives on the sitting page in a
read week, and the Evidence each post's numbers become.

gr0wthlab reads no platform: the Founder posts by hand (ADR 0004), and the weekly read uses no YouTube connection
(ADR 0005). So in a read week the run works out from the 14-day kit exactly what to ask for, and nothing more: each
post the read covers, on the platform the calendar names as the one whose metrics adjudicate it, with its views for
the floor, the numbers the pre-registered signals and kill criteria of the read's posts on that platform name, since
read-the-results.md ranks each post against the others in the bank on its own metric, and its comments, since comment
content is a first-class result. It writes the ask into the Review Queue, where the sitting page finds it, and queues
one notice that lists it. The Founder gives each post's numbers on the page, one post at a time (founder.RESULTS);
the next run takes each record in as Evidence for that post, with the date he read the numbers as its source.

A number he left blank is not reported, never zero, and nothing here estimates one. A post he gave nothing for is
not reported, never taken to be not posted: nothing reads back what was posted. No follower count, and no number
that no signal, kill criterion, or read rule names, is asked for or kept.

The floor is the one number of `read-the-results.md` the launcher reads itself (floor_from), since it checks the memo
against it; it counts each platform's views, the Founder's decision of 2026-10-14, and every memo says so.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from . import exchange, founder, kit
from .areas import Store, UnsafeFile, read_plain
from .boundary import FOUNDER
from .filming import listed
from .package import CHANGED, FAILED, READ, SKIPPED
from .settings import Window

# Each read's own calendar day, and the last calendar day it covers. The day-7 read covers days 1 to 5, as the
# calendar's midpoint gate says (days 6 and 7 are too fresh to read). The package names no range for the day-14 read,
# so it covers every day posted before its own day; the freshest posts fall under the floor by the floor's own rule.
READS = exchange.READ_DAYS
# How long a read stays due after its day: until the next read's day, or a week after the window's last read.
READ_WEEK = timedelta(days=7)
TIKTOK, YOUTUBE = exchange.TIKTOK, exchange.YOUTUBE
# What the calendar's Primary platform column may say, and the platform it names.
PRIMARY = {"tiktok": TIKTOK, "youtube shorts": YOUTUBE, "youtube": YOUTUBE}
STUDIO = {TIKTOK: "TikTok Studio", YOUTUBE: "YouTube Studio"}
PLATFORM_NAMES = {TIKTOK: "TikTok", YOUTUBE: "YouTube Shorts"}
# Each number as the page asks for it, named as each platform's own Studio shows it.
LABELS = {
    TIKTOK: {
        "views": "Video views",
        "average_watch_time_seconds": "Average watch time, in seconds",
        "watched_full_percent": "Watched full video, in percent",
        "likes": "Likes",
        "comments": "Comments",
        "shares": "Shares",
        "saves": "Saves",
        "profile_visits": "Profile visits",
    },
    YOUTUBE: {
        "views": "Views",
        "viewed_percent": "Viewed (vs. swiped away), in percent",
        "average_percentage_viewed": "Average percentage viewed",
        "likes": "Likes",
        "comments": "Comments",
        "shares": "Shares",
    },
}
# The words a pre-registered signal or kill criterion uses for each number, most specific first. "impressions" is not
# here: the floor counts views, which every ask holds.
TERMS = (
    ("watched_full_percent", ("watched-full", "watched full", "watch-through", "watch through")),
    ("viewed_percent", ("viewed-vs-swiped", "viewed vs swiped", "viewed vs. swiped", "viewed rate")),
    ("average_percentage_viewed", ("% viewed", "percent viewed", "percentage viewed")),
    ("average_watch_time_seconds", ("watch time",)),
    ("saves", ("saves",)),
    ("shares", ("shares",)),
    ("likes", ("likes",)),
    ("profile_visits", ("profile visit",)),
    ("comments", ("comment",)),
)
TERM_NAMES = {
    "watched_full_percent": "the watched-full rate",
    "viewed_percent": "the share viewed rather than swiped away",
    "average_percentage_viewed": "the average percentage viewed",
    "average_watch_time_seconds": "the average watch time",
    "saves": "saves",
    "shares": "shares",
    "likes": "likes",
    "profile_visits": "profile visits",
    "comments": "comments",
}
# read-the-results.md's floor line, as the package writes it.
FLOOR_LINE = re.compile(r"Any post under (\d[\d,]*) impressions is unread")
FLOOR_COUNTS = (
    "The 200-impression floor counts each platform's views, the Founder's decision of 2026-10-14, until"
    " `read-the-results.md` says which number counts."
)
EVIDENCE = ("evidence", "results")
NOTICE_ORIGIN = "results"
SOURCE_NAMES = {TIKTOK: "TikTok Studio numbers (sitting page)", YOUTUBE: "YouTube Studio numbers (sitting page)"}
# The one line a run with no Weekly Read due has for both.
GIVEN = "Weekly Read numbers (sitting page)"
NEEDS = ("results", "weekly-read")


def platform_of(primary: str) -> str | None:
    return PRIMARY.get(" ".join(primary.lower().split()))


def numbers_named(text: str) -> list[str]:
    """The numbers a signal or kill criterion names, in the order of TERMS."""
    lowered = text.lower()
    found = []
    for number, words in TERMS:
        if any(word in lowered for word in words):
            found.append(number)
    return found


def rules_path(registry: Mapping) -> str | None:
    """The package file of read-the-results.md for the active Product that has one, as the Product registry names it."""
    for product in registry.get("products", []):
        package = product.get("go_to_market_package") or {}
        role = (package.get("weekly_read") or {}).get("read_the_results")
        if product.get("status") == "active" and isinstance(role, str):
            return role
    return None


def views_counted(text: str) -> bool:
    """Whether read-the-results.md's floor line already says the floor counts views, so the proposal that asks it to
    has nothing left to ask."""
    line = next((line for line in text.splitlines() if FLOOR_LINE.search(line)), "")
    return "views" in line.lower()


def floor_from(text: str) -> int | None:
    """The floor read-the-results.md sets, from its own line; None when that line is not there as written."""
    match = FLOOR_LINE.search(text)
    return int(match.group(1).replace(",", "")) if match else None


def day_date(window: Window, number: int) -> date:
    return window.day_1 + timedelta(days=number - 1)


def due(window: Window, today: date) -> tuple[int | None, str]:
    """The Weekly Read due today, by its day (7 or 14), or None with why none is."""
    if window.day_1 is None:
        return None, f"window {window.number}'s first sitting is not set in config/run.json, so no Weekly Read is due"
    for read in sorted(READS, reverse=True):
        on = day_date(window, read)
        if on <= today < on + READ_WEEK:
            return read, ""
    first = day_date(window, min(READS))
    if today < first:
        return None, f"window {window.number}'s first Weekly Read is due on day {min(READS)}, {first:%A %Y-%m-%d}"
    return None, f"window {window.number}'s Weekly Reads are behind it"


# What to ask for.


@dataclass(frozen=True)
class Ask:
    """One post the read covers, on the platform that judges it, and what the Founder is asked to give of it."""

    platform: str
    day: int
    on: date
    angle: str | None
    pair: str | None
    leg: str | None
    numbers: tuple[str, ...]
    unasked: tuple[str, ...] = ()  # what its signal or kill criterion names that the platform's numbers hold none of
    why: str = ""

    def stem(self, window: int, read: int) -> str:
        return exchange.result_stem(window, read, self.platform, self.day)

    def label(self) -> str:
        angle = f" ({self.angle}{f', {self.pair} leg {self.leg}' if self.pair else ''})" if self.angle else ""
        return f"day {self.day}{angle}, {PLATFORM_NAMES[self.platform]}"

    def as_json(self) -> dict[str, object]:
        """The ask as the queue holds it for the sitting page, which reads no package file."""
        return {
            "platform": self.platform,
            "studio": STUDIO[self.platform],
            "day": self.day,
            "date": self.on.isoformat(),
            "angle": self.angle,
            "pair": self.pair,
            "leg": self.leg,
            "numbers": [[number, LABELS[self.platform][number]] for number in self.numbers],
            "comments": True,
            "why": self.why,
        }


@dataclass
class Read:
    """The Weekly Read due this run and what it asks of the Founder."""

    window: int
    read: int
    on: date
    covered: tuple[int, ...]
    asks: list[Ask] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # why something could not be asked, in plain words
    floor: int | None = None
    floor_problem: str = ""

    @property
    def name(self) -> str:
        return f"window {self.window} day-{self.read} Weekly Read"

    def stem(self) -> str:
        return f"window-{self.window}-read-{self.read:02d}"

    @property
    def origin(self) -> str:
        """What the queue's entry of this read's notice is marked with, so it is queued once for the read."""
        return f"{NOTICE_ORIGIN}/{self.stem()}"

    def ask_for(self, platform: str, day: int) -> Ask | None:
        return next((ask for ask in self.asks if ask.platform == platform and ask.day == day), None)

    def as_json(self) -> dict[str, object]:
        return {
            "window": self.window,
            "read": self.read,
            "date": self.on.isoformat(),
            "days": list(self.covered),
            "asks": [ask.as_json() for ask in self.asks],
            "floor": FLOOR_COUNTS,
        }


def asks_for(window: Window, read: int, parsed: kit.Kit, problems: list[str]) -> list[Ask]:
    """What to ask for each post the read covers: the calendar names its Angle and the platform that judges it, and
    the Angle bank its signal and kill criterion. A signal ranks a post against the others in the bank on its own
    platform (read-the-results.md), so each post is also asked for what the signals and kill criteria of the read's
    other posts on that platform name, and nothing more."""
    found_days = []
    for number in range(1, READS[read] + 1):
        found = parsed.days.get(number)
        if found is None:
            problems.append(f"the calendar has no day {number}, so nothing is asked for it")
            continue
        platform = platform_of(found.primary)
        if platform is None:
            problems.append(f"day {number}'s primary platform, {found.primary!r}, is not TikTok or YouTube Shorts")
            continue
        angle = parsed.angles.get(found.angle) if found.angle else None
        if found.angle and angle is None:
            problems.append(f"day {number}'s Angle {found.angle} is not in the Angle bank, so only its views are asked")
        named = numbers_named(f"{angle.signal} {angle.kill}") if angle is not None else []
        found_days.append((number, found, platform, angle, named))
    ranked: dict[str, list[str]] = {}
    for _, _, platform, _, named in found_days:
        ranked.setdefault(platform, [])
        ranked[platform] += [name for name in named if name in LABELS[platform] and name != "views"]
    asks = []
    for number, found, platform, angle, named in found_days:
        shown = LABELS[platform]
        own = [name for name in named if name in shown and name != "views"]
        others = [name for name, _ in TERMS if name in ranked[platform] and name not in own]
        numbers = ["views"] + [name for name, _ in TERMS if name in own or name in others]
        unasked = tuple(name for name in named if name not in shown)
        why = "its views, for the floor"
        if angle is not None:
            why += f", and what {found.angle}'s signal and kill criterion name" + (
                f": {listed([TERM_NAMES[name] for name in own])}" if own else ""
            )
            if unasked:
                why += f"; they also name {listed([TERM_NAMES[name] for name in unasked])}, which no number asked of"
                why += f" {STUDIO[platform]} holds"
            if not named:
                why += "; they name no number the launcher recognizes, so read them in the Angle bank"
        if others:
            why += (
                f"; and, so each post can be ranked against the others on {PLATFORM_NAMES[platform]}, what the read's"
                f" other posts there name: {listed([TERM_NAMES[name] for name in others])}"
            )
        asks.append(
            Ask(
                platform,
                number,
                day_date(window, number),
                found.angle,
                found.pair,
                found.leg,
                tuple(dict.fromkeys(numbers)),
                unasked,
                why,
            )
        )
    return asks


def prepare(window: Window, read: int, parsed: kit.Kit | None, kit_problem: str, rules_text: str | None) -> Read:
    """The read due this run, with what it asks for. A kit that could not be read asks for nothing, and says why."""
    found = Read(window.number, read, day_date(window, read), tuple(range(1, READS[read] + 1)))
    if parsed is None or kit_problem:
        found.problems.append(f"nothing could be asked: {kit_problem or 'the 14-day kit could not be read'}")
    else:
        found.asks = asks_for(window, read, parsed, found.problems)
    if rules_text is None:
        found.floor_problem = "`read-the-results.md` could not be read, so the floor is not known"
    else:
        found.floor = floor_from(rules_text)
        if found.floor is None:
            found.floor_problem = "`read-the-results.md` no longer says the floor in the words this read finds it by"
    return found


# What the Founder gave.


@dataclass(frozen=True)
class Given:
    """One post's results as a run took them in: the Founder's record, where it is, and its fingerprint."""

    result: exchange.Result
    path: str  # under ledger/
    sha256: str

    def value(self, number: str) -> float | int | None:
        return self.result.numbers.get(number)


@dataclass
class Taken:
    """What a run took in for the read due: each usable record by its platform and day, each record that cannot be
    used with why, why the folder could not be read, and the Evidence written."""

    given: dict[tuple[str, int], Given] = field(default_factory=dict)
    unusable: list[tuple[str, list[str], bytes | None]] = field(default_factory=list)  # name, why, its bytes
    failure: str = ""
    changed: list[str] = field(default_factory=list)  # Evidence files this run wrote or wrote again
    evidence: dict[int, str] = field(default_factory=dict)  # each covered day's Evidence file, under ledger/

    def missing(self, read: Read) -> list[Ask]:
        return [ask for ask in read.asks if (ask.platform, ask.day) not in self.given]


def readable(read: Read, taken: Taken, ask: Ask) -> bool | None:
    """Whether a post is readable on the platform that judges it: its views reported and at or above the floor. None
    when the floor itself is not known."""
    if read.floor is None:
        return None
    given = taken.given.get((ask.platform, ask.day))
    views = given.value("views") if given else None
    return views is not None and views >= read.floor


def take(store: Store, read: Read, run_id: str, now: datetime) -> Taken:
    """Take in the Founder's results records for the read due, and write each covered post's Evidence: every number
    asked of it, given or not reported, with the record it came from and the date he read the numbers as its source.
    A record that cannot be used is named with its problem and nothing is taken from it."""
    taken = Taken()
    found, others, failure = founder.read(store.root, founder.RESULTS)
    if failure:
        taken.failure = f"`{FOUNDER}/{founder.RESULTS}/` could not be read: {failure}"
        return taken
    taken.unusable += [(founder.named(founder.RESULTS, name), [why], None) for name, why in others]
    prefix = read.stem() + "-"
    for name, path, data in found:
        if not name.startswith(prefix):
            continue  # another read's record
        result, problems = founder.parse(name, data, exchange.parse_result)
        if result is None:
            taken.unusable.append((founder.named(founder.RESULTS, name), problems, data))
            continue
        taken.given[(result.platform, result.day)] = Given(
            result, store.relative(path), hashlib.sha256(data).hexdigest()
        )
    for number in read.covered:
        asked = [ask for ask in read.asks if ask.day == number]
        target = store.path(*EVIDENCE, f"window-{read.window}", f"read-{read.read:02d}", f"day-{number:02d}.json")
        record = post_evidence(read, number, asked, taken)
        try:
            existing = json.loads(read_plain(target).decode("utf-8"))
        except (OSError, UnsafeFile, ValueError):
            existing = None
        same = (
            isinstance(existing, dict)
            and {key: value for key, value in existing.items() if key not in ("taken_in_by_run", "taken_in_at")}
            == record
        )
        if not same:
            store.write_json(target, dict(record, taken_in_by_run=run_id, taken_in_at=now.isoformat()))
            taken.changed.append(store.relative(target))
        taken.evidence[number] = store.relative(target)
    return taken


def post_evidence(read: Read, number: int, asked: Sequence[Ask], taken: Taken) -> dict[str, object]:
    """One post's Evidence for one read: each platform it was asked on or given for, each number given or not
    reported, never zero, and the Founder's record with the date he read the numbers as the source."""
    platforms = {ask.platform: ask for ask in asked}
    for platform, day in taken.given:
        if day == number:
            platforms.setdefault(platform, None)
    shown: dict[str, object] = {}
    for platform in sorted(platforms):
        ask, given = platforms[platform], taken.given.get((platform, number))
        names = list(ask.numbers) if ask else []
        names += [name for name in (given.result.numbers if given else {}) if name not in names]
        shown[platform] = {
            "judges_this_post": ask is not None,
            "numbers": {name: given.value(name) if given else None for name in names},
            "not_reported": [name for name in names if not given or given.value(name) is None],
            "comments_given": len(given.result.comments) if given and given.result.comments is not None else None,
            "source": {
                "record": given.path,
                "sha256": given.sha256,
                "read_on": given.result.read_on,
                "what": f"the Founder's {STUDIO[platform]} numbers, given on the sitting page",
            }
            if given
            else None,
        }
    first = asked[0] if asked else None
    return {
        "window": read.window,
        "read": read.read,
        "day": number,
        "angle": first.angle if first else None,
        "pair": first.pair if first else None,
        "leg": first.leg if first else None,
        "platforms": shown,
        "note": "A number that is null was not reported, and is never zero. A post with nothing given is not"
        " reported, and is never taken to be not posted.",
    }


def source_lines(read: Read, taken: Taken) -> list[tuple[str, str, str]]:
    """Each platform's line for the run report: (name, status, detail). A platform the read asks nothing of has no
    line; one the Founder gave nothing for yet is skipped with that reason, since he gives them at the sitting."""
    lines = []
    changed = {path.rsplit("/", 1)[-1] for path in taken.changed}
    for platform in (TIKTOK, YOUTUBE):
        asks = [ask for ask in read.asks if ask.platform == platform]
        if not asks:
            continue
        name = SOURCE_NAMES[platform]
        if taken.failure:
            lines.append((name, FAILED, f"{taken.failure}."))
            continue
        given = [ask for ask in asks if (platform, ask.day) in taken.given]
        missing = [str(ask.day) for ask in asks if (platform, ask.day) not in taken.given]
        if not given:
            lines.append(
                (name, SKIPPED, f"not given yet for the {read.name}: the Founder gives them on the sitting page")
            )
            continue
        detail = f"{exchange.plural(len(given), 'post')} of {len(asks)} given for the {read.name}"
        if missing:
            detail += f"; not given, so not reported: day {', '.join(missing)}"
        fresh = any(f"day-{ask.day:02d}.json" in changed for ask in given)
        lines.append((name, CHANGED if fresh else READ, detail))
    return lines


def gaps(read: Read | None, taken: Taken | None, problem: str = "") -> list[str]:
    """Why the post results are incomplete this run: a kit that asked nothing, records that could not be read or
    used, or posts the Founder has not given numbers for, which are not reported."""
    if problem:
        return [problem]
    if read is None:
        return []
    found = list(read.problems)
    if taken is None:
        return found + ["the Founder's results were not taken in"]
    if taken.failure:
        return found + [taken.failure]
    found += [f"`{name}` cannot be used: {'; '.join(why)}" for name, why, _ in taken.unusable]
    missing = taken.missing(read)
    if missing:
        found.append("not given yet, so not reported: " + "; ".join(ask.label() for ask in missing))
    return found


def notice(read: Read, paths: Mapping[str, str]) -> tuple[str, str, str, str]:
    """The notice that lists exactly what to give for the read: which posts, on which platform, which numbers, and
    their comments."""
    title = f"Give the numbers for the {read.name} on the sitting page"
    lines = [
        f"The {read.name} covers days {read.covered[0]} to {read.covered[-1]}.",
        "Give each post's numbers on the sitting page, where it asks for them one post at a time, then start a run"
        " (`src/bin/gr0wthlab run`) so the Weekly Read takes them in.",
        "Each post is asked for only on the platform the calendar names as the one that judges it, and only the"
        " numbers the pre-registered signals and kill criteria of the read's posts on that platform name, since each"
        " post is ranked against the others there, with its views for the floor and its comments.",
        "Leave a number blank when the Studio does not show it: it is recorded as not reported, never as zero.",
        FLOOR_COUNTS,
        "",
    ]
    for platform in (TIKTOK, YOUTUBE):
        asks = [ask for ask in read.asks if ask.platform == platform]
        if not asks:
            continue
        lines.append(f"From {STUDIO[platform]}:")
        lines.append("")
        for ask in asks:
            labels = ", ".join(LABELS[platform][number] for number in ask.numbers)
            lines.append(f"- {ask.label()}, posted {ask.on:%A %Y-%m-%d}: {labels}, and the text of its comments.")
        lines.append("")
    if read.problems:
        lines.append("What could not be asked:")
        lines.append("")
        lines += [f"- {problem}" for problem in read.problems]
        lines.append("")
    touches = "- The Weekly Read memo and its decision items for this read"
    evidence = (
        f"- What each post is asked for comes from the signals and kill criteria of the Angles: `{paths['angles']}`\n"
        f"- Each post's day, Angle, and judging platform: `{paths['calendar']}`\n"
        "- Why the Founder gives these numbers by hand: `docs/adr/0005-the-weekly-read-uses-no-youtube-connection.md`"
    )
    return title, "\n".join(lines).rstrip() + "\n", touches, evidence
