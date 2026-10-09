"""One Marketing Engineer run, scheduled or on demand, from the pre-run sync to the saved records.

Order: bring the production clone up to origin's main; snapshot the Go-To-Market Package; take in the Founder's
decisions from Mandu; brief the agent and run it inside the sandbox (launcher.run); undo any change it made to
records only the launcher writes; queue the items it wrote that pass the format; write the Review Queue and the run
report; commit and push workspace/. Every step but the agent is deterministic code outside the sandbox, and every
write it makes goes through Areas, so it stays inside the six areas. One run at a time per checkout holds its run lock
from the sync to the saved records; a run started meanwhile refuses to start, and that checkout's next report says so.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

from . import exchange, launcher, package, records, report, settings
from . import state as run_state
from .areas import Areas, UnsafeFile, read_plain
from .boundary import Boundary, ConfigError, canonical, load_boundary, load_json
from .queue import INCOMING, OPEN, SET_ASIDE, SUPERSEDED, Ledger, QueueError
from .report import COMPLETE, INCOMPLETE, NOT_BUILT, SKIPPED, RunState, SourceLine

PRE_RUN_ENV = "GR0WTHLAB_PRE_RUN"
EXIT_RECORDS = 4
EXIT_BUSY = 5
EXIT_STOPPED = 6
CHECKOUTS = "checkouts"
LOCK_FILE = "run.lock"
NOTES_DIR = "notes"
SNAPSHOTS = "package-snapshots"
SUMMARY_LIMIT = 4000
# Records only the launcher writes; the agent's changes to them are undone after it finishes.
PROTECTED_DIRS = (
    ("review_queue", "items"),
    ("review_queue", "set-aside"),
    ("evidence", "decisions"),
    ("evidence", "sittings"),
    ("evidence", SNAPSHOTS),
    ("run_reports",),
)
PROTECTED_FILES = (("review_queue", "queue.json"),)


def entry_point(repo_root: Path) -> Path:
    return repo_root / "src" / "bin" / "gr0wthlab"


def head(repo_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def checkout_logs(log_dir: Path, repo_root: Path) -> Path:
    """The log folder of one checkout's run lock and notes for its next report, apart from every other checkout."""
    return log_dir / CHECKOUTS / hashlib.sha256(str(canonical(repo_root)).encode("utf-8")).hexdigest()[:12]


def output_titles(config: settings.Settings, keys: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(config.outputs.get(key, {}).get("title", key)) for key in keys)


# Mandu's exchange folder, read only.


def read_records(directory: Path) -> tuple[list[tuple[str, Path, bytes]], list[tuple[str, list[str]]]]:
    """(name, path, bytes) for every record file in one exchange subfolder; hidden files are Mandu's temporaries."""
    found, problems = [], []
    if not directory.is_dir():
        return found, problems
    for name in sorted(os.listdir(str(directory))):
        path = directory / name
        if name.startswith("."):
            continue
        if not name.endswith(".json") or not path.is_file():
            problems.append((f"{directory.name}/{name}", ["only <name>.json record files belong here"]))
            continue
        try:
            found.append((name, path, path.read_bytes()))
        except OSError as error:
            problems.append((f"{directory.name}/{name}", [error.strerror or str(error)]))
    return found, problems


def parse_records(found, parser) -> tuple[list[tuple[object, Path, str]], list[tuple[str, list[str]]]]:
    parsed, problems = [], []
    for name, path, data in found:
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            problems.append((f"{path.parent.name}/{name}", [f"not JSON: {error}"]))
            continue
        record, issues = parser(name[: -len(".json")], value)
        if issues:
            problems.append((f"{path.parent.name}/{name}", issues))
        else:
            parsed.append((record, path, hashlib.sha256(data).hexdigest()))
    return parsed, problems


# Records only the launcher writes.


def protected_paths(areas: Areas) -> tuple[list[Path], list[Path]]:
    directories = [areas.path(*parts) if len(parts) > 1 else areas.paths[parts[0]] for parts in PROTECTED_DIRS]
    files = [areas.path(*parts) for parts in PROTECTED_FILES]
    files += [path / "README.md" for path in areas.paths.values()]
    return directories, files


def protected_state(areas: Areas) -> dict[Path, bytes]:
    directories, files = protected_paths(areas)
    state = {}
    for path in files + [file for directory in directories for file in areas.files(directory)]:
        try:
            state[path] = read_plain(path)
        except (UnsafeFile, OSError):
            continue
    return state


