"""Start one agent session: resolve the boundary, prove it, then hand Codex the instruction.

The weekly LaunchAgent and an on-demand run both call run(), once for each session of a run; only the prompt's header
and instruction differ between them, never the configuration. A session has a time limit: one still running at it is
stopped with every process the process table shows it started, and the session's record says so.
"""

from __future__ import annotations

import json
import secrets
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from . import codex, fetch, founder, process
from .areas import clear_probe_files
from .boundary import MANDU, Boundary, ConfigError, filesystem_policy, load_boundary

TRIGGERS = ("on-demand", "scheduled")
EXIT_CONFIG = 2
EXIT_BOUNDARY = 3
# A run that could not finish its work: one stopped by an error, or one whose agent was stopped at its time limit.
EXIT_STOPPED = 6


def default_log_dir(env: Mapping[str, str], home: Path) -> Path:
    return Path(env.get("GR0WTHLAB_LOG_DIR") or home / "Library" / "Logs" / "gr0wthlab")


def new_run_id(trigger: str, now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%SZ}-{trigger}-{secrets.token_hex(2)}"


def compose_prompt(
    boundary: Boundary,
    run_id: str,
    trigger: str,
    started_at: str,
    instruction_path: Path,
    instruction: str,
    facts: Sequence[str] = (),
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
    for location in boundary.locations:
        if location.label != MANDU:
            lines.append(f"  - {location.label}: {location.path}")
            continue
        lines.append(f"  - {location.label}: {location.path}, of which only these paths; the runtime refuses the rest:")
        lines += [f"    - {path}" for path in boundary.package_paths]
    lines += [f"- {fact}" for fact in facts]
    lines += [f"- Instruction: {instruction_path}", "", "---", "", instruction.rstrip(), ""]
    return "\n".join(lines)


# Where a session's closing message goes, in a command shown before any session has a place for it.
ANY_RUN = Path("<run>.last-message.md")


class Resolved:
    """Everything that configures a run, resolved once and shared by show-config, preflight, and run, and by every
    session of one run: only the path of a session's closing message differs between two sessions' commands, and the
    fingerprint leaves that path out."""

    def __init__(self, repo_root: Path, env: Mapping[str, str], home: Path, last_message: Path = ANY_RUN):
        self.config, self.boundary = load_boundary(repo_root, env, home)
        # A folder of the Founder's records that is missing, or is a link, could not be proven refused: stop here.
        founder.check(self.boundary.ledger)
        # The hosts the launcher itself may read (config/guardrails/fetch.json); the sandbox must reach none of them.
        self.network_targets = [f"{host}:{fetch.PORT}" for host in fetch.load_policy(repo_root).hosts]
        self.codex_bin = codex.resolve_codex_binary(env)
        self.environment = codex.child_environment(home, self.codex_bin, codex.user_temp_dir())
        self.codex_version = codex.codex_version(self.codex_bin, self.environment)
        self.command = self.command_for(last_message)
        self.fingerprint = self.fingerprint_of(self.command)

    def command_for(self, last_message: Path) -> list[str]:
        """The command one session is started with, which writes its closing message there."""
        return codex.build_exec_command(self.config, self.boundary, self.codex_bin, last_message)

    def fingerprint_of(self, command: Sequence[str]) -> str:
        """The fingerprint of one session's own command, so that each session's record proves what it started with."""
        return codex.fingerprint(command, self.environment, self.codex_version)

    def describe(self, command: Sequence[str] | None = None) -> dict[str, object]:
        command = self.command if command is None else list(command)
        return {
            "fingerprint": self.fingerprint_of(command),
            "codex": str(self.codex_bin),
            "codex_version": self.codex_version,
            "model": self.config["codex"]["model"],
            "reasoning_effort": self.config["codex"]["reasoning_effort"],
            "working_directory": str(self.boundary.working_directory),
            "filesystem_policy": filesystem_policy(self.boundary),
            "command": command,
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


def footage_refused(reads: codex.ReadProbe) -> str:
    """What the read probe was refused, in a line: the footage place and how many footage folders in it."""
    folders = len(reads.refused) - 1
    return f"the footage place and of {folders} footage folder{'' if folders == 1 else 's'} in it"


def footage_reason(reads: codex.ReadProbe) -> str:
    """Why a read probe that did not pass keeps the agent from starting, the one wording the printed line and the
    session's record carry, and from that record the run report and the notice: the sandbox could read where raw
    footage is kept only where the probe's own output shows a folder listed. A probe that listed none, because it
    did not finish, ended with an error, or did not try a folder, shows nothing of what the sandbox can read."""
    if reads.listed:
        return "the sandbox could read where raw footage is kept"
    return "the check that the sandbox cannot read the footage place did not finish"


def network_reason(network: codex.NetworkProbe) -> tuple[str, str]:
    """The same for a network probe, as the session's record words it and as the printed line does: the sandbox
    reached the network only where the probe's own output shows a connection opened."""
    if network.reached:
        return "the sandbox's network was not closed", "the sandbox reached the network"
    unfinished = "the check that the sandbox cannot reach the network did not finish"
    return unfinished, unfinished


def log_name(run_id: str, session: str | None) -> str:
    """What a session's files in the log folder are named for: its run, and its own name when the run has several."""
    return f"{run_id}.{session}" if session else run_id


def run(
    repo_root: Path,
    instruction_path: Path,
    trigger: str,
    env: Mapping[str, str],
    home: Path,
    out: TextIO = sys.stdout,
    now: datetime | None = None,
    facts: Sequence[str] = (),
    run_id: str | None = None,
    *,
    time_limit: float,
    clock: process.Clock = process.CLOCK,
    session: str | None = None,
    instruction: str | None = None,
    resolved: Resolved | None = None,
) -> dict[str, object]:
    """Run the agent once and return the session's record; record["exit_code"] is the launcher's exit status.

    facts are extra header lines for the prompt, which the configuration fingerprint does not cover.
    session names one of a run's several sessions: its record, event stream, log, and closing message are then kept
    under the run's identifier and that name, so no session of a run writes over another's. instruction is the task
    definition the launcher put together for it, when it is more than the one file instruction_path names. resolved
    is the run's configuration when the run resolved it once for all its sessions; the boundary is still proved
    before this session's agent starts, and the fingerprint recorded is of this session's own command.
    record["agent_started"] says whether Codex itself was started, after the preflight passed.
    record["probe_files_removed"] names what a stopped boundary check had left in the areas, removed before the
    preflight so that no agent finds it and the records step after the run cannot commit it. The production clone's
    pre-run records step comes before this, so the cycle clears the areas ahead of it as well.
    time_limit is how many seconds the agent has, by the wall clock or awake, whichever the clock shows first. One
    still running then is stopped with every process the process table shows it started: record["timed_out"] is True,
    record["exit_code"] is EXIT_STOPPED whatever status the stopped agent left, and record["stopped"] names the
    processes asked to stop, forced, and left running.
    record["agent_seconds"] is the agent's wall-clock time, and record["agent_awake_seconds"] how much of it the Mac
    was awake.
    """
    if trigger not in TRIGGERS:
        raise ConfigError(f"trigger must be one of {', '.join(TRIGGERS)}")
    started = now or datetime.now(timezone.utc)
    run_id = run_id or new_run_id(trigger, started)
    log_dir = default_log_dir(env, home)
    log_dir.mkdir(parents=True, exist_ok=True)
    name = log_name(run_id, session)
    record_path = log_dir / f"{name}.json"
    record: dict[str, object] = {
        "run_id": run_id,
        "trigger": trigger,
        "started_at": started.isoformat(),
        "instruction": str(instruction_path),
        "agent_started": False,
    }
    if session:
        record.update(session=session, session_started_at=datetime.now(timezone.utc).isoformat())
    try:
        if instruction is None:
            instruction = instruction_path.read_text(encoding="utf-8")
        resolved = resolved or Resolved(repo_root, env, home)
        # A run resolves its configuration once for all its sessions, and the preflight below tries only folders that
        # exist: so each session checks again that every folder of the Founder's records is still a real folder, and
        # one that is not keeps this session from starting, never leaves its preflight one target short.
        founder.check(resolved.boundary.ledger)
    except (OSError, ConfigError) as error:
        record.update(exit_code=EXIT_CONFIG, error=str(error))
        write_json(record_path, record)
        print(f"gr0wthlab: refusing to start: {error}", file=out)
        return record
    command = resolved.command_for(log_dir / f"{name}.last-message.md")
    record.update(resolved.describe(command))
    said = f"run {run_id}, session {session}" if session else f"run {run_id}"
    print(f"gr0wthlab: {said} ({trigger}), configuration {record['fingerprint']}", file=out)
    left = clear_probe_files(resolved.boundary, keep=run_id)
    if left:
        record["probe_files_removed"] = left
        print(f"gr0wthlab: removed boundary probe files left in the areas: {', '.join(left)}", file=out)

    preflight = codex.run_preflight(
        resolved.config, resolved.boundary, resolved.codex_bin, resolved.environment, run_id
    )
    record["preflight"] = preflight_summary(preflight)
    if not preflight.ok:
        found = [f"wrote {path}" for path in preflight.breaches] + list(preflight.failures)
        record.update(exit_code=EXIT_BOUNDARY, error="the boundary preflight failed: " + "; ".join(found))
        write_json(record_path, record)
        print("gr0wthlab: boundary preflight failed; the agent was not started", file=out)
        for line in [str(path) for path in preflight.breaches] + list(preflight.failures):
            print(f"  {line}", file=out)
        return record
    print(
        f"gr0wthlab: preflight refused {len(preflight.refused)} paths and allowed {len(preflight.allowed)} areas",
        file=out,
    )
    reads = codex.run_read_probe(resolved.config, resolved.boundary, resolved.codex_bin, resolved.environment)
    record["preflight"]["footage"] = reads.as_json()
    if not reads.ok:
        reason = footage_reason(reads)
        found = [f"listed {path}" for path in reads.listed] + list(reads.failures)
        record.update(exit_code=EXIT_BOUNDARY, error=f"{reason}: " + "; ".join(found))
        write_json(record_path, record)
        print(f"gr0wthlab: {reason}; the agent was not started", file=out)
        for line in found:
            print(f"  {line}", file=out)
        return record
    if reads.refused:
        print(f"gr0wthlab: preflight refused a listing of {footage_refused(reads)}", file=out)
    network = codex.run_network_probe(
        resolved.config, resolved.boundary, resolved.codex_bin, resolved.environment, resolved.network_targets
    )
    record["preflight"]["network"] = network.as_json()
    if not network.ok:
        recorded, printed = network_reason(network)
        found = [f"reached {target}" for target in network.reached] + list(network.failures)
        record.update(exit_code=EXIT_BOUNDARY, error=f"{recorded}: " + "; ".join(found))
        write_json(record_path, record)
        print(f"gr0wthlab: {printed}; the agent was not started", file=out)
        for line in list(network.reached) + list(network.failures):
            print(f"  {line}", file=out)
        return record

    prompt = compose_prompt(
        resolved.boundary, run_id, trigger, started.isoformat(), instruction_path, instruction, facts
    )
    record.update(agent_started=True, time_limit_seconds=time_limit)
    write_json(record_path, record)
    with (
        (log_dir / f"{name}.events.jsonl").open("w", encoding="utf-8") as events,
        (log_dir / f"{name}.stderr.log").open("w", encoding="utf-8") as errors,
    ):
        completed = process.run(
            command,
            time_limit,
            input=prompt,
            stdout=events,
            stderr=errors,
            env=resolved.environment,
            cwd=str(resolved.boundary.working_directory),
            clock=clock,
        )
    record.update(
        exit_code=completed.returncode,
        agent_seconds=round(completed.seconds, 1),
        agent_awake_seconds=round(completed.awake, 1),
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    if completed.stop is None:
        print(f"gr0wthlab: {said} finished with exit code {completed.returncode}; logs in {log_dir}", file=out)
    else:
        record.update(
            exit_code=EXIT_STOPPED,
            timed_out=True,
            agent_exit_code=completed.returncode,
            stopped=completed.stop.as_json(),
        )
        print(
            f"gr0wthlab: {said} timed out: the agent was still running at its {process.limit_text(time_limit)}"
            f" time limit and was stopped; {completed.stop.describe()}; logs in {log_dir}",
            file=out,
        )
    write_json(record_path, record)
    return record
