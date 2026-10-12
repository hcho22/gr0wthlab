"""The post-Draft workflow (US-ME08): which calendar days a run prepares, what the agent is told about them, and,
once the agent has finished, which Drafts the launcher offers the Founder and which it blocks, naming the rule.

The agent writes one Draft per calendar day under workspace/drafts/posts/window-<n>/day-<nn>.md. The launcher, outside
the sandbox, checks each against the kit it read from Mandu before the agent started (drafts.evaluate) and queues a
post item only for a Draft that passes, so a post never reaches the Review Queue any other way. A Draft that fails
is blocked with every failing rule or checklist line named in the run report and a notice; an open post whose Draft
no longer passes is withdrawn the same way. A day already approved is never asked again, and neither is a Draft the
Founder rejected, until it changes.

A day's video (US-ME09) is part of its post. When the run films, take is given the filming workflow, which turns the
day's edit record into a finished asset once its Draft passes: the post item then shows the video file with the
copy, an edit record that fails a check blocks the day's post like any failing Draft check, and a post queued before
its video existed is replaced by one that shows it. A day whose copy the Founder approved before its video existed
is offered once more, with the video cut from that very copy, and a day approved with its video is never asked again.
"""

from __future__ import annotations

import hashlib
import json
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from . import exchange, kit, lint, schedule
from .areas import Areas, Store, UnsafeFile, read_plain
from .boundary import Boundary, ConfigError, load_json
from .codebase import CLT_GIT, COMMIT, Code, open_code
from .drafts import BLOCKS, DONE, Context, PostDraft, Verdict, evaluate, parse
from .queue import APPROVED, OPEN, REJECTED, Ledger
from .settings import Settings, Window

PLATFORMS_CONFIG = Path("config/platforms.json")
DRAFTS = "posts"
EVIDENCE = "post-drafts"
FIRST_BATCH = 7
ROLES = ("calendar", "angles", "pairs", "platforms", "brand_rules", "checklist", "competitors")
COMPETITOR_FILES = "competitor"  # the research files, in the competitors folder, whose names start with this
GIT = str(CLT_GIT)

# What became of each calendar day the run prepares.
QUEUED = "queued"
KEPT = "kept"
BLOCKED = "blocked"
MISSING = "no Draft"
APPROVED_BEFORE = "approved earlier"
REPEATED = "not queued again"
NOT_OFFERED = "not offered"
NOT_PREPARED = "not prepared"
STATUSES = (QUEUED, KEPT, BLOCKED, MISSING, APPROVED_BEFORE, REPEATED, NOT_OFFERED, NOT_PREPARED)
VISUAL_ACTIONS = (
    "  Of these rules, each beat's visual action, a filming note, is read only for social-proof phrases; it is also"
    " checked for another Hook."
)


@dataclass
class DayPlan:
    day: kit.KitDay
    hook: kit.FrozenHook | None
    slot: str | None
    open: dict[str, object] | None = None
    approved: dict[str, object] | None = None
    rejected: list[dict[str, object]] = field(default_factory=list)


