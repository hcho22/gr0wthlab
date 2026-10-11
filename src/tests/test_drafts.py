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
        self.root = Path(os.path.realpath(self.tmp.name))
        self.env = fakes.git_env(self.root)
        self.code = fakes.make_code(self.root / "RepToday", self.env)
        self.context = fakes.kit_context(self.code, self.env)

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
            ("### Beat 3: 9-12s", "### Beat 3: 9-58s", ("beat 3 time",)),
            ("### Beat 2: 3-9s", "### Beat 2: 4-9s", ("beat 2 time",)),
            ("### Beat 1 (hook): 0-3s", "### Beat 1 (hook): 0-2s", ("beat 1 time",)),
        )
        for old, new, fields in cases:
            with self.subTest(fields=fields):
                verdict = self.check(clean.replace(old, new), reference)
                self.assertEqual(rules_of(verdict), ["pair-legs"])
                self.assertEqual(tuple(finding.field for finding in verdict.blocks), fields)
        quicker = clean.replace("### Beat 2: 3-9s", "### Beat 2: 3-5s").replace("### Beat 3: 9-12s", "### Beat 3: 5-6s")
        self.assertEqual(
            [finding.field for finding in self.check(quicker, reference).blocks], ["beat 2 time", "beat 3 time"]
        )
        shorter = clean.split("### Beat 3")[0] + "## TikTok" + clean.split("## TikTok")[1]
        self.assertEqual(
            [finding.field for finding in self.check(shorter, reference).blocks],
            ["beat 3 time", "beat 3 visual action", "beat 3 spoken line", "beat 3 on-screen text"],
        )

    def test_a_leg_s_hook_beat_runs_as_long_as_its_reference_leg_s(self):
        def hook_beat_only(text):
            return text.split("### Beat 2")[0] + "## TikTok" + text.split("## TikTok")[1]

        reference = drafts.parse(hook_beat_only(fakes.draft(1)), "day-01.md")
        leg = hook_beat_only(fakes.draft(8))
        self.assertEqual(self.check(leg, reference).blocks, [])
        longer = self.check(leg.replace("### Beat 1 (hook): 0-3s", "### Beat 1 (hook): 0-58s"), reference)
        self.assertEqual([(finding.rule, finding.field) for finding in longer.blocks], [("pair-legs", "beat 1 time")])

    def test_a_re_cut_pair_s_legs_may_cut_their_opening_differently_and_match_beat_by_beat_after_it(self):
        hook_a, hook_b = fakes.KIT_DAYS[1][3], fakes.KIT_DAYS[8][3]
        body = ("Open today's session and tap Start.", "Real phone, real time.")
        close = ("Lock the phone.", "Done for today.")
        leg_a = fakes.with_beats(fakes.draft(1), ("Hold on the session list.", hook_b), body, close)
        leg_b = fakes.with_beats(fakes.draft(8), ("The home screen, then one tap.", hook_a), body, close)
        moved = fakes.with_beats(fakes.draft(8), body, ("The home screen, then one tap.", hook_a), close)
        sooner = fakes.with_beats(fakes.draft(8), body, close)
        shuffled = fakes.with_beats(fakes.draft(8), ("The home screen, then one tap.", hook_a), close, body)
        retimed = leg_b.replace("### Beat 4: 9-12s", "### Beat 4: 9-58s")
        changed = fakes.with_beats(
            fakes.draft(8), ("The home screen.", hook_a), ("Open today's session.", body[1]), close
        )
        # In an ordinary pair no beat shows the other leg's Hook, so neither check lets the opening move.
        self.assertEqual(rules_of(self.check(leg_a)), ["hook-isolation"])
        self.context = fakes.kit_context(self.code, self.env, fakes.recut_mandu(self.root / "Mandu"))
        reference = drafts.parse(leg_a, "day-01.md")
        self.assertEqual(self.check(leg_a).blocks, [])
        for name, leg in (
            ("the same opening order", leg_b),
            ("the other Hook later", moved),
            ("no other Hook", sooner),
        ):
            with self.subTest(name):
                self.assertEqual(self.check(leg, reference).blocks, [])
        for name, leg in (("shuffled", shuffled), ("re-timed", retimed), ("reworded", changed)):
            with self.subTest(name):
                self.assertEqual(
                    [(finding.rule, finding.field) for finding in self.check(leg, reference).blocks],
                    [("pair-legs", "beats after the re-cut opening")],
                )
        recaptioned = fakes.with_beats(fakes.draft(8, caption="Another second line."), ("A tap.", hook_a), body, close)
        self.assertEqual(
            [finding.field for finding in self.check(recaptioned, reference).blocks],
            ["TikTok caption", "YouTube Shorts description"],
        )

    def test_no_field_names_a_competitor_and_a_visual_action_is_a_field(self):
        shown = fakes.draft(3).replace("Open today's session and tap Start.", "IronFit's history view, then ours.")
        verdict = self.check(shown)
        self.assertEqual(rules_of(verdict), ["competitor-name"])
        self.assertEqual([finding.field for finding in verdict.blocks], ["beat 3 visual action"])
        tagged = fakes.draft(3).replace("#buildinpublic", "#ironfit")
        self.assertEqual(rules_of(self.check(tagged)), ["competitor-name"])

    def test_a_hook_the_kit_has_spoken_on_camera_passes_with_no_warning(self):
        text = fakes.draft(2).replace(
            "- Spoken line: none\n- On-screen text: I missed five days",
            "- Spoken line: I missed five days and the app welcomed me back.\n- On-screen text: I missed five days",
            1,
        )
        verdict = self.check(text)
        self.assertEqual((verdict.blocks, verdict.warnings), ([], []))

    def test_a_draft_with_no_claim_is_blocked(self):
        text = fakes.draft(3).split("## Claims")[0] + "## Claims\n"
        self.assertEqual(rules_of(self.check(text)), ["claims"])

    def test_a_claim_s_excerpt_may_quote_more_than_one_line_of_the_code_and_is_checked_whole(self):
        second = "value = max(floorValue, value - missPenalty)"
        text = fakes.draft(3).replace(
            f"  Shows: `{second}`",
            f"  Shows: `// A missed day lowers the score; nothing resets it to zero.\n  {second}`",
        )
        verdict = self.check(text)
        self.assertEqual(verdict.blocks, [])
        excerpt = verdict.claims[0].claim.excerpt
        self.assertEqual(excerpt, f"// A missed day lowers the score; nothing resets it to zero. {second}")
        wrong = self.check(text.replace("missPenalty", "hitPenalty"))
        self.assertEqual(rules_of(wrong), ["claim-location"])
        self.assertIn(f"do not contain {excerpt.replace('missPenalty', 'hitPenalty')!r}", wrong.blocks[0].detail)

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

    def test_a_named_claim_the_video_shows_in_a_visual_action_is_carried_by_the_draft(self):
        shown = fakes.draft(1).replace(
            "Open today's session and tap Start.", "A timer overlay shows the session built in under 100 ms."
        )
        verdict = self.check(shown)
        self.assertEqual(
            [(finding.rule, finding.detail) for finding in verdict.blocks],
            [
                (
                    "projects/RepToday/gtm/08-redteam/pre-publication-checklist.md line 12",
                    'Device benchmark record for the "under 100 milliseconds" claim: the Draft carries the'
                    " 'under 100 milliseconds' claim",
                )
            ],
        )

    def test_only_the_hashtags_of_a_platform_may_be_none(self):
        clean = fakes.draft(3)
        self.assertEqual(self.check(clean.replace("#buildinpublic", "none")).blocks, [])
        alt = "Screen recording of a workout app's history view: each missed day lowers a consistency score a little,"
        alt += " and the score climbs again after every gap."
        verdict = self.check(clean.replace(alt, "none"))
        self.assertEqual(
            [(finding.rule, finding.detail) for finding in verdict.blocks],
            [
                ("format", f"## {platform} ### Alt text is empty; only the hashtags may be none")
                for platform in ("TikTok", "YouTube Shorts")
            ],
        )
        empty = self.check(clean.replace("#buildinpublic\n", "\n"))
        self.assertEqual(
            [finding.detail for finding in empty.blocks],
            [
                f"## {platform} ### Hashtags is empty; only the hashtags may be none"
                for platform in ("TikTok", "YouTube Shorts")
            ],
        )

    def test_an_open_line_that_gates_every_post_blocks_it(self):
        item = next(item for item in self.context.kit.checklist if item.line == 7)
        self.context.kit.checklist = tuple(
            replace(entry, checked=False) if entry is item else entry for entry in self.context.kit.checklist
        )
        verdict = self.check(fakes.draft(3))
        self.assertEqual(rules_of(verdict), ["projects/RepToday/gtm/08-redteam/pre-publication-checklist.md line 7"])


if __name__ == "__main__":
    unittest.main()
