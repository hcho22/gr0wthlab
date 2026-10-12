"""Command line for src/bin/gr0wthlab, the one entry point for scheduled and on-demand runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import (
    beta,
    beta_drafts,
    codex,
    cycle,
    evidence,
    exchange,
    fetch,
    filming,
    launcher,
    learning,
    listening,
    messages,
    outreach,
    posts,
    probe,
    schedule,
    settings,
    sources,
)
from . import state as run_state
from .areas import Areas, Store, UnsafeFile, read_plain
from .boundary import LEDGER, PRODUCT_REGISTRY, ConfigError, load_json, load_runtime_config, resolve_boundary
from .queue import QUEUE_FILE, REVIEW_QUEUE, Ledger, QueueError

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRY = REPO_ROOT / "src" / "bin" / "gr0wthlab"
INCOMING = REPO_ROOT / "workspace" / "review-queue" / "incoming"
LEDGER_DIR = REPO_ROOT / LEDGER


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gr0wthlab", description="Start and check Marketing Engineer runs.")
    commands = root.add_subparsers(dest="command", required=True)

    run = commands.add_parser(
        "run",
        help="start one run: sync, snapshot, agent, Review Queue, report, records; a weekly scheduled start runs only"
        " while the week's run is still owed and the Mac is fully awake",
    )
    run.add_argument("--instruction", type=Path, help="a task definition under src/instructions/ (default: run.json's)")
    run.add_argument("--trigger", choices=launcher.TRIGGERS, default="on-demand")
    run.add_argument(
        "--once",
        metavar="YYYY-MM-DDTHH:MM",
        help="the one-off time a scheduled run was due at; such a run always runs, as a run on demand does",
    )

    commands.add_parser("show-config", help="print the resolved run configuration and its fingerprint")
    commands.add_parser(
        "preflight", help="prove the write boundary and the closed network in the sandbox, with no model"
    )
    commands.add_parser("check-incoming", help="check the Review Queue items waiting in review-queue/incoming/")
    drafts = commands.add_parser("check-drafts", help="check a run's post Drafts in drafts/posts/ as the launcher will")
    drafts.add_argument(
        "--run",
        required=True,
        metavar="RUN_ID",
        help="the run in progress, as its brief's check-drafts command names it",
    )
    recruiting = commands.add_parser(
        "check-beta-drafts", help="check a run's Beta Cohort recruiting Drafts as the launcher will"
    )
    recruiting.add_argument(
        "--run",
        required=True,
        metavar="RUN_ID",
        help="the run in progress, as its brief's check-beta-drafts command names it",
    )

    edits = commands.add_parser("check-edits", help="check a run's edit records in drafts/edits/ as the launcher will")
    edits.add_argument(
        "--run",
        required=True,
        metavar="RUN_ID",
        help="the run in progress, as its brief's check-edits command names it",
    )
    rebuild = commands.add_parser("rebuild-asset", help="render a finished asset again from its record and the footage")
    rebuild.add_argument("record", help="the asset's record under ledger/, such as evidence/filming/assets/<name>.json")
    work = commands.add_parser(
        "check-work", help="check a run's quote records, Angle and Hook proposals, messages, and rejection codes"
    )
    work.add_argument(
        "--run", required=True, metavar="RUN_ID", help="the run in progress, as its brief's check-work command names it"
    )

    agent = commands.add_parser("launch-agent", help="print a LaunchAgent plist that runs the launcher on a schedule")
    agent.add_argument(
        "--instruction", type=Path, help="a task definition under src/instructions/ (default: run.json's)"
    )
    agent.add_argument("--label", default=schedule.DEFAULT_LABEL)
    agent.add_argument("--boundary-check", action="store_true", help="schedule the boundary check instead of a run")
    agent.add_argument(
        "--once", metavar="YYYY-MM-DDTHH:MM", help="a one-off time instead of run.json's weekly schedule"
    )

    check = commands.add_parser("boundary-check", help="run the boundary probe on demand and verify nothing escaped")
    check.add_argument("--verify", metavar="RUN_ID", help="only verify and clean up an earlier probe run")
    check.add_argument("--trigger", choices=launcher.TRIGGERS, default="on-demand")
    return root


def queued(products: list[str]) -> tuple[Ledger, dict[str, str], str | None]:
    """The last saved Review Queue, and each queued item's fingerprint mapped to its identifier."""
    try:
        ledger = Ledger.load(LEDGER_DIR / REVIEW_QUEUE / QUEUE_FILE)
    except QueueError as error:
        return Ledger(), {}, f"repeats and supersedes could not be checked: {error}"
    hashes, _ = run_state.item_hashes(LEDGER_DIR, ledger.entries, products, run_state.ReviewQueueState())
    seen: dict[str, str] = {}
    for identifier, fingerprint in hashes.items():
        seen.setdefault(fingerprint, identifier)
    return ledger, seen, None


