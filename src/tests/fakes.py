"""Throwaway repositories, a throwaway Mandu, and a fake Codex, so whole runs can be tested without a model."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AREAS = ("evidence", "drafts", "review-queue", "weekly-reads", "run-reports", "instructions")
EXAMPLES = REPO / "src" / "examples" / "post-drafts"
BETA_EXAMPLES = REPO / "src" / "examples" / "beta-recruiting"
# A window whose days all fall far in the future, so a run that is not about post Drafts has none due.
QUIET_WINDOW = {"number": 1, "first_sitting": "2099-01-04", "slot": "19:00"}

# Stands in for codex. `codex sandbox` answers the preflight as an enforcing sandbox would, without running anything;
# `codex exec` plays the agent from behavior.json beside it, writing straight into the workspace. An agent told to
# hang does its writing, starts its children, the first in a session of its own as Codex starts a shell command, notes
# every process id in pids.txt, and then never exits and never reports its summary or its token counts. One told to
# detach first leaves what a shell command that has finished can leave, noted last: a process in a session of its own
# whose parent has ended.
FAKE_CODEX = """#!{python}
import json, os, re, shutil, signal, subprocess, sys, time
from pathlib import Path

here = Path(__file__).resolve().parent
args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("codex-cli 0.0.0-fake")
    sys.exit(0)
if args[:1] == ["sandbox"]:
    targets = args[args.index("--") + 6:]
    for target in targets:
        path = Path(target)
        writable = path.parent.name == "workspace" and path.name in {areas!r}
        print(("WROTE " if writable else "REFUSED ") + target)
    sys.exit(0)
prompt = sys.stdin.read()
(here / "prompt.txt").write_text(prompt)
behavior = json.loads((here / "behavior.json").read_text())
brief = Path(re.search(r"Run brief, read it first: (\\S+)", prompt).group(1))
workspace = brief.parents[2] / "workspace"
for relative in behavior.get("rmtree", []):
    shutil.rmtree(workspace / relative)
for relative, text in behavior.get("write", {{}}).items():
    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
