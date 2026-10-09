"""The production clone's git steps, run by the launcher outside the sandbox.

Before a run, bring main up to the reviewed code on origin by fast-forward only.
After a run, commit the changed workspace/ and ledger/ paths, the agent's outputs and the launcher's records, and push
them to main, never anything else and never by force; a README in either is documentation, which only a reviewed pull
request changes, so a change to one is put back instead.
Only the production clone (config/run.json's records.production_clone) runs either step; every other checkout,
such as a firstmate worktree, runs without touching git.
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .boundary import LEDGER
from .report import plural

RECORD_DIRS = ("workspace/", f"{LEDGER}/")
NETWORK_TIMEOUT = 120
LOCAL_TIMEOUT = 60
# Files that would change how git treats the records themselves are never committed.
GIT_CONTROL_FILES = (".gitattributes", ".gitignore", ".gitmodules")
DOCUMENTATION = "README.md"
PLAIN_MODES = ("100644", "100755")

# Pre-run outcomes.
UPDATED = "updated"
CURRENT = "current"
OFFLINE = "offline"
NOT_REPLAYED = "not replayed"
REFUSED = "refused"
# Post-run outcomes.
PUSHED = "pushed"
NOTHING = "nothing to save"
NOT_PUSHED = "not pushed"


def said(completed: subprocess.CompletedProcess) -> str:
    """Everything git said, on one line, so a report keeps the cause and not only git's closing hint."""
    return " ".join((completed.stderr or completed.stdout or "").split()) or "no output"


class GitError(Exception):
    def __init__(self, command: Sequence[str], completed: subprocess.CompletedProcess | None, detail: str = ""):
        super().__init__(f"git {' '.join(command)} failed: {detail or (said(completed) if completed else 'no output')}")


@dataclass
class Sync:
    """The pre-run step's outcome; ok_to_run is False only when the clone must not run at all."""

    status: str
    detail: str
    before: str | None = None
    after: str | None = None
    unpushed: int = 0
    ok_to_run: bool = True
    excluded: list[str] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)

    @property
    def code_changed(self) -> bool:
        return self.before is not None and self.after is not None and self.before != self.after

    def as_json(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass
class Save:
    status: str
    detail: str
    commit: str | None = None
    pushed: int = 0
    excluded: list[str] = field(default_factory=list)
    outside_records: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, object]:
        return dict(self.__dict__)