def check_incoming(out=sys.stdout) -> int:
    """The launcher's own check of each item in incoming/, for the agent to use before it finishes."""
    products = [product["name"] for product in load_json(REPO_ROOT / PRODUCT_REGISTRY).get("products", [])]
    try:
        if any(
            path.is_symlink() or (os.path.lexists(str(path)) and not path.is_dir())
            for path in (INCOMING.parent, INCOMING)
        ):
            print(
                f"PROBLEM {INCOMING} is not a real folder; the launcher removes it and takes in nothing from it",
                file=out,
            )
            return 1
        names = sorted(os.listdir(str(INCOMING))) if INCOMING.is_dir() else []
    except OSError as error:
        print(
            f"PROBLEM {INCOMING} could not be read ({error.strerror or error}); the launcher takes in nothing from it",
            file=out,
        )
        return 1
    ledger, seen, warning = queued(products)
    if warning:
        print(warning, file=out)
    kept = evidence.records(Store(LEDGER_DIR))
    failed = 0
    for name in names:
        item, problems = ledger.check_incoming(INCOMING / name, name, products, seen, kept)
        if item is not None:
            seen[exchange.item_hash(item)] = name
        failed += bool(problems)
        print(f"{'PROBLEM' if problems else 'OK'} {name}", file=out)
        for problem in problems:
            print(f"  - {problem}", file=out)
    print(f"{len(names)} item{'' if len(names) == 1 else 's'} checked, {failed} with problems", file=out)
    return 1 if failed else 0


def check_drafts(run_id: str, out=sys.stdout) -> int:
    """The launcher's own checks of each post Draft due in a run, for the agent to use before it finishes.

    Each day's standing is read from the record the launcher wrote for that run before the agent started, never
    worked out again here: the queue it comes from is saved only when the run ends. Without that record no Draft is
    checked, and the output says so. The record also fixes the commit every claim is checked at, and names each kit
    file's fingerprint: a kit file that is no longer as the launcher read it is named, since only what it holds now
    can be checked against, and so is a day due that the calendar no longer holds, whose Draft cannot be checked.
    """
    env = dict(os.environ)
    home = Path.home()
    config = settings.load(REPO_ROOT, env, home)
    registry = load_json(REPO_ROOT / PRODUCT_REGISTRY)
    # Reading the areas and checkouts needs no git directories, and looking them up from the sandbox only adds xcrun's
    # cache warnings.
    boundary = resolve_boundary(REPO_ROOT, load_runtime_config(REPO_ROOT), registry, env, home, git=[])
    products = [product["name"] for product in registry.get("products", [])]
    plan = posts.context_plan(REPO_ROOT, config, registry, boundary, env)
    if plan is None:
        print("No active Product has a 14-day kit, so there is no post Draft to check.", file=out)
        return 0
    try:
        record = Store(LEDGER_DIR).path(cycle.RUN_REPORTS, posts.plan_file(run_id))
        changed, gone = posts.restore(plan, json.loads(read_plain(record).decode("utf-8")))
    except (ConfigError, OSError, UnsafeFile, ValueError) as error:
        print(
            f"PROBLEM the post plan of run {run_id} could not be read ({error}), so no Draft was checked; the"
            " launcher checks every Draft once you finish.",
            file=out,
        )
        return 1
    print(plan.reason, file=out)
    if changed:
        names = ", ".join(f"`{path}`" for path in changed)
        print(
            f"Kit files in Mandu that are no longer as the launcher read them for this run: {names}. The launcher"
            " checks every Draft against what it read then, so its verdict may differ from the ones below, which use"
            " what Mandu holds now.",
            file=out,
        )
    if plan.code.problem:
        print(f"PROBLEM {plan.product}'s code could not be read: {plan.code.problem}", file=out)
    areas = Areas(boundary)
    failed = len(gone)
    for number in gone:
        print(
            f"PROBLEM day {number}: the calendar as Mandu holds it now has no day {number}, so its Draft was not"
            " checked",
            file=out,
        )
    for day_plan in plan.days:
        number = day_plan.day.day
        path = plan.draft_path(number)
        if day_plan.approved:
            print(f"SKIP day {number}: approved as {day_plan.approved['id']}; it is not asked again", file=out)
            continue
        draft, problem = posts.read_draft(areas, path)
        if draft is None:
            failed += bool(problem) or not day_plan.open
            standing = f"; the open {day_plan.open['id']} stands" if day_plan.open and not problem else ""
            print(
                f"{'PROBLEM' if problem or not standing else 'OK'} day {number}: {problem or 'no Draft'}{standing}",
                file=out,
            )
            continue
        verdict = posts.check_day(plan, day_plan, draft, areas, products)[0]
        edits_folder = areas.path("drafts", filming.EDITS, f"window-{plan.window.number}")
        edit = filming.read_edit(areas, edits_folder / f"day-{number:02d}.json")[0]
        rejected = None
        if verdict.passed:
            rejected = posts.refused(day_plan.rejected, draft.sha256, edit.sha256 if edit else None)
        failed += not verdict.passed or bool(rejected)
        if rejected:
            changes = "the Draft or its edit record changes" if rejected.get("asset_sha256") else "it changes"
            print(
                f"REJECTED day {number}: {draft.path}: the Founder rejected this Draft as {rejected['id']}, so it is"
                f" not asked again until {changes}",
                file=out,
            )
            continue
        print(f"{'OK' if verdict.passed else 'BLOCKED'} day {number}: {draft.path}", file=out)
        for line in posts.grouped(verdict.blocks):
            print(f"  - {line}", file=out)
        for line in posts.grouped(verdict.warnings):
            print(f"  - warning, which does not block: {line}", file=out)
    for number, why in plan.skipped:
        print(f"SKIP day {number}: {why}", file=out)
    due = len(plan.days) + len(gone)
    print(f"{due} day{'' if due == 1 else 's'} due, {failed} with problems", file=out)
    return 1 if failed else 0


