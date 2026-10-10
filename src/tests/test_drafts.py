"""A post Draft's format, and every deterministic check one Draft must pass before it is offered."""

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from gr0wthlab import drafts
from tests import fakes


def rules_of(verdict):
    return sorted({finding.rule for finding in verdict.blocks})


class DraftTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(self.tmp.name))
        env = fakes.git_env(root)
        self.context = fakes.kit_context(fakes.make_code(root / "RepToday", env), env)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, text, reference=None):
        return drafts.evaluate(drafts.parse(text, "drafts/posts/window-1/day.md"), self.context, reference)


class FormatTest(DraftTestCase):
    def test_a_clean_draft_parses_into_its_parts(self):
        draft = drafts.parse(fakes.draft(3), "day-03.md")
        self.assertEqual(draft.problems, [])
        self.assertEqual((draft.day, draft.fields["angle"], draft.fields["leg"]), (3, "P03", "A"))
        self.assertEqual([beat.number for beat in draft.beats], [1, 2, 3])
        self.assertTrue(draft.beats[0].hook)
        self.assertEqual(sorted(draft.platforms), ["TikTok", "YouTube Shorts"])
        self.assertEqual(draft.claims[0].location, "Engine/ConsistencyScore.swift:6-7")
        self.assertEqual(draft.claims[0].excerpt, "value = max(floorValue, value - missPenalty)")
        self.assertEqual(len(draft.sha256), 64)

    def test_each_format_problem_is_named_and_blocks_the_draft(self):
        clean = fakes.draft(3)
        cases = {
            clean.replace("draft: post\n", ""): "front matter needs draft: post",
            clean.replace("window: 1\n", "window: one\n"): "window must be a whole number",
            clean.replace("day: 3\n", "day: \u00b3\n"): "day must be a whole number",
            clean.replace("leg: A\n", ""): "a pair leg names both pair and leg",
            clean.replace("### Beat 1 (hook): 0-3s", "### Beat 1: 0-3s"): "beat 1 is the hook beat",
            clean.replace("### Beat 2: 3-9s", "### Beat 2: 1-9s"): "beat 2's time must follow beat 1's",
            clean.replace("### Beat 3: 9-12s", "### Beat 4: 9-12s"): "beats are numbered 1, 2, 3",
            clean.replace(
                "- Spoken line: none\n- On-screen text: Real phone", "- On-screen text: Real phone"
            ): "beat 3 needs - Spoken line:",
            clean.replace("  Shows: `value", "  Proves: `value"): "each claim is - Claim:",
            clean.replace("## Hook\n\n", "## Hook\n\nTwo\n"): "## Hook holds the Hook on one line",
            "No front matter.": "the Draft must start with front matter",
        }
        for text, problem in cases.items():
            with self.subTest(problem=problem):
                verdict = self.check(text)
                self.assertFalse(verdict.passed)
                self.assertTrue(any(problem in finding.detail for finding in verdict.blocks), verdict.blocks)


