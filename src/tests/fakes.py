"""Throwaway repositories, a throwaway Mandu, and a fake Codex, so whole runs can be tested without a model."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
AREAS = ("evidence", "drafts", "review-queue", "weekly-reads", "run-reports", "instructions")
EXAMPLES = REPO / "src" / "examples" / "post-drafts"
BETA_EXAMPLES = REPO / "src" / "examples" / "beta-recruiting"
# A window whose days all fall far in the future, so a run that is not about post Drafts has none due.
QUIET_WINDOW = {"number": 1, "first_sitting": "2099-01-04", "slot": "19:00"}

# Stands in for codex. `codex sandbox` answers the preflight as an enforcing sandbox would, without running anything,
# unless behavior.json says the sandbox reaches the network or reads where raw footage is kept, or that the probe of
# either falls short ("network_probe", "footage_probe"): it "hangs", "stalls" once it has answered for its first target,
# "fails" with an error, or "skips" every target. probe_next() has only the next probe of a kind fall short. One that
# hangs or stalls first notes that it is waiting, so stopped_at_its_limit() can have it stopped without a race;
# `codex exec` plays the agent of one session from behavior.json beside it, writing straight into the workspace. An
# agent told to hang does its writing, starts its children, the first in a session of its own as Codex starts a shell
# command, notes every process id in pids.txt, and then never exits and never reports its summary or its token counts.
# One told to detach first leaves what a shell command that has finished can leave, noted last: a process in a session
# of its own whose parent has ended. One told to work takes that many seconds before it finishes.
#
# A run starts one session for each workflow with work due, so the fake is started several times in one run. What
# behavior.json says at its top is how every session behaves, and "sessions" gives one workflow's session its own
# behavior over that: {"sessions": {"post-drafts": {"hang": true}}}. What a behavior writes, removes, links, or
# changes the mode of is done once in a run, by the session whose workflow the path belongs to (ROUTES), or by the
# run's first session when that workflow has no session this run, so a test still says only what "the agent" wrote.
# Each session's prompt is kept as prompt.<workflow>.txt, the last one also as prompt.txt, and sessions.txt lists the
# sessions started, in order, since behave() was last called. A session told to break the next preflight leaves the
# sandbox refusing every area once, so the session after it does not start and the one after that does; one told it is
# refused ends as Codex does when the model's provider refuses a request, with that error and exit code 1.
ROUTES = (
    ("drafts/posts/", "post-drafts"),
    ("drafts/edits/", "filming"),
    ("drafts/beta-recruiting/", "beta-recruiting"),
    ("evidence/listening/", "listening"),
    ("review-queue/angles/", "listening"),
    ("drafts/messages/replies/", "listening"),
    ("drafts/messages/outreach/", "outreach"),
    ("evidence/learning/", "learning"),
)
FAKE_CODEX = """#!{python}
import json, os, re, shutil, signal, subprocess, sys, time
from pathlib import Path

here = Path(__file__).resolve().parent
args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("codex-cli 0.0.0-fake")
    sys.exit(0)
if args[:1] == ["sandbox"] and args[args.index("--") + 4] in ("network", "footage"):
    kind, targets = args[args.index("--") + 4], args[args.index("--") + 6:]
    probe = json.loads((here / "behavior.json").read_text())
    if kind == "network":
        outcome = "REACHED " if probe.get("sandbox_reaches_network") else "UNREACHABLE "
        answers = [outcome + target + " 4242" for target in targets]
    else:
        outcome = "LISTED 4242 " if probe.get("sandbox_reads_footage") else "REFUSED 4242 "
        answers = [outcome + target for target in targets]
    how, once = probe.get(kind + "_probe"), here / (kind + "-probe-next")
    if once.exists():
        how = once.read_text()
        once.unlink()
    if how == "fails":
        sys.stderr.write("the profile could not be applied\\n")
        sys.exit(71)
    if how == "skips":
        sys.exit(0)
    if how in ("hangs", "stalls"):
        if how == "stalls":
            print(answers[0], flush=True)
        (here / (kind + "-probe-waiting")).write_text("")
        time.sleep(600)
    print("\\n".join(answers))
    sys.exit(0)
