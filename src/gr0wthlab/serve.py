"""The sitting page's server: a small page on the Founder's own Mac, which only the Founder can make decide.

`gr0wthlab sitting` starts it, prints its address, and serves until the Founder ends the sitting on its last view,
which records the sitting and stops the page, or stops the command with Ctrl-C. It is the only way a Founder record
is ever written (founder.py), so every request is held to this:

- It listens on 127.0.0.1 only, on a free port the Mac gives it and behind a secret in its address, both new each
  time it starts. A request whose address does not hold the secret gets a bare 404, whatever it asks for.
- A request that changes anything is a POST to an address that holds the secret, whose Host and Origin are the page's
  own. Any other POST is refused and writes nothing; a GET never writes a record.
- Every response forbids, by its content security policy, every script, style, image, video, form target, and
  request the page did not ship itself, and may not be framed. The page loads nothing from anywhere else.
- Everything an item, a run report, or a record says is shown as text (page.py); nothing in it is ever acted on.

It uses the standard library only and opens no connection of its own: there is no model, no agent, and no network in
a sitting.
"""

from __future__ import annotations

import fcntl
import hmac
import os
import secrets
import signal
import sys
import threading
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO
from urllib.parse import parse_qs, unquote, urlsplit

from . import exchange, founder, sitting
from .areas import UnsafeFile
from .boundary import ConfigError
from .page import Page, plural
from .sitting import ITEM, Entry, Refused, Saved, Sitting, View

HOST = "127.0.0.1"
# The page's own files, shipped with the launcher: its style sheet, its script, and its icon, and nothing else.
STATIC = Path(__file__).resolve().parents[1] / "sitting"
STATIC_FILES = {
    "page.css": "text/css; charset=utf-8",
    "page.js": "text/javascript; charset=utf-8",
    "icon.svg": "image/svg+xml",
}
MAX_BODY = 16 * 1024
FORM = "application/x-www-form-urlencoded"
POLICY = (
    "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; media-src 'self'; form-action 'self';"
    " base-uri 'none'; frame-ancestors 'none'"
)
HEADERS = {
    "Content-Security-Policy": POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # The page's address holds its secret, so it is never sent anywhere but back to the page itself. The policy cannot
    # be no-referrer: a browser then sends a form's Origin as null, and the page could not tell its own forms.
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}
VIDEO_BLOCK = 256 * 1024


