"""The results a Weekly Read judges (US-ME11): what the run asks the Founder for, the record he gives on the sitting
page, and the Evidence each post's numbers become. Every number here is synthetic."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from gr0wthlab import exchange, founder, kit, results, sitting
from gr0wthlab.areas import Store
from gr0wthlab.package import CHANGED, FAILED, READ, SKIPPED
from gr0wthlab.settings import Window
from tests import fakes

KIT = fakes.EXAMPLES / "files" / "mandu" / "projects" / "RepToday" / "gtm" / "05-social-pmf"
FIRST_SITTING = date(2026, 10, 18)  # a Sunday: day 1 is Monday 2026-10-19, day 7 Sunday 2026-10-25
WINDOW = Window(1, FIRST_SITTING, None)
NOW = datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)


def synthetic_kit() -> kit.Kit:
    parsed = kit.Kit()
    parsed.days = kit.parse_calendar((KIT / "cadence-14-day.md").read_text(encoding="utf-8"))
    parsed.angles = kit.parse_angles((KIT / "angles.md").read_text(encoding="utf-8"))
    parsed.pairs = kit.parse_pairs((KIT / "ab-pairs.md").read_text(encoding="utf-8"))
    return parsed


def planned(day: int) -> str:
    return (FIRST_SITTING + timedelta(days=day)).isoformat()


def record(day, platform="tiktok", read=7, read_on="2026-10-25", texts=None, posted_on=None, **numbers):
    """A results record as the sitting page writes it; the post went out on its calendar day unless another is given."""
    return {
        "exchange": exchange.EXCHANGE_VERSION,
        "window": 1,
        "read": read,
        "platform": platform,
        "day": day,
        "numbers": numbers,
        "comments": texts,
        "posted_on": posted_on or planned(day),
        "read_on": read_on,
        "recorded_at": "2026-10-25T18:40:00-07:00",
    }


class DueTest(unittest.TestCase):
    def test_no_read_is_due_before_the_window_s_first_sitting_is_set(self):
        read, why = results.due(Window(1, None, None), date(2026, 10, 25))
        self.assertIsNone(read)
        self.assertIn("first sitting is not set", why)

    def test_each_read_is_due_from_its_day_for_a_week(self):
        for today, expected in (
            (date(2026, 10, 24), None),  # day 6
            (date(2026, 10, 25), 7),  # day 7, the run before the sitting
            (date(2026, 10, 31), 7),  # day 13, a run on demand late in the week
            (date(2026, 11, 1), 14),  # day 14
            (date(2026, 11, 7), 14),
            (date(2026, 11, 8), None),  # the window's reads are behind it
        ):
            with self.subTest(today=today):
                self.assertEqual(results.due(WINDOW, today)[0], expected)
        self.assertIn("behind it", results.due(WINDOW, date(2026, 11, 8))[1])
        self.assertIn("day 7, Sunday 2026-10-25", results.due(WINDOW, date(2026, 10, 20))[1])


class AskTest(unittest.TestCase):
    """Exactly what is asked: each post on the platform that judges it, its views for the floor, what the signals and
    kill criteria of the read's posts on that platform name, since each post is ranked against the others there, and
    its comments; nothing else."""

    def test_each_post_is_asked_for_on_the_platform_that_judges_it_only(self):
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", None)
        self.assertEqual(read.covered, (1, 2, 3, 4, 5))
        self.assertEqual(
            [(ask.day, ask.platform) for ask in read.asks],
            [(1, "tiktok"), (2, "tiktok"), (3, "youtube"), (4, "youtube"), (5, "tiktok")],
        )
        self.assertEqual(read.problems, [])

    def test_a_post_is_asked_for_what_the_signals_of_the_read_s_posts_on_its_platform_name(self):
        """P01 ranks on the watched-full rate and P02 on comments, both on TikTok, so each TikTok post is asked for
        both, P05 too, whose own signal names no number; on YouTube, P03 ranks on the viewed rate and P04 on comments.
        Nothing a signal on the other platform names is asked."""
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", None)
        asked = {ask.day: ask.numbers for ask in read.asks}
        for day in (1, 2, 5):
            self.assertEqual(asked[day], ("views", "watched_full_percent", "comments"), day)
        for day in (3, 4):
            self.assertEqual(asked[day], ("views", "viewed_percent", "comments"), day)
        self.assertEqual(
            read.ask_for("tiktok", 1).why,
            "its views, for the floor, and what P01's signal and kill criterion name: the watched-full rate; and, so"
            " each post can be ranked against the others on TikTok, what the read's other posts there name: comments",
        )
        self.assertIn("name no number the launcher recognizes", read.ask_for("tiktok", 5).why)
        for ask in read.asks:
            self.assertNotIn("followers", " ".join(ask.numbers))

    def test_a_read_whose_posts_name_nothing_asks_only_for_views(self):
        parsed = synthetic_kit()
        for key, angle in list(parsed.angles.items()):
            parsed.angles[key] = kit.Angle(**{**angle.__dict__, "signal": "Average viewed", "kill": "None"})
        read = results.prepare(WINDOW, 7, parsed, "", None)
        self.assertEqual({ask.numbers for ask in read.asks}, {("views",)})

    def test_a_number_the_platform_does_not_hold_is_said_and_not_asked(self):
        parsed = synthetic_kit()
        angle = parsed.angles["P03"]
        parsed.angles["P03"] = kit.Angle(**{**angle.__dict__, "signal": "Saves in the top half"})
        read = results.prepare(WINDOW, 7, parsed, "", None)
        ask = read.ask_for("youtube", 3)
        self.assertEqual(ask.numbers, ("views", "viewed_percent", "comments"))
        self.assertEqual(ask.unasked, ("saves",))
        self.assertIn("saves, which no number asked of YouTube Studio holds", ask.why)

    def test_the_real_package_s_signals_name_numbers_the_platforms_hold(self):
        """The words of the real Angle bank's signals, which every Angle of window 1 uses, as of 2026-10-14."""
        for text, expected in (
            ("Watched-full rate in top half of bank rank (>=200 impressions)", ["watched_full_percent"]),
            ("Viewed-vs-swiped rate in top half of bank rank", ["viewed_percent"]),
            ("Saves per 1,000 impressions in top half of bank rank", ["saves"]),
            ("Comments per 1,000 impressions top half, plus comment sentiment echoing the paywall pain", ["comments"]),
            ("Comments naming offline as the reason, plus top-half viewed rate", ["viewed_percent", "comments"]),
            (
                "Average % viewed top half, plus comments questioning or confirming the speed",
                ["average_percentage_viewed", "comments"],
            ),
            (
                "Zero on-topic comments AND bottom-half watch-through after two reads",
                ["watched_full_percent", "comments"],
            ),
        ):
            with self.subTest(text=text):
                self.assertEqual(results.numbers_named(text), expected)

    def test_the_day_14_read_covers_every_day_before_its_own(self):
        read = results.prepare(WINDOW, 14, synthetic_kit(), "", None)
        self.assertEqual(read.covered, tuple(range(1, 14)))
        self.assertEqual(len(read.asks), 13)

    def test_a_kit_that_could_not_be_read_asks_for_nothing_and_says_why(self):
        read = results.prepare(WINDOW, 7, None, "the calendar could not be read", None)
        self.assertEqual(read.asks, [])
        self.assertEqual(read.problems, ["nothing could be asked: the calendar could not be read"])

    def test_the_notice_lists_each_post_its_platform_and_numbers(self):
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", None)
        title, body, _, _ = results.notice(read, {"angles": "a/angles.md", "calendar": "a/cadence.md"})
        self.assertEqual(title, "Give the numbers for the window 1 day-7 Weekly Read on the sitting page")
        self.assertIn("From TikTok Studio:", body)
        self.assertIn(
            "- day 1 (P01, AB-1 leg A), TikTok, planned for Monday 2026-10-19: the day it went out, Video views,"
            " Watched full",
            body,
        )
        self.assertIn("From YouTube Studio:", body)
        self.assertIn(
            "- day 3 (P03, AB-2 leg A), YouTube Shorts, planned for Wednesday 2026-10-21: the day it went out, Views,"
            " Viewed",
            body,
        )
        self.assertIn(results.FLOOR_COUNTS, body)

    def test_a_post_s_calendar_day_is_the_day_it_was_planned_never_posted(self):
        """Nothing reads back what was posted, so before the Founder gives the day a post went out, its calendar day
        is only ever the day it was planned: in the ask the page reads and in the notice."""
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", None)
        self.assertEqual(read.as_json()["asks"][0]["planned"], "2026-10-19")
        self.assertNotIn("date", read.as_json()["asks"][0])
        _, body, _, _ = results.notice(read, {"angles": "a/angles.md", "calendar": "a/cadence.md"})
        self.assertNotIn("posted", body.lower())
        self.assertIn("give the day it went out beside its numbers", body)
        self.assertNotIn("YouTube Studio: Views", body.split("From YouTube Studio:")[0])


