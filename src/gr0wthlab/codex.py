"""Turn the boundary into a Codex command line, and prove the boundary before each run.

Every run, scheduled or on demand, goes through build_exec_command and child_environment,
so both start Codex with the same configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import process
from .boundary import Boundary, ConfigError, canonical, filesystem_policy

SYSTEM_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
LANG = "en_US.UTF-8"
PREFLIGHT_PREFIX = ".gr0wthlab-preflight-"
# The directories an environment names; a Codex change that made any of them writable would widen writes.
ENVIRONMENT_DIRS = ("HOME", "TMPDIR", "CODEX_HOME")


# Codex's log filter (RUST_LOG): its errors, as by default, plus the records it keeps of each tool call. Every run
# starts with it, so the boundary check judges the same configuration a weekly run has.
LOG_FILTER = "error,codex_otel.log_only=info"
# How every record in Codex's log starts; a line that starts another way continues the record before it.
LOG_RECORD = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z +(?:TRACE|DEBUG|INFO|WARN|ERROR) ", re.MULTILINE)
TOOL_RESULT = re.compile(
    r'\S+ +INFO codex_otel\.log_only: event\.name="codex\.tool_result" tool_result_seq=(?P<seq>\d+)'
    r" tool_name=(?P<tool>\S+) tool_namespace=\S* call_id=\S+ duration_ms=\d+ success=(?P<success>true|false)"
    r" output_truncated=(?:true|false) agent_name=\S* arguments="
)
# What follows a tool call's output in its record, on one line: the fields Codex ends the record with.
TOOL_RESULT_END = re.compile(r" mcp_server=\S* mcp_server_origin=\S* event\.timestamp=[^\n]*\Z")


@dataclass(frozen=True)
class ToolResult:
    """One tool call as Codex recorded it: the tool, whether it succeeded, and the rest of the record, which is the
    call's arguments, its output, and Codex's closing fields.

    The arguments and the output are the agent's and the tool's own text, unescaped, so nothing in the record says
    for certain where one ends; `gave` matches the whole of it against an expected call instead of splitting it.
    """

    seq: int
    tool: str
    success: bool
    body: str

    def gave(self, output: str) -> str | None:
        """The call's arguments if its record ends with exactly this output and Codex's closing fields, else None."""
        closing = TOOL_RESULT_END.search(self.body)
        ending = " output=" + output
        if closing is None or not self.body[: closing.start()].endswith(ending):
            return None
        return self.body[: closing.start() - len(ending)]

    def said(self) -> str:
        """About what the call returned, on one line, for a message only: a guess at where the output starts."""
        closing = TOOL_RESULT_END.search(self.body)
        output = self.body[: closing.start() if closing else len(self.body)].rpartition(" output=")[2]
        return " ".join(output.split())[:200] or "nothing"


def tool_results(log: str) -> tuple[list[ToolResult], list[str]]:
    """Every tool call Codex recorded in its log, in order, and what is wrong with the record as a whole.

    Codex numbers the calls from 1 and may write two that ran together out of order; a number missing or repeated
    means a record was lost or is not what it seems, and the log cannot be taken as the whole record of what the
    agent did.
    """
    starts = [match.start() for match in LOG_RECORD.finditer(log)] + [len(log)]
    results = []
    for start, end in zip(starts, starts[1:]):
        record = log[start:end].rstrip("\n")
        match = TOOL_RESULT.match(record)
        if match:
            results.append(
                ToolResult(int(match["seq"]), match["tool"], match["success"] == "true", record[match.end() :])
            )
    numbers = sorted(result.seq for result in results)
    problems = []
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(f"its {len(numbers)} tool calls are numbered {numbers}, not 1 to {len(numbers)} once each")
    return results, problems


def toml_string(value: str) -> str:
    # A JSON string is a valid TOML basic string for every character json.dumps emits.
    return json.dumps(value)


def toml_inline_table(table: Mapping[str, str]) -> str:
    return "{" + ", ".join(f"{toml_string(k)} = {toml_string(v)}" for k, v in table.items()) + "}"


def config_overrides(config: Mapping, boundary: Boundary) -> list[str]:
    """The -c overrides that define and select the permission profile; shared by exec and the preflight."""
    codex = config["codex"]
    profile = codex["permission_profile"]
    overrides = [
        f"default_permissions={toml_string(profile)}",
        f"permissions.{profile}.filesystem={toml_inline_table(filesystem_policy(boundary))}",
        f"permissions.{profile}.network.enabled=false",
        f"approval_policy={toml_string(codex['approval_policy'])}",
        f"agents.enabled={'true' if codex['sub_agents'] else 'false'}",
        f"shell_environment_policy.set={toml_inline_table(codex.get('shell_environment') or {})}",
    ]
    args = []
    for override in overrides:
        args += ["-c", override]
    for feature in codex.get("disabled_features") or ():
        args += ["--disable", feature]
    return args


def resolve_codex_binary(env: Mapping[str, str]) -> Path:
    explicit = env.get("GR0WTHLAB_CODEX_BIN")
    if explicit:
        if not os.path.isabs(explicit):
            raise ConfigError("GR0WTHLAB_CODEX_BIN must be an absolute path")
        found: str | None = explicit
    else:
        found = shutil.which("codex", path=env.get("PATH", ""))
    if not found or not os.access(found, os.X_OK):
        raise ConfigError("codex executable not found; set GR0WTHLAB_CODEX_BIN")
    return Path(found)


def user_temp_dir() -> str:
    """The per-user temporary directory, the same under launchd and in a terminal."""
    try:
        asked = process.run(["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"], process.QUICK)
    except OSError:
        return tempfile.gettempdir()
    return (asked.stdout.strip() if asked.ok else "") or tempfile.gettempdir()


def child_environment(home: Path, codex_bin: Path, temp_dir: str) -> dict[str, str]:
    """Build Codex's environment from scratch so a launchd run and a terminal run see the same variables."""
    user = pwd.getpwuid(os.getuid())
    return {
        "HOME": str(home),
        "USER": user.pw_name,
        "LOGNAME": user.pw_name,
        "SHELL": user.pw_shell,
        "LANG": LANG,
        "TMPDIR": temp_dir,
        "PATH": os.pathsep.join((str(codex_bin.parent),) + SYSTEM_PATH),
        "CODEX_HOME": str(home / ".codex"),
        "RUST_LOG": LOG_FILTER,
    }