@dataclass
class Plan:
    """Everything the run knows about its post Drafts before the agent starts."""

    product: str
    window: Window
    reason: str
    days: list[DayPlan]
    skipped: list[tuple[int, str]]
    context: Context
    files: dict[str, tuple[str, str | None]]  # role: (Mandu-relative path, sha256 when read)
    folder: Path  # workspace/drafts/posts/window-<n>/
    waitlist_live: bool = False
    # Each calendar day's open or approved post, once the Founder's decisions were taken in and before the agent
    # started.
    posted: dict[int, dict[str, object]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    # The location overrides the run resolved, so check-drafts, in an environment built from scratch, reads the same
    # Mandu and code checkouts as the launcher.
    locations: list[tuple[str, str]] = field(default_factory=list)
    run: str = ""  # the run whose record of this plan's standing check-drafts reads

    @property
    def code(self) -> Code:
        return self.context.code

    def draft_path(self, number: int) -> Path:
        return self.folder / f"day-{number:02d}.md"

    def other_leg(self, day: kit.KitDay) -> kit.KitDay | None:
        if not day.pair:
            return None
        return next(
            (other for other in self.context.kit.days.values() if other.pair == day.pair and other.leg != day.leg),
            None,
        )


@dataclass
class DayResult:
    day: int
    status: str
    detail: str = ""
    item: str | None = None
    draft: str | None = None
    sha256: str | None = None
    verdict: Verdict | None = None
    withdrawn: str | None = None  # the open item this day's blocked Draft took off the queue
    asset: object | None = None  # filming.Asset: what became of the day's edit record, when the run films


@dataclass
class Outcome:
    results: list[DayResult] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    record: str | None = None

    def count(self, status: str) -> int:
        return sum(1 for result in self.results if result.status == status)

    def counts(self) -> list[str]:
        """How many days ended each way, such as "6 queued", in a fixed order, leaving out the ways none did."""
        return [f"{self.count(status)} {status}" for status in STATUSES if self.count(status)]

    @property
    def blocked(self) -> list[DayResult]:
        return [result for result in self.results if result.status == BLOCKED]

    @property
    def withdrawn(self) -> list[str]:
        return [result.withdrawn for result in self.results if result.withdrawn]


# Before the agent.


def kit_config(registry: Mapping) -> tuple[str, Mapping[str, str]] | None:
    """The Product whose post Drafts the run prepares, and the package file that plays each part in the checks."""
    for product in registry.get("products", []):
        package = product.get("go_to_market_package") or {}
        if product.get("status") == "active" and package.get("post_drafts"):
            roles = package["post_drafts"]
            missing = [role for role in ROLES if not isinstance(roles.get(role), str)]
            if missing:
                raise ConfigError(f"{product['name']} post_drafts must name: {', '.join(missing)}")
            for role in ROLES:
                covering = [
                    entry
                    for entry in package.get("sources") or ()
                    if roles[role] == entry.get("path")
                    or (str(entry.get("path", "")).endswith("/") and roles[role].startswith(entry["path"]))
                ]
                if not covering:
                    raise ConfigError(f"{product['name']} post_drafts {role} must be one of its package sources")
                if role == "competitors" and covering[0].get("files_starting_with", "") not in ("", COMPETITOR_FILES):
                    raise ConfigError(
                        f"{product['name']} post_drafts competitors reads the files starting with {COMPETITOR_FILES},"
                        " so its package source must cover them"
                    )
            return str(product["name"]), roles
    return None


def target_days(window: Window, calendar: Sequence[int], today: date, sitting_day: str) -> tuple[list[int], str]:
    """The calendar days this run prepares: days 1 to 7 until the window's first sitting is set; then, with day 1
    the day after that sitting, the days in the week after the coming sitting (today, when today is the sitting's
    weekday), and any day before that week from tomorrow on, which a run that started late or on demand mid-week
    would otherwise leave unprepared."""
    if window.day_1 is None:
        return (
            [number for number in sorted(calendar) if number <= FIRST_BATCH],
            f"Window {window.number}'s first sitting is not set in config/run.json, so this run prepares days 1 to"
            f" {FIRST_BATCH} as the first batch, with no posting slot yet.",
        )
    sitting = today + timedelta(days=(schedule.weekday(sitting_day) - today.weekday()) % 7)
    first, last = sitting + timedelta(days=1), sitting + timedelta(days=7)
    start = today + timedelta(days=1)
    days = [number for number in sorted(calendar) if start <= window.day_1 + timedelta(days=number - 1) <= last]
    tense = "began" if window.day_1 <= today else "begins"
    began = f"Window {window.number} {tense} on {window.day_1:%A %Y-%m-%d}, the day after its first sitting"
    week = f"the week after the sitting on {sitting:%A %Y-%m-%d} ({first:%Y-%m-%d} to {last:%Y-%m-%d})"
    if start < first:
        week += f", and the days from tomorrow, {start:%Y-%m-%d}, up to that week"
    if not days:
        return days, f"{began}; no calendar day falls in {week}."
    span = f"days {days[0]} to {days[-1]}" if len(days) > 1 else f"day {days[0]}"
    return days, f"{began}; this run prepares {span}: {week}."


def unchecked(plan: Plan) -> list[str]:
    """Why no Draft can be checked this run at all, whatever it says: a kit file, the brand rules, the platform facts,
    or the code could not be used."""
    paths = plan.context.paths
    reasons = [f"`{paths.get(role, role)}` could not be used" for role in sorted(plan.context.kit.problems)]
    if plan.context.rules is None:
        reasons.append("brand-rules.json could not be used")
    if plan.code.problem:
        reasons.append(f"{plan.code.name}'s code could not be read")
    return reasons


def slot_for(window: Window, number: int) -> str | None:
    if window.day_1 is None or window.slot is None:
        return None
    moment = datetime.combine(window.day_1 + timedelta(days=number - 1), window.slot).astimezone()
    return moment.isoformat(timespec="minutes")


def read_kit(mandu: Path, roles: Mapping[str, str]) -> tuple[kit.Kit, dict[str, tuple[str, str | None]], object, str]:
    """Parse every kit file now, once, so the Drafts are checked against what the agent was told.

    Returns the kit, each role's file with its fingerprint, brand-rules.json's data, and why that could not be read.
    A file that cannot be read or parsed is a problem for its role, and every Draft is blocked while it lasts.
    """
    parsed = kit.Kit()
    files: dict[str, tuple[str, str | None]] = {}
    texts: dict[str, str] = {}
    for role in ROLES:
        relative = roles[role]
        files[role] = (relative, None)
        try:
            if role == "competitors":
                folder = mandu / relative
                names = sorted(path.name for path in folder.iterdir() if path.name.startswith(COMPETITOR_FILES))
                found = {name: (folder / name).read_text(encoding="utf-8") for name in names}
                data = json.dumps(found, sort_keys=True).encode("utf-8")
                parsed.competitors = kit.parse_competitors(found)
            else:
                data = (mandu / relative).read_bytes()
                texts[role] = data.decode("utf-8")
            files[role] = (relative, hashlib.sha256(data).hexdigest())
        except (OSError, UnicodeDecodeError, kit.KitError) as error:
            parsed.problems[role] = getattr(error, "strerror", None) or str(error)
    parsers = (
        ("calendar", "days", kit.parse_calendar),
        ("calendar", "asset_checks", kit.parse_asset_checks),
        ("angles", "angles", kit.parse_angles),
        ("pairs", "pairs", kit.parse_pairs),
        ("platforms", "platforms", kit.parse_platforms),
        ("checklist", "checklist", kit.parse_checklist),
    )
    for role, attribute, parser in parsers:
        if role in texts:
            try:
                setattr(parsed, attribute, parser(texts[role]))
            except kit.KitError as error:
                parsed.problems[role] = str(error)
    rules_problem = parsed.problems.pop("brand_rules", "")
    rules_data: object = None
    if "brand_rules" in texts:
        try:
            rules_data = json.loads(texts["brand_rules"])
        except ValueError as error:
            rules_problem = f"not JSON: {error}"
    return parsed, files, rules_data, rules_problem


def day_entries(ledger: Ledger, product: str, window: int, number: int) -> list[dict[str, object]]:
    return [
        entry
        for entry in ledger.entries.values()
        if entry["kind"] == "post"
        and entry.get("product") == product
        and entry.get("window") == window
        and entry.get("day") == number
    ]


def approved_post(entries: Sequence[dict[str, object]]) -> dict[str, object] | None:
    """The approved post of a day: the one that shows its video when it has one, since a day's copy can be approved
    before its video exists."""
    approved = [entry for entry in entries if entry["status"] == APPROVED]
    return next((entry for entry in approved if entry.get("asset_sha256")), approved[0] if approved else None)


def standing_post(entries: Sequence[dict[str, object]]) -> dict[str, object] | None:
    """The post of a day that stands: its open one, otherwise its approved one."""
    return next((entry for entry in entries if entry["status"] == OPEN), None) or approved_post(entries)


def posted_days(ledger: Ledger, product: str, window: int, days: Sequence[int]) -> dict[int, dict[str, object]]:
    """Each of the days' open or approved post, for the days that have one."""
    found = {}
    for number in days:
        post = standing_post(day_entries(ledger, product, window, number))
        if post is not None:
            found[number] = post
    return found


def context_plan(
    repo_root: Path, config: Settings, registry: Mapping, boundary: Boundary, env: Mapping[str, str]
) -> Plan | None:
    """A plan with no day in it yet, or None when no active Product has a kit: the kit, brand rules, platform facts,
    and Product code every Draft is checked against, which the launcher and check-drafts read alike."""
    found = kit_config(registry)
    if found is None:
        return None
    product, roles = found
    mandu = next(location.path for location in boundary.locations if location.label == "Mandu")
    parsed, files, rules_data, rules_problem = read_kit(mandu, roles)
    rules = None
    if rules_data is not None:
        try:
            rules = lint.Rules(rules_data)
        except lint.RulesError as error:
            rules_problem = str(error)
    try:
        platforms = lint.load_platforms(load_json(repo_root / PLATFORMS_CONFIG))
    except (ConfigError, lint.PlatformError, AttributeError, TypeError) as error:
        platforms = {}
        parsed.problems["platform facts"] = str(error)
    entry = next(item for item in registry["products"] if item["name"] == product)
    location = next((loc.path for loc in boundary.locations if loc.label == product), None)
    branch = str((entry.get("repository") or {}).get("branch") or "main")
    code = open_code(product, location, branch, env) if location else Code(product, Path("."), branch)
    if location is None:
        code.problem = f"the Product registry names no {product} checkout"
    context = Context(product, config.window.number, parsed, rules, rules_problem, platforms, code, dict(roles))
    plan = Plan(
        product,
        config.window,
        "",
        [],
        [],
        context,
        files,
        Path(boundary.repo_root) / "workspace" / "drafts" / DRAFTS / f"window-{config.window.number}",
    )
    names = {"Mandu": (registry.get("mandu") or {}).get("env"), product: (entry.get("repository") or {}).get("env")}
    plan.locations = [
        (str(names[location.label]), str(location.path)) for location in boundary.locations if names.get(location.label)
    ]
    return plan


def due_day(
    plan: Plan,
    number: int,
    slot: str | None,
    open_post: dict[str, object] | None,
    approved: dict[str, object] | None,
    rejected: list[dict[str, object]],
) -> DayPlan:
    parsed = plan.context.kit
    day = parsed.days[number]
    hook = kit.frozen_hook(day, parsed)[0] if not parsed.problems.keys() & {"angles", "pairs"} else None
    return DayPlan(day, hook, slot, open_post, approved, rejected)


def prepare(
    repo_root: Path,
    config: Settings,
    registry: Mapping,
    boundary: Boundary,
    ledger: Ledger,
    now: datetime,
    env: Mapping[str, str],
    run_id: str,
) -> Plan | None:
    """The run's post-Draft plan, or None when no active Product has a kit: the checks' context, and each day's
    standing in the queue the launcher holds once it has taken in the Founder's decisions."""
    plan = context_plan(repo_root, config, registry, boundary, env)
    if plan is None:
        return None
    parsed, window, today = plan.context.kit, config.window, now.astimezone().date()
    plan.run = run_id
    plan.waitlist_live = config.waitlist_live(today)
    plan.posted = posted_days(ledger, plan.product, window.number, list(parsed.days))
    if "calendar" in parsed.problems:
        plan.reason = f"The calendar could not be read ({parsed.problems['calendar']}), so no day can be prepared."
        return plan
    numbers, plan.reason = target_days(window, list(parsed.days), today, config.weekly[0])
    for number in numbers:
        if parsed.days[number].angle is None:
            plan.skipped.append((number, f"the calendar decides its Angle later ({parsed.days[number].cell})"))
            continue
        entries = day_entries(ledger, plan.product, window.number, number)
        plan.days.append(
            due_day(
                plan,
                number,
                slot_for(window, number),
                next((item for item in entries if item["status"] == OPEN), None),
                approved_post(entries),
                [item for item in entries if item["status"] == REJECTED],
            )
        )
    return plan


class PlanError(ValueError):
    """A record that does not hold a run's post plan."""


def plan_file(run_id: str) -> str:
    """The name, among the run reports, of a run's record of its plan's standing."""
    return f"{run_id}.post-plan.json"


def kit_files(plan: Plan) -> dict[str, dict[str, str | None]]:
    """Each kit file the plan read from Mandu, by role, with its fingerprint; a file that could not be read has
    none."""
    return {role: {"path": path, "sha256": digest} for role, (path, digest) in plan.files.items()}


def plan_record(plan: Plan) -> dict[str, object]:
    """What the launcher fixed, once, after taking in the Founder's decisions and before the agent started: the days
    due and skipped, each day's open, approved, and rejected posts, the commit the Product's code is read at, or why
    it could not be read, and each kit file's fingerprint. The launcher records it for check-drafts, since the queue
    the standing comes from is saved only when the run ends, and the Product's branch and Mandu's files can move on
    while the agent works."""
    return {
        "run": plan.run,
        "product": plan.product,
        "window": plan.window.number,
        "reason": plan.reason,
        "waitlist_live": plan.waitlist_live,
        "posted": {str(number): post for number, post in plan.posted.items()},
        "due": [
            {"day": due.day.day, "slot": due.slot, "open": due.open, "approved": due.approved, "rejected": due.rejected}
            for due in plan.days
        ],
        "skipped": [{"day": number, "why": why} for number, why in plan.skipped],
        "code": {"commit": plan.code.commit, "problem": plan.code.problem},
        "kit": kit_files(plan),
    }


def restore(plan: Plan, record: object) -> tuple[list[str], list[int]]:
    """Give a plan what the launcher recorded for its run, in place of working it out again: each day's standing,
    and the commit the Product's code is read at, or why the launcher could not read it. Only what Mandu holds now
    can be checked against, so this returns the kit files, by their path in Mandu, that are no longer as the
    launcher read them, and the days due that the calendar no longer holds, which the plan leaves out."""
    try:
        plan.run, plan.reason = str(record["run"]), str(record["reason"])
        plan.waitlist_live = record["waitlist_live"] is True
        plan.posted = {int(number): dict(post) for number, post in record["posted"].items()}
        plan.skipped = [(int(entry["day"]), str(entry["why"])) for entry in record["skipped"]]
        due = {int(entry["day"]): entry for entry in record["due"]}
        calendar = plan.context.kit.days
        plan.days = [
            due_day(plan, number, entry["slot"], entry["open"], entry["approved"], list(entry["rejected"]))
            for number, entry in due.items()
            if number in calendar
        ]
        commit, problem = record["code"]["commit"], record["code"]["problem"]
        if not (problem if commit is None else COMMIT.fullmatch(commit)):
            raise ValueError("it names neither a commit of the Product's code nor why there is none")
        plan.code.commit, plan.code.problem = commit, problem or plan.code.problem
        read = {role: (entry["path"], entry["sha256"]) for role, entry in record["kit"].items()}
        changed = [path for role, (path, digest) in plan.files.items() if read[role] != (path, digest)]
        return changed, [number for number in due if number not in calendar]
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise PlanError(f"it does not hold a run's post plan ({type(error).__name__}: {error})") from error


# After the agent.


def read_draft(areas: Areas, path: Path) -> tuple[PostDraft | None, str]:
    """A Draft file the agent wrote, read without following links; None with the reason when there is none."""
    if not path.exists() and not path.is_symlink():
        return None, ""
    folder = areas.check(path.parent)
    if not areas.real_folder(folder):
        return None, f"`{areas.relative(folder)}` is not a real folder, so its Drafts were not read"
    try:
        text = read_plain(path).decode("utf-8")
    except (UnsafeFile, OSError, UnicodeDecodeError) as error:
        return None, f"`{areas.relative(path)}` could not be read ({error})"
    return parse(text, areas.relative(path)), ""


def reference_leg(plan: Plan, day_plan: DayPlan, draft: PostDraft, areas: Areas) -> tuple[PostDraft | None, bool, str]:
    """The Draft an A/B leg must match beyond the Hook, whether the Founder approved the post it was queued from, and
    why the leg cannot be compared with it when it cannot.

    Decided from the plan's standing and the Drafts as they are now. The launcher works that standing out once, after
    taking in the Founder's decisions and before the agent starts, and check-drafts reads its record of it, so both
    give one verdict. A leg whose own open post came from this very Draft is not checked again. A leg whose post
    stands is the reference for the other, newer leg, in the Draft that post was queued from, so a deviation never
    blocks or withdraws the reference. When this run takes a new Draft of both legs, the earlier day is checked on its
    own and the later day against the earlier day's Draft.
    """
    other = plan.other_leg(day_plan.day)
    if other is None or (day_plan.open and day_plan.open.get("draft_sha256") == draft.sha256):
        return None, False, ""
    posted = plan.posted.get(other.day)
    current = read_draft(areas, plan.draft_path(other.day))[0]
    taken = any(due.day.day == other.day and not due.approved for due in plan.days)
    if taken and current is not None and current.sha256 != (posted or {}).get("draft_sha256"):
        return (current if other.day < day_plan.day.day else None), False, ""
    if posted is None:
        return None, False, ""
    if current is None or current.sha256 != posted.get("draft_sha256"):
        return (
            None,
            False,
            (
                f"day {other.day}'s Draft is no longer the one `{posted['id']}` was queued from, so this leg cannot be"
                " compared with it"
            ),
        )
    return current, posted["status"] == APPROVED, ""


def rejected_as(day_plan: DayPlan, draft: PostDraft, video: str | None) -> dict[str, object] | None:
    """The post the Founder rejected that was queued from this very Draft, which is not asked again until it changes,
    once the run has made what video it can. A post rejected with its video is asked again once the video changes
    too; one rejected before its video existed was rejected for its copy, so no video brings it back. With no video
    to show, nothing has changed that the Founder has not refused, so the Draft is not asked again without one."""
    return next(
        (
            entry
            for entry in day_plan.rejected
            if entry.get("draft_sha256") == draft.sha256
            and (video is None or entry.get("asset_sha256") in (None, video))
        ),
        None,
    )


def refused(rejected: Sequence[Mapping[str, object]], draft: str, edit: str | None) -> Mapping[str, object] | None:
    """The same rejection as check-drafts and check-edits tell it before any video is cut, from a Draft's digest and
    the content digest of the day's edit record in place, None when it has none: a post rejected with its video
    counts while that record is the one its video was cut from, or is gone, since the run then has the same video
    to show, or none."""
    return next(
        (
            entry
            for entry in rejected
            if entry.get("draft_sha256") == draft
            and (not entry.get("asset_sha256") or edit in (None, entry.get("edit_sha256")))
        ),
        None,
    )


def judge(plan: Plan, day_plan: DayPlan, draft: PostDraft, areas: Areas) -> Verdict:
    """Every check of one day's Draft, as the launcher and check-drafts both run them."""
    reference, approved, problem = reference_leg(plan, day_plan, draft, areas)
    verdict = evaluate(draft, plan.context, reference, day_plan.day.day, approved)
    if problem:
        verdict.block("pair-legs", problem)
    return verdict


def offer(
    plan: Plan, day_plan: DayPlan, draft: PostDraft, verdict: Verdict, products: Sequence[str], asset=None
) -> exchange.Item | None:
    """The post item a Draft that passes becomes, with its video when the run made one; an item that does not
    follow the item format blocks the Draft instead."""
    if not verdict.passed:
        return None
    item = render(plan, day_plan, draft, verdict, asset)
    check = exchange.check_item(
        exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence), products
    )
    if check.item is None:
        verdict.block("item", "; ".join(check.problems))
    return item


