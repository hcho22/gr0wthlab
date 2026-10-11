"""Reading a Product's code at one commit for claim checks, without writing to its checkout."""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import codebase
from tests import fakes


def digest_tree(root: Path) -> dict[str, str]:
    found = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = Path(folder, name)
            found[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


class CodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.env = fakes.git_env(self.root)
        self.checkout = fakes.make_code(self.root / "RepToday", self.env)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_branch_resolves_to_one_commit_and_claims_are_checked_there(self):
        code = codebase.open_code("RepToday", self.checkout, "main", self.env)
        self.assertIsNone(code.problem)
        self.assertEqual(code.commit, fakes.git(self.checkout, "rev-parse", "main", env=self.env))
        self.assertIsNone(
            code.verify("Engine/ConsistencyScore.swift:6-7", "value = max(floorValue, value - missPenalty)")
        )
        self.assertIsNone(code.verify("App/ReadyScreen.swift:9", "SessionList(session:   session)"))

    def test_the_working_tree_never_changes_what_a_claim_is_checked_against(self):
        code = codebase.open_code("RepToday", self.checkout, "main", self.env)
        (self.checkout / "Engine/ConsistencyScore.swift").write_text("// rewritten, not committed\n")
        self.assertIsNone(code.verify("Engine/ConsistencyScore.swift:7", "max(floorValue"))

    def test_every_wrong_location_says_why(self):
        code = codebase.open_code("RepToday", self.checkout, "main", self.env)
        cases = {
            ("Engine/ConsistencyScore.swift", "max(floorValue"): "is not path:line",
            ("Engine/ConsistencyScore.swift:9-3", "max(floorValue"): "must run forward",
            ("Engine/ConsistencyScore.swift:1-60", "max(floorValue"): "span at most 40 lines",
            ("Engine/ConsistencyScore.swift:7", "max"): "at least 4 characters",
            ("Engine/Missing.swift:1", "struct"): "there is no file Engine/Missing.swift at",
            ("../outside.swift:1", "struct"): "relative to the repository root",
            ("Engine/\x00.swift:1", "struct"): "git could not read it",
            ("Engine/ConsistencyScore.swift:90", "struct"): "has 9 lines at",
            ("Engine/ConsistencyScore.swift:2-3", "max(floorValue"): "do not contain 'max(floorValue'",
        }
        for (location, excerpt), why in cases.items():
            with self.subTest(location=location):
                self.assertIn(why, code.verify(location, excerpt))

    def test_a_file_that_is_not_text_gives_a_reason_and_never_an_error(self):
        (self.checkout / "App/Icon.png").write_bytes(b"\x89PNG\r\n\xff\xfe\x00s\x00t\x00r\x00u\x00c\x00t\n")
        (self.checkout / "App/Notes.swift").write_bytes("// caf\u00e9 \u2019 struct Notes {}\n".encode("utf-8"))
        fakes.git(self.checkout, "add", "--all", env=self.env)
        fakes.git(self.checkout, "commit", "--quiet", "-m", "assets", env=self.env)
        code = codebase.open_code("RepToday", self.checkout, "main", self.env)
        self.assertIn("do not contain 'struct Icon'", code.verify("App/Icon.png:1-2", "struct Icon"))
        self.assertIsNone(code.verify("App/Notes.swift:1", "caf\u00e9 \u2019 struct Notes {}"))

    def test_a_checkout_that_cannot_be_read_blocks_every_claim(self):
        missing = codebase.open_code("RepToday", self.root / "absent", "main", self.env)
        self.assertIn("does not exist", missing.problem)
        no_branch = codebase.open_code("RepToday", self.checkout, "release", self.env)
        self.assertIn("has no branch release", no_branch.problem)
        self.assertEqual(no_branch.verify("App/ReadyScreen.swift:9", "SessionList"), no_branch.problem)

    def test_reading_writes_nothing_in_the_checkout(self):
        before = digest_tree(self.checkout / ".git")
        status = fakes.git(self.checkout, "status", "--porcelain", env=self.env)
        before = digest_tree(self.checkout / ".git")
        code = codebase.open_code("RepToday", self.checkout, "main", self.env)
        code.verify("Engine/ConsistencyScore.swift:6-7", "max(floorValue")
        code.verify("Engine/Missing.swift:1", "struct")
        self.assertEqual(digest_tree(self.checkout / ".git"), before)
        self.assertEqual(fakes.git(self.checkout, "status", "--porcelain", env=self.env), status)


if __name__ == "__main__":
    unittest.main()