def check_edits(run_id: str, out=sys.stdout) -> int:
    """The launcher's own checks of each edit record due in a run, for the agent to use before it finishes.

    Everything is read from the record the launcher wrote for that run before the agent started: the footage it
    listed and measured, each due day's shot list, and where each day's post stands. The footage place itself is
    never opened here. Nothing is rendered either: the launcher renders a record that passes once the run ends, only
    if the day's post Draft passes too, and then measures the result. The two legs of an A/B pair are compared as
    the videos a run that ended now would leave: the one a new record that passes would be cut into, otherwise the
    one the leg's post shows. A record that cannot be cut this run, for a day whose open post shows a video, is no
    problem to fix: the record stays as it is, and so does the post's video while its Draft is unchanged.
    """
    registry = load_json(REPO_ROOT / PRODUCT_REGISTRY)
    # As in check_drafts: reading the areas needs no git directories.
    boundary = resolve_boundary(
        REPO_ROOT, load_runtime_config(REPO_ROOT), registry, dict(os.environ), Path.home(), git=[]
    )
    store = Store(LEDGER_DIR)
    try:
        record = store.path(cycle.RUN_REPORTS, filming.record_file(run_id))
        found = filming.from_record(json.loads(read_plain(record).decode("utf-8")))
    except (ConfigError, OSError, UnsafeFile, ValueError) as error:
        print(
            f"PROBLEM the filming record of run {run_id} could not be read ({error}), so no edit record was checked;"
            " the launcher checks every one once you finish.",
            file=out,
        )
        return 1
    areas = Areas(boundary)
    found.preview(areas, store)
    failed = 0
    for number, day in sorted(found.days.items()):
        asset = found.results[number]
        draft = posts.read_draft(areas, found.draft_path(number))[0] if asset.status == filming.READY else None
        approved = found.approved.get(number) or {}
        video_posts = [entry for entry in found.rejected.get(number, ()) if entry.get("asset_sha256")]
        rejected = draft and posts.refused(video_posts, draft.sha256, asset.edit_sha256)
        if draft and approved and draft.sha256 != approved.get("draft_sha256"):
            failed += 1
            print(
                f"PROBLEM day {number}: {asset.edit} will not be cut this run: the Founder approved its copy as"
                f" {approved['id']}, and its Draft is no longer that copy",
                file=out,
            )
        elif rejected:
            failed += 1
            print(
                f"REJECTED day {number}: {asset.edit}: the Founder rejected the post made from this edit record and"
                f" its Draft as {rejected['id']}, so it is not asked again until the Draft or the edit record"
                " changes",
                file=out,
            )
        elif asset.status == filming.READY:
            print(f"OK day {number}: {asset.edit}: it passes; the launcher renders and measures it", file=out)
        elif asset.withheld:
            failed += 1
            print(f"PROBLEM day {number}: {asset.edit} would not be offered: {asset.detail}", file=out)
        elif asset.status == filming.BLOCKED:
            failed += 1
            print(f"BLOCKED day {number}: {asset.edit or found.edit_path(number)}", file=out)
            for finding in asset.blocks:
                print(f"  - {finding.line()}", file=out)
        elif asset.edit and found.waits(number):
            current, unread = posts.read_draft(areas, found.draft_path(number))
            queued_from = found.posted[number].get("draft_sha256")
            keeps = (current is None and not unread) or (current is not None and current.sha256 == queued_from)
            then = (
                "the day's post keeps the video it shows"
                if keeps
                else "the day's video is cut from it again once it can be"
            )
            print(
                f"KEPT day {number}: {asset.edit}: it cannot be cut this run ({asset.detail}), so leave it as it is:"
                f" {then}",
                file=out,
            )
        elif asset.edit:
            failed += 1
            print(f"PROBLEM day {number}: {asset.edit} will not be cut this run: {asset.detail}", file=out)
        elif day.ready:
            failed += 1
            print(f"PROBLEM day {number}: it is ready for an edit record and has none", file=out)
        else:
            print(f"SKIP day {number}: no edit record is due: {asset.detail}", file=out)
    print(f"{len(found.days)} day{'' if len(found.days) == 1 else 's'} checked, {failed} with problems", file=out)
    return 1 if failed else 0