def check_day(
    plan: Plan, day_plan: DayPlan, draft: PostDraft, areas: Areas, products: Sequence[str]
) -> tuple[Verdict, exchange.Item | None]:
    """Every check of one day's Draft, and the post item a Draft that passes becomes, before any video."""
    verdict = judge(plan, day_plan, draft, areas)
    return verdict, offer(plan, day_plan, draft, verdict, products)


def take(
    plan: Plan,
    areas: Areas,
    store: Store,
    ledger: Ledger,
    run_id: str,
    now: datetime,
    products: Sequence[str],
    video=None,
) -> Outcome:
    """Check every Draft of the run's days and queue each that passes; nothing else ever becomes a post item.
    video is the filming workflow when the run films: it turns a day's edit record into the asset its post shows.
    Every day is settled before any post is queued, so that the two videos of an A/B pair are compared as the run is
    about to leave them: a day whose post is about to change, with the video cut for it or with none, and every other
    day as its post stands."""
    outcome = Outcome()
    for number, why in plan.skipped:
        outcome.results.append(DayResult(number, NOT_PREPARED, why))
    read = [(day_plan, read_day(plan, day_plan, areas, video)) for day_plan in plan.days]
    if video is not None:
        passed = {day.day.day: found[0] for day, found in read if isinstance(found, tuple) and found[1].passed}
        video.finish(passed, areas, store, now)
    offers = []
    for day_plan, found in read:
        if isinstance(found, tuple):
            draft, found = found[0], settle_day(plan, day_plan, *found, store, products, video)
            if found.status == QUEUED:
                offers.append((day_plan, draft, found))
        outcome.results.append(found)
    if video is not None:
        changed = {result.day: None for result in outcome.results if result.withdrawn}
        changed.update({result.day: result.asset if result.asset.finished else None for _, _, result in offers})
        video.leave(changed, store)
    for day_plan, draft, result in offers:
        queue_day(plan, day_plan, draft, result, store, ledger, run_id, now, products, outcome)
    outcome.results.sort(key=lambda result: result.day)
    return outcome