class Git:
    def __init__(self, repo: Path, env: Mapping[str, str]):
        self.repo = repo
        # Never prompt, treat every pathspec literally, and run no hooks.
        self.env = dict(env, GIT_TERMINAL_PROMPT="0", GIT_LITERAL_PATHSPECS="1", LC_ALL="C")

    def run(self, *args: str, timeout: int = LOCAL_TIMEOUT, check: bool = True) -> subprocess.CompletedProcess:
        command = ["git", "-C", str(self.repo), "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgSign=false", *args]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, env=self.env, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise GitError(args, None, f"timed out after {timeout}s") from error
        if check and completed.returncode != 0:
            raise GitError(args, completed)
        return completed

    def out(self, *args: str, timeout: int = LOCAL_TIMEOUT) -> str:
        return self.run(*args, timeout=timeout).stdout.strip()

    def fields(self, *args: str) -> list[str]:
        """NUL-separated output, unstripped: a porcelain status line can start with a space."""
        return self.run(*args).stdout.split("\0")

    def branch(self) -> str | None:
        completed = self.run("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        return completed.stdout.strip() if completed.returncode == 0 else None

    def head(self) -> str:
        return self.out("rev-parse", "HEAD")

    def status(self) -> list[str]:
        """Every path git status reports, staged, unstaged, or untracked, including both sides of a rename."""
        paths, fields = [], self.fields("status", "--porcelain=v1", "-z", "--untracked-files=all")
        index = 0
        while index < len(fields):
            entry = fields[index]
            index += 1
            if not entry:
                continue
            paths.append(entry[3:])
            if entry[0] in "RC":
                paths.append(fields[index])
                index += 1
        return paths

    def commits(self, revisions: str) -> list[str]:
        return self.out("rev-list", revisions).split()

    def changed_paths(self, commit: str) -> list[str]:
        return self.fields("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", commit)


def outside(paths: Sequence[str]) -> list[str]:
    return sorted({path for path in paths if path and not path.startswith(RECORD_DIRS)})


def local_commits_outside(git: Git, upstream: str) -> list[str]:
    """Commits on main but not on the remote that touch anything outside workspace/ and ledger/."""
    return [commit for commit in git.commits(f"{upstream}..HEAD") if outside(git.changed_paths(commit))]


def restore_access(repo: Path) -> list[str]:
    """Give the owner read and write access, and search on folders (u+rwX), to every entry under workspace/ the agent
    left without it, without following links, so the records step and code updates can read and replace everything
    there; one line for each entry fixed, or that could not be."""
    lines = []
    for root, subdirs, files in os.walk(str(repo / RECORD_DIRS[0])):
        subdirs.sort()
        for name in subdirs + sorted(files):
            path = os.path.join(root, name)
            entry = os.path.relpath(path, str(repo))
            try:
                mode = os.lstat(path).st_mode
                wanted = stat.S_IRUSR | stat.S_IWUSR | (stat.S_IXUSR if stat.S_ISDIR(mode) else 0)
                if stat.S_ISLNK(mode) or mode & wanted == wanted:
                    continue
                os.chmod(path, stat.S_IMODE(mode) | wanted)
            except OSError as error:
                reason = error.strerror or error
                lines.append(f"`{entry}` was left without its owner's access, which could not be restored ({reason})")
                continue
            lines.append(f"`{entry}` was left without its owner's read and write access, so the launcher restored it")
    return lines


def prepare(repo: Path, remote: str, branch: str, started: str, env: Mapping[str, str], max_bytes: int) -> Sync:
    """Restore the owner's access to everything under workspace/, then bring the clone up to date with the remote."""
    repaired = restore_access(repo)
    result = update(repo, remote, branch, started, env, max_bytes)
    result.repaired = repaired
    return result


def update(repo: Path, remote: str, branch: str, started: str, env: Mapping[str, str], max_bytes: int) -> Sync:
    """Bring the clone to the remote's main, by fast-forward or by replaying unpushed records commits on top.

    It refuses to run a clone that is off main, has changes outside workspace/ and ledger/, or has local commits
    that change anything outside them, because the production clone runs only code reviewed onto the remote.
    """
    git = Git(repo, env)
    upstream = f"{remote}/{branch}"
    try:
        current = git.branch()
        if current != branch:
            return Sync(REFUSED, f"the clone is on {current or 'a detached HEAD'}, not {branch}", ok_to_run=False)
        stray = outside(git.status())
        if stray:
            detail = f"the clone has changes outside workspace/ and ledger/: {', '.join(stray[:5])}"
            return Sync(REFUSED, detail, ok_to_run=False)
        if local_commits_outside(git, upstream):
            detail = f"{branch} has local commits that change files outside workspace/ and ledger/"
            return Sync(REFUSED, detail, ok_to_run=False)
        excluded: list[str] = []
        leftover = save_commit(git, f"chore(records): outputs left by a run before {started}", max_bytes, excluded)
        before = git.head()
        fetched = git.run("fetch", "--quiet", remote, branch, timeout=NETWORK_TIMEOUT, check=False)
        if fetched.returncode != 0:
            return Sync(OFFLINE, f"could not fetch {remote}: {said(fetched)}; ran the current code", before, before)
        if local_commits_outside(git, upstream):
            return Sync(
                REFUSED,
                f"{branch} has commits outside workspace/ and ledger/ that {upstream} lacks",
                before,
                ok_to_run=False,
            )
        result = integrate(git, branch, upstream, before, leftover)
        result.excluded = excluded
        return result
    except GitError as error:
        return Sync(REFUSED, str(error), ok_to_run=False)


def integrate(git: Git, branch: str, upstream: str, before: str, leftover: str | None) -> Sync:
    ahead = len(git.commits(f"{upstream}..HEAD"))
    behind = len(git.commits(f"HEAD..{upstream}"))
    if behind == 0:
        return Sync(
            CURRENT, f"{branch} is current with {upstream}" + note_unpushed(ahead, leftover), before, before, ahead
        )
    if ahead == 0:
        git.run("merge", "--ff-only", "--quiet", upstream)
        after = git.head()
        return Sync(UPDATED, f"fast-forwarded {branch} from {before[:7]} to {after[:7]}", before, after)
    failure = replay(git, upstream)
    if failure:
        detail = (
            f"{plural(ahead, 'unpushed records commit')} could not be replayed onto {upstream} ({failure});"
            " ran the current code"
        )
        return Sync(NOT_REPLAYED, detail, before, before, ahead)
    after = git.head()
    detail = f"moved {branch} from {before[:7]} to {upstream} with {plural(ahead, 'unpushed records commit')} on top"
    return Sync(UPDATED, detail, before, after, ahead)


def note_unpushed(ahead: int, leftover: str | None) -> str:
    parts = []
    if ahead:
        parts.append(f"this run pushes {plural(ahead, 'unpushed records commit')}")
    if leftover:
        parts.append("outputs left by an earlier run were committed first")
    return "; " + "; ".join(parts) if parts else ""


def replay(git: Git, upstream: str) -> str | None:
    """Rebase unpushed records commits onto the remote; on any failure, leave main exactly as it was and say why."""
    completed = git.run("rebase", "--quiet", upstream, check=False)
    if completed.returncode == 0:
        return None
    git.run("rebase", "--abort", check=False)
    lines = (completed.stderr or completed.stdout or "").strip().splitlines()
    return lines[0] if lines else "no output"


def staged(git: Git) -> list[tuple[str, str]]:
    """(new mode, path) for every staged change."""
    fields = git.fields("diff", "--cached", "--raw", "-z", "--no-renames")
    entries = []
    for index in range(0, len(fields) - 1, 2):
        meta, path = fields[index], fields[index + 1]
        if meta.startswith(":"):
            entries.append((meta[1:].split()[1], path))
    return entries


def unsafe(repo: Path, mode: str, path: str, max_bytes: int) -> str | None:
    """Why a staged record path may not be committed, or None."""
    if Path(path).name in GIT_CONTROL_FILES:
        return "a git control file"
    if Path(path).name == DOCUMENTATION:
        return "documentation, which only a reviewed pull request changes; put back"
    if mode == "000000":
        return None  # a deletion
    if mode not in PLAIN_MODES:
        return "not a plain file"
    try:
        info = os.lstat(str(repo / path))
    except OSError as error:
        return error.strerror
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        return "not a plain file with one link"
    if info.st_size > max_bytes:
        return f"{info.st_size} bytes, over the {max_bytes}-byte limit"
    return None


def save_commit(git: Git, message: str, max_bytes: int, excluded: list[str] | None = None) -> str | None:
    """Stage workspace/ and ledger/ only, drop anything unsafe, put back any README, and commit; returns the new
    commit or None."""
    added = git.run("add", "--all", "--ignore-errors", "--", *RECORD_DIRS, check=False)
    if added.returncode not in (0, 1):
        raise GitError(["add"], added)
    if added.returncode and excluded is not None:
        unread = git.fields("ls-files", "-z", "--others", "--exclude-standard", "--", *RECORD_DIRS)
        unread += git.fields("diff", "-z", "--name-only", "--", *RECORD_DIRS)
        excluded += [f"{path} (could not be read)" for path in unread if path]
    entries = staged(git)
    stray = outside([path for _, path in entries])
    if stray:
        git.run("reset", "--quiet", "--", *RECORD_DIRS)
        detail = f"refusing to commit paths outside workspace/ and ledger/: {', '.join(stray[:5])}"
        raise GitError(["commit"], None, detail)
    for mode, path in entries:
        reason = unsafe(git.repo, mode, path, max_bytes or 1 << 62)
        if reason:
            git.run("reset", "--quiet", "--", path)
            if Path(path).name == DOCUMENTATION:
                git.run("checkout", "--quiet", "HEAD", "--", path, check=False)
            if excluded is not None:
                excluded.append(f"{path} ({reason})")
    if not staged(git):
        return None
    git.run("commit", "--quiet", "-m", message)
    return git.head()


def save(repo: Path, remote: str, branch: str, run_id: str, env: Mapping[str, str], max_bytes: int) -> Save:
    """Commit this run's workspace/ and ledger/ changes and push main; on a moved remote, replay and retry once."""
    git = Git(repo, env)
    upstream = f"{remote}/{branch}"
    result = Save(NOT_PUSHED, "")
    try:
        if git.branch() != branch:
            result.detail = f"the clone is no longer on {branch}; nothing was committed"
            return result
        result.commit = save_commit(
            git,
            f"chore(records): outputs of run {run_id}\n\n"
            "Written by the gr0wthlab launcher; only workspace/ and ledger/ change.",
            max_bytes,
            result.excluded,
        )
        result.outside_records = outside(git.status())
        unpushed = git.commits(f"{upstream}..HEAD")
        if not unpushed:
            result.status, result.detail = NOTHING, "no workspace/ or ledger/ changes to save"
            return result
        foreign = local_commits_outside(git, upstream)
        if foreign:
            result.detail = f"{branch} has local commits outside workspace/ and ledger/; nothing was pushed"
            return result
        if push(git, remote, branch):
            result.status, result.pushed = PUSHED, len(unpushed)
            result.detail = f"pushed {plural(len(unpushed), 'records commit')} to {upstream}"
            return result
        fetched = git.run("fetch", "--quiet", remote, branch, timeout=NETWORK_TIMEOUT, check=False)
        moved = fetched.returncode == 0 and git.commits(f"HEAD..{upstream}")
        if not moved:
            result.detail = "the push failed and the remote has not moved; the commits stay local for the next run"
            return result
        failure = (
            "there are local commits outside workspace/ and ledger/"
            if local_commits_outside(git, upstream)
            else replay(git, upstream)
        )
        if failure:
            result.detail = (
                f"{upstream} moved and the records commits could not be replayed ({failure}); they stay local"
            )
            return result
        unpushed = git.commits(f"{upstream}..HEAD")
        if push(git, remote, branch):
            result.status, result.pushed = PUSHED, len(unpushed)
            result.detail = f"{upstream} had moved; replayed and pushed {plural(len(unpushed), 'records commit')}"
        else:
            result.detail = "the retried push failed; the commits stay local for the next run"
        return result
    except GitError as error:
        result.detail = str(error)
        return result


def push(git: Git, remote: str, branch: str) -> bool:
    """A plain push of main; never forced."""
    refspec = f"refs/heads/{branch}:refs/heads/{branch}"
    return git.run("push", "--quiet", remote, refspec, timeout=NETWORK_TIMEOUT, check=False).returncode == 0
