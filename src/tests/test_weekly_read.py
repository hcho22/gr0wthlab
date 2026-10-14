"""The Weekly Read memo (US-ME12): the launcher's checks of the memo the agent writes, the memo the Founder reads,
and one Weekly Read decision item for each decision line. Every number here is synthetic."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gr0wthlab import exchange, founder, results, weekly_read
from gr0wthlab.areas import Store
from gr0wthlab.queue import OPEN, SUPERSEDED, Ledger
from tests import fakes
from tests.test_results import WINDOW, record, synthetic_kit

RULES = "- Any post under 200 impressions is unread, not failed.\n"
NOW = datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)
PATHS = {
    "calendar": "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md",
    "angles": "projects/RepToday/gtm/05-social-pmf/angles.md",
    "pairs": "projects/RepToday/gtm/05-social-pmf/ab-pairs.md",
    "read_the_results": "projects/RepToday/gtm/05-social-pmf/read-the-results.md",
}
# The US-ME12 Validation Test's result set for days 1 to 5, from the example set: day 1 is under the floor, day 2
# ranks first on views and missed its threshold, and day 3 cleared its signal; and the memo that passes on it.
EXAMPLES = fakes.REPO / "src" / "examples" / "weekly-read" / "files"
DAY_7 = json.loads((EXAMPLES / "results" / "day-07.json").read_text(encoding="utf-8"))
GOOD_DAY_7 = (EXAMPLES / "memos" / "day-07-good.md").read_text(encoding="utf-8")


class Lab:
    """A ledger with the Founder's records for one read, and the plan the run makes of them."""

    def __init__(self, records, read=7, rules=RULES):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(self.temporary.name))
        self.ledger_root = root / "ledger"
        fakes.make_founder(self.ledger_root)
        self.store = Store(self.ledger_root)
        self.areas = fakes.workspace_areas(root / "repo")
        self.ledger = Ledger()
        self.read = results.prepare(WINDOW, read, synthetic_kit(), "", rules)
        for data in records:
            stem = exchange.result_stem(data["window"], data["read"], data["platform"], data["day"])
            fakes.write_record(founder.folders(self.ledger_root)[founder.RESULTS], f"{stem}.json", data)

    def plan(self):
        taken = results.take(self.store, self.read, "run-1", NOW)
        return weekly_read.plan(self.read, taken, synthetic_kit(), PATHS, self.store, self.ledger)

    def write(self, text):
        path = self.areas.path("weekly_reads", f"window-1-read-{self.read.read:02d}.md")
        path.write_text(text, encoding="utf-8")

    def take(self, text, run="run-1"):
        self.write(text)
        found = self.plan()
        return found, weekly_read.take(
            found, self.areas, self.store, self.ledger, "RepToday", run, NOW, ["- not read"], ["- none"]
        )

    def close(self):
        self.temporary.cleanup()


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.lab = Lab(DAY_7)
        self.addCleanup(self.lab.close)

    def problems(self, text):
        return weekly_read.check(text, self.lab.plan())[1]

    def test_the_validation_test_s_memo_passes(self):
        """The under-floor post is unread, nothing is killed, the at-risk flag stands, and the flex slot goes to the
        Angle that cleared its threshold."""
        self.assertEqual(self.problems(GOOD_DAY_7), [])

    def test_a_kill_at_day_7_is_refused(self):
        text = GOOD_DAY_7.replace("- P04 (day 4): at risk.", "- P04 (day 4): met its kill criterion.").replace(
            "at the day-14 read. Decision: keep", "at the day-14 read. Decision: kill"
        )
        problems = self.problems(text)
        self.assertIn("P04: nothing can be killed at day 7; it may only be flagged at risk", problems)

    def test_an_under_floor_post_is_never_judged(self):
        text = GOOD_DAY_7.replace("- P01 (day 1): insufficient data.", "- P01 (day 1): missed its signal.")
        self.assertIn(
            "P01: none of its posts reached the floor of 200 views on the platform that judges it, so its result is"
            " `insufficient data`",
            self.problems(text),
        )

    def test_the_flex_slot_is_never_awarded_on_rank_alone(self):
        text = GOOD_DAY_7.replace("earned by P03. It cleared", "earned by P02. It cleared")
        self.assertNotEqual(text, GOOD_DAY_7)
        self.assertIn(
            "the flex slot goes to P02 only if its line says it cleared its signal, not merely that it ranked first",
            self.problems(text),
        )

    def test_every_angle_the_read_covers_has_one_line_naming_its_days(self):
        text = GOOD_DAY_7.replace(
            "- P03 (day 3): cleared its signal. Its viewed rate of 81% (n=1) ranks first of the 2 readable YouTube"
            " posts (n=2). Decision: keep\n",
            "",
        )
        self.assertNotEqual(text, GOOD_DAY_7)
        problems = self.problems(text)
        self.assertIn("P03 needs exactly one line under Angles; it has 0", problems)
        problems = self.problems(GOOD_DAY_7.replace("- P01 (day 1):", "- P01 (days 1 and 8):"))
        self.assertIn("Angles line 1 (P01) must name day 1, its posts in this read", problems)

    def test_every_number_has_its_n_beside_it(self):
        text = GOOD_DAY_7.replace("81% (n=1)", "81%")
        self.assertIn("P03: 1 number with no `(n=<posts>)` beside it", self.problems(text))

    def test_an_unread_or_at_risk_angle_says_what_would_settle_it(self):
        text = GOOD_DAY_7.replace(" What would settle it: day 11's comments at the day-14 read.", "")
        self.assertIn(
            "P04: an unread, at-risk, or reposted line ends with `What would settle it:` before its decision",
            self.problems(text),
        )

    def test_a_quoted_comment_must_be_one_the_founder_gave(self):
        text = GOOD_DAY_7.replace('"I lost a 200 day streak"', '"I lost a 300 day streak"')
        self.assertIn(
            "P05: a comment quoted under it from day 5 is not, word for word, in what the Founder gave for that post",
            self.problems(text),
        )

    def test_insufficient_data_is_its_own_result_and_every_line_ends_in_a_decision(self):
        text = GOOD_DAY_7.replace("Decision: test\n  >", "Decision: maybe\n  >")
        self.assertTrue(any(problem.startswith("Angles line 5 does not read") for problem in self.problems(text)))

    def test_the_sections_are_fixed(self):
        problems = self.problems(GOOD_DAY_7.replace("## Flex slot", "## Pairs"))
        self.assertEqual(problems, ["the sections must be `## Angles`, `## Flex slot`, `## Product`, in that order"])


