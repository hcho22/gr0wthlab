"""The launcher's network client: what it may request, what robots.txt binds, and what it logs.

These are the contract tests of Guardrails G5 and G8 for the network: the client can issue only a credential-free GET
to a listed host, never a path the host's robots.txt disallows, and in a unit test nothing can open a connection
beyond this machine, so the whole runs in test_work_cycle show that nothing but this client tries to.
"""

import http.client
import json
import unittest
from pathlib import Path
from unittest import mock

import tests
from gr0wthlab import fetch
from gr0wthlab.boundary import ConfigError
from tests import fakes

REPO = Path(__file__).resolve().parents[2]
POLICY = {
    "hosts": ["forum.example.com", "store.example.org"],
    "user_agent": "growthlab-reader/1 (unit tests; +https://example.com/contact)",
    "max_requests_per_run": 6,
    "seconds_between_requests_per_host": 2,
    "timeout_seconds": 5,
    "max_response_bytes": 2048,
    "max_wait_seconds": 30,
}


def client(web, **overrides):
    return fakes.client(web, dict(POLICY, **overrides))


class PolicyTest(unittest.TestCase):
    def test_the_committed_policy_lists_two_public_hosts_and_an_honest_reader(self):
        policy = fetch.load_policy(REPO)
        self.assertEqual(policy.hosts, ("www.reddit.com", "itunes.apple.com"))
        self.assertEqual(policy.token, "growthlab-reader")
        self.assertIn("github.com/hcho22", policy.user_agent)
        self.assertLessEqual(policy.max_requests, 30)

    def test_a_host_that_is_not_one_public_name_is_refused(self):
        for host in (
            "localhost",
            "127.0.0.1",
            "[::1]",
            "example.com:8443",
            "https://example.com",
            "example.com/path",
            "*.example.com",
            "printer.local",
            "db.internal",
            "Example.com",
            "user@example.com",
            "",
            7,
        ):
            with self.subTest(host=host), self.assertRaises(ConfigError):
                fetch.policy_from(dict(POLICY, hosts=[host]))
        for hosts in ([], ["a.example.com", "a.example.com"], "forum.example.com", None):
            with self.subTest(hosts=hosts), self.assertRaises(ConfigError):
                fetch.policy_from(dict(POLICY, hosts=hosts))

    def test_the_user_agent_names_a_product_token_and_no_address(self):
        for agent in ("", "Mozilla", "reader/1 (me@example.com)", "gr0wthlab/1 (digit in the token)", "a/1 (x\ny)"):
            with self.subTest(agent=agent), self.assertRaises(ConfigError):
                fetch.policy_from(dict(POLICY, user_agent=agent))

    def test_limits_are_whole_numbers_in_range(self):
        for key, value in (
            ("max_requests_per_run", 0),
            ("max_requests_per_run", 201),
            ("seconds_between_requests_per_host", 0),
            ("timeout_seconds", True),
            ("max_response_bytes", "big"),
            ("max_wait_seconds", -1),
        ):
            with self.subTest(key=key), self.assertRaises(ConfigError):
                fetch.policy_from(dict(POLICY, **{key: value}))


