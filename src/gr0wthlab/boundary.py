"""Load the runtime configuration and the Product registry, and resolve one run's filesystem boundary.

The boundary is the single source of truth for what a run may read and write.
Every check here fails closed: a configuration that could widen writes, or let the sandbox read the Founder's raw
footage, raises ConfigError, and the launcher refuses to start.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
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
MANDU = "Mandu"
# A footage folder (US-ME09): one per 14-day window, directly inside the footage place, as footage.py reads it. The
# Mac's volume takes a name in any case, so the rule that keeps the sandbox out of them does too.
FOOTAGE_FOLDER = re.compile(r"window-[0-9]+", re.IGNORECASE)
FOOTAGE_PLACE = "footage-place"


class ConfigError(Exception):
    """The configuration cannot be trusted to enforce the boundary."""


@dataclass(frozen=True)
class Location:
    """A read-only checkout named by the Product registry."""

    label: str
    path: Path


@dataclass(frozen=True)
class FootagePlace:
    """Where a Product's raw footage is, once the Founder has set it."""

    product: str
    path: Path | None
    env: str


@dataclass(frozen=True)
class Boundary:
    """One run's boundary. locations are the checkouts the Product registry names; the sandbox reads each Product's
    whole, and of Mandu only package_paths. footage is the footage place, which only the launcher reads."""

    repo_root: Path
    working_directory: Path
    areas: tuple[tuple[str, Path], ...]
    locations: tuple[Location, ...]
    git_dirs: tuple[Path, ...]
    read_system: tuple[str, ...]
    deny: tuple[str, ...]
    package_paths: tuple[Path, ...] = ()
    footage: FootagePlace | None = None

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


def resolve_home_path(raw: object, name: str, env_name: str | None, env: Mapping[str, str], home: Path) -> Path:
    override = env.get(env_name) if env_name else None
    if override:
        if not os.path.isabs(override):
            raise ConfigError(f"{env_name} must be an absolute path")
        return canonical(Path(override))
    if not isinstance(raw, str) or not raw:
        raise ConfigError(f"{name} must be a path")
    if raw.startswith("~/"):
        return canonical(home / raw[2:])
    if os.path.isabs(raw):
        return canonical(Path(raw))
    raise ConfigError(f"{name} must start with ~/ or be absolute")


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


def package_paths(registry: Mapping, mandu: Path) -> tuple[Path, ...]:
    """What a run's sandbox reads of Mandu: each Product's Go-To-Market Package, by the paths the Product registry
    names for it, and nothing else in that checkout. A path that leads out of the checkout, as a link there could,
    stops the run: granting it would hand the sandbox whatever it leads to."""
    named: list[tuple[str, object]] = []
    for product in registry.get("products", []):
        package = product.get("go_to_market_package")
        if not isinstance(package, dict):
            continue
        named += [(str(product.get("name")), package.get(key)) for key in ("path", "launch_checklist")]
        for source in package.get("sources") or ():
            named.append((str(product.get("name")), source.get("path") if isinstance(source, dict) else False))
    paths: list[Path] = []
    for product, relative in named:
        if relative is None:
            continue
        pure = PurePosixPath(relative) if isinstance(relative, str) else None
        if pure is None or not pure.parts or pure.is_absolute() or ".." in pure.parts:
            raise ConfigError(f"{product}'s package path {relative!r} must be relative to the Mandu checkout")
        path = canonical(mandu / pure)
        if path == mandu or not is_within(path, mandu):
            raise ConfigError(
                f"{product}'s package path {relative!r} leads to {path}, which is not inside the Mandu checkout at"
                f" {mandu}"
            )
        if not any(is_within(path, kept) for kept in paths):
            paths = [kept for kept in paths if not is_within(kept, path)] + [path]
    return tuple(paths)


def footage_place(registry: Mapping, env: Mapping[str, str], home: Path) -> FootagePlace | None:
    """The footage place of the one active Product that films, or None when none does; its path stays None until the
    Founder sets it."""
    found = [
        product
        for product in registry.get("products", [])
        if product.get("filming") and product.get("status") == "active"
    ]
    if not found:
        return None
    if len(found) > 1:
        raise ConfigError("only one Product may film until the run plans more than one")
    name = str(found[0].get("name"))
    try:
        where = found[0]["filming"]["footage"]
        if not isinstance(where, dict) or where.get("access") != "read-only":
            raise ConfigError(f"{name}'s footage place must be declared read-only")
        env_name = where.get("env")
        if not isinstance(env_name, str) or not env_name:
            raise ConfigError(f"{name}'s footage place needs an env override name")
        path = None
        if env.get(env_name) or where["local_path"] is not None:
            path = resolve_home_path(where["local_path"], f"{name}.filming.footage.local_path", env_name, env, home)
    except (KeyError, TypeError) as error:
        raise ConfigError(f"{name}'s filming block in the Product registry is incomplete: {error}") from error
    return FootagePlace(name, path, env_name)


