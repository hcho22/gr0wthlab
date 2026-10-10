"""The post-Draft example set (F5): every deterministic assertion in src/examples/post-drafts/evals.json holds."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import drafts, lint, posts
from gr0wthlab.settings import Window
from tests import fakes

EVALS = fakes.EXAMPLES / "evals.json"
LINT_RULES = set(lint.KNOWN_RULES) | {"need-marker", "hashtags"}


class ExampleSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(cls.tmp.name))
        env = fakes.git_env(root)
        cls.context = fakes.kit_context(fakes.make_code(root / "code", env), env)
        cls.data = json.loads(EVALS.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, example):
        paths = [fakes.EXAMPLES / name for name in example["files"]]
        draft = drafts.parse(paths[0].read_text(encoding="utf-8"), example["files"][0])
        other = drafts.parse(paths[1].read_text(encoding="utf-8"), example["files"][1]) if len(paths) > 1 else None
        return draft, drafts.evaluate(draft, self.context, other)

    def test_the_set_has_the_evals_json_shape_and_covers_every_guardrail_case(self):
        self.assertEqual(self.data["skill_name"], "post-drafts")
        ids = [example["id"] for example in self.data["evals"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertGreaterEqual(len(ids), 10)
        for example in self.data["evals"]:
            self.assertEqual(sorted(example), ["assertions", "expected_output", "files", "id", "prompt"])
            self.assertTrue(all((fakes.EXAMPLES / name).is_file() for name in example["files"]), example["id"])
            kinds = {assertion["kind"] for assertion in example["assertions"]}
            self.assertLessEqual(kinds, {"deterministic", "judged"})
            self.assertIn("deterministic", kinds)
        blocked = {
            assertion["rule"]
            for example in self.data["evals"]
            for assertion in example["assertions"]
            if assertion.get("check") == "blocked_by"
        }
        for case in ("banned_words_in_hook", "invented_proof_terms", "competitor-name", "frozen-hook", "max_hashtags"):
            self.assertTrue(any(case in rule for rule in blocked), case)
        self.assertTrue(any("pre-publication-checklist.md" in rule for rule in blocked))

    def test_every_deterministic_assertion_holds(self):
        for example in self.data["evals"]:
            draft, verdict = self.verdict(example)
            for assertion in example["assertions"]:
                if assertion["kind"] != "deterministic":
                    continue
                with self.subTest(example=example["id"], check=assertion["check"], rule=assertion.get("rule")):
                    self.assertTrue(
                        self.holds(assertion, draft, verdict), [finding.line() for finding in verdict.blocks]
                    )

    def holds(self, assertion, draft, verdict):
        check = assertion["check"]
        if check == "passes":
            return verdict.passed
        if check == "blocked_by":
            return any(finding.rule.startswith(assertion["rule"]) for finding in verdict.blocks)
        if check == "warns":
            return any(finding.rule == assertion["rule"] for finding in verdict.warnings)
        if check == "hook_frozen":
            return not any(finding.rule == "frozen-hook" for finding in verdict.blocks)
        if check == "lint_passes":
            return not any(
                finding.rule in LINT_RULES or finding.rule.startswith("config/platforms.json")
                for finding in verdict.blocks
            )
        if check == "cites_angle":
            return self.cites(assertion["angle"], draft, verdict)
        raise AssertionError(f"unknown check {check}")

    def cites(self, angle, draft, verdict):
        """The post item the Draft becomes cites its Angle, sourced pain, signal, and kill criterion by reference."""
        day = self.context.kit.days[draft.day]
        plan = posts.Plan(
            "RepToday",
            Window(1, None, None),
            "",
            [],
            [],
            self.context,
            {},
            Path("drafts/posts/window-1"),
            waitlist_live=False,
        )
        item = posts.render(plan, posts.DayPlan(day, verdict.hook, None), draft, verdict)
        evidence = item.evidence
        angles = self.context.paths["angles"]
        line = self.context.kit.angles[angle].line
        return all(
            text in evidence
            for text in (
                f"Angle {angle},",
                f"`{angles}` line {line}",
                "Sourced pain:",
                "https://example.com/threads/",
                "Pre-registered signal:",
                "Kill criterion:",
            )
        )


if __name__ == "__main__":
    unittest.main()
