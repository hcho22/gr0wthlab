"""Whether the GitHub repository the production clone pushes its records to is private, asked of GitHub by the
launcher outside the sandbox.

From the first real run on, every run commits the Drafts, the Evidence, and the Founder's records and pushes them,
so the production clone's run refuses to start while GitHub's answer says plainly that the repository is public, and
pushes its records only when GitHub, asked again once the run's work is done, says plainly that it is private. An
answer that cannot be had or is not clear is never taken as private: the run goes ahead and keeps its records local.
The question is one read, `gh api repos/<owner>/<name>`, with the GitHub login the records step pushes with (git's
`gh auth git-credential` helper for https://github.com, docs/operations.md), bounded by TIMEOUT.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from . import process

GH_ENV = "GR0WTHLAB_GH_BIN"
SEARCH = ("/opt/homebrew/bin", "/usr/local/bin")
TIMEOUT = 60
LOCAL_TIMEOUT = 60
SAID = 300  # characters of what gh or git wrote that a reason repeats
# The push address of a repository on github.com, over HTTPS or SSH, with any user part left out.
ADDRESS = re.compile(
    r"^(?:https://(?:[^/@]+@)?github\.com/|ssh://(?:[^/@]+@)?github\.com(?::22)?/|[^/@:]+@github\.com:)"
    r"(?P<name>[A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)
WHAT_A_RUN_PUBLISHES = "a real run would publish its Drafts, its Evidence, and the Founder's records there"

PRIVATE = "private"
PUBLIC = "public"
UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True)
class Answer:
    """What GitHub's answer shows: private only when it said so plainly."""

    status: str
    detail: str

    @property
    def private(self) -> bool:
        return self.status == PRIVATE

    @property
    def refusal(self) -> str:
        if self.status == PUBLIC:
            return f"{self.detail}: {WHAT_A_RUN_PUBLISHES}, so the repository must be made private first"
        return f"could not confirm that the GitHub repository is private ({self.detail}), and {WHAT_A_RUN_PUBLISHES}"


def repository(address: str) -> str | None:
    """owner/name of a github.com push address, or None for any other address."""
    match = ADDRESS.match(address.strip())
    return match.group("name") if match else None


def said(completed: process.Completed) -> str:
    text = " ".join((completed.stderr or completed.stdout or "").split()) or "no output"
    return text if len(text) <= SAID else text[: SAID - 1] + "…"


def locate(env: Mapping[str, str]) -> tuple[str | None, str]:
    override = env.get(GH_ENV)
    if override:
        if os.path.isabs(override) and os.access(override, os.X_OK):
            return override, ""
        return None, f"gh is not an executable at `{override}`"
    found = shutil.which("gh", path=os.pathsep.join([env.get("PATH", ""), *SEARCH]))
    return (found, "") if found else (None, f"gh was not found on the PATH or in {' or '.join(SEARCH)}")


def ask(repo: Path, remote: str, env: Mapping[str, str]) -> Answer:
    """Ask GitHub whether the repository `remote` pushes to is private; never raises."""
    try:
        address = process.run(
            ["git", "-C", str(repo), "remote", "get-url", "--push", remote],
            LOCAL_TIMEOUT,
            env=dict(env, GIT_TERMINAL_PROMPT="0", LC_ALL="C"),
        )
    except OSError as error:
        return Answer(UNCONFIRMED, f"git could not be run to read where `{remote}` pushes ({error})")
    if not address.ok:
        return Answer(UNCONFIRMED, f"git could not read where `{remote}` pushes: {said(address)}")
    name = repository(address.stdout)
    if name is None:
        return Answer(UNCONFIRMED, f"`{remote}` does not push to a repository on github.com")
    gh, problem = locate(env)
    if gh is None:
        return Answer(UNCONFIRMED, problem)
    quiet = dict(env, GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1", GH_PAGER="", NO_COLOR="1", CLICOLOR="0")
    try:
        completed = process.run([gh, "api", "--hostname", "github.com", f"repos/{name}"], TIMEOUT, env=quiet)
    except OSError as error:
        return Answer(UNCONFIRMED, f"gh could not be run ({error})")
    if completed.timed_out:
        return Answer(UNCONFIRMED, f"GitHub did not answer within {process.limit_text(TIMEOUT)}")
    if completed.returncode != 0:
        return Answer(UNCONFIRMED, f"gh api exited with {completed.returncode}: {said(completed)}")
    return read(name, completed.stdout)


def read(name: str, text: str) -> Answer:
    """GitHub's answer about one repository: private or public only when its `private` and `visibility` agree."""
    try:
        data = json.loads(text)
    except ValueError:
        return Answer(UNCONFIRMED, f"GitHub's answer about `{name}` could not be read")
    if not isinstance(data, dict):
        return Answer(UNCONFIRMED, f"GitHub's answer about `{name}` could not be read")
    flag, visibility = data.get("private"), data.get("visibility")
    if flag is True and visibility == PRIVATE:
        return Answer(PRIVATE, f"GitHub says the repository `{name}` is private")
    if flag is False and visibility == PUBLIC:
        return Answer(PUBLIC, f"the GitHub repository `{name}` is public")
    return Answer(UNCONFIRMED, f"GitHub's answer about `{name}` does not say plainly that it is private or public")