def folded(path: Path) -> PurePosixPath:
    """A path as the Mac's volume compares names, without regard to case, so that a place spelled in another case
    than a grant is still seen to be inside it."""
    return PurePosixPath(str(path).casefold())


def holds(root: PurePosixPath, path: PurePosixPath) -> bool:
    return path == root or root in path.parents


def keep_footage_unread(place: FootagePlace, mandu: Path, grants: Sequence[Path]) -> None:
    """Raw footage stays unreadable to the sandboxed agent (US-ME09). This is the one place that rule is kept.

    The footage folders are the window-<n>/ folders directly inside the footage place, and only the launcher reads
    them. The permission profile denies whatever it does not grant, so the sandbox cannot read a footage folder
    exactly when no grant covers one and none lies inside one. grants is every path the profile lets the sandbox
    read, taken from the table Codex is handed (read_grants). A footage place is accepted only when both of these
    hold, and anything else stops the run before it starts:

    - No grant covers the place: a place the sandbox can read is refused, whatever it is.
    - A grant inside the place is part of the Mandu checkout and is in no footage folder. So the place may be the
      folder in Mandu that also holds a Product's package, as the Founder's is; no other place may hold anything the
      sandbox reads.

    The rule is about the profile the launcher builds, which every session of a run is started with. The preflight
    then shows it true of the real sandbox before each session's agent starts, and the boundary check has the agent
    try (codex.run_read_probe, probe.read_steps).
    """
    if place.path is None:
        return
    name, path, checkout = place.product, folded(place.path), folded(mandu)
    for grant in grants:
        granted = folded(grant)
        if holds(granted, path):
            raise ConfigError(
                f"{name}'s footage place {place.path} is inside {grant}, which the sandboxed agent can read, so the"
                " agent could open the raw footage; raw footage lives where the run reads nothing"
            )
        if not holds(path, granted):
            continue
        if not (holds(checkout, path) and holds(checkout, granted)):
            raise ConfigError(
                f"{name}'s footage place {place.path} holds {grant}, which the sandboxed agent can read; only a place"
                " inside the Mandu checkout may hold anything the run reads, beside its footage folders"
            )
        folder = granted.relative_to(path).parts[0]
        if FOOTAGE_FOLDER.fullmatch(folder):
            raise ConfigError(
                f"{name}'s footage place {place.path} is refused: the sandboxed agent can read {grant}, which is in"
                f" its footage folder {folder}/, so the agent could open the raw footage"
            )


def footage_dirs(boundary: Boundary) -> dict[str, Path]:
    """The folders no run's sandbox may read, by a short label, as they are on disk now: the footage place and each
    footage folder in it. One that does not exist yet holds nothing to read and is left out, and a link is never a
    footage folder. Only the names in the place are read here, never a file."""
    place = boundary.footage.path if boundary.footage else None
    if place is None or not os.path.isdir(str(place)):
        return {}
    dirs = {FOOTAGE_PLACE: place}
    try:
        entries = sorted(os.scandir(str(place)), key=lambda entry: entry.name)
    except OSError:
        return dirs
    for entry in entries:
        if FOOTAGE_FOLDER.fullmatch(entry.name) and entry.is_dir(follow_symlinks=False):
            dirs[f"footage-{entry.name}"] = place / entry.name
    return dirs


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

    mandu = next(location.path for location in locations if location.label == MANDU)
    resolved = Boundary(
        repo_root=repo_root,
        working_directory=working_directory,
        areas=areas,
        locations=locations,
        git_dirs=tuple(git if git is not None else git_dirs(repo_root)),
        read_system=read_system,
        deny=deny,
        package_paths=package_paths(registry, mandu),
        footage=footage_place(registry, env, home),
    )
    if resolved.footage is not None:
        keep_footage_unread(resolved.footage, mandu, read_grants(resolved))
    return resolved


def load_boundary(repo_root: Path, env: Mapping[str, str], home: Path) -> tuple[dict, Boundary]:
    config = load_runtime_config(repo_root)
    registry = load_json(repo_root / PRODUCT_REGISTRY)
    return config, resolve_boundary(repo_root, config, registry, env, home)


def read_grants(boundary: Boundary) -> list[Path]:
    """Every path the permission profile lets the sandbox read, taken from the very table Codex is handed, so no
    grant added there escapes the rule on raw footage. What a :token stands for is the system's own and is not among
    them."""
    table = filesystem_policy(boundary)
    return [Path(path) for path, access in table.items() if access != "deny" and not path.startswith(":")]


def filesystem_policy(boundary: Boundary) -> dict[str, str]:
    """The Codex permission-profile filesystem table: everything denied unless granted, writes only in the areas.
    Of Mandu it grants the package paths and nothing else, so the rest of that checkout, the footage folders the
    Founder keeps there among it, is denied with everything else the table does not name."""
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
        if location.label != MANDU:
            policy[str(location.path)] = "read"
    for path in boundary.package_paths:
        policy[str(path)] = "read"
    for path in boundary.area_paths:
        policy[str(path)] = "write"
    return policy
