"""The sitting page behind its server, asked as a browser asks it, over the loopback address only.

Only the Founder's own act on the page writes a record. So: a request without the page's secret gets nothing; a
request that changes anything is a POST from the page's own form, to the page's own host; everything a response holds
is the page's own markup around text; and every response forbids whatever the page did not ship.
"""

import http.client
import io
import json
import threading
import unittest
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from gr0wthlab import exchange, serve
from tests import fakes
from tests.test_page import HOSTILE, PAGE_TAGS, Seen
from tests.test_sitting import DAY, SITTING, SittingTestCase

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


class ServeTestCase(SittingTestCase):
    def serve(self, state=None):
        """The sitting page, served on a free port of the loopback address until the test ends."""
        self.said = io.StringIO()
        self.server = serve.Server(state or self.sit_down(), 0, self.said)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.host, self.port = self.server.server_address
        self.base = f"/{self.server.secret}"
        return self.server

    def ask(self, method, path, fields=None, headers=None, body=None):
        """One request as it goes on the wire, and the status, headers, and text that come back."""
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        try:
            if fields is not None:
                body = urlencode(fields)
            sent = dict(headers or {})
            connection.request(method, path, body=body, headers=sent)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode("utf-8", errors="replace")
        finally:
            connection.close()

    def get(self, path="/", **headers):
        return self.ask("GET", self.base + path, headers=headers)

    def post(self, path, fields, **changes):
        """A POST as the page's own form sends it, unless changes say otherwise; None leaves a header out."""
        headers = dict(FORM, Origin=self.server.origin)
        for name, value in changes.items():
            name = name.replace("_", "-")
            if value is None:
                headers.pop(name, None)
            else:
                headers[name] = value
        return self.ask("POST", self.base + path, fields, headers)

    def unwritten(self):
        return fakes.tree_digest(self.exchange)