def build_exec_command(config: Mapping, boundary: Boundary, codex_bin: Path, last_message: Path) -> list[str]:
    """codex exec reading its prompt from stdin; the run's only writable paths are the areas."""
    return (
        [str(codex_bin), "exec", "--cd", str(boundary.working_directory)]
        + list(config["codex"]["session_flags"])
        + ["--model", config["codex"]["model"], "--json", "--output-last-message", str(last_message)]
        + config_overrides(config, boundary)
        + ["-"]
    )


def fingerprint(command: Sequence[str], environment: Mapping[str, str], codex_version: str) -> str:
    """A digest of everything that configures a run, excluding the per-run output path."""
    stable = list(command)
    if "--output-last-message" in stable:
        index = stable.index("--output-last-message")
        stable[index + 1] = "<run>"
    payload = json.dumps(
        {"command": stable, "environment": dict(sorted(environment.items())), "codex": codex_version},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def codex_version(codex_bin: Path, environment: Mapping[str, str]) -> str:
    try:
        asked = process.run([str(codex_bin), "--version"], process.QUICK, env=environment)
    except OSError as error:
        raise ConfigError(f"cannot run {codex_bin} --version: {error}") from error
    if asked.timed_out:
        raise ConfigError(f"{codex_bin} --version did not finish within {process.limit_text(asked.limit)}")
    if asked.returncode != 0:
        raise ConfigError(f"{codex_bin} --version exited {asked.returncode}: {asked.stderr.strip()[-500:]}")
    return asked.stdout.strip()


# Runs inside the sandbox: try to create one uniquely named empty file per target and report each outcome.
# It never modifies, moves, or deletes anything it did not just create.
PREFLIGHT_SCRIPT = """
name="$1"; shift
for target in "$@"; do
  file="$target/$name"
  if [ -e "$file" ]; then echo "EXISTS $target"; continue; fi
  if ( : > "$file" ) 2>/dev/null; then echo "WROTE $target"; rm -f "$file" 2>/dev/null; else echo "REFUSED $target"; fi
done
"""


@dataclass(frozen=True)
class PreflightResult:
    allowed: tuple[Path, ...]
    refused: tuple[Path, ...]
    breaches: tuple[Path, ...]
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.breaches and not self.failures


def preflight_targets(boundary: Boundary, *environments: Mapping[str, str]) -> tuple[list[Path], list[Path]]:
    """Paths every run must be able to write, and paths every run must be refused.

    The refused paths include the directories each given environment names.
    Registry locations (Mandu, Products) are left to the agent-driven boundary check, so a routine run never
    attempts a write inside the Founder's other repositories; they are refused by the same default-deny rule.
    """
    forbidden = [
        boundary.repo_root,
        boundary.repo_root / "workspace",
        boundary.ledger,
        boundary.repo_root / "src",
        boundary.repo_root / "config",
        boundary.repo_root / "config" / "guardrails",
        Path("/private/tmp"),
        Path("/private/var/tmp"),
    ]
    forbidden += list(boundary.git_dirs)
    for environment in environments:
        forbidden += [canonical(Path(environment[name])) for name in ENVIRONMENT_DIRS]
    return list(boundary.area_paths), [path for path in dict.fromkeys(forbidden) if path.is_dir()]


def evaluate_preflight(output: str, name: str, allowed: Sequence[Path], forbidden: Sequence[Path]) -> PreflightResult:
    outcomes = {}
    for line in output.splitlines():
        verb, _, target = line.partition(" ")
        if verb in ("WROTE", "REFUSED", "EXISTS"):
            outcomes[target] = verb
    ok_allowed, refused, breaches, failures = [], [], [], []
    for path in allowed:
        outcome = outcomes.get(str(path))
        if outcome == "WROTE":
            ok_allowed.append(path)
        else:
            failures.append(f"{path} must be writable but was {outcome or 'not probed'}")
    for path in forbidden:
        outcome = outcomes.get(str(path))
        if outcome == "REFUSED":
            refused.append(path)
        elif outcome == "WROTE":
            breaches.append(path / name)
        else:
            failures.append(f"{path} must be refused but was {outcome or 'not probed'}")
    return PreflightResult(tuple(ok_allowed), tuple(refused), tuple(breaches), tuple(failures))


def run_preflight(
    config: Mapping, boundary: Boundary, codex_bin: Path, environment: Mapping[str, str], run_id: str
) -> PreflightResult:
    """Prove the profile in the real sandbox, with no model, before the agent starts.

    The probe uses an empty Codex home so no user configuration can change the policy it sees, and probes the
    directories of both the run's environment and its own.
    A sentinel that lands outside the areas is deleted here, outside the sandbox, and the run is refused.
    A probe that does not finish in time is stopped and fails the preflight, so the agent is not started.
    """
    name = PREFLIGHT_PREFIX + run_id
    with tempfile.TemporaryDirectory(prefix="gr0wthlab-preflight-") as empty_home:
        sandbox_environment = dict(environment, CODEX_HOME=empty_home)
        allowed, forbidden = preflight_targets(boundary, environment, sandbox_environment)
        # The same -c overrides as codex exec; the working directory comes from cwd because
        # codex sandbox's -C would require selecting the profile with -P instead.
        command = (
            [str(codex_bin), "sandbox"]
            + config_overrides(config, boundary)
            + ["--", "/bin/sh", "-c", PREFLIGHT_SCRIPT, "preflight", name]
            + [str(path) for path in allowed + forbidden]
        )
        completed = process.run(command, process.QUICK, env=sandbox_environment, cwd=str(boundary.working_directory))
    result = evaluate_preflight(completed.stdout, name, allowed, forbidden)
    for sentinel in result.breaches:
        if sentinel.is_file() and sentinel.stat().st_size == 0:
            sentinel.unlink()
    failure = None
    if completed.timed_out:
        failure = f"codex sandbox did not finish within {process.limit_text(completed.limit)} and was stopped"
    elif completed.returncode != 0:
        failure = f"codex sandbox exited {completed.returncode}: {completed.stderr.strip()[-500:]}"
    if failure:
        return PreflightResult(result.allowed, result.refused, result.breaches, result.failures + (failure,))
    return result
