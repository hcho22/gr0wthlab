"""The launcher's only way onto the network: credential-free reads of a fixed list of hosts, run outside the sandbox.

The sandboxed agent has no network at all; the launcher fetches for it, before it starts, and hands it a snapshot it
can read and never write. Everything a request may be is fixed here and in config/guardrails/fetch.json, which only a
reviewed pull request changes (Guardrail G8):

- one method, GET, with no body, cookie, or credential (G5), over HTTPS on port 443, to a host the configuration
  lists and to no other; nothing else in the launcher opens a network connection, and send() is the one place this
  module does;
- each host's robots.txt is binding: it is read first, and a path it disallows for this reader is never requested;
  a robots.txt that cannot be read refuses the whole host for the run, since nothing shows what it allows;
- a small bounded number of requests per run, spaced out on each host, and a wait a host asks for (Retry-After, or
  Crawl-delay in its robots.txt) is kept once when it is short, never worked around when it is long;
- no read waits forever: each wait on a host ends at a timeout, and each whole read at a deadline, however slowly
  the host answers, so no host can hold the run;
- a redirect is followed only to a listed host, each hop checked like a first request;
- every request the run asked for, sent or not, is in the request log with its outcome.

A refusal is an answer: the caller reports the source as not read, with the reason.
"""

from __future__ import annotations

import contextlib
import http.client
import re
import socket
import ssl
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from .boundary import ConfigError, load_json

FETCH_CONFIG = Path("config/guardrails/fetch.json")
METHOD = "GET"
PORT = 443
ROBOTS_PATH = "/robots.txt"
ROBOTS_BYTES = 512 * 1024  # a reader parses at least the first 500 KiB of a robots.txt (RFC 9309)
MAX_REDIRECTS = 3
MAX_URL = 2000
REDIRECTS = (301, 302, 303, 307, 308)
WAIT_STATUSES = (429, 503)
# A public DNS name: at least two labels, the last one letters only, so never an address literal or a bare name.
HOST = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}")
LOCAL_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".arpa", ".onion")
# The product token holds only letters, hyphens, and underscores, as a robots.txt names a reader (RFC 9309).
USER_AGENT = re.compile(r"[A-Za-z][A-Za-z_-]*/[0-9][0-9A-Za-z.]* \([ -~]+\)")
UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"

# What became of one read.
READ = "read"
DISALLOWED = "disallowed"  # the host's robots.txt does not allow the path, so it was never requested
FAILED = "failed"  # the host refused, failed, or could not be reached
REFUSED = "refused"  # this client's own rules refused the request before anything was sent


# The configuration.


@dataclass(frozen=True)
class Policy:
    hosts: tuple[str, ...]
    user_agent: str
    max_requests: int
    interval: float
    timeout: float
    deadline: float
    max_bytes: int
    max_wait: float

    @property
    def token(self) -> str:
        """The product token a robots.txt names this reader by."""
        return self.user_agent.split("/", 1)[0].lower()


def whole(data: Mapping, key: str, low: int, high: int) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ConfigError(f"{FETCH_CONFIG}: {key} must be a whole number from {low} to {high}")
    return value


def policy_from(data: Mapping) -> Policy:
    """The fetch policy, or ConfigError for anything that could widen what the launcher may reach."""
    hosts = data.get("hosts")
    if not isinstance(hosts, list) or not hosts or len(set(hosts)) != len(hosts):
        raise ConfigError(f"{FETCH_CONFIG}: hosts must list distinct host names")
    for host in hosts:
        if not isinstance(host, str) or not HOST.fullmatch(host) or host.endswith(LOCAL_SUFFIXES):
            raise ConfigError(
                f"{FETCH_CONFIG}: host {host!r} must be one public DNS name in lowercase, with no scheme, port, path,"
                " wildcard, or address"
            )
    agent = data.get("user_agent")
    if not isinstance(agent, str) or not USER_AGENT.fullmatch(agent) or "@" in agent or len(agent) > 200:
        raise ConfigError(
            f"{FETCH_CONFIG}: user_agent must read like name/1 (who runs it; how to reach them): a product token of"
            " letters, hyphens, and underscores, and no email address"
        )
    return Policy(
        tuple(hosts),
        agent,
        whole(data, "max_requests_per_run", 1, 200),
        float(whole(data, "seconds_between_requests_per_host", 1, 60)),
        float(whole(data, "timeout_seconds", 1, 120)),
        float(whole(data, "read_deadline_seconds", 1, 600)),
        whole(data, "max_response_bytes", 1024, 20_000_000),
        float(whole(data, "max_wait_seconds", 0, 600)),
    )