def read_day(plan: Plan, day_plan: DayPlan, areas: Areas, video=None) -> DayResult | tuple[PostDraft, Verdict]:
    """A day's Draft with every check of it, or what became of the day when it has no Draft to check."""
    number = day_plan.day.day
    approved = day_plan.approved
    # A day approved with its video is settled. One approved before its video existed is taken up again only once
    # it has an edit record, so the Founder can approve the video with the copy, and only while its Draft is still
    # the copy the Founder approved, since the video's text is drawn from it.
    if approved and (approved.get("asset_sha256") or video is None or not video.wanted(number)):
        return DayResult(
            number, APPROVED_BEFORE, "the Founder approved it, so it is not asked again", str(approved["id"])
        )
    draft, problem = read_draft(areas, plan.draft_path(number))
    if approved and (draft is None or draft.sha256 != approved.get("draft_sha256")):
        why = "its Draft is gone" if draft is None else "its Draft is no longer that copy"
        video.hold(number, f"the Founder approved its copy as `{approved['id']}`, and {why}")
        return DayResult(
            number,
            APPROVED_BEFORE,
            f"the Founder approved its copy; {why}, so no video is cut for it",
            str(approved["id"]),
        )
    if draft is None:
        if problem:
            withdrawn = str(day_plan.open["id"]) if day_plan.open else None
            return DayResult(number, BLOCKED, problem, withdrawn=withdrawn)
        if day_plan.open:
            return DayResult(number, KEPT, "no new Draft; the open item stands", str(day_plan.open["id"]))
        return DayResult(number, MISSING, f"no Draft at `{areas.relative(plan.draft_path(number))}`")
    return draft, judge(plan, day_plan, draft, areas)