def rebuild_asset(record: str, env: dict[str, str], home: Path, out=sys.stdout) -> int:
    """Render a finished asset again from its record under ledger/ and the footage place, and say how it compares."""
    registry = load_json(REPO_ROOT / PRODUCT_REGISTRY)
    boundary = resolve_boundary(REPO_ROOT, load_runtime_config(REPO_ROOT), registry, env, home)
    where = filming.place(registry, boundary, env, home)
    ok, lines = filming.rebuild(Store(LEDGER_DIR), record, where.path if where else None, env)
    for line in lines:
        print(line, file=out)
    return 0 if ok else 1


def check_beta_drafts(run_id: str, out=sys.stdout) -> int:
    """The launcher's own checks of each recruiting Draft a run asked for, for the agent to use before it finishes.

    Which Drafts are due, and which the Founder already rejected, is read from the record the launcher wrote for that
    run before the agent started; without it no Draft is checked, and the output says so. That record names no
    Waitlist entry, and neither does anything printed here: who is invited is the launcher's alone.
    """
    env = dict(os.environ)
    home = Path.home()
    config = settings.load(REPO_ROOT, env, home)
    registry = load_json(REPO_ROOT / PRODUCT_REGISTRY)
    boundary = resolve_boundary(REPO_ROOT, load_runtime_config(REPO_ROOT), registry, env, home, git=[])
    rules = beta.rules(registry, config)
    if rules is None:
        print("No Product recruits a Beta Cohort, so there is no recruiting Draft to check.", file=out)
        return 0
    areas = Areas(boundary)
    try:
        record = Store(LEDGER_DIR).path(cycle.RUN_REPORTS, beta.plan_file(run_id))
        due = beta.restore(json.loads(read_plain(record).decode("utf-8")), areas.workspace)
    except (ConfigError, OSError, UnsafeFile, ValueError) as error:
        print(
            f"PROBLEM the recruiting plan of run {run_id} could not be read ({error}), so no Draft was checked; the"
            " launcher checks every Draft once you finish.",
            file=out,
        )
        return 1
    context = beta.context(rules, boundary)
    failed = 0
    for draft_plan in due:
        label = beta.LABELS[draft_plan.purpose]
        draft, problem = beta.read_draft(areas, draft_plan.path)
        standing = f"; the open {draft_plan.open['id']} stands" if draft_plan.open and not problem else ""
        if draft is None:
            failed += bool(problem) or not standing
            print(
                f"{'PROBLEM' if problem or not standing else 'OK'} {label}: {problem or 'no Draft'}{standing}", file=out
            )
            continue
        verdict = beta_drafts.evaluate(draft, context, draft_plan.purpose)
        rejected = beta.rejected_as(draft_plan, draft) if verdict.passed else None
        failed += not verdict.passed or bool(rejected)
        if rejected:
            print(
                f"REJECTED {label}: {draft.path}: the Founder rejected this Draft as {rejected['id']}, so it is not"
                " asked again until it changes",
                file=out,
            )
            continue
        print(f"{'OK' if verdict.passed else 'BLOCKED'} {label}: {draft.path}", file=out)
        for line in beta.grouped(verdict.blocks):
            print(f"  - {line}", file=out)
        for line in beta.grouped(verdict.warnings):
            print(f"  - warning, which does not block: {line}", file=out)
    print(f"{len(due)} Draft{'' if len(due) == 1 else 's'} due, {failed} with problems", file=out)
    return 1 if failed else 0