class SecretTest(ServeTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.one_proposal()
        self.serve()

    def test_it_listens_on_the_loopback_address_only_behind_a_secret_that_is_new_each_time(self):
        self.assertEqual(self.host, "127.0.0.1")
        self.assertEqual(self.server.address, f"http://127.0.0.1:{self.port}/{self.server.secret}/")
        self.assertGreaterEqual(len(self.server.secret), 43, "256 bits, as text")
        self.assertNotIn(self.server.secret, self.said.getvalue(), "the address is printed once, by the command")
        other = serve.Server(self.sit_down(), 0, io.StringIO())
        try:
            self.assertNotEqual(other.secret, self.server.secret)
            self.assertEqual(other.server_address[0], "127.0.0.1")
        finally:
            other.server_close()

    def test_an_address_without_the_secret_gets_nothing_whatever_it_asks_for(self):
        before = self.unwritten()
        decide = f"/item/{self.item}/decide"
        approve = {"decision": "approve", "line": ""}
        paths = [
            "/",
            "/queue",
            decide,
            f"/x{decide}",
            f"/{self.server.secret[:-1]}{decide}",
            f"/{self.server.secret}x/",
            "//",
        ]
        paths += [f"/{'A' * len(self.server.secret)}{decide}", "/static/page.css", f"/..{self.base}/", "/%2e%2e/"]
        for path in paths:
            for method in ("GET", "POST", "HEAD"):
                with self.subTest(method=method, path=path):
                    fields = approve if method == "POST" else None
                    headers = dict(FORM, Origin=self.server.origin) if method == "POST" else None
                    status, sent, body = self.ask(method, path, fields, headers)
                    self.assertEqual(status, 404)
                    self.assertIn(body, ("Not found.\n", ""))
                    self.assertNotIn(self.server.secret, json.dumps(sent))
        self.assertEqual(self.unwritten(), before)
        self.assertEqual(self.get("/")[0], 200, "and the page is still there for the Founder")

    def test_a_get_never_writes_a_record(self):
        before = self.unwritten()
        for path in (
            f"/item/{self.item}/decide",
            f"/item/{self.item}/decide?decision=approve&line=",
            f"/item/{self.item}/take-back",
            f"/item/{self.item}?decision=approve",
            "/end?minutes=40",
            "/stop",
            "/did/beta-build/RepToday?approved_on=2026-10-09",
        ):
            with self.subTest(path=path):
                self.assertIn(self.get(path)[0], (200, 404))
        self.assertEqual(self.unwritten(), before)
        self.assertEqual(self.get("/")[0], 200, "a GET for /stop stops nothing")

    def test_a_post_from_anywhere_but_the_page_s_own_form_is_refused_and_writes_nothing(self):
        before = self.unwritten()
        decide = f"/item/{self.item}/decide"
        approve = {"decision": "approve", "line": ""}
        own = self.server.origin
        refusals = {
            "another origin": {"Origin": "http://evil.example"},
            "another port of this Mac": {"Origin": f"http://127.0.0.1:{self.port + 1}"},
            "the same address by name": {"Origin": f"http://localhost:{self.port}"},
            "https": {"Origin": own.replace("http://", "https://")},
            "a null origin": {"Origin": "null"},
            "no origin": {"Origin": None},
            "a cross-site fetch": {"Sec_Fetch_Site": "cross-site"},
            "a same-site fetch from another origin": {"Sec_Fetch_Site": "same-site"},
            "a fetch with no site": {"Sec_Fetch_Site": "none"},
            "json": {"Content_Type": "application/json"},
            "plain text": {"Content_Type": "text/plain"},
            "a multipart form": {"Content_Type": "multipart/form-data; boundary=x"},
            "no content type": {"Content_Type": None},
        }
        for what, changes in refusals.items():
            with self.subTest(what):
                status, _, body = self.post(decide, approve, **changes)
                self.assertEqual(status, 403)
                self.assertIn("Nothing was saved", body)
                self.assertIn("so nothing was saved.", body)
        for what, host in (("another host", "evil.example"), ("this Mac by name", f"localhost:{self.port}")):
            with self.subTest(what):
                self.assertEqual(self.post(decide, approve, Host=host)[0], 404)
                self.assertEqual(self.get("/", Host=host)[0], 404)
        self.assertEqual(self.unwritten(), before)
        status, sent, _ = self.post(decide, approve)
        self.assertEqual(status, 303, "and the page's own form is taken")
        self.assertEqual(self.record("decisions", self.item)["decision"], "approve")

    def test_a_body_the_page_s_form_could_not_send_is_refused(self):
        before = self.unwritten()
        decide = self.base + f"/item/{self.item}/decide"
        headers = dict(FORM, Origin=self.server.origin)
        too_long = "decision=approve&line=" + "x" * serve.MAX_BODY
        for what, body in (("too long", too_long), ("not text", b"\xff\xfe\xfd"), ("not a form", "decision")):
            with self.subTest(what):
                self.assertEqual(self.ask("POST", decide, headers=headers, body=body)[0], 403)
        self.assertEqual(self.ask("POST", decide, headers=dict(headers, **{"Content-Length": "x"}))[0], 403)
        for method in ("PUT", "DELETE", "PATCH", "OPTIONS"):
            with self.subTest(method=method):
                self.assertEqual(self.ask(method, decide, headers=headers, body="decision=approve")[0], 501)
        self.assertEqual(self.unwritten(), before)


class HeadersTest(ServeTestCase):
    def test_every_response_forbids_what_the_page_did_not_ship(self):
        item = self.one_proposal()
        self.serve()
        answers = {
            "a view": self.get("/"),
            "an item": self.get(f"/item/{item}"),
            "the style sheet": self.get("/static/page.css"),
            "the script": self.get("/static/page.js"),
            "the icon": self.get("/static/icon.svg"),
            "nothing": self.ask("GET", "/"),
            "a refused post": self.post(f"/item/{item}/decide", {"decision": "approve"}, Origin="http://evil.example"),
            "a refused line": self.post(f"/item/{item}/decide", {"decision": "reject", "line": ""}),
            "a redirect": self.post(f"/item/{item}/decide", {"decision": "approve", "line": ""}),
            "a method it has not": self.ask("PUT", self.base + "/"),
        }
        self.assertEqual([answer[0] for answer in answers.values()], [200, 200, 200, 200, 200, 404, 403, 422, 303, 501])
        for what, (_, headers, _) in answers.items():
            with self.subTest(what):
                self.assertEqual(
                    headers["Content-Security-Policy"],
                    "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; media-src 'self';"
                    " form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
                )
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertEqual(headers["Referrer-Policy"], "same-origin")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                self.assertNotIn("Set-Cookie", headers)
                self.assertEqual(headers["Server"].strip(), "gr0wthlab-sitting")

    def test_the_page_ships_its_own_style_sheet_script_and_icon_and_loads_nothing_else(self):
        self.one_proposal()
        self.serve()
        status, headers, css = self.get("/static/page.css")
        self.assertEqual((status, headers["Content-Type"]), (200, "text/css; charset=utf-8"))
        self.assertNotIn("url(", css)
        self.assertNotIn("@import", css)
        self.assertNotIn("http", css)
        status, headers, script = self.get("/static/page.js")
        self.assertEqual((status, headers["Content-Type"]), (200, "text/javascript; charset=utf-8"))
        for banned in (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "sendBeacon",
            "eval(",
            "innerHTML",
            "document.write",
            "http",
            ".submit(",
            ".click(",
        ):
            self.assertNotIn(banned, script, "the script sends, fills, and chooses nothing")
        self.assertEqual(self.get("/static/icon.svg")[1]["Content-Type"], "image/svg+xml")
        for name in ("page.py", "../gr0wthlab/founder.py", "..%2Fgr0wthlab%2Ffounder.py", "page.css/x", ""):
            with self.subTest(name=name):
                self.assertEqual(self.get(f"/static/{name}")[0], 404)
        seen = Seen(self.get("/")[2])
        self.assertEqual([attrs["src"] for attrs in seen.named("script")], [f"{self.base}/static/page.js"])
        self.assertEqual(
            sorted(attrs["href"] for attrs in seen.named("link")),
            [f"{self.base}/static/icon.svg", f"{self.base}/static/page.css"],
        )

    def test_an_error_inside_the_page_is_said_plainly_and_claims_nothing_saved(self):
        item = self.one_proposal()
        self.serve()
        self.server.page.item = None  # whatever breaks while a view is drawn
        status, headers, body = self.get(f"/item/{item}")
        self.assertEqual(status, 500)
        self.assertIn("The page hit an error", body)
        self.assertIn("A decision is saved only when the page shows it as saved, read back from its file.", body)
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("the page hit an error it did not expect: TypeError", self.said.getvalue())
        self.assertEqual(self.get("/")[0], 200, "and the next request is answered")

    def test_a_file_that_is_no_record_is_never_shown_as_saved(self):
        self.one_proposal()
        self.serve()
        (self.repo / "ledger" / "founder" / "sittings" / f"{DAY}.json").write_text("[]\n", encoding="utf-8")
        status, _, body = self.get(f"/end?saved={DAY}&kind=sittings")
        self.assertEqual(status, 200)
        self.assertNotIn("Saved.", Seen(body).said)


class InertTest(ServeTestCase):
    """An item whose text carries markup, a script, a form, or a link is shown as that text, by the real server."""

    def setUp(self):
        super().setUp()
        hostile = "\n".join(HOSTILE)
        item = fakes.proposal(title="<script>alert(1)</script> [approve](http://example.com)").replace(
            "Replace the stale caveat with the cleared status.", hostile + "\n\n- " + "\n- ".join(HOSTILE)
        )
        fakes.behave(
            self.codex_dir,
            {"write": {"review-queue/incoming/hostile.md": item}, "summary": hostile + "\n\nSession: complete\n"},
        )
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        fakes.behave(self.codex_dir, {})
        (self.item,) = [entry["id"] for entry in self.queue()["open"] if entry["kind"] == "package-change-proposal"]
        self.serve()

    def test_the_item_reaches_the_browser_as_text_inside_the_page_s_own_markup(self):
        status, _, body = self.get(f"/item/{self.item}")
        self.assertEqual(status, 200)
        seen = Seen(body)
        self.assertLessEqual(seen.tags, PAGE_TAGS)
        for text in HOSTILE:
            self.assertIn(text, seen.said, "every character of it is shown")
        self.assertEqual(
            [attrs["action"] for attrs in seen.named("form")], [f"{self.base}/item/{self.item}/decide"] * 2
        )
        self.assertEqual([attrs["src"] for attrs in seen.named("script")], [f"{self.base}/static/page.js"])
        self.assertEqual(
            {attrs["href"] for attrs in seen.named("a") if not attrs["href"].startswith(self.base + "/")}, set()
        )
        for name in ("img", "iframe", "style", "base", "svg", "object", "embed"):
            self.assertEqual(seen.named(name), [], name)
        self.assertEqual(len(seen.named("meta")), 2, "the page's own charset and viewport, and no refresh")
        for element, attrs in seen.elements:
            self.assertFalse([name for name in attrs if name == "style" or name.startswith("on")], element)
        self.assertEqual(seen.named("title")[0], {})
        self.assertIn("<title>Approve package change: &lt;script&gt;alert(1)&lt;/script&gt;", body)

    def test_the_queue_the_start_and_the_end_show_it_as_text_too(self):
        for path in ("/", "/queue", "/end"):
            with self.subTest(path=path):
                seen = Seen(self.get(path)[2])
                self.assertLessEqual(seen.tags, PAGE_TAGS)
                self.assertEqual(len(seen.named("script")), 1)
                self.assertEqual(seen.named("img"), [])
                if path != "/":
                    self.assertIn("<script>alert(1)</script> [approve](http://example.com)", seen.said)

    def test_the_agent_s_own_closing_line_in_the_run_report_is_text_on_the_start_page(self):
        """The run report quotes the agent's last line as its word; the start page shows the report's summary."""
        fakes.behave(self.codex_dir, {"summary": "Done.\n\n<script>alert(1)</script><img src=x onerror=alert(2)>\n"})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        seen = Seen(self.get("/")[2])
        self.assertIn('its last line, "<script>alert(1)</script><img src=x onerror=alert(2)>", is neither', seen.said)
        self.assertEqual(len(seen.named("script")), 1)
        self.assertEqual(seen.named("img"), [])

    def test_what_the_founder_typed_comes_back_as_text_when_it_is_refused(self):
        typed = '"><script>alert(1)</script>' + "x" * 300
        status, _, body = self.post(f"/item/{self.item}/decide", {"decision": "reject", "line": typed})
        self.assertEqual(status, 422)
        seen = Seen(body)
        self.assertEqual(len(seen.named("script")), 1)
        self.assertIn(typed, [attrs.get("value") for attrs in seen.named("input")])
        self.assertIn("Nothing was saved.", seen.said)
        self.assertIn("The reason is 327 characters long; one line holds at most 300.", seen.said)
        self.assertEqual(self.records(), [])

    def test_a_decision_named_in_an_item_s_text_is_not_one_the_page_takes(self):
        """The page takes a decision from its own form's fields and from nothing an item says."""
        seen = Seen(self.get(f"/item/{self.item}")[2])
        hidden = [(attrs["name"], attrs["value"]) for attrs in seen.named("input") if attrs.get("type") == "hidden"]
        self.assertEqual(hidden, [("decision", "approve"), ("decision", "reject")])
        self.assertEqual(self.records(), [])


class WalkTest(ServeTestCase):
    def follow(self, answer):
        status, headers, _ = answer
        self.assertEqual(status, 303)
        location = urlsplit(headers["Location"])
        self.assertTrue(location.path.startswith(self.base + "/"))
        path = location.path[len(self.base) :] + (f"?{location.query}" if location.query else "")
        return path, Seen(self.get(path)[2])

    def test_us_me07_through_the_page_one_thing_at_a_time(self):
        ids = self.one_of_each()
        order = [entry["id"] for entry in self.queue()["open"]]
        self.serve()
        start = Seen(self.get("/")[2])
        self.assertIn("What the last run reports", start.said)
        self.assertIn("6 items to decide", start.said)
        (begin,) = [attrs["href"] for attrs in start.named("a") if attrs.get("class") == "button primary"]
        self.assertEqual(begin, f"{self.base}/item/{ids['post']}", "the post with the nearest slot comes first")
        first = Seen(self.get(f"/item/{ids['post']}")[2])
        self.assertIn("Item 1 of 6", first.said)
        self.assertIn("Approve day 1 post", first.said)
        for heading in ("Draft", "Touches", "Evidence", "Your answer"):
            self.assertIn(heading, [text.strip() for text in first.text])

        answers = {
            "post": ("approve", "Good hook."),
            "message": ("reject", "Too salesy for my network."),
            "weekly-read-decision": None,
            "dispatch-request": None,
            "package-change-proposal": ("reject", "Wait for counsel."),
            "notice": ("approve", ""),
        }
        for number, item in enumerate(order):
            kind = next(kind for kind, found in ids.items() if found == item)
            answer = answers[kind]
            if answer is None:
                continue  # left for later: nothing is sent, and nothing is written
            self.at += timedelta(minutes=2)
            path, shown = self.follow(self.post(f"/item/{item}/decide", {"decision": answer[0], "line": answer[1]}))
            onward = f"/item/{order[number + 1]}" if number + 1 < len(order) else "/end"
            self.assertEqual(path, f"{onward}?saved={item}&kind=decisions", "the next thing is shown")
            self.assertIn("Saved.", shown.said)
            self.assertIn(f"founder/decisions/{item}.json", shown.said)
            self.assertIn(answer[1] or "with no note", shown.said)
        self.assertEqual(
            self.records(), sorted(f"{ids[kind]}.json" for kind, answer in answers.items() if answer is not None)
        )
        self.assertEqual(
            self.record("decisions", ids["message"]),
            {
                "exchange": exchange.EXCHANGE_VERSION,
                "item": ids["message"],
                "decision": "reject",
                "reason": "Too salesy for my network.",
                "note": None,
                "decided_at": "2026-10-11T19:46:00-07:00",
                "sitting": DAY,
            },
        )
        queue = Seen(self.get("/queue")[2]).said
        self.assertIn("Queue 4 of 6 decided", queue)
        self.assertEqual(queue.count("Not decided"), 2)

        self.elapsed = 38 * 60.0
        end = Seen(self.get("/end")[2])
        self.assertIn("4 items decided, 2 left for later.", end.said)
        (minutes,) = [attrs["value"] for attrs in end.named("input") if attrs.get("name") == "minutes"]
        self.assertEqual(minutes, "38", "measured by the page")
        path, shown = self.follow(self.post("/end", {"minutes": "41", "note": ""}))
        self.assertEqual(path, f"/end?saved={DAY}&kind=sittings")
        self.assertIn(f"founder/sittings/{DAY}.json", shown.said)
        self.assertIn(f"Saved. The sitting on {DAY} took 41 minutes.", shown.said)
        self.assertEqual(self.record("sittings", DAY)["minutes"], 41, "corrected by the Founder")
        said = self.said.getvalue()
        self.assertIn(f"gr0wthlab: saved founder/decisions/{ids['post']}.json: approve", said)
        self.assertIn(f"gr0wthlab: saved founder/sittings/{DAY}.json: 41 minutes", said)

        second = self.next_run()
        self.assertEqual(
            [(entry["kind"], entry["carried_over"], entry["carried_over_from"]) for entry in second["open"]],
            [("weekly-read-decision", True, DAY), ("dispatch-request", True, DAY)],
        )
        closed = {entry["id"]: entry["status"] for entry in second["closed"]}
        self.assertEqual(
            [closed[ids[kind]] for kind in ("post", "notice", "message", "package-change-proposal")],
            ["approved", "approved", "rejected", "rejected"],
        )
        after = Seen(self.get("/")[2]).said
        self.assertIn("A run finished since you began.", after)
        self.assertIn("2 items to decide", after)
        self.assertIn("2 items carried over from an earlier sitting.", after)
        carried = Seen(self.get(f"/item/{ids['dispatch-request']}")[2]).said
        self.assertIn(f"Carried over from the sitting on {DAY}.", carried)
        self.assertEqual(self.get(f"/item/{ids['post']}")[0], 404, "a decided item is never shown again")
        status, _, body = self.post(f"/item/{ids['post']}/decide", {"decision": "reject", "line": "Too late."})
        self.assertEqual(status, 409)
        self.assertEqual(self.record("decisions", ids["post"])["decision"], "approve")

    def test_a_mis_click_is_changed_or_taken_back_on_the_page_until_a_run_takes_it_in(self):
        item = self.one_proposal()
        self.serve()
        self.follow(self.post(f"/item/{item}/decide", {"decision": "approve", "line": "Fine."}))
        shown = Seen(self.get(f"/item/{item}")[2])
        self.assertIn("Approved, with the note: Fine.", shown.said)
        self.assertIn("You can change it or take it back until a run takes it in.", shown.said)
        self.assertEqual([attrs["action"] for attrs in shown.named("form")], [f"{self.base}/item/{item}/take-back"])
        change = Seen(self.get(f"/item/{item}?change=1")[2])
        self.assertEqual(len([attrs for attrs in change.named("form") if attrs["action"].endswith("/decide")]), 2)
        self.follow(self.post(f"/item/{item}/decide", {"decision": "reject", "line": "Wait for counsel."}))
        self.assertEqual(self.record("decisions", item)["decision"], "reject")
        path, shown = self.follow(self.post(f"/item/{item}/take-back", {}))
        self.assertEqual(path, f"/item/{item}")
        self.assertIn("Your answer", shown.said)
        self.assertEqual(self.records(), [])
        self.follow(self.post(f"/item/{item}/decide", {"decision": "approve", "line": ""}))

        # A run in progress has taken it in: the queue still lists the item, and the page offers no change.
        evidence = self.ledger() / "evidence" / "decisions" / f"{item}.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("{}", encoding="utf-8")
        shown = Seen(self.get(f"/item/{item}")[2])
        self.assertIn("A run has taken this decision in, so it can no longer be changed.", shown.said)
        self.assertEqual(shown.named("form"), [])
        for path, fields in (
            (f"/item/{item}/decide", {"decision": "reject", "line": "No."}),
            (f"/item/{item}/take-back", {}),
        ):
            status, _, body = self.post(path, fields)
            self.assertEqual(status, 422)
            self.assertIn(
                "A run has already taken in your decision on this item, so it can no longer be changed.", body
            )
        self.assertEqual(self.record("decisions", item)["decision"], "approve")

    def test_an_empty_queue_and_no_queue_are_each_said_plainly(self):
        self.serve()
        seen = Seen(self.get("/")[2])
        self.assertIn("There is no Review Queue to show", seen.said)
        self.assertIn("No run has written a Review Queue in this checkout yet.", seen.said)
        self.assertEqual(self.get("/queue")[0], 200)
        self.assertEqual(self.get("/end")[0], 200)
        self.run_cycle()
        seen = Seen(self.get("/")[2])
        self.assertIn("Nothing is waiting for you", seen.said)
        self.assertIn("The Review Queue has no open item.", seen.said)
        self.assertIn("The Review Queue had no open item.", Seen(self.get("/end")[2]).said)

    def test_the_run_due_that_has_not_finished_is_said_first(self):
        self.one_proposal()
        self.serve(self.sit_down(SITTING + timedelta(days=7)))
        for path in ("/", "/queue", "/end"):
            with self.subTest(path=path):
                said = Seen(self.get(path)[2]).said
                self.assertIn("The weekly run due has not finished.", said)
                self.assertIn("It was due Sunday 2026-10-18 16:00", said)
                self.assertIn("are from the earlier run that ended Sunday 2026-10-11 16:00", said)

    def test_the_place_for_what_the_founder_did(self):
        item = self.one_of_each()["message"]
        self.serve()
        said = Seen(self.get("/did")[2]).said
        self.assertIn("No message is approved yet.", said)
        self.follow(self.post(f"/item/{item}/decide", {"decision": "approve", "line": ""}))
        shown = Seen(self.get("/did")[2])
        self.assertIn("Not recorded as sent.", shown.said)
        (form,) = [attrs["action"] for attrs in shown.named("form") if "/did/sent/" in attrs["action"]]
        self.assertEqual(form, f"{self.base}/did/sent/{item}")
        status, _, body = self.post(
            f"/did/sent/{item}", {"sent_on": "2026-10-12", "replied_on": "", "wait_days": "", "note": ""}
        )
        self.assertEqual(status, 422)
        self.assertIn("The day it was sent is 2026-10-12, which has not come yet.", Seen(body).said)
        self.assertIn("2026-10-12", [attrs.get("value") for attrs in Seen(body).named("input")], "what was typed stays")
        fields = {"sent_on": DAY, "replied_on": "", "wait_days": "10", "note": "By their contact form."}
        path, shown = self.follow(self.post(f"/did/sent/{item}", fields))
        self.assertEqual(path, f"/did?saved={item}&kind=outreach")
        self.assertIn(f"founder/outreach/{item}.json", shown.said)
        self.assertIn(f"Sent on {DAY}; no reply recorded.", shown.said)
        self.assertIn(f"Saved. {item}: sent on {DAY}; no reply recorded; a follow-up waits 10 days.", shown.said)
        self.assertEqual(
            self.record("outreach", item),
            {
                "exchange": exchange.EXCHANGE_VERSION,
                "item": item,
                "sent_on": DAY,
                "replied_on": None,
                "follow_up_wait_days": 10,
                "note": "By their contact form.",
            },
        )

    def test_a_beta_build_its_counts_and_a_stop_on_the_page(self):
        self.one_proposal()
        self.serve()
        shown = Seen(self.get("/did")[2])
        self.assertIn("No Beta Build is recorded, so gr0wthlab does nothing about its Beta Cohort.", shown.said)
        self.assertEqual(self.get("/counts/RepToday")[0], 404, "no counts before an approval")
        path, shown = self.follow(
            self.post("/did/beta-build/RepToday", {"approved_on": "2026-10-09", "build": "1.0 (42)"})
        )
        self.assertEqual(path, "/did?saved=RepToday&kind=beta-builds")
        self.assertIn("Beta Build approved on 2026-10-09, build 1.0 (42). Recruiting is open.", shown.said)
        self.assertIn("Saved. RepToday: Beta Build approved on 2026-10-09; recruiting is open.", shown.said)
        self.assertEqual(self.record("beta-builds", "RepToday")["recruiting"], "open")
        walk = Seen(self.get("/counts/RepToday")[2])
        self.assertIn("A count you leave blank is recorded as not reported, never as zero.", walk.said)
        counts = [attrs for attrs in walk.named("input") if attrs["name"] in exchange.BETA_COUNTS]
        self.assertEqual([attrs["value"] for attrs in counts], ["", "", ""], "no count is filled in for the Founder")
        status, _, body = self.post("/counts/RepToday", {"invitations_sent": "", "accepted": "", "sessions_booked": ""})
        self.assertEqual(status, 422)
        self.assertIn("Give at least one count", Seen(body).said)
        fields = {"invitations_sent": "10", "accepted": "", "sessions_booked": ""}
        path, shown = self.follow(self.post("/counts/RepToday", fields))
        self.assertEqual(path, f"/counts/RepToday?saved=RepToday-{DAY}&kind=beta-reports")
        words = "invitations sent 10, accepted not reported, first sessions booked not reported"
        self.assertIn(f"Saved. RepToday, on {DAY}: {words}.", shown.said)
        record = self.record("beta-reports", f"RepToday-{DAY}")
        self.assertEqual((record["invitations_sent"], record["accepted"], record["sessions_booked"]), (10, None, None))
        again = Seen(self.get("/counts/RepToday")[2])
        kept = {
            attrs["name"]: attrs["value"] for attrs in again.named("input") if attrs["name"] in exchange.BETA_COUNTS
        }
        self.assertEqual(kept, {"invitations_sent": "10", "accepted": "", "sessions_booked": ""})
        _, shown = self.follow(self.post("/did/recruiting/RepToday", {"recruiting": "stop", "stopped_on": DAY}))
        self.assertIn(f"Saved. RepToday: Beta Build approved on 2026-10-09; recruiting stopped on {DAY}.", shown.said)
        self.assertEqual(self.record("beta-builds", "RepToday")["recruiting"], "stopped")
        self.assertIn(f"Recruiting has been stopped since {DAY}.", Seen(self.get("/did")[2]).said)
        self.follow(self.post("/did/recruiting/RepToday", {"recruiting": "reopen"}))
        self.assertEqual(self.record("beta-builds", "RepToday")["stopped_on"], None)
        self.assertEqual(self.post("/did/recruiting/RepToday", {"recruiting": "delete"})[0], 404)


class VideoTest(ServeTestCase):
    def test_a_post_s_video_is_played_from_its_own_file_whole_or_in_part(self):
        item = self.one_proposal()
        state = self.sit_down()
        video = self.ledger() / "assets" / "window-1" / "day-01-0a1b2c3d4e5f.mp4"
        video.parent.mkdir(parents=True)
        data = bytes(range(256)) * 40
        video.write_bytes(data)
        state.look = lambda look=state.look: self.with_video(look(), state, video)
        self.serve(state)
        shown = Seen(self.get(f"/item/{item}")[2])
        (source,) = shown.named("source")
        self.assertEqual(source, {"src": f"{self.base}/video/{item}", "type": "video/mp4"})
        (player,) = shown.named("video")
        self.assertEqual(sorted(player), ["controls", "playsinline", "preload"], "it never starts by itself")
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        self.addCleanup(connection.close)

        def fetch(span=None):
            connection.request("GET", f"{self.base}/video/{item}", headers={"Range": span} if span else {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()

        status, headers, body = fetch()
        self.assertEqual(
            (status, headers["Content-Type"], headers["Accept-Ranges"], body), (200, "video/mp4", "bytes", data)
        )
        self.assertIn("Content-Security-Policy", headers)
        for span, start, end in (
            ("bytes=0-99", 0, 99),
            ("bytes=1000-", 1000, len(data) - 1),
            ("bytes=-10", len(data) - 10, len(data) - 1),
        ):
            with self.subTest(span=span):
                status, headers, body = fetch(span)
                self.assertEqual(status, 206)
                self.assertEqual(headers["Content-Range"], f"bytes {start}-{end}/{len(data)}")
                self.assertEqual(body, data[start : end + 1])
        self.assertEqual(fetch(f"bytes={len(data)}-")[0], 416)
        self.assertEqual(self.get("/video/20261011-no-such-item")[0], 404)
        self.assertEqual(self.ask("GET", f"/video/{item}")[0], 404, "never without the secret")

    def with_video(self, view, state, video):
        import hashlib

        for entry in view.entries:
            relative = str(video.relative_to(self.ledger()))
            entry.entry = dict(
                entry.entry, kind="post", asset=relative, asset_sha256=hashlib.sha256(video.read_bytes()).hexdigest()
            )
            entry.video = state.video(entry.entry)
        return view

    def test_a_video_that_is_not_the_file_the_post_was_queued_with_is_neither_played_nor_approved(self):
        item = self.one_proposal()
        state = self.sit_down()
        video = self.ledger() / "assets" / "window-1" / "day-01-0a1b2c3d4e5f.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"the cut the run measured")
        look = state.look

        def changed():
            view = self.with_video(look(), state, video)
            for entry in view.entries:
                entry.entry = dict(entry.entry, asset_sha256="0" * 64)
                entry.video = state.video(entry.entry)
            return view

        state.look = changed
        self.serve(state)
        shown = Seen(self.get(f"/item/{item}")[2])
        self.assertEqual(shown.named("video"), [])
        self.assertIn("is not the file this post was queued with", shown.said)
        self.assertIn("this post cannot be approved until its video can be shown", shown.said)
        forms = [Seen(self.get(f"/item/{item}")[2]).named("input")]
        self.assertEqual([attrs["value"] for attrs in forms[0] if attrs.get("type") == "hidden"], ["reject"])
        self.assertEqual(self.get(f"/video/{item}")[0], 404)
        status, _, body = self.post(f"/item/{item}/decide", {"decision": "approve", "line": ""})
        self.assertEqual(status, 422)
        self.assertIn("so the video and its copy cannot be approved", Seen(body).said)
        self.assertEqual(self.records(), [])


class StopTest(ServeTestCase):
    def test_the_page_stops_from_its_last_page_and_only_by_a_post_of_its_own(self):
        self.one_proposal()
        server = self.serve()
        self.assertEqual(self.post("/stop", {}, Origin="http://evil.example")[0], 403)
        self.assertEqual(self.get("/")[0], 200)
        status, _, body = self.post("/stop", {})
        self.assertEqual(status, 200)
        self.assertIn("The page has stopped", body)
        self.assertIn("Everything you saved is in ledger/founder/, and the next run takes it in.", body)
        stopped = threading.Event()
        threading.Thread(target=lambda: (server.shutdown(), stopped.set()), daemon=True).start()
        self.assertTrue(stopped.wait(5), "serving has ended")
        self.assertIn("gr0wthlab: stopped from the page", self.said.getvalue())

    def test_only_one_sitting_page_is_served_for_a_checkout(self):
        import fcntl

        from gr0wthlab.boundary import ConfigError

        self.one_proposal()
        holder = (self.ledger() / "sitting.lock").open("a")
        self.addCleanup(holder.close)
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with self.assertRaises(ConfigError) as raised:
            serve.serve(self.repo, self.env, 0, io.StringIO())
        self.assertEqual(
            str(raised.exception), "another sitting page is already being served for this checkout; stop it first"
        )


if __name__ == "__main__":
    unittest.main()