def settle_day(
    plan: Plan,
    day_plan: DayPlan,
    draft: PostDraft,
    verdict: Verdict,
    store: Store,
    products: Sequence[str],
    video=None,
) -> DayResult:
    """What becomes of a day whose Draft was checked, short of queueing anything: a result that is QUEUED names no
    item yet, and queue_day gives it one.

    An open post never loses the video it shows because that video could not be cut again this run, while its Draft
    is the one it was queued from, the day's edit record is in place, and the video's finished file is the file its
    record and the post name, by the one check the filming workflow keeps. When only its slot changed and its edit
    record is still the one the video was cut from, the post that replaces it shows the same video, carried over
    from its own record; with another edit record the open post stands as it is, and a new slot reaches it once the
    video is cut again.

    A finished file that is gone or changed is a video the post no longer has (the Founder's decision of 2026-10-12):
    the same post is queued in its place without a video, saying there is none yet and why, as a Draft that changed
    while its footage was away is, and the video comes back for approval once it is cut again. Where nothing may be
    asked in its place, since the Founder approved the day's copy or rejected this Draft, the open post leaves the
    queue. A file that could not be read is not a file that is gone: the open post stands, and the row says so.
    A day whose edit record is gone has no video to offer, so the brief and check-edits tell the agent to leave such
    a day's record as it is."""
    number = day_plan.day.day
    approved = day_plan.approved
    asset = None
    if video is not None and verdict.passed:
        # The day's video is cut only from a Draft that passes, since its text is drawn over it; an edit record
        # that fails a check blocks the day's post like any failing Draft check, and a cut that fails for a reason
        # outside the record holds the video and blocks nothing.
        asset = video.results[number]
        verdict.blocks += asset.blocks
    offer(plan, day_plan, draft, verdict, products, asset)
    result = DayResult(number, BLOCKED, "", None, draft.path, draft.sha256, verdict, asset=asset)
    if day_plan.open and unchecked(plan):
        # The open item passed when it was queued; a source that cannot be read now does not withdraw it.
        result.status, result.item = KEPT, str(day_plan.open["id"])
        result.detail = f"not checked again, since {'; '.join(unchecked(plan))}; the open item stands"
        return result
    if not verdict.passed:
        if day_plan.open:
            result.withdrawn = str(day_plan.open["id"])
        return result
    shown = asset.sha256 if asset is not None and asset.finished else None
    posted = day_plan.open or {}
    gone = None  # the open post that leaves the queue when nothing may be asked in its place
    queued_from = posted.get("draft") == draft.path and posted.get("draft_sha256") == draft.sha256
    moved = posted.get("slot") != day_plan.slot
    if queued_from and not moved and posted.get("asset_sha256") == shown:
        result.status, result.item = KEPT, str(posted["id"])
        result.detail = "its Draft is unchanged and passes" + (", and so is its video" if shown else "")
        return result
    if queued_from and posted.get("asset_sha256") and asset is not None and asset.held:
        # Its video could not be cut again this run for a reason outside the edit record, so the one it shows stands.
        same_record = asset.edit_sha256 == posted.get("edit_sha256")
        file = video.file(number, store)
        lost = file is not None and not file.intact and not file.unknown
        carried = video.carry(asset, store) if moved and same_record and not lost else None
        if carried is None and not lost:
            result.status, result.item = KEPT, str(posted["id"])
            result.detail = f"its video was not cut again ({asset.detail})"
            if file is not None and not file.intact:
                result.detail += f", and {file.told(' of the video it names')}"
            result.detail += "; the open item stands"
            if moved:
                result.detail += ", and its new slot reaches it once the video is cut again"
            return result
        if lost:
            # The post no longer has the video it names, so it gives way to one that shows none.
            video.drop(asset, file)
            gone = str(posted["id"])
        else:
            asset = result.asset = carried
            shown = carried.sha256
    if approved and shown is None:
        why = asset.detail if asset is not None and asset.detail else "its video is not finished"
        return DayResult(
            number,
            APPROVED_BEFORE,
            f"the Founder approved its copy; no video is offered yet ({why})",
            str(approved["id"]),
            draft.path,
            draft.sha256,
            verdict,
            withdrawn=gone,
            asset=asset,
        )
    rejected = rejected_as(day_plan, draft, shown)
    if rejected:
        result.status, result.item, result.withdrawn = REPEATED, str(rejected["id"]), gone
        result.detail = "the Founder rejected this Draft, so it is not asked again until it changes"
        return result
    result.status = QUEUED
    return result


def queue_day(
    plan: Plan,
    day_plan: DayPlan,
    draft: PostDraft,
    result: DayResult,
    store: Store,
    ledger: Ledger,
    run_id: str,
    now: datetime,
    products: Sequence[str],
    outcome: Outcome,
) -> None:
    """Queue the post a day was settled to offer, with its video when the run cut one. A video the pair check did
    not let through changes nothing for its day this run: no post is queued, and what stood before stays. The item
    queued is the one checked here, with what the pair check added to its video's checks: one that does not follow
    the item format blocks the day, as in settle_day."""
    number, asset, approved = day_plan.day.day, result.asset, day_plan.approved
    if asset is not None and asset.withheld:
        if day_plan.open:
            result.status, result.item = KEPT, str(day_plan.open["id"])
            result.detail = f"what this run changed is not offered, since {asset.detail}; the open item stands"
        elif approved:
            result.status, result.item = APPROVED_BEFORE, str(approved["id"])
            result.detail = f"the Founder approved its copy; no video is offered yet ({asset.detail})"
        else:
            result.status, result.detail = NOT_OFFERED, asset.detail
        return
    item = offer(plan, day_plan, draft, result.verdict, products, asset)
    if not result.verdict.passed:
        result.status = BLOCKED
        if day_plan.open:
            result.withdrawn = str(day_plan.open["id"])
        return
    if day_plan.open:
        item = exchange.Item(
            dict(item.fields, supersedes=str(day_plan.open["id"])), item.ask, item.body, item.touches, item.evidence
        )
    slug = f"post-w{plan.window.number}-day-{number:02d}"
    extra = {"draft": draft.path, "draft_sha256": draft.sha256}
    shown = asset is not None and asset.finished
    if shown:
        extra.update(asset.entry())
    identifier = ledger.publish(store, item, slug, run_id, now, extra)
    if day_plan.open:
        ledger.close(ledger.entries[str(day_plan.open["id"])], "superseded", run_id, now, superseded_by=identifier)
    outcome.published.append(identifier)
    result.item = identifier
    notes = [f"replaces `{day_plan.open['id']}`"] if day_plan.open else []
    if asset is not None and asset.dropped:
        notes.append(f"without the video that one named, which was not cut again this run ({asset.detail})")
    elif shown and asset.detail:
        notes.append(f"with the video that one showed, which was not cut again this run ({asset.detail})")
    elif shown:
        notes.append("with its finished video")
    if approved:
        notes.append(f"its copy was approved as `{approved['id']}`")
    result.detail = ", ".join(notes)


def withdraw(ledger: Ledger, outcome: Outcome, notice: str | None, run_id: str, now: datetime) -> None:
    """Take each open post whose Draft no longer passes off the queue, as replaced by the notice that says why."""
    for result in outcome.results:
        entry = ledger.entries.get(result.withdrawn or "")
        if entry and entry["status"] == OPEN:
            ledger.close(entry, "superseded", run_id, now, superseded_by=notice or "", withdrawn=True)


