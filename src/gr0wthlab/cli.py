"""Command line for src/bin/gr0wthlab, the one entry point for scheduled and on-demand runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import codex, cycle, exchange, launcher, probe, schedule, settings
from . import state as run_state
from .areas import UnsafeFile, read_plain
from .boundary import PRODUCT_REGISTRY, ConfigError, load_json
from .queue import QUEUE_FILE, Ledger, QueueError

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRY = REPO_ROOT / "src" / "bin" / "gr0wthlab"
INCOMING = REPO_ROOT / "workspace" / "review-queue" / "incoming"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gr0wthlab", description="Start and check Marketing Engineer runs.")
    commands = root.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="start one run: sync, snapshot, agent, Review Queue, report, records")
    run.add_argument("--instruction", type=Path, help="a task definition under src/instructions/ (default: run.json's)")
    run.add_argument("--trigger", choices=launcher.TRIGGERS, default="on-demand")
    due = run.add_mutually_exclusive_group()
    due.add_argument("--weekly", nargs=2, metavar=("DAY", "HH:MM"), help="the schedule a scheduled run was due on")
    due.add_argument("--once", metavar="YYYY-MM-DDTHH:MM", help="the one-off time a scheduled run was due at")

    commands.add_parser("show-config", help="print the resolved run configuration and its fingerprint")
    commands.add_parser("preflight", help="prove the write boundary in the sandbox, with no model")
    commands.add_parser("check-incoming", help="check the Review Queue items waiting in review-queue/incoming/")

    agent = commands.add_parser("launch-agent", help="print a LaunchAgent plist that runs the launcher on a schedule")
    agent.add_argument(
        "--instruction", type=Path, help="a task definition under src/instructions/ (default: run.json's)"
    )
    agent.add_argument("--label", default=schedule.DEFAULT_LABEL)
    agent.add_argument("--boundary-check", action="store_true", help="schedule the boundary check instead of a run")
    when = agent.add_mutually_exclusive_group()
    when.add_argument("--weekly", nargs=2, metavar=("DAY", "HH:MM"), help="default: run.json's schedule")
    when.add_argument("--once", metavar="YYYY-MM-DDTHH:MM")

    check = commands.add_parser("boundary-check", help="run the boundary probe on demand and verify nothing escaped")
    check.add_argument("--verify", metavar="RUN_ID", help="only verify and clean up an earlier probe run")
    check.add_argument("--trigger", choices=launcher.TRIGGERS, default="on-demand")
    return root


def queued_fingerprints(products: list[str]) -> tuple[dict[str, str], str | None]:
    """Each queued item's fingerprint, mapped to its identifier, as of the last saved Review Queue."""
    try:
        ledger = Ledger.load(INCOMING.parent / QUEUE_FILE)
    except QueueError as error:
        return {}, f"repeats were not checked: {error}"
    hashes, _ = run_state.item_hashes(INCOMING.parents[1], ledger.entries, products, run_state.ReviewQueueState())
    seen: dict[str, str] = {}
    for identifier, fingerprint in hashes.items():
        seen.setdefault(fingerprint, identifier)
    return seen, None


def check_incoming(out=sys.stdout) -> int:
    """The same item check the launcher applies after the run, for the agent to use before it finishes."""
    products = [product["name"] for product in load_json(REPO_ROOT / PRODUCT_REGISTRY).get("products", [])]
    names = sorted(name for name in os.listdir(str(INCOMING))) if INCOMING.is_dir() else []
    seen, warning = queued_fingerprints(products)
    if warning:
        print(warning, file=out)
    failed = 0
    for name in names:
        try:
            check = exchange.check_item(read_plain(INCOMING / name).decode("utf-8"), products)
            problems = check.problems
            if check.item is not None:
                fingerprint = exchange.item_hash(check.item)
                if fingerprint in seen:
                    problems = [f"asks the same as {seen[fingerprint]}, which is already queued or decided"]
                seen.setdefault(fingerprint, name)
        except (UnsafeFile, OSError, UnicodeDecodeError) as error:
            problems = [f"unreadable: {error}"]
        slug = name[: -len(".md")] if name.endswith(".md") else ""
        if not exchange.SLUG_PATTERN.fullmatch(slug):
            problems = ["name it <slug>.md, the slug in lowercase-with-hyphens"] + problems
        failed += bool(problems)
        print(f"{'PROBLEM' if problems else 'OK'} {name}", file=out)
        for problem in problems:
            print(f"  - {problem}", file=out)
    print(f"{len(names)} item{'' if len(names) == 1 else 's'} checked, {failed} with problems", file=out)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    args = parser().parse_args(arguments)
    env = dict(os.environ)
    home = Path.home()
    try:
        if args.command == "run":
            weekly = tuple(args.weekly) if args.weekly else None
            return cycle.main(REPO_ROOT, args.instruction, args.trigger, env, home, weekly, args.once, arguments)
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
        if args.command == "launch-agent":
            config = settings.load(REPO_ROOT, env, home)
            if args.boundary_check:
                program = schedule.boundary_check_arguments(ENTRY)
            else:
                instruction = settings.instruction_path(REPO_ROOT, args.instruction or config.instruction)
                weekly_at = None if args.once else tuple(args.weekly or config.weekly)
                program = schedule.run_arguments(ENTRY, instruction, weekly_at, args.once)
            calendar = schedule.once(args.once) if args.once else schedule.weekly(*(args.weekly or config.weekly))
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