class Server(ThreadingHTTPServer):
    """The page's server, with the sitting it serves and the secret every one of its addresses holds."""

    daemon_threads = True

    def __init__(self, state: Sitting, out: TextIO = sys.stdout):
        super().__init__((HOST, 0), Handler)
        self.state = state
        self.out = out
        self.secret = secrets.token_urlsafe(32)
        self.origin = f"http://{HOST}:{self.server_address[1]}"
        self.page = Page(f"/{self.secret}")
        # One request at a time reads and writes the records, so two clicks never cross.
        self.turn = threading.Lock()

    @property
    def address(self) -> str:
        """The page's address, which holds its secret."""
        return f"{self.origin}/{self.secret}/"

    def say(self, line: str) -> None:
        print(f"gr0wthlab: {line}", file=self.out, flush=True)

    def stop_soon(self) -> None:
        """Stop serving once the request that asked for it has been answered."""
        threading.Thread(target=self.shutdown, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server: Server
    protocol_version = "HTTP/1.1"
    server_version = "gr0wthlab-sitting"
    sys_version = ""
    timeout = 30

    def log_message(self, format: str, *args: object) -> None:
        """Nothing is logged per request: an address holds the page's secret, and what was saved is said in words."""

    # Answers.

    def answer(self, status: int, body: bytes, kind: str = "text/html; charset=utf-8", more: Mapping = ()) -> None:
        self.send_response(status)
        for name, value in {**HEADERS, **dict(more)}.items():
            self.send_header(name, value)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def html(self, text: str, status: int = HTTPStatus.OK) -> None:
        self.answer(status, text.encode("utf-8"))

    def nothing_here(self) -> None:
        """What every address that is not the page's gets: no word of what the page is or where it is."""
        self.answer(HTTPStatus.NOT_FOUND, b"Not found.\n", "text/plain; charset=utf-8")

    def refuse(self, why: str) -> None:
        page = self.server.page.plain("Nothing was saved", why)
        self.answer(HTTPStatus.FORBIDDEN, page.encode("utf-8"))

    def see(self, location: str) -> None:
        self.answer(HTTPStatus.SEE_OTHER, b"", more={"Location": location})

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """What a request the server cannot read gets: the page's own headers, and nothing of the request."""
        self.close_connection = True
        self.answer(code, b"Bad request.\n", "text/plain; charset=utf-8")

    # What a request must hold.

    def route(self) -> tuple[list[str], dict[str, str]] | None:
        """The parts of the address after the secret, and its query; None when the address does not hold the secret,
        or the request names another host."""
        if self.headers.get("Host") != self.server.origin[len("http://") :]:
            return None
        url = urlsplit(self.path)
        parts = url.path.split("/")
        if len(parts) < 3 or parts[0] or not hmac.compare_digest(parts[1].encode(), self.server.secret.encode()):
            return None
        query = {key: values[-1] for key, values in parse_qs(url.query).items()}
        return [unquote(part) for part in parts[2:] if part], query

    def own_post(self) -> str:
        """Why a POST is not one the page's own form sent, or "" when it is."""
        if self.headers.get("Origin") != self.server.origin:
            return "The request did not come from this page, so nothing was saved."
        if self.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin":
            return "The request did not come from this page, so nothing was saved."
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != FORM:
            return "The request was not one of this page's forms, so nothing was saved."
        return ""

    def fields(self) -> dict[str, str] | None:
        """The fields of a posted form; None when the body is missing, too long, or not a form's."""
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        if not 0 <= length <= MAX_BODY:
            return None
        try:
            body = self.rfile.read(length).decode("utf-8")
            parsed = parse_qs(body, keep_blank_values=True, strict_parsing=bool(body), max_num_fields=32)
        except (UnicodeDecodeError, ValueError):
            return None
        return {key: values[-1] for key, values in parsed.items()}

    # GET: every view, the page's own files, and a post's video. None of it writes a record.

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        try:
            self.get()
        except Exception as error:  # noqa: BLE001 - whatever went wrong, the Founder is told, in words
            self.failed(error)

    def failed(self, error: Exception) -> None:
        """A request the page could not answer: say so plainly, here and in the terminal, and never guess at what
        was saved. A record is saved only when the page shows it, read back from its file."""
        self.server.say(f"the page hit an error it did not expect: {type(error).__name__}: {error}")
        self.close_connection = True
        page = self.server.page.plain(
            "The page hit an error",
            f"It did not expect this: {type(error).__name__}.",
            "Go back and open the item again to see what is saved. A decision is saved only when the page shows it"
            " as saved, read back from its file.",
        )
        try:
            self.answer(HTTPStatus.INTERNAL_SERVER_ERROR, page.encode("utf-8"))
        except OSError:
            pass  # the browser had already gone

    def get(self) -> None:
        found = self.route()
        if found is None:
            return self.nothing_here()
        parts, query = found
        if parts[:1] == ["static"] and len(parts) == 2:
            return self.static(parts[1])
        with self.server.turn:
            state, page = self.server.state, self.server.page
            state.begin()
            view = state.look()
            if not parts:
                return self.html(page.start(view, state))
            if parts == ["queue"]:
                return self.html(page.queue(view, state))
            last = self.last_decision(query, view)
            if parts == ["did"]:
                saved = self.saved_record(query, founder.OUTREACH, founder.BETA_BUILDS)
                return self.html(page.did(view, state, saved=saved))
            if parts == ["end"]:
                return self.html(page.end(view, state, last=last))
            if len(parts) == 2 and parts[0] == "item":
                entry = view.find(parts[1])
                if entry is None:
                    return self.html(page.start(view, state), HTTPStatus.NOT_FOUND)
                typed = {"change": "1"} if query.get("change") else None
                return self.html(page.item(view, entry, state, typed=typed, last=last))
            if len(parts) == 2 and parts[0] == "counts":
                recruiting = view.product(parts[1])
                if recruiting is None or recruiting.build is None:
                    return self.html(page.did(view, state), HTTPStatus.NOT_FOUND)
                saved = self.saved_record(query, founder.BETA_REPORTS)
                return self.html(page.counts(view, recruiting, state, saved=saved, last=last))
            if len(parts) == 2 and parts[0] == "video":
                entry = view.find(parts[1])
                if entry is None or entry.video is None or entry.video.path is None:
                    return self.nothing_here()
                path = entry.video.path
        if len(parts) == 2 and parts[0] == "video":
            return self.video(path)
        return self.nothing_here()

    def saved_record(self, query: Mapping[str, str], *kinds: str) -> Saved | None:
        """The record a redirect names as just saved, read back from its file, when it is of one of these kinds; None
        when there is none to show."""
        kind, stem = query.get("kind", ""), query.get("saved", "")
        if kind not in kinds or not founder.STEM.fullmatch(stem):
            return None
        try:
            return self.server.state.saved(kind, stem)
        except (OSError, ValueError, UnsafeFile):
            return None

    def last_decision(self, query: Mapping[str, str], view: View) -> tuple[Saved, Entry] | None:
        """The decision a redirect names as just saved, with its item, for the next step of the walk to show."""
        saved = self.saved_record(query, founder.DECISIONS)
        entry = view.find(saved.stem) if saved else None
        return (saved, entry) if saved and entry else None

    def static(self, name: str) -> None:
        if name not in STATIC_FILES:
            return self.nothing_here()
        try:
            body = (STATIC / name).read_bytes()
        except OSError:
            return self.nothing_here()
        self.answer(HTTPStatus.OK, body, STATIC_FILES[name])

    def video(self, path: Path) -> None:
        """A post's finished video, whole or the byte range asked for, which a browser needs to play and seek it."""
        try:
            size = path.stat().st_size
            start, end = 0, size - 1
            status = HTTPStatus.OK
            asked = self.headers.get("Range", "")
            if asked.startswith("bytes=") and "," not in asked:
                first, _, last = asked[len("bytes=") :].partition("-")
                if first.isdigit():
                    start = int(first)
                    end = min(int(last), size - 1) if last.isdigit() else size - 1
                elif last.isdigit():
                    start = max(0, size - int(last))
                if start > end or start >= size:
                    return self.answer(
                        HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, b"", more={"Content-Range": f"bytes */{size}"}
                    )
                status = HTTPStatus.PARTIAL_CONTENT
            self.send_response(status)
            for name, value in HEADERS.items():
                self.send_header(name, value)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            with path.open("rb") as handle:
                handle.seek(start)
                left = end - start + 1
                while left > 0:
                    block = handle.read(min(VIDEO_BLOCK, left))
                    if not block:
                        break
                    self.wfile.write(block)
                    left -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True  # the browser stopped asking, as it does when a video is sought or left
        except OSError:
            self.close_connection = True

    # POST: the only requests that write, each one explicit act of the Founder's on the page.

    def do_POST(self) -> None:
        try:
            self.post()
        except Exception as error:  # noqa: BLE001 - as for a GET
            self.failed(error)

    def post(self) -> None:
        self.close_connection = True  # a refused request's body is never read, so nothing may follow it
        found = self.route()
        if found is None:
            return self.nothing_here()
        why = self.own_post()
        if why:
            return self.refuse(why)
        fields = self.fields()
        if fields is None:
            return self.refuse("The request was not one of this page's forms, so nothing was saved.")
        parts, _ = found
        with self.server.turn:
            self.act(parts, fields)

    def act(self, parts: list[str], fields: dict[str, str]) -> None:
        server = self.server
        state, page = server.state, server.page
        state.begin()
        get = lambda name: fields.get(name, "")  # noqa: E731
        try:
            if len(parts) == 3 and parts[0] == "item" and parts[2] == "decide":
                step = (ITEM, parts[1])
                onward = state.look().after(step)
                saved = state.decide(parts[1], get("decision"), get("line"))
                server.say(f"saved {saved.path}: {saved.record['decision']}")
                return self.see(page.step_url(onward, saved=saved.stem, kind=saved.kind))
            if len(parts) == 3 and parts[0] == "item" and parts[2] == "take-back":
                state.take_back(parts[1])
                server.say(f"took back the decision on {parts[1]}")
                return self.see(page.url("item", parts[1]))
            if len(parts) == 2 and parts[0] == "counts":
                saved = state.report_counts(parts[1], fields)
                server.say(f"saved {saved.path}")
                return self.see(page.url("counts", parts[1], saved=saved.stem, kind=saved.kind))
            if parts == ["end"]:
                saved = state.record_sitting(get("minutes"), get("note"))
                server.say(f"saved {saved.path}: {plural(saved.record['minutes'], 'minute')}")
                self.html(page.finished(saved))
                server.say("the sitting has ended, from the page")
                return server.stop_soon()
            if len(parts) == 3 and parts[:2] == ["did", "sent"]:
                saved = state.record_sent(parts[2], get("sent_on"), get("replied_on"), get("wait_days"), get("note"))
                server.say(f"saved {saved.path}")
                return self.see(page.url("did", saved=saved.stem, kind=saved.kind))
            if len(parts) == 3 and parts[:2] == ["did", "beta-build"]:
                saved = state.record_beta_build(parts[2], get("approved_on"), get("build"))
                server.say(f"saved {saved.path}: recruiting {saved.record['recruiting']}")
                return self.see(page.url("did", saved=saved.stem, kind=saved.kind))
            if len(parts) == 3 and parts[:2] == ["did", "recruiting"] and get("recruiting") in ("stop", "reopen"):
                saved = state.set_recruiting(parts[2], get("recruiting") == "stop", get("stopped_on"))
                server.say(f"saved {saved.path}: recruiting {saved.record['recruiting']}")
                return self.see(page.url("did", saved=saved.stem, kind=saved.kind))
        except Refused as refused:
            return self.refused(parts, fields, refused.reasons)
        return self.nothing_here()

    def refused(self, parts: list[str], fields: dict[str, str], reasons: list[str]) -> None:
        """The view an act came from, with why nothing was saved and what the Founder typed still in place."""
        state, page = self.server.state, self.server.page
        view = state.look()
        status = HTTPStatus.UNPROCESSABLE_ENTITY
        if parts[0] == "item":
            entry = view.find(parts[1])
            if entry is None:
                return self.html(page.start(view, state), HTTPStatus.CONFLICT)
            key = "reason" if fields.get("decision") == exchange.REJECT else "note"
            typed = {key: fields.get("line", ""), "change": "1"}
            return self.html(page.item(view, entry, state, reasons, typed), status)
        if parts[0] == "counts":
            recruiting = view.product(parts[1])
            if recruiting is None or recruiting.build is None:
                return self.html(page.did(view, state, reasons), status)
            return self.html(page.counts(view, recruiting, state, reasons, fields), status)
        if parts == ["end"]:
            return self.html(page.end(view, state, reasons, fields), status)
        at = {"sent": f"sent:{parts[2]}", "beta-build": f"build:{parts[2]}", "recruiting": f"build:{parts[2]}"}
        return self.html(page.did(view, state, reasons, fields, at=at.get(parts[1], "")), status)


def serve(repo_root: Path, out: TextIO = sys.stdout) -> int:
    """Serve one sitting until the Founder ends it on the page, which records it, or stops the command with Ctrl-C,
    which does not; returns the exit status."""
    state = Sitting(repo_root)
    lock = (state.ledger / sitting.SERVING_LOCK).open("a")
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ConfigError("another sitting page is already being served for this checkout; stop it first") from None
        try:
            server = Server(state, out)
        except OSError as error:
            raise ConfigError(f"the page could not be served on {HOST} ({error.strerror or error})") from error

        def stop(signum: int, frame: object) -> None:
            server.stop_soon()

        previous = {name: signal.signal(name, stop) for name in (signal.SIGINT, signal.SIGTERM)}
        try:
            server.say(f"the sitting page for {os.path.basename(str(repo_root))}/ledger is at:")
            print(f"\n  {server.address}\n", file=out, flush=True)
            server.say("open it in a browser on this Mac; its last page records the sitting and stops this command")
            server.serve_forever(poll_interval=0.2)
        finally:
            for name, handler in previous.items():
                signal.signal(name, handler)
            server.server_close()
        server.say("the sitting page has stopped")
        return 0
    finally:
        lock.close()