class OnlyListedReadsTest(unittest.TestCase):
    def test_a_listed_address_is_read_with_one_get(self):
        web = fakes.Web({"https://forum.example.com/threads.xml": "<feed/>"})
        reader = client(web)
        result = reader.get("https://forum.example.com/threads.xml", "threads")
        self.assertTrue(result.ok)
        self.assertEqual(result.body, b"<feed/>")
        self.assertEqual(
            web.requests, ["https://forum.example.com/robots.txt", "https://forum.example.com/threads.xml"]
        )
        self.assertEqual({entry["method"] for entry in reader.log}, {"GET"})

    def test_an_address_outside_the_rules_is_never_sent(self):
        web = fakes.Web({})
        reader = client(web)
        for url in (
            "https://evil.example.net/x",
            "http://forum.example.com/x",
            "https://forum.example.com:8443/x",
            "https://user:secret@forum.example.com/x",
            "https://forum.example.com@evil.example.net/x",
            "https://forum.example.com.evil.example.net/x",
            "https://FORUM.example.com/x",
            "https://127.0.0.1/x",
            "https://localhost/x",
            "https://forum.example.com/x#fragment",
            "https://forum.example.com",
            "https://forum.example.com/a b",
            "https://forum.example.com/a\\b",
            "https://forum.example.com/a\r\nHost: evil.example.net",
            "ftp://forum.example.com/x",
            "file:///etc/passwd",
            "//forum.example.com/x",
            "https://forum.example.com/" + "a" * 2100,
            "",
        ):
            with self.subTest(url=url):
                result = reader.get(url, "probe")
                self.assertEqual(result.status, fetch.REFUSED, result.detail)
        self.assertEqual(web.requests, [])
        self.assertEqual([entry["sent"] for entry in reader.log], [False] * len(reader.log))
        self.assertEqual(reader.summary()["sent"], 0)

    def test_what_goes_on_the_wire_is_one_get_with_no_body_cookie_or_credential(self):
        connections = []

        class Connection:
            def __init__(self, host, port, timeout=None, context=None):
                self.host, self.port, self.context, self.calls = host, port, context, []
                connections.append(self)

            def request(self, method, url, body=None, headers=None, **more):
                self.calls.append((method, url, body, dict(headers or {}), more))

            def getresponse(self):
                response = mock.Mock(status=200)
                response.getheaders.return_value = [("Content-Type", "text/plain")]
                response.read.return_value = b"ok"
                return response

            def close(self):
                self.calls.append("closed")

        with mock.patch.object(http.client, "HTTPSConnection", Connection):
            reader = fakes.client(None, POLICY)
            reader.transport = tests.REAL_SEND
            result = reader.get("https://forum.example.com/threads.xml?page=1", "threads")
        self.assertTrue(result.ok, result.detail)
        self.assertEqual([(c.host, c.port) for c in connections], [("forum.example.com", 443)] * 2)
        for connection in connections:
            (method, _, body, headers, more), closed = connection.calls
            self.assertEqual((method, body, more, closed), ("GET", None, {}, "closed"))
            self.assertEqual(
                sorted(headers), ["Accept", "Accept-Encoding", "Connection", "User-Agent"], "no cookie or credential"
            )
            self.assertEqual(headers["User-Agent"], POLICY["user_agent"])
            self.assertTrue(connection.context.check_hostname)
        self.assertEqual(connections[1].calls[0][1], "/threads.xml?page=1")

    def test_a_redirect_is_followed_only_to_a_listed_host(self):
        web = fakes.Web(
            {
                "https://forum.example.com/old": (301, {"location": "https://store.example.org/new"}, ""),
                "https://store.example.org/new": "moved here",
                "https://forum.example.com/out": (302, {"location": "https://evil.example.net/x"}, ""),
                "https://forum.example.com/down": (302, {"location": "http://forum.example.com/x"}, ""),
                "https://forum.example.com/loop": (302, {"location": "/loop"}, ""),
            }
        )
        reader = client(web, max_requests_per_run=20)
        self.assertEqual(reader.get("https://forum.example.com/old", "a").body, b"moved here")
        for path in ("out", "down"):
            result = reader.get(f"https://forum.example.com/{path}", "b")
            self.assertEqual(result.status, fetch.FAILED)
            self.assertIn("redirected to an address this reader never follows", result.detail)
        self.assertIn("more than 3 redirects", reader.get("https://forum.example.com/loop", "c").detail)
        self.assertNotIn("evil.example.net", " ".join(web.requests))
        self.assertTrue(all(url.startswith("https://") for url in web.requests))

    def test_a_redirect_to_an_address_that_cannot_be_parsed_is_a_failed_read(self):
        web = fakes.Web({"https://forum.example.com/odd": (302, {"location": "https://[x"}, "")})
        result = client(web).get("https://forum.example.com/odd", "odd")
        self.assertEqual(result.status, fetch.FAILED)
        self.assertIn("redirected to an address that cannot be parsed", result.detail)
        self.assertEqual(web.requests, ["https://forum.example.com/robots.txt", "https://forum.example.com/odd"])

    def test_an_address_the_wire_cannot_carry_is_a_failed_read(self):
        reader = fakes.client(None, POLICY)
        reader.transport = tests.REAL_SEND
        reader.robots["forum.example.com"] = fetch.Robots("forum.example.com", "none")
        result = reader.get("https://forum.example.com/caf\u00e9", "threads")
        self.assertEqual(result.status, fetch.FAILED)
        self.assertIn("forum.example.com could not be read: UnicodeEncodeError", result.detail)
        self.assertEqual([entry["outcome"] for entry in reader.log], [fetch.FAILED])

    def test_an_answer_over_the_size_limit_is_a_failure_not_a_cut_read(self):
        web = fakes.Web({"https://forum.example.com/big": "x" * 5000})
        result = client(web).get("https://forum.example.com/big", "big")
        self.assertEqual((result.status, result.body), (fetch.FAILED, b""))
        self.assertIn("larger than 2,048 bytes", result.detail)

    def test_a_run_sends_no_more_than_its_limit(self):
        web = fakes.Web({f"https://forum.example.com/{n}": "ok" for n in range(10)})
        reader = client(web, max_requests_per_run=4)
        results = [reader.get(f"https://forum.example.com/{n}", "n") for n in range(10)]
        self.assertEqual([result.ok for result in results], [True] * 3 + [False] * 7)
        self.assertEqual(len(web.requests), 4)
        self.assertIn("limit of 4 requests is used up", results[3].detail)

    def test_a_network_failure_is_a_failed_read_with_its_reason(self):
        web = fakes.Web({"https://forum.example.com/x": OSError("connection reset")})
        result = client(web).get("https://forum.example.com/x", "x")
        self.assertEqual(result.status, fetch.FAILED)
        self.assertIn("OSError: connection reset", result.detail)


