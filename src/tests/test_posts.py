"""The post-Draft workflow: which days a run prepares, and what the launcher does with each Draft afterwards."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timezone
from pathlib import Path

from gr0wthlab import boundary, exchange, lint, posts
from gr0wthlab.areas import Areas, Store
from gr0wthlab.boundary import ConfigError
from gr0wthlab.queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger
from gr0wthlab.settings import Window
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY

NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
PRODUCTS = ["RepToday", "Immerse"]
SUNDAY = date(2026, 10, 11)
ANGLES = "projects/RepToday/gtm/05-social-pmf/angles.md"
CHECKLIST = "projects/RepToday/gtm/08-redteam/pre-publication-checklist.md"
LINK = "https://example.com/threads/103"
PAIN = f'Pain 2: "the reset made me quit" - {LINK}'


class TargetDaysTest(unittest.TestCase):
    CALENDAR = list(range(1, 15))

    def test_until_the_first_sitting_is_set_the_first_batch_is_days_1_to_7(self):
        days, reason = posts.target_days(Window(1, None, None), self.CALENDAR, SUNDAY, "sunday")
        self.assertEqual(days, [1, 2, 3, 4, 5, 6, 7])
        self.assertIn("first sitting is not set in config/run.json", reason)

    def test_day_1_is_the_day_after_the_first_sitting_and_its_run_prepares_the_week_after_it(self):
        window = Window(1, SUNDAY, time(19, 0))
        first = posts.target_days(window, self.CALENDAR, SUNDAY, "sunday")
        self.assertEqual(first[0], [1, 2, 3, 4, 5, 6, 7])
        self.assertIn("Window 1 begins on Monday 2026-10-12, the day after its first sitting", first[1])
        later = posts.target_days(window, self.CALENDAR, date(2026, 10, 18), "sunday")
        self.assertEqual(later[0], [8, 9, 10, 11, 12, 13, 14])
        self.assertIn("the week after the sitting on Sunday 2026-10-18", later[1])
        self.assertEqual(posts.target_days(window, self.CALENDAR, date(2026, 10, 25), "sunday")[0], [])
        self.assertEqual(posts.target_days(window, self.CALENDAR, date(2026, 10, 4), "sunday")[0], [])

    def test_a_late_or_mid_week_run_also_prepares_the_days_left_before_that_week(self):
        window = Window(1, SUNDAY, time(19, 0))
        days, reason = posts.target_days(window, self.CALENDAR, date(2026, 10, 14), "sunday")
        self.assertEqual(days, list(range(4, 15)))
        self.assertIn("the days from tomorrow, 2026-10-15, up to that week", reason)

    def test_the_slot_is_the_day_s_date_at_the_window_s_time(self):
        window = Window(1, SUNDAY, time(19, 0))
        slot = posts.slot_for(window, 3)
        self.assertTrue(slot.startswith("2026-10-14T19:00"))
        self.assertIsNotNone(exchange.parse_datetime(slot))
        self.assertIsNone(posts.slot_for(Window(1, SUNDAY, None), 3))
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
                    [e for e in entries if e["status"] == REJECTED],
                )
            )
        folder = self.repo / "workspace/drafts/posts/window-1"
        posted = posts.posted_days(self.ledger, "RepToday", 1, list(kit.days))
        window = Window(1, None, None)
        return posts.Plan("RepToday", window, "First batch.", plans, [], self.context, {}, folder, False, posted)

    def write(self, day, text):
        path = self.repo / "workspace" / fakes.draft_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def take(self, *days, run="RUN1", slot=None):
        return posts.take(self.plan(*days, slot=slot), self.areas, self.store, self.ledger, run, NOW, PRODUCTS)

    def withdraw(self, outcome, run):
        posts.withdraw(self.ledger, outcome, "20261011-notice", run, NOW)


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
        self.assertIn(
            "- The kit's checklist for every asset (`projects/RepToday/gtm/05-social-pmf/cadence-14-day.md`), each"
            " line yours to judge on this post:\n  Line 26: Founder is on camera for every first-person line.\n",
            text,
        )

    def test_a_claim_line_that_gates_only_other_assets_is_never_said_to_be_about_a_claim_the_post_does_not_use(self):
        checklist = (fakes.EXAMPLES / "files" / "mandu" / CHECKLIST).read_text(encoding="utf-8")
        self.context.kit.checklist = posts.kit.parse_checklist(
            checklist.replace("(blocking: site, video, social)", "(blocking: site)")
        )
        self.write(1, (fakes.EXAMPLES / "files/drafts/day-01-speed-claim.md").read_text(encoding="utf-8"))
        [result] = self.take(1).results
        self.assertEqual(result.status, posts.QUEUED, result.verdict.blocks)
        text = (self.store.root / self.ledger.entries[result.item]["file"]).read_text(encoding="utf-8")
        self.assertIn("Built on the phone in under 100 ms", text)
        self.assertIn("  Done: line 7.\n  Open, gating other assets or none named: lines 8, 12, 16.\n", text)
        self.assertNotIn("which this post does not", text)

    def pain_line(self, pain):
        """The Sourced pain line in the Evidence of day 3's post item, when the Angle bank words its pain so."""
        bank = (fakes.EXAMPLES / "files" / "mandu" / ANGLES).read_text(encoding="utf-8")
        self.context.kit.angles = posts.kit.parse_angles(bank.replace(PAIN, pain))
        self.write(3, fakes.draft(3))
        plan = self.plan(3)
        draft = posts.read_draft(self.areas, plan.draft_path(3))[0]
        verdict, item = posts.check_day(plan, plan.days[0], draft, self.areas, PRODUCTS)
        self.assertEqual(verdict.blocks, [])
        return next(line for line in item.evidence.splitlines() if line.startswith("- Sourced pain: "))

    def test_the_sourced_pain_cites_the_angle_bank_and_keeps_its_link_whole_however_long_it_is(self):
        cited = f": `{ANGLES}` line 9"
        self.assertEqual(self.pain_line(PAIN), f"- Sourced pain: {PAIN}{cited}")
        words = ("the reset made me quit " * 22).strip()
        after = f'Pain 2: "{words}" - {LINK}'
        astride = f'Pain 2: "{words[:367]}" - {LINK} and the thread goes on from there'
        self.assertGreater(after.index(LINK), 400)
        self.assertTrue(astride.index(LINK) < 400 < astride.index(LINK) + len(LINK))
        for name, pain in (("the link comes after the cut", after), ("the link straddles the cut", astride)):
            with self.subTest(name):
                quote, cut, rest = self.pain_line(pain)[len("- Sourced pain: ") :].partition(" ...")
                self.assertTrue(pain.startswith(quote + " ") and 370 < len(quote) <= 400, quote)
                self.assertEqual(rest, f" {LINK}{cited}")

    def test_an_excerpt_is_cut_between_words_and_never_through_a_link(self):
        link = "https://example.com/" + "a" * 60
        self.assertEqual(posts.excerpt("one two  three", 30), "one two three")
        self.assertEqual(posts.excerpt("one two three four", 9), "one two ...")
        self.assertEqual(posts.excerpt(f"See {link}, then {link}/b.", 30), f"See ... {link} {link}/b")
        self.assertEqual(posts.excerpt(link, 30), f"... {link}")

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

    def test_an_open_post_is_replaced_when_its_slot_is_set_or_taken_away(self):
        slot = "2026-10-14T19:00-07:00"
        self.write(3, fakes.draft(3))
        [unslotted] = self.take(3).results
        [slotted] = self.take(3, run="RUN2", slot=slot).results
        self.assertEqual((slotted.status, self.ledger.entries[slotted.item]["slot"]), (posts.QUEUED, slot))
        [kept] = self.take(3, run="RUN3", slot=slot).results
        self.assertEqual((kept.status, kept.item), (posts.KEPT, slotted.item))
        # The window's first sitting or slot was set back to none in config/run.json.
        [again] = self.take(3, run="RUN4").results
        self.assertEqual(again.status, posts.QUEUED)
        self.assertNotIn("slot", self.ledger.entries[again.item])
        old = self.ledger.entries[slotted.item]
        self.assertEqual((old["status"], old["superseded_by"]), (SUPERSEDED, again.item))
        self.assertEqual([entry["id"] for entry in self.ledger.ordered()], [again.item])
        self.assertIn("Slot: not set yet", (self.store.root / self.ledger.entries[again.item]["file"]).read_text())
        self.assertEqual(self.ledger.entries[unslotted.item]["superseded_by"], slotted.item)

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

    def test_a_rejected_draft_is_not_asked_again_until_it_changes(self):
        self.write(4, fakes.draft(4))
        [first] = self.take(4).results
        self.ledger.close(self.ledger.entries[first.item], REJECTED, "RUN2", NOW, reason="Too flat.")
        # Its slot, like the Product's commit, changes the item's text and never the Draft the Founder rejected.
        outcome = self.take(4, run="RUN3", slot="2026-10-15T19:00-07:00")
        [again] = outcome.results
        self.assertEqual((again.status, again.item), (posts.REPEATED, first.item))
        self.assertEqual(outcome.published, [])
        self.write(4, fakes.draft(4, caption="The session was built on the phone before the signal went."))
        [rewritten] = self.take(4, run="RUN4").results
        self.assertEqual((rewritten.status, rewritten.item), (posts.QUEUED, "20261011-post-w1-day-04-2"))

    def test_a_draft_that_passes_again_after_its_post_was_withdrawn_is_queued_again(self):
        self.write(3, fakes.draft(3))
        [first] = self.take(3).results
        self.write(3, fakes.draft(3, caption="No grind here, only a score that forgives."))
        self.withdraw(self.take(3, run="RUN2"), "RUN2")
        self.write(3, fakes.draft(3))
        [restored] = self.take(3, run="RUN3").results
        self.assertEqual((restored.status, restored.item), (posts.QUEUED, "20261011-post-w1-day-03-2"))
        self.assertEqual(self.ledger.entries[first.item]["status"], SUPERSEDED)
        self.assertEqual(self.ledger.entries[restored.item]["status"], OPEN)

    def test_a_leg_s_open_post_is_the_reference_and_only_the_newer_leg_is_blocked(self):
        self.write(1, fakes.draft(1))
        [first] = self.take(1).results
        self.write(8, fakes.draft(8, caption="A different second line."))
        outcome = self.take(1, 8, run="RUN2")
        reference, newer = outcome.results
        self.assertEqual((reference.status, reference.item, reference.withdrawn), (posts.KEPT, first.item, None))
        self.assertEqual((newer.status, outcome.withdrawn, outcome.published), (posts.BLOCKED, [], []))
        self.assertEqual(
            posts.grouped(newer.verdict.blocks),
            [
                "pair-legs: differs from day 1's leg beyond the Hook (`drafts/posts/window-1/day-01.md`)"
                " (TikTok caption, YouTube Shorts description)"
            ],
        )
        self.write(8, fakes.draft(8))
        [matched] = self.take(8, run="RUN3").results
        self.assertEqual(matched.status, posts.QUEUED)
        # Both legs are open now; a change to one is checked against the other, which stands.
        self.write(1, fakes.draft(1).replace("Real phone, real time.", "Real phone."))
        outcome = self.take(1, 8, run="RUN4")
        changed, standing = outcome.results
        self.assertEqual((changed.status, changed.withdrawn), (posts.BLOCKED, first.item))
        self.assertIn("beat 3 on-screen text", posts.grouped(changed.verdict.blocks)[0])
        self.assertEqual((standing.status, standing.item, standing.withdrawn), (posts.KEPT, matched.item, None))

    def test_a_newer_leg_cannot_pass_against_a_reference_draft_that_is_not_the_one_posted(self):
        self.write(1, fakes.draft(1))
        [first] = self.take(1).results
        self.ledger.close(self.ledger.entries[first.item], APPROVED, "RUN2", NOW)
        rewritten = "A second line the Founder never approved."
        self.write(1, fakes.draft(1, caption=rewritten))
        self.write(8, fakes.draft(8, caption=rewritten))
        [newer] = self.take(8, run="RUN3").results
        self.assertEqual(newer.status, posts.BLOCKED)
        self.assertEqual(
            posts.grouped(newer.verdict.blocks),
            [
                f"pair-legs: day 1's Draft is no longer the one `{first.item}` was queued from, so this leg cannot be"
                " compared with it"
            ],
        )

    def test_a_draft_must_be_for_the_day_its_file_names(self):
        self.write(3, fakes.draft(4))
        [result] = self.take(3).results
        self.assertEqual(result.status, posts.BLOCKED)
        self.assertIn("calendar: the Draft in the file for day 3 says day 4", posts.grouped(result.verdict.blocks))

    def test_an_unreadable_draft_withdraws_its_day_s_open_post(self):
        self.write(3, fakes.draft(3))
        [first] = self.take(3).results
        path = self.repo / "workspace" / fakes.draft_path(3)
        path.unlink()
        (self.repo.parent / "outside.md").write_text(fakes.draft(3))
        path.symlink_to(self.repo.parent / "outside.md")
        [result] = self.take(3, run="RUN2").results
        self.assertEqual((result.status, result.withdrawn), (posts.BLOCKED, first.item))

    def test_a_draft_that_is_a_link_is_never_read(self):
        target = self.repo.parent / "outside.md"
        target.write_text(fakes.draft(3))
        path = self.repo / "workspace" / fakes.draft_path(3)
        path.parent.mkdir(parents=True)
        path.symlink_to(target)
        [result] = self.take(3).results
        self.assertEqual(result.status, posts.BLOCKED)
        self.assertIn("could not be read", result.detail)

    def test_a_consistent_rewrite_of_both_open_legs_lands_in_one_run(self):
        self.write(1, fakes.draft(1))
        self.write(8, fakes.draft(8))
        first, second = self.take(1, 8).results
        self.assertEqual((first.status, second.status), (posts.QUEUED, posts.QUEUED))
        caption = "The same new second line."
        self.write(1, fakes.draft(1, caption=caption))
        self.write(8, fakes.draft(8, caption=caption))
        outcome = self.take(1, 8, run="RUN2")
        self.assertEqual([result.status for result in outcome.results], [posts.QUEUED, posts.QUEUED])
        self.assertEqual(outcome.withdrawn, [])
        for old, new in zip((first, second), outcome.results):
            self.assertEqual(self.ledger.entries[old.item]["superseded_by"], new.item)

    def test_two_legs_drafted_in_one_run_get_the_same_verdict_from_check_drafts_and_the_launcher(self):
        self.write(1, fakes.draft(1))
        self.write(8, fakes.draft(8, caption="A different second line."))
        plan = self.plan(1, 8)
        before = [
            posts.check_day(
                plan, due, posts.read_draft(self.areas, plan.draft_path(due.day.day))[0], self.areas, PRODUCTS
            )[0]
            for due in plan.days
        ]
        outcome = posts.take(plan, self.areas, self.store, self.ledger, "RUN1", NOW, PRODUCTS)
        self.assertEqual([verdict.passed for verdict in before], [True, False])
        self.assertEqual([result.status for result in outcome.results], [posts.QUEUED, posts.BLOCKED])
        self.assertEqual(posts.grouped(before[1].blocks), posts.grouped(outcome.results[1].verdict.blocks))
        self.assertIn("pair-legs: differs from day 1's leg beyond the Hook", posts.grouped(before[1].blocks)[0])

    def test_a_rule_the_reference_leg_s_shared_text_now_fails_is_never_inherited_or_waived(self):
        caption = "No leaderboard here, only today."
        self.write(1, fakes.draft(1, caption=caption))
        [first] = self.take(1).results
        self.ledger.close(self.ledger.entries[first.item], APPROVED, "RUN2", NOW)
        data = dict(self.context.rules.data)
        data["banned_words_in_hook"] = [*data["banned_words_in_hook"], "leaderboard"]
        self.context.rules = lint.Rules(data)
        unresolved = (
            "pair-legs: day 1's leg, which this leg must match beyond the Hook, now fails banned_words_in_hook, so"
            " the pair cannot both pass until the Founder resolves it by a package change or by re-cutting both legs"
        )
        fields = "(TikTok caption, YouTube Shorts description)"
        self.write(8, fakes.draft(8, caption=caption))
        outcome = self.take(8, run="RUN3")
        [copied] = outcome.results
        self.assertEqual(
            posts.grouped(copied.verdict.blocks),
            [unresolved, f"banned_words_in_hook: banned word 'leaderboard' {fields}"],
        )
        self.assertIn(unresolved, posts.notice_section(outcome, "2026-10-11")[2])
        self.write(8, fakes.draft(8, caption="Only today."))
        [reworded] = self.take(8, run="RUN4").results
        differs = f"pair-legs: differs from day 1's leg beyond the Hook (`drafts/posts/window-1/day-01.md`) {fields}"
        self.assertEqual(posts.grouped(reworded.verdict.blocks), [differs, unresolved])

    def test_a_rule_failing_text_both_drafts_can_still_change_is_not_called_the_founder_s_to_resolve(self):
        caption = "It is really just simply a list."
        self.write(1, fakes.draft(1, caption=caption))
        self.write(8, fakes.draft(8, caption=caption))
        for result in self.take(1, 8).results:
            self.assertEqual({finding.rule for finding in result.verdict.blocks}, {"capped_words"}, result.day)
        self.write(1, fakes.draft(1))
        self.write(8, fakes.draft(8))
        [first, _] = self.take(1, 8, run="RUN2").results
        data = dict(self.context.rules.data)
        data["banned_words_in_hook"] = [*data["banned_words_in_hook"], "history"]
        self.context.rules = lint.Rules(data)
        self.write(8, fakes.draft(8, caption="This is the history view, again."))
        open_leg, newer = self.take(1, 8, run="RUN3").results
        self.assertEqual((open_leg.status, open_leg.withdrawn), (posts.BLOCKED, first.item))
        self.assertEqual({finding.rule for finding in newer.verdict.blocks}, {"banned_words_in_hook", "pair-legs"})
        self.assertNotIn("cannot both pass", " ".join(posts.grouped(newer.verdict.blocks)))

    def test_a_pair_leg_whose_angle_is_missing_from_the_bank_is_blocked_and_never_rendered(self):
        del self.context.kit.angles["P03"]
        self.write(3, fakes.draft(3))
        outcome = self.take(3)
        [result] = outcome.results
        self.assertEqual((result.status, outcome.published), (posts.BLOCKED, []))
        self.assertEqual(
            posts.grouped(result.verdict.blocks),
            ["angle-bank: Angle P03 is not in projects/RepToday/gtm/05-social-pmf/angles.md"],
        )

    def test_the_record_keeps_every_check_of_every_day(self):
        self.write(3, fakes.draft(3))
        self.write(1, fakes.draft(1, caption="Join 10,000 people who stopped quitting."))
        plan = self.plan(1, 3)
        outcome = posts.take(plan, self.areas, self.store, self.ledger, "RUN1", NOW, PRODUCTS)
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