class FloorTest(unittest.TestCase):
    def test_the_floor_is_read_the_results_md_s_own_figure(self):
        self.assertEqual(results.floor_from("- Any post under 200 impressions is unread, not failed.\n"), 200)
        self.assertEqual(results.floor_from("- Any post under 1,000 impressions is unread, not failed."), 1000)
        self.assertIsNone(results.floor_from("- Posts below some reach are not judged."))

    def test_a_read_says_when_the_floor_cannot_be_found(self):
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", "nothing about a floor", "a/read-the-results.md")
        self.assertIsNone(read.floor)
        self.assertEqual(read.rules_unusable, "it no longer says the floor in the words this read finds it by")
        self.assertEqual(
            read.floor_problem,
            "`a/read-the-results.md` could not be used (it no longer says the floor in the words this read finds it by)"
            ", so the floor is not known",
        )
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", None, "a/read-the-results.md", "it is not UTF-8 text")
        self.assertEqual(read.rules_unusable, "it is not UTF-8 text")
        self.assertIn("could not be used (it is not UTF-8 text)", read.floor_problem)
        read = results.prepare(WINDOW, 7, synthetic_kit(), "", None)
        self.assertEqual(read.floor_problem, "`read-the-results.md` could not be read, so the floor is not known")
        self.assertEqual(read.rules_unusable, "", "a file that could not be read is a failed source, not one unusable")