def undo_agent_changes(areas: Areas, before: Mapping[Path, bytes], run_id: str, ledger: Ledger) -> list[str]:
    """Restore launcher-only records the agent changed or removed, and set aside anything it added among them.

    A file or link the agent put in place of an area or a folder the launcher writes in is removed first, outermost
    first, so nothing after it reads or writes through a link, and the owner takes back each of those folders.
    Every folder the agent added among the records is removed last, so no later write finds a folder in its place.
    A repair that fails is noted in areas.problems, which reach the notice, and never stops the run.
    """
    undone = []
    directories, files = protected_paths(areas)
    folders = [*areas.paths.values(), *directories, areas.path("review_queue", INCOMING)]
    for folder in folders + [areas.path("review_queue", SET_ASIDE, run_id)]:
        try:
            if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
                if areas.remove(folder):
                    undone.append(f"removed `{areas.relative(folder)}`, which the agent put in place of a folder")
            elif folder.is_dir():
                areas.reclaim(folder)
        except OSError as error:
            areas.problems.append(f"could not undo the agent's change to `{areas.relative(folder)}` ({error})")
    after = protected_state(areas)
    present = set(files) | {path for directory in directories for path in areas.files(directory)}
    for path in sorted(present):
        if path in before or not os.path.lexists(str(path)):
            continue
        name = areas.relative(path)
        try:
            if path.is_dir() and not path.is_symlink():
                if areas.remove(path):
                    undone.append(f"removed folder `{name}`, which the agent added")
            else:
                moved = ledger.set_aside(areas, path, name, run_id, [])
                kept = f", as `{moved.moved_to}`" if moved.moved_to else ""
                undone.append(f"set aside `{name}`, which the agent added{kept}")
        except OSError as error:
            areas.problems.append(f"could not undo the agent's change to `{name}` ({error})")
    for path, content in sorted(before.items()):
        if after.get(path) == content:
            continue
        try:
            areas.write_bytes(path, content)
            undone.append(f"restored `{areas.relative(path)}`, which the agent changed or removed")
        except (OSError, ConfigError) as error:
            areas.problems.append(f"could not undo the agent's change to `{areas.relative(path)}` ({error})")
    for directory in directories:
        for folder in areas.remove_empty_folders(directory):
            undone.append(f"removed folder `{areas.relative(folder)}`, which the agent added")
    return undone


# The run.


