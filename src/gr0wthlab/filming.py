"""The filming workflow (US-ME09): the filming plan the Founder approves before filming, and the finished video cut
from the footage the Founder then drops in the footage place.

Before the agent starts, the launcher reads the shot lists from the kit (shots.py), groups them into the fewest
sittings, and files the filming plan as one Review Queue item under an identifier that never changes. The plan is
never asked again once the Founder decided it, and a new one replaces it only when the kit changes what must be
filmed. The launcher then lists the footage place, read-only, and measures each file, since the agent cannot watch
video: the agent learns each file's name and measured facts from the brief, never the file.

The agent's part is an edit record per calendar day (edits.py): which source ranges of which files make up the day's
video. Once the agent has finished, the launcher checks each record against the shot list, renders it with the text
of the day's post Draft drawn over it (video.py), measures the result, and hands the finished asset to the post-Draft
workflow, which shows it in the day's post item. Nothing is cut from footage of a shot the Founder has not approved a
plan for, a record that fails a check renders nothing, and tooling that is missing is reported as a skipped edit,
never as a failed run. A finished asset lives outside git, in ledger/assets/, and its record in ledger/evidence/
holds everything needed to rebuild it from the footage.

One rule covers the two legs of an A/B pair: when a run ends, their two posts never both show a video unless the two
videos show the same source ranges outside each one's opening. Filming.pair_check keeps it, once per pair, on what the
run is about to leave standing, judging each video by its own record in the ledger.

The plan's shot lists use one beat-sheet shape, a row per shot, adapted from skills/video/references/edit-anatomy.md of
github.com/coreyhaines31/marketingskills at commit 1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff (MIT; see
THIRD_PARTY_NOTICES.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import edits, exchange, footage, posts, shots, video
from .areas import Areas, Store, UnsafeFile, read_plain
from .boundary import Boundary, ConfigError, is_within, load_json
from .lint import Finding
from .queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger
from .settings import resolve_home_path, sandbox_readable
from .state import Tally

KIND = "filming-plan"
ORIGIN = "filming-plan"
ASSETS = "assets"
EVIDENCE = "filming"
EDITS = "edits"
ROLES = ("calendar", "angles", "pairs")

# Where the filming plan stands.
FILED = "filed"
REPLACED = "replaced"
WAITING = "open"
APPROVED_BEFORE = "approved"
DECIDED = "rejected"
NOT_FILED = "not filed"

# What became of one calendar day's edit record.
FINISHED = "finished"
BLOCKED = "blocked"
HELD = "not cut"
WITHHELD = "not offered"
NO_EDIT = "no edit record"
READY = "ready to cut"
SETTLED = "the Founder approved its post with its video, so nothing is cut again and its edit record stays as it is"
KEEPS = "its post keeps the video it shows"

# Where the finished file of a video stands against the digest its record holds.
INTACT = "intact"
GONE = "gone"
CHANGED = "changed"
UNREAD = "unread"
UNRECORDED = "no record"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def listed(numbers: Sequence[object]) -> str:
    """Numbers in a sentence: 2, 4, 6, and 12."""
    words = [str(number) for number in numbers]
    if len(words) < 3:
        return " and ".join(words)
    return f"{', '.join(words[:-1])}, and {words[-1]}"


def shot_names(names: Sequence[str]) -> str:
    return f"{'shot' if len(names) == 1 else 'shots'} {', '.join(names)}"


def record_file(run_id: str) -> str:
    """The name, among the run reports, of a run's record of its filming standing."""
    return f"{run_id}.filming.json"


# The footage place, from the Product registry.


@dataclass(frozen=True)
class Place:
    """Where a Product's raw footage is, once the Founder has set it."""

    product: str
    path: Path | None
    env: str


def place(registry: Mapping, boundary: Boundary, env: Mapping[str, str], home: Path) -> Place | None:
    """The footage place of the one active Product that films, or None when none does.

    Only the launcher reads it, outside the sandbox, so the agent never opens raw footage: a footage place anywhere
    the sandbox can read, which includes this repository, where runs write, stops the run before it starts.
    """
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
    if path is not None:
        for other in sandbox_readable(boundary):
            if is_within(path, other) or is_within(other, path):
                raise ConfigError(
                    f"{name}'s footage place {path} overlaps {other}, which the sandboxed agent can read; raw"
                    " footage lives outside every location the run reads"
                )
    return Place(name, path, env_name)


# The finished file of a video a post names.


@dataclass(frozen=True)
class OnDisk:
    """Where the finished file of a video stands, which is the one answer to whether a post shows or keeps it.

    The launcher never says a post shows or keeps a video unless the finished file is on disk and its fingerprint is
    the digest the video's record and the post's entry hold. Finished files never enter git, so one that is gone or
    changed is said to be exactly that, nothing is substituted, and the video is cut again by the rules that cut any
    video. A file that could not be read is not a file that is gone: nothing is said of it either way, no open post
    changes for it, and the filming output is incomplete with the reason."""

    state: str
    path: str  # the finished file, or the video's record when that is what could not be read; relative to ledger/
    why: str = ""

    @property
    def intact(self) -> bool:
        return self.state == INTACT

    @property
    def unknown(self) -> bool:
        """Whether the file's standing could not be learned, which is never taken for a file that is gone."""
        return self.state in (UNREAD, UNRECORDED)

    def told(self, of: str) -> str:
        """The file's standing in a clause, with the real reason; of says whose video it is."""
        if self.state == UNRECORDED:
            return f"the record `{self.path}`{of} cannot be read or does not name that video"
        standing = {
            INTACT: "is on disk and is the file its record names",
            GONE: "is gone",
            CHANGED: "is no longer the file its record names",
            UNREAD: f"could not be read ({self.why})",
        }[self.state]
        return f"the finished file `{self.path}`{of} {standing}"


def on_disk(store: Store, path: str, sha256: str) -> OnDisk:
    """The one check of a finished file against the digest its record holds, read without following a link. Every
    place that says a post shows or keeps a video it is not cutting asks here, and so does the carry-over."""
    try:
        digest = footage.fingerprint(store.path(path))[0]
    except FileNotFoundError:
        return OnDisk(GONE, path)
    except (ConfigError, OSError) as error:
        return OnDisk(UNREAD, path, getattr(error, "strerror", None) or str(error))
    return OnDisk(INTACT if digest == sha256 else CHANGED, path)


def posted_file(posted: Mapping[str, object] | None, store: Store) -> OnDisk | None:
    """Where the finished file of the video a post's entry names stands, or None for a post that names none: the
    file must be the one both the video's record and the post's entry name."""
    posted = posted or {}
    if not posted.get("asset_sha256"):
        return None
    record = str(posted.get("asset_record") or "")
    try:
        made = read_json(store.path(record)) if record else {}
    except ConfigError:
        made = {}
    path, digest = made.get("asset"), made.get("sha256")
    if not isinstance(path, str) or (path, digest) != (posted.get("asset"), posted["asset_sha256"]):
        return OnDisk(UNRECORDED, record)
    return on_disk(store, path, str(digest))


@dataclass(frozen=True)
class Shown:
    """The video a calendar day's open post names when the launcher last looked: the post, and where the file
    stands. Nothing is looked at or said of the video of a post the Founder approved, which is never asked again."""

    post: str
    file: OnDisk

    def account(self, number: int, due: bool) -> str:
        """What the Founder is told of an open post whose video's finished file is not the file the post names; due
        is whether the day is due this run, since no run cuts a video for a day that is not."""
        said = f"Day {number}'s open post `{self.post}`: " + self.file.told(" of the video it names")
        if self.file.unknown:
            return f"{said}, so nothing is said of whether the post keeps the video, and the post is left as it is"
        # A post the run could ask again without its video gave way to that one; this one stands and is named.
        said += ", so the post is not said to keep the video: nothing is substituted, and "
        if due:
            return f"{said}it is cut again once it can be"
        return f"{said}day {number} is not due this run, so nothing is cut for it and the post stands as it is"


# What the plan and each day's edit come to.


@dataclass
class Standing:
    """Where the filming plan stands in the Review Queue, and which jobs the Founder has approved filming for."""

    status: str
    item: str | None = None
    detail: str = ""
    replaced: str | None = None
    approved: frozenset = frozenset()  # (job key, job digest) of every job an approved plan holds

    @property
    def acted(self) -> bool:
        return self.status in (FILED, REPLACED)

    def account(self) -> str:
        return {
            FILED: f"filed this run as `{self.item}`",
            REPLACED: f"filed as `{self.item}` in place of `{self.replaced}`, as the kit changed what must be filmed",
            WAITING: f"open as `{self.item}`",
            APPROVED_BEFORE: f"approved as `{self.item}`; never asked again",
            DECIDED: f"rejected as `{self.item}`{self.detail}; not asked again until the kit changes what must be"
            " filmed",
            NOT_FILED: f"not filed: {self.detail}",
        }[self.status]


@dataclass
class DayEdit:
    """One due calendar day the plan covers: what its edit must follow, and whether an edit can be cut this run."""

    spec: edits.DaySpec
    ready: bool
    why: str = ""