class RecordTest(unittest.TestCase):
    """The Founder's record, as the page writes it and the run reads it."""

    def parse(self, data, stem=None):
        stem = stem or exchange.result_stem(data["window"], data["read"], data["platform"], data["day"])
        return exchange.parse_result(stem, json.loads(json.dumps(data)))

    def test_a_blank_number_is_not_reported_never_zero(self):
        result, problems = self.parse(record(1, views=412, watched_full_percent=None))
        self.assertEqual(problems, [])
        self.assertEqual(result.numbers, {"views": 412, "watched_full_percent": None})
        self.assertIsNone(result.comments)

    def test_no_follower_count_or_other_number_is_ever_taken(self):
        for key in ("followers", "new_followers", "subscribers_gained", "impressions"):
            with self.subTest(key=key):
                _, problems = self.parse(record(1, views=10, **{key: 3}))
                self.assertIn(f"{key!r} is not a number gr0wthlab takes from tiktok", problems)

    def test_numbers_must_be_of_their_kind(self):
        for numbers, expected in (
            ({"views": -1}, "views must be a whole number from 0"),
            ({"views": 1.5}, "views must be a whole number from 0"),
            ({"watched_full_percent": 140}, "watched_full_percent must be a percentage from 0 to 100"),
            ({"views": True}, "views must be a number"),
            ({"views": "412"}, "views must be a number"),
        ):
            with self.subTest(numbers=numbers):
                self.assertTrue(any(expected in problem for problem in self.parse(record(1, **numbers))[1]))

    def test_youtube_s_average_percentage_viewed_may_pass_100_and_the_other_percentages_may_not(self):
        """YouTube Studio counts every loop of a Short in its average percentage viewed, so the exact figure the
        Founder types can be over 100; a share of viewers never can."""
        result, problems = self.parse(record(3, "youtube", views=150, average_percentage_viewed=112.4))
        self.assertEqual((problems, result.numbers["average_percentage_viewed"]), ([], 112.4))
        for numbers, expected in (
            ({"average_percentage_viewed": 1000.5}, "average_percentage_viewed must be a percentage from 0 to 1000"),
            ({"viewed_percent": 100.5}, "viewed_percent must be a percentage from 0 to 100"),
        ):
            with self.subTest(numbers=numbers):
                problems = self.parse(record(3, "youtube", views=150, **numbers))[1]
                self.assertTrue(any(problem.startswith(expected) for problem in problems), problems)
        reasons = []
        self.assertEqual(sitting.studio_number("112.4%", "Average percentage viewed", "percent viewed", reasons), 112.4)
        self.assertIsNone(sitting.studio_number("101%", "Viewed", exchange.PERCENT, reasons))
        self.assertEqual(reasons, ["Viewed must be a percentage from 0 to 100"])

    def test_a_youtube_record_takes_youtube_s_numbers(self):
        result, problems = self.parse(record(3, "youtube", views=150, viewed_percent=61.5))
        self.assertEqual(problems, [])
        _, problems = self.parse(record(3, "youtube", saves=3))
        self.assertIn("'saves' is not a number gr0wthlab takes from youtube", problems)

    def test_the_name_must_match_the_record_and_the_day_be_one_the_read_covers(self):
        _, problems = self.parse(record(1, views=1), "window-1-read-07-tiktok-day-02")
        self.assertTrue(problems[0].startswith("the file name 'window-1-read-07-tiktok-day-02' must be"))
        _, problems = self.parse(record(6, views=1))
        self.assertIn("the day-7 read covers days 1 to 5; day 6 is not one of them", problems)

    def test_a_record_that_gives_nothing_is_no_record(self):
        _, problems = self.parse(record(1, views=None))
        self.assertEqual(problems, ["the record gives no number and no comment"])

    def test_comments_are_lines_of_text(self):
        result, problems = self.parse(record(1, views=3, texts=["No streak? Finally.", "Same here"]))
        self.assertEqual((problems, result.comments), ([], ("No streak? Finally.", "Same here")))
        _, problems = self.parse(record(1, views=3, texts=["two\nlines"]))
        self.assertIn("a comment must be one line of text", problems)
        _, problems = self.parse(record(1, views=3, texts=["x" * 301]))
        self.assertIn("a comment must be at most 300 characters", problems)

    def test_the_date_read_cannot_come_after_the_record(self):
        _, problems = self.parse(record(1, views=3, read_on="2026-10-26"))
        self.assertIn("read_on is after the day the record was made", problems)

    def test_the_record_keeps_the_day_the_founder_says_the_post_went_out(self):
        result, problems = self.parse(record(1, views=3, posted_on="2026-10-20"))
        self.assertEqual((problems, result.posted_on), ([], "2026-10-20"))
        for posted_on, expected in (
            (None, "posted_on must be the YYYY-MM-DD date the Founder says the post went out"),
            ("Monday", "posted_on must be the YYYY-MM-DD date the Founder says the post went out"),
            ("2026-10-26", "posted_on is after read_on, the day the numbers were read"),
        ):
            with self.subTest(posted_on=posted_on):
                _, problems = self.parse(dict(record(1, views=3), posted_on=posted_on))
                self.assertIn(expected, problems)