class RobotsTest(unittest.TestCase):
    def allows(self, text, target, token="growthlab-reader"):
        return fetch.parse_robots("forum.example.com", text, token).allows(target)[0]

    def test_a_disallowed_path_is_never_requested(self):
        web = fakes.Web(
            {"https://forum.example.com/threads.xml": "<feed/>"},
            robots={"forum.example.com": "User-agent: *\nDisallow: /\n"},
        )
        reader = client(web)
        result = reader.get("https://forum.example.com/threads.xml", "threads")
        self.assertEqual(result.status, fetch.DISALLOWED)
        self.assertIn(
            "robots.txt on forum.example.com disallows it for automated readers (`Disallow: /`)", result.detail
        )
        self.assertEqual(web.requests, ["https://forum.example.com/robots.txt"])
        self.assertEqual([entry["sent"] for entry in reader.log], [True, False])

    def test_the_named_sources_are_disallowed_by_their_hosts_today(self):
        """The two robots.txt files as read on 2026-10-11, and the path each named source would need."""
        reddit = "# Welcome\n\nUser-agent: *\nDisallow: /\n"
        apple = (
            "User-agent: *\nDisallow: /WebObjects/*\nAllow: /WebObjects/MZStore.woa/wa/viewMultiRoom?*\n"
            "Disallow: /search*\nDisallow: /*/rss/*\nDisallow: /*/lookup?\n\nUser-agent: Googlebot\nDisallow: /x\n"
        )
        self.assertFalse(self.allows(reddit, "/r/fitness30plus/new/.rss"))
        self.assertFalse(self.allows(reddit, "/r/fitness30plus/about/rules.json"))
        self.assertFalse(self.allows(apple, "/us/rss/customerreviews/page=1/id=301521403/sortby=mostrecent/json"))
        self.assertTrue(self.allows(apple, "/us/app/id301521403"))

    def test_a_byte_order_mark_does_not_hide_the_first_group(self):
        marked = "\ufeffUser-agent: *\nDisallow: /\n"
        self.assertFalse(self.allows(marked, "/x"))
        web = fakes.Web({"https://forum.example.com/x": "x"}, robots={"forum.example.com": marked})
        result = client(web).get("https://forum.example.com/x", "x")
        self.assertEqual(result.status, fetch.DISALLOWED)
        self.assertEqual(web.requests, ["https://forum.example.com/robots.txt"])

    def test_the_longest_rule_wins_and_allow_wins_a_tie(self):
        text = "User-agent: *\nDisallow: /a\nAllow: /a/b\nDisallow: /a/b/c\nAllow: /tie\nDisallow: /tie\n"
        self.assertFalse(self.allows(text, "/a/x"))
        self.assertTrue(self.allows(text, "/a/b/x"))
        self.assertFalse(self.allows(text, "/a/b/c/x"))
        self.assertTrue(self.allows(text, "/tie"))
        self.assertTrue(self.allows(text, "/other"))

    def test_wildcards_and_the_end_anchor(self):
        text = "User-agent: *\nDisallow: /*.json$\nDisallow: /p/*/edit\nDisallow: /q?x=\n"
        self.assertFalse(self.allows(text, "/r/a/about/rules.json"))
        self.assertTrue(self.allows(text, "/r/a/about/rules.json?raw=1"))
        self.assertFalse(self.allows(text, "/p/12/edit/now"))
        self.assertTrue(self.allows(text, "/p/12/view"))
        self.assertFalse(self.allows(text, "/q?x=1"))
        self.assertTrue(self.allows(text, "/q?y=1"))

    def test_a_group_naming_this_reader_replaces_the_star_group(self):
        text = (
            "User-agent: *\nDisallow: /\n\nUser-agent: other\nUser-agent: Growthlab-Reader\nAllow: /feeds/\n"
            "Disallow: /private/\n\nUser-agent: growthlab-reader\nDisallow: /also/\n"
        )
        self.assertTrue(self.allows(text, "/feeds/a"))
        self.assertTrue(self.allows(text, "/anything"))
        self.assertFalse(self.allows(text, "/private/a"))
        self.assertFalse(self.allows(text, "/also/a"))
        self.assertFalse(self.allows(text, "/feeds/a", token="someone-else"))

    def test_records_outside_a_group_and_empty_rules_change_nothing(self):
        text = (
            "Disallow: /early\nSitemap: https://x.example/s.xml\nUser-agent: *\nSitemap: s\nDisallow:\nAllow:\n# c\n"
            "Disallow: /b # c\n"
        )
        self.assertTrue(self.allows(text, "/early"))
        self.assertTrue(self.allows(text, "/a"))
        self.assertFalse(self.allows(text, "/b"))
        self.assertTrue(self.allows("", "/a"))

    def test_an_encoded_path_matches_the_rule_it_spells(self):
        text = "User-agent: *\nDisallow: /caf%C3%A9\nDisallow: /a%2fb\nDisallow: /%7Euser\n"
        self.assertFalse(self.allows(text, "/caf%c3%a9/menu"))
        self.assertFalse(self.allows(text, "/café"))
        self.assertFalse(self.allows(text, "/a%2Fb"))
        self.assertTrue(self.allows(text, "/a/b"))
        self.assertFalse(self.allows(text, "/~user"))

    def test_no_robots_txt_disallows_nothing_and_an_unreadable_one_disallows_everything(self):
        pages = {"https://forum.example.com/a": "a", "https://store.example.org/a": "a"}
        for status, readable in ((404, True), (410, True), (403, False), (401, False), (429, False), (500, False)):
            with self.subTest(status=status):
                web = fakes.Web(pages, robots={"forum.example.com": (status, {}, "")})
                result = client(web).get("https://forum.example.com/a", "a")
                self.assertEqual(result.ok, readable, result.detail)
                if not readable:
                    self.assertEqual(result.status, fetch.DISALLOWED)
                    self.assertIn("robots.txt on forum.example.com could not be read", result.detail)
                    self.assertEqual(web.requests, ["https://forum.example.com/robots.txt"])
        web = fakes.Web(pages, robots={"forum.example.com": OSError("no route to host")})
        reader = client(web)
        self.assertEqual(reader.get("https://forum.example.com/a", "a").status, fetch.DISALLOWED)
        self.assertTrue(reader.get("https://store.example.org/a", "a").ok, "another host is judged by its own file")

    def test_robots_txt_is_read_once_per_host_and_cut_at_its_limit(self):
        long_file = "User-agent: *\nDisallow: /private\n" + "# padding\n" * 80_000
        web = fakes.Web({"https://forum.example.com/a": "a", "https://forum.example.com/private": "p"})
        web.robots["forum.example.com"] = long_file
        reader = client(web)
        self.assertTrue(reader.get("https://forum.example.com/a", "a").ok)
        self.assertEqual(reader.get("https://forum.example.com/private", "p").status, fetch.DISALLOWED)
        self.assertEqual(web.requests.count("https://forum.example.com/robots.txt"), 1)

    def test_a_redirect_is_bound_by_the_robots_txt_of_where_it_lands(self):
        web = fakes.Web(
            {
                "https://forum.example.com/go": (302, {"location": "https://store.example.org/secret"}, ""),
                "https://store.example.org/secret": "s",
            },
            robots={"store.example.org": "User-agent: *\nDisallow: /secret\n"},
        )
        result = client(web).get("https://forum.example.com/go", "go")
        self.assertEqual(result.status, fetch.DISALLOWED)
        self.assertNotIn("https://store.example.org/secret", web.requests)


