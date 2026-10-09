"""config/run.json, and the Mandu exchange folder and the Waitlist view from config/products.json, validated before a
run starts."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath

from . import schedule
from .boundary import Boundary, ConfigError, canonical, is_within, load_json

RUN_CONFIG = Path("config/run.json")
INSTRUCTIONS = PurePosixPath("src/instructions")
TAG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# The Source and Fit answer of a sign-up the view cannot place; no configured tag or answer may take it.
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Records:
    production_clone: Path
    remote: str
    branch: str
    sync_before_run: bool
    save_after_run: bool
    max_file_bytes: int


@dataclass(frozen=True)
class Settings:
    data: Mapping
    instruction: Path
    weekly: tuple[str, str]
    late_after_minutes: int
    records: Records
    prices: Mapping[str, float]
    outputs: Mapping[str, Mapping]
    not_connected: tuple[Mapping, ...]


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


def instruction_path(repo_root: Path, path: Path) -> Path:
    """The run's task definition must be a reviewed file under src/instructions/, which the agent cannot edit."""
    resolved = canonical(path if path.is_absolute() else repo_root / path)
    if not is_within(resolved, canonical(repo_root / INSTRUCTIONS)) or not resolved.is_file():
        raise ConfigError(f"the instruction must be a file under {INSTRUCTIONS}/; got {path}")
    return resolved


def load(repo_root: Path, env: Mapping[str, str], home: Path) -> Settings:
    data = load_json(repo_root / RUN_CONFIG)
    try:
        weekly = (data["schedule"]["day"], data["schedule"]["time"])
        schedule.weekly(*weekly)
        late = int(data["schedule"]["late_after_minutes"])
        records = data["records"]
        resolved = Records(
            production_clone=resolve_home_path(
                records["production_clone"], "records.production_clone", records.get("env"), env, home
            ),
            remote=str(records["remote"]),
            branch=str(records["branch"]),
            sync_before_run=records["sync_before_run"] is True,
            save_after_run=records["save_after_run"] is True,
            max_file_bytes=int(records["max_file_bytes"]),
        )
        prices = {key: float(value) for key, value in data["cost"]["usd_per_million_tokens"].items()}
        outputs = dict(data["outputs"])
        not_connected = tuple(data.get("sources_not_connected") or ())
        instruction = instruction_path(repo_root, Path(data["instruction"]))
    except (KeyError, TypeError, ValueError, schedule.ScheduleError) as error:
        raise ConfigError(f"{RUN_CONFIG} is incomplete or malformed: {error}") from error
    for source in not_connected:
        for output in source.get("needed_by", ()):
            if output not in outputs:
                raise ConfigError(f"{RUN_CONFIG}: {source.get('name')} feeds unknown output {output}")
    return Settings(data, instruction, weekly, late, resolved, prices, outputs, not_connected)


def exchange_dir(registry: Mapping, boundary: Boundary, env: Mapping[str, str], home: Path) -> Path:
    """Mandu's exchange folder: inside the Mandu checkout unless overridden, and never inside this repository,
    where the agent could write a decision the Founder never made."""
    mandu = registry.get("mandu") or {}
    exchange = mandu.get("exchange")
    if not isinstance(exchange, dict) or exchange.get("access") != "read-only":
        raise ConfigError("the Product registry must name Mandu's exchange folder as read-only")
    override = env.get(exchange.get("env") or "")
    if override:
        path = resolve_home_path(None, "exchange", exchange.get("env"), env, home)
    else:
        relative = PurePosixPath(str(exchange.get("path", "")))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ConfigError("mandu.exchange.path must be relative to the Mandu checkout")
        mandu_path = next(location.path for location in boundary.locations if location.label == "Mandu")
        path = canonical(mandu_path / relative)
    if is_within(path, boundary.repo_root) or is_within(boundary.repo_root, path):
        raise ConfigError(f"the exchange folder {path} overlaps the repository; the agent could write in it")
    return path


@dataclass(frozen=True)
class Waitlist:
    """A Product's Waitlist: where its anonymous view is, if RepToday's build has made one, and how it is counted."""

    product: str
    view: Path | None
    source_tags: tuple[str, ...]
    fit_answers: tuple[str, ...]
    good_fit: tuple[str, ...]
    bar: int
    stale_after: timedelta


def tags(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(set(value)) != len(value):
        raise ConfigError(f"{name} must list distinct values")
    for tag in value:
        if not isinstance(tag, str) or not TAG_PATTERN.fullmatch(tag) or tag == UNKNOWN:
            raise ConfigError(f"{name} holds lowercase-with-hyphens values other than {UNKNOWN!r}")
    return tuple(value)


def sandbox_readable(boundary: Boundary) -> list[Path]:
    """Every place the run's sandbox may read besides the system files a shell needs."""
    system = [Path(entry) for entry in boundary.read_system if not entry.startswith(":")]
    return [boundary.repo_root, *boundary.git_dirs, *(location.path for location in boundary.locations), *system]


def waitlist(registry: Mapping, boundary: Boundary, env: Mapping[str, str], home: Path) -> Waitlist | None:
    """The Waitlist of the one Product that has one, or None.

    Only the launcher reads the view, outside the sandbox, so the agent never sees it (Guardrail G6): a view anywhere
    the sandbox can read would let the agent open it, so such a location stops the run before it starts.
    """
    found = [product for product in registry.get("products", []) if product.get("waitlist")]
    if not found:
        return None
    if len(found) > 1:
        raise ConfigError("only one Product may have a Waitlist until the run reads more than one view")
    product = found[0]
    name = str(product.get("name"))
    try:
        block = product["waitlist"]
        view = block["view"]
        if not isinstance(view, dict) or view.get("access") != "read-only":
            raise ConfigError(f"{name}'s Waitlist view must be declared read-only")
        env_name = view.get("env")
        if not isinstance(env_name, str) or not env_name:
            raise ConfigError(f"{name}'s Waitlist view needs an env override name")
        if env.get(env_name) or view["local_path"] is not None:
            path = resolve_home_path(view["local_path"], f"{name}.waitlist.view.local_path", env_name, env, home)
        else:
            path = None
        source_tags = tags(block["source_tags"], f"{name}.waitlist.source_tags")
        fit_answers = tags(block["fit_answers"], f"{name}.waitlist.fit_answers")
        good_fit = tags(block["good_fit"], f"{name}.waitlist.good_fit")
        bar, hours = block["beta_cohort_bar"], block["stale_after_hours"]
    except (KeyError, TypeError) as error:
        raise ConfigError(f"{name}'s Waitlist in the Product registry is incomplete: {error}") from error
    if not set(good_fit) <= set(fit_answers):
        raise ConfigError(f"{name}.waitlist.good_fit must name answers from fit_answers")
    for value, field in ((bar, "beta_cohort_bar"), (hours, "stale_after_hours")):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ConfigError(f"{name}.waitlist.{field} must be a whole number above zero")
    if path is not None:
        for place in sandbox_readable(boundary):
            if is_within(path, place) or is_within(place, path):
                raise ConfigError(
                    f"{name}'s Waitlist view {path} overlaps {place}, which the sandboxed agent can read;"
                    " it must be outside every location the run reads"
                )
    return Waitlist(name, path, source_tags, fit_answers, good_fit, bar, timedelta(hours=hours))