# The post item.


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def quoted(text: str) -> list[str]:
    return ["  > " + line if line.strip() else "  >" for line in text.splitlines()]


def excerpt(text: str, limit: int) -> str:
    """Package text for an Evidence line: whole when short, otherwise cut between words, so never through a link,
    and followed by each link the cut left out."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    kept = text[:limit].rpartition(" ")[0]
    return " ".join(filter(None, [kept, "...", *kit.urls(text[len(kept) :])]))


def lint_lines(plan: Plan, verdict: Verdict) -> list[str]:
    """What the brand lint passed and what it read, so the line never says more than was checked."""
    rules = plan.context.rules
    warnings = sorted({finding.line() for finding in verdict.warnings})
    pending = rules.pending() if rules else []
    line = (
        "- Brand lint (`brand-rules.json`, from Mandu) on the Hook, every spoken line and on-screen text, and each"
        " platform's fields, with the platform limits (`config/platforms.json`): passed"
    )
    if warnings:
        line += "; warnings: " + "; ".join(warnings)
    if pending:
        line += f"; rule types still waiting for their lists in Mandu: {', '.join(pending)}"
    return [line + ".", VISUAL_ACTIONS + " The rest of what it shows is yours to judge in the Video table."]


def checklist_lines(plan: Plan, verdict: Verdict) -> list[str]:
    """The post's status against every checklist line, short enough to read at a glance: the lines done, the open
    lines that gate only other assets, each open line about a claim this post does not use, and the calendar's own
    lines for every asset, which hold no state a check could read and so are the Founder's to judge."""
    done = [str(line.item.line) for line in verdict.checklist if line.status == DONE]
    waiting = [line for line in verdict.checklist if line.status not in (DONE, BLOCKS)]
    others = [str(line.item.line) for line in waiting if not line.item.gates_social]
    lines = ["- Pre-publication checklist (`pre-publication-checklist.md`): no open line blocks this post."]
    if done:
        lines.append(f"  Done: line{'s' if len(done) > 1 else ''} {', '.join(done)}.")
    if others:
        lines.append(
            f"  Open, gating other assets or none named: line{'s' if len(others) > 1 else ''} {', '.join(others)}."
        )
    for line in waiting:
        if line.item.gates_social:
            lines.append(
                f"  Open, gating only assets that use the {line.item.claim!r} claim, which this post does not:"
                f" line {line.item.line}."
            )
    checks = plan.context.kit.asset_checks
    if checks:
        calendar = plan.context.paths.get("calendar", "the calendar")
        lines.append(f"- The kit's checklist for every asset (`{calendar}`), each line yours to judge on this post:")
        lines += [f"  Line {check.line}: {lint.snippet(check.text, 240)}" for check in checks]
    return lines


def render(plan: Plan, day_plan: DayPlan, draft: PostDraft, verdict: Verdict, asset=None) -> exchange.Item:
    """The Review Queue item for a Draft that passed: the Draft itself, its checks, and its citations. asset is what
    the filming workflow made of the day's edit record, when the run films: the item then shows the finished video
    file, or says that there is none yet and that approving it approves the copy alone."""
    day, hook, angle = day_plan.day, verdict.hook, verdict.angle
    roles = plan.context.paths
    leg = f", {day.pair} leg {day.leg}" if day.pair else ""
    others = [name for name in plan.context.kit.platforms if name != day.primary]
    slot = (
        f"Slot: {datetime.fromisoformat(day_plan.slot):%A %Y-%m-%d %H:%M} ({day_plan.slot[-6:]})."
        if day_plan.slot
        else "Slot: not set yet; the window's first sitting and its posting slot are the Founder's call."
    )
    body = [
        f"Day {day.day} of {plan.product} window {plan.window.number}: Angle {angle.id} ({angle.name}){leg}."
        f" Primary platform {day.primary}; the same video and text post to {', '.join(others) or 'no other platform'}"
        " the same day.",
        slot,
        f"Nothing can be published until the {plan.product} Waitlist is live."
        if not plan.waitlist_live
        else "The Waitlist is live.",
        "",
        f"**Hook**, frozen in `{roles[hook.source]}` line {hook.line}: {hook.text}",
        "",
        "**Video**",
        "",
        "| Beat | Time | Visual action | Spoken line | On-screen text |",
        "| --- | --- | --- | --- | --- |",
    ]
    for beat in draft.beats:
        label = f"{beat.number} (hook)" if beat.hook else str(beat.number)
        body.append(
            f"| {label} | {beat.start:g}-{beat.end:g}s | {cell(beat.visual)} | {cell(beat.spoken)}"
            f" | {cell(beat.on_screen)} |"
        )
    if asset is not None:
        body += [""] + asset.lines()
        if day_plan.approved and asset.finished:
            body.append(
                f"- You approved this day's copy as `{day_plan.approved['id']}` before its video existed; this item"
                " adds the video."
            )
    first = None
    for platform in plan.context.kit.platforms:
        facts = plan.context.platforms[platform]
        values = draft.platforms[platform]
        body += ["", f"**{platform}**", ""]
        for limit in facts.fields:
            text = values[limit.name]
            if first is not None and not limit.title:
                continue
            if "\n" in text.strip():
                body += [f"- {limit.name}:"] + quoted(text)
            else:
                body.append(f"- {limit.name}: {text.strip()}")
        if first is not None:
            body.append(f"- The rest is identical to {first}'s: the same text, hashtags, and alt text.")
        first = first or platform
    commit = plan.code.short
    body += ["", f"**Claims, checked against {plan.product} `{plan.code.branch}` at `{commit}`**", ""]
    body += [f"- {claim.text} `{claim.location}` shows `{claim.excerpt}`" for claim in draft.claims]
    body += [
        "",
        "Only the claims listed here were checked. Anything else the Hook, the video, or the text says the app does is"
        " yours to judge.",
    ]
    body += ["", "**Checks**", ""] + lint_lines(plan, verdict) + checklist_lines(plan, verdict)
    touches = [
        f"- The day {day.day} post on {', '.join(plan.context.kit.platforms)},"
        f" {plan.product} window {plan.window.number}",
        f"- Its Draft: `{draft.path}`, in gr0wthlab's workspace",
    ]
    evidence = [
        f"- Calendar: day {day.day}, {day.asset}, {day.cell}, primary {day.primary}:"
        f" `{roles['calendar']}` line {day.line}",
        f"- Angle {angle.id}, {angle.name}: `{roles['angles']}` line {angle.line}",
        f"- Sourced pain: {excerpt(angle.pain, 400)}: `{roles['angles']}` line {angle.line}",
        f"- Pre-registered signal: {excerpt(angle.signal, 200)}: `{roles['angles']}` line {angle.line}",
        f"- Kill criterion: {excerpt(angle.kill, 200)}: `{roles['angles']}` line {angle.line}",
        f"- Frozen Hook: `{roles[hook.source]}` line {hook.line}",
    ]
    fields = {"kind": "post", "product": plan.product, "window": str(plan.window.number), "day": str(day.day)}
    if day_plan.slot:
        fields["slot"] = day_plan.slot
    if asset is not None and asset.finished:
        fields["asset"] = asset.path
        touches.append(f"- Its video: `{asset.path}`, in gr0wthlab's ledger, cut by `{asset.edit}`")
    named = day.asset if day.asset[1:2].isupper() else day.asset[:1].lower() + day.asset[1:]
    ask = f"Approve day {day.day} post: {named}"
    return exchange.Item(fields, ask[: exchange.MAX_TITLE], "\n".join(body), "\n".join(touches), "\n".join(evidence))


