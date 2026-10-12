"""One Marketing Engineer run, scheduled or on demand, from the pre-run sync to the saved records.

Order: bring the production clone up to origin's main; snapshot the Go-To-Market Package; take in the Founder's
decisions from Mandu; read the Waitlist's anonymous view, keeping only its counts; file the reviewed Dispatch requests
that need filing; plan the post Drafts from the 14-day kit (posts.prepare); file the filming plan and list and measure
the footage place (filming.prepare); read the Founder's Beta Build record and, only once it exists, plan the Beta
Cohort's next invitation batch (beta.prepare); read the fixed list of network sources into one snapshot (fetch.Client,
the launcher's only way onto the network), which is working data removed when the run ends, and plan Listening from it
and outreach from the Founder's records; brief the agent and run it inside the sandbox, which has no network
(launcher.run); put back any change the run made to its own Instructions; queue the items it wrote to
workspace/review-queue/incoming/ that pass the format, a post for each Draft it wrote that passes every check, with
the video cut from its edit record when it has one (posts.take), the recruiting Drafts that pass theirs (beta.take),
the quotes, proposals, and messages that pass theirs (listening.take, outreach.take), the code it proposed for each
rejection reason (learning.take), and the reviewed proposals that need filing; write the Review Queue and the run
report; commit and push workspace/ and ledger/. Every step but the agent is deterministic code outside the sandbox.
The launcher's records live in ledger/, which the agent can read and never write, so nothing it does can change them;
in workspace/ the launcher only restores its owner's access to entries the agent left without it, reads the Drafts and
the edit records, removes a recruiting Draft that holds what looks like an email address, reads and removes the items,
quote records, proposals, and codes it takes in, and puts the agent's Instructions back as they were. One run at a
time per checkout holds the run lock in its ledger/ from the sync to the saved records; a run started meanwhile
refuses to start, and the next report says so.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shlex
import shutil
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

from . import (
    beta,
    dispatch,
    evidence,
    exchange,
    fetch,
    filming,
    footage,
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
    settings,
    sources,
    waitlist,
)
from . import state as run_state
from .areas import Areas, Store, UnsafeFile, read_plain
from .boundary import LEDGER, Boundary, ConfigError, canonical, load_boundary, load_json
from .queue import INCOMING, OPEN, QUEUE_FILE, REVIEW_QUEUE, SET_ASIDE, SUPERSEDED, Ledger, QueueError, Stands
from .report import COMPLETE, INCOMPLETE, NOT_BUILT, SKIPPED, RunState, SourceLine, Unusable

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
STRAY = "only <name>.json record files belong here"  # a file that is no record, which is not a read that failed
# The folders, each inside one of the agent's areas, that the launcher takes the agent's work in from.
INTAKE = (
    ("evidence", listening.QUOTES_IN),
    ("evidence", learning.CODES_IN),
    ("review_queue", listening.ANGLES_IN),
    ("drafts", messages.DRAFTS),
    ("drafts", listening.REPLIES_IN),
    ("drafts", outreach.FOLDER),
)


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


# Mandu's exchange folder, read only.


def unusable(name: str, problems: Sequence[str], content: bytes | None = None) -> Unusable:
    """A record that could not be used, fingerprinted by its name and its content, or by its problems when it could not
    be read, so it is reported again only once that changes."""
    data = "; ".join(problems).encode("utf-8") if content is None else content
    return Unusable(name, tuple(problems), run_state.digest(f"{name}\n{hashlib.sha256(data).hexdigest()}"))


def read_records(directory: Path) -> tuple[list[tuple[str, Path, bytes]], list[Unusable], str | None]:
    """(name, path, bytes) for every record file in one exchange subfolder, the records that could not be read, and
    why the folder itself could not be listed, if it could not; hidden files are Mandu's temporaries."""
    found, problems = [], []
    try:
        names = sorted(os.listdir(str(directory))) if package.file_type(directory) == stat.S_IFDIR else []
    except OSError as error:
        return found, problems, error.strerror or str(error)
    for name in names:
        path = directory / name
        if name.startswith("."):
            continue
        try:
            if not name.endswith(".json") or package.file_type(path) != stat.S_IFREG:
                problems.append(unusable(f"{directory.name}/{name}", [STRAY]))
                continue
            found.append((name, path, path.read_bytes()))
        except OSError as error:
            problems.append(unusable(f"{directory.name}/{name}", [error.strerror or str(error)]))
    return found, problems, None


