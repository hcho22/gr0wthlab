"""Load the runtime configuration and the Product registry, and resolve one run's filesystem boundary.

The boundary is the single source of truth for what a run may read and write.
Every check here fails closed: a configuration that could widen writes raises ConfigError,
and the launcher refuses to start.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from . import process

RUNTIME_CONFIG = Path("config/guardrails/runtime.json")
PRODUCT_REGISTRY = Path("config/products.json")

# Guardrail G1's six areas, by their keys in runtime.json's writable_areas.
REQUIRED_AREAS = ("evidence", "drafts", "review_queue", "weekly_reads", "run_reports", "instructions")
WORKSPACE = PurePosixPath("workspace")
# The launcher's own records, outside every area: a run reads them and never writes them.
LEDGER = "ledger"
# The reasoning efforts Codex's model catalog lists for the run's model. Codex passes any other text on, and the model's
# service refuses it only once the agent starts, after everything a run does before its agent.
REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")


class ConfigError(Exception):
    """The configuration cannot be trusted to enforce the boundary."""


@dataclass(frozen=True)
class Location:
    """A read-only checkout named by the Product registry."""

    label: str
    path: Path


@dataclass(frozen=True)
class Boundary:
    repo_root: Path
    working_directory: Path
    areas: tuple[tuple[str, Path], ...]
    locations: tuple[Location, ...]
    git_dirs: tuple[Path, ...]
    read_system: tuple[str, ...]
    deny: tuple[str, ...]

    @property
    def area_paths(self) -> tuple[Path, ...]:
        return tuple(path for _, path in self.areas)

    @property
    def ledger(self) -> Path:
        return self.repo_root / LEDGER


def load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must hold a JSON object")
    return data


def load_runtime_config(repo_root: Path) -> dict:
    config = load_json(repo_root / RUNTIME_CONFIG)
    if config.get("runtime") != "codex":
        raise ConfigError("runtime must be 'codex', the runtime chosen in US-ME02")
    codex = config.get("codex")
    effort = codex.get("reasoning_effort") if isinstance(codex, dict) else None
    if not isinstance(effort, str) or effort not in REASONING_EFFORTS:
        raise ConfigError(
            f"{RUNTIME_CONFIG}: codex.reasoning_effort must be one of {', '.join(REASONING_EFFORTS)}; got {effort!r}"
        )
    return config


def canonical(path: Path) -> Path:
    """Resolve symlinks so the sandbox policy names the paths the kernel checks."""
    return Path(os.path.realpath(str(path)))


def is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def resolve_area(repo_root: Path, key: str, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ConfigError(f"writable area {key} must be a relative path string")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.parent == pure:
        raise ConfigError(f"writable area {key} must be a plain relative path, got {relative!r}")
    if pure.parts[0] != WORKSPACE.name or len(pure.parts) != 2:
        raise ConfigError(f"writable area {key} must be a direct child of workspace/, got {relative!r}")
    path = canonical(repo_root) / pure
    if canonical(path) != path or (path.exists() and not path.is_dir()):
        raise ConfigError(f"writable area {key} at {path} must be a real folder, not a link or a file")
    return path


def resolve_location(label: str, location: Mapping, env: Mapping[str, str], home: Path) -> Location:
    """Apply config/products.json's path_resolution rule to one checkout location."""
    if location.get("access") != "read-only":
        raise ConfigError(f"{label} must be declared read-only in the Product registry")
    env_name = location.get("env")
    override = env.get(env_name) if env_name else None
    if override:
        if not os.path.isabs(override):
            raise ConfigError(f"{env_name} must be an absolute path")
        return Location(label, canonical(Path(override)))
    raw = location.get("local_checkout")
    if not isinstance(raw, str) or not raw:
        raise ConfigError(f"{label} has no local_checkout")
    if raw.startswith("~/"):
        return Location(label, canonical(home / raw[2:]))
    if os.path.isabs(raw):
        return Location(label, canonical(Path(raw)))
    raise ConfigError(f"{label} local_checkout must start with ~/ or be absolute")


def registry_locations(registry: Mapping, env: Mapping[str, str], home: Path) -> list[Location]:
    mandu = registry.get("mandu")
    if not isinstance(mandu, dict):
        raise ConfigError("the Product registry must name Mandu")
    locations = [resolve_location("Mandu", mandu, env, home)]
    for product in registry.get("products", []):
        repository = product.get("repository")
        if repository:
            locations.append(resolve_location(product["name"], repository, env, home))
    return locations


