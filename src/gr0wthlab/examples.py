"""The workflows' example sets, and the gate that re-runs one on every Instructions change (US-ME16, FR-14, ADR 0003).

Each workflow's example set is src/examples/<workflow>/evals.json, in the marketingskills evals.json shape: each
example's prompt, the output expected, its assertions, and its files, built on synthetic fixtures and never on a
Product's package. Only a reviewed pull request changes a set: the sandbox can read src/examples/ and never write it,
and the boundary check proves that on its own.

An example that carries `run` is re-run by the agent. Its run is the workflow's own session, run the way a weekly run
runs it: the launcher builds a throwaway lab under ledger/working/examples/, which git ignores and the run removes
when it ends, holding a copy of the repository's code, configuration, and task definitions, the lab's own ledger/ and
workspace/ with the example's starting state, and the Instructions under test in its ledger/instructions/, beside a
synthetic Mandu, Product checkout, and, for filming, footage made with ffmpeg's test pattern. It then runs one weekly
run in the lab with that workflow's session only (cycle.Cycle with only=), through the same launcher code, Codex
command, permission profile, closed network, preflight, task definition, and brief. What an example's sources answer
comes from its fixtures, through the launcher's client with a transport that reads them, never through fetch.send.
The lab's run takes the session's work in with the checks a weekly run uses, and the example's deterministic
assertions are read off what it took in. A lab never writes the real ledger/: an example's synthetic records, the
Founder's among them, are copied into the lab's own.

The gate runs a workflow's set with the Instructions in force and with a proposed text, one example at a time, each
side in turn, on the same day and model. An assertion is worse when it held with the text in force and fails with the
proposed one. A change is kept only when no example is worse and every example was compared on both sides; the gate
stops at the first example that is worse or cannot be compared, since the change can then no longer be kept, and at
its own time bound. Judged statements, which no check can decide, are never judged: the notice lists them as such.
"""

from __future__ import annotations

import io
import json
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import beta, beta_drafts, fetch, filming, messages, posts, process, video
from .areas import UnsafeFile, read_plain
from .boundary import canonical
from .exchange import plural
from .waitlist import looks_like_address

FOLDER = Path("src/examples")
EVALS = "evals.json"
LABS = ("working", "examples")  # under ledger/
DETERMINISTIC, JUDGED = "deterministic", "judged"
IN_FORCE, PROPOSED = "in force", "proposed"
KEPT, NOT_KEPT, NOT_COMPARED = "kept", "not kept", "not compared"
RAN = "ran to its end"
# The time a lab's run happens at, unless its set or its example names another: a Sunday afternoon on the Mac's clock,
# so every date an example's checks turn on is fixed.
DEFAULT_AT = "2026-10-11T23:00:00+00:00"
# What the lab's repository holds of the real one, beside its own ledger/ and workspace/.
COPIED = ("config", "CONTEXT.md", ".gitignore", "docs/mandu-exchange.md")
SOURCE_SKIPPED = ("tests", "examples", "__pycache__")
AREAS = ("evidence", "drafts", "review-queue", "weekly-reads", "run-reports", "instructions")
FOUNDER_KINDS = ("decisions", "sittings", "beta-builds", "beta-reports", "outreach")
NO_SOURCES = {"subreddits": [], "app_store": None}
LAB_GIT = ("-c", "user.name=gr0wthlab lab", "-c", "user.email=gr0wthlab-lab", "-c", "commit.gpgsign=false")


class SetError(Exception):
    """A workflow's example set that cannot be read or run."""


@dataclass(frozen=True)
class Example:
    id: int
    prompt: str
    expected: str
    assertions: tuple[Mapping[str, object], ...]
    run: Mapping[str, object]

    @property
    def checks(self) -> list[Mapping[str, object]]:
        return [assertion for assertion in self.assertions if assertion.get("kind") == DETERMINISTIC]

    @property
    def judged(self) -> list[str]:
        return [str(assertion.get("text")) for assertion in self.assertions if assertion.get("kind") == JUDGED]


@dataclass(frozen=True)
class ExampleSet:
    workflow: str
    folder: Path
    data: Mapping[str, object]
    examples: tuple[Example, ...]

    @property
    def lab(self) -> Mapping[str, object]:
        """What every example's lab holds unless the example says otherwise."""
        lab = self.data.get("lab")
        return lab if isinstance(lab, dict) else {}


def load(repo_root: Path, workflow: str) -> ExampleSet:
    """A workflow's example set, with the examples the agent re-runs: those that carry `run`."""
    folder = repo_root / FOLDER / workflow
    try:
        data = json.loads(read_plain(folder / EVALS).decode("utf-8"))
    except (OSError, UnsafeFile, ValueError) as error:
        raise SetError(f"`{FOLDER / workflow / EVALS}` could not be read ({error})") from error
    if not isinstance(data, dict) or data.get("skill_name") != workflow or not isinstance(data.get("evals"), list):
        raise SetError(f"`{FOLDER / workflow / EVALS}` is not {workflow}'s example set")
    found = []
    for raw in data["evals"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("run"), dict):
            continue
        assertions = tuple(raw.get("assertions") or ())
        found.append(Example(int(raw["id"]), str(raw["prompt"]), str(raw["expected_output"]), assertions, raw["run"]))
    if not found:
        raise SetError(f"`{FOLDER / workflow / EVALS}` holds no example the agent re-runs")
    return ExampleSet(workflow, folder, data, tuple(found))


