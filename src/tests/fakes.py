"""Throwaway repositories, a throwaway Mandu, and a fake Codex, so whole runs can be tested without a model."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AREAS = ("evidence", "drafts", "review-queue", "weekly-reads", "run-reports", "instructions")
EXAMPLES = REPO / "src" / "examples" / "post-drafts"
# A window whose days all fall far in the future, so a run that is not about post Drafts has none due.
QUIET_WINDOW = {"number": 1, "first_sitting": "2099-01-04", "slot": "19:00"}

# Stands in for codex. `codex sandbox` answers the preflight as an enforcing sandbox would, without running anything;
# `codex exec` plays the agent from behavior.json beside it, writing straight into the workspace.
FAKE_CODEX = """#!{python}
import json, os, re, shutil, sys
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
    data[section] = dict(data[section], **values)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_window(repo: Path, window: dict) -> None:
    set_run(repo, "window", window)


def make_repo(path: Path, env: dict[str, str], window: dict | None = None) -> Path:
    """A gr0wthlab checkout with the real configuration, task definition, proposals, and area READMEs, committed on
    main; its window is QUIET_WINDOW unless a test gives another."""
    shutil.copytree(str(REPO / "config"), str(path / "config"))
    set_window(path, QUIET_WINDOW if window is None else window)
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


class Clock:
    """A clock that starts where a test says and moves a second per reading."""

    def __init__(self, start: datetime):
        self.moment = start

    def set(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        self.moment += timedelta(seconds=1)
        return self.moment


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
    calendar.write_text(text.replace("only the hook changes", "re-cut opening"), encoding="utf-8")
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