class Day14Test(unittest.TestCase):
    def memo(self, angle_lines, pair_lines):
        return (
            "# Weekly Read, window 1, day 14\n\n## Angles\n\n"
            + "\n".join(angle_lines)
            + "\n\n## Pairs\n\n"
            + "\n".join(pair_lines)
            + "\n\n## Product\n\n- None this read.\n"
        )

    def lab(self, views):
        records = [
            record(day, "youtube" if day in (3, 4, 10, 11) else "tiktok", read=14, read_on="2026-11-01", views=v)
            for day, v in views.items()
        ]
        for data in records:
            data["recorded_at"] = "2026-11-01T18:00:00-07:00"
        lab = Lab(records, read=14)
        self.addCleanup(lab.close)
        return lab

    def lines(self, results_by_angle):
        days = {
            "P01": "days 1 and 8",
            "P02": "days 2 and 9",
            "P03": "days 3 and 10",
            "P04": "days 4 and 11",
            "P05": "day 5",
            "P06": "days 6 and 12",
            "P07": "days 7 and 13",
        }
        out = []
        for angle, (result, decision) in results_by_angle.items():
            settle = " What would settle it: more readable posts." if result in ("insufficient data", "at risk") else ""
            out.append(f"- {angle} ({days[angle]}): {result}. The numbers say so.{settle} Decision: {decision}")
        return out

    def test_a_kill_needs_the_angle_at_risk_at_the_day_7_read(self):
        lab = self.lab({day: 500 for day in range(1, 14)})
        verdicts = {
            angle: ("cleared its signal", "keep") for angle in ("P01", "P02", "P03", "P04", "P05", "P06", "P07")
        }
        verdicts["P06"] = ("met its kill criterion", "kill")
        pairs = [
            "- AB-1 (days 1 and 8): resolved. Leg A ranked well above leg B. Decision: keep",
            "- AB-2 (days 3 and 10): resolved. Leg B ranked well above leg A. Decision: keep",
        ]
        found = lab.plan()
        problems = weekly_read.check(self.memo(self.lines(verdicts), pairs), found)[1]
        self.assertIn(
            "P06: a kill needs two consecutive Weekly Reads at or under the criterion, and at the day-7 read it had no"
            " line, not `at risk`",
            problems,
        )
        found.previous = {"P06": "at risk"}
        problems = weekly_read.check(self.memo(self.lines(verdicts), pairs), found)[1]
        self.assertEqual(problems, [])

    def test_a_pair_resolves_only_when_both_legs_were_readable(self):
        views = {day: 500 for day in range(1, 14)}
        views[8] = 120
        lab = self.lab(views)
        verdicts = {
            angle: ("cleared its signal", "keep") for angle in ("P01", "P02", "P03", "P04", "P05", "P06", "P07")
        }
        pairs = [
            "- AB-1 (days 1 and 8): resolved. Leg A ranked well above leg B. Decision: keep",
            "- AB-2 (days 3 and 10): repost. The gap is small. What would settle it: a repost in window 2."
            " Decision: test",
        ]
        problems = weekly_read.check(self.memo(self.lines(verdicts), pairs), lab.plan())[1]
        self.assertIn(
            "AB-1: a pair resolves only when both legs were readable; repost it before any Hook is declared the winner",
            problems,
        )
        missing = weekly_read.check(self.memo(self.lines(verdicts), pairs[1:]), lab.plan())[1]
        self.assertIn("AB-1 has both legs in this read and needs a line under Pairs", missing)