class PaceTest(unittest.TestCase):
    def test_requests_to_one_host_are_spaced_out(self):
        web = fakes.Web({"https://forum.example.com/a": "a", "https://forum.example.com/b": "b"})
        reader = client(web)
        reader.get("https://forum.example.com/a", "a")
        reader.get("https://forum.example.com/b", "b")
        self.assertEqual(web.slept, [2.0, 2.0])

    def test_a_crawl_delay_is_kept_when_short_and_closes_the_host_when_long(self):
        pages = {"https://forum.example.com/a": "a", "https://forum.example.com/b": "b"}
        web = fakes.Web(pages, robots={"forum.example.com": "User-agent: *\nCrawl-delay: 10\nAllow: /\n"})
        reader = client(web)
        self.assertTrue(reader.get("https://forum.example.com/a", "a").ok)
        self.assertTrue(reader.get("https://forum.example.com/b", "b").ok)
        self.assertEqual(web.slept, [10.0, 10.0])
        web = fakes.Web(pages, robots={"forum.example.com": "User-agent: *\nCrawl-delay: 600\n"})
        reader = client(web)
        result = reader.get("https://forum.example.com/a", "a")
        self.assertEqual(result.status, fetch.FAILED)
        self.assertIn("asked for a wait of 600 s between requests, longer than this run waits", result.detail)
        self.assertEqual((web.slept, len(web.requests)), ([], 1))

    def test_a_short_retry_after_is_waited_for_once(self):
        web = fakes.Web({"https://forum.example.com/a": [(429, {"retry-after": "7"}, ""), "a"]})
        reader = client(web)
        self.assertTrue(reader.get("https://forum.example.com/a", "a").ok)
        self.assertEqual(web.slept, [2.0, 7.0])
        web = fakes.Web({"https://forum.example.com/a": [(429, {"retry-after": "7"}, "")] * 2 + ["a"]})
        result = client(web).get("https://forum.example.com/a", "a")
        self.assertEqual(result.status, fetch.FAILED)
        self.assertEqual(web.requests.count("https://forum.example.com/a"), 2)

    def test_a_long_or_unstated_wait_closes_the_host_for_the_run(self):
        for headers, asked in (
            ({"retry-after": "3600"}, "for 3600 s"),
            ({"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}, "without saying for how long"),
            ({}, "without saying for how long"),
        ):
            with self.subTest(headers=headers):
                pages = {"https://forum.example.com/a": (429, headers, ""), "https://forum.example.com/b": "b"}
                web = fakes.Web(pages)
                reader = client(web)
                first = reader.get("https://forum.example.com/a", "a")
                self.assertEqual(first.status, fetch.FAILED)
                self.assertIn(f"answered HTTP 429 and asked this reader to wait {asked}", first.detail)
                second = reader.get("https://forum.example.com/b", "b")
                self.assertEqual(second.status, fetch.FAILED, "the host is not asked again")
                self.assertEqual(web.requests.count("https://forum.example.com/b"), 0)

    def test_a_plain_server_error_is_one_failure_and_the_host_stays_open(self):
        web = fakes.Web({"https://forum.example.com/a": (503, {}, ""), "https://forum.example.com/b": "b"})
        reader = client(web)
        self.assertIn("HTTP 503", reader.get("https://forum.example.com/a", "a").detail)
        self.assertTrue(reader.get("https://forum.example.com/b", "b").ok)


class RequestLogTest(unittest.TestCase):
    def test_the_log_holds_every_request_sent_or_not(self):
        web = fakes.Web(
            {"https://forum.example.com/a": "a"}, robots={"store.example.org": "User-agent: *\nDisallow: /\n"}
        )
        reader = client(web)
        reader.get("https://forum.example.com/a", "threads")
        reader.get("https://store.example.org/reviews", "reviews")
        reader.get("https://evil.example.net/x", "never")
        summary = json.loads(json.dumps(reader.summary()))
        self.assertEqual((summary["sent"], summary["not_sent"], summary["bodies_sent"]), (3, 2, 0))
        self.assertEqual(summary["methods_sent"], ["GET"])
        self.assertEqual(summary["hosts_contacted"], ["forum.example.com", "store.example.org"])
        self.assertLessEqual(set(summary["hosts_contacted"]), set(POLICY["hosts"]))
        self.assertEqual(
            [(entry["purpose"], entry["sent"], entry["outcome"]) for entry in summary["requests"]],
            [
                ("robots.txt of forum.example.com", True, "HTTP 404"),
                ("threads", True, "HTTP 200"),
                ("robots.txt of store.example.org", True, "HTTP 200"),
                ("reviews", False, "disallowed"),
                ("never", False, "refused"),
            ],
        )
        self.assertEqual(summary["robots"]["store.example.org"]["rules"], ["Disallow: /"])


class OnlyOneDoorTest(unittest.TestCase):
    """No unit test can leave this machine, so a whole run under test (test_work_cycle) reads the web only through
    the transport its client was given."""

    def test_the_client_s_own_send_is_replaced_by_a_refusal(self):
        with self.assertRaises(AssertionError):
            fetch.send("forum.example.com", "/robots.txt", {}, 1.0, 10)

    def test_the_real_send_is_stopped_before_it_leaves_this_machine(self):
        tried = len(tests.ATTEMPTS)
        with self.assertRaises(AssertionError):
            tests.REAL_SEND("forum.example.com", "/robots.txt", {}, 1.0, 10)
        self.assertEqual(tests.ATTEMPTS[tried:], ["forum.example.com"])
        del tests.ATTEMPTS[tried:]


if __name__ == "__main__":
    unittest.main()
