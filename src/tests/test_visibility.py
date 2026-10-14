"""Whether the repository a production clone pushes to is private, asked of a stand-in for gh: private only on GitHub's
plain word, and never on an answer that could not be had or is not clear."""

import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gr0wthlab import visibility
from tests import REAL_ASK, fakes

PRIVATE = json.dumps({"full_name": "example/records", "private": True, "visibility": "private"})
PUBLIC = json.dumps({"full_name": "example/records", "private": False, "visibility": "public"})


class RepositoryTest(unittest.TestCase):
    def test_a_github_push_address_names_its_repository(self):
        for address in (
            "https://github.com/example/records.git",
            "https://github.com/example/records",
            "https://github.com/example/records/",
            "https://someone@github.com/example/records.git",
            "git@github.com:example/records.git",
            "ssh://git@github.com/example/records.git",
            "ssh://git@github.com:22/example/records",
        ):
            self.assertEqual(visibility.repository(address + "\n"), "example/records", address)

    def test_any_other_address_names_none(self):
        for address in (
            "/srv/remote.git",
            "file:///srv/remote.git",
            "https://gitlab.com/example/records.git",
            "https://github.example.com/example/records.git",
            "https://github.com.example.net/example/records.git",
            "https://github.com/example",
            "https://github.com/example/records/tree/main",
            "http://github.com/example/records.git",
            "",
        ):
            self.assertIsNone(visibility.repository(address), address)


class ReadTest(unittest.TestCase):
    def test_private_and_public_only_when_both_fields_agree(self):
        self.assertEqual(visibility.read("example/records", PRIVATE).status, visibility.PRIVATE)
        self.assertEqual(visibility.read("example/records", PUBLIC).status, visibility.PUBLIC)
        for answer in (
            {"private": True, "visibility": "internal"},
            {"private": True},
            {"visibility": "private"},
            {"private": "true", "visibility": "private"},
            {"private": False, "visibility": "private"},
            {"private": True, "visibility": "public"},
            {},
            [],
            "private",
        ):
            read = visibility.read("example/records", json.dumps(answer))
            self.assertEqual(read.status, visibility.UNCONFIRMED, answer)
            self.assertFalse(read.private)
        self.assertEqual(visibility.read("example/records", "not json").status, visibility.UNCONFIRMED)

    def test_the_refusals_say_what_a_real_run_would_publish(self):
        public = visibility.read("example/records", PUBLIC)
        self.assertEqual(
            public.refusal,
            "the GitHub repository `example/records` is public: a real run would publish its Drafts, its Evidence,"
            " and the Founder's records there, so the repository must be made private first",
        )
        unclear = visibility.Answer(visibility.UNCONFIRMED, "GitHub did not answer within 1 min")
        self.assertEqual(
            unclear.refusal,
            "could not confirm that the GitHub repository is private (GitHub did not answer within 1 min), and a real"
            " run would publish its Drafts, its Evidence, and the Founder's records there",
        )


class AskTest(unittest.TestCase):
    """The whole question, from the clone's push address through gh's answer, with a stand-in for gh."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.env = fakes.git_env(self.root)
        self.repo = self.root / "clone"
        self.repo.mkdir()
        fakes.git(self.repo, "init", "--quiet", env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", "https://github.com/example/records.git", env=self.env)
        self.calls = self.root / "gh-calls.txt"

    def gh(self, stdout="", stderr="", code=0, wait=0):
        """A stand-in for gh that notes its arguments and its login's environment, then answers as told."""
        script = self.root / "gh"
        script.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> {shlex.quote(str(self.calls))}\n'
            f'printf "token=%s prompt=%s\\n" "$GH_TOKEN" "$GH_PROMPT_DISABLED" >> {shlex.quote(str(self.calls))}\n'
            + (f"sleep {wait}\n" if wait else "")
            + f"printf %s {shlex.quote(stdout)}\n"
            + f"printf %s {shlex.quote(stderr)} >&2\n"
            + f"exit {code}\n"
        )
        script.chmod(0o755)
        self.env[visibility.GH_ENV] = str(script)

    def ask(self, remote="origin"):
        return REAL_ASK(self.repo, remote, self.env)

    def test_the_tests_never_ask_github_itself(self):
        with self.assertRaises(AssertionError):
            visibility.ask(self.repo, "origin", self.env)

    def test_private(self):
        self.gh(PRIVATE)
        self.env["GH_TOKEN"] = "the-login"
        answer = self.ask()
        self.assertTrue(answer.private, answer.detail)
        self.assertEqual(answer.detail, "GitHub says the repository `example/records` is private")
        self.assertEqual(
            self.calls.read_text().splitlines(),
            ["api --hostname github.com repos/example/records", "token=the-login prompt=1"],
        )

    def test_public(self):
        self.gh(PUBLIC)
        answer = self.ask()
        self.assertEqual(answer.status, visibility.PUBLIC)
        self.assertFalse(answer.private)

    def test_the_push_address_is_the_one_asked_about(self):
        fakes.git(self.repo, "remote", "set-url", "--push", "origin", "git@github.com:other/place.git", env=self.env)
        self.gh(PRIVATE)
        self.ask()
        self.assertIn("api --hostname github.com repos/other/place", self.calls.read_text())

    def test_an_error_from_gh_is_the_reason(self):
        self.gh(stderr="error connecting to api.github.com\ncheck your internet connection", code=1)
        answer = self.ask()
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertEqual(
            answer.detail,
            "gh api exited with 1: error connecting to api.github.com check your internet connection",
        )

    def test_no_login(self):
        self.gh(stderr="To get started with GitHub CLI, please run:  gh auth login", code=4)
        answer = self.ask()
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertIn("gh api exited with 4: To get started with GitHub CLI", answer.detail)

    def test_an_answer_that_is_not_clear(self):
        self.gh(json.dumps({"private": True, "visibility": "internal"}))
        answer = self.ask()
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertEqual(
            answer.detail, "GitHub's answer about `example/records` does not say plainly that it is private or public"
        )

    def test_a_github_that_does_not_answer_in_time(self):
        self.gh(PRIVATE, wait=30)
        with mock.patch.object(visibility, "TIMEOUT", 1):
            answer = self.ask()
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertEqual(answer.detail, "GitHub did not answer within 1 s")

    def test_no_gh(self):
        self.env[visibility.GH_ENV] = str(self.root / "missing-gh")
        answer = self.ask()
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertIn("gh is not an executable at", answer.detail)

    def test_a_remote_that_is_not_on_github_is_never_asked_about(self):
        self.gh(PRIVATE)
        fakes.git(self.repo, "remote", "set-url", "origin", str(self.root / "remote.git"), env=self.env)
        answer = self.ask()
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertEqual(answer.detail, "`origin` does not push to a repository on github.com")
        self.assertFalse(self.calls.exists())

    def test_a_missing_remote(self):
        self.gh(PRIVATE)
        answer = self.ask("elsewhere")
        self.assertEqual(answer.status, visibility.UNCONFIRMED)
        self.assertIn("git could not read where `elsewhere` pushes", answer.detail)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