def usable(repo_root: Path, workflow: str, env: Mapping[str, str]) -> ExampleSet:
    """A workflow's example set that can run on this Mac: one with an example that names footage needs the video
    tooling that makes it."""
    example_set = load(repo_root, workflow)
    if any(setting(example_set, example, "footage") for example in example_set.examples):
        footage_tooling(env)
    return example_set


def footage_tooling(env: Mapping[str, str]) -> video.Tooling:
    tooling = video.find(env)
    if not tooling.ok:
        raise SetError(f"the video tooling that makes its footage cannot be used on this Mac ({tooling.problem})")
    return tooling


# One check, one run of an example, one example on both sides.


@dataclass(frozen=True)
class Check:
    assertion: Mapping[str, object]
    held: bool
    detail: str = ""

    @property
    def name(self) -> str:
        return describe(self.assertion)


def describe(assertion: Mapping[str, object]) -> str:
    """An assertion in a few words, as the report and the notice name it.

    `queued: 1 package-change-proposal citing a.md`: plain words, never a list's code, since the Founder reads it.
    """
    rest = {key: value for key, value in assertion.items() if key not in ("kind", "check")}
    phrases = []
    if "item" in rest:
        at_least = "at least" if rest.pop("at_least", False) else ""
        words = [str(word) for word in (at_least, rest.pop("count", ""), rest.pop("item")) if word != ""]
        if rest.get("cites"):
            words.append("citing " + " and ".join(str(name) for name in listed(rest.pop("cites"))))
        phrases.append(" ".join(words))
    phrases += [f"{key} {' and '.join(str(value) for value in listed(value))}" for key, value in rest.items()]
    name = str(assertion.get("check")).replace("_", " ")
    return f"{name}: {', '.join(phrases)}" if phrases else name


