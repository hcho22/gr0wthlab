"""Command line for src/bin/gr0wthlab, the one entry point for scheduled and on-demand runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import codex, cycle, exchange, launcher, posts, probe, schedule, settings
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

    run = commands.add_parser("run", help="start one run: sync, snapshot, agent, Review Queue, report, records")
    run.add_argument("--instruction", type=Path, help="a task definition under src/instructions/ (default: run.json's)")
    run.add_argument("--trigger", choices=launcher.TRIGGERS, default="on-demand")
    run.add_argument("--once", metavar="YYYY-MM-DDTHH:MM", help="the one-off time a scheduled run was due at")

    commands.add_parser("show-config", help="print the resolved run configuration and its fingerprint")
    commands.add_parser("preflight", help="prove the write boundary in the sandbox, with no model")
    commands.add_parser("check-incoming", help="check the Review Queue items waiting in review-queue/incoming/")
    drafts = commands.add_parser("check-drafts", help="check a run's post Drafts in drafts/posts/ as the launcher will")
    drafts.add_argument(
        "--run",
        required=True,
        metavar="RUN_ID",
        help="the run in progress, as its brief's check-drafts command names it",
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
    failed = 0
    for name in names:
        item, problems = ledger.check_incoming(INCOMING / name, name, products, seen)
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
    can be checked against.
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
        changed = posts.restore(plan, json.loads(read_plain(record).decode("utf-8")))
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
    failed = 0
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
        rejected = posts.rejected_as(day_plan, draft) if verdict.passed else None
        failed += not verdict.passed or bool(rejected)
        if rejected:
            print(
                f"REJECTED day {number}: {draft.path}: the Founder rejected this Draft as {rejected['id']}, so it is"
                " not asked again until it changes",
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
    print(f"{len(plan.days)} day{'' if len(plan.days) == 1 else 's'} due, {failed} with problems", file=out)
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
            print(json.dumps(launcher.preflight_summary(result), indent=2))
            return 0 if result.ok else launcher.EXIT_BOUNDARY
        if args.command == "check-incoming":
            return check_incoming()
        if args.command == "check-drafts":
            return check_drafts(args.run)
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
            sys.stdout.buffer.write(
                schedule.launch_agent(
                    args.label, program, REPO_ROOT, calendar, overrides, launcher.default_log_dir(env, home)
                )
            )
            return 0
        if args.command == "boundary-check":
            return probe.main(REPO_ROOT, env, home, args.verify, trigger=args.trigger)
    except (ConfigError, schedule.ScheduleError) as error:
        print(f"gr0wthlab: {error}", file=sys.stderr)
        return launcher.EXIT_CONFIG
    return 1