# Records.


def findings_json(verdict: Verdict | None) -> dict[str, object]:
    if verdict is None:
        return {}
    return {
        "blocks": [finding.__dict__ for finding in verdict.blocks],
        "warnings": [finding.__dict__ for finding in verdict.warnings],
        "checklist": [
            {"line": line.item.line, "title": line.item.title, "status": line.status, "note": line.note}
            for line in verdict.checklist
        ],
        "claims": [
            {
                "claim": result.claim.text,
                "code": result.claim.location,
                "shows": result.claim.excerpt,
                "problem": result.problem,
            }
            for result in verdict.claims
        ],
    }


def record(plan: Plan, outcome: Outcome, store: Store, run_id: str, now: datetime) -> str:
    """The run's account of every day it prepared, kept in ledger/evidence/post-drafts/<run id>.json."""
    rules = plan.context.rules
    data = {
        "run": run_id,
        "at": now.isoformat(),
        "product": plan.product,
        "window": {
            "number": plan.window.number,
            "first_sitting": plan.window.first_sitting.isoformat() if plan.window.first_sitting else None,
            "day_1": plan.window.day_1.isoformat() if plan.window.day_1 else None,
            "slot": plan.window.slot.strftime("%H:%M") if plan.window.slot else None,
        },
        "plan": plan.reason,
        "kit": kit_files(plan),
        "kit_problems": dict(plan.context.kit.problems),
        "competitors": [competitor.name for competitor in plan.context.kit.competitors],
        "code": {
            "checkout": str(plan.code.checkout),
            "branch": plan.code.branch,
            "commit": plan.code.commit,
            "problem": plan.code.problem,
        },
        "lint": [row.__dict__ for row in rules.statuses()] if rules else plan.context.rules_problem,
        "days": [
            {
                "day": result.day,
                "status": result.status,
                "detail": result.detail,
                "item": result.item,
                "withdrawn": result.withdrawn,
                "draft": result.draft,
                "draft_sha256": result.sha256,
                "video": result.asset.summary() if result.asset is not None else None,
                **findings_json(result.verdict),
            }
            for result in outcome.results
        ],
    }
    path = store.path("evidence", EVIDENCE, f"{run_id}.json")
    store.write_json(path, data)
    outcome.record = store.relative(path)
    return outcome.record


def grouped(findings: Sequence[lint.Finding]) -> list[str]:
    """Findings with the same rule and detail on one line, naming every field they were found in."""
    lines: dict[tuple[str, str], list[str]] = {}
    for finding in findings:
        fields = lines.setdefault((finding.rule, finding.detail), [])
        if finding.field and finding.field not in fields:
            fields.append(finding.field)
    return [
        f"{rule}: {detail}" + (f" ({', '.join(fields)})" if fields else "") for (rule, detail), fields in lines.items()
    ]


# What the agent, the run report, and the Founder are told.


def leg_label(day: kit.KitDay) -> str:
    return f"{day.angle} / {day.pair} leg {day.leg}" if day.pair else str(day.angle or day.cell)


def standing(day_plan: DayPlan) -> str:
    if day_plan.approved:
        return f"approved as `{day_plan.approved['id']}`; do not draft it again"
    if day_plan.open:
        return f"open as `{day_plan.open['id']}` from its Draft; rewrite the Draft only to change it"
    if day_plan.rejected:
        latest = day_plan.rejected[-1]
        return f"rejected as `{latest['id']}`: {latest.get('reason', 'no reason recorded')}"
    return "nothing yet"


def rule_summary(plan: Plan) -> list[str]:
    rules = plan.context.rules
    if rules is None:
        return [
            f"- Brand rules: `brand-rules.json` could not be used ({plan.context.rules_problem}),"
            " so every Draft is blocked."
        ]
    statuses = rules.statuses()
    by = {
        status: [row.rule for row in statuses if row.status == status] for status in ("applied", "pending", "unknown")
    }
    lines = [
        f"- Brand rules from `{plan.context.paths['brand_rules']}`, run on every field a viewer reads:"
        f" {', '.join(by['applied'])}.",
        VISUAL_ACTIONS,
    ]
    if by["pending"]:
        lines.append(f"  Pending, until Mandu adds their lists: {', '.join(by['pending'])}.")
    if by["unknown"]:
        lines.append(f"  Unknown to gr0wthlab, so they block every Draft: {', '.join(by['unknown'])}.")
    return lines


def checklist_summary(plan: Plan) -> list[str]:
    items = plan.context.kit.checklist
    every = [item for item in items if not item.checked and item.gates_social and not item.claim]
    claims = [item for item in items if not item.checked and item.gates_social and item.claim]
    lines = []
    if every:
        lines.append(
            "- Open checklist lines that block every post until Mandu checks them, so the launcher will block each"
            " Draft (write every Draft all the same): "
            + "; ".join(f"line {item.line} ({lint.snippet(item.title, 60)})" for item in every)
            + "."
        )
    if claims:
        lines.append(
            "- Open checklist lines that block a post using their claim, or whose Angle depends on it: "
            + "; ".join(f"line {item.line} (the {item.claim!r} claim)" for item in claims)
            + "."
        )
    return lines


def check_command(plan: Plan, repo_root: Path) -> str:
    """check-drafts as the agent runs it, reading the same Mandu and code checkouts as this run, and this run's
    record of each day's standing."""
    overrides = " ".join(f"{name}={shlex.quote(path)}" for name, path in plan.locations)
    return f"{overrides} /usr/bin/python3 {repo_root / 'src/bin/gr0wthlab'} check-drafts --run {plan.run}".strip()