class TakeTest(unittest.TestCase):
    def setUp(self):
        self.lab = Lab(DAY_7)
        self.addCleanup(self.lab.close)

    def test_each_decision_line_is_its_own_item_and_the_memo_is_composed(self):
        found, outcome = self.lab.take(GOOD_DAY_7)
        self.assertEqual(outcome.problems, [])
        self.assertEqual(len(outcome.published), 6, "five Angles and the flex slot; the Product section says none")
        asks = [self.lab.ledger.entries[item]["ask"] for item in outcome.published]
        self.assertIn("Weekly Read day 7: P03, cleared its signal: keep", asks)
        self.assertIn("Weekly Read day 7: P01, insufficient data: test", asks)
        self.assertIn("Weekly Read day 7: flex slot earned: test", asks)
        touches = {
            self.lab.ledger.entries[item]["ask"]: (self.lab.ledger_root / self.lab.ledger.entries[item]["file"])
            .read_text(encoding="utf-8")
            .split("## Touches", 1)[1]
            for item in outcome.published
        }
        # Keeping or testing an Angle changes nothing in the package; only a kill or a change would.
        self.assertIn(
            "- Nothing: approving keeps P03's row in `projects/RepToday/gtm/05-social-pmf/angles.md` as it is",
            touches["Weekly Read day 7: P03, cleared its signal: keep"],
        )
        for item in outcome.published:
            entry = self.lab.ledger.entries[item]
            self.assertEqual((entry["kind"], entry["window"], entry["read"]), ("weekly-read-decision", 1, 7))
            text = (self.lab.ledger_root / entry["file"]).read_text(encoding="utf-8")
            self.assertEqual(exchange.check_item(text, ["RepToday"], published=True).problems, [])
        memo = (self.lab.ledger_root / outcome.composed).read_text(encoding="utf-8")
        self.assertIn(results.FLOOR_COUNTS, memo)
        self.assertIn(weekly_read.CANNOT_TELL, memo)
        # Each post's row has every number asked of its platform, its own Angle's and the ones it is ranked on.
        self.assertIn(
            "| 5 | P05 | TikTok (readable) | Video views: 320 (n=1); Watched full video, in percent: 35% (n=1);"
            " Comments: 4 (n=1) | 1 comment | 2026-10-25 |",
            memo,
        )
        self.assertIn("in percent: 55% (n=1); Comments: 3 (n=1) | 3 comments | 2026-10-25 |", memo)
        self.assertIn(exchange.THIRD_PARTY, memo)
        # Day 3's comment text was not given, and day 1's views are under the floor: each row says which.
        self.assertIn("| 3 | P03 (AB-2 leg A) | YouTube Shorts (readable) | Views: 900 (n=1);", memo)
        self.assertIn("in percent: 81% (n=1); Comments: 2 (n=1) | none given | 2026-10-25 |", memo)
        self.assertIn("| 1 | P01 (AB-1 leg A) | TikTok (unread: under the floor) |", memo)

    def test_only_a_kill_or_a_change_is_said_to_change_the_angle_bank(self):
        found = self.lab.plan()
        for decision, said in (
            (
                "kill",
                "- P04's row in `projects/RepToday/gtm/05-social-pmf/angles.md`, which Mandu changes if you approve",
            ),
            ("change", "which Mandu changes if you approve"),
            ("keep", "- Nothing: approving keeps P04's row in"),
            ("test", "- Nothing: approving keeps P04's row in"),
        ):
            with self.subTest(decision=decision):
                line = weekly_read.Line(weekly_read.ANGLE, "P04", weekly_read.AT_RISK, decision, "- P04 (day 4): ...")
                self.assertIn(said, weekly_read.item_for(found, line, "weekly-reads/memo.md", "RepToday").touches)

    def test_a_memo_that_fails_a_check_queues_nothing_and_stays_as_written(self):
        text = GOOD_DAY_7.replace("81% (n=1)", "81%")
        _, outcome = self.lab.take(text)
        self.assertEqual(outcome.published, [])
        self.assertTrue(outcome.problems)
        path = self.lab.areas.path("weekly_reads", "window-1-read-07.md")
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_a_memo_written_again_replaces_the_read_s_open_items_line_for_line(self):
        _, first = self.lab.take(GOOD_DAY_7)
        found = self.lab.plan()
        self.assertFalse(found.due, "nothing changed since the memo was written")
        fakes.write_record(
            founder.folders(self.lab.ledger_root)[founder.RESULTS],
            "window-1-read-07-tiktok-day-01.json",
            record(1, views=180, watched_full_percent=40.0),
        )
        self.assertTrue(self.lab.plan().due, "a corrected number writes the memo again")
        _, second = self.lab.take(GOOD_DAY_7, run="run-2")
        self.assertEqual(sorted(second.replaced), sorted(first.published))
        for item in first.published:
            self.assertEqual(self.lab.ledger.entries[item]["status"], SUPERSEDED)
        for item in second.published:
            self.assertEqual(self.lab.ledger.entries[item]["status"], OPEN)

    def test_a_decided_item_keeps_its_memo(self):
        _, first = self.lab.take(GOOD_DAY_7)
        self.lab.ledger.close(self.lab.ledger.entries[first.published[0]], "approved", "run-2", NOW)
        fakes.write_record(
            founder.folders(self.lab.ledger_root)[founder.RESULTS],
            "window-1-read-07-tiktok-day-01.json",
            record(1, views=180, watched_full_percent=40.0),
        )
        found = self.lab.plan()
        self.assertEqual(
            found.why, "the Founder has decided items of the window 1 day-7 Weekly Read, so its memo stands as it is"
        )


class NumberTest(unittest.TestCase):
    def test_identifiers_and_quotes_need_no_n(self):
        self.assertEqual(weekly_read.bare_numbers('P01 (days 1 and 8) on day-14, window 1: "200 day streak"'), [])
        self.assertEqual(weekly_read.bare_numbers("412 views (n=1) and 31.5% (n=1) of 3 readable posts (n=3)"), [])
        self.assertEqual(weekly_read.bare_numbers("412 views and 31.5%"), ["412", "31.5"])


if __name__ == "__main__":
    unittest.main()
