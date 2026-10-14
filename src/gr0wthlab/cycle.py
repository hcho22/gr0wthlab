"""One Marketing Engineer run, scheduled or on demand, from the pre-run sync to the saved records.

Order: bring the production clone up to origin's main; snapshot the Go-To-Market Package; take in the Founder's
decisions from ledger/founder/, which only `gr0wthlab sitting` writes (founder.py) and from which every Founder record
below is read; read the Waitlist's anonymous view, keeping only its counts; file the reviewed Dispatch requests
that need filing; plan the post Drafts from the 14-day kit (posts.prepare); file the filming plan and list and measure
the footage (filming.prepare); read the Founder's Beta Build record and, only once it exists, plan the Beta
Cohort's next invitation batch (beta.prepare); read the fixed list of network sources into one snapshot (fetch.Client,
the launcher's only way onto the network), which is working data removed when the run ends, and plan Listening from it
and outreach from the Founder's records; decide which workflows have work for the agent, and for each of those, one
after another in a fixed order, write its brief and run one agent session inside the sandbox, which has no network
(sessions.py, launcher.run), and after each session put back any change it made to the agent's Instructions, so no
session works from Instructions another changed; once the last session has ended, queue the items the sessions
wrote to workspace/review-queue/incoming/ that pass the format, a post for
each Draft that passes every check, with the video cut from its edit record when it has one (posts.take), the
recruiting Drafts that pass theirs (beta.take), the quotes, proposals, and messages that pass theirs (listening.take,
outreach.take), the code proposed for each rejection reason (learning.take), and the reviewed proposals that need
filing; count what each session did, for the report to show beside that session's own word (work.py); write the Review
Queue and the run report; commit and push workspace/ and ledger/. Every step but the sessions is deterministic code
outside the sandbox. The launcher's records live in ledger/, which an agent can read and never write, so nothing it
does can change them; in workspace/ the launcher only restores its owner's access to entries a session left without
it, removes what a stopped boundary check left at the top of the areas, before the first records step can commit it,
reads the Drafts and the edit records, reads the items in incoming/ before each session starts and once it has
ended, removes a recruiting Draft that holds what looks like an email address, reads and removes the items, quote
records, proposals, and codes it takes in, and after each session puts the agent's Instructions back as they were.
Nothing is taken in
while a session can still write: one take-in, after the last session, keeps every take-in rule what it was when a run
had one session. One run at a time per checkout holds the run lock in its ledger/ from the sync to the saved records;
a run started meanwhile refuses to start, and the next report says so.

One session's trouble stays its own workflow's: a session that does not start, is stopped at its time limit, or ends
with an error leaves the sessions after it to run, and marks only its own workflow's outputs incomplete. Every session
has the same time limit, counted for that session alone, and all of a run's sessions together have one bound
(config/run.json), so every run ends with its report.

A weekly scheduled start comes first as a check (attempts.py): it begins a run only while the launcher's records show
the week's run is still owed and the Mac is fully awake, and every run notes there how it ended, so a weekly run the
Mac's sleep cut short, wherever in it the sleep fell, is followed by a fresh one and no other run is. A one-off
scheduled start (--once) always runs, as a run on demand does.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shlex
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO, TypeVar

from . import (
    attempts,
    beta,
    dispatch,
    evidence,
    exchange,
    fetch,
    filming,
    footage,
    founder,
    launcher,
    learning,
    listening,
    messages,
    outreach,
    package,
    posts,
    process,
    proposals,
    records,
    report,
    sessions,
    settings,
    sources,
    waitlist,
    work,
)
from . import state as run_state
from .areas import Areas, Store, UnsafeFile, clear_probe_files, read_plain
from .boundary import FOUNDER, LEDGER, Boundary, ConfigError, canonical, load_boundary, load_json
from .queue import INCOMING, OPEN, QUEUE_FILE, REVIEW_QUEUE, SET_ASIDE, SUPERSEDED, Ledger, QueueError, Stands
from .report import COMPLETE, INCOMPLETE, NOT_BUILT, SKIPPED, RunState, SourceLine, Unusable
from .sessions import Session

PRE_RUN_ENV = "GR0WTHLAB_PRE_RUN"
EXIT_RECORDS = 4
EXIT_BUSY = 5
EXIT_STOPPED = launcher.EXIT_STOPPED
LOCK_FILE = "run.lock"
NOTES_DIR = "notes"
RUN_REPORTS = "run-reports"
SNAPSHOTS = "package-snapshots"
SUMMARY_LIMIT = 4000
WAITLIST_NEEDS = ("waitlist-counts", "weekly-read", "beta-recruiting")
WORKING = "working"
FILMING = "filming"
# The folders, each inside one of the agent's areas, that the launcher takes the agent's work in from.
INTAKE = (
    ("evidence", listening.QUOTES_IN),
    ("evidence", learning.CODES_IN),
    ("review_queue", listening.ANGLES_IN),
    ("drafts", messages.DRAFTS),
    ("drafts", listening.REPLIES_IN),
    ("drafts", outreach.FOLDER),
)
# The package review's row when it is complete: complete by the agent's closing line alone, so the row says whose word
# that is and where the launcher's own counts are.
REVIEW_SAID_COMPLETE = "the agent said it finished its review; the launcher's counts are under Sessions"
# The two counts made from what stands in workspace/ before a session starts and once it has ended.
WRITTEN = "the Draft claims and the proposals"
T = TypeVar("T")


def entry_point(repo_root: Path) -> Path:
    return repo_root / "src" / "bin" / "gr0wthlab"


def head(repo_root: Path) -> str:
    try:
        asked = process.run(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"], process.QUICK)
    except OSError:
        return "unknown"
    return asked.stdout.strip() if asked.ok else "unknown"


def output_titles(config: settings.Settings, keys: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(config.outputs.get(key, {}).get("title", key)) for key in keys)


# The Founder's records, read only: a run never writes one (founder.py).


def unusable(name: str, problems: Sequence[str], content: bytes | None = None) -> Unusable:
    """A record that could not be used, fingerprinted by its name and its content, or by its problems when it could not
    be read, so it is reported again only once that changes."""
    data = "; ".join(problems).encode("utf-8") if content is None else content
    return Unusable(name, tuple(problems), run_state.digest(f"{name}\n{hashlib.sha256(data).hexdigest()}"))


def read_records(ledger: Path, kind: str) -> tuple[list[founder.Raw], list[Unusable], str | None]:
    """(name, path, bytes) for every record file of one kind in ledger/founder/, the files there that are no record,
    and why the folder itself could not be read, if it could not."""
    found, others, failure = founder.read(ledger, kind)
    return found, [unusable(founder.named(kind, name), [why]) for name, why in others], failure


def parse_records(kind: str, found, parser) -> tuple[list[tuple[object, Path, str]], list[Unusable]]:
    """Each record a parser could use, with its path and fingerprint, and each it could not (founder.parse)."""
    parsed, problems = [], []
    for name, path, data in found:
        record, issues = founder.parse(name, data, parser)
        if issues:
            problems.append(unusable(founder.named(kind, name), issues, data))
        else:
            parsed.append((record, path, hashlib.sha256(data).hexdigest()))
    return parsed, problems


def named_item(record: Unusable) -> Unusable:
    """A decision record with the item its file is named for."""
    name = Path(record.name)
    return replace(record, item=name.stem) if name.suffix == ".json" else record


# The run.


class Cycle:
    def __init__(
        self,
        repo_root: Path,
        env: Mapping[str, str],
        home: Path,
        out: TextIO,
        clock: Callable[[], datetime],
        client: Callable[[fetch.Policy], fetch.Client] | None = None,
        clocks: process.Clock = process.CLOCK,
    ):
        self.repo_root = repo_root
        self.env = env
        self.home = home
        self.out = out
        self.clock = clock
        self.client = client or fetch.Client  # the real network, through fetch.send, unless a test gives another
        self.clocks = clocks
        self.store = Store(canonical(repo_root) / LEDGER)
        self.started: datetime | None = None
        self.run_id: str | None = None
        self.due: datetime | None = None  # when a weekly start's run was due, once its settings could be read
        self.unsure = False  # the Mac did not say whether it was fully awake when a weekly start asked
        self.noted = False  # how this run ended is in the record of the run due at its time
        self.since: Callable[[], tuple[float, float]] | None = None  # the clocks' reading from this start's beginning
        self.before = (0.0, 0.0)  # what this start had taken when it restarted on new code, as taken() gives it

    def say(self, message: str) -> None:
        print(f"gr0wthlab: {message}", file=self.out)

    def now(self) -> datetime:
        return self.clock()

    def taken(self) -> tuple[float, float]:
        """The seconds since this start began, then those of them the Mac was awake, a restart on new code included,
        on the clocks every time limit is measured on."""
        seconds, awake = self.since()
        return self.before[0] + seconds, self.before[1] + awake

    def asleep(self) -> float:
        """About how many seconds the Mac has been asleep since this start began, by the measure and the tolerance of
        the agent's own time; 0 when it stayed awake."""
        return report.asleep_for(*self.taken())

    def snapshot(self, state: RunState, config: settings.Settings, boundary: Boundary, registry) -> None:
        mandu = next(location.path for location in boundary.locations if location.label == "Mandu")
        state.mandu = str(mandu)
        directory = self.store.path("evidence", SNAPSHOTS)
        previous = package.latest_snapshot(directory, state.run_id)
        state.previous_snapshot = previous[0] if previous else None
        sources = package.package_sources(registry)
        state.snapshot = package.take(
            mandu, sources, package.last_known(previous[1] if previous else None), lambda: self.now().isoformat()
        )
        path = directory / f"{state.run_id}.json"
        self.store.write_json(
            path, package.record(state.run_id, self.now(), mandu, state.snapshot, state.previous_snapshot)
        )
        state.snapshot_file = self.store.relative(path)
        for result in state.snapshot:
            needs = output_titles(config, ("package-snapshot", "package-review", *result.source.needed_by))
            label = f"{result.source.product} package"
            if result.reason:
                state.sources.append(
                    SourceLine(f"{label}: `{result.source.path}`", package.FAILED, f"{result.reason}.", needs)
                )
            for file in result.files:
                line = SourceLine(f"{label}: `{file.path}`", file.status, report.file_line(file), needs)
                state.sources.append(line)
            for removed in result.removed:
                state.sources.append(
                    SourceLine(f"{label}: `{removed}`", package.CHANGED, "removed since the previous snapshot", needs)
                )

    def take_decisions(
        self,
        state: RunState,
        config: settings.Settings,
        ledger: Ledger,
        ledger_ok: bool,
        review_state: run_state.ReviewQueueState,
    ) -> None:
        """Take in the Founder's decision and sitting records from ledger/founder/; when the ledger could not be read,
        no decision is matched and only sittings are taken in. A sitting that left no sitting record is still kept
        as one that took place, from the date each decision given at it carries, so what it left undecided carries
        over; its time is then not recorded. A decision record for an item still open that cannot
        be used is reported at every run until the Founder decides the item again on the page; any other record that
        cannot be used is reported by the first run to find it as it is, and the Review Queue state remembers it by
        its fingerprint while it stays so.

        The page may change a decision until a run has taken it in, so the reading and the taking in happen under the
        lock the page holds for a change (founder.locked). A lock that stays held takes in nothing this run.
        """
        needs = output_titles(config, ("decisions", "review-queue"))
        sitting_needs = output_titles(config, ("review-queue",))
        state.reported_before = set(review_state.reported)
        try:
            with founder.locked(self.store.root):
                self.take_records(state, ledger, ledger_ok, review_state, needs, sitting_needs)
        except founder.Busy as error:
            detail = f"{error}, so no decision and no sitting was taken in this run; the next run takes them in."
            state.sources.append(SourceLine("Founder decisions", package.FAILED, detail, needs))
            state.sources.append(SourceLine("Sittings", package.FAILED, detail, sitting_needs))

    def take_records(
        self,
        state: RunState,
        ledger: Ledger,
        ledger_ok: bool,
        review_state: run_state.ReviewQueueState,
        needs: tuple[str, ...],
        sitting_needs: tuple[str, ...],
    ) -> None:
        root = self.store.root
        unmatched = (
            None
            if ledger_ok
            else SourceLine(
                "Founder decisions",
                SKIPPED,
                "the Review Queue could not be read, so no decision could be matched to its item",
                needs,
            )
        )
        found, problems, failure = ([], [], None) if unmatched else read_records(root, founder.DECISIONS)
        decisions, more = parse_records(founder.DECISIONS, found, exchange.parse_decision)
        problems += more
        sittings_found, sitting_problems, sitting_failure = read_records(root, founder.SITTINGS)
        sittings, more = parse_records(founder.SITTINGS, sittings_found, exchange.parse_sitting)
        sitting_problems += more
        now = self.now()
        outcomes = ledger.take_decisions([d for d, _, _ in decisions], state.run_id, now)
        state.decisions = [outcome for outcome in outcomes if outcome.status in ("taken", "already-taken")]
        contents = {name: data for name, _, data in found}
        for outcome in outcomes:
            if outcome.status in ("unknown-item", "conflict"):
                name = f"{outcome.decision.item}.json"
                why = [report.outcome_text(outcome.status)]
                problems.append(unusable(founder.named(founder.DECISIONS, name), why, contents[name]))
        problems = [named_item(record) for record in problems]
        state.unusable = problems + sitting_problems
        reported = {record.fingerprint for record in state.unusable}
        review_state.reported = sorted(reported | state.reported_before if failure or sitting_failure else reported)
        digests = {d.item: (self.store.relative(path), digest) for d, path, digest in decisions}
        for outcome in state.decisions:
            if outcome.status != "taken":
                continue
            decision, entry = outcome.decision, outcome.entry
            source, digest = digests[decision.item]
            self.store.write_json(
                self.store.path(*founder.TAKEN_IN, f"{decision.item}.json"),
                {
                    "item": decision.item,
                    "kind": entry["kind"],
                    "ask": entry["ask"],
                    "item_file": entry["file"],
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "note": decision.note,
                    "decided_at": decision.decided_at,
                    "sitting": decision.sitting,
                    "superseded_by": entry.get("superseded_by"),
                    "source": {"path": source, "sha256": digest},
                    "taken_in_by_run": state.run_id,
                    "taken_in_at": now.isoformat(),
                },
            )
            entry["evidence"] = f"evidence/decisions/{decision.item}.json"
            for key in ("reason", "note"):
                if getattr(decision, key):
                    entry[key] = getattr(decision, key)
        for sitting, path, digest in sittings:
            target = self.store.path("evidence", "sittings", f"{sitting.day}.json")
            record = {
                "date": sitting.day,
                "minutes": sitting.minutes,
                "note": sitting.note,
                "source": {"path": self.store.relative(path), "sha256": digest},
            }
            try:
                existing = json.loads(read_plain(target).decode("utf-8"))
            except (UnsafeFile, ValueError):
                existing = None
            existing = existing if isinstance(existing, dict) else None
            if existing is None or existing.get("source") != record["source"]:
                first = (existing or {}).get("taken_in_by_run", state.run_id)
                self.store.write_json(target, dict(record, taken_in_by_run=first))
                state.sittings.append(sitting)
        # A sitting that ended without its record still took place: each decision given at it carries its date. Its
        # time is not known, and is kept as null, never as zero. A decision is the only other sign of a sitting a
        # run reads: one that left neither leaves no mark.
        given: dict[str, list[str]] = {}
        for outcome in state.decisions:
            if outcome.status == "taken" and outcome.decision.sitting:
                given.setdefault(outcome.decision.sitting, []).append(digests[outcome.decision.item][0])
        recorded = {sitting.day for sitting, _, _ in sittings}
        unusable_records = {record.name for record in sitting_problems}
        for day in sorted(set(given) - recorded):
            target = self.store.path("evidence", "sittings", f"{day}.json")
            try:
                known = isinstance(json.loads(read_plain(target).decode("utf-8")), dict)
            except (UnsafeFile, ValueError):
                known = False
            if known:
                continue
            record = {"date": day, "minutes": None, "note": None, "source": None, "shown_by": sorted(given[day])}
            self.store.write_json(target, dict(record, taken_in_by_run=state.run_id))
            # Only a folder that was read, and that holds no file for the date, shows that no time was recorded.
            if not sitting_failure and founder.named(founder.SITTINGS, f"{day}.json") not in unusable_records:
                state.untimed.append(day)
        taken = sum(1 for outcome in state.decisions if outcome.status == "taken")
        if unmatched:
            state.sources.append(unmatched)
        elif failure:
            detail = f"`{FOUNDER}/{founder.DECISIONS}/` could not be read: {failure}."
            state.sources.append(SourceLine("Founder decisions", package.FAILED, detail, needs))
        else:
            detail = f"{report.plural(len(found), 'record')}, {taken} new since the previous run" + (
                f", {len(problems)} could not be used" if problems else ""
            )
            state.sources.append(
                SourceLine("Founder decisions", package.CHANGED if taken else package.READ, detail, needs)
            )
        if sitting_failure:
            detail = f"`{FOUNDER}/{founder.SITTINGS}/` could not be read: {sitting_failure}."
            state.sources.append(SourceLine("Sittings", package.FAILED, detail, sitting_needs))
        else:
            detail = f"{report.plural(len(sittings_found), 'record')}, {len(state.sittings)} new" + (
                f", {len(sitting_problems)} could not be used" if sitting_problems else ""
            )
            state.sources.append(SourceLine("Sittings", package.CHANGED if state.sittings else package.READ, detail))

    def read_waitlist(self, state: RunState, config: settings.Settings, rules: settings.Waitlist | None) -> None:
        """Read the Waitlist's anonymous view before the agent starts and keep its counts as Evidence when it is usable;
        the agent reads only those counts, never the view, which lies outside everything the sandbox can read."""
        reading = state.waitlist = waitlist.read(rules, state.started)
        needs = output_titles(config, WAITLIST_NEEDS)
        state.sources.append(SourceLine(waitlist.SOURCE_NAME, reading.status, reading.detail, needs))
        if reading.status == package.READ:
            path = self.store.path("evidence", "waitlist", f"{state.run_id}.json")
            self.store.write_json(path, waitlist.evidence(reading, state.run_id, self.now()))
            state.waitlist_file = self.store.relative(path)

    def file_dispatches(
        self,
        state: RunState,
        ledger: Ledger,
        products: Sequence[str],
        seen: dict[str, str],
        hashes: Mapping[str, str],
    ) -> None:
        """File each reviewed Dispatch request that needs filing, before the agent starts, so its brief lists it."""
        requests, problems = dispatch.load(self.repo_root, products)
        state.problems += problems
        state.dispatches = dispatch.file(ledger, self.store, requests, products, seen, state.run_id, self.now(), hashes)
        state.problems += [filing.account() for filing in state.dispatches if filing.status == dispatch.HELD]
        state.dispatch_unread = dispatch.unread(problems, state.dispatches)
        state.published += [str(filing.identifier) for filing in state.dispatches if filing.acted]

    def queue_notice(
        self,
        state: RunState,
        ledger: Ledger,
        seen: dict[str, str],
        notice: tuple[str, str, str, str],
        slug: str,
        what: str,
        product: str | None = None,
    ) -> str | None:
        """Queue one of the launcher's notices, unless the same one is already waiting for the Founder; its identifier
        either way, or None when it could not be written."""
        title, body, touches, evidence = notice
        fields = {"kind": "notice", "product": product} if product else {"kind": "notice"}
        item = exchange.Item(fields, title, body, touches, evidence)
        fingerprint = exchange.item_hash(item)
        repeated = seen.get(fingerprint)
        if repeated and ledger.entries[repeated]["status"] == OPEN:
            return repeated
        try:
            identifier = ledger.publish(self.store, item, slug, state.run_id, self.now())
        except (OSError, ConfigError) as error:
            state.problems.append(f"{what} could not be written ({error})")
            return None
        state.published.append(identifier)
        seen.setdefault(fingerprint, identifier)
        return identifier

    def sitting_runs(self, state: RunState) -> dict[str, str]:
        """Each sitting known so far, by date, with the run that first took in a record of it: its sitting record,
        or a decision given at it."""
        runs = {}
        folder = self.store.path("evidence", "sittings")
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            try:
                record = json.loads(read_plain(path).decode("utf-8"))
                runs[str(record["date"])] = str(record["taken_in_by_run"])
            except (OSError, ValueError, KeyError, TypeError, UnsafeFile) as error:
                name = self.store.relative(path)
                state.problems.append(f"`{name}` could not be read, so no item carries over from it ({error})")
        return runs

    def load_state(self, state: RunState, run_id: str) -> run_state.States:
        """Each workflow's run state; an invalid file is set aside and its workflow starts again from the record."""
        states, invalid = run_state.load(self.store)
        for workflow, path, reason in invalid:
            target = self.store.path(REVIEW_QUEUE, SET_ASIDE, run_id, f"{RUN_REPORTS}--state--{path.name}")
            self.store.move(path, target)
            rebuilt = "rebuilt from the Review Queue" if workflow == run_state.REVIEW_QUEUE else "started empty"
            where = f"set aside as `{self.store.relative(target)}`"
            state.problems.append(f"the {workflow} run state was not valid ({reason}); it was {where} and {rebuilt}")
        return states

    def save_state(
        self, state: RunState, ledger: Ledger, states: run_state.States, products: Sequence[str], now: datetime
    ) -> None:
        """Bring the Review Queue state into line with the ledger, note every difference, and save every state."""
        hashes, _ = run_state.item_hashes(self.store.root, ledger.entries, products, states.review_queue)
        states.review_queue, state.state_notes = run_state.reconcile(states.review_queue, ledger.entries, hashes)
        if state.beta is not None:
            state.state_notes += state.beta.notes
        run_state.save(self.store, states, state.run_id, now.isoformat())

    def tallies(self, state: RunState, ledger: Ledger, incoming: int, ledger_ok: bool) -> list[run_state.Tally]:
        """What each workflow checked and acted on this run, so a quiet run still says what it looked at."""
        files = [file for result in state.snapshot for file in result.files]
        failed = sum(1 for file in files if file.status == package.FAILED) + sum(
            1 for result in state.snapshot if result.reason
        )
        changed = sum(1 for file in files if file.status == package.CHANGED)
        filed = {str(filing.identifier) for filing in state.dispatches if filing.acted}
        breach = state.breach_notice if state.breach_notice in state.published else None
        queued = [ledger.entries[i] for i in state.published if i not in filed and i != breach]
        # Each queued item counts once, under the workflow that produced it; until a workflow has its own tally
        # (Weekly Reads), its items count under the Review Queue with the launcher's notices.
        outcome = state.post_outcome
        drafting = set(outcome.published if outcome else ()) | ({state.filed} if state.filed else set())
        drafting |= set(state.beta_outcome.published if state.beta_outcome else ())
        if state.filming is not None and state.filming.standing.acted:
            drafting.add(state.filming.standing.item)
        drafting |= set(state.work_published)  # counted by Listening and outreach, each under its own workflow
        gap = state.agent_gap
        proposals = sum(
            1 for entry in queued if entry["kind"] == "package-change-proposal" and entry["id"] not in drafting
        )
        others = sum(
            1 for entry in queued if entry["kind"] != "package-change-proposal" and entry["id"] not in drafting
        )
        taken = sum(1 for outcome in state.decisions if outcome.status == "taken")
        superseded = sum(
            1
            for entry in ledger.entries.values()
            if entry["status"] == SUPERSEDED
            and entry.get("closed_by_run") == state.run_id
            and not entry.get("withdrawn")
        )
        carried = sum(1 for entry in state.queue_after if entry.get("carried_over"))
        records = len(state.decisions) + len(state.unusable)
        return [
            run_state.Tally(
                "package-review",
                len(files) + sum(1 for result in state.snapshot if result.reason),
                proposals,
                f"{report.plural(len(files), 'file')}, {changed} changed, {failed} failed;"
                f" {report.plural(proposals, 'proposal')} queued",
                state.review_gap(),
            ),
            run_state.Tally(
                "review-queue",
                records + incoming + len(state.queue_before),
                taken + others + superseded,
                f"{report.plural(taken, 'decision')} taken in, {report.plural(others, 'other item')} queued,"
                f" {superseded} superseded, {carried} carried over, {len(state.set_aside)} set aside",
            ),
            self.waitlist_tally(state, breach),
            run_state.Tally(
                "dispatch-requests",
                len(state.dispatches),
                len(filed),
                "; ".join(filing.account() for filing in state.dispatches)
                or ("no reviewed Dispatch request" if ledger_ok else "none filed: the Review Queue could not be read"),
                "; ".join(state.dispatch_unread),
            ),
            self.post_tally(state),
            self.filming_tally(state),
            self.beta_tally(state),
            listening.tally(state.listening, state.listening_result, state.listening_problem, gap(listening.WORKFLOW)),
            outreach.tally(state.outreach, state.outreach_result, state.outreach_problem, gap(outreach.WORKFLOW)),
            learning.tally(state.learning, state.learning_problem, gap(learning.WORKFLOW)),
        ]

    def waitlist_tally(self, state: RunState, breach: str | None) -> run_state.Tally:
        """The Waitlist's line: the sign-ups counted, or why there are no counts; a routine read acts on nothing, and a
        breach notice queued this run is the one thing it acts on."""
        reading = state.waitlist
        if reading is None or reading.status == SKIPPED:
            return run_state.Tally("waitlist", 0, 0, f"skipped: {reading.detail if reading else 'not read'}")
        if reading.status == package.READ:
            note = f"{report.plural(len(reading.entries), 'sign-up')} counted; {report.waitlist_progress(reading)}"
            return run_state.Tally("waitlist", len(reading.entries), 0, note)
        if reading.status == waitlist.REFUSED:
            note = "read refused" + (f"; breach notice `{breach}` queued" if breach else "")
            return run_state.Tally("waitlist", 0, int(bool(breach)), note, "the view held what looks like an address")
        return run_state.Tally("waitlist", 0, 0, "no counts this run", "the view could not be used")

    def post_tally(self, state: RunState) -> run_state.Tally:
        """What the post-Draft workflow checked and acted on: each Draft taken in, each item queued or withdrawn, and
        the brand-rules proposal when this run filed it, whether or not any Draft was taken in."""
        outcome = state.post_outcome
        gaps = self.post_gaps(state)
        if outcome is None:
            checked, acted = 0, 0
            note = state.posts_problem or "no calendar day was prepared"
        else:
            checked = len(outcome.results)
            acted = len(outcome.published) + len(outcome.withdrawn)
            note = f"{report.plural(checked, 'day')}: {', '.join(outcome.counts()) or 'none due'}"
            if outcome.withdrawn:
                note += f"; {len(outcome.withdrawn)} withdrawn"
        if state.filed:
            acted += 1
            note += "; the brand-rules proposal filed"
        return run_state.Tally("post-drafts", checked, acted, note, "; ".join(gaps))

    def filming_tally(self, state: RunState) -> run_state.Tally:
        if state.filming is None and state.filming_problem:
            return run_state.Tally("filming", 0, 0, state.filming_problem, state.filming_problem)
        return filming.tally(state.filming, state.agent_gap(FILMING))

    def beta_tally(self, state: RunState) -> run_state.Tally:
        """What Beta Cohort recruiting checked and acted on: the sign-ups that asked for an invitation, and each item
        queued or withdrawn. Before the Founder's gate it checks and acts on nothing, and says why."""
        plan, outcome = state.beta, state.beta_outcome
        if plan is None:
            return run_state.Tally(beta.WORKFLOW, 0, 0, "no Product recruits a Beta Cohort")
        if not plan.active:
            why = (
                "no Beta Build approval is recorded"
                if plan.gate.status == beta.NOT_RECORDED
                else "the Beta Build record could not be used"
            )
            return run_state.Tally(beta.WORKFLOW, 0, 0, f"not started: {why}")
        reading = plan.reading
        checked = len(reading.candidates) if reading is not None and reading.status == package.READ else 0
        acted = len(outcome.published) + len(outcome.withdrawn) if outcome else 0
        note = state.beta_problem or beta.batch_line(plan, outcome)
        if plan.gap:
            note += f"; the pool is {plan.gap} short of {plan.rules.minimum}"
        return run_state.Tally(beta.WORKFLOW, checked, acted, note, "; ".join(self.beta_gaps(state)))

    def beta_gaps(self, state: RunState) -> list[str]:
        return beta.gaps(state.beta, state.beta_outcome, state.beta_problem, state.agent_gap(beta.WORKFLOW))

    def post_gaps(self, state: RunState) -> list[str]:
        """Why the post Drafts are incomplete this run: a kit file, the code, or the brand rules could not be used,
        a Draft could not be checked because something its check needs could not be read, a due day has no Draft, or
        the post Drafts session or the take-in fell short. A Draft blocked by a check the launcher could make is the
        check working, not a gap."""
        plan, outcome = state.posts, state.post_outcome
        if plan is None:
            return [state.posts_problem] if state.posts_problem else []
        gaps = posts.unchecked(plan)
        if outcome is None:
            gaps.append(state.posts_problem or "the Drafts were not taken in")
        else:
            gaps += [reason for reason in outcome.unread if reason not in gaps]
            missing = [str(result.day) for result in outcome.results if result.status == posts.MISSING]
            if missing:
                gaps.append(f"no Draft for day {', '.join(missing)}")
        gap = state.agent_gap(sessions.POSTS)
        if plan.days and gap:
            gaps.append(gap)
        # A kit file the run read and could not use is named by its failed source, which leads the row: once is enough.
        unusable = {line.name for line in state.sources if line.status == package.UNUSABLE}
        paths = plan.context.paths
        told = {role for role, path in paths.items() if f"{plan.product} package: `{path}`" in unusable}
        said = {f"`{paths[role]}` could not be used" for role in told}
        said |= {"brand-rules.json could not be used"} if "brand_rules" in told else set()
        return [reason for reason in gaps if reason not in said]

    def queue_gaps(self, state: RunState) -> list[str]:
        """Why the Review Queue is incomplete this run though the ledger was read: an item file could not be, so a
        reviewed Dispatch request, or an item the agent wrote, could not be compared with the item it would replace,
        which therefore stands, or with one it may ask again, so it was not queued."""
        review_queue = [reason for title, kept in state.stood if title == state.queue_title for reason in kept.unread]
        return list(dict.fromkeys(state.dispatch_unread + state.queue_unread + review_queue))

    def left_standing(self, state: RunState, config: settings.Settings, ledger: Ledger) -> None:
        """Gather each open item this run left exactly as it was because a read its standing rests on could not be
        made, with the output it belongs to: what every workflow decided through queue.stands, in one list, so the
        run's notice names each item and the read that failed."""
        state.queue_title = output_titles(config, ("review-queue",))[0]
        found: list[tuple[str, Stands]] = []

        def add(key: str, results: Sequence) -> None:
            title = output_titles(config, (key,))[0]
            found.extend((title, Stands(str(result.item), tuple(result.unread))) for result in results if result.stood)

        add("post-drafts", state.post_outcome.results if state.post_outcome else ())
        if state.filming is not None and state.filming.stood:
            found.append((output_titles(config, ("filming-plan",))[0], state.filming.stood))
        add(beta.WORKFLOW, state.beta_outcome.results if state.beta_outcome else ())
        add("listening", state.listening_result.replies if state.listening_result else ())
        add("outreach-drafts", state.outreach_result.outcomes if state.outreach_result else ())
        if state.outreach is not None:
            found += [(output_titles(config, ("outreach-drafts",))[0], kept) for kept in state.outreach.stood]
        found += [
            (state.queue_title, Stands(str(filing.identifier), (filing.unread,)))
            for filing in state.dispatches
            if filing.status == dispatch.UNREAD
        ]
        found += [(state.queue_title, kept) for kept in ledger.stood]
        state.stood = found

    def outputs(self, state: RunState, config: settings.Settings, ledger_ok: bool) -> None:
        """Each output's status: a built output is incomplete when a failed source it needs names it, or when its own
        step fell short. A step that needed a session names that session's falling short among its gaps, and the
        outputs whose rows hold that gap are the ones the run's notice names for the session; the rows are therefore
        worked out before that notice is written, and again once the Review Queue holds it. One session's gap is
        never put in another workflow's row, and a session that fell short always has its gap in its own."""
        failed = state.failed_sources()
        gap = state.agent_gap
        decisions = next((line.detail for line in state.sources if line.name == "Founder decisions"), "")
        queued = report.plural(len(state.queue_after), "open item") + (
            f"; {len(state.set_aside)} set aside" if state.set_aside else ""
        )
        review_gap = state.review_gap()
        review = state.session(sessions.REVIEW)
        reviewed = REVIEW_SAID_COMPLETE if review is None or review.due else f"no session: {review.why}"
        reading = state.waitlist
        skipped = {"waitlist-counts": reading.detail} if reading and reading.status == SKIPPED else {}
        if state.beta is None or state.beta.gate.status == beta.NOT_RECORDED:
            skipped[beta.WORKFLOW] = (
                "the Founder has recorded no approved Beta Build" if state.beta else "no Product recruits one"
            )
        if state.filming is None and not state.filming_problem:
            skipped["filming-plan"] = "no active Product films"
        heard, offered = gap(listening.WORKFLOW), gap(outreach.WORKFLOW)
        own = {
            "package-snapshot": ([], f"`{state.snapshot_file}`"),
            "package-review": ([review_gap] if review_gap else [], reviewed),
            "decisions": ([] if ledger_ok else ["the ledger could not be read; no decision was matched"], decisions),
            "review-queue": (
                self.queue_gaps(state) if ledger_ok else ["the ledger could not be read; the queue was left as it was"],
                queued,
            ),
            "waitlist-counts": (
                ["the read was refused, as the view held what looks like an email address (Guardrail G6)"]
                if reading and reading.status == waitlist.REFUSED
                else [],
                f"`{state.waitlist_file}`",
            ),
            "post-drafts": (self.post_gaps(state), self.post_tally(state).note),
            beta.WORKFLOW: (self.beta_gaps(state), self.beta_tally(state).note),
            "filming-plan": (
                filming.gaps(state.filming, gap(FILMING)) if state.filming is not None else [state.filming_problem],
                self.filming_tally(state).note,
            ),
            "listening": (
                listening.gaps(state.listening, state.listening_result, state.listening_problem, heard),
                listening.tally(state.listening, state.listening_result, state.listening_problem, heard).note,
            ),
            "outreach-drafts": (
                outreach.gaps(state.outreach, state.outreach_result, state.outreach_problem, offered),
                outreach.tally(state.outreach, state.outreach_result, state.outreach_problem, offered).note,
            ),
            "rejection-codes": (
                learning.gaps(state.learning, state.learning_problem, gap(learning.WORKFLOW)),
                learning.tally(state.learning, state.learning_problem, gap(learning.WORKFLOW)).note,
            ),
        }
        rows = []
        held: dict[str, list[str]] = {session.key: [] for session in state.sessions}
        for key, output in config.outputs.items():
            title = str(output.get("title", key))
            if not output.get("built"):
                rows.append([title, NOT_BUILT, str(output.get("story", ""))])
                continue
            if key in skipped:
                rows.append([title, SKIPPED, skipped[key]])
                continue
            gaps, done = own.get(key, ([], ""))
            for session in state.sessions:
                if session.workflow.output == key and session.gap() and session.gap() in gaps:
                    held[session.key].append(title)
            gaps = [f"{line.name} {line.failure}" for line in failed if title in line.needed_by] + gaps
            rows.append([title, INCOMPLETE if gaps else COMPLETE, "; ".join(gaps) or done])
        state.outputs = rows
        for session in state.sessions:
            session.incomplete = tuple(held[session.key])

    def prepare_posts(
        self, state: RunState, config: settings.Settings, registry, boundary: Boundary, ledger: Ledger
    ) -> None:
        """The run's post-Draft plan, with its record of each day's standing for check-drafts, and the Product code it
        checks claims against as one of the run's sources."""
        try:
            plan = posts.prepare(self.repo_root, config, registry, boundary, ledger, self.now(), self.env, state.run_id)
            if plan is not None:
                record = self.store.path(RUN_REPORTS, posts.plan_file(state.run_id))
                self.store.write_json(record, posts.plan_record(plan))
        except (ConfigError, OSError) as error:
            state.posts_problem = f"not prepared: {error}"
            state.problems.append(f"the post Drafts could not be prepared ({error})")
            return
        if plan is None:
            return
        state.posts = plan
        code = state.posts.code
        needs = output_titles(config, ("post-drafts",))
        if code.problem:
            state.sources.append(SourceLine(f"{code.name} repository", package.FAILED, f"{code.problem}.", needs))
        else:
            detail = f"`{code.branch}` at `{code.short}`, read at that commit for claim checks"
            state.sources.append(SourceLine(f"{code.name} repository", package.READ, detail, needs))

    def unusable_sources(self, state: RunState, config: settings.Settings) -> None:
        """Mark each package file the snapshot read that launcher code then could not use, as it could not be parsed
        or decoded, as a failed source, with the real reason and the outputs whose own gap already names it: a kit
        file for the post Drafts and, of the files the filming plan reads, for filming; the brand rules for
        recruiting; and the channel plan for outreach. A file whose read failed is a failed source already, and one
        file is one line however many steps could not use it."""
        found: dict[tuple[str, str], tuple[dict[str, None], dict[str, None]]] = {}  # file: (reasons, output keys)

        def add(product: str, path: str, reason: str, *keys: str) -> None:
            reasons, outputs = found.setdefault((product, path), ({}, {}))
            reasons[reason.rstrip(".")] = None
            outputs.update(dict.fromkeys(keys))

        plan = state.posts
        if plan is not None:
            paths = plan.context.paths
            for role, problem in plan.context.kit.problems.items():
                if role in paths:
                    filmed = state.filming is not None and role in filming.ROLES
                    add(plan.product, paths[role], problem, "post-drafts", *["filming-plan"] * filmed)
            if plan.context.rules is None and plan.context.rules_problem and "brand_rules" in paths:
                add(plan.product, paths["brand_rules"], plan.context.rules_problem, "post-drafts")
        recruiting = state.beta
        if recruiting is not None and recruiting.active and recruiting.context is not None:
            if recruiting.context.rules is None and recruiting.context.rules_problem:
                rules = recruiting.rules
                add(rules.product, rules.brand_rules, recruiting.context.rules_problem, beta.WORKFLOW)
        if state.outreach is not None and state.outreach.unusable:
            add(state.outreach.product, state.outreach.plan_path, state.outreach.unusable, "outreach-drafts")
        for (product, path), (reasons, keys) in found.items():
            name = f"{product} package: `{path}`"
            under = name[:-1] if path.endswith("/") else name  # a folder's files are named under it
            covered = [line for line in state.sources if line.name.startswith(under)]
            if not covered or any(line.status == package.FAILED for line in covered):
                continue  # not read by the snapshot, or its read failed: either way not a file read and unusable
            line = next((line for line in covered if line.name == name), None)
            if line is None:  # a folder whose files were each read, and which could not be used as a whole
                line = SourceLine(name, package.UNUSABLE, "")
                state.sources.append(line)
            told = f"{line.detail.rstrip('.')}; read, but" if line.detail else "Read, but"
            line.status = package.UNUSABLE
            line.detail = f"{told} could not be used: {'; '.join(reasons)}."
            line.needed_by = output_titles(config, tuple(keys))

    def prepare_filming(
        self,
        state: RunState,
        config: settings.Settings,
        where: filming.Place | None,
        areas: Areas,
        ledger: Ledger,
        ledger_ok: bool,
        products: Sequence[str],
        seen: dict[str, str],
    ) -> None:
        """The run's filming standing, fixed before the agent starts: the filming plan filed or found, and the
        footage place listed and measured, with the video tooling and the footage place as two of the run's
        sources. Tooling that is missing is a skipped source, so its edits are skipped, never a failed run."""
        if where is None:
            return
        if state.posts is None:
            state.filming_problem = "not planned: the post Drafts, whose calendar the plan reads, were not prepared"
            return
        if not ledger_ok:
            state.filming_problem = "not planned: the Review Queue could not be read"
            return
        try:
            found = filming.prepare(
                canonical(self.repo_root),
                state.posts,
                where,
                ledger,
                self.store,
                areas,
                products,
                seen,
                self.env,
                state.run_id,
                self.now(),
            )
            self.store.write_json(self.store.path(RUN_REPORTS, filming.record_file(state.run_id)), found.as_record())
        except (ConfigError, OSError) as error:
            state.filming_problem = f"not planned: {error}"
            state.problems.append(f"the filming plan could not be prepared ({error})")
            return
        state.filming = found
        if found.standing.acted:
            state.published.append(str(found.standing.item))
        needs = output_titles(config, ("filming-plan",))
        tooling = found.tooling
        detail = tooling.describe() if tooling.ok else f"{tooling.problem}; every edit is skipped until it can be used"
        state.sources.append(SourceLine("Video tooling", package.READ if tooling.ok else SKIPPED, detail, needs))
        inventory = found.inventory
        status = {footage.READ: package.READ, footage.FAILED: package.FAILED}.get(inventory.status, SKIPPED)
        state.sources.append(SourceLine("Footage place", status, inventory.detail, needs))

    def take_posts(
        self,
        state: RunState,
        areas: Areas,
        ledger: Ledger,
        products: Sequence[str],
        run_id: str,
        now: datetime,
        seen: dict[str, str],
    ) -> None:
        """Queue each Draft that passes, record every check, and file the brand-rules proposal unless it ever was."""
        if state.posts is not None:
            try:
                state.post_outcome = posts.take(
                    state.posts, areas, self.store, ledger, run_id, now, products, state.filming
                )
                state.published += state.post_outcome.published
                posts.record(state.posts, state.post_outcome, self.store, run_id, now)
            except (OSError, ConfigError) as error:
                state.posts_problem = f"not taken in: {error}"
                state.problems.append(f"the post Drafts could not be taken in ({error})")
        if state.filming is not None:
            state.filming.settle(state.post_outcome, self.store)
            try:
                filming.record(state.filming, self.store, run_id, now)
            except (OSError, ConfigError) as error:
                state.problems.append(f"the run's filming record could not be written ({error})")
        rules = state.posts.context.rules if state.posts else None
        try:
            filing = proposals.file_once(
                canonical(self.repo_root),
                proposals.BRAND_RULES,
                rules.data if rules else None,
                self.store,
                ledger,
                products,
                run_id,
                now,
                seen,
            )
        except (OSError, ConfigError) as error:
            state.problems.append(f"`{proposals.BRAND_RULES}` could not be filed ({error})")
            return
        if filing.status == proposals.FILED:
            state.filed = filing.item
            state.published.append(filing.item)
        elif filing.status == proposals.UNUSABLE:
            state.problems.append(f"`{filing.source}` could not be filed: {filing.detail}")
        state.filing = proposals.describe(filing, ledger)

    def prepare_beta(
        self,
        state: RunState,
        config: settings.Settings,
        rules: beta.Rules | None,
        registry,
        boundary: Boundary,
        ledger: Ledger,
        ledger_ok: bool,
        areas: Areas,
        previous: run_state.BetaRecruitingState,
    ) -> None:
        """Read the Founder's Beta Build record, the gate, as one of the run's sources. Before it exists nothing else
        happens here: the Founder's reports are not read, no entry is chosen, and nothing is written. Once it does,
        fix the run's recruiting plan and record which Drafts are due for check-beta-drafts. A run whose Review Queue
        could not be read stops at the gate as well, since only the Review Queue says who is invited or offered."""
        if rules is None:
            return
        needs = output_titles(config, (beta.WORKFLOW,))
        root = self.store.root
        found, others, failure = founder.read(root, beta.BUILDS)
        gate = beta.read_gate(rules.product, self.relative_records(found), others, failure)
        if gate.recorded and not ledger_ok:
            state.beta = beta.Plan(rules, gate, state.run_id)
            state.beta_problem = "not prepared: the Review Queue could not be read"
        else:
            reports, reports_failure, unreadable = None, None, []
            if gate.recorded:
                reports, others, reports_failure = founder.read(root, beta.REPORTS)
                reports = self.relative_records(reports)
                for name, why in others:
                    state.problems.append(f"{founder.shown(beta.REPORTS, name)} could not be used ({why})")
                unreadable = [name for name, why in others if why != founder.STRAY]
            try:
                state.beta = beta.prepare(
                    rules,
                    gate,
                    reports,
                    reports_failure,
                    registry,
                    boundary,
                    ledger,
                    previous,
                    state.waitlist,
                    state.waitlist_file,
                    self.store,
                    state.run_id,
                    self.now(),
                    unreadable,
                )
                if state.beta.active:
                    record = self.store.path(RUN_REPORTS, beta.plan_file(state.run_id))
                    self.store.write_json(record, beta.plan_record(state.beta, areas))
            except (ConfigError, OSError) as error:
                state.beta = beta.Plan(rules, gate, state.run_id)
                state.beta_problem = f"not prepared: {error}"
                state.problems.append(f"Beta Cohort recruiting could not be prepared ({error})")
        for name, status, detail in beta.source_lines(state.beta):
            state.sources.append(SourceLine(name, status, detail, needs))

    def relative_records(self, found: Sequence[founder.Raw]) -> list[founder.Raw]:
        """Record files with each path given from ledger/, the form a record that is kept names its source in."""
        return [(name, Path(self.store.relative(path)), data) for name, path, data in found]

    def take_beta(
        self,
        state: RunState,
        areas: Areas,
        ledger: Ledger,
        products: Sequence[str],
        run_id: str,
        now: datetime,
    ) -> None:
        """Queue each recruiting Draft that passes, the invitation with its batch attached, and record every check."""
        plan = state.beta
        if plan is None or not plan.active or plan.batch is None or state.beta_problem:
            return
        try:
            state.beta_outcome = beta.take(plan, areas, self.store, ledger, run_id, now, products)
            state.published += state.beta_outcome.published
        except (OSError, ConfigError) as error:
            state.beta_problem = f"not taken in: {error}"
            state.problems.append(f"the Beta Cohort recruiting Drafts could not be taken in ({error})")

    def settle_beta(
        self, state: RunState, ledger: Ledger, states: run_state.States, run_id: str, now: datetime
    ) -> None:
        """Once the run's notice exists: take the recruiting items that no longer stand off the queue, bring the run
        state to where the Review Queue now stands, and keep the run's recruiting Evidence."""
        if state.beta_outcome is None:
            return
        beta.withdraw(ledger, state.beta_outcome, state.notice, run_id, now)
        states.beta_recruiting = beta.settle(states.beta_recruiting, ledger.entries, state.beta)
        try:
            beta.record(state.beta, state.beta_outcome, self.store, run_id, now)
        except (OSError, ConfigError) as error:
            state.problems.append(f"the Beta Cohort recruiting Evidence could not be written ({error})")

    def clear_probe_files(self) -> list[str]:
        """Remove what a stopped boundary check left in the areas before the pre-run records step commits workspace/,
        and return it. A checkout whose boundary cannot be resolved is left as it is: no check could start in it
        either, and whether this run starts is for the code the sync brings to say."""
        try:
            _, boundary = load_boundary(self.repo_root, self.env, self.home)
        except ConfigError:
            return []
        left = clear_probe_files(boundary)
        if left:
            self.say(f"pre-run: removed boundary probe files left in the areas: {', '.join(left)}")
        return left

    def research_apps(
        self, state: RunState, config: sources.Config, mandu: Path
    ) -> tuple[list[sources.App], list[str], str]:
        """The App Store apps whose reviews this run reads: the competitors the research in Mandu names, as the
        post-Draft checks already read them, each by the store page its own section cites; the names with none; and
        why the research could not be used, if it could not."""
        if config.app_store is None:
            return [], [], ""
        plan = state.posts
        if plan is None or "competitors" in plan.context.kit.problems:
            why = plan.context.kit.problems["competitors"] if plan else state.posts_problem or "no kit was read"
            return [], [], f"the competitors could not be read from the research ({why}), so no review was read"
        competitors = plan.context.kit.competitors
        folder = mandu / plan.context.paths["competitors"]
        texts = {}
        for name in sorted({competitor.source for competitor in competitors}):
            try:
                texts[name] = (folder / name).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        apps, missing = sources.research_apps(competitors, texts, config.app_store.country)
        return apps, missing, ""

    def read_sources(
        self,
        state: RunState,
        config: settings.Settings,
        policy: fetch.Policy,
        source_config: sources.Config,
        mandu: Path,
        seen: run_state.ListeningState,
    ) -> tuple[sources.Snapshot, list[tuple[str, str]], str]:
        """Read the fixed list of network sources, outside the sandbox, into this run's snapshot, and keep the
        request log; every source's result goes into the run report, read or not."""
        self.discard_working()
        now = self.now()
        apps, missing, research_problem = self.research_apps(state, source_config, mandu)
        limit = source_config.app_store.max_apps if source_config.app_store else 0
        skipped = [(f"App Store reviews: {name}", "the research cites no App Store page for it") for name in missing]
        skipped += [
            (f"App Store reviews: {app.name}", f"over this run's limit of {limit} apps") for app in apps[limit:]
        ]
        client = self.client(policy)
        snapshot = listening.read_sources(client, source_config, apps, seen, state.run_id, now)
        needs = output_titles(config, ("listening",))
        for reading in snapshot.readings:
            state.sources.append(SourceLine(reading.source.name, reading.status, reading.detail, needs))
        state.sources += [SourceLine(name, SKIPPED, why) for name, why in skipped]
        if research_problem:
            detail = f"{research_problem[0].upper()}{research_problem[1:]}."
            state.sources.append(SourceLine("App Store reviews", package.FAILED, detail, needs))
        if snapshot.readings:
            path = self.store.path(WORKING, f"{state.run_id}.sources.json")
            self.store.write_json(path, snapshot.as_json())
            state.snapshot_sources = self.store.relative(path)
            log = self.store.path(RUN_REPORTS, f"{state.run_id}.requests.json")
            self.store.write_json(log, dict(client.summary(), run=state.run_id))
            state.requests_file = self.store.relative(log)
        return snapshot, skipped, research_problem

    def discard_working(self) -> None:
        """Remove what a run fetched over the network: working data for that run alone, which is gone when the run
        ends and which no later run reads."""
        shutil.rmtree(str(self.store.path(WORKING)), ignore_errors=True)

    def prepare_work(
        self,
        state: RunState,
        config: settings.Settings,
        registry: Mapping,
        boundary: Boundary,
        areas: Areas,
        ledger: Ledger | None,
        states: run_state.States,
        network: tuple[fetch.Policy, sources.Config, outreach.Settings],
    ) -> None:
        """Before the first session: read the network sources, plan Listening from them and outreach from the
        Founder's outreach records, and record both plans for each session's own check. Each step fails on its own;
        with no ledger, as when the Review Queue could not be read, nothing is filed or matched."""
        policy, source_config, outreach_settings = network
        mandu = next(location.path for location in boundary.locations if location.label == "Mandu")
        today = self.now().astimezone().date()
        try:
            snapshot, skipped, research_problem = self.read_sources(
                state, config, policy, source_config, mandu, states.listening
            )
            fit = listening.package_role(registry)
            fit_readable = fit is not None and any(
                file.path == fit[1] and file.status != package.FAILED
                for result in state.snapshot
                for file in result.files
            )
            limits, _ = messages.run_limits(canonical(self.repo_root), registry, config.waitlist_live(today))
            state.listening = listening.prepare(
                registry,
                source_config,
                snapshot,
                state.snapshot_sources,
                self.store,
                ledger,
                fit_readable,
                limits,
                state.run_id,
                self.now(),
            )
            if state.listening is not None:
                state.listening.skipped, state.listening.research_problem = skipped, research_problem
                state.problems += state.listening.problems.values()
                state.published += state.listening.filed
                state.work_published += state.listening.filed
        except (OSError, ConfigError, sources.SourceError) as error:
            state.listening_problem = f"not prepared: {error}"
            state.problems.append(f"Listening could not be prepared ({error})")
        try:
            records, counted = outreach.Records(), ""
            if ledger is not None:
                found, problems, failure = read_records(self.store.root, founder.OUTREACH)
                parsed, more = parse_records(founder.OUTREACH, found, exchange.parse_outreach)
                bad = {Path(record.name).name: "; ".join(record.problems) for record in problems + more}
                records = outreach.Records(tuple(record for record, _, _ in parsed), bad, failure or "")
                if found or bad or failure:
                    counted = report.plural(len(found), "record") + (f", {len(bad)} could not be used" if bad else "")
            try:
                if ledger is not None:
                    state.outreach, states.outreach = outreach.prepare(
                        canonical(self.repo_root),
                        outreach_settings,
                        registry,
                        mandu,
                        ledger,
                        records,
                        states.outreach,
                        areas,
                        self.now(),
                        state.run_id,
                        config.waitlist_live(today),
                    )
                else:
                    state.outreach_problem = "not prepared: the Review Queue could not be read"
            finally:
                unread = state.outreach.unread if state.outreach is not None else []
                needs = output_titles(config, ("outreach-drafts",))
                if records.failure:
                    detail = f"`{FOUNDER}/{founder.OUTREACH}/` could not be read: {records.failure}."
                    line = SourceLine("Outreach records", package.FAILED, detail, needs)
                elif unread:
                    detail = "; ".join(f"{who}: {why}" for who, why in unread) + "."
                    line = SourceLine("Outreach records", package.FAILED, detail, needs)
                elif counted:
                    line = SourceLine("Outreach records", package.READ, counted, needs)
                else:
                    line = SourceLine("Outreach records", SKIPPED, "no message has been recorded as sent yet")
                state.sources.append(line)
        except (OSError, ConfigError, run_state.StateError) as error:
            state.outreach_problem = f"not prepared: {error}"
            state.problems.append(f"the outreach messages could not be prepared ({error})")
        try:
            if ledger is not None:
                state.reasons, problems = learning.reasons(self.store, ledger)
                learning.answered(
                    self.store, ledger, [str(p["name"]) for p in registry.get("products", [])], state.reasons
                )
                state.problems += problems
            record = {
                "run": state.run_id,
                "listening": listening.plan_record(state.listening) if state.listening else None,
                "outreach": outreach.plan_record(state.outreach, areas) if state.outreach else None,
            }
            self.store.write_json(self.store.path(RUN_REPORTS, f"{state.run_id}.work-plan.json"), record)
        except (OSError, ConfigError) as error:
            state.problems.append(f"the plan for the agent's own check could not be written ({error})")
        overrides = (
            " ".join(f"{name}={shlex.quote(path)}" for name, path in state.posts.locations) if state.posts else ""
        )
        entry = canonical(self.repo_root) / "src/bin/gr0wthlab"
        state.check_work = f"{overrides} /usr/bin/python3 {entry} check-work --run {state.run_id}".strip()
        for area, parts in INTAKE:
            for depth in range(1, len(parts) + 1):
                areas.ensure_folder(areas.path(area, *parts[:depth]))

    def take_work(
        self,
        state: RunState,
        areas: Areas,
        ledger: Ledger,
        ledger_ok: bool,
        products: Sequence[str],
        run_id: str,
        now: datetime,
        seen: dict[str, str],
    ) -> None:
        """After the last session: take in the Listening work, the outreach Drafts, and the codes proposed for
        rejection reasons, each on its own."""
        if not ledger_ok:
            unread = "not taken in: the Review Queue could not be read"
            state.listening_problem = state.listening_problem or unread
            state.outreach_problem = state.outreach_problem or unread
            state.learning_problem = "the rejection reasons were not read: the Review Queue could not be read"
            return
        context = state.posts.context if state.posts else None
        if state.listening is not None:
            try:
                state.listening_result = listening.take(
                    state.listening, context, areas, self.store, ledger, run_id, now, products, seen
                )
                state.published += state.listening_result.published
                state.work_published += state.listening_result.published
            except (OSError, ConfigError) as error:
                state.listening_problem = f"not taken in: {error}"
                state.problems.append(f"the Listening work could not be taken in ({error})")
        plan = state.outreach
        if plan is not None and not plan.problem:
            try:
                if context is None:
                    state.outreach_problem = "not taken in: the kit could not be read, so no message could be checked"
                else:
                    state.outreach_result = outreach.take(
                        plan, context, areas, self.store, ledger, run_id, now, products
                    )
                    state.published += state.outreach_result.published
                    state.work_published += state.outreach_result.published
            except (OSError, ConfigError) as error:
                state.outreach_problem = f"not taken in: {error}"
                state.problems.append(f"the outreach Drafts could not be taken in ({error})")
        if plan is not None and plan.slots:
            self.file_outreach_lists(state, context, ledger, products, run_id, now, seen)
        try:
            state.learning = learning.take(areas, self.store, ledger, products, run_id, now)
            state.problems += [problem for problem in state.learning.problems if problem not in state.problems]
        except (OSError, ConfigError, ValueError) as error:
            state.learning_problem = f"the rejection reasons could not be coded ({error})"
            state.problems.append(state.learning_problem)

    def file_outreach_lists(self, state: RunState, context, ledger: Ledger, products, run_id, now, seen) -> None:
        """File the loss-framing and sponsorship lists proposal unless it ever was, or Mandu's file holds them."""
        rules = context.rules if context else None
        try:
            filing = proposals.file_once(
                canonical(self.repo_root),
                outreach.RULES_PROPOSAL,
                rules.data if rules else None,
                self.store,
                ledger,
                products,
                run_id,
                now,
                seen,
            )
        except (OSError, ConfigError) as error:
            state.problems.append(f"`{outreach.RULES_PROPOSAL}` could not be filed ({error})")
            return
        if filing.status == proposals.FILED:
            state.published.append(filing.item)
            state.work_published.append(filing.item)
        elif filing.status == proposals.UNUSABLE:
            state.problems.append(f"`{filing.source}` could not be filed: {filing.detail}")
        state.outreach_filing = proposals.describe(filing, ledger)

    def counted(self, state: RunState, what: str, count: Callable[[], T]) -> T | None:
        """Make one count of a session, for the run report to show beside the agent's own word. The counts gate
        nothing, so a count that cannot be made is a launcher problem, told once however many sessions it is missing
        from, and the run goes on without it."""
        try:
            return count()
        except (OSError, ConfigError) as error:
            problem = f"{what} could not be counted ({error})"
            if problem not in state.problems:
                state.problems.append(problem)
            return None

    def count_work(
        self,
        state: RunState,
        config: settings.Settings,
        log_dir: Path,
        readings: Mapping[str, tuple[work.Standing | None, work.Standing | None]],
        taken_in: bool,
    ) -> None:
        """Count what each session did, once the last has ended and the run's items are taken in. readings holds, for
        each session that ran, what stood in workspace/ of the Drafts due and of incoming/ before it started and once
        it had ended: a Draft or a proposal is a session's own only when that session wrote or changed it, so nothing
        an earlier run or another session left is counted as its work, and without both readings neither its Draft
        claims nor its proposals are counted. The run's totals are read the same way, from before its first session
        to after its last. taken_in says whether the launcher took in what stood in incoming/."""
        mandu = Path(state.mandu)
        set_aside = {item.name for item in state.set_aside}
        ran = state.ran

        def queued(written: work.Written) -> list[str]:
            return [name for name in written.proposals if taken_in and name not in set_aside]

        for session in ran:
            before, after = readings.get(session.key, (None, None))
            claims = proposals = None
            if before is not None and after is not None:
                written = work.written(before, after)
                claims, proposals = written.claims, work.count_proposals(written.proposals, queued(written))
            files = {
                file.path: mandu / file.path
                for file in report.brief_files(state, session)
                if file.status != package.FAILED
            }
            events = log_dir / f"{launcher.log_name(state.run_id, session.key)}.events.jsonl"
            session.work = self.counted(
                state,
                f"the {session.title} session's work",
                lambda events=events, files=files, claims=claims, proposals=proposals: work.measure(
                    events, config.shown_output_chars, files, claims, proposals
                ),
            )
        first = readings.get(ran[0].key, (None, None))[0] if ran else None
        last = readings.get(ran[-1].key, (None, None))[1] if ran else None
        if first is not None and last is not None:
            whole = work.written(first, last)
            state.claims = whole.claims
            state.proposals = work.count_proposals(whole.proposals, queued(whole), whole_run=True)

    def nothing_due(self, state: RunState, key: str) -> str:
        """Why one workflow has no work for the agent this run, or "" when it has, from what the launcher read before
        the first session. A workflow has work exactly when the launcher can name it: a package file to review, a
        calendar day whose copy is not approved, a day ready for an edit record, a recruiting Draft, a thread or a
        review to read, a message that is due, a rejection reason with no code, or a strategy reason with no
        proposal. This is the one test of a session: it decides whether the session starts, and a session it starts
        that falls short always leaves its own workflow's output incomplete, whatever it had written by then, since
        every workflow's gap rule adds the gap of a session that was due (Session.gap)."""
        if key == sessions.REVIEW:
            read = [file for result in state.snapshot for file in result.files if file.status != package.FAILED]
            return "" if read else "no package file could be read"
        if key == sessions.POSTS:
            plan = state.posts
            if plan is None:
                problem = state.posts_problem
                return f"the post Drafts were {problem}" if problem else "no active Product has a 14-day kit"
            if "calendar" in plan.context.kit.problems:
                return "the calendar could not be used"
            if not plan.days:
                return "no calendar day is due this run"
            waiting = any(not day_plan.approved for day_plan in plan.days)
            return "" if waiting else "the Founder approved every calendar day due this run"
        if key == FILMING:
            found = state.filming
            if found is None:
                problem = state.filming_problem
                return f"filming was {problem}" if problem else "no active Product films"
            return "" if found.ready() else "no calendar day is ready for an edit record"
        if key == beta.WORKFLOW:
            plan = state.beta
            if plan is None:
                return "no Product recruits a Beta Cohort"
            if state.beta_problem:
                return f"recruiting was {state.beta_problem}"
            if not plan.active:
                return (
                    "the Founder has recorded no approved Beta Build"
                    if plan.gate.status == beta.NOT_RECORDED
                    else "the Beta Build record could not be used"
                )
            return "" if plan.drafts else "no recruiting Draft is due this run"
        if key == listening.WORKFLOW:
            plan = state.listening
            if plan is None:
                problem = state.listening_problem
                return f"Listening was {problem}" if problem else "no active Product listens"
            if not plan.snapshot.readings and not plan.skipped:
                return "no Listening source is configured"
            return "" if plan.heard() else "no thread or review could be read this run"
        if key == outreach.WORKFLOW:
            plan = state.outreach
            if plan is None:
                problem = state.outreach_problem
                return f"outreach was {problem}" if problem else "no active Product has a channel plan"
            if plan.problem:
                return plan.problem
            return "" if plan.due() else "no outreach message is due this run"
        waiting = learning.uncoded(state.reasons) or learning.owed(state.reasons)
        return "" if waiting else "no rejection reason needs a code or a proposal"

    def plan_sessions(self, state: RunState, config: settings.Settings) -> None:
        """Decide once, before the first session starts, which workflows have work for the agent this run, in the
        order their sessions run. A workflow with nothing due starts no session, and the report says why."""
        state.run_limit = config.agent.run_time_limit
        state.sessions = []
        for found in sessions.WORKFLOWS:
            why = self.nothing_due(state, found.key)
            state.sessions.append(Session(found, not why, why, config.agent.time_limit))

    def waiting_items(self, areas: Areas) -> list[tuple[str, str]]:
        """Each file standing in incoming/ now, by its name, for the brief of a session that may write items: what
        an earlier session of this run, or an earlier run, left there. Only the names are told, so a brief, which is
        the launcher's record, repeats none of an agent's words; the session reads the files themselves."""
        incoming = areas.path("review_queue", INCOMING)
        try:
            names = sorted(os.listdir(str(incoming))) if areas.real_folder(incoming) else []
        except OSError:
            return []
        return [(name, "not taken in yet") for name in names]

    def drafts_in_place(self, state: RunState, areas: Areas) -> list[tuple[int, str]]:
        """For the Filming session's brief: each day ready for an edit record, with whether its post Draft is in
        place, as the post Drafts session of this run or an earlier run left it."""
        found = state.filming
        days = []
        for number in found.ready() if found is not None else []:
            draft, problem = posts.read_draft(areas, found.draft_path(number))
            name = found.draft_path(number).name
            if draft is not None:
                days.append((number, f"`{name}` is in place"))
            elif problem:
                days.append((number, f"`{name}` cannot be read ({problem}), so write no edit record for it this run"))
            else:
                days.append((number, "no post Draft, so write no edit record for it this run"))
        return days

    def write_brief(self, state: RunState, session: Session, areas: Areas) -> Path:
        """Write one session's brief just before it starts, so it can name what earlier sessions left."""
        brief = self.store.path(RUN_REPORTS, f"{state.run_id}.{session.key}.brief.md")
        waiting = self.waiting_items(areas) if session.workflow.writes_items else []
        in_place = self.drafts_in_place(state, areas) if session.key == FILMING else []
        text = report.render_brief(
            state,
            session,
            canonical(self.repo_root),
            areas.workspace,
            self.store.root,
            report.brief_files(state, session),
            waiting,
            in_place,
        )
        self.store.write_text(brief, text)
        session.brief = self.store.relative(brief)
        return brief

    def run_sessions(
        self,
        state: RunState,
        config: settings.Settings,
        definitions: Mapping[str, str],
        areas: Areas,
        products: Sequence[str],
    ) -> dict[str, tuple[work.Standing | None, work.Standing | None]]:
        """Run one agent session for each workflow that has work due, one after another, and return what stood in
        workspace/ before and after each, for the counts. Each session is a fresh Codex process with the same
        command, proved against the boundary before its agent starts, with its own brief and task definition, under
        the one time limit every session has. A session that does not start, is stopped at its limit, or ends with
        an error leaves the next to run. Once a session has ended, the launcher takes back its access to what the
        session left and puts the agent's Instructions back as the run noted them before its first session, so
        every session starts from those and none reads what another changed; each change it undoes is told once,
        with the session it was found after.
        A session starts only while the bound on all of the run's sessions together has time left, and gets what is
        left of it when that is less than a session's limit."""
        root = canonical(self.repo_root)
        log_dir = launcher.default_log_dir(self.env, self.home)
        readings: dict[str, tuple[work.Standing | None, work.Standing | None]] = {}
        resolved = None  # what configures every session, resolved before the first and shared by all of them
        for session in sessions.due(state.sessions):
            # In tenths of a second, as a session's time is recorded, so that a limit reads as plainly as it is kept.
            left = round(state.run_limit - state.agent_seconds, 1)
            if left <= 0:
                bound = process.limit_text(state.run_limit)
                why = f"the {bound} that bounds all of a run's sessions together was used up before its turn"
                self.not_started(session, EXIT_STOPPED, why, out_of_time=True)
                continue
            before = self.counted(state, WRITTEN, lambda: work.standing(state.posts, areas, products))
            try:
                resolved = resolved or launcher.Resolved(self.repo_root, self.env, self.home)
            except (OSError, ConfigError) as error:
                # Fail closed for this session, and resolve again for the next: what failed may have been passing.
                self.not_started(session, launcher.EXIT_CONFIG, str(error))
                continue
            try:
                brief = self.write_brief(state, session, areas)
                session.record = launcher.run(
                    self.repo_root,
                    sessions.definition_files(root, session.workflow)[-1],
                    state.trigger,
                    self.env,
                    self.home,
                    out=self.out,
                    now=state.started,
                    facts=[sessions.header(state.sessions, session), f"Run brief, read it first: {brief}"],
                    run_id=state.run_id,
                    time_limit=min(session.limit, left),
                    session=session.key,
                    instruction=definitions[session.key],
                    resolved=resolved,
                )
            except OSError as error:
                self.not_started(session, launcher.EXIT_CONFIG, str(error))
            name = launcher.log_name(state.run_id, session.key)
            last_message = log_dir / f"{name}.last-message.md"
            if session.started and last_message.is_file():
                summary = last_message.read_text(encoding="utf-8", errors="replace")
                session.summary = summary[:SUMMARY_LIMIT]
                session.closing = (summary.strip().splitlines() or [""])[-1].strip()
            if session.started:
                session.usage = report.token_usage(log_dir / f"{name}.events.jsonl")
                session.error = sessions.last_error(log_dir / f"{name}.events.jsonl")
            if session.usage:
                session.cost = report.cost(session.usage, config.prices)
            left_running = report.left_running(session) if session.timed_out else None
            if left_running:
                state.problems.append(left_running)
            # Before the next session reads workspace/, and before anything is counted or taken in from it.
            state.problems += [problem for problem in records.restore_access(root) if problem not in state.problems]
            undone = [f"after the {session.title} session: {line}" for line in learning.put_back(state.guidance, areas)]
            state.put_back += undone
            state.problems += [f"{line}; no run may change its own Instructions yet" for line in undone]
            if session.started:
                after = (
                    self.counted(state, WRITTEN, lambda: work.standing(state.posts, areas, products))
                    if before is not None
                    else None
                )
                readings[session.key] = (before, after)
        # Once more when no session was due, so that a run with no agent still leaves workspace/ readable.
        state.problems += [problem for problem in records.restore_access(root) if problem not in state.problems]
        return readings

    def not_started(self, session: Session, code: int, why: str, **more: object) -> None:
        """Record that a session the run came to was not started, with the launcher's exit status for that and the
        reason, which the run report and the notice give as it is."""
        session.record = dict({"session": session.key, "agent_started": False, "exit_code": code, "error": why}, **more)
        self.say(f"session {session.key} was not started: {why}")

    def exit_code(self, state: RunState) -> int:
        """The run's exit status: 0 when every session it had work for ended without an error, and otherwise that of
        the first session that fell short, which is EXIT_STOPPED for one stopped at a limit."""
        short = state.short
        if not short:
            return 0
        if short[0].shortfall == attempts.TIMED_OUT:
            return EXIT_STOPPED
        code = short[0].exit_code
        return code if isinstance(code, int) and not isinstance(code, bool) and code else 1

    def leave_note(self, run_id: str, line: str) -> None:
        """A one-line note in ledger/notes/, which the next run's report shows."""
        self.store.write_text(self.store.path(NOTES_DIR, f"{run_id}.txt"), line + "\n")

    def lock(self, trigger: str) -> TextIO | None:
        """This checkout's run lock in its ledger/, held until the returned file is closed; None if another run holds
        it, in which case the refusal is left as a note for the next run report."""
        path = self.store.path(LOCK_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            now = self.now()
            run_id = launcher.new_run_id(trigger, now)
            line = (
                f"Run {run_id} ({trigger}) was refused at {report.wall_clock(now):%A %Y-%m-%d %H:%M}:"
                " another run was in progress."
            )
            self.leave_note(run_id, line)
            self.say("refusing to start: another run is in progress; the next run's report will say so")
            return None
        return handle

    def owed(self) -> int | None:
        """A weekly scheduled start is first a check of the launcher's own records: None while the week's run is still
        owed and the Mac is fully awake, and otherwise the exit status of a start that begins nothing. The check takes
        no lock and writes nothing, so the LaunchAgent can make it every few minutes, and it prints its reason only at
        a terminal, so a LaunchAgent's log does not grow by a line each time."""
        try:
            config = settings.load(self.repo_root, self.env, self.home)
        except ConfigError as error:
            self.say(f"refusing to start: {error}")
            return launcher.EXIT_CONFIG
        self.due = report.due_time(self.now(), config.weekly)
        record = attempts.load(self.store, self.due)
        why = attempts.waiting(record, config.attempts_per_week)
        if not why:
            awake = attempts.fully_awake()
            self.unsure = awake is None
            why = "" if awake or self.unsure else "the Mac is not fully awake, and a run starts only while it is"
        if why and self.out.isatty():
            self.say(f"nothing to start: {why}")
        return 0 if why else None

    def claim(self, state: RunState, config: settings.Settings) -> attempts.Attempt | None:
        """Under the run lock, note this weekly scheduled attempt in the record of the run due at its time before
        anything else is done, so that an attempt that never ends still counts; None when the record shows that no run
        is owed after all, as when another start completed it meanwhile."""
        record = attempts.load_to_write(self.store, state.due)
        why = attempts.waiting(record, config.attempts_per_week)
        if why:
            self.say(f"nothing to start: {why}")
            return None
        if record.problem:
            state.problems.append(
                f"the record of the attempts at the run due {report.moment(state.due)} could not be used"
                f" ({record.problem}); it was set aside and started again, so this run may repeat one already made"
            )
        if self.unsure:
            state.problems.append(
                "the Mac did not say whether it was fully awake, so this run started without knowing; a run started"
                " in a dark wake is likely to be cut short by sleep"
            )
        self.due = state.due
        return attempts.claim(self.store, record, config.attempts_per_week, state.started)

    def note_ending(self, state: RunState, config: settings.Settings) -> None:
        """Note how this run ended in the record of the run due at its time, which the next weekly start reads to
        tell whether a run is still owed. A run on demand or a one-off scheduled run is noted at the weekly time
        before it started and is never an attempt, so one that completed counts as that week's run."""
        if state.attempt:
            due, kind = state.due, attempts.SCHEDULED
        else:
            due = report.due_time(state.started, config.weekly)
            kind = attempts.ONE_OFF if state.trigger == attempts.SCHEDULED else attempts.ON_DEMAND
        attempts.finish(self.store, due, kind, state.started, state.run_id, state.ending, self.now(), state.slept)
        self.noted = True
        follows = report.what_follows(state)
        if follows:
            self.say(follows)

    def note_no_report(self, trigger: str, ending: str) -> None:
        """Note the ending of a weekly scheduled start that never reached its report, refused or stopped by an error.
        One the Mac slept during was cut short by sleep, as a run that reached its report would be; any other does not
        earn another attempt, so the owed-run check does not start it again every few minutes."""
        if trigger != attempts.SCHEDULED or self.due is None or self.noted:
            return
        try:
            started = self.started or self.now()
            asleep = self.asleep()
            ending = attempts.SLEPT if asleep else ending
            attempts.finish(self.store, self.due, trigger, started, self.run_id, ending, self.now(), asleep)
        except (OSError, ConfigError) as error:
            self.say(f"how this start ended could not be noted ({error})")

    def run(
        self,
        trigger: str,
        once: str | None,
        argv: Sequence[str],
        execve: Callable[[str, list[str], Mapping[str, str]], None] = os.execve,
    ) -> int:
        self.since = self.clocks.start()
        if trigger == attempts.SCHEDULED and once is None and not self.env.get(PRE_RUN_ENV):
            code = self.owed()
            if code is not None:
                return code
        lock = self.lock(trigger)
        if lock is None:
            return EXIT_BUSY
        with lock:
            try:
                for name, line in attempts.left_without_ending(self.store):
                    self.leave_note(name, line)
                code = self.locked_run(trigger, once, argv, execve)
            except (OSError, ConfigError) as error:
                started = self.started or self.now()
                run_id = self.run_id or launcher.new_run_id(trigger, started)
                line = (
                    f"Run {run_id} ({trigger}), started {report.wall_clock(started):%A %Y-%m-%d %H:%M}, stopped"
                    f" before it finished: {error}."
                )
                self.leave_note(run_id, line)
                self.say(f"the run stopped: {error}; the next run's report will say so")
                self.note_no_report(trigger, attempts.STOPPED)
                return EXIT_STOPPED
            finally:
                self.discard_working()
            if code:
                self.note_no_report(trigger, attempts.REFUSED)
            return code

    def locked_run(
        self,
        trigger: str,
        once: str | None,
        argv: Sequence[str],
        execve: Callable[[str, list[str], Mapping[str, str]], None],
    ) -> int:
        pre = json.loads(self.env[PRE_RUN_ENV]) if self.env.get(PRE_RUN_ENV) else None
        started = datetime.fromisoformat(pre["started_at"]) if pre else self.now()
        self.started, self.run_id = started, None
        if pre:
            self.before = tuple(pre.get("taken", self.before))
        try:
            config = settings.load(self.repo_root, self.env, self.home)
            definitions = sessions.definitions(canonical(self.repo_root))
            if trigger not in launcher.TRIGGERS:
                raise ConfigError(f"trigger must be one of {', '.join(launcher.TRIGGERS)}")
            # Before the pre-run records step, which would commit a missing folder's removal and leave git nothing
            # to restore it from. That step changes no file, and a sync that moves main starts this process again.
            founder.check(self.store.root)
        except ConfigError as error:
            self.say(f"refusing to start: {error}")
            return launcher.EXIT_CONFIG

        production = canonical(self.repo_root) == config.records.production_clone
        if pre:
            sync = pre["sync"]
        elif not production:
            clone = config.records.production_clone
            sync = {"status": "not production", "detail": f"not the production clone ({clone}): no sync, no records"}
        elif not config.records.sync_before_run:
            sync = {"status": "off", "detail": "the pre-run sync is turned off in config/run.json"}
        else:
            removed = self.clear_probe_files()
            result = records.prepare(
                self.repo_root,
                config.records.remote,
                config.records.branch,
                f"{started:%Y%m%dT%H%M%SZ}",
                self.env,
                config.records.max_file_bytes,
            )
            self.say(f"pre-run: {result.status}: {result.detail}")
            if not result.ok_to_run:
                self.say("refusing to start; the production clone needs attention first")
                return EXIT_RECORDS
            sync = dict(result.as_json(), probe_files_removed=removed)
            if result.code_changed:
                # Run the reviewed code just fetched, not the code already loaded in this process.
                entry = str(entry_point(self.repo_root))
                carried = json.dumps({"started_at": started.isoformat(), "sync": sync, "taken": self.taken()})
                for stream in (self.out, sys.stdout, sys.stderr):
                    stream.flush()  # execve discards anything still buffered
                execve(entry, [entry, *argv], dict(self.env, **{PRE_RUN_ENV: carried}))
                return 0  # only reached when execve is replaced in tests

        run_id = self.run_id = launcher.new_run_id(trigger, started)
        state = RunState(run_id, trigger, started, str(sessions.FOLDER), sync=sync)
        state.problems += list(sync.get("repaired", []))
        state.late_after = timedelta(minutes=config.late_after_minutes)
        state.titles = {key: str(output.get("title", key)) for key, output in config.outputs.items()}
        if trigger == "scheduled":
            state.due = report.due_time(started, config.weekly, once)
            if once is None:
                state.attempt = self.claim(state, config)
                if state.attempt is None:
                    return 0
        state.code = head(self.repo_root)
        try:
            _, boundary = load_boundary(self.repo_root, self.env, self.home)
            registry = load_json(self.repo_root / "config" / "products.json")
            rules = settings.waitlist(registry, boundary, self.env, self.home)
            beta_rules = beta.rules(registry, config)
            footage_place = boundary.footage
            policy = fetch.load_policy(canonical(self.repo_root))
            network = (policy, sources.load(canonical(self.repo_root), policy), outreach.settings(config.data))
        except ConfigError as error:
            self.say(f"refusing to start: {error}")
            return launcher.EXIT_CONFIG
        areas = Areas(boundary)
        products = [str(product["name"]) for product in registry.get("products", [])]
        self.say(f"run {run_id} ({trigger}): {report.start_line(state)}")

        self.snapshot(state, config, boundary, registry)
        ledger_path = self.store.path(REVIEW_QUEUE, QUEUE_FILE)
        ledger_ok = True
        try:
            ledger = Ledger.load(ledger_path)
        except QueueError as error:
            ledger, ledger_ok = Ledger(), False
            state.problems.append(f"{error}; the Review Queue was left untouched this run")
        states = self.load_state(state, run_id)
        self.take_decisions(state, config, ledger, ledger_ok, states.review_queue)
        sittings = self.sitting_runs(state)
        hashes, unreadable = run_state.item_hashes(self.store.root, ledger.entries, products, states.review_queue)
        state.problems += unreadable
        lost = {
            identifier: f"`{entry['file']}`, its item file, could not be read"
            for identifier, entry in ledger.entries.items()
            if identifier not in hashes
        }
        seen: dict[str, str] = {}
        for identifier, fingerprint in hashes.items():
            seen.setdefault(fingerprint, identifier)
        for source in config.not_connected:
            state.sources.append(
                SourceLine(
                    str(source["name"]),
                    SKIPPED,
                    f"not connected until {source.get('story')}",
                    output_titles(config, source.get("needed_by", ())),
                )
            )
        self.read_waitlist(state, config, rules)
        if ledger_ok:
            self.file_dispatches(state, ledger, products, seen, hashes)
        self.prepare_posts(state, config, registry, boundary, ledger)
        self.prepare_filming(state, config, footage_place, areas, ledger, ledger_ok, products, seen)
        state.queue_before = ledger.ordered()
        state.replaced = {str(entry["id"]): ledger.decided_replaced(entry) for entry in state.queue_before}
        state.closed_proposals = [
            entry
            for entry in ledger.entries.values()
            if entry["kind"] == "package-change-proposal" and entry["status"] != OPEN
        ]
        self.prepare_beta(
            state, config, beta_rules, registry, boundary, ledger, ledger_ok, areas, states.beta_recruiting
        )
        areas.ensure_folder(areas.path("review_queue", INCOMING))
        self.prepare_work(state, config, registry, boundary, areas, ledger if ledger_ok else None, states, network)
        self.unusable_sources(state, config)
        # A stopped boundary check's script sits among the agent's Instructions, so every run removes what such a check
        # left before it remembers them: the guard would put back after the agent whatever it had remembered.
        state.probe_files_removed = clear_probe_files(boundary)
        if state.probe_files_removed:
            self.say(f"removed boundary probe files left in the areas: {', '.join(state.probe_files_removed)}")
        state.guidance = learning.remember(areas)
        state.problems += state.guidance.problems
        self.plan_sessions(state, config)
        readings = self.run_sessions(state, config, definitions, areas, products)
        state.slept = self.asleep()
        log_dir = launcher.default_log_dir(self.env, self.home)

        now = self.now()
        published: list[str] = []
        if ledger_ok:
            kept = evidence.records(self.store)
            published, state.set_aside = ledger.take_incoming(
                areas, self.store, products, run_id, now, seen, kept, lost
            )
            state.queue_unread = ledger.unsettled
            state.published += published
        incoming = len(published) + len(state.set_aside)
        if ledger_ok:
            self.take_posts(state, areas, ledger, products, run_id, now, seen)
            self.take_beta(state, areas, ledger, products, run_id, now)
        elif state.posts is not None:
            state.posts_problem = "not taken in: the Review Queue could not be read"
        self.take_work(state, areas, ledger, ledger_ok, products, run_id, now, seen)
        self.count_work(state, config, log_dir, readings, ledger_ok)
        report_path = self.store.path(RUN_REPORTS, f"{run_id}.md")
        state.problems += areas.problems
        areas.problems.clear()
        if state.waitlist is not None and state.waitlist.status == waitlist.REFUSED:
            if ledger_ok:
                state.breach_notice = self.queue_notice(
                    state,
                    ledger,
                    seen,
                    report.breach_notice(state, self.store.relative(report_path)),
                    "notice-waitlist-breach",
                    "the Guardrail breach notice",
                    state.waitlist.rules.product,
                )
            else:
                state.problems.append(
                    "the Guardrail breach notice could not be queued, as the Review Queue could not be read; this"
                    " report is the only place it is told"
                )
        state.queue_after = ledger.ordered()
        self.left_standing(state, config, ledger)
        self.outputs(state, config, ledger_ok)
        notice = report.problems_notice(state, self.store.relative(report_path))
        if notice and ledger_ok:
            state.notice = self.queue_notice(
                state, ledger, seen, notice, "notice-run-problems", "the notice of this run's problems"
            )
        if ledger_ok and state.post_outcome is not None and state.post_outcome.withdrawn:
            posts.withdraw(ledger, state.post_outcome, state.notice, run_id, now)
        if ledger_ok:
            taken_back = list(state.listening_result.replies if state.listening_result else ())
            taken_back += list(state.outreach_result.outcomes if state.outreach_result else ())
            messages.withdraw(ledger, taken_back, state.notice, run_id, now)
            self.settle_beta(state, ledger, states, run_id, now)
        state.queue_after = ledger.ordered()
        self.outputs(state, config, ledger_ok)
        if ledger_ok:
            ledger.mark_carried_over(sittings)
            # While a fresh run is to follow by itself, the next weekly run is the one already due.
            next_run = state.due.astimezone() if state.again else report.next_due(now, config.weekly)
            try:
                self.store.write_json(
                    ledger_path, ledger.as_json(run_id, now, self.store.relative(report_path), next_run)
                )
            except OSError as error:
                state.problems.append(
                    f"the Review Queue could not be written, so the sitting page shows the last one ({error})"
                )
            state.queue_after = ledger.ordered()
            try:
                self.save_state(state, ledger, states, products, now)
            except (OSError, ConfigError) as error:
                state.problems.append(f"the run state could not be saved ({error})")
        state.tallies = self.tallies(state, ledger, incoming, ledger_ok)
        notes = sorted(self.store.path(NOTES_DIR).glob("*.txt"))
        state.notes = [path.read_text(encoding="utf-8").strip() for path in notes]
        try:
            self.store.write_text(report_path, report.render_report(state))
        except OSError as error:
            line = f"Run {run_id} could not write its report `{self.store.relative(report_path)}`: {error}."
            self.leave_note(run_id, line)
            self.say(f"{line} The next run's report will say so.")
        else:
            for path in notes:
                path.unlink()
            self.say(f"run report: {report_path}")

        self.note_ending(state, config)
        saved = None
        if production and config.records.save_after_run:
            result = records.save(
                self.repo_root,
                config.records.remote,
                config.records.branch,
                run_id,
                self.env,
                config.records.max_file_bytes,
            )
            saved = result.as_json()
            self.say(f"records: {result.status}: {result.detail}")
        code = self.exit_code(state)
        self.log(log_dir, sync, saved, report_path, state, code)
        return code

    def log(self, log_dir: Path, sync, saved, report_path: Path, state: RunState, code: int) -> None:
        """The run's own record in the log folder: what the launcher did around its sessions, and every session with
        the launcher's record of it, which each session's own file also holds, and what was read and counted of it."""
        record = {
            "run_id": state.run_id,
            "trigger": state.trigger,
            "started_at": state.started.isoformat(),
            "exit_code": code,
            "timed_out": state.timed_out,
            "sessions": [
                dict(
                    session.record,
                    workflow=session.key,
                    due=session.due,
                    why=session.why,
                    ended=session.ended(),
                    time_limit_of_its_own=session.limit,
                    brief=session.brief,
                    usage=session.usage,
                    cost_usd=session.cost,
                    codex_last_error=session.error or None,
                    work=session.work.as_json() if session.work else None,
                )
                for session in state.sessions
            ],
            "run_time_limit_seconds": state.run_limit,
            "agent_seconds": round(state.agent_seconds, 1),
            "sync": sync,
            "records": saved,
            "report": str(report_path),
            "late": state.late,
            "ending": state.ending,
            "usage": state.usage,
            "cost_usd": state.cost,
            "queued": state.published,
            "problems": state.problems,
            "set_aside": [item.name for item in state.set_aside],
        }
        log_dir.mkdir(parents=True, exist_ok=True)
        launcher.write_json(log_dir / f"{state.run_id}.json", record)


def main(
    repo_root: Path,
    trigger: str,
    env: Mapping[str, str],
    home: Path,
    once: str | None = None,
    argv: Sequence[str] = (),
    out: TextIO = sys.stdout,
) -> int:
    cycle = Cycle(repo_root, env, home, out, lambda: datetime.now(timezone.utc))
    return cycle.run(trigger, once, argv)
