"""Shot lists read from the kit: each Format's recordings, the filming jobs, and the fewest sittings."""

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from gr0wthlab import kit, shots
from tests import fakes

CALENDAR = "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
RULE = shots.ScreenRule(31, True, True, True)


def one(text, rule=None):
    return shots.shot_list("d01", text, rule, CALENDAR)


class ShotListTest(unittest.TestCase):
    def test_a_screen_recording_states_its_length_device_real_time_and_no_cuts(self):
        length, found = one(
            "8-12s screen record, cold open to a ready session, no cuts, real time, on-screen text only"
        )
        self.assertEqual(length, (8, 12))
        self.assertEqual(len(found), 1)
        shot = found[0]
        self.assertEqual(
            (shot.id, shot.kind, shot.setup, shot.needs), ("d01-s1", "screen recording", "device", "a real device")
        )
        self.assertEqual(
            shot.what, "screen record, cold open to a ready session, no cuts, real time, on-screen text only"
        )
        self.assertEqual((shot.real_time, shot.real_time_why), (True, "the Format: real time"))
        self.assertEqual((shot.uncut, shot.uncut_why), (True, "the Format: no cuts"))

    def test_what_the_format_does_not_state_is_not_stated_never_guessed(self):
        _, (shot,) = one("12s screen record: the history view with a missed day, on-screen text")
        self.assertEqual((shot.real_time, shot.uncut, shot.real_device), (None, False, False))
        self.assertEqual(shot.what, "screen record: the history view with a missed day, on-screen text")
        _, (founder,) = one("20s founder-on-camera (mandatory, first person), review shown as on-screen text")
        self.assertEqual((founder.kind, founder.setup, founder.needs), ("founder on camera", "camera", "the Founder"))
        self.assertEqual((founder.real_time, founder.uncut), (None, False))

    def test_the_calendar_s_rule_for_every_screen_recording_fills_in_what_the_format_leaves_out(self):
        _, (shot,) = one("12s screen record: the history view with a missed day", RULE)
        self.assertEqual((shot.real_time, shot.uncut, shot.real_device), (True, True, True))
        self.assertEqual(shot.real_time_why, f"{CALENDAR} line 31: screen recordings are real time")
        self.assertIn("cuts only where the shot list declares them, and it declares none", shot.uncut_why)
        _, (founder,) = one("20s founder-on-camera line", RULE)
        self.assertEqual((founder.real_time, founder.uncut), (None, False))

    def test_a_recording_starts_after_then_or_at_an_insert_and_keeps_the_format_s_own_words(self):
        length, found = one(
            "20-30s founder-on-camera intro (mandatory, first person) then screen record of a missed day"
        )
        self.assertEqual(length, (20, 30))
        self.assertEqual(
            [(shot.id, shot.kind) for shot in found], [("d01-s1", "founder on camera"), ("d01-s2", "screen recording")]
        )
        self.assertEqual(found[0].what, "founder-on-camera intro (mandatory, first person)")
        self.assertEqual(found[1].what, "screen record of a missed day")
        _, insert = one(
            "20-30s founder-on-camera (mandatory for first-person lines) with screen-record insert of the return flow"
        )
        self.assertEqual(
            [shot.what for shot in insert],
            ["founder-on-camera (mandatory for first-person lines)", "screen-record insert of the return flow"],
        )
        _, demo = one(
            "15-20s founder-on-camera line (mandatory, first person) then immediate cold-open demo, no chaperone"
            " sentence"
        )
        self.assertEqual(
            [(shot.kind, shot.setup) for shot in demo], [("founder on camera", "camera"), ("device demo", "device")]
        )

    def test_words_that_name_no_recording_stay_with_the_recording_before_them(self):
        _, overlay = one("10s screen record with a tap counter overlay that increments only on visible taps, real time")
        self.assertEqual(len(overlay), 1)
        self.assertTrue(overlay[0].real_time)
        _, history = one("12s screen record: history view with a missed day, the score dips and does not reset")
        self.assertEqual(len(history), 1)
        _, pan = one("12s video: slow pan of a bare room, then app opens to a ready session")
        self.assertEqual([(shot.kind, shot.setup) for shot in pan], [("camera footage", "camera")])
        self.assertEqual(pan[0].what, "video: slow pan of a bare room, then app opens to a ready session")

    def test_a_timelapse_and_slow_motion_are_never_real_time(self):
        _, (lapse,) = one("15-20s timelapse of one real 5-minute session, phone timer visible")
        self.assertEqual((lapse.kind, lapse.setup, lapse.real_time), ("timelapse", "camera", False))
        self.assertEqual(lapse.real_time_why, "the Format: timelapse")
        length, (slow,) = one(
            "15s: high-frame-rate capture of cold open played in slow motion, then once at real speed, no cuts"
            " within each take"
        )
        self.assertEqual(
            (length, slow.kind, slow.setup, slow.real_time, slow.uncut),
            ((15, 15), "slow-motion capture", "not stated", False, True),
        )

    def test_no_cuts_within_each_take_holds_for_every_shot(self):
        _, found = one("20s founder-on-camera line then screen record of the app, no cuts within each take")
        self.assertEqual([shot.uncut for shot in found], [True, True])

    def test_a_format_that_names_no_recording_has_no_shot(self):
        self.assertEqual(one("a carousel of three cards"), (None, ()))
        self.assertEqual(one("3 screens of text"), (None, ()))

    def test_a_footage_file_is_named_for_its_shot_and_for_the_leg_whose_opening_it_is(self):
        self.assertEqual(shots.file_shot("d01-s1.mov"), ("d01-s1", None))
        self.assertEqual(shots.file_shot("D06-S1b-take-2.MOV"), ("d06-s1", "B"))
        self.assertEqual(shots.file_shot("d06-s1a.mp4"), ("d06-s1", "A"))
        self.assertEqual(shots.file_shot("d12-s2 take 3.mov"), ("d12-s2", None))
        for name in ("holiday.mov", "d1-s1.mov", "d01-s1x.mov", "d01-s12b3.mov", "xd01-s1.mov"):
            self.assertIsNone(shots.file_shot(name), name)


class RequirementsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.kit, cls.roles = fakes.filming_kit(Path(os.path.realpath(cls.tmp.name)) / "Mandu")
        cls.found = shots.requirements(cls.kit, cls.roles["calendar"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_legs_of_a_pair_share_one_job_and_the_later_leg_films_nothing(self):
        jobs = {job.key: job for job in self.found.jobs}
        self.assertEqual(list(jobs), ["d01", "d02", "d03", "d04", "d05", "d06", "d07", "d11", "d12", "d13"])
        self.assertEqual((jobs["d01"].days, jobs["d01"].pair, jobs["d01"].recut), ((1, 8), "AB-1", False))
        self.assertEqual((jobs["d02"].days, jobs["d02"].pair, jobs["d02"].recut), ((2, 9), "AB-3", True))
        self.assertEqual((jobs["d01"].films, jobs["d01"].reuses), (1, (8,)))
        self.assertEqual(self.found.reuse_days(), [8, 9, 10])
        self.assertEqual(self.found.on_camera_days(), [2])
        self.assertIs(self.found.job_for(9), jobs["d02"])
        self.assertIsNone(self.found.job_for(14))

    def test_a_day_of_the_same_angle_outside_a_pair_is_its_own_job(self):
        jobs = {job.key: job for job in self.found.jobs}
        self.assertEqual(
            (jobs["d04"].days, jobs["d11"].days, jobs["d04"].angle, jobs["d11"].angle), ((4,), (11,), "P04", "P04")
        )

    def test_each_job_quotes_its_format_and_holds_each_day_s_frozen_hook(self):
        job = self.found.job_for(2)
        self.assertEqual(job.format, "20s founder-on-camera line, then a screen record of the app opening")
        self.assertEqual(job.line, self.kit.angles["P02"].line)
        self.assertEqual([shot.id for shot in job.shots], ["d02-s1", "d02-s2"])
        self.assertEqual(
            [(hook.day, hook.leg, hook.text, hook.source) for hook in job.hooks],
            [
                (2, "A", "I open my own app and the session is already there.", "pairs"),
                (9, "B", "The session is already there when I open my own app.", "pairs"),
            ],
        )
        self.assertTrue(job.shots[1].uncut and job.shots[1].real_time)

    def test_a_day_whose_angle_the_calendar_decides_later_is_left_out_with_the_reason(self):
        self.assertEqual([number for number, _ in self.found.unplanned], [14])
        self.assertIn("the calendar decides its Angle later", self.found.unplanned[0][1])

    def test_a_format_no_shot_can_be_read_from_and_an_unknown_angle_are_left_out_too(self):
        angles = dict(self.kit.angles, P04=replace(self.kit.angles["P04"], format="a carousel of three cards"))
        del angles["P06"]
        found = shots.requirements(replace(self.kit, angles=angles))
        reasons = dict(found.unplanned)
        self.assertIn("Format names no recording the plan can read ('a carousel of three cards')", reasons[4])
        self.assertEqual(reasons[6], "Angle P06 is not in the Angle bank")
        self.assertEqual(sorted(reasons), [4, 6, 11, 12, 14])

    def test_the_fewest_sittings_are_one_per_setup_the_shot_lists_state(self):
        groups = shots.sittings(self.found)
        self.assertEqual(
            [(group.number, group.setup) for group in groups], [(1, "device"), (2, "camera"), (3, "not stated")]
        )
        self.assertEqual([shot.id for _, shot in groups[0].shots], ["d01-s1", "d02-s2", "d03-s1", "d04-s1", "d11-s1"])
        self.assertEqual([shot.id for _, shot in groups[1].shots], ["d02-s1", "d06-s1", "d07-s1", "d12-s1", "d13-s1"])
        self.assertEqual(groups[1].label, "On camera")
        self.assertEqual(groups[0].days(), [1, 2, 3, 4, 8, 9, 10, 11])
        # Every shot is in exactly one sitting, and no two sittings share a setup: no grouping has fewer.
        placed = [shot.id for group in groups for _, shot in group.shots]
        self.assertEqual(sorted(placed), sorted(shot.id for _, shot in self.found.shots()))
        self.assertEqual(len(groups), len({shot.setup for _, shot in self.found.shots()}))

    def test_a_window_whose_shots_share_one_setup_is_one_sitting(self):
        days = {number: day for number, day in self.kit.days.items() if number in (1, 3, 4, 8, 10, 11)}
        found = shots.requirements(replace(self.kit, days=days))
        groups = shots.sittings(found)
        self.assertEqual([(group.setup, len(group.shots)) for group in groups], [("device", 4)])

    def test_the_fingerprint_changes_only_when_the_kit_changes_what_must_be_filmed(self):
        before = self.found.fingerprint()
        self.assertEqual(shots.requirements(self.kit, self.roles["calendar"]).fingerprint(), before)
        # A changed signal, or the Hook of a screen recording, which is drawn in the edit, changes no filming.
        angles = dict(self.kit.angles, P01=replace(self.kit.angles["P01"], signal="Another signal"))
        pair = self.kit.pairs["AB-1"]
        legs = dict(pair.legs, B=replace(pair.legs["B"], hook="Another hook drawn over the same screen record."))
        same = replace(self.kit, angles=angles, pairs=dict(self.kit.pairs, **{"AB-1": replace(pair, legs=legs)}))
        self.assertEqual(shots.requirements(same, self.roles["calendar"]).fingerprint(), before)
        # A changed Format, a Hook the Founder says on camera, and a day that joins the calendar each change it.
        changed = dict(self.kit.angles, P01=replace(self.kit.angles["P01"], format="12s screen record, no cuts"))
        self.assertNotEqual(shots.requirements(replace(self.kit, angles=changed)).fingerprint(), before)
        spoken = self.kit.pairs["AB-3"]
        said = dict(spoken.legs, B=replace(spoken.legs["B"], hook="Another line said on camera."))
        other = replace(self.kit, pairs=dict(self.kit.pairs, **{"AB-3": replace(spoken, legs=said)}))
        digests = shots.requirements(other, self.roles["calendar"]).digests()
        self.assertNotEqual(digests["d02"], self.found.digests()["d02"])
        self.assertEqual(digests["d01"], self.found.digests()["d01"])
        fewer = {number: day for number, day in self.kit.days.items() if number != 13}
        self.assertNotEqual(
            shots.requirements(replace(self.kit, days=fewer), self.roles["calendar"]).fingerprint(), before
        )

    def test_the_screen_rule_is_read_from_the_calendar_s_own_checklist(self):
        rule = shots.screen_rule(self.kit.asset_checks)
        self.assertEqual((rule.real_device, rule.real_time, rule.cuts_declared_only), (True, True, True))
        self.assertIsNone(shots.screen_rule((kit.AssetCheck(3, "Founder is on camera for every first-person line."),)))


if __name__ == "__main__":
    unittest.main()