def brief_lines(plan: Plan, repo_root: Path) -> list[str]:
    roles = plan.context.paths
    lines = ["## Post Drafts", "", plan.reason]
    if not plan.waitlist_live:
        lines.append(
            f"The {plan.product} Waitlist is not live, so nothing can be published yet; prepare the Drafts as normal."
        )
    lines += [
        "",
        f"Write each day's Draft as `{plan.folder}/day-NN.md`, such as `day-03.md`, with your file-editing tool, in the"
        f" format the task definition gives. Check them before you finish: `{check_command(plan, repo_root)}`. The"
        " launcher queues a post only from a Draft that passes every check, and blocks any other, naming the rule.",
        "",
        "| Day | Asset | Angle / pair leg | Primary | Frozen Hook | In the Review Queue |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for day_plan in plan.days:
        day, hook = day_plan.day, day_plan.hook
        frozen = f"{cell(hook.text)} (`{roles[hook.source]}` line {hook.line})" if hook else "could not be read"
        lines.append(
            f"| {day.day} | {cell(day.asset)} | {leg_label(day)} | {day.primary} | {frozen}"
            f" | {cell(standing(day_plan))} |"
        )
    if not plan.days:
        lines.append("| - | - | - | - | - | No calendar day is due this run. |")
    lines.append("")
    lines += [f"- Not prepared: day {number}: {why}." for number, why in plan.skipped]
    code = plan.code
    if code.problem:
        lines.append(
            f"- {plan.product}'s code could not be read ({code.problem}), so every Draft is blocked:"
            " no claim can be checked."
        )
    else:
        lines.append(
            f"- {plan.product}'s code: branch `{code.branch}` of `{code.checkout}` is commit `{code.commit}`."
            f" Read it at that commit only, with `{GIT} -C {code.checkout} show {code.commit}:<path>`, and find line"
            f" numbers with `{GIT} -C {code.checkout} grep -n '<text>' {code.commit} -- <path>`; the working tree"
            " may differ, and every claim is checked at that commit."
        )
    for platform in plan.context.kit.platforms:
        facts = plan.context.platforms.get(platform)
        if facts is None:
            lines.append(f"- `config/platforms.json` has no facts for {platform}, so every Draft is blocked.")
            continue
        fields = []
        for limit in facts.fields:
            notes = [
                "the Hook" if limit.title else "",
                "starts with the Hook, identical on every platform" if limit.body else "",
                f"at most {limit.max_chars} characters" + (" with the hashtags" if limit.body else "")
                if limit.max_chars
                else "",
                f"about {limit.visible_chars} show" if limit.visible_chars else "",
                f"at most {facts.max_hashtags}" if limit.hashtags and facts.max_hashtags else "",
                f"more than {facts.hashtags_void_above} voids them all"
                if limit.hashtags and facts.hashtags_void_above
                else "",
            ]
            detail = "; ".join(note for note in notes if note)
            fields.append(f"### {limit.name}" + (f" ({detail})" if detail else ""))
        lines.append(f"- `## {platform}` holds exactly: {', '.join(fields)}.")
    names = ", ".join(competitor.name for competitor in plan.context.kit.competitors)
    if names:
        lines.append(f"- Competitors the research names, which no Draft may name: {names}.")
    lines += rule_summary(plan) + checklist_summary(plan)
    for role, problem in sorted(plan.context.kit.problems.items()):
        lines.append(
            f"- `{roles.get(role, role)}` could not be used ({problem}), so every Draft is blocked until it can."
        )
    return lines + [""]


def result_detail(result: DayResult) -> str:
    parts = [result.detail] if result.detail else []
    if result.item and result.status in (QUEUED, KEPT, APPROVED_BEFORE, REPEATED):
        parts.insert(0, f"`{result.item}`")
    if result.verdict and result.status == BLOCKED:
        count = len(grouped(result.verdict.blocks))
        parts.append(f"{count} failing check{'' if count == 1 else 's'}, listed below")
    if result.withdrawn:
        parts.append(f"the open `{result.withdrawn}` was withdrawn")
    return "; ".join(parts)


def report_lines(plan: Plan | None, outcome: Outcome | None, filing: str, problem: str = "") -> list[str]:
    lines = ["## Post Drafts", ""]
    if plan is None:
        return lines + [problem or "No active Product has a 14-day kit, so no post Draft was prepared."]
    lines.append(plan.reason)
    code = plan.code
    lines.append("")
    lines.append(
        f"- Claims checked against {plan.product} `{code.branch}` at `{code.short}` (`{code.checkout}`)."
        " Only the claims a Draft lists are checked; each post item says so."
        if not code.problem
        else f"- {plan.product}'s code could not be read: {code.problem}; every Draft was blocked."
    )
    if not plan.waitlist_live:
        lines.append(f"- Nothing can be published until the {plan.product} Waitlist is live; every post item says so.")
    lines += rule_summary(plan)
    if filing:
        lines.append(f"- Proposed brand-rules lists: {filing}")
    competitors = plan.context.kit.competitors
    lines.append(
        f"- Competitors read from the research: {len(competitors)} ({', '.join(c.name for c in competitors)})."
    )
    lines += checklist_summary(plan)
    if outcome is None:
        return lines + ["", problem or "The Drafts were not taken in this run."]
    if outcome.record:
        lines.append(f"- Every check of every Draft: `{outcome.record}`.")
    days = {day_plan.day.day: day_plan.day for day_plan in plan.days}
    if not outcome.results:
        return lines + ["", "No calendar day was due this run."]
    lines += ["", "| Day | Angle / pair leg | Result | Detail |", "| --- | --- | --- | --- |"]
    for result in outcome.results:
        label = leg_label(days[result.day]) if result.day in days else "-"
        lines.append(f"| {result.day} | {label} | {result.status} | {cell(result_detail(result))} |")
    for result in outcome.results:
        if result.verdict and result.status == BLOCKED:
            lines += ["", f"Day {result.day} blocked (`{result.draft}`):", ""]
            lines += [f"- {line}" for line in grouped(result.verdict.blocks)]
    warned = [result for result in outcome.results if result.verdict and result.verdict.warnings]
    for result in warned:
        lines += ["", f"Day {result.day} warnings, which do not block:", ""]
        lines += [f"- {line}" for line in grouped(result.verdict.warnings)]
    return lines


def notice_section(outcome: Outcome | None, day_text: str) -> tuple[int, str, str] | None:
    """The blocked Drafts, any day with no Draft, and any post withdrawn, for the run's notice; None if nothing."""
    if outcome is None:
        return None
    blocked = outcome.blocked
    missing = [result for result in outcome.results if result.status == MISSING]
    if not blocked and not missing:
        return None
    lines = []
    if blocked:
        lines.append(
            "These post Drafts were not offered for approval; each line names the rule or checklist line that"
            " blocked it:"
        )
        for result in blocked:
            failing = "; ".join(grouped(result.verdict.blocks)) if result.verdict else result.detail
            where = f" (`{result.draft}`)" if result.draft else ""
            lines.append(f"- Day {result.day}{where}: {failing}")
            if result.withdrawn:
                video = result.asset is not None and bool(result.asset.blocks)
                lines.append(
                    f"- The open post `{result.withdrawn}` for day {result.day} is withdrawn, since its"
                    f" {'edit record does not pass' if video else 'Draft no longer passes'}."
                )
    for result in missing:
        lines.append(f"- Day {result.day} has no Draft, so it has no post this run.")
    count = len(blocked) + len(missing)
    title = f"{count} post Draft{'s' if count != 1 else ''} not offered on {day_text}"
    return count, title, "\n".join(lines)