if args[:1] == ["sandbox"]:
    targets = args[args.index("--") + 6:]
    if (here / "preflight-broken").exists():
        (here / "preflight-broken").unlink()
        for target in targets:
            print("REFUSED " + target)
        sys.exit(0)
    for target in targets:
        path = Path(target)
        writable = path.parent.name == "workspace" and path.name in {areas!r}
        print(("WROTE " if writable else "REFUSED ") + target)
    sys.exit(0)
prompt = sys.stdin.read()
(here / "prompt.txt").write_text(prompt)
behavior = json.loads((here / "behavior.json").read_text())
named = re.search(r"^- Session: (\\S+), the .* session, \\d+ of the \\d+ this run starts \\(([^)]*)\\)", prompt, re.M)
session = named.group(1) if named else None
running = named.group(2).split(", ") if named else []
if session:
    if session == running[0]:
        for earlier in here.glob("prompt.*.txt"):
            earlier.unlink()  # what an earlier run's sessions were told
    (here / ("prompt." + session + ".txt")).write_text(prompt)
    with (here / "sessions.txt").open("a") as started:
        started.write(session + "\\n")
    behavior = dict(behavior, **behavior.get("sessions", {{}}).get(session, {{}}))


def mine(relative):
    # Whether this session is the one that does a behavior's work on a path in workspace/.
    if not session:
        return True
    owner = next((workflow for prefix, workflow in {routes!r} if relative.startswith(prefix)), running[0])
    return session == (owner if owner in running else running[0])


brief = Path(re.search(r"Run brief, read it first: (\\S+)", prompt).group(1))
workspace = brief.parents[2] / "workspace"
for relative in behavior.get("rmtree", []):
    if mine(relative):
        shutil.rmtree(workspace / relative)
