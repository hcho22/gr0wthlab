"""Beta Cohort recruiting (US-ME15): the Founder's gate, who is invited next, the counts the Founder reports, and
what a run offers the Founder.

The gate is launcher code. It is the Beta Build record the Founder makes in Mandu (docs/mandu-exchange.md), read
here and never inferred from anything else. Until that record exists this workflow does nothing: no candidate, no
Draft, no Evidence, and no word of recruiting in the agent's brief; the run report lists the approval as not
recorded.

Once it exists, each run offers at most one invitation batch, and the next only after the Founder has decided the
last, so the Founder's sends and the first sessions stay manageable. The launcher chooses the batch by entry
identifier, in the order the Waitlist reader gives (waitlist.SELECTION_RULE), from the sign-ups no batch holds yet.
The agent writes the message without learning who is invited; the launcher checks it (beta_drafts) and attaches the
identifiers to the Review Queue item. gr0wthlab sends nothing: the Founder resolves addresses and sends.

An entry in a batch the Founder approved is invited and is never offered again; one in an open batch is offered and
waits; a rejected or withdrawn batch frees its entries. The Review Queue is the record of that, and the run state a
copy checked against it every run.

Recruiting goes on until the Founder reports that the cohort reached its maximum, or records a stop in Mandu. The
only Evidence kept of what happened after a send is the three counts the Founder reports, and a count the Founder
left out is recorded as not reported, never as zero. A pool too small to reach the cohort's minimum is reported with
the size of the gap, and the agent is asked for the Waitlist ask that helps close it. An open ask states that gap, so
it is replaced when the gap changes and withdrawn once the gap closes.

Three of these follow the recruiting patterns of the marketingskills library, considered for this story: batches
that are throttled, a selection rule that is written down and neutral, and no invented scarcity. Its survey benchmark
is not adopted, since the package's K8 rubric governs the first sessions. No text of the library is used here.
"""

from __future__ import annotations

import hashlib
import json
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import exchange, lint, package, waitlist
from .areas import Areas, Store, UnsafeFile, read_plain
from .beta_drafts import INVITATION, WAITLIST_ASK, Context, MessageDraft, evaluate, parse
from .boundary import Boundary, ConfigError
from .drafts import Verdict
from .queue import APPROVED, OPEN, REJECTED, Ledger
from .settings import Settings
from .state import INVITED, OFFERED, BetaRecruitingState

WORKFLOW = "beta-recruiting"
BUILDS = "beta-builds"
REPORTS = "beta-reports"
EVIDENCE = "beta-recruiting"
DRAFTS = "beta-recruiting"
EVIDENCE_FORMAT = 1
GATE_SOURCE = "Beta Build approval in Mandu"
REPORT_SOURCE = "Beta Cohort reports in Mandu"
# The launcher's own sources: the agent never works from either, so its brief never names them.
LAUNCHER_SOURCES = (GATE_SOURCE, REPORT_SOURCE)
SKIPPED = "skipped"  # as report.SKIPPED
# Brand rules about a post's Hook and its Angle, which a message has neither of.
NOT_FOR_MESSAGES = ("hook_max_words", "pain_source_url_must_start_with")
NOT_RECORDED = "not recorded"
UNUSABLE = "unusable"
DRAFT_FILES = {INVITATION: "invitation.md", WAITLIST_ASK: "waitlist-ask.md"}
LABELS = {INVITATION: "Beta invitation", WAITLIST_ASK: "Waitlist ask"}
COUNT_LABELS = {"invitations_sent": "invitations sent", "accepted": "accepted", "sessions_booked": "sessions booked"}
HOLDS_ADDRESS = "it holds something that looks like an email address, so nothing in it was read or kept"

# What a run does about the invitation batch.
NEW = "new"
KEEP = "keep"
REBUILD = "rebuild"
NONE = "none"

# What became of each Draft the run asked for.
QUEUED = "queued"
KEPT = "kept"
BLOCKED = "blocked"
MISSING = "no Draft"
REPEATED = "not queued again"
APPROVED_BEFORE = "approved earlier"
NOT_DUE = "not due"
STATUSES = (QUEUED, KEPT, BLOCKED, MISSING, REPEATED, APPROVED_BEFORE, NOT_DUE)

Raw = tuple[str, Path, bytes]  # a record file in Mandu's exchange folder: its name, its path, and its bytes


# Configuration.


@dataclass(frozen=True)
class Rules:
    """How one Product's Beta Cohort is recruited: the package files a Draft may cite, the cohort's size, and the
    size of a batch."""

    product: str
    k8: str
    brand_rules: str
    citable: tuple[package.Source, ...]
    minimum: int
    maximum: int
    batch_size: int


def rules(registry: Mapping, config: Settings) -> Rules | None:
    """The one Product whose Beta Cohort is recruited, or None; a registry that names it wrongly stops the run."""
    found = [
        product
        for product in registry.get("products", [])
        if product.get("status") == "active" and product.get("beta_recruiting")
    ]
    if not found:
        return None
    if len(found) > 1:
        raise ConfigError("only one Product may recruit a Beta Cohort until the run reads more than one Waitlist view")
    product = found[0]
    name = str(product.get("name"))
    block = product["beta_recruiting"]
    if not product.get("waitlist"):
        raise ConfigError(
            f"{name} recruits its Beta Cohort from its Waitlist, which the Product registry does not name"
        )
    citable = tuple(
        source
        for source in package.package_sources(registry)
        if source.product == name and WORKFLOW in source.needed_by
    )
    k8, brand_rules = (block.get(key) if isinstance(block, dict) else None for key in ("k8", "brand_rules"))
    if not isinstance(k8, str) or not k8.endswith("/") or not any(source.covers(f"{k8}x") for source in citable):
        raise ConfigError(f"{name}.beta_recruiting.k8 must be a folder among the package sources {WORKFLOW} needs")
    if not isinstance(brand_rules, str) or not any(source.covers(brand_rules) for source in citable):
        raise ConfigError(f"{name}.beta_recruiting.brand_rules must be one of the package sources {WORKFLOW} needs")
    cohort = block.get("cohort")
    sizes = [cohort.get(key) for key in ("minimum", "maximum")] if isinstance(cohort, dict) else [None, None]
    if any(isinstance(size, bool) or not isinstance(size, int) for size in sizes) or not 1 <= sizes[0] <= sizes[1]:
        raise ConfigError(f"{name}.beta_recruiting.cohort needs whole numbers minimum and maximum, from 1, in order")
    if config.beta_batch_size > sizes[1]:
        raise ConfigError(f"config/run.json: beta_recruiting.batch_size is larger than {name}'s cohort of {sizes[1]}")
    return Rules(name, k8, brand_rules, citable, sizes[0], sizes[1], config.beta_batch_size)


# Mandu's records.


def mandu_file(folder: str, name: str) -> str:
    """One of Mandu's files, as a record names it. A file name is Mandu's free text, so one that looks like an
    address is never repeated."""
    if waitlist.looks_like_address(name):
        return f"a file in `{folder}/` whose name is not repeated here"
    return f"`{folder}/{name}`"


def read_record(data: bytes, parser, stem: str) -> tuple[object | None, list[str]]:
    """One of Mandu's records, parsed. The address check runs over the file's name and the whole file first, and a
    record that fails it is refused whole, so nothing it holds is ever repeated."""
    if waitlist.looks_like_address(stem) or waitlist.looks_like_address(data.decode("utf-8", errors="replace")):
        return None, [HOLDS_ADDRESS]
    try:
        value = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return None, ["it is not UTF-8 text"]
    except ValueError as error:
        return None, [f"it is not JSON (line {getattr(error, 'lineno', '?')})"]
    return parser(stem, value)