def load_policy(repo_root: Path) -> Policy:
    return policy_from(load_json(repo_root / FETCH_CONFIG))


# One request on the wire.


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]  # names in lowercase
    body: bytes


Transport = Callable[[str, str, Mapping[str, str], float, int, float], Response]


def send(host: str, target: str, headers: Mapping[str, str], timeout: float, limit: int, deadline: float) -> Response:
    """Send one GET with no body to host:443 over verified TLS and read at most limit + 1 bytes of the answer. Each
    wait on the socket ends after timeout seconds and the whole exchange after deadline seconds: once the deadline
    has passed, the connection's socket is shut, so a host that answers a byte at a time ends in a TimeoutError.

    The only place the launcher opens a network connection. http.client follows no redirect, keeps no cookie, and
    reads no proxy or credential from the environment or from any file.
    """
    connection = http.client.HTTPSConnection(host, PORT, timeout=timeout, context=ssl.create_default_context())
    over, late = threading.Event(), threading.Event()
    # The socket itself, kept once the request is sent: http.client lets go of it as soon as it has read the headers
    # of an answer that closes the connection, and the response alone then reads the body from it.
    kept: socket.socket | None = None

    def cut() -> None:
        if over.wait(deadline):
            return
        late.set()
        while True:
            sock = connection.sock if kept is None else kept
            if sock is not None:
                with contextlib.suppress(OSError):
                    socket.socket.shutdown(sock, socket.SHUT_RDWR)
            if over.wait(0.05):
                return

    threading.Thread(target=cut, daemon=True).start()
    answer = None
    try:
        connection.request(METHOD, target, headers=dict(headers))
        kept = connection.sock
        response = connection.getresponse()
        body = response.read(limit + 1)
        answer = Response(response.status, {name.lower(): value for name, value in response.getheaders()}, body)
    except (OSError, http.client.HTTPException):
        if not late.is_set():
            raise
    finally:
        over.set()
        connection.close()
    if late.is_set():
        raise TimeoutError(f"no complete answer within {deadline:.0f} s")
    return answer


# robots.txt.


def normalized(text: str) -> str:
    """A path or a robots.txt pattern in one spelling: other bytes percent-encoded, an encoded unreserved character
    decoded, and every other escape in uppercase."""
    text = quote(text, safe="/%*$?=&+,:;@!'()[]~-._#")

    def escape(match: re.Match) -> str:
        character = chr(int(match.group(1), 16))
        return character if character in UNRESERVED else f"%{match.group(1).upper()}"

    return re.sub(r"%([0-9A-Fa-f]{2})", escape, text)


@dataclass(frozen=True)
class Rule:
    allow: bool
    pattern: str
    line: str  # the rule as the robots.txt wrote it

    def matches(self, target: str) -> bool:
        pattern = normalized(self.pattern)
        anchored = pattern.endswith("$")
        body = ".*".join(re.escape(part) for part in pattern.rstrip("$").split("*"))
        return re.match(body + ("$" if anchored else ""), target, re.DOTALL) is not None


