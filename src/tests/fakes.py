"""Throwaway repositories, a throwaway Mandu, and a fake Codex, so whole runs can be tested without a model."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AREAS = ("evidence", "drafts", "review-queue", "weekly-reads", "run-reports", "instructions")

# Stands in for codex. `codex sandbox` answers the preflight as an enforcing sandbox would, without running anything;
# `codex exec` plays the agent from behavior.json beside it, writing straight into the workspace.
FAKE_CODEX = """#!{python}
import json, re, shutil, sys
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
workspace = brief.parents[1]
run = brief.name[: -len(".brief.md")]
def at(relative):
    return workspace / relative.replace("{{run}}", run)
for relative in behavior.get("rmtree", []):
    shutil.rmtree(at(relative))
for relative, text in behavior.get("write", {{}}).items():
    target = at(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
for relative, target in behavior.get("symlink", {{}}).items():
    at(relative).parent.mkdir(parents=True, exist_ok=True)
    at(relative).symlink_to(target)
for relative in behavior.get("delete", []):
    (workspace / relative).unlink()
Path(args[args.index("--output-last-message") + 1]).write_text(behavior.get("summary", "Checked the package."))
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


def make_repo(path: Path, env: dict[str, str]) -> Path:
    """A gr0wthlab checkout with the real configuration, task definition, and area READMEs, committed on main."""
    shutil.copytree(str(REPO / "config"), str(path / "config"))
    shutil.copytree(str(REPO / "src" / "instructions"), str(path / "src" / "instructions"))
    for area in AREAS:
        (path / "workspace" / area).mkdir(parents=True)
        (path / "workspace" / area / "README.md").write_text(f"# {area}\n")
    git(path, "init", "--quiet", env=env)
    git(path, "add", "--all", env=env)
    git(path, "commit", "--quiet", "-m", "initial", env=env)
    return path


def make_mandu(path: Path) -> Path:
    """A Mandu checkout holding every package source the real Product registry names."""
    registry = json.loads((REPO / "config" / "products.json").read_text(encoding="utf-8"))
    for product in registry["products"]:
        for source in (product.get("go_to_market_package") or {}).get("sources", []):
            target = path / source["path"]
            if source["path"].endswith("/"):
                target = target / "plan.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"{source['path']}\n", encoding="utf-8")
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