for relative, text in behavior.get("write", {{}}).items():
    if mine(relative):
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
for relative, target in behavior.get("symlink", {{}}).items():
    if mine(relative):
        (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
        (workspace / relative).symlink_to(target)
for relative, mode in behavior.get("chmod", {{}}).items():
    if mine(relative):
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
if behavior.get("breaks_next_preflight"):
    (here / "preflight-broken").write_text("")
pids = " ".join(str(pid) for pid in [os.getpid(), *children])
(here / "pids.txt").write_text(pids)
if session:
    (here / ("pids." + session + ".txt")).write_text(pids)
for line in behavior.get("events", []):
    print(line, flush=True)
while behavior.get("hang"):
    time.sleep(600)
time.sleep(behavior.get("work", 0))
if behavior.get("refused"):
    refusal = "exceeded retry limit, last status: 429 Too Many Requests"
    print(json.dumps({{"type": "error", "message": refusal}}))
    print(json.dumps({{"type": "turn.failed", "error": {{"message": refusal}}}}))
    sys.exit(1)
summary = behavior.get("summary", "Checked the package.\\n\\nSession: complete\\n")
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
    """An environment whose git has an identity, none of the developer's own configuration, and no maintenance of
    its own: git starts that detached after a commit, a fetch, a merge, a rebase, or a push it receives, so it would
    still be writing in a repository while the test that made the repository removes it."""
    config = root / "gitconfig"
    config.write_text(
        "[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n"
        "[maintenance]\n\tauto = false\n"
    )
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


def set_sources(repo: Path, data: dict) -> None:
    """config/sources.json in a throwaway checkout."""
    (repo / "config" / "sources.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def sources_with(subreddits=(), app_store: bool = False) -> dict:
    """The quiet source list with these subreddits, and App Store reviews when asked."""
    data = json.loads(json.dumps(SOURCES_QUIET))
    data["listening"]["subreddits"] = list(subreddits)
    if app_store:
        data["listening"]["app_store"] = {
            "country": "us",
            "reviews": "https://itunes.apple.com/{country}/rss/customerreviews/page=1/id={id}/sortby=mostrecent/json",
            "reviews_page": "https://apps.apple.com/{country}/app/id{id}?see-all=reviews",
            "max_apps": 12,
        }
    return data


def make_repo(path: Path, env: dict[str, str], window: dict | None = None, films: bool = False) -> Path:
    """A gr0wthlab checkout with the real configuration, task definition, proposals, and area READMEs, committed on
    main; its window is QUIET_WINDOW unless a test gives another, no Product films unless a test says so, so a run
    that is not about filming files no filming plan, and it reads no network source and prepares no outreach message
    unless a test gives it some (set_sources, set_run)."""
    shutil.copytree(str(REPO / "config"), str(path / "config"))
    set_window(path, QUIET_WINDOW if window is None else window)
    set_filming(path, films)
    set_sources(path, SOURCES_QUIET)
    set_run(path, "outreach", {"network_ask_source": None, "creators": []})
    shutil.copytree(str(REPO / "src" / "instructions"), str(path / "src" / "instructions"))
    shutil.copytree(str(REPO / "src" / "proposals"), str(path / "src" / "proposals"))
    shutil.copy(str(REPO / ".gitignore"), str(path / ".gitignore"))
    (path / "ledger").mkdir()
    (path / "ledger" / "README.md").write_text("# ledger\n")
    make_founder(path / "ledger")
    for area in AREAS:
        (path / "workspace" / area).mkdir(parents=True)
        (path / "workspace" / area / "README.md").write_text(f"# {area}\n")
    git(path, "init", "--quiet", env=env)
    git(path, "add", "--all", env=env)
    git(path, "commit", "--quiet", "-m", "initial", env=env)
    return path


def make_founder(ledger: Path) -> Path:
    """The Founder's records area as the repository holds it: its five folders, each kept by a .gitkeep."""
    from gr0wthlab import founder

    for folder in founder.folders(ledger).values():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ".gitkeep").write_text("")
    return founder.root(ledger)


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
    codex.write_text(FAKE_CODEX.format(python=sys.executable, areas=set(AREAS), routes=ROUTES), encoding="utf-8")
    codex.chmod(codex.stat().st_mode | stat.S_IXUSR)
    behave(directory, {})
    return codex


def behave(directory: Path, behavior: dict) -> None:
    """How the fake agent behaves from now on: every session as the behavior says, and one workflow's session as
    behavior["sessions"][<workflow>] says over that. The list of sessions started so far starts again."""
    (directory / "behavior.json").write_text(json.dumps(behavior), encoding="utf-8")
    started = directory / "sessions.txt"
    if started.exists():
        started.unlink()


def probe_next(directory: Path, kind: str, how: str) -> None:
    """Only the next no-model probe of that kind, "network" or "footage", falls short, as how says; the ones after
    it behave as behave() set them."""
    (directory / f"{kind}-probe-next").write_text(how, encoding="utf-8")


def stopped_at_its_limit(directory: Path, kind: str):
    """A patch under which a no-model probe of that kind that the fake leaves unfinished is stopped at its time limit
    without a test waiting the limit out, and never before the fake has written all it is going to: once the fake
    has noted that it is waiting, that probe's wall clock reads past its limit. Every other process, a later probe
    of the same kind included, is timed as it is."""
    from gr0wthlab import process

    real, waiting = process.run, directory / f"{kind}-probe-waiting"

    def run(command, timeout, **kwargs):
        if kind not in command:
            return real(command, timeout, **kwargs)
        clock = process.Clock(time.monotonic, lambda: time.time() + (2 * timeout if waiting.exists() else 0))
        try:
            return real(command, timeout, **dict(kwargs, clock=clock))
        finally:
            if waiting.exists():
                waiting.unlink()

    return mock.patch.object(process, "run", run)


def sessions_started(directory: Path) -> list[str]:
    """The sessions the fake agent was started for since behave() was last called, in order, by workflow."""
    started = directory / "sessions.txt"
    return started.read_text(encoding="utf-8").split() if started.exists() else []


def prompt(directory: Path, session: str = "package-review") -> str:
    """The prompt one session of the last run was started with."""
    return (directory / f"prompt.{session}.txt").read_text(encoding="utf-8")


def prompts(directory: Path) -> str:
    """Every prompt the last run's sessions were started with, one after another, so a test can say what none of
    the run's agents was told."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(directory.glob("prompt.*.txt")))


def session(key: str = "package-review", closing: str = "Session: complete", limit: float = 1800.0, **record):
    """One workflow's session as a run's state holds it once its agent has ended: with work due, started, ended by
    itself, and closed with that line, unless the record given says otherwise."""
    from gr0wthlab import sessions

    kept = dict({"agent_started": True, "exit_code": 0, "time_limit_seconds": limit}, **record)
    kept.setdefault("agent_awake_seconds", kept.get("agent_seconds"))
    summary = f"Did the work.\n\n{closing}\n" if closing else ""
    return sessions.Session(sessions.workflow(key), True, "", limit, kept, summary=summary, closing=closing)


# Codex's event stream, as `codex exec --json` writes it: one line for each step that ran to its end.


def command_event(command: str, output: str = "", exit_code: int = 0) -> str:
    """One finished shell command, with all of its output, as the stream holds it whatever the model was shown."""
    item = {
        "id": "item_1",
        "type": "command_execution",
        "command": f"/bin/zsh -lc {shlex.quote(command)}",
        "aggregated_output": output,
        "exit_code": exit_code,
        "status": "completed",
    }
    return json.dumps({"type": "item.completed", "item": item})


def read_event(*paths: Path) -> str:
    """The agent reading files whole, one after another, in one command."""
    output = "".join(path.read_text(encoding="utf-8") for path in paths)
    return command_event("cat " + " ".join(str(path) for path in paths), output)


def edit_event(*paths: str) -> str:
    """One finished file edit; the stream names the files and never holds their text."""
    item = {
        "id": "item_2",
        "type": "file_change",
        "changes": [{"path": path, "kind": "add"} for path in paths],
        "status": "completed",
    }
    return json.dumps({"type": "item.completed", "item": item})


def write_events(path: Path, *lines: str) -> Path:
    """A session's event stream on disk, opened and closed as Codex opens and closes one."""
    stream = [json.dumps({"type": "thread.started", "thread_id": "t"}), json.dumps({"type": "turn.started"}), *lines]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(stream) + "\n", encoding="utf-8")
    return path