@dataclass(frozen=True)
class Robots:
    """What one host's robots.txt lets this reader request. state is "read", "none" when the host has no robots.txt,
    so nothing is disallowed, or "unavailable" when it could not be read, so everything is."""

    host: str
    state: str
    detail: str = ""
    rules: tuple[Rule, ...] = ()
    delay: float = 0.0

    def allows(self, target: str) -> tuple[bool, str]:
        """Whether the path, with its query, may be requested, and the rule or reason that decides. The longest
        matching rule wins, and an Allow wins a tie (RFC 9309)."""
        if target.split("?", 1)[0] == ROBOTS_PATH:
            return True, "robots.txt itself is always readable"
        if self.state == "unavailable":
            return False, f"robots.txt on {self.host} could not be read ({self.detail}), so nothing on it was requested"
        path = normalized(target)
        matching = [rule for rule in self.rules if rule.pattern and rule.matches(path)]
        if not matching:
            return True, "no robots.txt rule covers it"
        best = max(matching, key=lambda rule: (len(normalized(rule.pattern)), rule.allow))
        if best.allow:
            return True, f"robots.txt allows it (`{best.line}`)"
        return False, f"robots.txt on {self.host} disallows it for automated readers (`{best.line}`)"


def parse_robots(host: str, text: str, token: str) -> Robots:
    """The rules of the group that names this reader's product token, or of the * group when none does."""
    groups: list[tuple[list[str], list[Rule], list[float]]] = []
    collecting = False  # whether the last record read was a user-agent line, so the next one joins its group
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.split("#", 1)[0].strip()
        key, colon, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not colon:
            continue
        if key == "user-agent":
            if not collecting:
                groups.append(([], [], []))
            groups[-1][0].append(value.lower())
            collecting = True
            continue
        if key in ("allow", "disallow") and groups:
            groups[-1][1].append(Rule(key == "allow", value, f"{key.capitalize()}: {value}"))
        elif key == "crawl-delay" and groups:
            try:
                groups[-1][2].append(float(value))
            except ValueError:
                pass
        else:
            continue  # a record this reader does not use, such as Sitemap, belongs to no group and ends none
        collecting = False
    named = [group for group in groups if token in group[0]]
    chosen = named or [group for group in groups if "*" in group[0]]
    rules = tuple(rule for _, found, _ in chosen for rule in found)
    delays = [delay for _, _, found in chosen for delay in found if delay > 0]
    return Robots(host, "read", "", rules, max(delays, default=0.0))


# The client.


@dataclass(frozen=True)
class Result:
    """One read's outcome: the body when it was read, and otherwise why not, in words a run report can show."""

    status: str
    detail: str
    url: str
    body: bytes = b""
    http_status: int | None = None
    at: str = ""

    @property
    def ok(self) -> bool:
        return self.status == READ


