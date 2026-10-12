"""A Product's code, read only, at its default branch: where each behavioral claim in a Draft is supported.

The launcher resolves the branch to one commit before the agent starts and checks every claim at that commit, so a
claim is checked against the code the agent was told to read, whatever the checkout's working tree holds. Only git's
object reads are used (rev-parse and cat-file), with optional locks off, so the checkout's index, refs, and working
tree are never written.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import process

MAX_SPAN = 40
MIN_EXCERPT = 4
TIMEOUT = 30
# The Command Line Tools' git, called directly, reads without the xcrun shim's cache writes, which the sandbox refuses
# with warnings; any other machine uses the git on its PATH.
CLT_GIT = Path("/Library/Developer/CommandLineTools/usr/bin/git")
LOCATION = re.compile(r"([^\s:`]+):(\d+)(?:-(\d+))?")
COMMIT = re.compile(r"[0-9a-f]{40,64}")


def environment(env: Mapping[str, str]) -> dict[str, str]:
    return dict(env, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")


def squash(text: str) -> str:
    return " ".join(text.split())


@dataclass
class Code:
    """One checkout at one commit; problem says why it could not be read, and then no claim can be checked."""

    name: str
    checkout: Path
    branch: str
    commit: str | None = None
    problem: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    files: dict[str, list[str] | str] = field(default_factory=dict)
    failed: set[str] = field(default_factory=set)  # each path git could not read, which is not a file that is not there

    @property
    def short(self) -> str:
        return (self.commit or "")[:7]

    def git(self, *args: str) -> process.Completed:
        git = str(CLT_GIT) if CLT_GIT.is_file() else "git"
        command = [git, "--no-optional-locks", "-C", str(self.checkout), *args]
        completed = process.run(command, TIMEOUT, env=environment(self.env))
        if completed.timed_out:
            raise TimeoutError(f"Command '{command}' timed out after {TIMEOUT} seconds")
        return completed

    def lines(self, path: str) -> list[str] | str:
        """A file's lines at the commit, or why it cannot be read there. A file that is not there is told from a
        read git could not make: the first is what the commit says, and the second says nothing of the file."""
        if path not in self.files:
            pure = PurePosixPath(path)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                self.files[path] = "the path must be relative to the repository root"
            else:
                try:
                    completed = self.git("cat-file", "blob", f"{self.commit}:{pure}")
                    lost = "" if completed.returncode == 0 else self.unlisted(pure, completed)
                except (OSError, ValueError) as error:
                    completed, lost = None, str(error)
                if lost:
                    self.files[path] = f"git could not read it ({lost})"
                    self.failed.add(path)
                elif completed.returncode == 0:
                    self.files[path] = completed.stdout.splitlines()
                else:
                    self.files[path] = f"there is no file {path} at {self.short}"
        return self.files[path]

    def unlisted(self, path: PurePosixPath, refused: process.Completed) -> str:
        """Why git's refusal to read a file at the commit is a read it could not make, or "" when the commit's own
        tree, which git could read, holds no file at that path."""
        listed = self.git("ls-tree", "--full-tree", "-z", str(self.commit), "--", str(path))
        entry = listed.stdout.split("\t", 1)[0].split()
        if listed.returncode == 0 and entry[1:2] != ["blob"]:
            return ""
        said = refused if listed.returncode == 0 else listed
        return squash(said.stderr or "") or f"git exited with {said.returncode}"

    def verify(self, location: str, excerpt: str) -> str | None:
        """Why a claim's code location does not show its excerpt at the commit, or None when it does."""
        if self.problem:
            return self.problem
        match = LOCATION.fullmatch(location.strip())
        if not match:
            return f"{location!r} is not path:line or path:start-end"
        path, start = match.group(1), int(match.group(2))
        end = int(match.group(3) or start)
        if start < 1 or end < start or end - start + 1 > MAX_SPAN:
            return f"lines {start}-{end} must run forward and span at most {MAX_SPAN} lines"
        if len(squash(excerpt)) < MIN_EXCERPT:
            return f"the excerpt must quote at least {MIN_EXCERPT} characters of the code"
        lines = self.lines(path)
        if isinstance(lines, str):
            return lines
        if end > len(lines):
            return f"{path} has {len(lines)} lines at {self.short}, so line {end} does not exist"
        if squash(excerpt) not in squash(" ".join(lines[start - 1 : end])):
            return f"{path} lines {start}-{end} at {self.short} do not contain {squash(excerpt)!r}"
        return None

    def unread(self, location: str) -> str:
        """Why the code a verified claim's location names could not be read at all: the checkout, or git's read of
        that one file. "" when it was read, or when the file is not there."""
        if self.problem:
            return f"{self.name}'s code could not be read"
        match = LOCATION.fullmatch(location.strip())
        if match and match.group(1) in self.failed:
            return f"git could not read `{match.group(1)}` in {self.name}'s code"
        return ""


def open_code(name: str, checkout: Path, branch: str, env: Mapping[str, str]) -> Code:
    """The checkout's branch resolved to one commit, or the reason it cannot be."""
    code = Code(name, checkout, branch, env=env)
    if not checkout.is_dir():
        code.problem = f"the {name} checkout {checkout} does not exist"
        return code
    if not os.access(str(checkout), os.R_OK | os.X_OK):
        code.problem = f"the {name} checkout {checkout} cannot be read"
        return code
    try:
        completed = code.git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}")
    except OSError as error:
        code.problem = f"git could not read the {name} checkout ({error})"
        return code
    if completed.returncode != 0 or not COMMIT.fullmatch(completed.stdout.strip()):
        code.problem = f"the {name} checkout {checkout} has no branch {branch}"
        return code
    code.commit = completed.stdout.strip()
    return code