def git_dirs(repo_root: Path) -> list[Path]:
    """The checkout's git directories; a linked worktree keeps them outside the repository root."""
    dirs = []
    for flag in ("--git-dir", "--git-common-dir"):
        command = ["git", "-C", str(repo_root), "rev-parse", "--path-format=absolute", flag]
        try:
            asked = process.run(command, process.QUICK)
        except OSError as error:
            raise ConfigError(f"{repo_root} is not a git checkout: {error}") from error
        if asked.timed_out:
            raise ConfigError(f"git did not answer for {repo_root} within {process.limit_text(asked.limit)}")
        if asked.returncode != 0:
            raise ConfigError(f"{repo_root} is not a git checkout: {' '.join(asked.stderr.split()) or 'no output'}")
        path = canonical(Path(asked.stdout.strip()))
        if path not in dirs:
            dirs.append(path)
    return dirs


def resolve_boundary(
    repo_root: Path,
    config: Mapping,
    registry: Mapping,
    env: Mapping[str, str],
    home: Path,
    git: list[Path] | None = None,
) -> Boundary:
    repo_root = canonical(repo_root)
    areas_config = config.get("writable_areas")
    if not isinstance(areas_config, dict) or tuple(sorted(areas_config)) != tuple(sorted(REQUIRED_AREAS)):
        raise ConfigError(f"writable_areas must name exactly the six G1 areas: {', '.join(REQUIRED_AREAS)}")
    areas = tuple((key, resolve_area(repo_root, key, areas_config[key])) for key in REQUIRED_AREAS)
    if len({path for _, path in areas}) != len(areas):
        raise ConfigError("writable areas must be distinct")

    working_directory = canonical(repo_root / config.get("working_directory", ""))
    if not is_within(working_directory, repo_root):
        raise ConfigError("working_directory must be inside the repository")

    filesystem = config.get("filesystem") or {}
    if filesystem.get("default") != "deny":
        raise ConfigError("filesystem.default must be 'deny'")
    if not filesystem.get("read_repository") or not filesystem.get("read_registry_locations"):
        raise ConfigError("the run must read its repository and every registry location")
    read_system = tuple(filesystem.get("read_system") or ())
    deny = tuple(filesystem.get("deny") or ())
    for entry in read_system + deny:
        if not isinstance(entry, str) or not (entry.startswith(":") or os.path.isabs(entry)):
            raise ConfigError(f"system entries must be :tokens or absolute paths, got {entry!r}")
        if not entry.startswith(":") and any(is_within(path, canonical(Path(entry))) for _, path in areas):
            raise ConfigError(f"system entry {entry} would cover a writable area")

    locations = tuple(registry_locations(registry, env, home))
    for location in locations:
        if is_within(location.path, repo_root) or is_within(repo_root, location.path):
            raise ConfigError(
                f"{location.label} at {location.path} overlaps the repository at {repo_root};"
                " a write area would fall inside it"
            )

    if config.get("network") is not False:
        raise ConfigError(
            "network must be false; a story that needs it adds a Codex network_proxy allow-list in a reviewed change"
        )

    return Boundary(
        repo_root=repo_root,
        working_directory=working_directory,
        areas=areas,
        locations=locations,
        git_dirs=tuple(git if git is not None else git_dirs(repo_root)),
        read_system=read_system,
        deny=deny,
    )


def load_boundary(repo_root: Path, env: Mapping[str, str], home: Path) -> tuple[dict, Boundary]:
    config = load_runtime_config(repo_root)
    registry = load_json(repo_root / PRODUCT_REGISTRY)
    return config, resolve_boundary(repo_root, config, registry, env, home)


def filesystem_policy(boundary: Boundary) -> dict[str, str]:
    """The Codex permission-profile filesystem table: everything denied unless granted, writes only in the areas."""
    policy = {":root": "deny"}
    for entry in boundary.read_system:
        policy[entry] = "read"
    for entry in boundary.deny:
        policy[entry] = "deny"
    policy[str(boundary.repo_root)] = "read"
    for path in boundary.git_dirs:
        if not is_within(path, boundary.repo_root):
            policy[str(path)] = "read"
    for location in boundary.locations:
        policy[str(location.path)] = "read"
    for path in boundary.area_paths:
        policy[str(path)] = "write"
    return policy