@dataclass(frozen=True)
class Gate:
    """What the Founder's Beta Build record says this run; recruiting exists only while it is recorded."""

    status: str  # NOT_RECORDED, UNUSABLE, or the record's own recruiting: open or stopped
    detail: str
    record: exchange.BetaBuild | None = None
    path: Path | None = None
    sha256: str | None = None

    @property
    def recorded(self) -> bool:
        return self.record is not None

    @property
    def stopped(self) -> bool:
        return self.status == exchange.RECRUITING_STOPPED


def read_gate(product: str, found: Sequence[Raw], unusable: Sequence[tuple[str, str]], failure: str | None) -> Gate:
    """The gate, from beta-builds/: its record files, the files there that could not be used, each with its reason,
    and why the folder could not be listed, if it could not. Only a valid record named for the Product is an
    approval: a folder or file that cannot be read, or a record that does not follow its format, is not one. A file
    there under any other name is no approval either, and the gate says so, so a misnamed record is never a silent
    miss."""
    name = f"{product}.json"
    not_started = "so nothing shows an approval and recruiting has not started"
    if failure:
        return Gate(UNUSABLE, f"`{BUILDS}/` in Mandu's exchange folder could not be read ({failure}), {not_started}.")
    mine = next((why for other, why in unusable if other == name), None)
    if mine is not None:
        return Gate(UNUSABLE, f"`{BUILDS}/{name}` could not be used ({mine}), {not_started}.")
    match = next((raw for raw in found if raw[0] == name), None)
    if match is None:
        others = [other for other, _, _ in found] + [other for other, _ in unusable]
        # A file name is Mandu's free text, so one that looks like an address is counted, never repeated.
        named = [f"`{other}`" for other in sorted(others) if not waitlist.looks_like_address(other)]
        strays = ""
        if others:
            hidden = len(others) - len(named)
            shown = ", ".join(named + [f"{hidden} whose name is not repeated here"] * bool(hidden))
            strays = f"; `{BUILDS}/` holds {shown}, and only `{name}` is {product}'s record"
        return Gate(
            NOT_RECORDED,
            f"not recorded: the Founder has recorded no approved Beta Build for {product} in Mandu, so Beta Cohort"
            f" recruiting has not started{strays}",
        )
    _, path, data = match
    digest = hashlib.sha256(data).hexdigest()
    record, problems = read_record(data, exchange.parse_beta_build, product)
    if record is None:
        why = "; ".join(problems)
        return Gate(UNUSABLE, f"`{BUILDS}/{name}` could not be used ({why}), {not_started}.", None, path, digest)
    build = f", build {record.build}" if record.build else ""
    standing = (
        f"the Founder stopped recruiting on {record.stopped_on}"
        if record.recruiting == exchange.RECRUITING_STOPPED
        else "recruiting is open"
    )
    detail = f"approved on {record.approved_on}{build}, recorded {record.recorded_at}; {standing}"
    return Gate(record.recruiting, detail, record, path, digest)


@dataclass
class Counts:
    """The three counts as the Founder last reported them. stated holds each count some report gave, with that
    report's date; a count no report gave is absent: not reported, never zero."""

    latest: str | None = None  # the date of the latest report, or None when the Founder has reported nothing
    stated: dict[str, tuple[int, str]] = field(default_factory=dict)

    @property
    def accepted(self) -> int | None:
        """The cohort's size as the Founder last reported it."""
        return self.stated["accepted"][0] if "accepted" in self.stated else None

    def text(self, key: str) -> str:
        label = COUNT_LABELS[key]
        if key not in self.stated:
            return f"{label} not reported"
        value, day = self.stated[key]
        return f"{label} {value}" if day == self.latest else f"{label} not reported (last reported: {value} on {day})"

    def line(self) -> str:
        if self.latest is None:
            return "none reported yet: " + ", ".join(self.text(key) for key in exchange.BETA_COUNTS)
        return f"as reported on {self.latest}: " + ", ".join(self.text(key) for key in exchange.BETA_COUNTS)

    def as_json(self) -> dict[str, object]:
        """Each count of the latest report, null when it left the count out, and the counts it left out by name."""
        current = {
            key: self.stated[key][0] if self.stated.get(key, (0, ""))[1] == self.latest else None
            for key in COUNT_LABELS
        }
        last = {key: {"value": value, "reported_on": day} for key, (value, day) in self.stated.items()}
        return {
            "as_of": self.latest,
            **current,
            "not_reported": [key for key, value in current.items() if value is None],
            "last_reported": last,
        }


def read_reports(product: str, found: Sequence[Raw]) -> tuple[list[tuple[exchange.BetaReport, Path, str]], list[str]]:
    """Each usable report of the Product's, oldest first, and every record that could not be used with its reason."""
    usable, problems = [], []
    for name, path, data in found:
        record, issues = read_record(data, exchange.parse_beta_report, name[: -len(".json")])
        if record is None:
            problems.append(f"{mandu_file(REPORTS, name)}: {'; '.join(issues)}")
        elif record.product != product:
            problems.append(f"{mandu_file(REPORTS, name)}: it names a Product whose Beta Cohort is not being recruited")
        else:
            usable.append((record, path, hashlib.sha256(data).hexdigest()))
    return sorted(usable, key=lambda found: found[0].day), problems


def standing(reports: Sequence[exchange.BetaReport]) -> Counts:
    counts = Counts()
    for report in reports:
        counts.latest = report.day
        for key, value in report.counts.items():
            if value is not None:
                counts.stated[key] = (value, report.day)
    return counts


def keep_reports(
    store: Store, reports: Sequence[tuple[exchange.BetaReport, Path, str]], run_id: str, now: datetime
) -> list[str]:
    """Keep each report as Evidence: its counts, its source, and when it was gathered, and nothing else it held.
    Returns the reports that are new or changed since they were last kept."""
    new = []
    for report, path, digest in reports:
        target = store.path("evidence", EVIDENCE, "reports", f"{report.product}-{report.day}.json")
        source = {"path": str(path), "sha256": digest}
        try:
            existing = json.loads(read_plain(target).decode("utf-8"))
        except (UnsafeFile, ValueError):
            existing = None
        if isinstance(existing, dict) and existing.get("source") == source:
            continue
        store.write_json(
            target,
            {
                "format": EVIDENCE_FORMAT,
                "product": report.product,
                "date": report.day,
                **report.counts,
                "not_reported": [key for key, value in report.counts.items() if value is None],
                "recorded_at": report.recorded_at,
                "source": source,
                "taken_in_by_run": run_id,
                "taken_in_at": now.isoformat(),
                "note": "Counts only, as the Founder reported them; a null count was not reported and is never zero.",
            },
        )
        new.append(report.day)
    return new


# Who has been offered an invitation.


def queue_order(entry: Mapping[str, object]) -> tuple[str, str]:
    """Where an item stands among those queued, oldest first."""
    return str(entry["published_at"]), str(entry["id"])


def batches(ledger_entries: Mapping[str, Mapping[str, object]], product: str) -> list[Mapping[str, object]]:
    """Every invitation batch ever queued for the Product, oldest first."""
    found = [
        entry
        for entry in ledger_entries.values()
        if entry.get("beta") == INVITATION and entry.get("product") == product
    ]
    return sorted(found, key=queue_order)