def package_files(mandu: Path) -> list[Path]:
    """Every package file a run's brief lists for the throwaway Mandu, in the registry's order."""
    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    found = []
    for product in registry["products"]:
        for source in (product.get("go_to_market_package") or {}).get("sources", []):
            target = mandu / source["path"]
            prefix = source.get("files_starting_with", "")
            found += sorted(target.glob(f"{prefix}*")) if source["path"].endswith("/") else [target]
    return [path for path in found if path.is_file()]


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


class Mac:
    """The two clocks of a Mac that sleeps where a test says: awake time is real, and the wall clock is ahead of it by
    every second the Mac has slept."""

    def __init__(self):
        self.slept = 0.0

    def wall(self) -> float:
        return time.time() + self.slept

    @property
    def clocks(self):
        from gr0wthlab import process

        return process.Clock(time.monotonic, self.wall)

    def asleep_in(self, word: str, seconds: float, after: float = 0.0, session: str | None = None):
        """A patch under which every process the launcher waits for is timed on this Mac's clocks, and the Mac falls
        asleep `after` seconds into the first one whose command line has `word`, to wake `seconds` later. With
        session, it is the first such process of that workflow's session, whose command names that session's closing
        message, so the Mac can sleep through a run's second or third agent and not its first."""
        from gr0wthlab import process

        real, left = process.run, [seconds]

        def run(command, timeout, **kwargs):
            clocks = self.clocks
            named = session is None or any(str(part).endswith(f".{session}.last-message.md") for part in command)
            if left and word in command and named:
                begun = []

                def wall() -> float:
                    if not begun:
                        begun.append(time.monotonic())
                    elif left and time.monotonic() - begun[0] >= after:
                        self.slept += left.pop()
                    return self.wall()

                clocks = process.Clock(time.monotonic, wall)
            return real(command, timeout, **dict(kwargs, clock=clocks))

        return mock.patch.object(process, "run", run)


SUNDAY_RUN = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)


