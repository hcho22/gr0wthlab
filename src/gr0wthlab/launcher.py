"""Start one Marketing Engineer run: resolve the boundary, prove it, then hand Codex the instruction.

The weekly LaunchAgent and an on-demand run both call run(); only the trigger label in the prompt differs.
"""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from . import codex
from .boundary import Boundary, ConfigError, filesystem_policy, load_boundary

TRIGGERS = ("on-demand", "scheduled")
EXIT_CONFIG = 2
EXIT_BOUNDARY = 3


def default_log_dir(env: Mapping[str, str], home: Path) -> Path:
    return Path(env.get("GR0WTHLAB_LOG_DIR") or home / "Library" / "Logs" / "gr0wthlab")


def new_run_id(trigger: str, now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%SZ}-{trigger}-{secrets.token_hex(2)}"


def compose_prompt(
    boundary: Boundary, run_id: str, trigger: str, started_at: str, instruction_path: Path, instruction: str
) -> str:
    """Facts about this run, then the instruction; the boundary itself is enforced by the sandbox, not by this text."""
    lines = [
        f"# gr0wthlab run {run_id}",
        "",
        f"- Trigger: {trigger}, started {started_at}.",
        f"- Repository: {boundary.repo_root} (git directory {boundary.git_dirs[0]}).",
        "- Writable areas; the runtime refuses every other write:",
    ]
    lines += [f"  - {key}: {path}" for key, path in boundary.areas]
    lines.append("- Read-only locations:")
    lines += [f"  - {location.label}: {location.path}" for location in boundary.locations]
    lines += [f"- Instruction: {instruction_path}", "", "---", "", instruction.rstrip(), ""]
    return "\n".join(lines)


class Resolved:
    """Everything that configures a run, resolved once and shared by show-config, preflight, and run."""

    def __init__(self, repo_root: Path, env: Mapping[str, str], home: Path, last_message: Path):
        self.config, self.boundary = load_boundary(repo_root, env, home)
        self.codex_bin = codex.resolve_codex_binary(env)
        self.environment = codex.child_environment(env, home, self.codex_bin, codex.user_temp_dir())
        self.codex_version = codex.codex_version(self.codex_bin, self.environment)
        self.model = codex.model(self.config, env)
        self.command = codex.build_exec_command(self.config, self.boundary, self.codex_bin, self.model, last_message)
        self.fingerprint = codex.fingerprint(self.command, self.environment, self.codex_version)

    def describe(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "codex": str(self.codex_bin),
            "codex_version": self.codex_version,
            "model": self.model,
            "working_directory": str(self.boundary.working_directory),
            "filesystem_policy": filesystem_policy(self.boundary),
            "network": self.boundary.network,
            "command": self.command,
            "environment": self.environment,
        }


def write_json(path: Path, data: Mapping) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preflight_summary(result: codex.PreflightResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "writable": [str(path) for path in result.allowed],
        "refused": [str(path) for path in result.refused],
        "breaches": [str(path) for path in result.breaches],
        "failures": list(result.failures),
    }


def run(
    repo_root: Path,
    instruction_path: Path,
    trigger: str,
    env: Mapping[str, str],
    home: Path,
    out: TextIO = sys.stdout,
    now: datetime | None = None,
) -> dict[str, object]:
    """Run once and return the run record; record["exit_code"] is the launcher's exit status."""
    if trigger not in TRIGGERS:
        raise ConfigError(f"trigger must be one of {', '.join(TRIGGERS)}")
    started = now or datetime.now(timezone.utc)
    run_id = new_run_id(trigger, started)
    log_dir = default_log_dir(env, home)
    log_dir.mkdir(parents=True, exist_ok=True)
    record_path = log_dir / f"{run_id}.json"
    record: dict[str, object] = {
        "run_id": run_id,
        "trigger": trigger,
        "started_at": started.isoformat(),
        "instruction": str(instruction_path),
    }
    try:
        instruction = instruction_path.read_text(encoding="utf-8")
        resolved = Resolved(repo_root, env, home, log_dir / f"{run_id}.last-message.md")
    except (OSError, ConfigError) as error:
        record.update(exit_code=EXIT_CONFIG, error=str(error))
        write_json(record_path, record)
        print(f"gr0wthlab: refusing to start: {error}", file=out)
        return record
    record.update(resolved.describe())
    print(f"gr0wthlab: run {run_id} ({trigger}), configuration {resolved.fingerprint}", file=out)

    preflight = codex.run_preflight(
        resolved.config, resolved.boundary, resolved.codex_bin, resolved.environment, run_id
    )
    record["preflight"] = preflight_summary(preflight)
    if not preflight.ok:
        record["exit_code"] = EXIT_BOUNDARY
        write_json(record_path, record)
        print("gr0wthlab: boundary preflight failed; the agent was not started", file=out)
        for line in [str(path) for path in preflight.breaches] + list(preflight.failures):
            print(f"  {line}", file=out)
        return record
    print(
        f"gr0wthlab: preflight refused {len(preflight.refused)} paths and allowed {len(preflight.allowed)} areas",
        file=out,
    )

    prompt = compose_prompt(resolved.boundary, run_id, trigger, started.isoformat(), instruction_path, instruction)
    write_json(record_path, record)
    with (
        (log_dir / f"{run_id}.events.jsonl").open("w", encoding="utf-8") as events,
        (log_dir / f"{run_id}.stderr.log").open("w", encoding="utf-8") as errors,
    ):
        completed = subprocess.run(
            resolved.command,
            input=prompt,
            stdout=events,
            stderr=errors,
            text=True,
            env=resolved.environment,
            cwd=str(resolved.boundary.working_directory),
        )
    record.update(exit_code=completed.returncode, finished_at=datetime.now(timezone.utc).isoformat())
    write_json(record_path, record)
    print(f"gr0wthlab: run {run_id} finished with exit code {completed.returncode}; logs in {log_dir}", file=out)
    return record