def held_entries(
    previous: BetaRecruitingState, ledger_entries: Mapping[str, Mapping[str, object]], product: str
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Each entry an invitation batch holds, as the Review Queue says: invited once the Founder approved its batch,
    offered while its batch is open. The Review Queue alone says who is invited; the run state is checked against
    it. Returns the entries and every entry the state held as invited that the Review Queue does not."""
    held: dict[str, dict[str, str]] = {}
    for entry in batches(ledger_entries, product):
        approved = entry["status"] == APPROVED or entry.get("decided") == APPROVED
        status = INVITED if approved else OFFERED if entry["status"] == OPEN else None
        for identifier in entry.get("candidates") or ():
            if status and held.get(str(identifier), {}).get("status") != INVITED:
                held[str(identifier)] = {"status": status, "item": str(entry["id"])}
    notes = []
    for identifier, before in sorted(previous.entries.items()):
        # An offered entry moves on with its batch in the ordinary way; only an invitation is expected to last.
        if before["status"] != INVITED or held.get(identifier, {}).get("status") == INVITED:
            continue
        item = ledger_entries.get(before["item"])
        has = f"has that item {item['status']}" if item else "does not hold that item"
        notes.append(f"state had `{identifier}` invited under `{before['item']}`; the Review Queue {has}")
    return held, notes


def invited(held: Mapping[str, Mapping[str, str]]) -> list[str]:
    return sorted(identifier for identifier, entry in held.items() if entry["status"] == INVITED)


@dataclass
class Batch:
    """What the run does about the invitation batch, fixed before the agent starts."""

    action: str
    why: str
    number: int = 0
    candidates: tuple[waitlist.Candidate, ...] = ()
    open: Mapping[str, object] | None = None
    ended: bool = False  # recruiting is over, so no open recruiting item stands
    stale: bool = False  # the open batch holds an entry that may no longer be invited, so it cannot stand

    @property
    def entries(self) -> list[str]:
        return [candidate.entry for candidate in self.candidates]

    @property
    def good_fit(self) -> int:
        return sum(candidate.good_fit for candidate in self.candidates)


def decide(
    rules: Rules,
    gate: Gate,
    reading: waitlist.Reading | None,
    entries: Sequence[Mapping[str, object]],
    held: Mapping[str, Mapping[str, str]],
    counts: Counts,
) -> Batch:
    """The run's one decision about the batch, from the gate, the view, the batches queued so far, and the counts.

    Recruiting ends at the Founder's stop, or once the Founder reports that the cohort reached its maximum. An open
    batch stands while every entry in it may still be invited, and is made again when one left the Waitlist or its
    opt-in. Otherwise the next batch holds the next entries in invitation order that no batch holds, as many as the
    batch size and the room left in the cohort allow. While the Founder has not reported how many accepted, the
    cohort cannot be larger than the entries invited, so that number stands in for it, never zero."""
    current = next((entry for entry in entries if entry["status"] == OPEN), None)
    accepted = counts.accepted
    if gate.stopped:
        return Batch(NONE, f"the Founder stopped recruiting on {gate.record.stopped_on}", open=current, ended=True)
    if accepted is not None and accepted >= rules.maximum:
        day = counts.stated["accepted"][1]
        why = f"the Beta Cohort reached {rules.maximum} people: {accepted} accepted, as the Founder reported on {day}"
        return Batch(NONE, why, open=current, ended=True)
    if reading is None or reading.status != package.READ:
        return Batch(
            NONE, "the Waitlist's anonymous view could not be used this run, so no entry was chosen", open=current
        )
    order = {candidate.entry: candidate for candidate in reading.candidates}
    free = [candidate for candidate in reading.candidates if candidate.entry not in held]
    room = rules.maximum - (accepted if accepted is not None else len(invited(held)))
    if current is not None:
        number = int(current.get("batch") or 1)
        mine = [str(identifier) for identifier in current.get("candidates") or ()]
        still = [
            identifier
            for identifier in mine
            if identifier in order and held.get(identifier, {}).get("item") == current["id"]
        ]
        if len(still) == len(mine):
            kept = tuple(order[identifier] for identifier in mine)
            return Batch(KEEP, f"batch {number} is open as `{current['id']}`", number, kept, current)
        chosen = set(still) | {candidate.entry for candidate in free[: max(0, min(len(mine), room) - len(still))]}
        again = tuple(candidate for candidate in reading.candidates if candidate.entry in chosen)
        gone = len(mine) - len(still)
        why = (
            f"{gone} of the {len(mine)} entries in `{current['id']}` left the Waitlist or its beta opt-in, or were"
            " invited another way, so the batch was made again without them"
        )
        if not again:
            return Batch(NONE, why + "; no entry is left to offer", number, open=current, stale=True)
        return Batch(REBUILD, why, number, again, current)
    number = 1 + len({int(entry.get("batch") or 0) for entry in entries if held_as_invited(entry)})
    if room <= 0:
        return Batch(
            NONE,
            f"{len(invited(held))} entries are approved for invitation and the Founder has not reported how many"
            f" accepted, so the cohort may already hold {rules.maximum}; no further batch until that count is reported",
        )
    if not free:
        return Batch(NONE, "every sign-up that asked for a beta invitation has been offered one")
    size = min(rules.batch_size, room, len(free))
    return Batch(
        NEW, f"batch {number}: the next {size} of {len(free)} entries no batch holds yet", number, tuple(free[:size])
    )


def held_as_invited(entry: Mapping[str, object]) -> bool:
    return entry["status"] == APPROVED or entry.get("decided") == APPROVED


def gap(
    rules: Rules, reading: waitlist.Reading | None, held: Mapping[str, Mapping[str, str]], counts: Counts
) -> int | None:
    """How far short of its minimum the cohort would be even if everyone approved for invitation, and every sign-up
    that asks for one now, accepted; None when the view could not be read, since the pool is then unknown. An entry
    offered in an open batch counts only while the view still holds it."""
    if reading is None or reading.status != package.READ:
        return None
    reachable = len(set(invited(held)) | {candidate.entry for candidate in reading.candidates})
    return max(0, rules.minimum - max(reachable, counts.accepted or 0))


# The run's plan, fixed before the agent starts.


@dataclass
class DraftPlan:
    purpose: str
    path: Path  # where the agent writes it, in workspace/drafts/
    open: Mapping[str, object] | None = None
    approved: list[Mapping[str, object]] = field(default_factory=list)
    rejected: list[Mapping[str, object]] = field(default_factory=list)


@dataclass
class Plan:
    rules: Rules
    gate: Gate
    run: str = ""
    counts: Counts = field(default_factory=Counts)
    reports: int = 0  # how many of the Founder's reports were read
    new_reports: list[str] = field(default_factory=list)
    report_problems: list[str] = field(default_factory=list)
    reports_failure: str | None = None
    held: dict[str, dict[str, str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)  # where the run state disagreed with the Review Queue
    batch: Batch | None = None
    gap: int | None = None
    pool: int = 0  # the sign-ups that asked for an invitation and that no batch holds
    reading: waitlist.Reading | None = None
    waitlist_file: str = ""
    drafts: list[DraftPlan] = field(default_factory=list)  # the Drafts this run asks the agent for
    context: Context | None = None
    folder: Path | None = None
    locations: list[tuple[str, str]] = field(default_factory=list)
    changed: bool = False  # the Beta Build record differs from the one last read

    @property
    def active(self) -> bool:
        """Whether the Founder's gate is recorded; nothing below the gate exists until it is."""
        return self.gate.recorded

    @property
    def product(self) -> str:
        return self.rules.product

    def due(self, purpose: str) -> DraftPlan | None:
        return next((draft for draft in self.drafts if draft.purpose == purpose), None)


def draft_plan(
    purpose: str, folder: Path, ledger_entries: Mapping[str, Mapping[str, object]], product: str
) -> DraftPlan:
    found = sorted(
        (
            entry
            for entry in ledger_entries.values()
            if entry.get("beta") == purpose and entry.get("product") == product
        ),
        key=queue_order,
    )
    return DraftPlan(
        purpose,
        folder / DRAFT_FILES[purpose],
        next((entry for entry in found if entry["status"] == OPEN), None),
        [entry for entry in found if held_as_invited(entry)],
        [entry for entry in found if entry["status"] == REJECTED or entry.get("decided") == REJECTED],
    )


def context(rules: Rules, boundary: Boundary) -> Context:
    """What a recruiting Draft is checked against: Mandu, the package sources it may cite, and the brand rules, read
    now, once, from Mandu's brand-rules.json and nowhere else."""
    mandu = next(location.path for location in boundary.locations if location.label == "Mandu")
    brand_rules, problem = None, ""
    try:
        brand_rules = lint.Rules(json.loads((mandu / rules.brand_rules).read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError) as error:
        problem = getattr(error, "strerror", None) or str(error)
    except ValueError as error:  # not JSON, or not the rules lint.Rules reads
        problem = str(error)
    return Context(rules.product, mandu, rules.citable, rules.k8, brand_rules, problem)


def drafts_folder(boundary: Boundary, product: str) -> Path:
    return Path(boundary.repo_root) / "workspace" / "drafts" / DRAFTS / product


def locations(registry: Mapping, boundary: Boundary) -> list[tuple[str, str]]:
    """The Mandu location the run resolved, as an override, so check-beta-drafts reads the same checkout."""
    name = (registry.get("mandu") or {}).get("env")
    return [(str(name), str(loc.path)) for loc in boundary.locations if loc.label == "Mandu" and name]


def prepare(
    rules: Rules,
    gate: Gate,
    reports: Sequence[Raw] | None,
    reports_failure: str | None,
    registry: Mapping,
    boundary: Boundary,
    ledger: Ledger,
    previous: BetaRecruitingState,
    reading: waitlist.Reading | None,
    waitlist_file: str,
    store: Store,
    run_id: str,
    now: datetime,
) -> Plan:
    """The run's recruiting plan. Before the gate it holds the gate alone, and nothing is read, chosen, or written."""
    plan = Plan(rules, gate, run_id)
    if not plan.active:
        return plan
    plan.changed = gate.sha256 != previous.build
    usable, plan.report_problems = read_reports(rules.product, reports or ())
    plan.reports, plan.reports_failure = len(reports or ()), reports_failure
    plan.new_reports = keep_reports(store, usable, run_id, now)
    plan.counts = standing([report for report, _, _ in usable])
    plan.held, plan.notes = held_entries(previous, ledger.entries, rules.product)
    plan.reading, plan.waitlist_file = reading, waitlist_file
    plan.batch = decide(rules, gate, reading, batches(ledger.entries, rules.product), plan.held, plan.counts)
    if reading is not None and reading.status == package.READ:
        plan.pool = sum(1 for candidate in reading.candidates if candidate.entry not in plan.held)
    plan.gap = None if plan.batch.ended else gap(rules, reading, plan.held, plan.counts)
    plan.folder = drafts_folder(boundary, rules.product)
    plan.context = context(rules, boundary)
    plan.locations = locations(registry, boundary)
    if plan.batch.action != NONE:
        plan.drafts.append(draft_plan(INVITATION, plan.folder, ledger.entries, rules.product))
    if plan.gap:
        plan.drafts.append(draft_plan(WAITLIST_ASK, plan.folder, ledger.entries, rules.product))
    return plan


def source_lines(plan: Plan) -> list[tuple[str, str, str]]:
    """The run report's Sources rows for this workflow: (name, status, detail). Before the gate the approval is listed
    as not recorded, and the Founder's reports as not read; a run that prepared nothing past the gate took none in."""
    gate = plan.gate
    if gate.status == NOT_RECORDED:
        rows = [(GATE_SOURCE, SKIPPED, gate.detail)]
    elif gate.status == UNUSABLE:
        rows = [(GATE_SOURCE, package.FAILED, gate.detail)]
    else:
        rows = [(GATE_SOURCE, package.CHANGED if plan.changed else package.READ, gate.detail)]
    if not plan.active:
        return rows + [(REPORT_SOURCE, SKIPPED, "not read: Beta Cohort recruiting has not started")]
    if plan.batch is None:
        return rows + [(REPORT_SOURCE, SKIPPED, "not taken in: Beta Cohort recruiting was not prepared this run")]
    if plan.reports_failure:
        detail = f"`{REPORTS}/` in Mandu's exchange folder could not be read: {plan.reports_failure}."
        return rows + [(REPORT_SOURCE, package.FAILED, detail)]
    detail = f"{plan.reports} record{'' if plan.reports == 1 else 's'}, {len(plan.new_reports)} new"
    if plan.report_problems:
        detail += f"; {len(plan.report_problems)} could not be used: " + "; ".join(plan.report_problems)
        return rows + [(REPORT_SOURCE, package.FAILED, detail + ".")]
    return rows + [(REPORT_SOURCE, package.CHANGED if plan.new_reports else package.READ, detail)]


class PlanError(ValueError):
    """A record that does not hold a run's recruiting plan."""


def cannot_stand(plan: Plan, due: DraftPlan) -> bool:
    """Whether a Draft's open item cannot stand, whatever becomes of the Draft: an open batch that holds an entry who
    may no longer be invited, or an open ask that states a gap the pool no longer has."""
    if due.purpose == INVITATION:
        return plan.batch.action == REBUILD
    return due.open is not None and due.open.get("gap") != plan.gap


def plan_file(run_id: str) -> str:
    """The name, among the run reports, of what a run asked the agent to draft; it never holds a Waitlist entry."""
    return f"{run_id}.beta-plan.json"


def plan_record(plan: Plan, areas: Areas) -> dict[str, object]:
    """What check-beta-drafts needs to give the launcher's verdict: the Drafts due, each with the fingerprints of
    the Drafts the Founder already rejected and of the one its open item came from, when that item can stand."""
    return {
        "run": plan.run,
        "product": plan.product,
        "drafts": [
            {
                "purpose": due.purpose,
                "path": areas.relative(due.path),
                "open": {"id": due.open["id"], "draft_sha256": due.open.get("draft_sha256")}
                if due.open and not cannot_stand(plan, due)
                else None,
                "rejected": [{"id": entry["id"], "draft_sha256": entry.get("draft_sha256")} for entry in due.rejected],
            }
            for due in plan.drafts
        ],
    }


def restore(record: object, workspace: Path) -> list[DraftPlan]:
    """The Drafts a run asked for, from its record."""
    try:
        return [
            DraftPlan(
                str(entry["purpose"]),
                workspace / str(entry["path"]),
                dict(entry["open"]) if entry["open"] else None,
                [],
                [dict(rejected) for rejected in entry["rejected"]],
            )
            for entry in record["drafts"]
            if entry["purpose"] in DRAFT_FILES
        ]
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise PlanError(f"it does not hold a run's recruiting plan ({type(error).__name__}: {error})") from error


# After the agent.


@dataclass
class DraftResult:
    purpose: str
    status: str
    detail: str = ""
    item: str | None = None
    draft: str | None = None
    sha256: str | None = None
    verdict: Verdict | None = None
    withdrawn: str | None = None  # the open item this result took off the queue
    removed: bool = False  # the Draft file held what looks like an address, so the launcher removed it


@dataclass
class Outcome:
    results: list[DraftResult] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    record: str | None = None

    def result(self, purpose: str) -> DraftResult | None:
        return next((result for result in self.results if result.purpose == purpose), None)

    @property
    def withdrawn(self) -> list[str]:
        return [result.withdrawn for result in self.results if result.withdrawn]


def read_draft(areas: Areas, path: Path) -> tuple[MessageDraft | None, str]:
    """A Draft file the agent wrote, read without following links; None with the reason when there is none. As with
    Mandu's records, the address check runs over the whole file first, whatever its bytes."""
    if not path.exists() and not path.is_symlink():
        return None, ""
    folder = areas.check(path.parent)
    if not areas.real_folder(folder):
        return None, f"`{areas.relative(folder)}` is not a real folder, so its Drafts were not read"
    try:
        data = read_plain(path)
    except (UnsafeFile, OSError) as error:
        return None, f"`{areas.relative(path)}` could not be read ({error})"
    draft = parse(data.decode("utf-8", errors="replace"), areas.relative(path))
    if not draft.holds_address:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            return None, f"`{areas.relative(path)}` could not be read ({error})"
    return draft, ""


def rejected_as(due: DraftPlan, draft: MessageDraft) -> Mapping[str, object] | None:
    """The item the Founder rejected that was queued from this very Draft, which is not asked again until it changes."""
    return next((entry for entry in due.rejected if entry.get("draft_sha256") == draft.sha256), None)


def check_draft(
    plan: Plan, due: DraftPlan, draft: MessageDraft, products: Sequence[str]
) -> tuple[Verdict, exchange.Item | None]:
    """Every check of one Draft, as the launcher and check-beta-drafts both run them, and the item a Draft that
    passes becomes."""
    verdict = evaluate(draft, plan.context, due.purpose)
    if not verdict.passed:
        return verdict, None
    item = render(plan, due, draft, verdict)
    check = exchange.check_item(
        exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence), products
    )
    if check.item is None:
        verdict.block("item", "; ".join(check.problems))
    return verdict, item


def take(
    plan: Plan, areas: Areas, store: Store, ledger: Ledger, run_id: str, now: datetime, products: Sequence[str]
) -> Outcome:
    """Check each Draft the run asked for and queue each that passes, the invitation with its batch attached; nothing
    else ever becomes a recruiting item. When recruiting has ended, every open recruiting item is taken off the
    queue instead, and so is an open Waitlist ask once the gap it asks about has closed."""
    outcome = Outcome()
    batch = plan.batch
    if batch.ended:
        for purpose in (INVITATION, WAITLIST_ASK):
            current = draft_plan(purpose, plan.folder, ledger.entries, plan.product).open
            if current is not None or purpose == INVITATION:
                withdrawn = str(current["id"]) if current else None
                outcome.results.append(DraftResult(purpose, NOT_DUE, batch.why, withdrawn=withdrawn))
        return outcome
    if batch.action == NONE:
        current = str(batch.open["id"]) if batch.open else None
        if current and not batch.stale:
            outcome.results.append(DraftResult(INVITATION, KEPT, batch.why, current))
        else:
            outcome.results.append(DraftResult(INVITATION, NOT_DUE, batch.why, withdrawn=current))
    for due in plan.drafts:
        outcome.results.append(take_draft(plan, due, areas, store, ledger, run_id, now, products, outcome))
    if plan.gap == 0:
        current = draft_plan(WAITLIST_ASK, plan.folder, ledger.entries, plan.product).open
        if current is not None:
            why = f"the Beta Cohort can now reach its minimum of {plan.rules.minimum}, so the ask is no longer needed"
            outcome.results.append(DraftResult(WAITLIST_ASK, NOT_DUE, why, withdrawn=str(current["id"])))
    return outcome


def take_draft(
    plan: Plan,
    due: DraftPlan,
    areas: Areas,
    store: Store,
    ledger: Ledger,
    run_id: str,
    now: datetime,
    products: Sequence[str],
    outcome: Outcome,
) -> DraftResult:
    purpose = due.purpose
    stale = cannot_stand(plan, due)
    current = str(due.open["id"]) if due.open else None
    draft, problem = read_draft(areas, due.path)
    if draft is None:
        if problem:
            return DraftResult(purpose, BLOCKED, problem, withdrawn=current)
        if current and not stale:
            return DraftResult(purpose, KEPT, "no new Draft; the open item stands", current)
        if purpose == WAITLIST_ASK and due.approved:
            earlier = str(due.approved[-1]["id"])
            why = "the Founder approved it, so it is not asked again"
            return DraftResult(purpose, APPROVED_BEFORE, why, earlier, withdrawn=current)
        where = f"no Draft at `{areas.relative(due.path)}`"
        return DraftResult(purpose, MISSING, where, withdrawn=current)
    result = DraftResult(purpose, BLOCKED, "", None, draft.path, draft.sha256)
    if draft.holds_address:
        # FR-11: the file leaves the workspace before the records step can save it, and nothing in it is quoted.
        areas.remove(due.path)
        result.removed = True
    elif current and not stale and plan.context.rules is None:
        # The open item passed when it was queued; brand rules that cannot be read now do not withdraw it.
        result.status, result.item = KEPT, current
        result.detail = "not checked again, since brand-rules.json could not be used; the open item stands"
        return result
    result.verdict, item = check_draft(plan, due, draft, products)
    if not result.verdict.passed:
        result.withdrawn = current
        return result
    same = due.open is not None and due.open.get("draft_sha256") == draft.sha256
    if same and not stale:
        result.status, result.item, result.detail = KEPT, current, "its Draft is unchanged and passes"
        return result
    rejected = rejected_as(due, draft)
    if rejected and not same:
        result.status, result.item = REPEATED, str(rejected["id"])
        result.detail = "the Founder rejected this Draft, so it is not asked again until it changes"
        result.withdrawn = current if stale else None
        return result
    approved = next((entry for entry in due.approved if entry.get("draft_sha256") == draft.sha256), None)
    if purpose == WAITLIST_ASK and approved and not current:
        result.status, result.item = APPROVED_BEFORE, str(approved["id"])
        result.detail = "the Founder approved this Draft, so it is not asked again until it changes"
        return result
    if current:
        item = exchange.Item(dict(item.fields, supersedes=current), item.ask, item.body, item.touches, item.evidence)
    extra: dict[str, object] = {"beta": purpose, "draft": draft.path, "draft_sha256": draft.sha256}
    if purpose == INVITATION:
        slug = f"beta-invitation-batch-{plan.batch.number:02d}"
        extra.update(batch=plan.batch.number, candidates=plan.batch.entries)
    else:
        slug = "beta-waitlist-ask"
        extra.update(gap=plan.gap)
    identifier = ledger.publish(store, item, slug, run_id, now, extra)
    if current:
        ledger.close(ledger.entries[current], "superseded", run_id, now, superseded_by=identifier)
    outcome.published.append(identifier)
    result.status, result.item = QUEUED, identifier
    result.detail = f"replaces `{current}`" if current else ""
    return result


def withdraw(ledger: Ledger, outcome: Outcome, notice: str | None, run_id: str, now: datetime) -> None:
    """Take each open recruiting item that no longer stands off the queue, as replaced by the notice that says why."""
    for identifier in outcome.withdrawn:
        entry = ledger.entries.get(identifier)
        if entry and entry["status"] == OPEN:
            ledger.close(entry, "superseded", run_id, now, superseded_by=notice or "", withdrawn=True)


def settle(
    previous: BetaRecruitingState, ledger_entries: Mapping[str, Mapping[str, object]], plan: Plan
) -> BetaRecruitingState:
    """Bring the plan and the run state to where the Review Queue stands once the run has queued and withdrawn its
    items: who is invited, who is offered, and how many sign-ups that asked no batch holds."""
    plan.held, _ = held_entries(previous, ledger_entries, plan.product)
    if plan.reading is not None and plan.reading.status == package.READ:
        plan.pool = sum(1 for candidate in plan.reading.candidates if candidate.entry not in plan.held)
    return BetaRecruitingState(plan.held, plan.gate.sha256 or previous.build)


# The items.


def quoted(text: str) -> list[str]:
    return ["> " + line if line.strip() else ">" for line in text.splitlines()]


def listed(identifiers: Sequence[str]) -> str:
    return ", ".join(f"`{identifier}`" for identifier in identifiers)


def plural(count: int, noun: str, many: str | None = None) -> str:
    return f"{count} {noun if count == 1 else many or noun + 's'}"


def cohort_line(plan: Plan) -> str:
    """Where the cohort stands against its size, from the Founder's count alone."""
    rules, accepted = plan.rules, plan.counts.accepted
    size = f"{rules.minimum} to {rules.maximum} people"
    if accepted is None:
        approved = len(invited(plan.held))
        if not approved:
            return f"The Beta Cohort is {size}. No invitation has been approved yet, so nobody has joined it."
        return (
            f"The Beta Cohort is {size}. How many people accepted is not reported, so its size is unknown; it cannot"
            f" be larger than the {plural(approved, 'entry', 'entries')} approved for invitation."
        )
    day = plan.counts.stated["accepted"][1]
    if accepted < rules.minimum:
        short = rules.minimum - accepted
        return (
            f"The Beta Cohort is {size}: {accepted} accepted, as reported on {day}, {short} short of {rules.minimum}."
        )
    if accepted < rules.maximum:
        return (
            f"The Beta Cohort is {size}: {accepted} accepted, as reported on {day}, which is within it. Recruiting"
            f" goes on until it reaches {rules.maximum} or the Founder records a stop in Mandu."
        )
    return f"The Beta Cohort is {size}: {accepted} accepted, as reported on {day}, so it is full."


def gap_line(plan: Plan) -> str:
    """The pool that is too small, stated plainly with the size of the gap; empty when it is not."""
    if not plan.gap:
        return ""
    reachable = plan.rules.minimum - plan.gap
    return (
        f"The pool is too small to reach {plan.rules.minimum}: {plural(reachable, 'sign-up')} asked for a beta"
        f" invitation in all, so even if every one accepted, the Beta Cohort would be {plan.gap} short of"
        f" {plan.rules.minimum}."
    )


def check_lines(plan: Plan, purpose: str, verdict: Verdict) -> list[str]:
    """What the launcher checked and passed, so the lines never say more than was checked."""
    brand = plan.context.rules
    warnings = sorted({finding.line() for finding in verdict.warnings})
    pending = brand.pending() if brand else []
    lint_line = "- Brand lint (`brand-rules.json`, from Mandu) on the subject and the message: passed"
    if warnings:
        lint_line += "; warnings: " + "; ".join(warnings)
    if pending:
        lint_line += f"; rule types still waiting for their lists in Mandu: {', '.join(pending)}"
    lines = [
        "- No email address anywhere in the Draft, and no link in the subject or the message: passed.",
        "- Every package line it cites is in Mandu, word for word, and every figure it states is in one of them, so"
        " it states no count or spot number of its own: passed.",
    ]
    if purpose == INVITATION:
        lines.append(
            f"- It cites the thesis's K8 files (`{plan.rules.k8}`), says the first session is recorded, and says how"
            " many minutes it takes: passed."
        )
    return lines + [lint_line + ".", "- Whether it is identity-framed, and how it reads, is yours to judge."]


def render(plan: Plan, due: DraftPlan, draft: MessageDraft, verdict: Verdict) -> exchange.Item:
    """The Review Queue item for a Draft that passed: the message, what it was checked for, and its citations; an
    invitation also carries its batch, which only the launcher knows."""
    product, batch, rules = plan.product, plan.batch, plan.rules
    message = ["**Subject**", "", f"> {draft.subject}", "", "**Message**", "", *quoted(draft.message)]
    evidence = [f'- "{citation.quote}": `{citation.path}` line {citation.line}' for citation in draft.citations]
    evidence.append(
        f"- The Beta Build approval the Founder recorded: `{BUILDS}/{product}.json` in Mandu's exchange folder"
    )
    evidence.append(
        "- Where recruiting stood when this item was queued, with the rule and every check:"
        f" `evidence/{EVIDENCE}/{plan.run}.json`"
    )
    if plan.waitlist_file:
        evidence.append(f"- The Waitlist counts of this run: `{plan.waitlist_file}`")
    touches = [f"- Its Draft: `{draft.path}`, in gr0wthlab's workspace"]
    if due.purpose == WAITLIST_ASK:
        body = [
            gap_line(plan),
            "This message asks people who have not signed up to join the Waitlist and ask for a beta invitation. You"
            " send it yourself, wherever you choose; it carries no link and no address, so add the Waitlist link for"
            " the channel you use. gr0wthlab sends nothing.",
            "",
            *message,
            "",
            "**Checks**",
            "",
            *check_lines(plan, due.purpose, verdict),
        ]
        ask = f"Approve Waitlist ask: the pool is {plan.gap} short of a {rules.minimum}-person Beta Cohort"
        touches.insert(0, f"- The message asking people to join {product}'s Waitlist, which you send")
        fields = {"kind": "message", "product": product}
        return exchange.Item(fields, ask, "\n".join(body), "\n".join(touches), "\n".join(evidence))
    count = len(batch.candidates)
    entries = plural(count, "Waitlist entry", "Waitlist entries")
    good = [candidate.entry for candidate in batch.candidates if candidate.good_fit]
    others = [candidate.entry for candidate in batch.candidates if not candidate.good_fit]
    body = [
        f"Batch {batch.number} of {product}'s Beta Cohort invitations: {entries}, chosen by the launcher from the"
        " anonymous view. The Marketing Engineer wrote the message without learning who is invited.",
        "You resolve each entry identifier to its address on your side and send; gr0wthlab holds no address and sends"
        " nothing. The message carries no link and no address, whichever way you invite, by a TestFlight public link"
        " or by individual email invitation: add what your route needs when you send.",
        "",
        *message,
        "",
        "**Candidates, in invitation order**",
        "",
        f"- Good Fit, asked for a beta invitation ({len(good)}): {listed(good) or 'none'}",
    ]
    if others:
        body.append(f"- Asked for a beta invitation, with another Fit answer or none ({len(others)}): {listed(others)}")
    body += [
        "",
        f"{waitlist.SELECTION_RULE} No entry is offered twice.",
        "",
        f"**Where recruiting stood when run `{plan.run}` queued this item**",
        "",
        f"- Beta Build approved on {plan.gate.record.approved_on}, as the Founder recorded in Mandu.",
        f"- Approved for invitation before this batch: {plural(len(invited(plan.held)), 'entry', 'entries')}.",
        f"- The Founder's counts, {plan.counts.line()}.",
        f"- {cohort_line(plan)}",
    ]
    if plan.gap:
        body.append(f"- {gap_line(plan)}")
    body += [
        "",
        "**Checks**",
        "",
        *check_lines(plan, due.purpose, verdict),
        "",
        "After you send, report in Mandu how many invitations you sent, how many people accepted, and how many first"
        " sessions are booked, each as a total to date. A count you leave out is recorded as not reported, never as"
        " zero.",
    ]
    ask = f"Approve Beta Cohort invitation, batch {batch.number}: {plural(count, 'Waitlist entry', 'Waitlist entries')}"
    touches.insert(
        0, f"- The Beta Cohort invitation to {plural(count, 'Waitlist entry', 'Waitlist entries')}, which you send"
    )
    fields = {"kind": "message", "product": product}
    return exchange.Item(fields, ask, "\n".join(body), "\n".join(touches), "\n".join(evidence))


# Records.


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


def record(plan: Plan, outcome: Outcome, store: Store, run_id: str, now: datetime) -> str:
    """The run's Evidence of recruiting, in ledger/evidence/beta-recruiting/<run id>.json: the gate and its source,
    the Founder's counts, the batch by entry identifier, who is invited and offered as the run leaves the Review
    Queue, and every check of every Draft. Entry identifiers and counts only."""
    gate, batch, brand = plan.gate, plan.batch, plan.context.rules
    data = {
        "format": EVIDENCE_FORMAT,
        "run": run_id,
        "at": now.isoformat(),
        "product": plan.product,
        "beta_build": {
            "approved_on": gate.record.approved_on,
            "build": gate.record.build,
            "recruiting": gate.record.recruiting,
            "stopped_on": gate.record.stopped_on,
            "recorded_at": gate.record.recorded_at,
            "source": {"path": str(gate.path), "sha256": gate.sha256},
        },
        "founder_counts": plan.counts.as_json(),
        "cohort": {"minimum": plan.rules.minimum, "maximum": plan.rules.maximum, "accepted": plan.counts.accepted},
        "waitlist_evidence": plan.waitlist_file or None,
        "selection_rule": waitlist.SELECTION_RULE,
        "batch_size": plan.rules.batch_size,
        "batch": {
            "action": batch.action,
            "why": batch.why,
            "number": batch.number or None,
            "candidates": batch.entries,
            "good_fit": batch.good_fit,
        },
        "invited": invited(plan.held),
        "offered": sorted(identifier for identifier, entry in plan.held.items() if entry["status"] == OFFERED),
        "pool": {"not_offered_yet": plan.pool, "gap": plan.gap},
        "lint": [row.__dict__ for row in brand.statuses()] if brand else plan.context.rules_problem,
        "drafts": [
            {
                "purpose": result.purpose,
                "status": result.status,
                "detail": result.detail,
                "item": result.item,
                "withdrawn": result.withdrawn,
                "draft": result.draft,
                "draft_sha256": result.sha256,
                "removed": result.removed,
                "blocks": [finding.__dict__ for finding in result.verdict.blocks] if result.verdict else [],
                "warnings": [finding.__dict__ for finding in result.verdict.warnings] if result.verdict else [],
            }
            for result in outcome.results
        ],
        "note": "Entry identifiers and counts only; no email address or anything else a sign-up wrote is ever kept.",
    }
    path = store.path("evidence", EVIDENCE, f"{run_id}.json")
    store.write_json(path, data)
    outcome.record = store.relative(path)
    return outcome.record


# What the agent, the run report, and the Founder are told.


def draft_standing(due: DraftPlan) -> str:
    if due.open:
        return f"open as `{due.open['id']}` from its Draft; rewrite the Draft only to change it"
    decided = sorted(due.rejected[-1:] + due.approved[-1:], key=queue_order)
    if not decided:
        return "nothing yet"
    latest = decided[-1]
    if latest in due.rejected:
        return f"rejected as `{latest['id']}`: {latest.get('reason', 'no reason recorded')}"
    note = f" Note: {latest['note']}" if latest.get("note") else ""
    return f"approved as `{latest['id']}`; rewrite the Draft only if there is a reason to.{note}"


def check_command(plan: Plan, repo_root: Path) -> str:
    """check-beta-drafts as the agent runs it, reading the same Mandu checkout as this run."""
    overrides = " ".join(f"{name}={shlex.quote(path)}" for name, path in plan.locations)
    return f"{overrides} /usr/bin/python3 {repo_root / 'src/bin/gr0wthlab'} check-beta-drafts --run {plan.run}".strip()


def rule_summary(plan: Plan) -> list[str]:
    brand = plan.context.rules
    if brand is None:
        return [
            f"- Brand rules: `brand-rules.json` could not be used ({plan.context.rules_problem}), so every recruiting"
            " Draft is blocked."
        ]
    statuses = [row for row in brand.statuses() if row.rule not in NOT_FOR_MESSAGES]
    by = {
        status: [row.rule for row in statuses if row.status == status] for status in ("applied", "pending", "unknown")
    }
    lines = [
        f"- Brand rules from `{plan.rules.brand_rules}`, run on the subject and the message:"
        f" {', '.join(by['applied'])}. The Hook's word cap and the pain-source rule are about posts, so a message is"
        " not held to them."
    ]
    if by["pending"]:
        lines.append(f"  Pending, until Mandu adds their lists: {', '.join(by['pending'])}.")
    if by["unknown"]:
        lines.append(f"  Unknown to gr0wthlab, so they block every Draft: {', '.join(by['unknown'])}.")
    return lines


def brief_lines(plan: Plan, repo_root: Path) -> list[str]:
    """What the agent is told once the gate is recorded and a Draft is due: which message to write and where, never
    who is invited. Nothing read from the Waitlist view is here."""
    if not plan.active or not plan.drafts:
        return []
    lines = [
        "## Beta Cohort recruiting",
        "",
        f"The Founder recorded in Mandu that a {plan.product} Beta Build passed Apple's review (approved"
        f" {plan.gate.record.approved_on}), so its Beta Cohort is being recruited from the Waitlist.",
        "The launcher chooses who is invited, from the view you cannot read, and attaches them to the item. You write"
        ' only the message, the same words for everyone, as the task definition\'s "Writing a recruiting Draft" and'
        " `workspace/instructions/beta-recruiting.md` describe.",
        "",
        "| Draft | Write it as | In the Review Queue |",
        "| --- | --- | --- |",
    ]
    for due in plan.drafts:
        lines.append(f"| {LABELS[due.purpose]} (`purpose: {due.purpose}`) | `{due.path}` | {draft_standing(due)} |")
    lines.append("")
    if plan.due(WAITLIST_ASK):
        lines.append(
            "- The Waitlist cannot fill the cohort yet, so the run also asks for the Waitlist ask: a message for people"
            " who have not signed up."
        )
    sources = ", ".join(f"`{source.path}`" for source in plan.rules.citable)
    lines += [
        f"- Package files a Draft may cite, in the Mandu checkout: {sources}.",
        f"  The invitation cites at least one line of the thesis's K8 files in `{plan.rules.k8}`.",
        *rule_summary(plan),
        f"- Check the Drafts before you finish: `{check_command(plan, repo_root)}`. The launcher offers the Founder"
        " only a Draft that passes every check, and blocks any other, naming the rule.",
        "",
    ]
    return lines


def result_detail(result: DraftResult) -> str:
    parts = [result.detail] if result.detail else []
    if result.item and result.status in (QUEUED, KEPT, APPROVED_BEFORE, REPEATED):
        parts.insert(0, f"`{result.item}`")
    if result.verdict and result.status == BLOCKED:
        count = len(grouped(result.verdict.blocks))
        parts.append(f"{count} failing check{'' if count == 1 else 's'}, listed below")
    if result.removed:
        parts.append("the Draft file was removed, since it held what looks like an email address")
    if result.withdrawn:
        parts.append(f"the open `{result.withdrawn}` was withdrawn")
    return "; ".join(parts)


def batch_line(plan: Plan, outcome: Outcome | None) -> str:
    """What became of the batch this run, in one sentence."""
    batch = plan.batch
    result = outcome.result(INVITATION) if outcome else None
    if batch.action == NONE:
        return f"no batch: {batch.why}"
    count = plural(len(batch.candidates), "entry", "entries")
    others = len(batch.candidates) - batch.good_fit
    mix = f"{batch.good_fit} good Fit" + (f", {others} with another Fit answer or none" if others else "")
    if result is None:
        return f"batch {batch.number} of {count} ({mix}) was chosen, but its Draft was not taken in"
    if result.status == QUEUED:
        return f"batch {batch.number} queued as `{result.item}`: {count} ({mix})"
    if result.status == KEPT:
        return f"batch {batch.number} stays open as `{result.item}`: {count} ({mix})"
    why = {
        MISSING: "it has no Draft",
        BLOCKED: "its Draft was blocked",
        REPEATED: "the Founder rejected its Draft, which has not changed",
    }.get(result.status, result.status)
    return f"batch {batch.number} of {count} ({mix}) was not offered: {why}"


def summary(plan: Plan | None, outcome: Outcome | None, problem: str = "") -> str:
    """The run report's one line on recruiting; empty before the gate, when there is nothing to say."""
    if plan is None or not plan.active:
        return ""
    if problem:
        return f"Beta Cohort recruiting: {problem}"
    short = gap_line(plan).rstrip(".")
    parts = [batch_line(plan, outcome), short[:1].lower() + short[1:]]
    return "Beta Cohort recruiting: " + "; ".join(part for part in parts if part) + "."


def report_lines(plan: Plan | None, outcome: Outcome | None, problem: str = "") -> list[str]:
    """The run report's section; none before the gate, which the Sources table reports as not recorded."""
    if plan is None or not plan.active:
        return []
    if plan.batch is None:
        return ["## Beta Cohort recruiting", "", f"- Beta Build: {plan.gate.detail}.", f"- This run: {problem}."]
    held = plan.held
    offered = sum(1 for entry in held.values() if entry["status"] == OFFERED)
    lines = [
        "## Beta Cohort recruiting",
        "",
        f"- Beta Build: {plan.gate.detail}.",
        f"- The Founder's counts, {plan.counts.line()}.",
        f"- {cohort_line(plan)}",
        f"- Invitations so far: {plural(len(invited(held)), 'entry', 'entries')} approved for invitation, {offered}"
        f" offered and waiting for the Founder's decision, {plural(plan.pool, 'sign-up')} that asked for an invitation"
        " not offered one yet."
        if plan.reading is not None and plan.reading.status == package.READ
        else f"- Invitations so far: {plural(len(invited(held)), 'entry', 'entries')} approved for invitation,"
        f" {offered} offered and waiting for the Founder's decision; the pool is unknown, as the view could not be"
        " used.",
        f"- This run: {problem or batch_line(plan, outcome)}.",
    ]
    if plan.gap:
        lines.append(f"- {gap_line(plan)}")
    lines.append(f"- Selection rule: {waitlist.SELECTION_RULE} Batches hold at most {plan.rules.batch_size}.")
    lines += rule_summary(plan)
    if outcome is None:
        return lines
    if outcome.record:
        lines.append(f"- Evidence, with every check of every Draft: `{outcome.record}`.")
    if outcome.results:
        lines += ["", "| Draft | Result | Detail |", "| --- | --- | --- |"]
        for result in outcome.results:
            detail = result_detail(result).replace("|", "\\|")
            lines.append(f"| {LABELS[result.purpose]} | {result.status} | {detail} |")
    for result in outcome.results:
        if result.verdict and result.status == BLOCKED:
            lines += ["", f"{LABELS[result.purpose]} blocked (`{result.draft}`):", ""]
            lines += [f"- {line}" for line in grouped(result.verdict.blocks)]
        if result.verdict and result.verdict.warnings:
            lines += ["", f"{LABELS[result.purpose]} warnings, which do not block:", ""]
            lines += [f"- {line}" for line in grouped(result.verdict.warnings)]
    return lines


def gaps(plan: Plan | None, outcome: Outcome | None, problem: str, agent_gap: str) -> list[str]:
    """Why recruiting is incomplete this run: a Draft the run asked for is missing, the brand rules or the view could
    not be used, or the agent or the take-in fell short. A blocked Draft is the check working, not a gap."""
    if plan is None or not plan.active:
        return []
    found = [problem] if problem else []
    if plan.context is None:
        return found
    if plan.context.rules is None:
        found.append("brand-rules.json could not be used")
    if plan.reading is not None and plan.reading.status == waitlist.REFUSED:
        found.append("the Waitlist view was refused, so no entry could be chosen")
    for result in outcome.results if outcome else ():
        if result.status == MISSING:
            found.append(f"no {LABELS[result.purpose]} Draft")
    if plan.drafts and agent_gap:
        found.append(agent_gap)
    return found


def notice_section(outcome: Outcome | None, day_text: str, again: bool = False) -> tuple[int, str, str] | None:
    """The blocked and missing Drafts, and every open item withdrawn, for the run's notice; None if there is none.
    again says a fresh, whole run follows this one by itself, which writes a missing Draft or reports on it itself,
    so a missing Draft is left out; an item this run withdrew is still named."""
    if outcome is None:
        return None
    missing = () if again else (MISSING,)
    lines = []
    for result in outcome.results:
        label = LABELS[result.purpose]
        if result.status == BLOCKED:
            failing = "; ".join(grouped(result.verdict.blocks)) if result.verdict else result.detail
            where = f" (`{result.draft}`)" if result.draft else ""
            lines.append(f"- The {label} Draft{where} was not offered: {failing}")
            if result.removed:
                lines.append("- The launcher removed that Draft file, so nothing it held is kept or repeated here.")
        elif result.status in missing:
            lines.append(f"- The {label} has no Draft, so it was not offered this run.")
        if result.withdrawn:
            why = f": {result.detail}" if result.status == NOT_DUE and result.detail else ", since it no longer stands"
            freed = " Its entries were not invited." if result.purpose == INVITATION else ""
            lines.append(f"- The open `{result.withdrawn}` is withdrawn{why}.{freed}")
    if not lines:
        return None
    count = sum(1 for result in outcome.results if result.status in (BLOCKED, *missing) or result.withdrawn)
    title = f"{plural(count, 'Beta Cohort recruiting item')} not offered or withdrawn on {day_text}"
    return count, title, "\n".join(lines)