for relative, target in behavior.get("symlink", {{}}).items():
    (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
    (workspace / relative).symlink_to(target)
for relative, mode in behavior.get("chmod", {{}}).items():
    os.chmod(workspace / relative, int(mode, 8))
children = [
    subprocess.Popen(["/bin/sleep", "600"], start_new_session=number == 0).pid
    for number in range(behavior.get("children", 0))
]
if behavior.get("detach"):
    detach = (
        "import subprocess; sleep = ['/bin/sleep', '600']; "
        "print(subprocess.Popen(sleep, start_new_session=True, stdout=subprocess.DEVNULL).pid)"
    )
    children.append(int(subprocess.run([sys.executable, "-c", detach], stdout=subprocess.PIPE, text=True).stdout))
if behavior.get("ignore_stop"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
(here / "pids.txt").write_text(" ".join(str(pid) for pid in [os.getpid(), *children]))
for line in behavior.get("events", []):
    print(line, flush=True)
while behavior.get("hang"):
    time.sleep(600)
summary = behavior.get("summary", "Checked the package.\\n\\nReview: complete\\n")
Path(args[args.index("--output-last-message") + 1]).write_text(summary)
usage = {{"input_tokens": 200000, "cached_input_tokens": 150000, "cache_write_input_tokens": 0, "output_tokens": 4000}}
print(json.dumps({{"type": "turn.completed", "usage": usage}}))
sys.exit(behavior.get("exit", 0))
"""


def git(repo: Path, *args: str, env=None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


def git_env(root: Path) -> dict[str, str]:
    """An environment whose git has an identity and none of the developer's own configuration."""
    config = root / "gitconfig"
    config.write_text("[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n")
    return dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM="1")


def set_run(repo: Path, section: str, values: dict) -> None:
    """One section of config/run.json in a throwaway checkout."""
    path = repo / "config" / "run.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[section] = dict(data.get(section, {}), **values)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_window(repo: Path, window: dict) -> None:
    set_run(repo, "window", window)


def set_filming(repo: Path, films: bool) -> None:
    """Whether any Product films in a throwaway checkout: with films, the registry is the real one; without, no
    Product has a filming block, so a run files no filming plan."""
    path = repo / "config" / "products.json"
    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    if not films:
        for product in registry["products"]:
            product.pop("filming", None)
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def make_repo(path: Path, env: dict[str, str], window: dict | None = None, films: bool = False) -> Path:
    """A gr0wthlab checkout with the real configuration, task definition, proposals, and area READMEs, committed on
    main; its window is QUIET_WINDOW unless a test gives another, and no Product films unless a test says so, so a
    run that is not about filming files no filming plan."""
    shutil.copytree(str(REPO / "config"), str(path / "config"))
    set_window(path, QUIET_WINDOW if window is None else window)
    set_filming(path, films)
    shutil.copytree(str(REPO / "src" / "instructions"), str(path / "src" / "instructions"))
    shutil.copytree(str(REPO / "src" / "proposals"), str(path / "src" / "proposals"))
    shutil.copy(str(REPO / ".gitignore"), str(path / ".gitignore"))
    (path / "ledger").mkdir()
    (path / "ledger" / "README.md").write_text("# ledger\n")
    for area in AREAS:
        (path / "workspace" / area).mkdir(parents=True)
        (path / "workspace" / area / "README.md").write_text(f"# {area}\n")
    git(path, "init", "--quiet", env=env)
    git(path, "add", "--all", env=env)
    git(path, "commit", "--quiet", "-m", "initial", env=env)
    return path


def make_mandu(path: Path, kit: bool = True) -> Path:
    """A Mandu checkout holding every package source the real Product registry names; with kit, the 14-day kit
    files are the example set's synthetic kit, whose brand rules already hold every list the F1 proposal adds."""
    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    for product in registry["products"]:
        for source in (product.get("go_to_market_package") or {}).get("sources", []):
            target = path / source["path"]
            if source["path"].endswith("/"):
                if kit and source.get("files_starting_with"):
                    continue  # the kit holds the files it covers
                target = target / f"{source.get('files_starting_with', '')}plan.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"{source['path']}\n", encoding="utf-8")
    if kit:
        shutil.copytree(str(EXAMPLES / "files" / "mandu"), str(path), dirs_exist_ok=True)
    return path


def make_code(path: Path, env: dict[str, str]) -> Path:
    """A Product checkout on main holding the example set's code, for claim checks."""
    shutil.copytree(str(EXAMPLES / "files" / "code"), str(path))
    git(path, "init", "--quiet", env=env)
    git(path, "add", "--all", env=env)
    git(path, "commit", "--quiet", "-m", "code", env=env)
    return path


def install_codex(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    codex = directory / "codex"
    codex.write_text(FAKE_CODEX.format(python=sys.executable, areas=set(AREAS)), encoding="utf-8")
    codex.chmod(codex.stat().st_mode | stat.S_IXUSR)
    behave(directory, {})
    return codex


def behave(directory: Path, behavior: dict) -> None:
    (directory / "behavior.json").write_text(json.dumps(behavior), encoding="utf-8")


def agent_pids(directory: Path) -> list[int]:
    """The fake agent's own process id, its children's, and last that of a process it detached, as its last run
    noted them."""
    return [int(pid) for pid in (directory / "pids.txt").read_text(encoding="utf-8").split()]


def running(pid: int) -> bool:
    """Whether a process is still running; one that has ended and only waits to be collected is not."""
    from gr0wthlab import process

    rows = process.table()
    return rows is not None and pid in rows and not rows[pid][1].startswith(process.ZOMBIE)


def all_gone(pids, within: float = 10.0) -> bool:
    """Whether every one of these processes ends within a few seconds."""
    deadline = time.monotonic() + within
    while any(running(pid) for pid in pids):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def stop_leftovers(directory: Path) -> None:
    """End whatever a test's processes left running, so a failing test never leaves one behind; only a process that
    still shows a command line the tests start is touched."""
    from gr0wthlab import process

    try:
        pids = agent_pids(directory)
    except (OSError, ValueError):
        return
    for pid in pids:
        shown = subprocess.run([process.PS, "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
        if (
            str(directory) in shown
            or "signal.SIG_IGN" in shown
            or shown.strip() in ("/bin/sleep 600", "/bin/sleep 599")
        ):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


class Clock:
    """A clock that starts where a test says and moves a second per reading."""

    def __init__(self, start: datetime):
        self.moment = start

    def set(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        self.moment += timedelta(seconds=1)
        return self.moment


def stepped_clock(step: float, after: float = 1.0):
    """The two clocks of a Mac whose wall clock steps once it has been read for `after` seconds: forward by `step`
    seconds, as it reads when the Mac wakes from that long a sleep, or back, as when it is set back. Awake time is
    real."""
    from gr0wthlab import process

    first = None

    def wall() -> float:
        nonlocal first
        now = time.monotonic()
        first = now if first is None else first
        return time.time() + (step if now - first >= after else 0)

    return process.Clock(time.monotonic, wall)


SUNDAY_RUN = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)


PROPOSAL = """---
kind: package-change-proposal
product: RepToday
---

# Approve package change: record the name as cleared

## Proposal

Replace the stale caveat with the cleared status.

## Touches

- `projects/RepToday/gtm/02-brand/brand-guidelines.md`

## Evidence

- Cleared and reserved: `projects/RepToday/02-marketing-launch-checklist_260807.md` line 24
- Still says unverified: `projects/RepToday/gtm/02-brand/brand-guidelines.md` line 35

## Options

- Approve, optionally with a note
- Reject, with a one-line reason
"""


def proposal(kind: str = "package-change-proposal", extra: str = "", title: str = "record the name as cleared") -> str:
    from gr0wthlab import exchange

    text = PROPOSAL.replace("kind: package-change-proposal", f"kind: {kind}\n{extra}".rstrip("\n"))
    text = text.replace("record the name as cleared", title)
    text = text.replace("## Proposal", f"## {exchange.KINDS[kind]}")
    return text.replace(
        "- Approve, optionally with a note\n- Reject, with a one-line reason\n",
        "".join(f"- {option}\n" for option in exchange.options(kind)),
    )


# The Waitlist's anonymous view, as RepToday's build would write it: twelve sign-ups across every Source and Fit
# answer over two weeks (the weeks of 2026-09-28 and 2026-10-05), generated an hour before SUNDAY_RUN.
WAITLIST_ENTRIES = [
    ("Qm7tLx2a", "tiktok", "lost-the-routine", True, "2026-09-29"),
    ("Vb3kPz9w", "tiktok", "lost-the-routine", False, "2026-10-01"),
    ("Hc8nRy4e", "tiktok", "exercises-regularly", True, "2026-10-06"),
    ("Jd2wGs6u", "tiktok", "lost-the-routine", True, "2026-10-08"),
    ("Ne5qTb1o", "youtube", "never-had-a-routine", True, "2026-09-30"),
    ("Xf9mKa3i", "youtube", "lost-the-routine", True, "2026-10-07"),
    ("Ug4vWc7y", "youtube", None, False, "2026-10-09"),
    ("Ps1hDe8t", "reddit", "exercises-regularly", False, "2026-10-02"),
    ("Lr6jFq5s", "reddit", "lost-the-routine", True, "2026-10-10"),
    ("Ka0zMn2p", "network", "lost-the-routine", True, "2026-10-03"),
    ("Yt3bHv9r", "network", "never-had-a-routine", False, "2026-10-11"),
    ("Wi7cJx4l", "unknown", None, True, "2026-10-05"),
]
ADDRESS = "jane.doe@example.com"


def waitlist_view(generated_at: str = "2026-10-11T22:00:00+00:00", entries=WAITLIST_ENTRIES) -> dict:
    keys = ("entry", "source", "fit", "beta_opt_in", "signed_up_on")
    return {"view": 1, "generated_at": generated_at, "entries": [dict(zip(keys, entry)) for entry in entries]}


def address_variant() -> dict:
    """The seed with an address-bearing field on one sign-up."""
    view = waitlist_view()
    view["entries"][2]["email"] = ADDRESS
    return view


def write_view(path: Path, view: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(view, indent=1), encoding="utf-8")
    return path


def add_dispatches(repo: Path, env: dict[str, str]) -> None:
    """The reviewed Dispatch requests, committed in a throwaway checkout as they are in this repository."""
    shutil.copytree(str(REPO / "src" / "dispatches"), str(repo / "src" / "dispatches"))
    git(repo, "add", "--all", env=env)
    git(repo, "commit", "--quiet", "-m", "dispatches", env=env)


# Post Drafts for the synthetic kit in src/examples/post-drafts/files/mandu.

# Each calendar day's Angle, pair leg, and frozen Hook in the synthetic kit.
KIT_DAYS = {
    1: ("P01", "AB-1", "A", "Open it and the session is already waiting."),
    2: ("P02", None, None, "I missed five days and the app welcomed me back."),
    3: ("P03", "AB-2", "A", "Skip a day and the score dips. It never resets."),
    4: ("P04", None, None, "Airplane mode on. The session still appears."),
    5: ("P05", None, None, "The session builds before the screen settles."),
    6: ("P06", None, None, "A hallway is enough room for today."),
    7: ("P07", None, None, "Five minutes still counts as showing up."),
    8: ("P01", "AB-1", "B", "The session is on screen before you decide."),
    9: ("P02", None, None, "I missed five days and the app welcomed me back."),
    10: ("P03", "AB-2", "B", "A skipped day never takes you back to zero."),
    11: ("P04", None, None, "Airplane mode on. The session still appears."),
    12: ("P06", None, None, "A hallway is enough room for today."),
    13: ("P07", None, None, "Five minutes still counts as showing up."),
}
CLEAN_DRAFT = EXAMPLES / "files" / "drafts" / "day-03-clean.md"


def draft(day: int, caption: str = "This is the history view after three missed days this month.") -> str:
    """A Draft for a calendar day of the synthetic kit that passes every check, built from the example set's clean
    day 3 Draft; caption replaces its second caption line on both platforms."""
    angle, pair, leg, hook = KIT_DAYS[day]
    text = CLEAN_DRAFT.read_text(encoding="utf-8")
    text = text.replace("This is the history view after three missed days this month.", caption)
    text = text.replace("Skip a day and the score dips. It never resets.", hook)
    legs = f"pair: {pair}\nleg: {leg}\n" if pair else ""
    return text.replace("day: 3\nangle: P03\npair: AB-2\nleg: A\n", f"day: {day}\nangle: {angle}\n{legs}")


def with_beats(text: str, *later: tuple[str, str]) -> str:
    """A Draft with its beats after the hook beat replaced by the given (visual action, on-screen text) pairs."""
    head, rest = text.split("### Beat 2", 1)
    beats = "".join(
        f"### Beat {number}: {3 * number - 3}-{3 * number}s\n\n- Visual action: {visual}\n- Spoken line: none\n"
        f"- On-screen text: {shown}\n\n"
        for number, (visual, shown) in enumerate(later, start=2)
    )
    return head + beats + "## TikTok" + rest.split("## TikTok", 1)[1]


def recut_mandu(path: Path) -> Path:
    """A Mandu whose synthetic calendar marks AB-1, days 1 and 8, as a re-cut pair."""
    calendar = make_mandu(path) / "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
    text = calendar.read_text(encoding="utf-8")
    calendar.write_text(text.replace("with only its hook swapped", "re-cut opening"), encoding="utf-8")
    return path


def draft_path(day: int, window: int = 1) -> str:
    """Where the agent writes a day's Draft, relative to workspace/."""
    return f"drafts/posts/window-{window}/day-{day:02d}.md"


def window_from(first_sitting: date) -> dict:
    """A window whose first sitting is that Sunday, so its day 1 is the Monday after, with a 19:00 slot."""
    return {"number": 1, "first_sitting": first_sitting.isoformat(), "slot": "19:00"}


def keep_days(mandu: Path, *days: int) -> None:
    """Cut the synthetic calendar in a throwaway Mandu down to the given days, for a run that needs few due."""
    path = mandu / "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
    rows = [(re.match(r"\| (\d+) \|", line), line) for line in path.read_text(encoding="utf-8").splitlines()]
    kept = [line for row, line in rows if row is None or int(row.group(1)) in days]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def kit_context(code_checkout: Path, env: dict[str, str], mandu: Path | None = None):
    """The post-Draft checks' context for the synthetic kit, as a run builds it, with the given code checkout."""
    from gr0wthlab import codebase, drafts, lint, posts

    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    product, roles = posts.kit_config(registry)
    parsed, _, data, problem = posts.read_kit(mandu or EXAMPLES / "files" / "mandu", roles)
    rules = lint.Rules(data) if data is not None else None
    platforms = lint.load_platforms(json.loads((REPO / "config" / "platforms.json").read_text(encoding="utf-8")))
    code = codebase.open_code(product, code_checkout, "main", env)
    return drafts.Context(product, 1, parsed, rules, problem, platforms, code, dict(roles))


# Beta Cohort recruiting, on the synthetic thesis, K8 rubric, and channel plan in src/examples/beta-recruiting.

BETA_BUILD = {
    "exchange": 4,
    "product": "RepToday",
    "approved_on": "2026-10-09",
    "build": "1.0 (42)",
    "recruiting": "open",
    "stopped_on": None,
    "recorded_at": "2026-10-10T19:40:00-07:00",
}
INVITATION = "drafts/beta-recruiting/RepToday/invitation.md"
WAITLIST_ASK = "drafts/beta-recruiting/RepToday/waitlist-ask.md"
# The seeded view's sign-ups that asked for a beta invitation, in invitation order: good Fit first, then by date.
GOOD_FIT_OPT_INS = ["Qm7tLx2a", "Ka0zMn2p", "Xf9mKa3i", "Jd2wGs6u", "Lr6jFq5s"]
OTHER_OPT_INS = ["Ne5qTb1o", "Wi7cJx4l", "Hc8nRy4e"]


def beta_mandu(path: Path) -> Path:
    """A Mandu holding the synthetic kit and, over it, the Beta Cohort example set's thesis, K8 rubric, channel plan,
    and brand guidelines."""
    if not path.exists():
        make_mandu(path)
    shutil.copytree(str(BETA_EXAMPLES / "files" / "mandu"), str(path), dirs_exist_ok=True)
    return path


def beta_draft(name: str = "invitation-clean", old: str = "", new: str = "") -> str:
    """One of the example set's recruiting Drafts, with old replaced by new."""
    text = (BETA_EXAMPLES / "files" / "drafts" / f"{name}.md").read_text(encoding="utf-8")
    assert not old or old in text, old
    return text.replace(old, new) if old else text


def beta_report(day: str, **counts) -> dict:
    return {"exchange": 4, "product": "RepToday", "date": day, **counts, "recorded_at": f"{day}T19:55:00-07:00"}


def write_record(folder: Path, name: str, record) -> Path:
    """One of Mandu's records in its exchange folder; a string is written as it is."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(record if isinstance(record, str) else json.dumps(record), encoding="utf-8")
    return path


def batch_entry(batch: dict, product: str = "RepToday") -> dict:
    """A Review Queue entry for an invitation batch a scenario says was already queued."""
    return {
        "kind": "message",
        "ask": f"Approve Beta Cohort invitation, batch {batch['batch']}",
        "file": f"review-queue/items/{batch['id']}.md",
        "product": product,
        "published_by_run": "20261004T230000Z-scheduled-0000",
        "beta": "beta-invitation",
        "draft": INVITATION,
        "draft_sha256": "0" * 64,
        **batch,
    }


def beta_plan(root: Path, scenario: dict, view: dict | None):
    """A run's recruiting plan for a scenario, built as the cycle builds it: the gate from the scenario's Beta Build
    record, the reading from the view, and the batches already queued. Returns the plan, the store it wrote its
    Evidence to, and the ledger."""
    from gr0wthlab import beta, boundary, settings, waitlist
    from gr0wthlab.areas import Store
    from gr0wthlab.queue import Ledger
    from gr0wthlab.state import BetaRecruitingState

    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    runtime = json.loads((REPO / "config" / "guardrails" / "runtime.json").read_text(encoding="utf-8"))
    repo = root / "gr0wthlab"
    for area in runtime["writable_areas"].values():
        (repo / area).mkdir(parents=True, exist_ok=True)
    env = {"GR0WTHLAB_MANDU_DIR": str(beta_mandu(root / "Mandu"))}
    resolved = boundary.resolve_boundary(repo, runtime, registry, env, root, git=[])
    config = settings.load(REPO, {}, root)
    config = dataclasses.replace(config, beta_batch_size=scenario.get("batch_size", config.beta_batch_size))
    rules = beta.rules(registry, config)
    started = datetime.fromisoformat(scenario["run_started"])
    reading = None
    if view is not None:
        block = next(product for product in registry["products"] if product["name"] == rules.product)["waitlist"]
        counted = settings.Waitlist(
            rules.product,
            write_view(root / "exports" / "waitlist-view.json", view),
            tuple(block["source_tags"]),
            tuple(block["fit_answers"]),
            tuple(block["good_fit"]),
            block["beta_cohort_bar"],
        )
        reading = waitlist.read(counted, started)
    exchange_dir = root / "exchange"
    build = scenario.get("beta_build")
    name = f"{rules.product}.json"
    found = [(name, exchange_dir / beta.BUILDS / name, json.dumps(build).encode("utf-8"))] if build else []
    gate = beta.read_gate(rules.product, found, [], None)
    reports = [
        (
            f"{report['product']}-{report['date']}.json",
            exchange_dir / beta.REPORTS / f"{report['product']}-{report['date']}.json",
            json.dumps(report).encode("utf-8"),
        )
        for report in scenario.get("reports", [])
    ]
    ledger = Ledger([batch_entry(batch) for batch in scenario.get("batches", [])])
    store = Store(resolved.ledger)
    read = reading is not None and reading.status == "read"
    plan = beta.prepare(
        rules,
        gate,
        reports if gate.recorded else None,
        None,
        registry,
        resolved,
        ledger,
        BetaRecruitingState(),
        reading,
        "evidence/waitlist/RUN.json" if read else "",
        store,
        "20261011T230000Z-on-demand-0000",
        started,
    )
    return plan, store, ledger


# Filming (US-ME09): the filming example set's synthetic kit, laid over the post-Draft one, and video tooling.

FILMING = REPO / "src" / "examples" / "filming"
FAKE_FFMPEG_VERSION = "ffmpeg version 0.0-fake"

# Stands in for ffprobe. A test's footage file is a small JSON text of the facts ffprobe would measure, and so is
# what the fake ffmpeg renders; this prints those facts as ffprobe's own JSON, and fails on anything else.
FAKE_FFPROBE = """#!{python}
import json, sys
try:
    facts = json.loads(open(sys.argv[-1]).read())
except (OSError, ValueError):
    sys.stderr.write(sys.argv[-1] + ": Invalid data found when processing input\\n")
    sys.exit(1)
picture = {{
    "codec_type": "video", "codec_name": facts.get("codec", "h264"), "pix_fmt": facts.get("pix_fmt", "yuv420p"),
    "width": facts["width"], "height": facts["height"], "avg_frame_rate": str(facts.get("fps", 30)) + "/1",
    "duration": str(facts["duration"]), "sample_aspect_ratio": "1:1", "color_transfer": facts.get("transfer", ""),
}}
streams = [picture] + ([{{"codec_type": "audio", "codec_name": "aac"}}] if facts.get("sound") else [])
print(json.dumps({{"streams": streams, "format": {{"duration": str(facts["duration"])}}}}))
"""

# Stands in for ffmpeg. It answers the version and the listings a run checks, and "renders" by writing the facts of
# the asset the command asks for, with the command's inputs and the text file it was given, so a test can read what
# a render was made from, and with a digest of each input's bytes, so that other footage renders as another file, as
# it does for real. ffmpeg.json beside it overrides the facts written, or makes the render fail part way, as
# ffmpeg does: with half a file already at the output, whose path it then adds to partial.log beside it. With "only",
# just the renders whose output path holds that text fail.
FAKE_FFMPEG = """#!{python}
import hashlib, json, re, sys
from pathlib import Path

here = Path(__file__).resolve().parent
args = sys.argv[1:]
behavior = json.loads((here / "ffmpeg.json").read_text()) if (here / "ffmpeg.json").exists() else {{}}
if "-version" in args:
    print("{version} Copyright (c) the tests")
    sys.exit(0)
if "-filters" in args:
    for name in {filters!r}:
        if name not in behavior.get("lacks", []):
            print(" ... " + name + " V->V a filter")
    sys.exit(0)
if "-encoders" in args:
    for name in ("libx264", "aac"):
        print(" V....D " + name + " an encoder")
    sys.exit(0)
if behavior.get("fail") and behavior.get("only", "") in args[-1]:
    Path(args[-1]).write_text("half of a render that did not finish")
    with (here / "partial.log").open("a") as log:
        log.write(args[-1] + "\\n")
    sys.stderr.write(behavior["fail"] + "\\n")
    sys.exit(1)
graph = args[args.index("-filter_complex") + 1]
width, height = re.search(r"pad=(\\d+):(\\d+)", graph).groups()
inputs = [args[i + 1] for i, arg in enumerate(args) if arg == "-i"]
facts = {{
    "duration": float(args[len(args) - 4]), "width": int(width), "height": int(height),
    "fps": int(re.search(r"fps=(\\d+)", graph).group(1)), "codec": "h264", "pix_fmt": "yuv420p",
    "sound": "[ac]" in graph, "inputs": inputs,
    "footage": [hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in inputs],
    "seeks": [args[i + 1] for i, arg in enumerate(args) if arg == "-ss"], "graph": graph,
    "text": Path("overlay.ass").read_text() if Path("overlay.ass").exists() else "",
}}
facts.update(behavior.get("facts", {{}}))
Path(args[-1]).write_text(json.dumps(facts))
"""


def filming_mandu(path: Path) -> Path:
    """A Mandu whose kit is the filming example set's: the post-Draft one with Formats that name each recording, a
    founder-on-camera pair whose opening is re-cut (AB-3, days 2 and 9), and the rule for every screen recording."""
    shutil.copytree(str(FILMING / "files" / "mandu"), str(make_mandu(path)), dirs_exist_ok=True)
    return path


def filming_kit(root: Path):
    """The filming example set's kit, parsed as a run parses it, with each role's path."""
    from gr0wthlab import posts

    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    _, roles = posts.kit_config(registry)
    parsed, _, _, _ = posts.read_kit(filming_mandu(root), roles)
    return parsed, dict(roles)


def install_video_tools(directory: Path) -> dict[str, str]:
    """A fake ffmpeg and ffprobe, and the environment that points a run at them."""
    from gr0wthlab import video

    directory.mkdir(parents=True, exist_ok=True)
    names = video.FILTERS + video.SOUND_FILTERS + video.HDR_FILTERS
    scripts = {
        "ffmpeg": FAKE_FFMPEG.format(python=sys.executable, version=FAKE_FFMPEG_VERSION, filters=names),
        "ffprobe": FAKE_FFPROBE.format(python=sys.executable),
    }
    for name, text in scripts.items():
        (directory / name).write_text(text, encoding="utf-8")
        (directory / name).chmod(0o755)
    return {"GR0WTHLAB_FFMPEG_BIN": str(directory / "ffmpeg"), "GR0WTHLAB_FFPROBE_BIN": str(directory / "ffprobe")}


def fake_clip(path: Path, duration: float, width: int = 886, height: int = 1920, fps: int = 60, **more) -> Path:
    """A footage file for the fake tooling: the facts the fake ffprobe reports of it, plainly labelled."""
    path.parent.mkdir(parents=True, exist_ok=True)
    facts = dict(test_input="not footage: facts for the fake ffprobe", duration=duration, width=width, height=height)
    path.write_text(json.dumps(dict(facts, fps=fps, **more)), encoding="utf-8")
    return path


def edit_record(day: int, *segments: tuple, window: int = 1, product: str = "RepToday") -> str:
    """An edit record whose segments are (shot, file name in the window's folder, in, out[, more keys])."""
    pieces = []
    for shot, source, start, end, *more in segments:
        name = source if "/" in source else f"window-{window}/{source}"
        pieces.append(dict({"shot": shot, "source": name, "in": start, "out": end}, **(more[0] if more else {})))
    return json.dumps({"edit": 1, "product": product, "window": window, "day": day, "segments": pieces}, indent=1)


def edit_path(day: int, window: int = 1) -> str:
    """Where the agent writes a day's edit record, relative to workspace/."""
    return f"drafts/edits/window-{window}/day-{day:02d}.json"


def filming_draft(day: int) -> str:
    """The filming example set's post Draft for a calendar day, which passes every post-Draft check on its kit."""
    return (FILMING / "files" / "drafts" / f"day-{day:02d}.md").read_text(encoding="utf-8")


def tree_digest(root: Path) -> dict[str, tuple]:
    """Every entry under a folder with its bytes' SHA-256, size, mode, and modification time, so a test can show a
    run left the folder exactly as it was."""
    import hashlib

    found = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else None
        found[str(path.relative_to(root))] = (digest, info.st_size, info.st_mode, info.st_mtime_ns)
    return found


def real_video_tools():
    """The real ffmpeg and ffprobe with the canvas the repository configures, or the reason a test that needs them
    is skipped where they, or the canvas's font, are not installed."""
    from gr0wthlab import video

    canvas = video.load_canvas(json.loads((REPO / "config" / "platforms.json").read_text(encoding="utf-8")))
    tooling = video.find(dict(os.environ), canvas)
    return (
        (tooling, canvas, "")
        if tooling.ok
        else (tooling, canvas, f"the video tooling is not usable here: {tooling.problem}")
    )


def make_test_clip(
    tooling, path: Path, duration: float, width: int, height: int, fps: int, sound: bool = False
) -> Path:
    """A real video file made from ffmpeg's own test pattern, labelled on every frame as test input: a stand-in for
    footage, with a running clock so a cut would show."""
    path.parent.mkdir(parents=True, exist_ok=True)
    label = "drawbox=y=ih/2-60:w=iw:h=120:color=black@0.7:t=fill"
    command = [str(tooling.ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    command += ["-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={fps}:duration={duration}"]
    if sound:
        command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    command += ["-vf", label, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    command += (["-c:a", "aac", "-shortest"] if sound else []) + [str(path)]
    subprocess.run(command, check=True, capture_output=True)
    return path