class EvaluateTest(DraftTestCase):
    def test_a_clean_draft_passes_and_shows_its_checklist_status(self):
        verdict = self.check(fakes.draft(3))
        self.assertEqual(verdict.blocks, [])
        statuses = {line.item.line: line.status for line in verdict.checklist}
        self.assertEqual(statuses, {7: drafts.DONE, 8: drafts.OPEN, 12: drafts.OPEN, 16: drafts.OPEN})
        self.assertEqual(verdict.hook.text, "Skip a day and the score dips. It never resets.")
        self.assertEqual(verdict.angle.id, "P03")
        self.assertIsNone(verdict.claims[0].problem)

    def test_a_draft_must_be_the_calendar_s_day(self):
        wrong_angle = fakes.draft(3).replace("angle: P03", "angle: P04")
        self.assertIn("calendar", rules_of(self.check(wrong_angle)))
        wrong_window = fakes.draft(3).replace("window: 1", "window: 2")
        self.assertIn("calendar", rules_of(self.check(wrong_window)))
        no_day = fakes.draft(3).replace("day: 3", "day: 40")
        self.assertEqual(rules_of(self.check(no_day)), ["calendar"])

    def test_another_leg_s_hook_never_appears_in_a_caption(self):
        text = fakes.draft(3, caption="A skipped day never takes you back to zero.")
        verdict = self.check(text)
        self.assertEqual(rules_of(verdict), ["hook-isolation"])
        self.assertIn("another leg of this Angle", verdict.blocks[0].detail)

    def test_both_platforms_carry_identical_content(self):
        clean = fakes.draft(3)
        tiktok, youtube = clean.split("## YouTube Shorts")
        youtube = youtube.replace("Built by one person. Not released yet.", "Not released yet.", 1)
        self.assertEqual(rules_of(self.check(tiktok + "## YouTube Shorts" + youtube)), ["identical-content"])
        missing = clean.split("## YouTube Shorts")[0] + "## Claims" + clean.split("## Claims")[1]
        self.assertIn("platforms", rules_of(self.check(missing)))

    def test_a_leg_matches_its_reference_leg_in_every_field_beyond_the_hook(self):
        reference = drafts.parse(fakes.draft(1), "day-01.md")
        clean = fakes.draft(8)
        self.assertTrue(self.check(clean, reference).passed)
        recut = clean.replace("The history view with yesterday unmarked", "A cold open on the home screen")
        self.assertTrue(self.check(recut, reference).passed)  # the hook beat is the Hook's own
        cases = (
            (
                "This is the history view after three missed days this month.",
                "A different second line.",
                ("TikTok caption", "YouTube Shorts description"),
            ),
            ("#buildinpublic", "#fitness", ("TikTok hashtags", "YouTube Shorts hashtags")),
            (
                "Screen recording of a workout app's history view",
                "A recording of the history view",
                ("TikTok alt text", "YouTube Shorts alt text"),
            ),
            ("Three gaps this month. Still climbing.", "Three gaps. Still climbing.", ("beat 2 on-screen text",)),
            (
                "- Spoken line: none\n- On-screen text: Real phone",
                "- Spoken line: Start here.\n- On-screen text: Real phone",
                ("beat 3 spoken line",),
            ),
            ("Open today's session and tap Start.", "Open today's session.", ("beat 3 visual action",)),
        )
        for old, new, fields in cases:
            with self.subTest(fields=fields):
                verdict = self.check(clean.replace(old, new), reference)
                self.assertEqual(rules_of(verdict), ["pair-legs"])
                self.assertEqual(tuple(finding.field for finding in verdict.blocks), fields)
        shorter = clean.split("### Beat 3")[0] + "## TikTok" + clean.split("## TikTok")[1]
        self.assertEqual(
            [finding.field for finding in self.check(shorter, reference).blocks],
            ["beat 3 visual action", "beat 3 spoken line", "beat 3 on-screen text"],
        )

    def test_no_field_names_a_competitor_and_a_visual_action_is_a_field(self):
        shown = fakes.draft(3).replace("Open today's session and tap Start.", "IronFit's history view, then ours.")
        verdict = self.check(shown)
        self.assertEqual(rules_of(verdict), ["competitor-name"])
        self.assertEqual([finding.field for finding in verdict.blocks], ["beat 3 visual action"])
        tagged = fakes.draft(3).replace("#buildinpublic", "#ironfit")
        self.assertEqual(rules_of(self.check(tagged)), ["competitor-name"])

    def test_the_hook_beat_s_channels_should_not_repeat_each_other(self):
        text = fakes.draft(2).replace(
            "- Spoken line: none\n- On-screen text: I missed five days",
            "- Spoken line: I missed five days and the app welcomed me back.\n- On-screen text: I missed five days",
            1,
        )
        verdict = self.check(text)
        self.assertTrue(verdict.passed, verdict.blocks)
        self.assertIn("hook-channels", [finding.rule for finding in verdict.warnings])

    def test_a_draft_with_no_claim_is_blocked(self):
        text = fakes.draft(3).split("## Claims")[0] + "## Claims\n"
        self.assertEqual(rules_of(self.check(text)), ["claims"])

    def test_a_kit_rules_or_code_problem_blocks_every_draft(self):
        self.context.kit.problems["calendar"] = "Permission denied"
        self.assertIn("kit", rules_of(self.check(fakes.draft(3))))
        self.context.kit.problems.clear()
        self.context.rules, self.context.rules_problem = None, "not JSON"
        self.assertIn("brand-rules.json", rules_of(self.check(fakes.draft(3))))

    def test_a_named_claim_matches_any_spelling_of_its_number_and_unit(self):
        pattern = drafts.claim_pattern("under 100 milliseconds")
        for text in ("in under 100 ms", "<100ms", "an under-100ms build", "100 milliseconds", "100 msec"):
            with self.subTest(text=text):
                self.assertTrue(pattern.search(text))
        for text in ("1000 ms", "100 minutes", "10.100 ms"):
            with self.subTest(text=text):
                self.assertFalse(pattern.search(text))
        self.assertTrue(drafts.claim_pattern("works offline").search("It works   offline."))

    def test_an_open_line_that_gates_every_post_blocks_it(self):
        item = next(item for item in self.context.kit.checklist if item.line == 7)
        self.context.kit.checklist = tuple(
            replace(entry, checked=False) if entry is item else entry for entry in self.context.kit.checklist
        )
        verdict = self.check(fakes.draft(3))
        self.assertEqual(rules_of(verdict), ["projects/RepToday/gtm/08-redteam/pre-publication-checklist.md line 7"])


if __name__ == "__main__":
    unittest.main()