@dataclass
class Asset:
    """What the launcher made of one calendar day's edit record. The post-Draft workflow reads blocks, finished,
    held, withheld, detail, sha256, entry, and lines; everything else is for the run's own account."""

    day: int
    status: str
    detail: str = ""
    edit: str | None = None  # the edit record, relative to workspace/
    edit_sha256: str | None = None
    blocks: list[Finding] = field(default_factory=list)
    path: str | None = None  # the finished asset, relative to ledger/
    sha256: str | None = None
    bytes: int | None = None
    facts: video.Facts | None = None
    record: str | None = None  # the asset's own record, relative to ledger/
    reused: bool = False
    told: bool = False  # not cut for a reason the run's notice gives the Founder
    cuts: list[dict[str, object]] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    parsed: edits.Edit | None = None
    opening: list[list[float]] = field(default_factory=list)  # where its Draft puts a re-cut leg's opening
    dropped: bool = False  # its day's open post gives way to one with no video, as the video's finished file is lost

    @property
    def finished(self) -> bool:
        return self.status == FINISHED

    @property
    def held(self) -> bool:
        """An edit record that could not be cut this run for a reason outside it, such as missing tooling."""
        return self.status == HELD

    @property
    def withheld(self) -> bool:
        """A video that was cut and is not offered, since it and the video of its pair's other leg differ."""
        return self.status == WITHHELD

    def shows(self, clips: Mapping[str, edits.Clip]) -> dict[str, object]:
        """What a video cut from this record shows, as far as its record in the ledger tells the pair check: each
        cut with the fingerprint of the file it is made from, and where the opening is."""
        cuts = [dict(segment.as_json(), sha256=clips[segment.source].sha256) for segment in self.parsed.segments]
        return {"day": self.day, "opening": self.opening, "cuts": cuts}

    def entry(self) -> dict[str, object]:
        """What a post's Review Queue entry keeps of its video."""
        if not self.finished:
            return {}
        return {
            "asset": self.path,
            "asset_sha256": self.sha256,
            "asset_record": self.record,
            "edit": self.edit,
            "edit_sha256": self.edit_sha256,
        }

    def lines(self) -> list[str]:
        """The post item's account of its video file."""
        if not self.finished:
            why = self.detail.rstrip(".") or "its footage is not edited yet"
            return [
                f"**Video file**: none yet ({why}). Approving this item approves its copy and its beat plan; the"
                " finished video comes back with this copy for approval."
            ]
        facts = self.facts
        sound = "with sound" if facts.sound else "no sound"
        lines = [
            "**Video file**",
            "",
            f"- `{self.path}`, under gr0wthlab's `ledger/`: {facts.duration:.2f}s, {facts.shape()},"
            f" {facts.fps:g} frames a second, {sound}. SHA-256 `{self.sha256}`.",
            f"- Cut by `{self.edit}` from the Founder's footage; nothing in it is generated:",
            "",
            "| Time | Shot | Footage file | From | To | Speed |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for cut in self.cuts:
            speed = "as recorded" if cut["speed"] == 1 else f"{cut['speed']:g}x"
            lines.append(
                f"| {cut['at']:g}-{cut['until']:g}s | {cut['shot']} | `{cut['source']}` | {cut['in']:g}s"
                f" | {cut['out']:g}s | {speed} |"
            )
        lines += ["", "- Checked: " + "; ".join(self.checks) + "."]
        lines.append(f"- Everything needed to rebuild it from the footage: `{self.record}`.")
        return lines

    def summary(self) -> dict[str, object]:
        return {
            "day": self.day,
            "status": self.status,
            "detail": self.detail,
            "edit": self.edit,
            "edit_sha256": self.edit_sha256,
            "blocks": [finding.__dict__ for finding in self.blocks],
            "asset": self.path,
            "asset_sha256": self.sha256,
            "bytes": self.bytes,
            "facts": self.facts.as_json() if self.facts else None,
            "asset_record": self.record,
            "reused": self.reused,
            "checks": self.checks,
        }


@dataclass
class Filming:
    """Everything a run knows about filming: the plan, the footage, and each due day's edit."""

    product: str
    window: int
    run: str
    place: Place
    canvas: video.Canvas | None
    tooling: video.Tooling
    standing: Standing
    inventory: footage.Inventory
    drafts: Path  # workspace/drafts/posts/window-<n>/
    edits: Path  # workspace/drafts/edits/window-<n>/
    requirements: shots.Requirements = field(default_factory=shots.Requirements)
    paths: dict[str, str] = field(default_factory=dict)  # kit role: its Mandu-relative path
    days: dict[int, DayEdit] = field(default_factory=dict)
    unplanned: dict[int, str] = field(default_factory=dict)
    posted: dict[int, dict[str, object]] = field(default_factory=dict)  # each calendar day's standing post
    due: dict[int, bool] = field(default_factory=dict)  # each due day: whether its video is already approved
    approved: dict[int, dict[str, object]] = field(default_factory=dict)  # each due day's approved post, if any
    rejected: dict[int, list[dict[str, object]]] = field(default_factory=dict)  # each due day's rejected posts
    problem: str = ""  # why nothing could be planned this run
    calendar_lines: list[int] = field(default_factory=list)  # the calendar rows the plan read
    screen_rule: shots.ScreenRule | None = None
    results: dict[int, Asset] = field(default_factory=dict)
    record: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)  # what the video tooling runs with
    apart: list[str] = field(default_factory=list)  # each pair whose two videos differ, as the Founder is told
    videos: dict[int, Shown] = field(default_factory=dict)  # each day whose open post names a video, as last looked at
    dropped: dict[int, str] = field(default_factory=dict)  # each day whose open post lost its video: that post
    replaced: list[str] = field(default_factory=list)  # each such post that left the queue, as the Founder is told

    def edit_path(self, number: int) -> Path:
        return self.edits / f"day-{number:02d}.json"

    def draft_path(self, number: int) -> Path:
        return self.drafts / f"day-{number:02d}.md"

    def sittings(self) -> list[shots.Sitting]:
        return shots.sittings(self.requirements)

    # After the agent: what the post-Draft workflow asks.

    def wanted(self, number: int) -> bool:
        """Whether a day has an edit record, so its video can be offered even after its copy was approved."""
        path = self.edit_path(number)
        return path.exists() or path.is_symlink()

    def examine(self, number: int, areas: Areas, draft: posts.PostDraft | None = None) -> Asset:
        """Every check one day's edit record has on its own that needs no tooling, as the launcher and check-edits
        both run them; an Asset that is READY passed them all. Whether it shows the same footage as its pair's other
        leg is not one of them: that is judged on the two videos (pair_check)."""
        day = self.days.get(number)
        path = self.edit_path(number)
        relative = areas.relative(path)
        if day is None:
            why = self.unplanned.get(number) or f"the filming plan does not cover day {number}"
            return Asset(
                number, HELD if self.wanted(number) else NO_EDIT, why, relative if self.wanted(number) else None
            )
        if self.due.get(number):
            return Asset(number, HELD, day.why)
        edit, problem = read_edit(areas, path)
        if edit is None and not problem:
            return Asset(number, NO_EDIT, day.why if not day.ready else "it is ready for an edit record and has none")
        if edit is None:
            return Asset(number, BLOCKED, problem, relative, blocks=[Finding("edit-format", "", problem)])
        asset = Asset(number, BLOCKED, "", edit.path, edit.sha256, parsed=edit)
        if not day.ready:
            asset.status, asset.detail = HELD, day.why
            return asset
        if draft is None:
            draft, problem = posts.read_draft(areas, self.draft_path(number))
            if draft is None or draft.problems:
                asset.status = HELD
                asset.detail = (
                    problem or f"day {number} has no post Draft that can be read, and its text is drawn from it"
                )
                return asset
        asset.blocks = edits.check(edit, day.spec, self.inventory.clips, draft, self.canvas)
        asset.checks = [
            f"{shot.id}, which may not be cut, is one unbroken source range" for shot in day.spec.shots if shot.uncut
        ]
        if all(segment.speed == 1 for segment in edit.segments):
            asset.checks.append("every cut plays at the speed it was recorded at")
        if not asset.blocks:
            asset.opening = [list(window) for window in edits.opening_windows(draft, day.spec.hooks)]
            asset.status = READY
        return asset

    def finish(self, drafts: Mapping[int, posts.PostDraft], areas: Areas, store: Store, now: datetime) -> None:
        """Turn the edit record of each day whose Draft passed into a finished asset when it passes every check:
        render it with the Draft's text drawn over it, measure it, and keep it only if it measures as the canvas
        asks. A failure outside the edit record (the tooling, footage that changed while the run worked, a file that
        could not be written) holds the day, as missing tooling does, and the run's notice says why."""
        for number in sorted(drafts):
            asset = self.results[number] = self.examine(number, areas, drafts[number])
            if asset.status != READY:
                continue
            try:
                self.cut(asset, drafts[number], store, now)
            except video.VideoError as error:
                asset.status, asset.detail, asset.told = HELD, str(error), True
            except OSError as error:
                where = f" `{error.filename}`" if error.filename else ""
                asset.status, asset.told = HELD, True
                asset.detail = (
                    f"a file could not be read or written while it was cut ({error.strerror or error}{where})"
                )

    def leave(self, changed: Mapping[int, Asset | None], store: Store) -> None:
        """The pair check of a run, once the post-Draft workflow knows what it is about to queue and before it queues
        anything: changed holds each day whose post is about to change, with the video the post is about to show,
        the one this run cut for it or the one its post showed carried over, or None when it is about to show
        none."""
        fresh = {
            number: read_json(store.path(asset.record)) if asset is not None else None
            for number, asset in changed.items()
        }
        self.pair_check(fresh, changed, store)

    def carry(self, held: Asset, store: Store) -> Asset | None:
        """The video a day's standing post shows, as a finished asset the post that replaces it can show again, for
        a day whose video could not be cut again this run, which held says why; None when the finished file is gone
        or is no longer the file its record and its post name."""
        posted, made = self.posted.get(held.day) or {}, self.standing_video(held.day, store)
        file = posted_file(posted, store)
        if file is None or not file.intact:
            return None
        try:
            asset = Asset(
                held.day,
                FINISHED,
                held.detail,
                made["edit"]["path"],
                made["edit"]["sha256"],
                path=made["asset"],
                sha256=made["sha256"],
                bytes=made["bytes"],
                facts=video.Facts.from_json(made["facts"]),
                record=str(posted["asset_record"]),
                reused=True,
                checks=list(made["checks"]),
                opening=made["opening"],
            )
            clock = 0.0
            for cut in made["cuts"]:
                segment = edits.Segment(cut["shot"], cut["source"], cut["in"], cut["out"], cut["speed"])
                asset.cuts.append(dict(segment.as_json(), at=round(clock, 3), until=round(clock + segment.length, 3)))
                clock += segment.length
        except (ConfigError, OSError, KeyError, TypeError, ValueError):
            return None
        return asset

    def preview(self, areas: Areas, store: Store) -> None:
        """Each due day's edit record as check-edits sees it before anything is cut: its own checks, then the pair
        check on the videos a run that ended now would leave. A record that passes would be cut into a video for its
        day's post, unless that video would show, cut for cut, what the video of the day's standing post shows,
        which then stands."""
        fresh = {}
        self.look(store)
        for number in sorted(self.days):
            asset = self.results[number] = self.examine(number, areas)
            if asset.status != READY:
                continue
            would, standing = asset.shows(self.inventory.clips), self.standing_video(number, store)
            try:
                stands = (edits.footage(standing), standing["opening"]) == (edits.footage(would), would["opening"])
            except (KeyError, TypeError):
                stands = False
            if not stands:
                fresh[number] = would
        self.pair_check(fresh, self.results, store)

    def pair_check(self, fresh: Mapping[int, Mapping | None], assets: Mapping[int, Asset | None], store: Store) -> None:
        """The one rule of an A/B pair's videos: when a run ends, the two posts of a pair never both show a video
        unless the two videos show the same source ranges outside each one's opening.

        Checked once per pair, on what the run is about to leave standing. fresh holds each day whose post the run is
        about to change, with the record of the video the post is about to show, or None when it is about to show
        none, and assets what the launcher made of that video, where the outcome is written; any other day keeps the
        video its standing post shows. Each video is judged by its own record in the ledger, which holds each cut
        with the fingerprint of the file it was made from and where the opening is, never by the files in place or
        by their names.

        When the two videos differ, nothing the run changed for the pair is offered, so what stood before stays, and
        the run report and the notice name the pair and say why. A leg's checks say it shows the same source ranges
        as its other leg only when the two were compared here and matched."""
        for number in sorted(fresh):
            day = self.days.get(number)
            other = day.spec.other if day is not None else None
            if fresh[number] is None or other is None or (fresh.get(other) is not None and other < number):
                continue
            theirs = fresh[other] if other in fresh else self.standing_video(other, store)
            cut = [leg for leg in (number, other) if fresh.get(leg) is not None]
            if theirs is None:
                assets[number].checks.append(f"day {other}, its pair's other leg, has no video to compare with yet")
                continue
            try:
                differ = edits.unlike(fresh[number], theirs)
            except (KeyError, TypeError, ValueError):
                differ = None
            if differ == "":
                where = "after the re-cut opening" if day.spec.recut else "from the first frame to the last"
                for leg in cut:
                    assets[leg].checks.append(f"the same source ranges as day {number + other - leg}'s leg {where}")
                continue
            where = "after each one's opening" if day.spec.recut else "from the first frame to the last"
            said = (
                f"do not show the same footage {where} ({differ})"
                if differ
                else "could not be compared, since the ledger's record of one of them does not say what footage it"
                " shows"
            )
            names = {
                leg: f"the video cut for day {leg}"
                if leg in cut
                else f"the video in day {leg}'s post `{self.posted[leg]['id']}`"
                for leg in (number, other)
            }
            for leg in cut:
                asset = assets[leg]
                asset.status, asset.detail = WITHHELD, f"the video cut for it and {names[number + other - leg]} {said}"
            first, second = sorted((number, other))
            self.apart.append(
                f"Pair {day.spec.pair}, days {first} and {second}: {names[first]} and {names[second]} {said}. Nothing"
                " this run changed for either day is offered, and what stood before stays."
            )

    def standing_video(self, number: int, store: Store) -> dict | None:
        """The record of the video a day's standing post shows, or None when it shows none."""
        record = (self.posted.get(number) or {}).get("asset_record")
        return read_json(store.path(str(record))) if record else None

    def file(self, number: int, store: Store) -> OnDisk | None:
        """Where the finished file of the video a day's standing post names stands now, or None when it names none."""
        return posted_file(self.posted.get(number), store)

    def look(self, store: Store) -> None:
        """Note where the finished file of every open post's video stands, before anything is said of one. A post
        the Founder approved is never asked again, so its file is not read and nothing is said of it."""
        self.videos = {}
        for number, posted in self.posted.items():
            file = self.file(number, store) if posted.get("status") == OPEN else None
            if file is not None:
                self.videos[number] = Shown(str(posted["id"]), file)

    def waits(self, number: int) -> bool:
        """Whether a day that cannot be cut this run has an open post that names a video. The day's edit record stays
        as it is until the video can be cut again, so nothing the agent is shown may ask it to change or remove that
        record; whether the post keeps the video meanwhile is what kept says."""
        day, posted = self.days.get(number), self.posted.get(number) or {}
        shows = posted.get("status") == OPEN and bool(posted.get("asset_sha256"))
        return day is not None and not day.ready and not self.due.get(number) and shows

    def keeps(self, number: int) -> bool:
        """Whether a day's post names a video when the run ends though the Founder has not approved one for it, so
        that a video that could not be cut for it this run is never said to be none; what the run may say of that
        video is what kept says."""
        return number in self.videos and not self.due.get(number)

    def intact(self, number: int) -> bool:
        """Whether the launcher may say a day's post shows or keeps the video it names: only when it looked, and
        the finished file is on disk and is the file the video's record and the post's entry name."""
        return number in self.videos and self.videos[number].file.intact

    def kept(self, number: int) -> str:
        """What is said of the video a day's post names when it is not cut this run: that the post keeps it, only
        when its finished file is intact, and otherwise where that file stands, with the real reason."""
        if self.intact(number):
            return KEEPS
        shown = self.videos.get(number)
        if shown is None:
            return "the finished file of the video its post names was not looked at, so nothing is said of it"
        said = shown.file.told(" of the video its post names")
        if shown.file.unknown:
            return f"{said}, so nothing is said of whether the post keeps it, and the post is left as it is"
        return f"{said}, so the post is not said to keep it: nothing is substituted, and it is cut again once it can be"

    def lost(self) -> list[str]:
        """Each open post whose video's finished file is not the file the post names, as the Founder is told."""
        return [
            shown.account(number, number in self.due)
            for number, shown in sorted(self.videos.items())
            if not shown.file.intact
        ]

    def drop(self, held: Asset, file: OnDisk) -> None:
        """Account for a day whose open post names a video it no longer has: the finished file is gone or changed,
        and the video could not be cut again this run, which held says why. The post-Draft workflow then queues the
        same post in its place without a video, and held's reason, with where the file stands, is what that post,
        the report, and the notice give."""
        post = str(self.posted[held.day]["id"])
        held.detail = f"{held.detail}, and {file.told(f' of the video `{post}` named')}"
        held.dropped = True
        self.dropped[held.day] = post

    def hold(self, number: int, why: str) -> None:
        """Account for a day the post-Draft workflow asked no video of for a reason the Founder must be told."""
        self.results[number] = Asset(number, HELD, why, told=True)

    def settle(self, outcome: posts.Outcome | None, store: Store) -> None:
        """Account for each due day the post-Draft workflow did not ask a video of, so the report names every day.
        A video is cut only from a Draft that passes, so a day with an edit record and no video gets the reason
        its post got; outcome is None when the Drafts could not be taken in at all.

        It also notes which days' posts name a video when the run ends, and where each one's finished file stands
        then, so that the report and the notice never say a day has no video while its post names one, and never say
        a post keeps a video whose file is not there: the post queued for the day when it has a video, and otherwise
        the post that stood, unless the run withdrew it."""
        taken = {result.day: result for result in outcome.results} if outcome else {}
        self.look(store)
        for number, result in taken.items():
            if result.status == posts.QUEUED:
                asset = result.asset if result.asset is not None and result.asset.finished else None
                self.videos.pop(number, None)
                if asset is not None:
                    file = on_disk(store, asset.path, asset.sha256)
                    self.videos[number] = Shown(str(result.item), file)
            elif result.withdrawn:
                self.videos.pop(number, None)
        for number, post in sorted(self.dropped.items()):
            result, why = taken.get(number), self.results[number].detail
            later = "the video comes back for approval once it is cut again"
            if result is None:
                continue
            if result.status == posts.QUEUED:
                self.replaced.append(
                    f"Day {number}'s post `{post}` gave way to `{result.item}`, which shows no video: {why}."
                    f" Approving it approves the copy alone, and {later}."
                )
            elif result.withdrawn == post:
                self.replaced.append(
                    f"Day {number}'s post `{post}` left the queue: {why}. Nothing is asked in its place, since the"
                    f" Founder already decided this day's copy, and {later}."
                )
        for number, day in self.days.items():
            result = taken.get(number)
            if number in self.results:
                continue
            exists = self.wanted(number)
            if not exists or self.due.get(number):
                why = day.why if not day.ready else "it is ready for an edit record and has none"
            else:
                if result is None:
                    why = "the post Drafts were not taken in this run"
                elif result.status == posts.BLOCKED and not result.detail:
                    why = "its post Draft did not pass its checks"
                else:
                    why = f"its post Draft was not checked ({result.detail})"
                why += ", and a video is cut only from a Draft that passes"
            self.results[number] = Asset(number, HELD if exists else NO_EDIT, why)

    def cut(self, asset: Asset, draft: posts.PostDraft, store: Store, now: datetime) -> None:
        env = self.env
        edit = asset.parsed
        clips = [self.inventory.clips[segment.source] for segment in edit.segments]
        for clip in {clip.name: clip for clip in clips}.values():
            if footage.fingerprint(self.inventory.path(clip))[0] != clip.sha256:
                raise video.VideoError(
                    f"`{clip.name}` changed while the run was working, so nothing was cut from it; the next run"
                    " measures it again"
                )
        overlays = edits.overlays(draft)
        cuts = [
            video.Cut(self.inventory.path(clip), segment.start, segment.end, segment.speed, clip.facts)
            for segment, clip in zip(edit.segments, clips)
        ]
        made = {
            "tooling": self.tooling.version,
            "encoding": [*video.VIDEO_CODEC, *video.SOUND_CODEC, *video.REPEATABLE],
            "canvas": self.canvas.as_json(),
            "overlays": [overlay.__dict__ for overlay in overlays],
            "opening": asset.opening,
            "cuts": [
                dict(segment.as_json(), sha256=clip.sha256, bytes=clip.bytes, facts=clip.facts.as_json())
                for segment, clip in zip(edit.segments, clips)
            ],
        }
        recipe = hashlib.sha256(json.dumps(made, sort_keys=True).encode("utf-8")).hexdigest()
        stem = f"day-{asset.day:02d}-{recipe[:12]}"
        target = store.path(ASSETS, f"window-{self.window}", f"{stem}.mp4")
        record = store.path("evidence", EVIDENCE, ASSETS, f"window-{self.window}-{stem}.json")
        known = read_json(record)
        asset.reused = bool(known) and target.is_file() and footage.fingerprint(target)[0] == known.get("sha256")
        if asset.reused:
            facts, problems = video.probe(self.tooling, target, env), []
        else:
            facts, problems = produce(self.tooling, self.canvas, cuts, overlays, target, env)
        if problems:
            asset.status = BLOCKED
            asset.blocks = [
                Finding("asset-shape", "", f"the rendered asset was not kept: {problem}") for problem in problems
            ]
            return
        asset.sha256, asset.bytes = footage.fingerprint(target)
        asset.path, asset.record, asset.facts = store.relative(target), store.relative(record), facts
        clock = 0.0
        for segment in edit.segments:
            asset.cuts.append(dict(segment.as_json(), at=round(clock, 3), until=round(clock + segment.length, 3)))
            clock += segment.length
        asset.checks.insert(0, f"measured {facts.shape()} at {facts.fps:g} frames a second")
        asset.status = FINISHED
        if not known or known.get("sha256") != asset.sha256:
            store.write_json(
                record,
                dict(
                    made,
                    asset=asset.path,
                    sha256=asset.sha256,
                    bytes=asset.bytes,
                    facts=facts.as_json(),
                    recipe=recipe,
                    product=self.product,
                    window=self.window,
                    day=asset.day,
                    made_by_run=self.run,
                    made_at=now.isoformat(),
                    edit={"path": edit.path, "sha256": edit.sha256, "record": edit.as_json()},
                    draft={"path": draft.path, "sha256": draft.sha256},
                    checks=asset.checks,
                    rebuild=f"src/bin/gr0wthlab rebuild-asset {asset.record}",
                ),
            )

    # The record check-edits reads.

    def as_record(self) -> dict[str, object]:
        """What the launcher fixed for this run's edits before the agent started: the footage it measured, each due
        day's shot list and whether an edit can be cut, and where each day's post stands."""
        inventory = self.inventory
        return {
            "run": self.run,
            "product": self.product,
            "window": self.window,
            "plan": {"status": self.standing.status, "item": self.standing.item},
            "problem": self.problem,
            "tooling": self.tooling.as_json(),
            "canvas": self.canvas.as_json() if self.canvas else None,
            "footage": {
                "place": str(inventory.place) if inventory.place else None,
                "folder": inventory.folder,
                "status": inventory.status,
                "detail": inventory.detail,
                "clips": [clip.as_json() for clip in inventory.clips.values()],
                "ignored": [list(entry) for entry in inventory.ignored],
            },
            "days": {
                str(number): {"spec": day.spec.as_json(), "ready": day.ready, "why": day.why}
                for number, day in self.days.items()
            },
            "unplanned": {str(number): why for number, why in self.unplanned.items()},
            "posted": {str(number): post for number, post in self.posted.items()},
            "due": {str(number): approved for number, approved in self.due.items()},
            "approved": {str(number): post for number, post in self.approved.items()},
            "rejected": {str(number): entries for number, entries in self.rejected.items()},
            "drafts": str(self.drafts),
            "edits": str(self.edits),
        }


