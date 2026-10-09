"""Command line for src/bin/gr0wthlab, the one entry point for scheduled and on-demand runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import codex, launcher, probe, schedule
from .boundary import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRY = REPO_ROOT / "src" / "bin" / "gr0wthlab"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gr0wthlab", description="Start and check Marketing Engineer runs.")
    commands = root.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="start one run with an instruction file")
    run.add_argument("--instruction", required=True, type=Path)
    run.add_argument("--trigger", choices=launcher.TRIGGERS, default="on-demand")

    commands.add_parser("show-config", help="print the resolved run configuration and its fingerprint")
    commands.add_parser("preflight", help="prove the write boundary in the sandbox, with no model")

    agent = commands.add_parser("launch-agent", help="print a LaunchAgent plist that runs the launcher on a schedule")
    agent.add_argument("--instruction", required=True, type=Path)
    agent.add_argument("--label", default=schedule.DEFAULT_LABEL)
    when = agent.add_mutually_exclusive_group(required=True)
    when.add_argument("--weekly", nargs=2, metavar=("DAY", "HH:MM"))
    when.add_argument("--once", metavar="YYYY-MM-DDTHH:MM")

    check = commands.add_parser("boundary-check", help="run the boundary probe on demand and verify nothing escaped")
    check.add_argument("--verify", metavar="RUN_ID", help="only verify and clean up an earlier probe run")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    env = dict(os.environ)
    home = Path.home()
    try:
        if args.command == "run":
            instruction = args.instruction.resolve()
            return int(launcher.run(REPO_ROOT, instruction, args.trigger, env, home)["exit_code"])
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
        if args.command == "launch-agent":
            calendar = schedule.weekly(*args.weekly) if args.weekly else schedule.once(args.once)
            overrides = {key: value for key, value in env.items() if key.startswith("GR0WTHLAB_")}
            overrides["GR0WTHLAB_CODEX_BIN"] = str(codex.resolve_codex_binary(env))
            sys.stdout.buffer.write(
                schedule.launch_agent(
                    args.label,
                    ENTRY,
                    REPO_ROOT,
                    args.instruction.resolve(),
                    calendar,
                    overrides,
                    launcher.default_log_dir(env, home),
                )
            )
            return 0
        if args.command == "boundary-check":
            return probe.main(REPO_ROOT, env, home, args.verify)
    except (ConfigError, schedule.ScheduleError) as error:
        print(f"gr0wthlab: {error}", file=sys.stderr)
        return launcher.EXIT_CONFIG
    return 1