PROPOSAL = """---
kind: package-change-proposal
product: RepToday
new_angle: no
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


def proposal(
    kind: str = "package-change-proposal",
    extra: str = "",
    title: str = "record the name as cleared",
    new_angle: str | None = "no",
) -> str:
    """PROPOSAL as an item of another kind, with more front matter, another ask, or another declaration; only a
    package-change proposal declares new_angle, and None leaves the declaration out."""
    from gr0wthlab import exchange

    text = PROPOSAL.replace("kind: package-change-proposal", f"kind: {kind}\n{extra}".rstrip("\n"))
    declared = f"new_angle: {new_angle}\n" if kind == "package-change-proposal" and new_angle else ""
    text = text.replace("new_angle: no\n", declared)
    text = text.replace("record the name as cleared", title)
    text = text.replace("## Proposal", f"## {exchange.KINDS[kind]}")
    return text.replace(
        "- Approve, optionally with a note\n- Reject, with a one-line reason\n",
        "".join(f"- {option}\n" for option in exchange.options(kind)),
    )


def refused_items(marker: str) -> dict:
    """One file the launcher refuses from incoming/ for each kind of item and each way the item format can fail, by
    file name, each with the kind its record keeps and its text; every file carries marker in its title, its body,
    and its Evidence paths, and each failing line carries it too, so a test can show none of it is kept."""
    files = {
        "a-post.md": ("post", proposal("post", extra="window: 1\nday: 3\n", title=marker)),
        "a-message.md": ("message", proposal("message", title=marker)),
        "a-filming-plan.md": ("filming-plan", proposal("filming-plan", title=marker)),
        "a-new-angle.md": ("package-change-proposal", proposal(new_angle="yes", title=marker)),
        "a-line.md": ("weekly-read-decision", proposal("weekly-read-decision", extra=f"{marker}: it\n")),
        "a-repeat.md": ("dispatch-request", proposal("dispatch-request", extra=f"supersedes: 20261011-{marker}\n")),
        "a-source.md": ("notice", proposal("notice").replace("Still says unverified: `", f"{marker}: ")),
        "a-section.md": ("package-change-proposal", PROPOSAL.replace("## Touches", f"## {marker} Touches")),
        "a-kind.md": (None, PROPOSAL.replace("kind: package-change-proposal", f"kind: {marker}")),
    }
    return {
        name: (
            kind,
            text.replace("Replace the stale caveat with the cleared status.", f"{marker} said this.").replace(
                "`projects/RepToday", f"`projects/RepToday/{marker}"
            ),
        )
        for name, (kind, text) in files.items()
    }


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
    """One of the Founder's records in its folder of ledger/founder/; a string is written as it is."""
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
    exchange_dir = Path("founder")  # a record's path is given from ledger/
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


# The web the launcher's client reads, without a network.


