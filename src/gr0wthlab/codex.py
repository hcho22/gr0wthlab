"""Turn the boundary into a Codex command line, and prove the boundary before each run.

Every run, scheduled or on demand, goes through build_exec_command and child_environment,
so both start Codex with the same configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .boundary import Boundary, ConfigError, canonical, filesystem_policy

SYSTEM_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
LANG = "en_US.UTF-8"
PREFLIGHT_PREFIX = ".gr0wthlab-preflight-"
# The directories an environment names; a Codex change that made any of them writable would widen writes.
ENVIRONMENT_DIRS = ("HOME", "TMPDIR", "CODEX_HOME")


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
        f"permissions.{profile}.network.enabled={'true' if boundary.network else 'false'}",
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
        value = subprocess.run(
            ["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if value:
            return value
    except (OSError, subprocess.CalledProcessError):
        pass
    return tempfile.gettempdir()


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
        return subprocess.run(
            [str(codex_bin), "--version"], check=True, capture_output=True, text=True, env=dict(environment)
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ConfigError(f"cannot run {codex_bin} --version: {error}") from error


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
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=sandbox_environment,
            cwd=str(boundary.working_directory),
        )
    result = evaluate_preflight(completed.stdout, name, allowed, forbidden)
    for sentinel in result.breaches:
        if sentinel.is_file() and sentinel.stat().st_size == 0:
            sentinel.unlink()
    if completed.returncode != 0:
        failure = f"codex sandbox exited {completed.returncode}: {completed.stderr.strip()[-500:]}"
        return PreflightResult(result.allowed, result.refused, result.breaches, result.failures + (failure,))
    return result