def work_context(run_id: str, config, registry, boundary, env, out):
    """The kit, brand rules, and Product code a message is checked against, with the code fixed to the commit the
    launcher recorded for the run, as check-drafts reads it; None when no active Product has a kit."""
    plan = posts.context_plan(REPO_ROOT, config, registry, boundary, env)
    if plan is None:
        return None
    try:
        record = Store(LEDGER_DIR).path(cycle.RUN_REPORTS, posts.plan_file(run_id))
        posts.restore(plan, json.loads(read_plain(record).decode("utf-8")))
    except (ConfigError, OSError, UnsafeFile, ValueError) as error:
        print(
            f"The post plan of run {run_id} could not be read ({error}), so claims are checked against the code as it"
            " is now; the launcher checks them at the commit it recorded.",
            file=out,
        )
    return plan.context


def check_work(run_id: str, out=sys.stdout) -> int:
    """The launcher's own checks of a run's Listening work, outreach Drafts, and proposed rejection codes, for the
    agent to use before it finishes. Nothing is written, kept, or queued here.

    What may be offered is read from the record the launcher wrote for the run before the agent started, never
    worked out again: the Founder's decisions and records it rests on are saved only when the run ends. Every quote
    is checked against that run's snapshot, which the launcher fetched and keeps only while the run is in progress;
    this command never touches the network.
    """
    env = dict(os.environ)
    home = Path.home()
    config = settings.load(REPO_ROOT, env, home)
    registry = load_json(REPO_ROOT / PRODUCT_REGISTRY)
    boundary = resolve_boundary(REPO_ROOT, load_runtime_config(REPO_ROOT), registry, env, home, git=[])
    products = [product["name"] for product in registry.get("products", [])]
    store, areas = Store(LEDGER_DIR), Areas(boundary)
    try:
        record = json.loads(read_plain(store.path(cycle.RUN_REPORTS, f"{run_id}.work-plan.json")).decode("utf-8"))
        policy = fetch.load_policy(REPO_ROOT)
        source_config = sources.load(REPO_ROOT, policy)
        planned = record.get("listening") or {}
        snapshot = (
            sources.load_snapshot(store.path(*Path(planned["snapshot"]).parts)) if planned.get("snapshot") else None
        )
    except (ConfigError, OSError, UnsafeFile, ValueError, sources.SourceError) as error:
        print(
            f"PROBLEM the plan of run {run_id} could not be read ({error}), so nothing was checked; the launcher"
            " checks everything once you finish.",
            file=out,
        )
        return 1
    context = work_context(run_id, config, registry, boundary, env, out)
    ledger, seen, warning = queued(products)
    if warning:
        print(warning, file=out)
    now = datetime.now(timezone.utc)
    checked = failed = 0

    def say(ok: bool, line: str, problems=()) -> None:
        nonlocal checked, failed
        checked += 1
        failed += not ok
        print(line, file=out)
        for problem in problems:
            print(f"  - {problem}", file=out)

    def say_message(outcome: messages.Outcome, what: str) -> None:
        good = outcome.status in (messages.QUEUED, messages.KEPT, messages.APPROVED_BEFORE)
        quiet = outcome.status == messages.NOT_DUE
        word = "OK" if good else "NOT OFFERED" if quiet else outcome.status.upper()
        if outcome.status == messages.BLOCKED and outcome.verdict is not None:
            say(False, f"{word} {what}", messages.failing(outcome))
        else:
            say(good or quiet, f"{word} {what}" + (f": {outcome.detail}" if outcome.detail else ""))
        if outcome.verdict:
            for finding in sorted({finding.line() for finding in outcome.verdict.warnings}):
                print(f"  - warning, which does not block: {finding}", file=out)

    if record.get("listening"):
        empty = sources.Snapshot(run_id, now.isoformat(), now.astimezone().date().isoformat())
        plan = listening.restore(record["listening"], source_config, snapshot or empty, store, run_id)
        result = listening.take(plan, context, areas, store, ledger, run_id, now, products, dict(seen), publish=False)
        for quote in result.accepted:
            say(True, f"OK quote {quote.id}: its words stand in the text fetched from {quote.link}")
        for name, problems in result.rejected:
            say(False, f"PROBLEM quote {name}", problems)
        for name, _ in result.proposed:
            say(True, f"OK proposal {name}: every source it cites is validated Listening Evidence")
        for name, problems in result.discarded:
            say(False, f"PROBLEM proposal {name}", problems)
        for outcome in result.replies:
            say_message(outcome, f"reply {outcome.target.key}")
    if record.get("outreach"):
        plan = outreach.restore(record["outreach"], areas, run_id)
        if plan.problem:
            print(f"{plan.problem[0].upper()}{plan.problem[1:]}.", file=out)
        elif context is None:
            say(False, "PROBLEM no active Product has a kit, so no message could be checked")
        else:
            for outcome in outreach.take(plan, context, areas, store, ledger, run_id, now, products, False).outcomes:
                say_message(outcome, f"{outcome.target.label}, {outreach.kind_of(outcome.target)}")
    coded = learning.take(areas, store, ledger, products, run_id, now, publish=False)
    for item, code in coded.coded:
        say(True, f"OK code {item}: {code}, {learning.kind(code)}")
    for name, problems in coded.set_aside:
        say(False, f"PROBLEM code {name}", problems)
    for reason in coded.uncoded():
        say(False, f"PROBLEM code {reason.item}: its rejection reason has no code yet")
    print(f"{checked} checked, {failed} with problems", file=out)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    args = parser().parse_args(arguments)
    env = dict(os.environ)
    home = Path.home()
    try:
        if args.command == "run":
            return cycle.main(REPO_ROOT, args.instruction, args.trigger, env, home, args.once, arguments)
        if args.command == "show-config":
            resolved = launcher.Resolved(REPO_ROOT, env, home, Path("<run>.last-message.md"))
            print(json.dumps(resolved.describe(), indent=2, sort_keys=True))
            return 0
        if args.command == "preflight":
            resolved = launcher.Resolved(REPO_ROOT, env, home, Path("<run>.last-message.md"))
            result = codex.run_preflight(
                resolved.config, resolved.boundary, resolved.codex_bin, resolved.environment, "manual"
            )
            network = codex.run_network_probe(
                resolved.config, resolved.boundary, resolved.codex_bin, resolved.environment, resolved.network_targets
            )
            print(json.dumps(dict(launcher.preflight_summary(result), network=network.as_json()), indent=2))
            return 0 if result.ok and network.ok else launcher.EXIT_BOUNDARY
        if args.command == "check-incoming":
            return check_incoming()
        if args.command == "check-drafts":
            return check_drafts(args.run)
        if args.command == "check-edits":
            return check_edits(args.run)
        if args.command == "rebuild-asset":
            return rebuild_asset(args.record, env, home)
        if args.command == "check-beta-drafts":
            return check_beta_drafts(args.run)
        if args.command == "check-work":
            return check_work(args.run)
        if args.command == "launch-agent":
            config = settings.load(REPO_ROOT, env, home)
            if args.boundary_check:
                program = schedule.boundary_check_arguments(ENTRY)
            else:
                instruction = settings.instruction_path(REPO_ROOT, args.instruction or config.instruction)
                program = schedule.run_arguments(ENTRY, instruction, args.once)
            calendar = schedule.once(args.once) if args.once else schedule.weekly(*config.weekly)
            overrides = {
                key: value for key, value in env.items() if key.startswith("GR0WTHLAB_") and key != cycle.PRE_RUN_ENV
            }
            overrides["GR0WTHLAB_CODEX_BIN"] = str(codex.resolve_codex_binary(env))
            # Only the weekly run is checked again at an interval; a one-off job starts once, at its time.
            weekly = not args.once and not args.boundary_check
            sys.stdout.buffer.write(
                schedule.launch_agent(
                    args.label,
                    program,
                    REPO_ROOT,
                    calendar,
                    overrides,
                    launcher.default_log_dir(env, home),
                    config.check_every_minutes * 60 if weekly else None,
                )
            )
            return 0
        if args.command == "boundary-check":
            return probe.main(REPO_ROOT, env, home, args.verify, trigger=args.trigger)
    except (ConfigError, schedule.ScheduleError) as error:
        print(f"gr0wthlab: {error}", file=sys.stderr)
        return launcher.EXIT_CONFIG
    return 1