def parse_wait(headers: Mapping[str, str]) -> float | None:
    """The seconds a Retry-After header asks for; a date, or anything else, is a wait of unknown length."""
    value = headers.get("retry-after", "").strip()
    if not value:
        return None
    return float(value) if re.fullmatch(r"\d{1,6}", value) else float("inf")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def short(text: object, limit: int = 160) -> str:
    """Text for a log or report line: on one line, no control character, and never long."""
    cleaned = " ".join("".join(c if c.isprintable() else " " for c in str(text)).split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def refusal(policy: Policy, url: str) -> str | None:
    """Why the client never sends a request for the address, or None when it may."""
    if not isinstance(url, str) or len(url) > MAX_URL or any(c.isspace() or not c.isprintable() for c in url):
        return "the address is not one plain line of at most 2,000 characters"
    if "\\" in url:
        return "the address holds a backslash"
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return "the address cannot be parsed"
    if parts.scheme != "https":
        return "only https addresses are read"
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        return "an address may carry no user name or password"
    if port is not None:
        return "an address may name no port; every read goes to port 443"
    if parts.netloc not in policy.hosts:
        return f"{short(parts.netloc or 'no host', 80)} is not a host listed in {FETCH_CONFIG}"
    if parts.fragment:
        return "an address may carry no fragment"
    if not parts.path.startswith("/"):
        return "the address needs a path"
    return None


@dataclass
class Client:
    """Reads for one run. Every request it is asked for is logged, whether or not it was sent."""

    policy: Policy
    transport: Transport | None = None
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    now: Callable[[], datetime] = utc_now
    log: list[dict[str, object]] = field(default_factory=list)
    sent: int = 0
    robots: dict[str, Robots] = field(default_factory=dict)
    ready: dict[str, float] = field(default_factory=dict)  # host: the earliest moment of its next request
    closed: dict[str, str] = field(default_factory=dict)  # host: why no more is asked of it this run

    def refusal(self, url: str) -> str | None:
        return refusal(self.policy, url)

    def record(self, url: str, purpose: str, sent: bool, outcome: str, detail: str, **extra: object) -> None:
        try:
            host = short(urlsplit(url).netloc, 80)
        except ValueError:
            host = ""
        entry = {"at": self.now().isoformat(), "method": METHOD, "url": short(url, MAX_URL), "purpose": purpose}
        entry.update(sent=sent, host=host, outcome=outcome, detail=detail, **extra)
        self.log.append(entry)

    def get(self, url: str, purpose: str) -> Result:
        """Read one address, if this client's rules, the host's robots.txt, and the host itself allow it."""
        return self.read(url, purpose, self.policy.max_bytes, bound=True)

    def robots_for(self, host: str) -> Robots:
        """The host's robots.txt, read once per run. No robots.txt (404 or 410) disallows nothing; any other answer
        that is not the file leaves nothing on the host readable this run."""
        if host not in self.robots:
            result = self.read(f"https://{host}{ROBOTS_PATH}", f"robots.txt of {host}", ROBOTS_BYTES, bound=False)
            if result.ok:
                parsed = parse_robots(host, result.body.decode("utf-8", errors="replace"), self.policy.token)
            elif result.http_status in (404, 410):
                parsed = Robots(host, "none", "the host has no robots.txt")
            else:
                parsed = Robots(host, "unavailable", result.detail)
            self.robots[host] = parsed
            if parsed.delay:
                self.ready[host] = max(self.ready.get(host, 0.0), self.clock() + parsed.delay)
        return self.robots[host]

    def read(self, url: str, purpose: str, limit: int, bound: bool) -> Result:
        """Follow one read to its end. bound is False only for a robots.txt itself, which is read whatever it says
        and may be cut at limit; every other read is bound by its host's robots.txt at every hop."""
        for hop in range(MAX_REDIRECTS + 1):
            problem = self.refusal(url)
            if problem:
                self.record(url, purpose, False, REFUSED, problem)
                if hop:
                    return Result(
                        FAILED, f"the host redirected to an address this reader never follows: {problem}", url
                    )
                return Result(REFUSED, f"not requested: {problem}", short(url, 300))
            parts = urlsplit(url)
            host, target = parts.netloc, parts.path + (f"?{parts.query}" if parts.query else "")
            if bound:
                allowed, why = self.robots_for(host).allows(target)
                if not allowed:
                    self.record(url, purpose, False, DISALLOWED, why)
                    return Result(DISALLOWED, f"not read: {why}", url)
            response, failure = self.exchange(host, target, url, purpose, limit)
            if response is None:
                return Result(FAILED, failure, url)
            if response.status in REDIRECTS:
                location = response.headers.get("location", "")
                if not location:
                    return Result(
                        FAILED, f"HTTP {response.status} with no address to follow", url, b"", response.status
                    )
                try:
                    url = urljoin(url, location)
                except ValueError:
                    return Result(
                        FAILED, "the host redirected to an address that cannot be parsed", url, b"", response.status
                    )
                continue
            if response.status != 200:
                return Result(FAILED, f"the host answered HTTP {response.status}", url, b"", response.status)
            body = response.body
            if len(body) > limit:
                if bound:
                    return Result(FAILED, f"the answer is larger than {limit:,} bytes", url, b"", 200)
                body = body[:limit]
            return Result(READ, f"HTTP 200, {len(body):,} bytes", url, body, 200, self.now().isoformat())
        return Result(FAILED, f"more than {MAX_REDIRECTS} redirects", short(url, 300))

    def wait_for(self, host: str) -> str | None:
        """Wait until the host may be asked again; why it is not asked at all when the wait its robots.txt asks for
        is too long. The pause this client keeps between its own requests is always kept, whatever max_wait is."""
        if host in self.closed:
            return self.closed[host]
        asked = self.robots[host].delay if host in self.robots else 0.0
        if asked > self.policy.max_wait:
            self.closed[host] = (
                f"{host} asked for a wait of {asked:.0f} s between requests, longer than this run waits"
                f" ({self.policy.max_wait:.0f} s), so it was not asked again"
            )
            return self.closed[host]
        wait = self.ready.get(host, 0.0) - self.clock()
        if wait > 0:
            self.sleep(wait)
        return None

    def exchange(self, host: str, target: str, url: str, purpose: str, limit: int) -> tuple[Response | None, str]:
        """Send one request, keeping the run's request limit and the host's pace; a host that answers with a short
        wait (Retry-After on 429 or 503) is asked once more after it, and a long or unstated wait closes the host."""
        headers = {
            "User-Agent": self.policy.user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        for attempt in (1, 2):
            closed = self.wait_for(host)
            if closed:
                self.record(url, purpose, False, FAILED, closed)
                return None, closed
            if self.sent >= self.policy.max_requests:
                detail = f"this run's limit of {self.policy.max_requests} requests is used up"
                self.record(url, purpose, False, FAILED, detail)
                return None, detail
            self.sent += 1
            try:
                response = (self.transport or send)(
                    host, target, headers, self.policy.timeout, limit, self.policy.deadline
                )
            except (OSError, http.client.HTTPException, ValueError) as error:
                detail = f"{host} could not be read: {type(error).__name__}: {short(error)}"
                self.ready[host] = self.clock() + self.policy.interval
                self.record(url, purpose, True, FAILED, detail)
                return None, detail
            self.ready[host] = self.clock() + max(self.policy.interval, self.robots.get(host, Robots(host, "")).delay)
            self.record(
                url, purpose, True, f"HTTP {response.status}", "", status=response.status, bytes=len(response.body)
            )
            wait = parse_wait(response.headers)
            if response.status not in WAIT_STATUSES or (wait is None and response.status != 429):
                return response, ""
            if wait is not None and wait <= self.policy.max_wait and attempt == 1:
                self.ready[host] = max(self.ready[host], self.clock() + wait)
                continue
            asked = "without saying for how long" if wait in (None, float("inf")) else f"for {wait:.0f} s"
            self.closed[host] = (
                f"{host} answered HTTP {response.status} and asked this reader to wait {asked}, so it was not asked"
                " again this run"
            )
            return None, self.closed[host]
        return None, f"{host} could not be read"

    def summary(self) -> dict[str, object]:
        """The run's request log: the rules in force, every request asked for, and what left the machine."""
        sent = [entry for entry in self.log if entry["sent"]]
        return {
            "note": "Every request the launcher was asked to make this run. Only entries with sent true left the"
            " machine: each was one GET with no body, cookie, or credential, to a listed host on port 443.",
            "policy": {
                "config": str(FETCH_CONFIG),
                "hosts": list(self.policy.hosts),
                "user_agent": self.policy.user_agent,
                "max_requests_per_run": self.policy.max_requests,
            },
            "sent": len(sent),
            "not_sent": len(self.log) - len(sent),
            "methods_sent": sorted({str(entry["method"]) for entry in sent}),
            "hosts_contacted": sorted({str(entry["host"]) for entry in sent}),
            "bodies_sent": 0,
            "robots": {
                host: {"state": robots.state, "detail": robots.detail, "rules": [rule.line for rule in robots.rules]}
                for host, robots in sorted(self.robots.items())
            },
            "requests": self.log,
        }