class Web:
    """A fake web: pages by address, each host's robots.txt, and a clock that moves only when the client sleeps.

    An answer is a body (HTTP 200), a (status, headers, body) tuple, an exception to raise, or a list of answers given
    one per request, the last one repeating. A host with no robots.txt entry has none (404), so nothing on it is
    disallowed; an address with no page answers 404.
    """

    def __init__(self, pages=None, robots=None):
        self.pages = dict(pages or {})
        self.robots = dict(robots or {})
        self.requests: list[str] = []
        self.slept: list[float] = []
        self.time = 0.0

    def __call__(self, host, target, headers, timeout, limit, deadline):
        from gr0wthlab import fetch

        url = f"https://{host}{target}"
        self.requests.append(url)
        missing = (404, {}, "")
        answer = self.robots.get(host, missing) if target == "/robots.txt" else self.pages.get(url, missing)
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        status, answer_headers, body = (200, {}, answer) if isinstance(answer, (str, bytes)) else answer
        data = body.encode("utf-8") if isinstance(body, str) else body
        return fetch.Response(status, dict(answer_headers), data[: limit + 1])

    def clock(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.time += seconds


FETCH_POLICY = {
    "hosts": ["www.reddit.com", "itunes.apple.com"],
    "user_agent": "growthlab-reader/1 (unit tests; +https://example.com/contact)",
    "max_requests_per_run": 30,
    "seconds_between_requests_per_host": 2,
    "timeout_seconds": 5,
    "read_deadline_seconds": 15,
    "max_response_bytes": 2_000_000,
    "max_wait_seconds": 30,
}


def client(web: Web | None = None, policy=None):
    """The launcher's network client reading a fake web, on that web's clock; policy is a fetch policy, or the
    configuration of one."""
    from gr0wthlab import fetch

    web = web or Web()
    if not isinstance(policy, fetch.Policy):
        policy = fetch.policy_from(policy or FETCH_POLICY)
    return fetch.Client(policy, transport=web, clock=web.clock, sleep=web.sleep, now=lambda: SUNDAY_RUN)


# What the named sources answer, in their own formats, with synthetic content.


def atom_feed(entries) -> str:
    """An Atom feed of (link, title, text, published) entries, as a subreddit's feed writes it."""
    from xml.sax.saxutils import escape

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom">']
    for link, title, text, published in entries:
        markup = f'<!-- SC_OFF --><div class="md"><p>{escape(text)}</p></div><!-- SC_ON --> &#32; submitted by'
        markup += ' &#32; <a href="https://www.reddit.com/user/someone"> /u/someone </a> <br/> <span><a href='
        markup += f'"{link}">[link]</a></span> &#32; <span><a href="{link}">[comments]</a></span>'
        body = f'<content type="html">{escape(markup)}</content>'
        parts.append(
            f"<entry><author><name>/u/someone</name></author>{body}<id>x</id>"
            f'<link rel="alternate" href="{escape(link)}"/><published>{published}</published>'
            f"<title>{escape(title)}</title></entry>"
        )
    return "".join(parts) + "</feed>"


def review_feed(reviews) -> str:
    """Apple's customer-review feed of (review id, title, text, rating, updated) reviews."""
    entries = [
        {
            "author": {"name": {"label": "a reviewer"}},
            "id": {"label": identifier},
            "title": {"label": title},
            "content": {"label": text, "attributes": {"type": "text"}},
            "im:rating": {"label": rating},
            "updated": {"label": updated},
        }
        for identifier, title, text, rating, updated in reviews
    ]
    return json.dumps({"feed": {"entry": entries, "title": {"label": "Customer Reviews"}}})


def rules_json(rules) -> str:
    """A subreddit's rule list of (name, text) rules."""
    return json.dumps({"rules": [{"short_name": name, "description": text} for name, text in rules], "site_rules": []})


THREAD = "https://www.reddit.com/r/fitness30plus/comments/abc123/back_after_two_years/"
THREAD_TEXT = (
    "I used to lift four days a week. Then the baby came and I have not trained in two years. Every app I open wants"
    " me to pick a plan first and I close it again."
)
OTHER_THREAD = "https://www.reddit.com/r/getdisciplined/comments/def456/one_missed_day/"
OTHER_TEXT = "One missed day and the app put me back to zero. I deleted it that night and never opened it again."
RULES_TEXT = [
    ("Be kind", "No personal attacks."),
    ("No self promotion", "Do not link your own products, apps, or surveys here. You will be banned."),
]
SOURCES_QUIET = {
    "product": "RepToday",
    "listening": {
        "subreddits": [],
        "reddit": {
            "threads": "https://www.reddit.com/r/{subreddit}/new/.rss",
            "rules": "https://www.reddit.com/r/{subreddit}/about/rules.json",
            "rules_page": "https://www.reddit.com/r/{subreddit}/about/rules",
        },
        "app_store": None,
        "max_documents_per_source": 25,
        "max_document_chars": 2000,
    },
}


def listening_web(threads: bool = True, rules: bool = True) -> Web:
    """A web where the two subreddits' feeds and rules can be read, since no robots.txt disallows them."""
    pages = {}
    if threads:
        pages["https://www.reddit.com/r/fitness30plus/new/.rss"] = atom_feed(
            [(THREAD, "Back after two years", THREAD_TEXT, "2026-10-09T14:00:00+00:00")]
        )
        pages["https://www.reddit.com/r/getdisciplined/new/.rss"] = atom_feed(
            [(OTHER_THREAD, "One missed day", OTHER_TEXT, "2026-10-10T09:30:00+00:00")]
        )
    if rules:
        for name in ("fitness30plus", "getdisciplined"):
            pages[f"https://www.reddit.com/r/{name}/about/rules.json"] = rules_json(RULES_TEXT)
    return Web(pages)


def quote_record(document: str, link: str, quote: str, **fields: str) -> str:
    """A Listening Evidence record as the agent writes it; a field replaces a front matter line, or removes it when
    it is None."""
    front = {
        "evidence": "listening",
        "product": "RepToday",
        "document": document,
        "link": link,
        "read_on": "2026-10-11",
        "theme": "lost-the-routine",
        "fit": "strong",
        "intent": "venting",
        "answerable": "yes",
    }
    front.update(fields)
    lines = ["---"] + [f"{key}: {value}" for key, value in front.items() if value is not None] + ["---", ""]
    lines += ["## Quote", "", quote, "", "## Context", "", "The opening post of a thread about returning to exercise."]
    return "\n".join(lines) + "\n"


# Message Drafts for the synthetic kit, and the three creators its channel plan names.

KIT_CREATORS = [("slow-strength", "Slow Strength"), ("hallway-moves", "Hallway Moves"), ("desk-reset", "Desk Reset")]


def creators(pairs=KIT_CREATORS) -> list[dict]:
    """(key, name) creators as config/run.json's outreach lists them."""
    return [{"key": key, "name": name} for key, name in pairs]


SOURCE_LINK = "reptoday.app/network"
CLAIM = (
    "- Claim: A missed day lowers the score, and nothing resets it to zero.\n"
    "  Code: `Engine/ConsistencyScore.swift:6-7`\n"
    "  Shows: `value = max(floorValue, value - missPenalty)`"
)
CREATOR_BODY = (
    "Hello. I build Rep Today, a small workout app for people who lost their routine.\n"
    "A missed day lowers a score a little, and nothing ever resets it.\n"
    "If early access would be of use to you, it is yours, with nothing asked in return."
)
NETWORK_BODY = (
    "I have been building Rep Today for people who want movement to fit the life they already have.\n"
    "A missed day lowers a score a little, and nothing ever resets it.\n"
    f"If that sounds like you, the waitlist is at {SOURCE_LINK}."
)
REPLY_BODY = (
    "I was in the same place after a long break. What helped me was having one short session ready before I could"
    " talk myself out of it, and not treating a missed day as starting over."
)


def message(purpose: str, to: str, body: str, **parts: str) -> str:
    """A message Draft as the agent writes it. parts may give angle, offer, title, notes, and claims; a creator
    message offers early access unless told otherwise."""
    creator = purpose in ("creator", "creator-follow-up")
    front = {
        "draft": "message",
        "product": "RepToday",
        "purpose": purpose,
        "to": to,
        "angle": parts.get("angle", "P03"),
    }
    if creator or "offer" in parts:
        front["offer"] = parts.get("offer", "early-access")
    lines = ["---"] + [f"{key}: {value}" for key, value in front.items() if value is not None] + ["---", ""]
    lines += [f"# {parts.get('title', 'A short hello')}", "", "## Message", "", body, ""]
    lines += ["## Notes", "", parts.get("notes", "none"), "", "## Claims", "", parts.get("claims", CLAIM)]
    return "\n".join(lines) + "\n"


def message_path(purpose: str, key: str = "") -> str:
    """Where the agent writes an outreach or reply Draft, relative to workspace/."""
    name = {
        "network-ask": "outreach/network-ask.md",
        "creator": f"outreach/creator-{key}.md",
        "creator-follow-up": f"outreach/follow-up-{key}.md",
        "reply": f"replies/{key}.md",
    }[purpose]
    return f"drafts/messages/{name}"


def workspace_areas(root: Path):
    """The six workspace areas under a throwaway folder, as the launcher's Areas reads them, with no checkout."""
    from types import SimpleNamespace

    from gr0wthlab.areas import Areas

    pairs = tuple((name.replace("-", "_"), root / "workspace" / name) for name in AREAS)
    for _, path in pairs:
        path.mkdir(parents=True, exist_ok=True)
    return Areas(SimpleNamespace(repo_root=root, areas=pairs))
