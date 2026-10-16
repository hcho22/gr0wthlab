"""The Weekly Read example set (US-ME12, F9): every deterministic assertion in its evals.json holds, on synthetic
fixtures, with the launcher's own checks of a memo."""

import json
import unittest
from datetime import datetime, timezone

from gr0wthlab import exchange, founder, results, weekly_read
from tests import fakes
from tests.test_results import WINDOW, synthetic_kit
from tests.test_weekly_read import Lab

SET = fakes.REPO / "src" / "examples" / "weekly-read"
RULES = (fakes.EXAMPLES / "files/mandu/projects/RepToday/gtm/05-social-pmf/read-the-results.md").read_text(
    encoding="utf-8"
)
NOW = datetime(2026, 11, 1, 23, 0, tzinfo=timezone.utc)


class WeeklyReadExampleSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((SET / "evals.json").read_text(encoding="utf-8"))

    def outcome(self, example):
        memo, numbers = (SET / name for name in example["files"])
        records = json.loads(numbers.read_text(encoding="utf-8"))
        read = records[0]["read"]
        lab = Lab([], read=read, rules=RULES)
        self.addCleanup(lab.close)
        for record in records:
            stem = exchange.result_stem(record["window"], record["read"], record["platform"], record["day"])
            fakes.write_record(founder.folders(lab.ledger_root)[founder.RESULTS], f"{stem}.json", record)
        lab.read = results.prepare(WINDOW, read, synthetic_kit(), "", RULES)
        text = memo.read_text(encoding="utf-8")
        found = lab.plan()
        lines, problems = weekly_read.check(text, found)
        queued = []
        if not problems:
            lab.write(text)
            outcome = weekly_read.take(found, lab.areas, lab.store, lab.ledger, "RepToday", "run", NOW, [], [])
            queued = outcome.published
        return {"problems": problems, "lines": lines, "queued": queued}

    def test_the_set_has_the_evals_json_shape(self):
        self.assertEqual(self.data["skill_name"], "weekly-read")
        ids = [example["id"] for example in self.data["evals"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertGreaterEqual(len(ids), 10)
        for example in self.data["evals"]:
            self.assertEqual(sorted(example), ["assertions", "expected_output", "files", "id", "prompt"])
            self.assertTrue(all((SET / name).is_file() for name in example["files"]), example["id"])
            kinds = {assertion["kind"] for assertion in example["assertions"]}
            self.assertLessEqual(kinds, {"deterministic", "judged"})
            self.assertIn("deterministic", kinds)

    def test_every_deterministic_assertion_holds(self):
        for example in self.data["evals"]:
            outcome = self.outcome(example)
            for assertion in example["assertions"]:
                if assertion["kind"] != "deterministic":
                    continue
                with self.subTest(example=example["id"], check=assertion["check"]):
                    if assertion["check"] == "passes":
                        self.assertEqual(outcome["problems"], [])
                    elif assertion["check"] == "items":
                        self.assertEqual(len(outcome["queued"]), assertion["count"])
                    else:
                        self.assertEqual(assertion["check"], "refused")
                        self.assertTrue(
                            any(problem.startswith(assertion["problem"]) for problem in outcome["problems"]),
                            outcome["problems"],
                        )

    def test_no_number_in_the_set_is_a_zero_standing_for_one_not_given(self):
        for path in (SET / "files" / "results").glob("*.json"):
            for record in json.loads(path.read_text(encoding="utf-8")):
                self.assertNotIn(0, record["numbers"].values(), path.name)


if __name__ == "__main__":
    unittest.main()