def listed(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else [value]


@dataclass
class Run:
    """One example on one side of the gate: whether its session ran to its end, and each check's result."""

    side: str
    status: str
    why: str = ""
    checks: list[Check] = field(default_factory=list)
    seconds: float = 0.0
    cost: float | None = None
    lab_run: str = ""
    started: bool = False  # whether Codex was started for its session

    @property
    def ran(self) -> bool:
        return self.status == RAN

    def held(self) -> int:
        return sum(1 for check in self.checks if check.held)

    def summary(self) -> str:
        if not self.ran:
            return f"not compared: {self.why}"
        return f"{self.held()} of {plural(len(self.checks), 'check')} held"

    def as_json(self) -> dict[str, object]:
        return {
            "side": self.side,
            "status": self.status,
            "why": self.why or None,
            "lab_run": self.lab_run or None,
            "agent_seconds": round(self.seconds, 1),
            "cost_usd": self.cost,
            "checks": [{"check": check.name, "held": check.held, "detail": check.detail} for check in self.checks],
        }


@dataclass
class Pair:
    """One example run on both sides of a change, and, where a check did worse with the change, the Instructions in
    force run again: an agent's output varies from one session to the next, so a check that failed with the change is
    taken as the change's doing unless it fails without the change too."""

    example: Example
    before: Run | None = None
    after: Run | None = None
    again: Run | None = None  # the Instructions in force, run again where a check did worse with the change

    @property
    def compared(self) -> bool:
        return bool(self.before and self.after and self.before.ran and self.after.ran)

    def flipped(self) -> list[str]:
        """The checks that held with the text in force and failed with the proposed text."""
        if not self.compared:
            return []
        after = {check.name: check for check in self.after.checks}
        return [
            check.name
            for check in self.before.checks
            if check.held and check.name in after and not after[check.name].held
        ]

    def cleared(self) -> list[str]:
        """The checks that did worse with the change and failed with the Instructions in force too, run again."""
        if self.again is None or not self.again.ran:
            return []
        again = {check.name: check.held for check in self.again.checks}
        return [name for name in self.flipped() if name in again and not again[name]]

    def worse(self) -> list[str]:
        """Each check that did worse with the change and held again with the Instructions in force, in words."""
        names = self.flipped()
        if names and (self.again is None or not self.again.ran):
            return []  # not yet worse: the gate runs the Instructions in force again first
        cleared = self.cleared()
        after = {check.name: check for check in self.after.checks} if self.after else {}
        return [
            f"`{name}` held with the Instructions in force, and again when they were run again, and failed with the"
            " change" + (f" ({after[name].detail})" if after.get(name) and after[name].detail else "")
            for name in names
            if name not in cleared
        ]

    def unrun(self) -> str:
        """Why the example on both sides could not be compared, or ""."""
        for run in (self.before, self.after):
            if run is not None and not run.ran:
                return f"with the {'Instructions in force' if run.side == IN_FORCE else 'change'}, {run.why}"
        return "" if self.compared else "it was not run on both sides"

    def not_compared(self) -> str:
        """Why this example could not be compared, its repeat included, or ""."""
        missing = self.unrun()
        if missing or not self.flipped():
            return missing
        if self.again is None:
            return "it did worse with the change and the Instructions in force were not run again"
        return f"run again with the Instructions in force, {self.again.why}" if not self.again.ran else ""

    def repeat_line(self) -> str:
        """What running the Instructions in force again showed, for the notice and the record, or ""."""
        flipped = self.flipped()
        if not flipped or self.again is None or not self.again.ran:
            return ""
        cleared = self.cleared()
        held = [name for name in flipped if name not in cleared]
        said = [f"{quoted(held)} held again"] if held else []
        said += [f"{quoted(cleared)} failed there too"] if cleared else []
        verdict = "so the example is worse" if held else "so the change is not taken as the cause"
        return (
            f"Example {self.example.id}: {quoted(flipped)} did worse with the change; run again with the Instructions"
            f" in force, {' and '.join(said)}, {verdict}."
        )


def quoted(names: Sequence[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


@dataclass
class Gate:
    workflow: str
    pairs: list[Pair] = field(default_factory=list)
    not_run: list[Example] = field(default_factory=list)
    outcome: str = NOT_COMPARED
    why: str = ""
    bound: float = 0.0

    @property
    def runs(self) -> list[Run]:
        found = []
        for pair in self.pairs:
            found += [run for run in (pair.before, pair.after, pair.again) if run is not None]
        return found

    @property
    def seconds(self) -> float:
        return sum(run.seconds for run in self.runs)

    @property
    def cost(self) -> float | None:
        priced = [run.cost for run in self.runs if run.cost is not None]
        return sum(priced) if priced else None

    @property
    def sessions(self) -> int:
        return sum(1 for run in self.runs if run.started)

    def cost_line(self) -> str:
        cost = f"about ${self.cost:.2f} at API prices" if self.cost is not None else "a cost not reported"
        return (
            f"The example set took {plural(self.sessions, 'agent session')}, {self.seconds:.0f} seconds of agent time"
            f" against a bound of {self.bound:.0f}, and {cost}."
        )

    def decide(self) -> None:
        """Kept only when every example was compared on both sides and none got worse."""
        for pair in self.pairs:
            missing = pair.not_compared()
            if missing:
                self.outcome, self.why = NOT_COMPARED, f"example {pair.example.id} could not be compared: {missing}"
                return
            worse = pair.worse()
            if worse:
                self.outcome, self.why = NOT_KEPT, f"example {pair.example.id} got worse: {'; '.join(worse)}"
                return
        if self.not_run or not self.pairs:
            self.outcome, self.why = NOT_COMPARED, self.why or "no example was run"
            return
        self.outcome = KEPT
        self.why = f"no example of {plural(len(self.pairs), 'example')} did worse"

    def as_json(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "outcome": self.outcome,
            "why": self.why,
            "bound_seconds": self.bound,
            "agent_seconds": round(self.seconds, 1),
            "sessions": self.sessions,
            "cost_usd": self.cost,
            "examples": [
                {
                    "id": pair.example.id,
                    "prompt": pair.example.prompt,
                    "in_force": pair.before.as_json() if pair.before else None,
                    "proposed": pair.after.as_json() if pair.after else None,
                    "in_force_again": pair.again.as_json() if pair.again else None,
                    "worse": pair.worse(),
                    "not_judged": pair.example.judged,
                }
                for pair in self.pairs
            ],
            "not_run": [example.id for example in self.not_run],
        }


def result_lines(gate: Gate) -> list[str]:
    """Every example's result before and after a change, for the notice: what was checked, and what was not."""
    lines = [
        f"Each example is one {gate.workflow} session the agent ran in a throwaway lab, once with the Instructions in"
        " force and once with the change; the launcher's own checks read what each one wrote.",
        "",
        "| Example | With the Instructions in force | With the change |",
        "| --- | --- | --- |",
    ]
    for pair in gate.pairs:
        before = result(pair.before, pair.again)
        after = result(pair.after, None)
        lines.append(f"| {pair.example.id}: {cell(pair.example.prompt)} | {cell(before)} | {cell(after)} |")
    for example in gate.not_run:
        lines.append(f"| {example.id}: {cell(example.prompt)} | not run | not run |")
    repeats = [pair.repeat_line() for pair in gate.pairs if pair.repeat_line()]
    if repeats:
        lines += [
            "",
            "Where a check did worse with the change, the Instructions in force were run again: a check that fails"
            " there too is not taken as the change's doing.",
            "",
        ]
        lines += [f"- {line}" for line in repeats]
    judged = [(pair.example.id, text) for pair in gate.pairs for text in pair.example.judged]
    if judged:
        lines += ["", "Not judged by anything, by the launcher or a model; yours to judge, if you want to:", ""]
        lines += [f"- Example {number}: {text}" for number, text in judged]
    lines += ["", gate.cost_line()]
    return lines


def result(run: Run | None, again: Run | None) -> str:
    """One side of an example in the notice's table, its repeat beside it when it was run again."""
    text = run.summary() if run else "not run"
    return f"{text}; run again, {again.summary()}" if again is not None else text


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


# The lab.


@dataclass
class Lab:
    root: Path
    repo: Path
    mandu: Path
    product: Path
    env: dict[str, str]
    at: datetime
    example_set: ExampleSet
    pages: dict[str, str] = field(default_factory=dict)


def git(repo: Path, *args: str) -> str:
    done = process.run(["git", "-C", str(repo), *LAB_GIT, *args], process.QUICK)
    if done.timed_out or done.returncode != 0:
        raise SetError(f"git {args[0]} failed in the lab: {' '.join(done.stderr.split())[:300] or 'no output'}")
    return done.stdout


def overlay(source: Path, target: Path) -> None:
    """Lay one fixture tree over a lab folder: every file copied, nothing followed."""
    if not source.is_dir():
        raise SetError(f"`{source.name}` is not a fixture folder")
    shutil.copytree(str(source), str(target), dirs_exist_ok=True, symlinks=False)


def setting(example_set: ExampleSet, example: Example, key: str, default=None):
    """One of the lab's settings: the example's own, or else its set's."""
    return example.run.get(key, example_set.lab.get(key, default))


def layers(example_set: ExampleSet, example: Example, key: str) -> list[object]:
    """The fixture trees laid over one part of a lab, its set's first and then the example's own."""
    return list(example_set.lab.get(key) or ()) + list(example.run.get(key) or ())


def fixture(example_set: ExampleSet, relative: object) -> Path:
    """A fixture an example set names, from its own folder: one of its files, or another set's, as the outreach set
    reads the post-Draft set's kit; never anything outside the example sets."""
    path = (example_set.folder / str(relative)).resolve()
    if not str(path).startswith(str(example_set.folder.parent.resolve()) + os.sep):
        raise SetError(f"{relative!r} is not a file of the example sets")
    return path


def build(
    repo_root: Path,
    example_set: ExampleSet,
    example: Example,
    text: str,
    root: Path,
    env: Mapping[str, str],
    log_dir: Path,
    limit: float,
) -> Lab:
    """A throwaway lab for one example: a repository like the real one with the Instructions under test, and its own
    synthetic Mandu and Product checkout beside it. Its workspace READMEs are as the last commit holds them, never as
    a session left the checkout's."""
    workflow = example_set.workflow
    if root.exists():
        shutil.rmtree(str(root))
    repo = root / "gr0wthlab"
    shutil.copytree(
        str(repo_root / "src"),
        str(repo / "src"),
        ignore=lambda folder, names: (
            [name for name in names if name in SOURCE_SKIPPED and folder.endswith("src")]
            + [name for name in names if name == "__pycache__"]
        ),
    )
    (repo / FOLDER).mkdir()
    (repo / FOLDER / "README.md").write_text("# Examples\n\nA lab holds no example set.\n", encoding="utf-8")
    for name in COPIED:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not (repo_root / name).exists():
            continue
        if (repo_root / name).is_dir():
            shutil.copytree(str(repo_root / name), str(target))
        else:
            shutil.copy(str(repo_root / name), str(target))
    ledger, workspace = repo / "ledger", repo / "workspace"
    for kind in FOUNDER_KINDS:
        (ledger / "founder" / kind).mkdir(parents=True)
        (ledger / "founder" / kind / ".gitkeep").write_text("")
    shutil.copytree(str(repo_root / "ledger" / "instructions"), str(ledger / "instructions"))
    (ledger / "instructions" / f"{workflow}.md").write_text(text, encoding="utf-8")
    (ledger / "README.md").write_text("# ledger\n\nA lab's records.\n", encoding="utf-8")
    for area in AREAS:
        (workspace / area).mkdir(parents=True)
        readme = git(repo_root, "show", f"HEAD:workspace/{area}/README.md")
        (workspace / area / "README.md").write_text(readme, encoding="utf-8")
    for key, target in (("ledger", ledger), ("workspace", workspace)):
        for relative in layers(example_set, example, key):
            overlay(fixture(example_set, relative), target)

    mandu = root / "Mandu"
    registry = json.loads((repo_root / "config" / "products.json").read_text(encoding="utf-8"))
    for product in registry.get("products", []):
        for source in (product.get("go_to_market_package") or {}).get("sources", []):
            path = mandu / source["path"]
            path = path / "placeholder.md" if source["path"].endswith("/") else path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"Synthetic placeholder for `{source['path']}`.\n", encoding="utf-8")
    for relative in layers(example_set, example, "mandu"):
        overlay(fixture(example_set, relative), mandu)
    days = example.run.get("calendar_days")
    if days:
        keep_days(mandu, [int(day) for day in days])
    make_footage(example_set, example, mandu / "projects" / "RepToday", root.parent / "_footage", env)

    product = root / "RepToday"
    product.mkdir()
    code = setting(example_set, example, "code")
    if code:
        overlay(fixture(example_set, code), product)
    else:
        (product / "README.md").write_text("A synthetic Product checkout.\n", encoding="utf-8")
    git(product, "init", "--quiet")
    git(product, "add", "--all")
    git(product, "commit", "--quiet", "-m", "code")
    (root / "Immerse").mkdir()

    run_config = json.loads((repo / "config" / "run.json").read_text(encoding="utf-8"))
    run_config["agent"] = dict(run_config["agent"], time_limit_seconds=limit, run_time_limit_seconds=limit)
    for section, values in (setting(example_set, example, "config", {}) or {}).items():
        run_config[section] = dict(run_config.get(section) or {}, **values)
    (repo / "config" / "run.json").write_text(json.dumps(run_config, indent=2), encoding="utf-8")
    sources = json.loads((repo / "config" / "sources.json").read_text(encoding="utf-8"))
    sources["listening"] = dict(sources["listening"], **(setting(example_set, example, "sources", NO_SOURCES) or {}))
    (repo / "config" / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    git(repo, "init", "--quiet")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "lab")

    view = setting(example_set, example, "waitlist_view")
    if view:
        # The anonymous Waitlist view lies outside the lab's repository and every checkout, as the real one must.
        (root / "exports").mkdir()
        shutil.copy(str(fixture(example_set, view)), str(root / "exports" / "waitlist-view.json"))
    pages_file = setting(example_set, example, "pages")
    pages = json.loads(fixture(example_set, pages_file).read_text(encoding="utf-8")) if pages_file else {}
    at = datetime.fromisoformat(str(setting(example_set, example, "at", DEFAULT_AT)))
    lab_env = {key: value for key, value in env.items() if not key.startswith("GR0WTHLAB_")}
    for key in ("GR0WTHLAB_CODEX_BIN", video.FFMPEG_ENV, video.FFPROBE_ENV):
        if env.get(key):
            lab_env[key] = env[key]
    lab_env.update(
        GR0WTHLAB_MANDU_DIR=str(mandu),
        GR0WTHLAB_REPTODAY_DIR=str(product),
        GR0WTHLAB_IMMERSE_DIR=str(root / "Immerse"),
        GR0WTHLAB_FOOTAGE_DIR=str(mandu / "projects" / "RepToday"),
        GR0WTHLAB_LOG_DIR=str(log_dir),
        GR0WTHLAB_PRODUCTION_CLONE=str(root / "no-production-clone"),
    )
    if view:
        lab_env["GR0WTHLAB_WAITLIST_VIEW"] = str(canonical(root / "exports" / "waitlist-view.json"))
    return Lab(root, canonical(repo), canonical(mandu), canonical(product), lab_env, at, example_set, pages)


def make_footage(example_set: ExampleSet, example: Example, place: Path, cache: Path, env: Mapping[str, str]) -> None:
    """Put the footage an example names in its lab's footage place: real video files made with ffmpeg's own test
    pattern, labelled as test input on every frame, with the length, size, frame rate, and sound the set's inventory
    gives each. Each file is made once for all of a run's labs and copied into each; none is ever filmed footage."""
    names = setting(example_set, example, "footage", []) or []
    if not names:
        return
    tooling = footage_tooling(env)
    inventory = json.loads(fixture(example_set, example_set.data["footage"]).read_text(encoding="utf-8"))
    clips = {str(clip["name"]): clip["facts"] for clip in inventory["clips"]}
    for name in names:
        facts = clips[str(name)]
        made = cache / str(name)
        if not made.is_file():
            made.parent.mkdir(parents=True, exist_ok=True)
            size, rate, length = f"{facts['width']}x{facts['height']}", int(facts["fps"]), float(facts["duration"])
            command = [str(tooling.ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
            command += ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={length}"]
            if facts.get("sound"):
                command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={length}"]
            command += ["-vf", "drawbox=y=ih/2-60:w=iw:h=120:color=black@0.7:t=fill"]
            command += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
            command += (["-c:a", "aac", "-shortest"] if facts.get("sound") else []) + [str(made)]
            done = process.run(command, process.SLOW, env=dict(env))
            if done.timed_out or done.returncode != 0:
                made.unlink(missing_ok=True)
                raise SetError(f"its footage `{name}` could not be made: {' '.join(done.stderr.split())[:300]}")
        target = place / str(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(made), str(target))


def keep_days(mandu: Path, days: Sequence[int]) -> None:
    """Cut a lab's synthetic calendar down to the given days, so only they can fall due."""
    import re

    path = mandu / "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
    rows = [(re.match(r"\| (\d+) \|", line), line) for line in path.read_text(encoding="utf-8").splitlines()]
    kept = [line for row, line in rows if row is None or int(row.group(1)) in days]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


class Pages:
    """The answers an example's sources give, from its fixtures, as the launcher's client reads them: a transport
    that never opens a connection, on a clock that moves only when the client waits."""

    def __init__(self, pages: Mapping[str, str]):
        self.pages = dict(pages)
        self.time = 0.0

    def __call__(self, host, target, headers, timeout, limit, deadline) -> fetch.Response:
        body = self.pages.get(f"https://{host}{target}")
        if body is None:
            return fetch.Response(404, {}, b"")
        return fetch.Response(200, {}, body.encode("utf-8")[: limit + 1])

    def clock(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.time += seconds


def run_example(
    repo_root: Path,
    example_set: ExampleSet,
    example: Example,
    side: str,
    text: str,
    root: Path,
    env: Mapping[str, str],
    home: Path,
    log_dir: Path,
    limit: float,
) -> Run:
    """Run one example in a lab of its own, with the given Instructions text, and read its checks off what the lab's
    run took in. A lab whose launcher could not take the session's work in, or whose run stopped, says nothing of the
    Instructions, so the example is not run."""
    from . import cycle

    try:
        lab = build(repo_root, example_set, example, text, root, env, log_dir, limit)
    except (OSError, SetError, ValueError, KeyError, TypeError) as error:
        return Run(side, "not run", f"its lab could not be built ({error})")
    pages = Pages(lab.pages)

    def reader(policy: fetch.Policy) -> fetch.Client:
        return fetch.Client(policy, transport=pages, clock=pages.clock, sleep=pages.sleep, now=lambda: lab.at)

    out = io.StringIO()
    runner = cycle.Cycle(lab.repo, lab.env, home, out, lambda: lab.at, reader, only=example_set.workflow)
    try:
        code = runner.run("on-demand", None, ["run"])
    except Exception as error:
        # Whatever stops a lab's run is that example's trouble, never the weekly run's: the run still ends with its
        # report, and the example reads as not compared.
        return Run(side, "not run", f"its lab's run stopped ({type(error).__name__}: {error})")
    finally:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{root.name}.out.log").write_text(out.getvalue(), encoding="utf-8")
    state = runner.state
    if state is None:
        return Run(side, "not run", "its lab's run did not start")
    session = state.session(example_set.workflow)
    result = Run(side, "not run", lab_run=state.run_id)
    if session is not None:
        result.seconds, result.cost, result.started = session.seconds or 0.0, session.cost, session.started
    if session is None or not session.due:
        result.why = f"its lab had no work for the agent ({session.why if session else 'no session was planned'})"
        return result
    if not session.finished:
        result.why = f"its session did not run to its end: {session.gap()}"
        return result
    problem = take_in_problem(state, example_set.workflow)
    if problem:
        result.why = f"its session's work was {problem}"
        return result
    if code:
        result.why = f"its lab's run stopped before it finished, with exit status {code}; its log says why"
        return result
    result.status = RAN
    evaluate = EVALUATORS.get(example_set.workflow)
    for assertion in example.checks:
        try:
            if evaluate is None:
                raise SetError(f"no check reads {example_set.workflow}'s work")
            held, detail = evaluate(assertion, example, state, lab)
        except Exception as error:
            # A check that cannot be read did not hold; the example is still compared on what could be read.
            held, detail = False, f"the check could not be read ({type(error).__name__}: {error})"
        result.checks.append(Check(assertion, held, detail))
    return result


def take_in_problem(state, workflow: str) -> str:
    """Why a lab's launcher could not take its session's work in, or "": the filming session's edit records are taken
    in with the post Drafts."""
    return {
        "post-drafts": state.posts_problem,
        "filming": state.posts_problem,
        "beta-recruiting": state.beta_problem,
        "listening": state.listening_problem,
        "outreach": state.outreach_problem,
    }.get(workflow, "")


def gate(
    repo_root: Path,
    workflow: str,
    before: str,
    proposed: str,
    change: str,
    env: Mapping[str, str],
    home: Path,
    log_dir: Path,
    bound: float,
    example_limit: float,
    labs: Path,
) -> Gate:
    """Run a workflow's example set on both sides of a change, example by example, within the gate's bound, and
    decide it. Each lab is removed once its checks are read; its run's log stays in the log folder."""
    result = Gate(workflow, bound=bound)
    try:
        example_set = usable(repo_root, workflow, env)
    except SetError as error:
        result.why = str(error)
        return result

    def run_one(example: Example, side: str, text: str, round_: str, spent: float) -> Run:
        left = bound - spent
        if left <= 0:
            return Run(side, "not run", f"the gate's bound of {bound:.0f} seconds of agent time was used up")
        name = f"{example.id:02d}-{'in-force' if side == IN_FORCE else 'proposed'}{round_}"
        root = labs / change / name
        run = run_example(
            repo_root, example_set, example, side, text, root, env, home, log_dir / change, min(example_limit, left)
        )
        shutil.rmtree(str(root), ignore_errors=True)
        return run

    for index, example in enumerate(example_set.examples):
        pair = Pair(example)
        pair.before = run_one(example, IN_FORCE, before, "", result.seconds)
        if pair.before.ran:
            pair.after = run_one(example, PROPOSED, proposed, "", result.seconds + pair.before.seconds)
        if pair.flipped():
            spent = result.seconds + pair.before.seconds + pair.after.seconds
            pair.again = run_one(example, IN_FORCE, before, "-again", spent)
        result.pairs.append(pair)
        if pair.not_compared() or pair.worse():
            result.not_run = list(example_set.examples[index + 1 :])
            break
    result.decide()
    return result


# Reading an example's checks off what its lab's run took in.


def queued_items(state, kind: str) -> list[Mapping[str, object]]:
    """The items of one kind the lab's run queued."""
    return [entry for entry in state.queue_after if entry.get("kind") == kind and entry["id"] in state.published]


def item_text(lab: Lab, entry: Mapping[str, object]) -> str:
    return (lab.repo / "ledger" / str(entry["file"])).read_text(encoding="utf-8")


def common(assertion: Mapping[str, object], state, lab: Lab) -> tuple[bool, str] | None:
    """The checks every workflow's examples may use: what was queued, and what was set aside."""
    check = assertion.get("check")
    if check == "queued":
        kind = str(assertion["item"])
        found = queued_items(state, kind)
        wanted = int(assertion.get("count", 1))
        texts = [item_text(lab, entry) for entry in found]
        for words in assertion.get("cites", ()) or ():
            texts = [text for text in texts if str(words) in text]
        expected = f"at least {wanted}" if assertion.get("at_least") else str(wanted)
        held = len(texts) >= wanted if assertion.get("at_least") else len(texts) == wanted
        return held, f"{plural(len(texts), kind + ' item')} queued as asked, {expected} expected"
    if check == "nothing_queued":
        kind = str(assertion["item"])
        found = queued_items(state, kind)
        return not found, f"{plural(len(found), kind + ' item')} queued"
    if check == "nothing_set_aside":
        return not state.set_aside, f"{plural(len(state.set_aside), 'file')} set aside from incoming/"
    return None


def day_result(state, day: int) -> posts.DayResult | None:
    outcome = state.post_outcome
    return next((result for result in outcome.results if result.day == day), None) if outcome else None


def evaluate_posts(assertion: Mapping[str, object], example: Example, state, lab: Lab) -> tuple[bool, str]:
    shared = common(assertion, state, lab)
    if shared is not None:
        return shared
    check = assertion.get("check")
    day = int(assertion.get("day") or example.run["calendar_days"][0])
    result = day_result(state, day)
    if result is None:
        return False, f"day {day} was not taken in"
    verdict = result.verdict
    blocks = [finding.rule for finding in verdict.blocks] if verdict else []
    status = f"day {day}: {result.status}" + (f", blocked by {', '.join(sorted(set(blocks)))}" if blocks else "")
    if check == "passes":
        return result.status == posts.QUEUED and verdict is not None and verdict.passed, status
    if check == "blocked_by":
        rule = str(assertion["rule"])
        return result.status == posts.BLOCKED and any(found.startswith(rule) for found in blocks), status
    if check == "not_blocked_by":
        rule = str(assertion["rule"])
        return verdict is not None and not any(found.startswith(rule) for found in blocks), status
    if check == "hook_frozen":
        return verdict is not None and "frozen-hook" not in blocks, status
    if check == "lint_passes":
        from . import lint

        known = set(lint.KNOWN_RULES) | {"need-marker", "hashtags"}
        broken = [rule for rule in blocks if rule in known or rule.startswith("config/platforms.json")]
        return verdict is not None and not broken, status
    if check == "cites_angle":
        if result.item is None:
            return False, status
        text = (lab.repo / "ledger" / "review-queue" / "items" / f"{result.item}.md").read_text(encoding="utf-8")
        return f"Angle {assertion['angle']}," in text, status
    raise SetError(f"unknown check {check!r}")


def message_outcome(outcomes: Sequence, to: str, purpose: str | None):
    """The outcome of the one message an assertion names: the personal-network ask, or a creator's message, the
    first one unless purpose names the follow-up."""
    wanted = messages.NETWORK if to == "network" else (purpose or messages.CREATOR)
    return next((o for o in outcomes if o.target.purpose == wanted and (to == "network" or o.target.key == to)), None)


def evaluate_messages(assertion: Mapping[str, object], outcomes: Sequence) -> tuple[bool, str] | None:
    """The checks of a message, in the outreach and Listening examples alike."""
    check = assertion.get("check")
    if check not in ("offered", "blocked_by", "carries_source_link"):
        return None
    to = str(assertion.get("to") or "network") if check == "carries_source_link" else str(assertion.get("to"))
    outcome = message_outcome(outcomes, to, assertion.get("purpose"))
    if outcome is None:
        return False, f"no message to {to} was taken in"
    blocks = [finding.rule for finding in outcome.verdict.blocks] if outcome.verdict else []
    detail = f"to {to}: {outcome.status}" + (f", blocked by {', '.join(sorted(set(blocks)))}" if blocks else "")
    if check == "offered":
        return outcome.status == messages.QUEUED, detail
    if check == "blocked_by":
        return outcome.status == messages.BLOCKED and any(rule.startswith(str(assertion["rule"])) for rule in blocks), (
            detail
        )
    return outcome.status == messages.QUEUED and outcome.item is not None, detail


def evaluate_outreach(assertion: Mapping[str, object], example: Example, state, lab: Lab) -> tuple[bool, str]:
    shared = common(assertion, state, lab)
    if shared is not None:
        return shared
    outcomes = state.outreach_result.outcomes if state.outreach_result else []
    found = evaluate_messages(assertion, outcomes)
    if found is None:
        raise SetError(f"unknown check {assertion.get('check')!r}")
    held, detail = found
    if held and assertion.get("check") == "carries_source_link":
        outcome = message_outcome(outcomes, "network", None)
        text = (lab.repo / "ledger" / "review-queue" / "items" / f"{outcome.item}.md").read_text(encoding="utf-8")
        held = "It carries the personal-network Source link `" in text
        detail += "" if held else ", and its item names no personal-network Source link"
    return held, detail


def evaluate_beta(assertion: Mapping[str, object], example: Example, state, lab: Lab) -> tuple[bool, str]:
    shared = common(assertion, state, lab)
    if shared is not None:
        return shared
    check = assertion.get("check")
    purpose = beta_drafts.WAITLIST_ASK if assertion.get("draft") == "waitlist-ask" else beta_drafts.INVITATION
    outcome = state.beta_outcome
    result = outcome.result(purpose) if outcome else None
    if result is None:
        return False, f"no {purpose} Draft was taken in"
    verdict = result.verdict
    blocks = [finding.rule for finding in verdict.blocks] if verdict else []
    detail = f"{purpose}: {result.status}" + (f", blocked by {', '.join(sorted(set(blocks)))}" if blocks else "")
    if check == "passes":
        return result.status == beta.QUEUED and verdict is not None and verdict.passed, detail
    if check == "blocked_by":
        return result.status == beta.BLOCKED and any(rule.startswith(str(assertion["rule"])) for rule in blocks), detail
    if check == "not_blocked_by":
        return verdict is not None and not any(rule.startswith(str(assertion["rule"])) for rule in blocks), detail
    if check == "no_address_in_findings":
        lines = [finding.line() for finding in (verdict.blocks + verdict.warnings)] if verdict else []
        return not any(looks_like_address(line) for line in lines), detail
    raise SetError(f"unknown check {check!r}")


def evaluate_listening(assertion: Mapping[str, object], example: Example, state, lab: Lab) -> tuple[bool, str]:
    shared = common(assertion, state, lab)
    if shared is not None:
        return shared
    check = assertion.get("check")
    result = state.listening_result
    if result is None:
        return False, "nothing of Listening was taken in"
    kept = [quote.id for quote in result.accepted]
    said = f"{plural(len(kept), 'quote')} kept, {len(result.rejected)} refused, {len(result.discarded)} discarded"
    if check == "kept":
        document = assertion.get("document")
        return (document in kept) if document else bool(kept), said
    if check == "nothing_refused":
        names = ", ".join(name for name, _ in result.rejected)
        return not result.rejected, said + (f": {names}" if names else "")
    if check == "nothing_discarded":
        names = ", ".join(name for name, _ in result.discarded)
        return not result.discarded, said + (f": {names}" if names else "")
    replies = {outcome.target.key: outcome for outcome in result.replies}
    if check in ("offered", "not_offered"):
        to = str(assertion["to"])
        outcome = replies.get(to)
        status = outcome.status if outcome else "no Draft"
        offered = outcome is not None and outcome.status == messages.QUEUED
        return offered if check == "offered" else not offered, f"a reply to {to}: {status}"
    if check == "fetched_text_stays_data":
        document = str(assertion["document"])
        snapshot = json.loads(fixture(lab.example_set, "files/snapshot.json").read_text(encoding="utf-8"))
        text = next(entry["text"] for entry in snapshot["documents"] if entry["id"] == document)
        sentences = [sentence.strip() for sentence in text.split(". ") if len(sentence.split()) > 3]
        session = state.session("listening")
        brief = (lab.repo / "ledger" / session.brief).read_text(encoding="utf-8") if session and session.brief else ""
        told = [sentence for sentence in sentences if sentence in brief]
        linked = [
            o.target.key for o in result.replies if o.verdict and any(f.rule == "no-link" for f in o.verdict.blocks)
        ]
        held = bool(brief) and not told and not linked
        return (
            held,
            f"{len(told)} of its sentences in the brief; replies blocked for a link: {', '.join(linked) or 'none'}",
        )
    raise SetError(f"unknown check {check!r}")


def evaluate_filming(assertion: Mapping[str, object], example: Example, state, lab: Lab) -> tuple[bool, str]:
    shared = common(assertion, state, lab)
    if shared is not None:
        return shared
    check, day = assertion.get("check"), int(assertion["day"])
    found = state.filming
    asset = found.results.get(day) if found is not None else None
    status = asset.status if asset is not None else filming.NO_EDIT
    blocks = [finding.rule for finding in asset.blocks] if asset is not None else []
    detail = f"day {day}: {status}" + (f", blocked by {', '.join(sorted(set(blocks)))}" if blocks else "")
    if check == "edit_passes":
        return status in (filming.READY, filming.FINISHED) and not blocks, detail
    if check == "renders":
        return status == filming.FINISHED, detail
    if check == "no_edit":
        record = lab.repo / "workspace" / "drafts" / filming.EDITS / "window-1" / f"day-{day:02d}.json"
        return not (record.exists() or record.is_symlink()), detail
    raise SetError(f"unknown check {check!r}")


def evaluate_review(assertion: Mapping[str, object], example: Example, state, lab: Lab) -> tuple[bool, str]:
    """A package review's examples read only what it queued: the checks every workflow's examples may use."""
    shared = common(assertion, state, lab)
    if shared is None:
        raise SetError(f"unknown check {assertion.get('check')!r}")
    return shared


EVALUATORS: dict[str, Callable[[Mapping[str, object], Example, object, Lab], tuple[bool, str]]] = {
    "post-drafts": evaluate_posts,
    "outreach": evaluate_outreach,
    "beta-recruiting": evaluate_beta,
    "listening": evaluate_listening,
    "package-review": evaluate_review,
    "filming": evaluate_filming,
}