class Cycle:
    def __init__(
        self,
        repo_root: Path,
        env: Mapping[str, str],
        home: Path,
        out: TextIO,
        clock: Callable[[], datetime],
    ):
        self.repo_root = repo_root
        self.env = env
        self.home = home
        self.out = out
        self.clock = clock

    def say(self, message: str) -> None:
        print(f"gr0wthlab: {message}", file=self.out)

    def now(self) -> datetime:
        return self.clock()

    def snapshot(self, state: RunState, config: settings.Settings, areas: Areas, boundary: Boundary, registry) -> None:
        mandu = next(location.path for location in boundary.locations if location.label == "Mandu")
        state.mandu = str(mandu)
        directory = areas.path("evidence", SNAPSHOTS)
        previous = package.latest_snapshot(directory, state.run_id)
        state.previous_snapshot = previous[0] if previous else None
        sources = package.package_sources(registry)
        state.snapshot = package.take(
            mandu, sources, package.last_known(previous[1] if previous else None), lambda: self.now().isoformat()
        )
        path = directory / f"{state.run_id}.json"
        areas.write_json(path, package.record(state.run_id, self.now(), mandu, state.snapshot, state.previous_snapshot))
        state.snapshot_file = areas.relative(path)
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
        self, state: RunState, config: settings.Settings, areas: Areas, folder: Path, ledger: Ledger
    ) -> None:
        anything_queued = bool(ledger.entries)
        needs = output_titles(config, ("decisions", "review-queue"))
        if not folder.is_dir():
            if anything_queued and ledger.open_entries():
                detail = f"Mandu's exchange folder `{folder}` does not exist, so no decision can reach gr0wthlab."
                state.sources.append(SourceLine("Mandu decisions", package.FAILED, detail, needs))
            else:
                detail = "no Review Queue item is waiting for a decision yet"
                state.sources.append(SourceLine("Mandu decisions", SKIPPED, detail, needs))
            state.sources.append(SourceLine("Mandu sittings", SKIPPED, "Mandu's exchange folder does not exist yet"))
            return
        found, problems = read_records(folder / "decisions")
        decisions, more = parse_records(found, exchange.parse_decision)
        problems += more
        sittings_found, sitting_problems = read_records(folder / "sittings")
        sittings, more = parse_records(sittings_found, exchange.parse_sitting)
        sitting_problems += more
        state.decision_problems = problems + sitting_problems
        now = self.now()
        state.decisions = ledger.take_decisions([(d, str(path)) for d, path, _ in decisions], state.run_id, now)
        digests = {d.item: (str(path), digest) for d, path, digest in decisions}
        for outcome in state.decisions:
            if outcome.status != "taken":
                continue
            decision, entry = outcome.decision, outcome.entry
            source, digest = digests[decision.item]
            areas.write_json(
                areas.path("evidence", "decisions", f"{decision.item}.json"),
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
                    "source": {"path": source, "sha256": digest},
                    "taken_in_by_run": state.run_id,
                    "taken_in_at": now.isoformat(),
                },
            )
            entry["evidence"] = f"evidence/decisions/{decision.item}.json"
            if decision.reason:
                entry["reason"] = decision.reason
        for sitting, path, digest in sittings:
            target = areas.path("evidence", "sittings", f"{sitting.day}.json")
            record = {
                "date": sitting.day,
                "minutes": sitting.minutes,
                "note": sitting.note,
                "source": {"path": str(path), "sha256": digest},
            }
            existing = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
            if existing is None or existing.get("source") != record["source"]:
                first = (existing or {}).get("taken_in_by_run", state.run_id)
                areas.write_json(target, dict(record, taken_in_by_run=first))
                state.sittings.append(sitting)
        taken = sum(1 for outcome in state.decisions if outcome.status == "taken")
        unusable = len(problems) + sum(1 for o in state.decisions if o.status not in ("taken", "already-taken"))
        detail = f"{report.plural(len(found), 'record')}, {taken} new since the previous run" + (
            f", {unusable} could not be used" if unusable else ""
        )
        status = package.CHANGED if taken else package.READ
        state.sources.append(SourceLine("Mandu decisions", status, detail, needs))
        sitting_detail = f"{report.plural(len(sittings_found), 'record')}, {len(state.sittings)} new" + (
            f", {len(sitting_problems)} could not be used" if sitting_problems else ""
        )
        state.sources.append(
            SourceLine("Mandu sittings", package.CHANGED if state.sittings else package.READ, sitting_detail)
        )

    def sitting_runs(self, state: RunState, areas: Areas) -> dict[str, str]:
        """Each sitting taken in so far, by date, with the run that first took in its record."""
        runs = {}
        for path in areas.files(areas.path("evidence", "sittings")):
            try:
                record = json.loads(read_plain(path).decode("utf-8"))
                runs[str(record["date"])] = str(record["taken_in_by_run"])
            except (OSError, ValueError, KeyError, TypeError, UnsafeFile) as error:
                name = areas.relative(path)
                state.problems.append(f"`{name}` could not be read, so no item carries over from it ({error})")
        return runs

    def load_state(self, state: RunState, areas: Areas, ledger: Ledger, run_id: str) -> run_state.States:
        """Each workflow's run state; an invalid file is set aside and its workflow starts again from the record."""
        states, invalid = run_state.load(areas)
        for workflow, path, reason in invalid:
            moved = ledger.set_aside(areas, path, f"run-reports/state/{path.name}", run_id, [reason])
            rebuilt = "rebuilt from the Review Queue" if workflow == run_state.REVIEW_QUEUE else "started empty"
            where = f"set aside as `{moved.moved_to}`" if moved.moved_to else "removed"
            state.problems.append(f"the {workflow} run state was not valid ({reason}); it was {where} and {rebuilt}")
        return states

    def save_state(
        self,
        state: RunState,
        areas: Areas,
        ledger: Ledger,
        states: run_state.States,
        products: Sequence[str],
        now: datetime,
    ) -> None:
        """Bring the Review Queue state into line with the ledger, note every difference, and save every state."""
        hashes, _ = run_state.item_hashes(areas.workspace, ledger.entries, products, states.review_queue)
        states.review_queue, state.state_notes = run_state.reconcile(states.review_queue, ledger.entries, hashes)
        run_state.save(areas, states, state.run_id, now.isoformat())

    def tallies(self, state: RunState, ledger: Ledger, incoming: int) -> list[run_state.Tally]:
        """What each workflow checked and acted on this run, so a quiet run still says what it looked at."""
        files = [file for result in state.snapshot for file in result.files]
        failed = sum(1 for file in files if file.status == package.FAILED) + sum(
            1 for result in state.snapshot if result.reason
        )
        changed = sum(1 for file in files if file.status == package.CHANGED)
        queued = [ledger.entries[identifier] for identifier in state.published]
        # Each queued item counts once, under the workflow that produced it; until a workflow has its own tally
        # (Drafts, Weekly Reads, Dispatch requests), its items count under the Review Queue with the launcher's notices.
        proposals = sum(1 for entry in queued if entry["kind"] == "package-change-proposal")
        others = len(queued) - proposals
        taken = sum(1 for outcome in state.decisions if outcome.status == "taken")
        superseded = sum(
            1
            for entry in ledger.entries.values()
            if entry["status"] == SUPERSEDED and entry.get("closed_by_run") == state.run_id
        )
        carried = sum(1 for entry in state.queue_after if entry.get("carried_over"))
        records = len(state.decisions) + len(state.decision_problems)
        return [
            run_state.Tally(
                "package-review",
                len(files) + sum(1 for result in state.snapshot if result.reason),
                proposals,
                f"{len(files)} files, {changed} changed, {failed} failed;"
                f" {report.plural(proposals, 'proposal')} queued",
            ),
            run_state.Tally(
                "review-queue",
                records + incoming + len(state.queue_before),
                taken + others + superseded,
                f"{taken} decisions taken in, {others} other items queued, {superseded} superseded,"
                f" {carried} carried over, {len(state.set_aside)} set aside",
            ),
            run_state.Tally("listening", 0, 0, "not built until US-ME13"),
            run_state.Tally("outreach", 0, 0, "not built until US-ME14"),
        ]

    def outputs(self, state: RunState, config: settings.Settings, ledger_ok: bool) -> None:
        """Each output's status: a built output is incomplete when a failed source it needs names it, or when its own
        step fell short."""
        failed = state.failed_sources()
        decisions = next((line.detail for line in state.sources if line.name == "Mandu decisions"), "")
        queued = report.plural(len(state.queue_after), "open item") + (
            f"; {len(state.set_aside)} set aside" if state.set_aside else ""
        )
        own = {
            "package-snapshot": ([], f"`{state.snapshot_file}`"),
            "package-review": (
                [] if state.agent.get("exit_code") == 0 else ["the agent did not finish"],
                "the agent finished its review",
            ),
            "decisions": ([], decisions),
            "review-queue": (
                [] if ledger_ok else ["the ledger could not be read; the queue was left as it was"],
                queued,
            ),
        }
        rows = []
        for key, output in config.outputs.items():
            title = str(output.get("title", key))
            if not output.get("built"):
                rows.append([title, NOT_BUILT, str(output.get("story", ""))])
                continue
            gaps, done = own.get(key, ([], ""))
            gaps = [f"{line.name} could not be read" for line in failed if title in line.needed_by] + gaps
            rows.append([title, INCOMPLETE if gaps else COMPLETE, "; ".join(gaps) or done])
        state.outputs = rows

    def leave_note(self, log_dir: Path, run_id: str, line: str) -> None:
        """A one-line note in this checkout's log folder, which its next run's report shows."""
        folder = checkout_logs(log_dir, self.repo_root) / NOTES_DIR
        folder.mkdir(parents=True, exist_ok=True)
        temporary = folder / f".{run_id}.tmp"
        temporary.write_text(line + "\n", encoding="utf-8")
        os.replace(str(temporary), str(folder / f"{run_id}.txt"))

    def lock(self, log_dir: Path, trigger: str) -> TextIO | None:
        """This checkout's run lock, held until the returned file is closed; None if another run holds it, in which
        case the refusal is left as a note for the checkout's next run report."""
        logs = checkout_logs(log_dir, self.repo_root)
        logs.mkdir(parents=True, exist_ok=True)
        handle = (logs / LOCK_FILE).open("a")
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
            self.leave_note(log_dir, run_id, line)
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
        log_dir = launcher.default_log_dir(self.env, self.home)
        lock = self.lock(log_dir, trigger)
        if lock is None:
            return EXIT_BUSY
        with lock:
            try:
                return self.locked_run(instruction, trigger, once, argv, execve)
            except (OSError, ConfigError) as error:
                now = self.now()
                line = (
                    f"A {trigger} run started at {report.wall_clock(now):%A %Y-%m-%d %H:%M} stopped before it"
                    f" finished: {error}."
                )
                self.leave_note(log_dir, launcher.new_run_id(trigger, now), line)
                self.say(f"the run stopped: {error}; the next run's report will say so")
                return EXIT_STOPPED

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

        run_id = launcher.new_run_id(trigger, started)
        state = RunState(run_id, trigger, started, str(task.relative_to(canonical(self.repo_root))), sync=sync)
        state.late_after = timedelta(minutes=config.late_after_minutes)
        if trigger == "scheduled":
            state.due = report.due_time(started, config.weekly, once)
        state.code = head(self.repo_root)
        try:
            _, boundary = load_boundary(self.repo_root, self.env, self.home)
            registry = load_json(self.repo_root / "config" / "products.json")
            folder = settings.exchange_dir(registry, boundary, self.env, self.home)
        except ConfigError as error:
            self.say(f"refusing to start: {error}")
            return launcher.EXIT_CONFIG
        areas = Areas(boundary)
        products = [str(product["name"]) for product in registry.get("products", [])]
        self.say(f"run {run_id} ({trigger}): {report.start_line(state)}")

        self.snapshot(state, config, areas, boundary, registry)
        ledger_path = areas.path("review_queue", "queue.json")
        ledger_ok = True
        try:
            ledger = Ledger.load(ledger_path)
        except QueueError as error:
            ledger, ledger_ok = Ledger(), False
            state.problems.append(f"{error}; the Review Queue was left untouched this run")
        self.take_decisions(state, config, areas, folder, ledger)
        sittings = self.sitting_runs(state, areas)
        states = self.load_state(state, areas, ledger, run_id)
        hashes, unreadable = run_state.item_hashes(areas.workspace, ledger.entries, products, states.review_queue)
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
        state.queue_before = ledger.ordered()
        state.closed_proposals = [
            entry
            for entry in ledger.entries.values()
            if entry["kind"] == "package-change-proposal" and entry["status"] != OPEN
        ]
        areas.path("review_queue", "incoming").mkdir(parents=True, exist_ok=True)
        brief = areas.path("run_reports", f"{run_id}.brief.md")
        areas.write_text(brief, report.render_brief(state, canonical(self.repo_root), areas.workspace))

        for directory in protected_paths(areas)[0]:
            areas.remove_empty_folders(directory)
        before = protected_state(areas)
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
            )
        except OSError as error:
            state.agent = {"exit_code": launcher.EXIT_CONFIG, "agent_started": False, "error": str(error)}
        finally:
            state.restored = undo_agent_changes(areas, before, run_id, ledger)
        log_dir = launcher.default_log_dir(self.env, self.home)
        last_message = log_dir / f"{run_id}.last-message.md"
        if last_message.is_file():
            state.agent_summary = last_message.read_text(encoding="utf-8", errors="replace")[:SUMMARY_LIMIT]
        state.usage = report.token_usage(log_dir / f"{run_id}.events.jsonl")
        if state.usage:
            state.cost = report.cost(state.usage, config.prices)

        now = self.now()
        if ledger_ok:
            state.published, state.set_aside = ledger.take_incoming(areas, products, run_id, now, seen)
        incoming = len(state.published) + len(state.set_aside)
        report_path = areas.path("run_reports", f"{run_id}.md")
        state.queue_after = ledger.ordered()
        state.problems += areas.problems
        areas.problems.clear()
        self.outputs(state, config, ledger_ok)
        notice = report.problems_notice(state, areas.relative(report_path))
        if notice and ledger_ok:
            title, body, touches, evidence = notice
            item = exchange.Item({"kind": "notice"}, title, body, touches, evidence)
            repeated = seen.get(exchange.item_hash(item))
            if repeated and ledger.entries[repeated]["status"] == OPEN:
                state.notice = repeated  # the same problems are already waiting for the Founder
            else:
                try:
                    state.notice = ledger.publish(areas, item, "notice-run-problems", run_id, now)
                    state.published.append(state.notice)
                except (OSError, ConfigError) as error:
                    state.problems.append(f"the notice of this run's problems could not be written ({error})")
            state.queue_after = ledger.ordered()
            self.outputs(state, config, ledger_ok)
        if ledger_ok:
            ledger.mark_carried_over(sittings)
            next_run = report.next_due(now, config.weekly)
            try:
                areas.write_json(ledger_path, ledger.as_json(run_id, now, areas.relative(report_path), next_run))
            except (OSError, ConfigError) as error:
                state.problems.append(
                    f"`review-queue/queue.json` could not be written, so Mandu sees the last one ({error})"
                )
            state.queue_after = ledger.ordered()
            try:
                self.save_state(state, areas, ledger, states, products, now)
            except (OSError, ConfigError) as error:
                state.problems.append(f"the run state could not be saved ({error})")
        state.tallies = self.tallies(state, ledger, incoming)
        notes = sorted((checkout_logs(log_dir, self.repo_root) / NOTES_DIR).glob("*.txt"))
        state.notes = [path.read_text(encoding="utf-8").strip() for path in notes]
        state.problems += areas.problems
        try:
            areas.write_text(report_path, report.render_report(state))
        except (OSError, ConfigError) as error:
            line = f"Run {run_id} could not write its report `{areas.relative(report_path)}`: {error}."
            self.leave_note(log_dir, run_id, line)
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
            undone=state.restored,
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