def parse_records(found, parser) -> tuple[list[tuple[object, Path, str]], list[Unusable]]:
    parsed, problems = [], []
    for name, path, data in found:
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            problems.append(unusable(f"{path.parent.name}/{name}", [f"not JSON: {error}"], data))
            continue
        record, issues = parser(name[: -len(".json")], value)
        if issues:
            problems.append(unusable(f"{path.parent.name}/{name}", issues, data))
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
    ):
        self.repo_root = repo_root
        self.env = env
        self.home = home
        self.out = out
        self.clock = clock
        self.client = client or fetch.Client  # the real network, through fetch.send, unless a test gives another
        self.store = Store(canonical(repo_root) / LEDGER)
        self.started: datetime | None = None
        self.run_id: str | None = None

    def say(self, message: str) -> None:
        print(f"gr0wthlab: {message}", file=self.out)

    def now(self) -> datetime:
        return self.clock()

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
        folder: Path,
        ledger: Ledger,
        ledger_ok: bool,
        review_state: run_state.ReviewQueueState,
    ) -> None:
        """Take in Mandu's decision and sitting records; when the ledger could not be read, no decision is matched and
        only sittings are taken in. A decision record for an item still open that cannot be used is reported at every
        run until Mandu replaces it; any other record that cannot be used is reported by the first run to find it as
        it is, and the Review Queue state remembers it by its fingerprint while it stays so."""
        needs = output_titles(config, ("decisions", "review-queue"))
        sitting_needs = output_titles(config, ("review-queue",))
        state.reported_before = set(review_state.reported)
        unmatched = (
            None
            if ledger_ok
            else SourceLine(
                "Mandu decisions",
                SKIPPED,
                "the Review Queue could not be read, so no decision could be matched to its item",
                needs,
            )
        )
        try:
            present = package.file_type(folder) == stat.S_IFDIR
        except OSError as error:
            detail = f"Mandu's exchange folder `{folder}` could not be read: {error.strerror or error}."
            state.sources.append(unmatched or SourceLine("Mandu decisions", package.FAILED, detail, needs))
            state.sources.append(SourceLine("Mandu sittings", package.FAILED, detail, sitting_needs))
            return
        if not present:
            if unmatched:
                state.sources.append(unmatched)
            elif ledger.open_entries():
                detail = f"Mandu's exchange folder `{folder}` does not exist, so no decision can reach gr0wthlab."
                state.sources.append(SourceLine("Mandu decisions", package.FAILED, detail, needs))
            else:
                detail = "no Review Queue item is waiting for a decision yet"
                state.sources.append(SourceLine("Mandu decisions", SKIPPED, detail, needs))
            state.sources.append(SourceLine("Mandu sittings", SKIPPED, "Mandu's exchange folder does not exist yet"))
            return
        found, problems, failure = ([], [], None) if unmatched else read_records(folder / "decisions")
        decisions, more = parse_records(found, exchange.parse_decision)
        problems += more
        sittings_found, sitting_problems, sitting_failure = read_records(folder / "sittings")
        sittings, more = parse_records(sittings_found, exchange.parse_sitting)
        sitting_problems += more
        now = self.now()
        outcomes = ledger.take_decisions([d for d, _, _ in decisions], state.run_id, now)
        state.decisions = [outcome for outcome in outcomes if outcome.status in ("taken", "already-taken")]
        contents = {name: data for name, _, data in found}
        for outcome in outcomes:
            if outcome.status in ("unknown-item", "conflict"):
                name = f"{outcome.decision.item}.json"
                problems.append(unusable(f"decisions/{name}", [report.outcome_text(outcome.status)], contents[name]))
        problems = [named_item(record) for record in problems]
        state.unusable = problems + sitting_problems
        reported = {record.fingerprint for record in state.unusable}
        review_state.reported = sorted(reported | state.reported_before if failure or sitting_failure else reported)
        digests = {d.item: (str(path), digest) for d, path, digest in decisions}
        for outcome in state.decisions:
            if outcome.status != "taken":
                continue
            decision, entry = outcome.decision, outcome.entry
            source, digest = digests[decision.item]
            self.store.write_json(
                self.store.path("evidence", "decisions", f"{decision.item}.json"),
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
                "source": {"path": str(path), "sha256": digest},
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
        taken = sum(1 for outcome in state.decisions if outcome.status == "taken")
        if unmatched:
            state.sources.append(unmatched)
        elif failure:
            detail = f"`{folder / 'decisions'}` could not be read: {failure}."
            state.sources.append(SourceLine("Mandu decisions", package.FAILED, detail, needs))
        else:
            detail = f"{report.plural(len(found), 'record')}, {taken} new since the previous run" + (
                f", {len(problems)} could not be used" if problems else ""
            )
            state.sources.append(
                SourceLine("Mandu decisions", package.CHANGED if taken else package.READ, detail, needs)
            )
        if sitting_failure:
            detail = f"`{folder / 'sittings'}` could not be read: {sitting_failure}."
            state.sources.append(SourceLine("Mandu sittings", package.FAILED, detail, sitting_needs))
        else:
            detail = f"{report.plural(len(sittings_found), 'record')}, {len(state.sittings)} new" + (
                f", {len(sitting_problems)} could not be used" if sitting_problems else ""
            )
            state.sources.append(
                SourceLine("Mandu sittings", package.CHANGED if state.sittings else package.READ, detail)
            )

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

    def file_dispatches(self, state: RunState, ledger: Ledger, products: Sequence[str], seen: dict[str, str]) -> None:
        """File each reviewed Dispatch request that needs filing, before the agent starts, so its brief lists it."""
        requests, problems = dispatch.load(self.repo_root, products)
        state.problems += problems
        state.dispatches = dispatch.file(ledger, self.store, requests, products, seen, state.run_id, self.now())
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
        """Each sitting taken in so far, by date, with the run that first took in its record."""
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
        agent_gap = state.agent_gap()
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
            listening.tally(state.listening, state.listening_result, state.listening_problem, agent_gap),
            outreach.tally(state.outreach, state.outreach_result, state.outreach_problem, agent_gap),
            learning.tally(state.learning, state.learning_problem, agent_gap),
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
        return filming.tally(state.filming, state.agent_gap())

    def beta_tally(self, state: RunState) -> run_state.Tally:
        """What Beta Cohort recruiting checked and acted on: the sign-ups that asked for an invitation, and each item
        queued or withdrawn. Before the Founder's gate it checks and acts on nothing, and says why."""
        plan, outcome = state.beta, state.beta_outcome
        if plan is None:
            return run_state.Tally(beta.WORKFLOW, 0, 0, "no Product recruits a Beta Cohort")
        if not plan.active:
            why = (
                "no Beta Build approval is recorded in Mandu"
                if plan.gate.status == beta.NOT_RECORDED
                else "the Beta Build record in Mandu could not be used"
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
        return beta.gaps(state.beta, state.beta_outcome, state.beta_problem, state.agent_gap())

    def post_gaps(self, state: RunState) -> list[str]:
        """Why the post Drafts are incomplete this run: a kit file, the code, or the brand rules could not be used,
        a Draft could not be checked because something its check needs could not be read, a due day has no Draft, or
        the agent or the take-in fell short. A Draft blocked by a check the launcher could make is the check working,
        not a gap."""
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
        if plan.days and state.agent_gap():
            gaps.append(state.agent_gap())
        return gaps

    def queue_gaps(self, state: RunState) -> list[str]:
        """Why the Review Queue is incomplete this run though the ledger was read: an item file could not be, so a
        reviewed Dispatch request, or an item the agent wrote to take an open item's place, could not be compared
        with the item it would replace, which therefore stands."""
        review_queue = [reason for title, kept in state.stood if title == state.queue_title for reason in kept.unread]
        return list(dict.fromkeys(state.dispatch_unread + review_queue))

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
        found += [
            (state.queue_title, Stands(str(filing.identifier), (filing.unread,)))
            for filing in state.dispatches
            if filing.unread
        ]
        found += [(state.queue_title, kept) for kept in ledger.stood]
        state.stood = found

    def outputs(self, state: RunState, config: settings.Settings, ledger_ok: bool) -> None:
        """Each output's status: a built output is incomplete when a failed source it needs names it, or when its own
        step fell short. A step that needed the agent names the agent's not finishing among its gaps, and the outputs
        whose rows hold that gap are the ones the run's notice names; the rows are therefore worked out before that
        notice is written, and again once the Review Queue holds it."""
        failed = state.failed_sources()
        agent_gap = state.agent_gap()
        decisions = next((line.detail for line in state.sources if line.name == "Mandu decisions"), "")
        queued = report.plural(len(state.queue_after), "open item") + (
            f"; {len(state.set_aside)} set aside" if state.set_aside else ""
        )
        review_gap = state.review_gap()
        reading = state.waitlist
        skipped = {"waitlist-counts": reading.detail} if reading and reading.status == SKIPPED else {}
        if state.beta is None or state.beta.gate.status == beta.NOT_RECORDED:
            skipped[beta.WORKFLOW] = (
                "the Founder has recorded no approved Beta Build in Mandu" if state.beta else "no Product recruits one"
            )
        if state.filming is None and not state.filming_problem:
            skipped["filming-plan"] = "no active Product films"
        own = {
            "package-snapshot": ([], f"`{state.snapshot_file}`"),
            "package-review": ([review_gap] if review_gap else [], "the agent finished its review"),
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
                filming.gaps(state.filming, agent_gap) if state.filming is not None else [state.filming_problem],
                self.filming_tally(state).note,
            ),
            "listening": (
                listening.gaps(state.listening, state.listening_result, state.listening_problem, agent_gap),
                listening.tally(state.listening, state.listening_result, state.listening_problem, agent_gap).note,
            ),
            "outreach-drafts": (
                outreach.gaps(state.outreach, state.outreach_result, state.outreach_problem, agent_gap),
                outreach.tally(state.outreach, state.outreach_result, state.outreach_problem, agent_gap).note,
            ),
            "rejection-codes": (
                learning.gaps(state.learning, state.learning_problem, agent_gap),
                learning.tally(state.learning, state.learning_problem, agent_gap).note,
            ),
        }
        rows, agent_incomplete = [], []
        for key, output in config.outputs.items():
            title = str(output.get("title", key))
            if not output.get("built"):
                rows.append([title, NOT_BUILT, str(output.get("story", ""))])
                continue
            if key in skipped:
                rows.append([title, SKIPPED, skipped[key]])
                continue
            gaps, done = own.get(key, ([], ""))
            if agent_gap and agent_gap in gaps:
                agent_incomplete.append(title)
            gaps = [f"{line.name} could not be read" for line in failed if title in line.needed_by] + gaps
            rows.append([title, INCOMPLETE if gaps else COMPLETE, "; ".join(gaps) or done])
        state.outputs = rows
        state.agent_incomplete = tuple(agent_incomplete)

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
            state.filming.settle(state.post_outcome)
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
        folder: Path,
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
        found, problems, failure = read_records(folder / beta.BUILDS)
        unusable = [(Path(record.name).name, "; ".join(record.problems)) for record in problems]
        gate = beta.read_gate(rules.product, found, unusable, failure)
        if gate.recorded and not ledger_ok:
            state.beta = beta.Plan(rules, gate, state.run_id)
            state.beta_problem = "not prepared: the Review Queue could not be read"
        else:
            reports, reports_failure, unreadable = None, None, []
            if gate.recorded:
                reports, problems, reports_failure = read_records(folder / beta.REPORTS)
                for record in problems:
                    name = beta.mandu_file(beta.REPORTS, Path(record.name).name)
                    state.problems.append(f"{name} could not be used ({'; '.join(record.problems)})")
                unreadable = [Path(record.name).name for record in problems if record.problems != (STRAY,)]
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
        folder: Path,
        network: tuple[fetch.Policy, sources.Config, outreach.Settings],
    ) -> None:
        """Before the agent: read the network sources, plan Listening from them and outreach from the Founder's
        records in Mandu, and record both plans for the agent's own check. Each step fails on its own; with no
        ledger, as when the Review Queue could not be read, nothing is filed or matched."""
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
            if ledger is not None and package.file_type(folder / "outreach") == stat.S_IFDIR:
                found, problems, failure = read_records(folder / "outreach")
                parsed, more = parse_records(found, exchange.parse_outreach)
                bad = {Path(record.name).name: "; ".join(record.problems) for record in problems + more}
                records = outreach.Records(tuple(record for record, _, _ in parsed), bad, failure or "")
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
                    detail = f"`{folder / 'outreach'}` could not be read: {records.failure}."
                    line = SourceLine("Mandu outreach records", package.FAILED, detail, needs)
                elif unread:
                    detail = "; ".join(f"{who}: {why}" for who, why in unread) + "."
                    line = SourceLine("Mandu outreach records", package.FAILED, detail, needs)
                elif counted:
                    line = SourceLine("Mandu outreach records", package.READ, counted, needs)
                else:
                    line = SourceLine("Mandu outreach records", SKIPPED, "no message has been recorded as sent yet")
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
        """After the agent: put back any change to its Instructions, then take in its Listening work, its outreach
        Drafts, and the codes it proposed for rejection reasons, each on its own."""
        if state.guidance is not None:
            state.put_back = learning.put_back(state.guidance, areas)
            state.problems += [f"{line}; no run may change its own Instructions yet" for line in state.put_back]
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

    def run(
        self,
        instruction: Path | None,
        trigger: str,
        once: str | None,
        argv: Sequence[str],
        execve: Callable[[str, list[str], Mapping[str, str]], None] = os.execve,
    ) -> int:
        lock = self.lock(trigger)
        if lock is None:
            return EXIT_BUSY
        with lock:
            try:
                return self.locked_run(instruction, trigger, once, argv, execve)
            except (OSError, ConfigError) as error:
                started = self.started or self.now()
                run_id = self.run_id or launcher.new_run_id(trigger, started)
                line = (
                    f"Run {run_id} ({trigger}), started {report.wall_clock(started):%A %Y-%m-%d %H:%M}, stopped"
                    f" before it finished: {error}."
                )
                self.leave_note(run_id, line)
                self.say(f"the run stopped: {error}; the next run's report will say so")
                return EXIT_STOPPED
            finally:
                self.discard_working()

    def locked_run(
        self,
        instruction: Path | None,
        trigger: str,
        once: str | None,
        argv: Sequence[str],
        execve: Callable[[str, list[str], Mapping[str, str]], None],
    ) -> int:
        pre = json.loads(self.env[PRE_RUN_ENV]) if self.env.get(PRE_RUN_ENV) else None
        started = datetime.fromisoformat(pre["started_at"]) if pre else self.now()
        self.started, self.run_id = started, None
        try:
            config = settings.load(self.repo_root, self.env, self.home)
            task = config.instruction if instruction is None else settings.instruction_path(self.repo_root, instruction)
            if trigger not in launcher.TRIGGERS:
                raise ConfigError(f"trigger must be one of {', '.join(launcher.TRIGGERS)}")
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
            sync = result.as_json()
            if result.code_changed:
                # Run the reviewed code just fetched, not the code already loaded in this process.
                entry = str(entry_point(self.repo_root))
                carried = json.dumps({"started_at": started.isoformat(), "sync": sync})
                for stream in (self.out, sys.stdout, sys.stderr):
                    stream.flush()  # execve discards anything still buffered
                execve(entry, [entry, *argv], dict(self.env, **{PRE_RUN_ENV: carried}))
                return 0  # only reached when execve is replaced in tests

        run_id = self.run_id = launcher.new_run_id(trigger, started)
        state = RunState(run_id, trigger, started, str(task.relative_to(canonical(self.repo_root))), sync=sync)
        state.problems += list(sync.get("repaired", []))
        state.late_after = timedelta(minutes=config.late_after_minutes)
        if trigger == "scheduled":
            state.due = report.due_time(started, config.weekly, once)
        state.code = head(self.repo_root)
        try:
            _, boundary = load_boundary(self.repo_root, self.env, self.home)
            registry = load_json(self.repo_root / "config" / "products.json")
            folder = settings.exchange_dir(registry, boundary, self.env, self.home)
            rules = settings.waitlist(registry, boundary, self.env, self.home)
            beta_rules = beta.rules(registry, config)
            footage_place = filming.place(registry, boundary, self.env, self.home)
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
        self.take_decisions(state, config, folder, ledger, ledger_ok, states.review_queue)
        sittings = self.sitting_runs(state)
        hashes, unreadable = run_state.item_hashes(self.store.root, ledger.entries, products, states.review_queue)
        state.problems += unreadable
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
            self.file_dispatches(state, ledger, products, seen)
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
            state, config, beta_rules, folder, registry, boundary, ledger, ledger_ok, areas, states.beta_recruiting
        )
        areas.ensure_folder(areas.path("review_queue", INCOMING))
        self.prepare_work(
            state, config, registry, boundary, areas, ledger if ledger_ok else None, states, folder, network
        )
        state.guidance = learning.remember(areas)
        state.problems += state.guidance.problems
        brief = self.store.path(RUN_REPORTS, f"{run_id}.brief.md")
        self.store.write_text(
            brief, report.render_brief(state, canonical(self.repo_root), areas.workspace, self.store.root)
        )

        try:
            state.agent = launcher.run(
                self.repo_root,
                task,
                trigger,
                self.env,
                self.home,
                out=self.out,
                now=started,
                facts=[f"Run brief, read it first: {brief}"],
                run_id=run_id,
                time_limit=config.agent.time_limit,
            )
        except OSError as error:
            state.agent = {"exit_code": launcher.EXIT_CONFIG, "agent_started": False, "error": str(error)}
        log_dir = launcher.default_log_dir(self.env, self.home)
        last_message = log_dir / f"{run_id}.last-message.md"
        if last_message.is_file():
            summary = last_message.read_text(encoding="utf-8", errors="replace")
            state.agent_summary = summary[:SUMMARY_LIMIT]
            state.review = (summary.strip().splitlines() or [""])[-1].strip()
        state.usage = report.token_usage(log_dir / f"{run_id}.events.jsonl")
        if state.usage:
            state.cost = report.cost(state.usage, config.prices)
        left = report.left_running(state.stop) if state.timed_out else None
        if left:
            state.problems.append(left)
        state.problems += records.restore_access(canonical(self.repo_root))

        now = self.now()
        published: list[str] = []
        if ledger_ok:
            kept = evidence.records(self.store)
            lost = {
                identifier: f"`{entry['file']}`, its item file, could not be read"
                for identifier, entry in ledger.entries.items()
                if identifier not in hashes
            }
            published, state.set_aside = ledger.take_incoming(
                areas, self.store, products, run_id, now, seen, kept, lost
            )
            state.published += published
        incoming = len(published) + len(state.set_aside)
        if ledger_ok:
            self.take_posts(state, areas, ledger, products, run_id, now, seen)
            self.take_beta(state, areas, ledger, products, run_id, now)
        elif state.posts is not None:
            state.posts_problem = "not taken in: the Review Queue could not be read"
        self.take_work(state, areas, ledger, ledger_ok, products, run_id, now, seen)
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
            next_run = report.next_due(now, config.weekly)
            try:
                self.store.write_json(
                    ledger_path, ledger.as_json(run_id, now, self.store.relative(report_path), next_run)
                )
            except OSError as error:
                state.problems.append(f"the Review Queue could not be written, so Mandu sees the last one ({error})")
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
        self.log(log_dir, run_id, sync, saved, report_path, state)
        return int(state.agent.get("exit_code", 1))

    def log(self, log_dir: Path, run_id: str, sync, saved, report_path: Path, state: RunState) -> None:
        path = log_dir / f"{run_id}.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = {"run_id": run_id}
        record.update(
            sync=sync,
            records=saved,
            report=str(report_path),
            late=state.late,
            usage=state.usage,
            cost_usd=state.cost,
            queued=state.published,
            problems=state.problems,
            set_aside=[item.name for item in state.set_aside],
        )
        launcher.write_json(path, record)


def main(
    repo_root: Path,
    instruction: Path | None,
    trigger: str,
    env: Mapping[str, str],
    home: Path,
    once: str | None = None,
    argv: Sequence[str] = (),
    out: TextIO = sys.stdout,
) -> int:
    cycle = Cycle(repo_root, env, home, out, lambda: datetime.now(timezone.utc))
    return cycle.run(instruction, trigger, once, argv)