class TakeTest(unittest.TestCase):
    """The US-ME11 Validation Test's collection, on a synthetic export that misses one post."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = Path(os.path.realpath(self.temporary.name)) / "ledger"
        fakes.make_founder(self.ledger)
        self.store = Store(self.ledger)
        self.read = results.prepare(WINDOW, 7, synthetic_kit(), "", "- Any post under 200 impressions is unread.")

    def give(self, data):
        stem = exchange.result_stem(data["window"], data["read"], data["platform"], data["day"])
        fakes.write_record(founder.folders(self.ledger)[founder.RESULTS], f"{stem}.json", data)

    def evidence(self, day):
        return json.loads(
            (self.ledger / "evidence" / "results" / "window-1" / "read-07" / f"day-{day:02d}.json").read_text()
        )

    def test_each_post_given_becomes_evidence_with_its_source_and_a_missing_post_is_not_reported(self):
        self.give(record(1, views=412, watched_full_percent=31.0))
        self.give(record(2, views=180, comments=4))
        self.give(record(3, "youtube", views=950, viewed_percent=72.5))
        self.give(record(4, "youtube", views=260, comments=None, read_on="2026-10-24"))
        # Day 5 was not in the export.
        taken = results.take(self.store, self.read, "run-1", NOW)
        self.assertEqual(taken.unusable, [])
        day1 = self.evidence(1)
        self.assertEqual(
            day1["platforms"]["tiktok"]["numbers"], {"views": 412, "watched_full_percent": 31.0, "comments": None}
        )
        self.assertEqual(day1["platforms"]["tiktok"]["posted_on"], "2026-10-19")
        self.assertEqual(day1["platforms"]["tiktok"]["source"]["read_on"], "2026-10-25")
        self.assertEqual(
            day1["platforms"]["tiktok"]["source"]["record"], "founder/results/window-1-read-07-tiktok-day-01.json"
        )
        day4 = self.evidence(4)
        self.assertEqual(
            day4["platforms"]["youtube"]["numbers"], {"views": 260, "viewed_percent": None, "comments": None}
        )
        self.assertEqual(day4["platforms"]["youtube"]["not_reported"], ["viewed_percent", "comments"])
        day5 = self.evidence(5)
        self.assertEqual(
            day5["platforms"]["tiktok"]["numbers"], {"views": None, "watched_full_percent": None, "comments": None}
        )
        self.assertEqual(day5["platforms"]["tiktok"]["not_reported"], ["views", "watched_full_percent", "comments"])
        self.assertIsNone(day5["platforms"]["tiktok"]["source"])
        self.assertIsNone(day5["platforms"]["tiktok"]["posted_on"], "not reported, never taken to be not posted")
        self.assertNotIn(
            0,
            [
                value
                for day in (1, 2, 3, 4, 5)
                for value in self.evidence(day)["platforms"].get("tiktok", {}).get("numbers", {}).values()
            ],
        )
        self.assertEqual([ask.day for ask in taken.missing(self.read)], [5])
        self.assertEqual(results.gaps(self.read, taken), ["not given yet, so not reported: day 5 (P05), TikTok"])

    def test_the_floor_reads_views_on_the_platform_that_judges_the_post(self):
        self.give(record(1, views=199))
        self.give(record(3, "youtube", views=200))
        taken = results.take(self.store, self.read, "run-1", NOW)
        self.assertFalse(results.readable(self.read, taken, self.read.ask_for("tiktok", 1)))
        self.assertTrue(results.readable(self.read, taken, self.read.ask_for("youtube", 3)))
        self.assertFalse(results.readable(self.read, taken, self.read.ask_for("tiktok", 2)), "not reported is unread")

    def test_evidence_is_written_again_only_when_what_it_rests_on_changed(self):
        self.give(record(1, views=412))
        first = results.take(self.store, self.read, "run-1", NOW)
        self.assertEqual(len(first.changed), 5)
        second = results.take(self.store, self.read, "run-2", NOW)
        self.assertEqual(second.changed, [])
        self.give(record(1, views=500))
        third = results.take(self.store, self.read, "run-3", NOW)
        self.assertEqual(third.changed, ["evidence/results/window-1/read-07/day-01.json"])

    def test_a_record_that_cannot_be_used_is_named_and_nothing_is_taken_from_it(self):
        folder = founder.folders(self.ledger)[founder.RESULTS]
        (folder / "window-1-read-07-tiktok-day-01.json").write_text('{"exchange": 8, "window": 1}')
        taken = results.take(self.store, self.read, "run-1", NOW)
        self.assertEqual(taken.given, {})
        ((name, problems, _),) = taken.unusable
        self.assertEqual(name, "founder/results/window-1-read-07-tiktok-day-01.json")
        self.assertTrue(problems)

    def test_the_source_lines_say_what_was_given_and_never_call_a_missing_post_failed(self):
        taken = results.take(self.store, self.read, "run-1", NOW)
        lines = {name: (status, detail) for name, status, detail in results.source_lines(self.read, taken)}
        self.assertEqual(lines["TikTok Studio numbers (sitting page)"][0], SKIPPED)
        self.give(record(1, views=412))
        taken = results.take(self.store, self.read, "run-2", NOW)
        lines = {name: (status, detail) for name, status, detail in results.source_lines(self.read, taken)}
        self.assertEqual(
            lines["TikTok Studio numbers (sitting page)"],
            (CHANGED, "1 post of 3 given for the window 1 day-7 Weekly Read; not given, so not reported: day 2, 5"),
        )
        taken = results.take(self.store, self.read, "run-3", NOW)
        lines = {name: status for name, status, _ in results.source_lines(self.read, taken)}
        self.assertEqual(lines["TikTok Studio numbers (sitting page)"], READ)

    def test_a_folder_that_cannot_be_read_is_a_failed_source(self):
        folder = founder.folders(self.ledger)[founder.RESULTS]
        (folder / ".gitkeep").unlink()
        os.rmdir(folder)
        taken = results.take(self.store, self.read, "run-1", NOW)
        self.assertIn("could not be read", taken.failure)
        statuses = {status for _, status, _ in results.source_lines(self.read, taken)}
        self.assertEqual(statuses, {FAILED})


if __name__ == "__main__":
    unittest.main()