class RecordError(ValueError):
    """A record that does not hold a run's filming standing."""


def from_record(data: object) -> Filming:
    """A run's filming standing as the launcher recorded it, for check-edits; the footage itself is never needed."""
    try:
        held = data["footage"]
        inventory = footage.Inventory(
            Path(held["place"]) if held["place"] else None,
            str(held["folder"]),
            str(held["status"]),
            str(held["detail"]),
            {clip["name"]: edits.Clip.from_json(clip) for clip in held["clips"]},
            [tuple(entry) for entry in held["ignored"]],
        )
        canvas = data["canvas"]
        tooling = data["tooling"]
        return Filming(
            str(data["product"]),
            int(data["window"]),
            str(data["run"]),
            Place(str(data["product"]), inventory.place, ""),
            video.Canvas(**dict(canvas, font=Path(canvas["font"]))) if canvas else None,
            video.Tooling(
                None, None, str(tooling["version"]), str(tooling["problem"]), tooling["converts_hdr"] is True
            ),
            Standing(str(data["plan"]["status"]), data["plan"]["item"]),
            inventory,
            Path(data["drafts"]),
            Path(data["edits"]),
            days={
                int(number): DayEdit(edits.DaySpec.from_json(day["spec"]), day["ready"] is True, str(day["why"]))
                for number, day in data["days"].items()
            },
            unplanned={int(number): str(why) for number, why in data["unplanned"].items()},
            posted={int(number): dict(post) for number, post in data["posted"].items()},
            due={int(number): approved is True for number, approved in data["due"].items()},
            approved={int(number): dict(post) for number, post in data["approved"].items()},
            rejected={int(number): [dict(entry) for entry in entries] for number, entries in data["rejected"].items()},
            problem=str(data["problem"]),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise RecordError(f"it does not hold a run's filming standing ({type(error).__name__}: {error})") from error


def read_json(path: Path) -> dict:
    """One of the launcher's own JSON records, or {} when there is none that can be read."""
    try:
        data = json.loads(read_plain(path).decode("utf-8"))
    except (UnsafeFile, OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_edit(areas: Areas, path: Path) -> tuple[edits.Edit | None, str]:
    """An edit record the agent wrote, read without following links; None with the reason when there is none."""
    if not path.exists() and not path.is_symlink():
        return None, ""
    folder = areas.check(path.parent)
    if not areas.real_folder(folder):
        return None, f"`{areas.relative(folder)}` is not a real folder, so its edit records were not read"
    try:
        text = read_plain(path).decode("utf-8")
    except (UnsafeFile, OSError, UnicodeDecodeError) as error:
        return None, f"`{areas.relative(path)}` could not be read ({error})"
    return edits.parse(text, areas.relative(path)), ""


def produce(
    tooling: video.Tooling,
    canvas: video.Canvas,
    cuts: Sequence[video.Cut],
    overlays: Sequence[video.Overlay],
    target: Path,
    env: Mapping[str, str],
    sha256: str | None = None,
) -> tuple[video.Facts, list[str]]:
    """Render an asset beside where it belongs, measure it there, and move it into place only if it measures as the
    canvas asks and, when sha256 names the file it must be, is byte for byte that file. Returns what was measured
    and why the render was not kept; whatever was at target is as it was unless the render took its place."""
    unchecked = target.with_name(f".{target.name}.unchecked")
    try:
        video.render(tooling, canvas, cuts, overlays, unchecked, env)
        facts = video.probe(tooling, unchecked, env)
        problems = video.verify(facts, canvas, sum(cut.length for cut in cuts))
        digest = footage.fingerprint(unchecked)[0]
        if sha256 not in (None, digest):
            problems.append(f"its SHA-256 is {digest}, not the {sha256} its record names")
        if not problems:
            os.replace(str(unchecked), str(target))
    finally:
        unchecked.unlink(missing_ok=True)
    return facts, problems


# Before the agent.


def device(shot: shots.Shot, product: str) -> str:
    if shot.setup == shots.DEVICE:
        real = "real device" if shot.real_device else "device"
        return f"The {real} running {product}, screen recording"
    if shot.setup == shots.CAMERA:
        return "Camera, the Founder in frame" if shot.kind == shots.FOUNDER_ON_CAMERA else "Camera"
    return "Not stated"


def real_time(shot: shots.Shot) -> str:
    if shot.real_time is None:
        return "Not stated"
    return "Yes" if shot.real_time else f"No: {shot.kind}"


def span(length: tuple[int, int] | None) -> str:
    if length is None:
        return "not stated"
    return f"{length[0]}s" if length[0] == length[1] else f"{length[0]}-{length[1]}s"


def plan_item(filming: Filming, previous: Mapping[str, object] | None = None) -> exchange.Item:
    """The filming plan as one Review Queue item: the sittings, then one beat sheet per asset, each quoting only
    the kit text it uses."""
    found, product, window = filming.requirements, filming.product, filming.window
    roles, canvas = filming.paths, filming.canvas
    groups = filming.sittings()
    days = sorted(day for job in found.jobs for day in job.days)
    reuse = found.reuse_days()
    many = len(reuse) > 1
    body = [
        f"{product} window {window} needs footage for {plural(len(found.jobs), 'asset')}, filmed in"
        f" {plural(len(groups), 'sitting')}, for calendar {'days' if len(days) > 1 else 'day'} {listed(days)}."
        + (
            f" {'Days' if many else 'Day'} {listed(reuse)} {'are' if many else 'is'} cut from an earlier day's"
            f" footage with only the opening changed, so {'they add' if many else 'it adds'} no shot of"
            f" {'their' if many else 'its'} own to film; any opening take a leg records for itself is named with its"
            " shot list below."
            if reuse
            else ""
        ),
        "No video is cut from a shot's footage until a plan that holds the shot is approved.",
    ]
    if previous is not None:
        before = previous.get("filming_jobs") or {}
        now = found.digests()
        changed = [key for key in now if key in before and before[key] != now[key]]
        new = [key for key in now if key not in before]
        gone = [key for key in before if key not in now]
        parts = [
            f"{', '.join(keys)} {word}" for keys, word in ((changed, "changed"), (new, "new"), (gone, "gone")) if keys
        ]
        decided = f", which you {previous['status']}" if previous["status"] in (APPROVED, REJECTED) else ""
        body.append(
            f"This plan replaces `{previous['id']}`{decided}, because the kit changed what must be filmed:"
            f" {'; '.join(parts) or 'the sittings'}."
        )
    body += ["", "**Before you film**", ""]
    if canvas is not None:
        body.append(
            f"- Every asset is finished at {canvas.shape}, so film upright. Text is drawn {canvas.top} pixels from"
            f" the top and {canvas.bottom} from the bottom, so keep what matters between them. A recording of"
            " another shape is shown whole, with black beside it, and never cropped."
        )
    body += [
        f"- Drop each file in the footage place's `window-{window}/` folder, named for its shot, such as"
        " `d01-s1.mov`, or `d01-s1-take-2.mov` for another take; `docs/operations.md` has the rest.",
        "- On-screen text and captions are never filmed: the edit draws them from each day's post Draft, whose"
        " Video table is that day's script.",
        "- Sound is not chosen in the edit: a cut that plays at the speed it was recorded at keeps its recording's"
        " sound, and a cut that plays at another speed, such as a timelapse, is silent.",
        "- Nothing is generated or substituted: a shot with no file has no video.",
    ]
    for sitting in groups:
        served = sitting.days()
        body += [
            "",
            f"**Sitting {sitting.number}: {sitting.label.lower()}**, for {'days' if len(served) > 1 else 'day'}"
            f" {listed(served)}",
            "",
            "| Shot | For | Time | What to record | Device | Real time | On-screen text | Caption | May not be cut |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for job, shot in sitting.shots:
            time = span(job.length) if len(job.shots) == 1 else f"part of {span(job.length)}"
            text = "The Hook, then the Draft's" if shot.number == 1 else "The Draft's"
            caption = "The spoken lines" if shot.kind == shots.FOUNDER_ON_CAMERA else "None unless a line is spoken"
            body.append(
                f"| {shot.id} | {'days' if len(job.days) > 1 else 'day'} {listed(job.days)} | {time}"
                f" | {posts.cell(shot.what)} | {device(shot, product)} | {real_time(shot)} | {text} | {caption}"
                f" | {'Yes' if shot.uncut else 'Not stated'} |"
            )
    names = {role: Path(path).name for role, path in roles.items()}
    body += ["", "**Where each shot list comes from, and what each day opens on**", ""]
    for job in found.jobs:
        pair = f", {job.pair}" + (", opening re-cut" if job.recut else "") if job.pair else ""
        line = (
            f"- {job.key}, {'days' if len(job.days) > 1 else 'day'} {listed(job.days)} ({job.angle}{pair}): Format in"
            f" `{names['angles']}` line {job.line}."
        )
        for hook in job.hooks:
            line += f' Day {hook.day} opens on "{hook.text}" (`{names[hook.source]}` line {hook.line}).'
        if job.recut and len(job.hooks) > 1:
            first = job.shots[0].id
            legs = [hook for hook in job.hooks if hook.leg]
            takes = " and ".join(f"`{edits.own_take(first, hook.leg)}` for day {hook.day}" for hook in legs)
            line += f" Each leg opens on its own Hook, so record the opening once for each: name the takes {takes}."
            if any(edits.own_opening(job.shots, hook.leg, job.recut) for hook in legs):
                line += " The Founder is on camera in it, so a leg has no video until its own take is there."
            line += (
                " Everything after the opening is shared by both legs: record it once, in a take named without a"
                f" leg letter, such as `{first}.mov`."
            )
        body.append(line)
    for number, why in found.unplanned:
        body.append("")
        body.append(f"Not planned: day {number}, since {why}.")
    touches = [
        f"- The filming of {product} window {window}: shot lists {', '.join(sorted(found.digests()))}",
        "- The raw footage place set in `config/products.json`, which gr0wthlab only ever reads",
    ]
    rows = sorted(filming.calendar_lines)
    formats = sorted({job.line for job in found.jobs})
    evidence = [
        f"- The calendar's days, their Angles and pair legs: `{roles['calendar']}` lines {rows[0]}-{rows[-1]}"
        if rows
        else f"- The calendar: `{roles['calendar']}`",
        f"- Each Angle's Format, quoted in the shot lists: `{roles['angles']}`"
        f" {'lines' if len(formats) > 1 else 'line'} {listed(formats)}",
        f"- Each pair's legs and frozen Hooks: `{roles['pairs']}`",
    ]
    rule = filming.screen_rule
    if rule is not None:
        evidence.append(f"- What holds for every screen recording: `{roles['calendar']}` line {rule.line}")
    evidence.append("- The finished asset's shape and safe zone: `config/platforms.json`")
    ask = (
        f"Approve the filming plan for {product} window {window}: {plural(len(found.jobs), 'asset')} in"
        f" {plural(len(groups), 'sitting')}"
    )
    fields = {"kind": KIND, "product": product}
    return exchange.Item(fields, ask[: exchange.MAX_TITLE], "\n".join(body), "\n".join(touches), "\n".join(evidence))


def origin(product: str, window: int) -> str:
    return f"{ORIGIN}/{product}/window-{window}"


def file_plan(
    filming: Filming,
    ledger: Ledger,
    store: Store,
    products: Sequence[str],
    seen: dict[str, str],
    now: datetime,
) -> Standing:
    """Queue the filming plan unless it already stands: one item, under an identifier that never changes.

    The plan is compared by what must be filmed, never by its wording. A plan the Founder approved is never asked
    again, and neither is one the Founder rejected; a plan still open stays as it is. A new plan is filed only when
    there is none, or when the kit changed what must be filmed, and it then takes the earlier one's place.
    """
    found = filming.requirements
    fingerprint, digests = found.fingerprint(), found.digests()
    mine = sorted(
        (entry for entry in ledger.entries.values() if entry.get("origin") == origin(filming.product, filming.window)),
        key=lambda entry: (str(entry["published_at"]), str(entry["id"])),
    )
    approved = [entry for entry in mine if APPROVED in (entry["status"], entry.get("decided"))]
    held = frozenset((key, digest) for entry in approved for key, digest in (entry.get("filming_jobs") or {}).items())
    current = next((entry for entry in mine if entry["status"] == OPEN), None)
    same = [entry for entry in mine if entry.get("filming_sha256") == fingerprint]
    settled = next((entry for entry in reversed(same) if entry in approved), None)
    if settled is not None:
        if current is not None:
            # The kit went back to what the Founder approved, so the plan filed for the change has nothing to ask.
            ledger.close(current, SUPERSEDED, filming.run, now, superseded_by=str(settled["id"]))
        return Standing(APPROVED_BEFORE, str(settled["id"]), approved=held)
    if current is not None and current in same:
        return Standing(WAITING, str(current["id"]), approved=held)
    refused = next((entry for entry in reversed(same) if REJECTED in (entry["status"], entry.get("decided"))), None)
    if current is None and refused is not None:
        reason = f": {refused['reason']}" if refused.get("reason") else ""
        return Standing(DECIDED, str(refused["id"]), reason, approved=held)
    decided = [entry for entry in mine if {APPROVED, REJECTED} & {entry["status"], entry.get("decided")}]
    previous = current or next(reversed(decided or mine), None)
    item = plan_item(filming, previous)
    if previous is not None:
        item = exchange.Item(
            dict(item.fields, supersedes=str(previous["id"])), item.ask, item.body, item.touches, item.evidence
        )
    check = exchange.check_item(
        exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence), products
    )
    if check.item is None:
        return Standing(NOT_FILED, None, "; ".join(check.problems), approved=held)
    extra = {"filming_sha256": fingerprint, "filming_jobs": digests}
    identifier = ledger.publish(
        store,
        item,
        f"filming-plan-w{filming.window}",
        filming.run,
        now,
        extra,
        origin=origin(filming.product, filming.window),
    )
    seen[exchange.item_hash(item)] = identifier
    if current is None:
        return Standing(FILED, identifier, approved=held)
    ledger.close(current, SUPERSEDED, filming.run, now, superseded_by=identifier)
    return Standing(REPLACED, identifier, replaced=str(current["id"]), approved=held)


def gate(filming: Filming, job: shots.Job) -> str:
    """Why nothing may be cut from a job's footage yet, or "" once a plan the Founder approved holds the job as the
    kit has it now: the plan is approved before filming."""
    standing = filming.standing
    if (job.key, job.digest()) in standing.approved:
        return ""
    if standing.status == DECIDED:
        return f"the filming plan was rejected as `{standing.item}`, so nothing is cut from its footage"
    if standing.item is None:
        return "there is no filming plan yet"
    if standing.approved:
        return (
            f"the kit changed what day {job.films} films since a filming plan was approved, and the plan"
            f" `{standing.item}` that holds it now is not approved yet"
        )
    return f"the filming plan `{standing.item}` is not approved yet"


def lacking(
    inventory: footage.Inventory, wanted: Sequence[shots.Shot], leg: str | None, recut: bool
) -> tuple[list[str], list[str], list[str], list[str]]:
    """The shots of a day no edit can be cut from yet: those with no footage, those whose footage could not be
    measured, for a pair leg those with no take both legs can use, and the opening shot of a leg that must open on a
    take of its own and has none. The legs of a pair share their footage, so a take named for one leg is only that
    leg's opening in a re-cut pair: the first shot of several can do with one, and every other shot needs a take
    named without a leg letter. Where the Founder is on camera in that first shot, each leg needs its own take of it
    too, since its Hook is said there: once the footage place holds any take of that shot, a leg without its own is
    told so, whether or not a take both legs can use is there."""
    missing, unread, unshared, unopened = [], [], [], []
    own = edits.own_opening(wanted, leg, recut)
    for index, shot in enumerate(wanted):
        usable = inventory.for_shot(shot.id, leg)
        unmeasured = inventory.for_shot(shot.id, leg, measured=False)
        opening = recut and index == 0 and len(wanted) > 1
        owed = shot == own and any(clip.shot == shot.id for clip in inventory.clips.values())
        lacks = []
        if owed and not any(clip.leg for clip in usable):
            lacks.append(unread if any(clip.leg for clip in unmeasured) else unopened)
        if not usable and not owed:
            lacks.append(unread if unmeasured else missing)
        elif leg and not opening and all(clip.leg for clip in usable):
            lacks.append(unread if any(not clip.leg for clip in unmeasured) else unshared)
        for group in lacks:
            if shot.id not in group:
                group.append(shot.id)
    return missing, unread, unshared, unopened


def no_shared_take(names: Sequence[str], recut: bool) -> str:
    """Why a pair leg has no video while a shot the legs share is filmed only in takes named for one leg."""
    where = "everything after the opening" if recut else "all of their footage"
    one = len(names) == 1
    return (
        f"{shot_names(names)} {'has' if one else 'have'} no take both legs can use (the legs share {where}, so"
        f" {'it needs' if one else 'each needs'} a file named without a leg letter, such as `{names[0]}.mov`)"
    )


def no_own_take(shot: str, leg: str) -> str:
    """Why a re-cut leg has no video while its opening shot, with the Founder on camera, has no take of the leg's."""
    take = edits.own_take(shot, leg)
    return (
        f"shot {shot} has no opening take of leg {leg}'s own (the Founder is on camera in it and each leg opens on"
        f" its own Hook, so it needs a file named `{take}`, such as `{take}.mov`)"
    )


def readiness(filming: Filming, job: shots.Job, leg: str | None) -> str:
    """Why a day's edit cannot be cut this run, or "" when it can: its job is in an approved plan, the footage
    place could be read and measured, and every shot has footage the day's video can be cut from."""
    inventory = filming.inventory
    waiting = gate(filming, job)
    if waiting:
        return waiting
    if inventory.status in (footage.NOT_SET, footage.FAILED):
        return inventory.detail
    if not filming.tooling.ok:
        return f"the video tooling cannot be used ({filming.tooling.problem})"
    if filming.canvas is None:
        return filming.problem or "config/platforms.json holds no canvas"
    missing, unread, unshared, unopened = lacking(inventory, job.shots, leg, job.recut)
    reasons = [f"no footage yet for {shot_names(missing)}"] if missing else []
    if unread:
        reasons.append(f"the footage of {shot_names(unread)} could not be measured")
    if unshared:
        reasons.append(no_shared_take(unshared, job.recut))
    if unopened:
        reasons.append(no_own_take(unopened[0], leg))
    return "; ".join(reasons)


def prepare(
    repo_root: Path,
    plan: posts.Plan,
    where: Place,
    ledger: Ledger,
    store: Store,
    areas: Areas,
    products: Sequence[str],
    seen: dict[str, str],
    env: Mapping[str, str],
    run_id: str,
    now: datetime,
) -> Filming:
    """The run's filming standing, fixed before the agent starts: the plan filed or found, the footage place listed
    and measured, and, for each calendar day due this run, whether an edit can be cut."""
    parsed, window = plan.context.kit, plan.window.number
    problem = ""
    try:
        canvas = video.load_canvas(load_json(repo_root / posts.PLATFORMS_CONFIG))
    except (ConfigError, ValueError) as error:
        canvas, problem = None, str(error)
    tooling = video.find(env, canvas) if canvas is not None else video.Tooling(None, None, problem=problem)
    edits_folder = areas.path("drafts", EDITS, f"window-{window}")
    filming = Filming(
        where.product,
        window,
        run_id,
        where,
        canvas,
        tooling,
        Standing(NOT_FILED, None, "the kit could not be read"),
        footage.Inventory(where.path, f"window-{window}", footage.NOT_SET),
        plan.folder,
        edits_folder,
        paths=dict(plan.context.paths),
        problem=problem,
        env=dict(env),
    )
    unread = [
        f"`{plan.context.paths.get(role, role)}` ({parsed.problems[role]})" for role in ROLES if role in parsed.problems
    ]
    if unread:
        filming.problem = f"the kit could not be read: {', '.join(unread)}"
        filming.standing = Standing(NOT_FILED, None, filming.problem)
        return filming
    found = filming.requirements = shots.requirements(parsed, plan.context.paths["calendar"])
    filming.unplanned = dict(found.unplanned)
    filming.calendar_lines = [day.line for day in parsed.days.values()]
    filming.screen_rule = shots.screen_rule(parsed.asset_checks)
    if found.jobs:
        filming.standing = file_plan(filming, ledger, store, products, seen, now)
    else:
        filming.standing = Standing(NOT_FILED, None, "the calendar holds no day the plan can read")
    known = {shot.id for _, shot in found.shots()}
    filming.inventory = footage.read(where.path, window, known, tooling, env)
    for number in parsed.days:
        post = posts.standing_post(posts.day_entries(ledger, plan.product, window, number))
        if post is not None:
            filming.posted[number] = dict(post)
    for due in plan.days:
        number, day = due.day.day, due.day
        filming.due[number] = bool(due.approved and due.approved.get("asset_sha256"))
        if due.approved:
            filming.approved[number] = dict(due.approved)
        filming.rejected[number] = [dict(entry) for entry in due.rejected]
        job = found.job_for(number)
        if job is None:
            continue
        why = SETTLED if filming.due[number] else readiness(filming, job, day.leg)
        filming.days[number] = DayEdit(day_spec(plan.product, window, number, day.leg, job), not why, why)
    filming.look(store)
    return filming


def day_spec(product: str, window: int, number: int, leg: str | None, job: shots.Job) -> edits.DaySpec:
    """What one calendar day's edit must follow, from its filming job: the job's shots and length, and, for a pair
    leg, the other leg and both Hooks of a pair whose opening the kit marks as re-cut."""
    others = [other for other in job.days if other != number]
    return edits.DaySpec(
        product,
        window,
        number,
        job.key,
        leg,
        job.pair,
        job.recut,
        others[0] if others else None,
        job.length,
        job.shots,
        tuple(hook.text for hook in job.hooks) if job.recut else (),
    )


# What the agent, the run report, and the Founder are told.


def check_command(filming: Filming, repo_root: Path) -> str:
    """check-edits as the agent runs it, reading this run's record of the footage and of each day's standing."""
    return f"/usr/bin/python3 {repo_root / 'src/bin/gr0wthlab'} check-edits --run {shlex.quote(filming.run)}"


def shot_rules(shot: shots.Shot) -> str:
    rules = [shot.kind]
    if shot.uncut:
        rules.append("one unbroken range, never cut")
    rules.append("no speed change" if shot.real_time is not False else "may run at another speed")
    return f"{shot.id} ({'; '.join(rules)})"


def brief_lines(filming: Filming, repo_root: Path) -> list[str]:
    lines = ["## Filming", ""]
    if filming.problem and not filming.requirements.jobs:
        return lines + [f"Nothing could be planned this run: {filming.problem}. Write no edit record.", ""]
    inventory, canvas = filming.inventory, filming.canvas
    lines += [
        f"- Filming plan: {filming.standing.account()}. The launcher files it from the kit; never write one.",
        f"- Video tooling: {filming.tooling.describe()}.",
        f"- Footage place: {inventory.detail or inventory.status}. You cannot open it and need not: every file in"
        " it is listed below with what the launcher measured.",
    ]
    if canvas is not None:
        lines.append(
            f"- A finished video is {canvas.shape} at {canvas.fps} frames a second; the launcher renders it from"
            " your edit record, with the text of the day's post Draft drawn over it."
        )
    ready = [number for number, day in filming.days.items() if day.ready]
    lines += [
        "",
        f"Write an edit record for each day marked ready, as `{filming.edits}/day-NN.json`, in the format the task"
        " definition gives, and for no other day. Where the table says to leave a day's edit record as it is, change"
        f" nothing in it and do not remove it. Check them before you finish: `{check_command(filming, repo_root)}`.",
        "",
        "| Day | Shots its edit must show | Length | Footage files | Edit record |",
        "| --- | --- | --- | --- | --- |",
    ]
    for number, day in sorted(filming.days.items()):
        spec = day.spec
        files = []
        for shot in spec.shots:
            for clip in inventory.for_shot(shot.id, spec.leg):
                measured = clip.facts.describe() if clip.facts else "not measured"
                files.append(f"`{clip.name}` for {shot.id}: {measured}")
            for clip in inventory.for_shot(shot.id, spec.leg, measured=False):
                files.append(f"`{clip.name}` for {shot.id}: could not be measured")
        if spec.other is not None:
            where = "after its opening" if spec.recut else "from the first frame to the last"
            pair = f"; the same source ranges as day {spec.other} {where}"
        else:
            pair = ""
        state = "ready" if day.ready else f"not ready: {day.why}"
        if filming.waits(number) and filming.intact(number):
            state += f"; {KEEPS} while its Draft stays as it is, so leave its edit record as it is"
        elif filming.waits(number):
            state += f"; {filming.kept(number)}; leave its edit record as it is"
        lines.append(
            f"| {number} | {posts.cell('; '.join(shot_rules(shot) for shot in spec.shots))} | {span(spec.length)}{pair}"
            f" | {posts.cell('; '.join(files) or 'none yet')} | {posts.cell(state)} |"
        )
    if not filming.days:
        lines.append("| - | - | - | - | No calendar day due this run has a shot list. |")
    lines.append("")
    lines += [f"- Day {number} is not in the filming plan: {why}." for number, why in sorted(filming.unplanned.items())]
    for clip in inventory.unmatched():
        lines.append(f"- `{clip.name}` is footage of no shot ({clip.problem}); never use it.")
    for clip in inventory.unmeasured():
        lines.append(f"- `{clip.name}` could not be measured ({clip.problem}); never use it.")
    if not ready:
        lines.append("- No day is ready for an edit record this run.")
    return lines + [""]


def describe_blocks(findings: Sequence[Finding]) -> str:
    return "; ".join(finding.line() for finding in findings)


def result_line(asset: Asset) -> str:
    if asset.finished:
        made = "kept from an earlier run" if asset.reused else "rendered this run"
        return f"`{asset.path}`, {asset.facts.describe()}, {made}"
    if asset.status == BLOCKED:
        return describe_blocks(asset.blocks) or asset.detail
    return asset.detail


def report_lines(filming: Filming | None, skipped: str = "") -> list[str]:
    lines = ["## Filming", ""]
    if filming is None:
        return lines + [skipped or "No active Product films, so there is no filming plan and no edit."]
    found, inventory = filming.requirements, filming.inventory
    if filming.problem and not found.jobs:
        return lines + [f"Nothing could be planned this run: {filming.problem}."]
    groups = filming.sittings()
    lines += [
        f"- Filming plan: {filming.standing.account()}.",
        f"- {plural(len(found.jobs), 'asset')} to film in {plural(len(groups), 'sitting')}: "
        + "; ".join(f"{sitting.label} ({', '.join(shot.id for _, shot in sitting.shots)})" for sitting in groups)
        + ".",
    ]
    lines += [f"- Not planned: day {number}, since {why}." for number, why in found.unplanned]
    lines.append(f"- Video tooling: {filming.tooling.describe()}.")
    lines.append(f"- Footage place: {inventory.detail or inventory.status}.")
    for name, why in inventory.ignored:
        lines.append(f"- Left alone in the footage place: `{name}` ({why}).")
    for clip in inventory.unmatched():
        lines.append(f"- Footage of no shot: `{clip.name}` ({clip.problem}).")
    for clip in inventory.unmeasured():
        lines.append(f"- Footage that could not be measured: `{clip.name}` ({clip.problem}).")
    if filming.record:
        lines.append(f"- Every file measured and every edit checked: `{filming.record}`.")
    lost = filming.lost()
    if lost:
        lost = ["", "Posts whose video's finished file is not the file they name:", ""] + [
            f"- {line}." for line in lost
        ]
    if filming.replaced:
        lost += ["", "Posts that lost the video they named:", ""] + [f"- {line}" for line in filming.replaced]
    if not filming.days:
        return lines + ["", "No calendar day due this run has a shot list."] + lost
    lines += ["", "| Day | Shots | Edit | Detail |", "| --- | --- | --- | --- |"]
    for number, day in sorted(filming.days.items()):
        asset = filming.results.get(number)
        status = asset.status if asset else (NO_EDIT if day.ready else HELD)
        detail = result_line(asset) if asset else day.why
        if asset is not None and asset.held and filming.keeps(number):
            detail += f"; {filming.kept(number)}"
        names = ", ".join(shot.id for shot in day.spec.shots)
        lines.append(f"| {number} | {names} | {status} | {posts.cell(detail)} |")
    if filming.apart:
        lines += ["", "A/B pairs whose two videos differ:", ""]
        lines += [f"- {line}" for line in filming.apart]
    return lines + lost


def notice_section(filming: Filming | None, day_text: str) -> tuple[int, str, str] | None:
    """What the Founder must know of this run's footage: each shot of an approved plan with no footage it can be
    cut from once footage has begun to arrive, each file that is footage of no shot or could not be measured, edits
    skipped for want of tooling, each video not cut for a reason outside its edit record, and each A/B pair whose two
    videos differ, so that nothing the run changed for it is offered, and each open post whose video's finished
    file is gone, changed, or could not be read; None when there is nothing. Before any footage is in the window's
    folder nothing is missing yet, so no shot is named, and neither is a shot of a day whose video the Founder already
    approved. An edit record that failed a check blocked its day's post, so the post Drafts' part of the notice names
    it. A day whose post names a video when the run ends is never said to have none: its video could not be cut
    again, and its post is said to keep the video it shows only while that video's finished file is intact."""
    if filming is None:
        return None
    lines = []
    blocked = [asset for asset in filming.results.values() if asset.status == BLOCKED]
    inventory = filming.inventory
    begun = inventory.status == footage.READ and any(clip.shot for clip in inventory.clips.values())
    for number, day in sorted(filming.days.items()):
        spec = day.spec
        job = filming.requirements.job_for(number)
        missing, unread, unshared, unopened = lacking(inventory, spec.shots, spec.leg, spec.recut)
        approved = job is not None and not gate(filming, job)
        owed = begun and approved and not filming.due.get(number)
        lacks = missing or unread or unshared or unopened
        if owed and lacks and number not in [asset.day for asset in blocked]:
            reasons = [f"{shot_names(missing)} {'has' if len(missing) == 1 else 'have'} no footage"] if missing else []
            if unread:
                reasons.append(f"the footage of {shot_names(unread)} could not be measured")
            if unshared:
                reasons.append(no_shared_take(unshared, spec.recut))
            if unopened:
                reasons.append(no_own_take(unopened[0], spec.leg))
            if filming.keeps(number):
                keeping = f"; {KEEPS}" if filming.intact(number) else ""
                lines.append(f"- Day {number}'s video could not be cut again: {' and '.join(reasons)}{keeping}.")
            else:
                lines.append(f"- Day {number} has no video: {' and '.join(reasons)}, and nothing is substituted.")
    for clip in inventory.unmatched():
        lines.append(f"- `{clip.name}` in the footage place is footage of no shot: {clip.problem}.")
    for clip in inventory.unmeasured():
        lines.append(f"- `{clip.name}` in the footage place could not be measured: {clip.problem}.")
    waiting = sorted(asset.day for asset in filming.results.values() if asset.held and asset.edit)
    if waiting and not filming.tooling.ok:
        many = len(waiting) > 1
        kept = [number for number in waiting if filming.keeps(number) and filming.intact(number)]
        keeping = (
            f"; the {'posts' if len(kept) > 1 else 'post'} of {'days' if len(kept) > 1 else 'day'} {listed(kept)}"
            f" {'keep the videos they show' if len(kept) > 1 else 'keeps the video it shows'}"
            if kept
            else ""
        )
        lines.append(
            f"- The {'edits' if many else 'edit'} of {'days' if many else 'day'} {listed(waiting)}"
            f" {'were' if many else 'was'} skipped: {filming.tooling.problem}{keeping}."
        )
    for asset in sorted(filming.results.values(), key=lambda asset: asset.day):
        if asset.told and filming.keeps(asset.day):
            keeping = f"; {KEEPS}" if filming.intact(asset.day) else ""
            lines.append(f"- Day {asset.day}'s video could not be cut again: {asset.detail}{keeping}.")
        elif asset.told:
            lines.append(f"- Day {asset.day}'s video was not cut: {asset.detail}.")
    lines += [f"- {line}" for line in filming.apart]
    lines += [f"- {line}." for line in filming.lost()]
    lines += [f"- {line}" for line in filming.replaced]
    if not lines:
        return None
    title = f"{plural(len(lines), 'filming problem')} on {day_text}"
    return (
        len(lines),
        title,
        "These videos were not made or are not offered, or these files not used:\n" + "\n".join(lines),
    )


def tally(filming: Filming | None, agent_gap: str) -> Tally:
    """What the filming workflow checked and acted on: each asset planned, each footage file measured, each edit
    record examined, the plan when this run filed it, and each video it rendered."""
    if filming is None:
        return Tally("filming", 0, 0, "no active Product films")
    results = list(filming.results.values())
    examined = [asset for asset in results if asset.edit]
    rendered = [asset for asset in results if asset.sha256 and not asset.reused]
    counts = [
        f"{sum(1 for asset in results if asset.status == status)} {status}"
        for status in (FINISHED, WITHHELD, BLOCKED, HELD)
        if any(asset.status == status for asset in results)
    ]
    note = (
        f"plan {filming.standing.account()}; {plural(len(filming.requirements.jobs), 'asset')} planned,"
        f" {plural(len(filming.inventory.clips), 'footage file')} measured"
        + (f"; edits: {', '.join(counts)}" if counts else "")
    )
    return Tally(
        "filming",
        len(filming.requirements.jobs) + len(filming.inventory.clips) + len(examined),
        int(filming.standing.acted) + len(rendered),
        note,
        "; ".join(gaps(filming, agent_gap)),
    )


def gaps(filming: Filming, agent_gap: str) -> list[str]:
    """Why the filming output is incomplete this run: the kit or the canvas could not be read, the plan could not be
    filed, the footage place could not be listed, the finished file of a video an open post names could not be read, or
    the agent did not finish and left a day that was ready for an edit record without one. An edit that waits on
    footage, approval, or tooling is not a gap: the report names it as not cut. Neither is a ready day that an agent
    which finished left without an edit record, nor a finished file that is gone or changed, which the notice names."""
    found = []
    if filming.problem:
        found.append(filming.problem)
    if filming.standing.status == NOT_FILED and not filming.problem:
        found.append(f"the filming plan was not filed ({filming.standing.detail})")
    if filming.inventory.status == footage.FAILED:
        found.append(filming.inventory.detail)
    for number, shown in sorted(filming.videos.items()):
        if shown.file.unknown:
            found.append(shown.file.told(f" of the video day {number}'s post names"))
    if agent_gap and any(day.ready and not filming.wanted(number) for number, day in filming.days.items()):
        found.append(agent_gap)
    return found


def record(filming: Filming, store: Store, run_id: str, now: datetime) -> str:
    """The run's account of filming, kept in ledger/evidence/filming/<run id>.json: the plan, every footage file it
    measured, and what became of every due day's edit record."""
    found = filming.requirements
    data = {
        "run": run_id,
        "at": now.isoformat(),
        "product": filming.product,
        "window": filming.window,
        "plan": {
            "status": filming.standing.status,
            "item": filming.standing.item,
            "fingerprint": found.fingerprint() if found.jobs else None,
            "jobs": [
                {
                    "key": job.key,
                    "days": list(job.days),
                    "angle": job.angle,
                    "pair": job.pair,
                    "recut": job.recut,
                    "format": f"{filming.paths.get('angles', 'the Angle bank')} line {job.line}",
                    "digest": job.digest(),
                    "shots": [shot.as_json() for shot in job.shots],
                }
                for job in found.jobs
            ],
            "sittings": [
                {"number": sitting.number, "setup": sitting.setup, "shots": [shot.id for _, shot in sitting.shots]}
                for sitting in filming.sittings()
            ],
            "unplanned": [{"day": number, "why": why} for number, why in found.unplanned],
        },
        "problem": filming.problem,
        "tooling": filming.tooling.as_json(),
        "footage": filming.as_record()["footage"],
        "days": [
            dict(
                filming.results[number].summary() if number in filming.results else {"status": NO_EDIT},
                day=number,
                ready=day.ready,
                why=day.why,
            )
            for number, day in sorted(filming.days.items())
        ],
    }
    path = store.path("evidence", EVIDENCE, f"{run_id}.json")
    store.write_json(path, data)
    filming.record = store.relative(path)
    return filming.record


# Rebuilding a finished asset from its record.


def rebuild(store: Store, relative: str, where: Path | None, env: Mapping[str, str]) -> tuple[bool, list[str]]:
    """Render a finished asset again from its record and the footage place alone, and put it back where its record
    says it was only if it comes out byte for byte the asset the record names; the footage is read as ever, and a
    render that is anything else leaves whatever is there as it was."""
    try:
        path = store.path(relative)
        made = json.loads(read_plain(path).decode("utf-8"))
        canvas = video.Canvas(**dict(made["canvas"], font=Path(made["canvas"]["font"])))
        target = store.path(str(made["asset"]))
        if not is_within(target, store.path(ASSETS)):
            raise ValueError("its asset is not under assets/")
        named, maker = str(made["sha256"]), str(made["tooling"])
        overlays = [video.Overlay(**overlay) for overlay in made["overlays"]]
        cuts = []
        for cut in made["cuts"]:
            if where is None or not edits.inside(str(cut["source"])):
                raise ValueError("the footage place is not set, or a source is not inside it")
            source = where / str(cut["source"])
            if footage.fingerprint(source)[0] != cut["sha256"]:
                raise ValueError(f"`{cut['source']}` is no longer the footage this asset was cut from")
            facts = video.Facts.from_json(cut["facts"])
            cuts.append(video.Cut(source, cut["in"], cut["out"], cut["speed"], facts))
    except (ConfigError, UnsafeFile, OSError, KeyError, TypeError, ValueError) as error:
        return False, [f"`{relative}` cannot be rebuilt: {getattr(error, 'strerror', None) or error}"]
    tooling = video.find(env, canvas)
    try:
        facts, problems = produce(tooling, canvas, cuts, overlays, target, env, named)
    except (video.VideoError, OSError) as error:
        return False, [f"`{made['asset']}` was not rebuilt: {getattr(error, 'strerror', None) or error}"]
    if not problems:
        return True, [
            f"`{made['asset']}` rebuilt with {tooling.version}: {facts.describe()}.",
            "It is byte for byte the asset its record names.",
        ]
    lines = [
        f"`{made['asset']}` was not rebuilt, and whatever is at that path is as it was: rendered again with"
        f" {tooling.version}, it is not the asset its record names."
    ]
    lines += [f"PROBLEM {problem}" for problem in problems]
    if maker != tooling.version:
        lines.append(f"Its record says it was made by {maker}; other tooling encodes the same frames differently.")
    return False, lines
