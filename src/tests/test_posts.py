"""The post-Draft workflow: which days a run prepares, and what the launcher does with each Draft afterwards."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timezone
from pathlib import Path

from gr0wthlab import boundary, exchange, posts
from gr0wthlab.areas import Areas, Store
from gr0wthlab.boundary import ConfigError
from gr0wthlab.queue import APPROVED, OPEN, SUPERSEDED, Ledger
from gr0wthlab.settings import Window
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY

NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
PRODUCTS = ["RepToday", "Immerse"]
SUNDAY = date(2026, 10, 11)


class TargetDaysTest(unittest.TestCase):
    CALENDAR = list(range(1, 15))

    def test_until_day_1_is_set_the_first_batch_is_days_1_to_7(self):
        days, reason = posts.target_days(Window(1, None, None), self.CALENDAR, SUNDAY, "sunday")
        self.assertEqual(days, [1, 2, 3, 4, 5, 6, 7])
        self.assertIn("day 1 is not set in config/run.json", reason)

    def test_a_sunday_run_prepares_the_week_after_that_evening_s_sitting(self):
        window = Window(1, date(2026, 10, 12), time(19, 0))
        self.assertEqual(posts.target_days(window, self.CALENDAR, SUNDAY, "sunday")[0], [1, 2, 3, 4, 5, 6, 7])
        later = posts.target_days(window, self.CALENDAR, date(2026, 10, 18), "sunday")
        self.assertEqual(later[0], [8, 9, 10, 11, 12, 13, 14])
        self.assertIn("the week after the sitting on Sunday 2026-10-18", later[1])
        self.assertEqual(posts.target_days(window, self.CALENDAR, date(2026, 10, 25), "sunday")[0], [])

    def test_a_late_or_mid_week_run_also_prepares_the_days_left_before_that_week(self):
        window = Window(1, date(2026, 10, 12), time(19, 0))
        days, reason = posts.target_days(window, self.CALENDAR, date(2026, 10, 14), "sunday")
        self.assertEqual(days, list(range(4, 15)))
        self.assertIn("the days from tomorrow, 2026-10-15, up to that week", reason)

    def test_the_slot_is_the_day_s_date_at_the_window_s_time(self):
        window = Window(1, date(2026, 10, 12), time(19, 0))
        slot = posts.slot_for(window, 3)
        self.assertTrue(slot.startswith("2026-10-14T19:00"))
        self.assertIsNotNone(exchange.parse_datetime(slot))
        self.assertIsNone(posts.slot_for(Window(1, date(2026, 10, 12), None), 3))
        self.assertIsNone(posts.slot_for(Window(1, None, time(19, 0)), 3))


class KitConfigTest(unittest.TestCase):
    def registry(self):
        return json.loads((fakes.REPO / "config/products.json").read_text(encoding="utf-8"))

    def test_every_role_must_be_named_and_snapshotted(self):
        registry = self.registry()
        roles = registry["products"][0]["go_to_market_package"]["post_drafts"]
        del roles["checklist"]
        with self.assertRaisesRegex(ConfigError, "must name: checklist"):
            posts.kit_config(registry)
        registry = self.registry()
        registry["products"][0]["go_to_market_package"]["post_drafts"]["angles"] = "projects/RepToday/elsewhere.md"
        with self.assertRaisesRegex(ConfigError, "angles must be one of its package sources"):
            posts.kit_config(registry)

    def test_the_competitor_files_must_be_the_ones_the_snapshot_covers(self):
        registry = self.registry()
        source = next(
            entry
            for entry in registry["products"][0]["go_to_market_package"]["sources"]
            if entry.get("files_starting_with")
        )
        source["files_starting_with"] = "teardown"
        with self.assertRaisesRegex(ConfigError, "reads the files starting with competitor"):
            posts.kit_config(registry)

    def test_a_product_with_no_kit_has_no_post_drafts(self):
        registry = self.registry()
        del registry["products"][0]["go_to_market_package"]["post_drafts"]
        self.assertIsNone(posts.kit_config(registry))

    def test_a_kit_file_that_cannot_be_read_or_parsed_is_a_problem_for_its_role(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        mandu = fakes.make_mandu(Path(tmp.name) / "Mandu")
        (mandu / "projects/RepToday/gtm/05-social-pmf/angles.md").write_text("no table\n")
        (mandu / "projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json").write_text("{not json")
        (mandu / "projects/RepToday/gtm/05-social-pmf/ab-pairs.md").unlink()
        _, roles = posts.kit_config(self.registry())
        parsed, files, data, problem = posts.read_kit(mandu, roles)
        self.assertIn("no table with the columns", parsed.problems["angles"])
        self.assertIn("No such file", parsed.problems["pairs"])
        self.assertIsNone(files["pairs"][1])
        self.assertEqual(len(files["calendar"][1]), 64)
        self.assertIsNone(data)
        self.assertTrue(problem.startswith("not JSON"))


class TakeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(self.tmp.name))
        env = fakes.git_env(root)
        self.repo = root / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        resolved = boundary.resolve_boundary(self.repo, CONFIG, REGISTRY, {}, root, git=[self.repo / ".git"])
        self.areas = Areas(resolved)
        self.store = Store(resolved.ledger)
        self.ledger = Ledger()
        self.context = fakes.kit_context(fakes.make_code(root / "RepToday", env), env)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, *days, slot=None):
        kit = self.context.kit
        plans = []
        for number in days:
            entries = posts.day_entries(self.ledger, "RepToday", 1, number)
            plans.append(
                posts.DayPlan(
                    kit.days[number],
                    posts.kit.frozen_hook(kit.days[number], kit)[0],
                    slot,
                    next((e for e in entries if e["status"] == OPEN), None),
                    next((e for e in entries if e["status"] == APPROVED), None),
                )
            )
        folder = self.repo / "workspace/drafts/posts/window-1"
        return posts.Plan("RepToday", Window(1, None, None), "First batch.", plans, [], self.context, {}, folder, False)

    def write(self, day, text):
        path = self.repo / "workspace" / fakes.draft_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def take(self, *days, run="RUN1", seen=None):
        return posts.take(
            self.plan(*days), self.areas, self.store, self.ledger, run, NOW, {} if seen is None else seen, PRODUCTS
        )


class TakeTest(TakeTestCase):
    def test_a_draft_that_passes_becomes_one_post_item_citing_its_angle(self):
        self.write(3, fakes.draft(3))
        outcome = self.take(3)
        [result] = outcome.results
        self.assertEqual((result.status, result.item), (posts.QUEUED, "20261011-post-w1-day-03"))
        entry = self.ledger.entries[result.item]
        self.assertEqual((entry["kind"], entry["window"], entry["day"]), ("post", 1, 3))
        self.assertEqual(entry["draft"], "drafts/posts/window-1/day-03.md")
        text = (self.store.root / entry["file"]).read_text(encoding="utf-8")
        check = exchange.check_item(text, PRODUCTS, published=True)
        self.assertEqual(check.problems, [])
        self.assertEqual(check.item.ask, "Approve day 3 post: score dip demo")
        self.assertIn("Nothing can be published until the RepToday Waitlist is live.", text)
        self.assertIn("Slot: not set yet", text)
        self.assertIn("**Hook**, frozen in `projects/RepToday/gtm/05-social-pmf/ab-pairs.md` line 13", text)
        self.assertIn("`Engine/ConsistencyScore.swift:6-7` shows `value = max(floorValue, value - missPenalty)`", text)
        self.assertIn("- Angle P03, Score that dips: `projects/RepToday/gtm/05-social-pmf/angles.md` line 9", text)
        self.assertIn("- Kill criterion: Bottom quartile viewed rate on two reads:", text)
        self.assertIn("no open line blocks this post", text)
        self.assertIn("  Done: line 7.\n  Open, gating other assets or none named: lines 8, 16.\n", text)
        self.assertIn(
            "  Open, gating only assets that use the 'under 100 milliseconds' claim, which this post does not:"
            " line 12.",
            text,
        )

    def test_an_unchanged_draft_keeps_its_open_item_and_a_changed_one_supersedes_it(self):
        self.write(3, fakes.draft(3))
        [first] = self.take(3).results
        [kept] = self.take(3, run="RUN2").results
        self.assertEqual((kept.status, kept.item), (posts.KEPT, first.item))
        self.write(3, fakes.draft(3, caption="The history view after three gaps this month."))
        [second] = self.take(3, run="RUN3").results
        self.assertEqual(second.status, posts.QUEUED)
        old = self.ledger.entries[first.item]
        self.assertEqual((old["status"], old["superseded_by"]), (SUPERSEDED, second.item))
        new_text = (self.store.root / self.ledger.entries[second.item]["file"]).read_text(encoding="utf-8")
        self.assertIn(f"supersedes: {first.item}", new_text)

    def test_a_blocked_draft_is_never_queued_and_withdraws_an_open_item_for_its_day(self):
        self.write(3, fakes.draft(3))
        [first] = self.take(3).results
        self.write(3, fakes.draft(3, caption="No grind here, only a score that forgives."))
        outcome = self.take(3, run="RUN2")
        [result] = outcome.results
        self.assertEqual((result.status, result.withdrawn), (posts.BLOCKED, first.item))
        self.assertEqual(outcome.published, [])
        self.assertIn(
            "banned_words_in_hook: banned word 'grind' (TikTok caption, YouTube Shorts description)",
            posts.grouped(result.verdict.blocks),
        )
        posts.withdraw(self.ledger, outcome, "20261011-notice", "RUN2", NOW)
        entry = self.ledger.entries[first.item]
        self.assertEqual(
            (entry["status"], entry["superseded_by"], entry["withdrawn"]), (SUPERSEDED, "20261011-notice", True)
        )
        _, title, text = posts.notice_section(outcome, "2026-10-11")
        self.assertEqual(title, "1 post Draft not offered on 2026-10-11")
        self.assertIn("- Day 3 (`drafts/posts/window-1/day-03.md`): banned_words_in_hook: banned word 'grind'", text)
        self.assertIn(f"The open post `{first.item}` for day 3 is withdrawn", text)

    def test_a_source_that_cannot_be_read_now_keeps_an_open_item(self):
        self.write(3, fakes.draft(3))
        [first] = self.take(3).results
        self.context.kit.problems["calendar"] = "Permission denied"
        [result] = self.take(3, run="RUN2").results
        self.assertEqual((result.status, result.item, result.withdrawn), (posts.KEPT, first.item, None))
        self.assertIn("could not be used", result.detail)

    def test_an_approved_day_is_never_asked_again_and_a_missing_draft_is_named(self):
        self.write(3, fakes.draft(3))
        [first] = self.take(3).results
        self.ledger.close(self.ledger.entries[first.item], APPROVED, "RUN2", NOW)
        self.write(3, fakes.draft(3, caption="A rewrite after approval."))
        outcome = self.take(3, 6, run="RUN3")
        self.assertEqual([(r.day, r.status) for r in outcome.results], [(3, posts.APPROVED_BEFORE), (6, posts.MISSING)])
        self.assertEqual(outcome.published, [])
        _, title, text = posts.notice_section(outcome, "2026-10-11")
        self.assertIn("- Day 6 has no Draft, so it has no post this run.", text)

    def test_the_same_ask_as_a_decided_item_is_not_queued_again(self):
        self.write(3, fakes.draft(3))
        seen = {}
        [first] = self.take(3, seen=seen).results
        self.ledger.close(self.ledger.entries[first.item], "rejected", "RUN2", NOW, reason="Too flat.")
        [again] = self.take(3, run="RUN3", seen=seen).results
        self.assertEqual((again.status, again.item), (posts.REPEATED, first.item))

    def test_a_draft_that_is_a_link_is_never_read(self):
        target = self.repo.parent / "outside.md"
        target.write_text(fakes.draft(3))
        path = self.repo / "workspace" / fakes.draft_path(3)
        path.parent.mkdir(parents=True)
        path.symlink_to(target)
        [result] = self.take(3).results
        self.assertEqual(result.status, posts.BLOCKED)
        self.assertIn("could not be read", result.detail)

    def test_the_record_keeps_every_check_of_every_day(self):
        self.write(3, fakes.draft(3))
        self.write(1, fakes.draft(1, caption="Join 10,000 people who stopped quitting."))
        plan = self.plan(1, 3)
        outcome = posts.take(plan, self.areas, self.store, self.ledger, "RUN1", NOW, {}, PRODUCTS)
        relative = posts.record(plan, outcome, self.store, "RUN1", NOW)
        data = json.loads((self.store.root / relative).read_text(encoding="utf-8"))
        days = {day["day"]: day for day in data["days"]}
        self.assertEqual(days[1]["status"], posts.BLOCKED)
        self.assertEqual(days[1]["blocks"][0]["rule"], "invented_proof_terms")
        self.assertEqual(
            days[3]["checklist"][0],
            {"line": 7, "title": "Trademark search for the name", "status": "done", "note": "checked"},
        )
        self.assertEqual(data["code"]["commit"], self.context.code.commit)
        self.assertEqual(data["competitors"], ["IronFit", "Pulseday", "Stretchly"])


if __name__ == "__main__":
    unittest.main()
