"""Every process the launcher starts and waits for, each with a time limit, so no wait can last forever.

run() is the one place such a process starts. One still running at its limit is stopped with everything it started:
asked first (SIGTERM), then forced (SIGKILL) after a grace period, and the result says which processes that took and
whether any is still running, read from the process table rather than assumed. A process that finishes in time is
never signalled, and it stays in the launcher's own session and process group, so an interrupt at the terminal and
launchd's own cleanup reach it as before.

What a process started is found as the process table shows it: its descendants, each remembered by its process id
and start time, and every session one of them leads, so a child left without its parent is still found. Codex starts
each shell command in a session of its own and does not stop it when Codex itself is asked to stop.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import IO

# Local commands that finish in well under a second: git rev-parse, getconf, codex --version, the sandbox preflight.
QUICK = 60
# Commands whose work grows with what they read: git status over a whole checkout, a query of the kernel log.
SLOW = 300
# How long a process asked to stop has before it is forced, and how long a forced one has to leave the table.
STOP_GRACE = 10.0
KILL_WAIT = 5.0
POLL = 0.1
TABLE_TIMEOUT = 10
PS = next((path for path in ("/bin/ps", "/usr/bin/ps") if os.path.exists(path)), "ps")
ZOMBIE = "Z"


@dataclass(frozen=True)
class Stop:
    """What stopping a process at its time limit took: the processes asked to stop, the ones then forced, and the ones
    still running after that; proven is whether the process table could be read to confirm what is left."""

    asked: tuple[int, ...]
    forced: tuple[int, ...]
    left: tuple[int, ...]
    proven: bool

    @property
    def clean(self) -> bool:
        """Whether the process table shows that nothing the process started is still running."""
        return self.proven and not self.left

    def as_json(self) -> dict[str, object]:
        return {"asked": list(self.asked), "forced": list(self.forced), "left": list(self.left), "proven": self.proven}


@dataclass(frozen=True)
class Completed:
    """A finished process; stop is set only when it was stopped at its time limit, and then returncode says nothing
    about its work: Codex asked to stop exits with 0."""

    returncode: int | None
    stdout: str
    stderr: str
    limit: float
    stop: Stop | None = None

    @property
    def timed_out(self) -> bool:
        return self.stop is not None

    @property
    def ok(self) -> bool:
        return self.stop is None and self.returncode == 0


def limit_text(span: float) -> str:
    """A time limit in words, in whole minutes where it is one."""
    if span >= 60 and span % 60 == 0:
        return f"{int(span // 60)} min"
    return f"{span:g} s"


def table() -> dict[int, tuple[int, str, str]] | None:
    """Every process as (parent, state, start time) by process id, or None when the table could not be read."""
    try:
        listed = subprocess.run(
            [PS, "-A", "-o", "pid=,ppid=,stat=,lstart="],
            capture_output=True,
            text=True,
            env=dict(os.environ, LC_ALL="C"),
            timeout=TABLE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if listed.returncode != 0:
        return None
    rows = {}
    for line in listed.stdout.splitlines():
        fields = line.split(None, 3)
        if len(fields) == 4 and fields[0].isdigit() and fields[1].isdigit():
            rows[int(fields[0])] = (int(fields[1]), fields[2], fields[3].strip())
    return rows


def session(pid: int) -> int | None:
    try:
        return os.getsid(pid)
    except OSError:
        return None


class Family:
    """A process and everything it started, followed across readings of the process table."""

    def __init__(self, root: subprocess.Popen):
        self.root = root
        self.members: dict[int, str] = {}  # process id: start time, which together name one process
        self.sessions: set[int] = set()  # sessions led from inside the family, never the launcher's own
        self.own_session = os.getsid(0)
        self.readable = True

    def running(self) -> list[int]:
        """The family's processes still running, after one more reading of the table.

        When the table cannot be read, only the process itself can be answered for.
        """
        self.root.poll()  # reaps the process itself once it has ended
        rows = table()
        self.readable = rows is not None
        if rows is None:
            return [self.root.pid] if self.root.returncode is None else []
        if self.root.returncode is None and self.root.pid in rows:
            self.members.setdefault(self.root.pid, rows[self.root.pid][2])
        # A remembered process whose id now names another process, or none, has ended.
        self.members = {pid: start for pid, start in self.members.items() if pid in rows and rows[pid][2] == start}
        sessions = {pid: session(pid) for pid in rows}
        grew = True
        while grew:
            grew = False
            for pid, (parent, _, start) in rows.items():
                if pid in self.members or pid == os.getpid():
                    continue
                if parent in self.members or sessions[pid] in self.sessions:
                    self.members[pid] = start
                    grew = True
            for pid in self.members:
                led = sessions[pid]
                if led is not None and led != self.own_session and led not in self.sessions:
                    self.sessions.add(led)
                    grew = True
        return sorted(pid for pid in self.members if not rows[pid][1].startswith(ZOMBIE))

    def signal(self, signum: int) -> tuple[int, ...]:
        """Send one signal to every process of the family still running; the ones it was sent to."""
        sent = []
        for pid in self.running():
            try:
                os.kill(pid, signum)
            except OSError:
                continue  # it ended between the reading and the signal
            sent.append(pid)
        return tuple(sent)

    def wait(self, limit: float) -> list[int]:
        """Wait up to limit seconds for the whole family to end; the processes still running."""
        deadline = time.monotonic() + limit
        while True:
            left = self.running()
            if not left or time.monotonic() >= deadline:
                return left
            time.sleep(POLL)


def stop(process: subprocess.Popen, grace: float | None = None) -> Stop:
    """Stop a process and everything it started: ask, wait up to grace seconds (STOP_GRACE unless given), force what
    is left, and read the process table once more to say what, if anything, is still running."""
    family = Family(process)
    asked = family.signal(signal.SIGTERM)
    forced: tuple[int, ...] = ()
    if family.wait(STOP_GRACE if grace is None else grace):
        forced = family.signal(signal.SIGKILL)
    left = family.wait(KILL_WAIT)
    return Stop(asked, forced, tuple(left), family.readable)


def run(
    command: Sequence[str],
    timeout: float,
    *,
    input: str | None = None,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    errors: str = "replace",
    grace: float | None = None,
) -> Completed:
    """Run a command to its end or to its time limit in seconds, whichever comes first.

    stdout and stderr are returned as text unless a file is given for them. The command reads input, or nothing: it
    never waits on the launcher's own standard input.
    """
    process = subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL if input is None else subprocess.PIPE,
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE if stderr is None else stderr,
        text=True,
        encoding="utf-8",
        errors=errors,
        env=None if env is None else dict(env),
        cwd=cwd,
    )
    try:
        out, err = process.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired:
        stopped = stop(process, grace)
        out, err = drain(process)
        return Completed(process.returncode, out, err, timeout, stopped)
    except BaseException:  # an interrupt at the terminal included, as subprocess.run handles it
        process.kill()
        process.wait()
        raise
    return Completed(process.returncode, out or "", err or "", timeout)


def drain(process: subprocess.Popen) -> tuple[str, str]:
    """What a stopped process had written before it ended; nothing when a process that could not be stopped still
    holds its pipes open, which are then closed so that nothing waits on them."""
    try:
        out, err = process.communicate(timeout=KILL_WAIT)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass
        return "", ""
    return out or "", err or ""
