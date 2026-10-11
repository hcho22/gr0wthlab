"""Edit records: the format the agent writes, and every check against the shot list, the footage, and the Draft."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from gr0wthlab import drafts, edits, filming, shots, video
from tests import fakes

CANVAS = video.load_canvas(json.loads((fakes.REPO / "config" / "platforms.json").read_text(encoding="utf-8")))
FILES = fakes.FILMING / "files"


def clips():
    held = json.loads((FILES / "footage.json").read_text(encoding="utf-8"))["clips"]
    return {clip["name"]: edits.Clip.from_json(clip) for clip in held}


def draft(day):
    name = f"files/drafts/day-{day:02d}.md"
    return drafts.parse((fakes.FILMING / name).read_text(encoding="utf-8"), name)


def record(day, *segments):
    return edits.parse(fakes.edit_record(day, *segments), f"drafts/edits/window-1/day-{day:02d}.json")


class EditTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.kit, cls.roles = fakes.filming_kit(Path(os.path.realpath(cls.tmp.name)) / "Mandu")
        cls.found = shots.requirements(cls.kit, cls.roles["calendar"])
        cls.clips = clips()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def spec(self, day):
        return filming.day_spec("RepToday", 1, day, self.kit.days[day].leg, self.found.job_for(day))

    def rules(self, edit, day, text=None):
        found = edits.check(edit, self.spec(day), self.clips, draft(day) if text is None else text, CANVAS)
        return [finding.rule for finding in found], [finding.line() for finding in found]


class ParseTest(unittest.TestCase):
    def test_an_edit_record_holds_its_day_and_its_segments(self):
        edit = record(1, ("d01-s1", "d01-s1.mov", 2, 12.0))
        self.assertEqual(edit.problems, [])
        self.assertEqual((edit.product, edit.window, edit.day, edit.length), ("RepToday", 1, 1, 10.0))
        self.assertEqual(edit.segments[0], edits.Segment("d01-s1", "window-1/d01-s1.mov", 2.0, 12.0))
        self.assertEqual(len(edit.sha256), 64)
        self.assertEqual(edits.parse(json.dumps(edit.as_json()), edit.path).segments, edit.segments)

    def test_a_segment_may_add_speed_fit_and_mute_and_nothing_else(self):
        edit = record(7, ("d07-s1", "d07-s1.mov", 0, 300, {"speed": 20, "fit": "cover", "mute": True}))
        self.assertEqual(edit.problems, [])
        self.assertEqual((edit.segments[0].speed, edit.segments[0].fit, edit.segments[0].mute), (20.0, "cover", True))
        self.assertEqual(edit.length, 15.0)
        bad = record(7, ("d07-s1", "d07-s1.mov", 0, 300, {"filter": "blur"}))
        self.assertIn("segment 1 holds the keys shot, source, in, out, and may add speed, fit, mute", bad.problems)

    def test_what_does_not_follow_the_format_is_named(self):
        for text, problem in (
            ("not json", "it is not JSON"),
            ('{"edit": 1}', "it holds exactly the keys edit, product, window, day, segments"),
            (fakes.edit_record(1).replace('"edit": 1', '"edit": 2'), "edit must be 1"),
            (fakes.edit_record(1), "segments must list at least one piece of the timeline"),
            (fakes.edit_record(1, ("d01-s1", "d01-s1.mov", "2", 12)), "segment 1: in, out, and speed are numbers"),
            (fakes.edit_record(1, ("d01-s1", "d01-s1.mov", True, 12)), "segment 1: in, out, and speed are numbers"),
            (fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 2, 12, {"fit": "stretch"})), "fit is one of contain, cover"),
            (fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 2, 12)).replace('"day": 1', '"day": "one"'), "day must be"),
        ):
            with self.subTest(problem=problem):
                self.assertTrue(any(problem in found for found in edits.parse(text, "x.json").problems))

    def test_an_edit_has_a_bounded_number_of_segments(self):
        many = [("d01-s1", "d01-s1.mov", 0, 1)] * (edits.MAX_SEGMENTS + 1)
        self.assertIn("an edit has at most 60", edits.parse(fakes.edit_record(1, *many), "x.json").problems[0])


class CheckTest(EditTestCase):
    def test_one_unbroken_range_of_the_shot_s_own_file_passes(self):
        self.assertEqual(self.rules(record(1, ("d01-s1", "d01-s1.mov", 2, 12)), 1), ([], []))

    def test_an_edit_record_cannot_name_a_source_outside_the_footage_place(self):
        for source in (
            "../outside.mov",
            "window-1/../../outside.mov",
            "/Users/founder/Movies/holiday.mov",
            "~/Movies/holiday.mov",
            "window-1//d01-s1.mov",
            "window-1/./d01-s1.mov",
            "window-1\\d01-s1.mov",
            "",
        ):
            with self.subTest(source=source):
                rules, lines = self.rules(record(1, ("d01-s1", source or "/", 2, 12)), 1)
                self.assertIn("footage-place", rules)
                self.assertTrue(any("names a source outside the footage place" in line for line in lines), lines)

    def test_a_file_the_footage_place_does_not_hold_cannot_be_used(self):
        rules, lines = self.rules(record(1, ("d01-s1", "d01-s1-take-9.mov", 2, 12)), 1)
        self.assertEqual(rules, ["footage-place"])
        self.assertIn("the footage place holds no file 'window-1/d01-s1-take-9.mov'", lines[0])

    def test_a_file_is_used_only_as_the_shot_it_is_named_for(self):
        rules, lines = self.rules(record(1, ("d01-s1", "d02-s2.mov", 2, 12)), 1)
        self.assertEqual(rules, ["shot-list"])
        self.assertIn("`window-1/d02-s2.mov` is footage of shot d02-s2, so it cannot be used as d01-s1", lines[0])
        rules, lines = self.rules(record(1, ("d09-s1", "d01-s1.mov", 2, 12)), 1)
        self.assertIn("'d09-s1' is not a shot of day 1's shot list (d01-s1)", lines[0])

    def test_a_shot_that_may_not_be_cut_is_one_unbroken_source_range(self):
        cut = record(1, ("d01-s1", "d01-s1.mov", 1, 5), ("d01-s1", "d01-s1.mov", 7, 13))
        rules, lines = self.rules(cut, 1)
        self.assertEqual(rules, ["no-cut"])
        self.assertIn("shot d01-s1 may not be cut (the Format: no cuts)", lines[0])
        self.assertIn("as 2 source ranges, not one unbroken range", lines[0])
        # Two segments that run on from each other are one unbroken range.
        joined = record(1, ("d01-s1", "d01-s1.mov", 2, 6), ("d01-s1", "d01-s1.mov", 6, 12))
        self.assertEqual(self.rules(joined, 1)[0], [])
        # The same recording shown twice is two ranges.
        twice = record(1, ("d01-s1", "d01-s1.mov", 2, 7), ("d01-s1", "d01-s1.mov", 2, 7))
        self.assertEqual(self.rules(twice, 1)[0], ["no-cut"])

    def test_an_uncut_shot_split_around_another_shot_is_cut_even_when_its_source_runs_on(self):
        whole = record(
            2,
            ("d02-s1", "d02-s1a-take-1.mov", 1, 4),
            ("d02-s2", "d02-s2.mov", 2, 7),
            ("d02-s2", "d02-s2.mov", 7, 13),
            ("d02-s1", "d02-s1-closing.mov", 5, 11),
        )
        self.assertEqual(self.rules(whole, 2)[0], [])
        split = record(
            2,
            ("d02-s1", "d02-s1a-take-1.mov", 1, 4),
            ("d02-s2", "d02-s2.mov", 2, 7),
            ("d02-s1", "d02-s1-closing.mov", 5, 11),
            ("d02-s2", "d02-s2.mov", 7, 13),
        )
        rules, lines = self.rules(split, 2)
        self.assertEqual(rules, ["no-cut"])
        self.assertIn("shot d02-s2 may not be cut", lines[0])
        self.assertIn("as 2 source ranges, not one unbroken range", lines[0])
        gap = record(
            2,
            ("d02-s2", "d02-s2.mov", 2, 8),
            ("d02-s1", "d02-s1-closing.mov", 0, 9),
            ("d02-s2", "d02-s2.mov", 9, 14),
        )
        self.assertEqual(self.rules(gap, 2)[0], ["no-cut"])

    def test_every_shot_of_the_list_needs_footage_or_there_is_no_asset(self):
        only = record(2, ("d02-s1", "d02-s1a-take-1.mov", 1, 4), ("d02-s1", "d02-s1-closing.mov", 0, 15))
        rules, lines = self.rules(record(2, ("d02-s1", "d02-s1-closing.mov", 0, 15)), 2)
        self.assertIn("missing-shot", rules)
        rules, lines = self.rules(only, 2)
        self.assertIn("missing-shot", rules)
        self.assertTrue(
            any(
                "shot d02-s2 (a screen record of the app opening) has no footage in this edit" in line for line in lines
            )
        )

    def test_nothing_runs_at_another_speed_unless_its_shot_list_says_it_is_not_real_time(self):
        rules, lines = self.rules(record(1, ("d01-s1", "d01-s1.mov", 0, 14, {"speed": 1.4})), 1)
        self.assertEqual(rules, ["real-time"])
        self.assertIn("d01-s1 plays at 1.4x, and its shot list says real time", lines[0])
        founder = record(
            2,
            ("d02-s1", "d02-s1-closing.mov", 0, 15, {"speed": 1.5}),
            ("d02-s2", "d02-s2.mov", 2, 12),
        )
        rules, lines = self.rules(founder, 2)
        self.assertEqual(rules, ["real-time"])
        self.assertIn("its shot list does not say it may run at another speed", lines[0])
        lapse = record(7, ("d07-s1", "d07-s1.mov", 5, 325, {"speed": 20}))
        self.assertEqual(self.rules(lapse, 7), ([], []))

    def test_a_source_range_lies_inside_the_file_as_measured(self):
        for start, end, said in (
            (-1, 9, "in must be 0 or later"),
            (5, 5, "out at least one frame after it"),
            (6, 16, "out is 16s, past the end of `window-1/d01-s1.mov`, which measures 14.00s"),
        ):
            with self.subTest(said=said):
                rules, lines = self.rules(record(1, ("d01-s1", "d01-s1.mov", start, end)), 1)
                self.assertEqual(rules, ["source-range"])
                self.assertIn(said, lines[0])

    def test_a_speed_is_above_zero_and_bounded(self):
        for speed in (0, -2, 101):
            with self.subTest(speed=speed):
                edit = record(7, ("d07-s1", "d07-s1.mov", 0, 300, {"speed": speed}))
                self.assertEqual(edit.problems, ["segment 1: speed is above 0 and at most 100"])
                self.assertEqual(self.rules(edit, 7)[0], ["edit-format"])

    def test_the_length_is_the_format_s_and_the_one_the_draft_s_beats_add_up_to(self):
        rules, lines = self.rules(record(1, ("d01-s1", "d01-s1.mov", 1, 13)), 1)
        self.assertEqual(rules, ["length", "length"])
        self.assertIn("the edit runs 12.00s, and the Format gives 10s", lines[0])
        self.assertIn("the beats of `files/drafts/day-01.md` end at 10s", lines[1])
        # A range of the Format's length that the Draft's beats do not add up to.
        longer = replace(draft(7), beats=draft(7).beats[:2])
        rules, lines = self.rules(record(7, ("d07-s1", "d07-s1.mov", 5, 325, {"speed": 20})), 7, longer)
        self.assertEqual(rules, ["length"])
        self.assertIn("end at 13s", lines[0])
        # A Format that gives a range takes any length inside it.
        within = replace(
            draft(7), beats=[replace(beat, end=19 if beat.number == 3 else beat.end) for beat in draft(7).beats]
        )
        self.assertEqual(self.rules(record(7, ("d07-s1", "d07-s1.mov", 0, 285, {"speed": 15})), 7, within)[0], [])

    def test_a_file_that_could_not_be_measured_cannot_be_used(self):
        broken = dict(self.clips)
        broken["window-1/d01-s1.mov"] = replace(broken["window-1/d01-s1.mov"], facts=None, problem="it holds no video")
        found = edits.check(record(1, ("d01-s1", "d01-s1.mov", 2, 12)), self.spec(1), broken, draft(1), CANVAS)
        self.assertEqual([finding.rule for finding in found], ["footage"])
        self.assertIn("`window-1/d01-s1.mov` cannot be used: it holds no video", found[0].detail)

    def test_the_record_is_the_day_s_own(self):
        rules, lines = self.rules(record(8, ("d01-s1", "d01-s1.mov", 2, 12)), 1)
        self.assertEqual(rules, ["edit-day"])
        wrong = edits.parse(fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 2, 12), product="Immerse"), "x.json")
        self.assertEqual(self.rules(wrong, 1)[0], ["edit-day"])

    def test_a_record_that_does_not_follow_the_format_fails_on_that_alone(self):
        rules, lines = self.rules(edits.parse("{}", "x.json"), 1)
        self.assertEqual(rules, ["edit-format"])

    def test_text_the_renderer_cannot_draw_or_fit_blocks_the_edit(self):
        base = draft(1)
        braces = replace(base, beats=[replace(base.beats[0], on_screen="Open {it}"), *base.beats[1:]])
        self.assertEqual(self.rules(record(1, ("d01-s1", "d01-s1.mov", 2, 12)), 1, braces)[0], ["overlay-text"])
        long = replace(base, beats=[replace(base.beats[0], spoken="word " * 40), *base.beats[1:]])
        rules, lines = self.rules(record(1, ("d01-s1", "d01-s1.mov", 2, 12)), 1, long)
        self.assertEqual(rules, ["overlay-text"])
        self.assertIn("the caption at 0s is 200 characters, more than the 160 that fit the safe zone", lines[0])

    def test_a_take_named_for_one_leg_is_that_leg_s(self):
        other = record(
            9,
            ("d02-s1", "d02-s1a-take-1.mov", 1, 4),
            ("d02-s2", "d02-s2.mov", 2, 13),
            ("d02-s1", "d02-s1-closing.mov", 5, 11),
        )
        rules, lines = self.rules(other, 9)
        self.assertEqual(rules, ["shot-list"])
        self.assertIn("`window-1/d02-s1a-take-1.mov` is leg A's take, and day 9 is leg B", lines[0])


class OverlayTest(unittest.TestCase):
    def test_each_beat_s_on_screen_text_and_spoken_line_are_drawn_for_the_beat_s_time(self):
        found = edits.overlays(draft(2))
        self.assertEqual(
            [(overlay.start, overlay.end, overlay.caption) for overlay in found],
            [(0.0, 3.0, False), (3.0, 14.0, False), (14.0, 20.0, False), (14.0, 20.0, True)],
        )
        self.assertEqual(found[0].text, "I open my own app and the session is already there.")
        self.assertEqual(found[3].text, "I am building this on my own. It is not released yet.")

    def test_a_spoken_line_the_on_screen_text_already_says_is_not_drawn_twice(self):
        hook = [overlay for overlay in edits.overlays(draft(2)) if overlay.start == 0]
        self.assertEqual(len(hook), 1)
        self.assertEqual([overlay.caption for overlay in edits.overlays(draft(1))], [False, False, False])


class PairTest(EditTestCase):
    def pair(self, mine, day, theirs, other):
        found = edits.check_pair(mine, draft(day), theirs, draft(other), self.spec(day))
        return [finding.line() for finding in found]

    def test_the_legs_of_a_plain_pair_share_every_source_range(self):
        day_1 = record(1, ("d01-s1", "d01-s1.mov", 2, 12))
        self.assertEqual(self.pair(record(8, ("d01-s1", "d01-s1.mov", 2, 12)), 8, day_1, 1), [])
        # The same range written as two segments that run on is the same range.
        self.assertEqual(
            self.pair(record(8, ("d01-s1", "d01-s1.mov", 2, 5), ("d01-s1", "d01-s1.mov", 5, 12)), 8, day_1, 1), []
        )
        lines = self.pair(record(8, ("d01-s1", "d01-s1.mov", 3, 13)), 8, day_1, 1)
        self.assertEqual(len(lines), 1)
        self.assertIn(
            "pair-legs: its source ranges differ from day 1's leg (`drafts/edits/window-1/day-01.json`) from its"
            " first frame",
            lines[0],
        )
        self.assertIn("this leg shows `window-1/d01-s1.mov` 3-13s, that leg `window-1/d01-s1.mov` 2-12s", lines[0])
        self.assertIn("the legs of AB-1 share their footage", lines[0])

    def test_a_plain_pair_s_legs_may_not_differ_even_in_their_first_seconds(self):
        day_1 = record(1, ("d01-s1", "d01-s1.mov", 2, 12))
        other_opening = record(8, ("d01-s1", "d01-s1.mov", 0, 3), ("d01-s1", "d01-s1.mov", 5, 12))
        self.assertEqual(len(self.pair(other_opening, 8, day_1, 1)), 1)
        muted = record(8, ("d01-s1", "d01-s1.mov", 2, 12, {"mute": True}))
        self.assertEqual(len(self.pair(muted, 8, day_1, 1)), 1)

    def test_the_legs_of_a_re_cut_pair_share_every_source_range_after_the_opening(self):
        tail = (("d02-s2", "d02-s2.mov", 2, 13), ("d02-s1", "d02-s1-closing.mov", 5, 11))
        day_2 = record(2, ("d02-s1", "d02-s1a-take-1.mov", 1, 4), *tail)
        day_9 = record(9, ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5), *tail)
        self.assertEqual(self.pair(day_9, 9, day_2, 2), [])
        moved = record(9, ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5), ("d02-s2", "d02-s2.mov", 4, 15), tail[1])
        lines = self.pair(moved, 9, day_2, 2)
        self.assertIn(
            "differ from day 2's leg (`drafts/edits/window-1/day-02.json`) after the re-cut opening", lines[0]
        )
        self.assertIn("`window-1/d02-s2.mov` 4-15s", lines[0])

    def test_a_re_cut_opening_may_be_cut_from_the_take_the_rest_runs_on_from(self):
        # One leg opens on its own take; the other's opening and what follows are one unbroken take.
        day_2 = record(2, ("d02-s1", "d02-s1-closing.mov", 0, 9), ("d02-s2", "d02-s2.mov", 2, 13))
        day_9 = record(
            9,
            ("d02-s1", "d02-s1b-take-1.mov", 0, 3),
            ("d02-s1", "d02-s1-closing.mov", 3, 9),
            ("d02-s2", "d02-s2.mov", 2, 13),
        )
        self.assertEqual(self.pair(day_9, 9, day_2, 2), [])

    def test_the_opening_of_a_re_cut_leg_is_its_hook_beat_and_any_beat_that_shows_a_hook_of_the_pair(self):
        hooks = self.spec(9).hooks
        self.assertEqual(len(hooks), 2)
        self.assertEqual(edits.opening_windows(draft(9), hooks), [(0.0, 3.0)])
        base = draft(9)
        later = replace(base, beats=[base.beats[0], replace(base.beats[1], spoken=hooks[0]), base.beats[2]])
        self.assertEqual(edits.opening_windows(later, hooks), [(0.0, 3.0), (3.0, 14.0)])
        self.assertEqual(edits.opening_windows(draft(8), ()), [])

    def test_source_ranges_outside_the_opening_are_read_to_the_millisecond(self):
        segments = record(1, ("d01-s1", "d01-s1.mov", 2, 12)).segments
        self.assertEqual(edits.pieces(segments), [("window-1/d01-s1.mov", 2.0, 12.0, 1.0, "contain", False)])
        self.assertEqual(edits.pieces(segments, [(0, 3)]), [("window-1/d01-s1.mov", 5.0, 12.0, 1.0, "contain", False)])
        self.assertEqual(
            edits.pieces(segments, [(0, 3), (5, 6)]),
            [
                ("window-1/d01-s1.mov", 5.0, 7.0, 1.0, "contain", False),
                ("window-1/d01-s1.mov", 8.0, 12.0, 1.0, "contain", False),
            ],
        )
        fast = record(7, ("d07-s1", "d07-s1.mov", 0, 300, {"speed": 20})).segments
        self.assertEqual(edits.pieces(fast, [(0, 3)]), [("window-1/d07-s1.mov", 60.0, 300.0, 20.0, "contain", False)])


if __name__ == "__main__":
    unittest.main()
