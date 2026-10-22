"""A post Draft's format, and every deterministic check one Draft must pass before it is offered."""

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from gr0wthlab import drafts, lint
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

    def test_a_claim_listed_with_no_code_blocks_the_draft_naming_it_whatever_else_the_code_supports(self):
        text = fakes.draft(2) + "- Claim: After missed days, the app welcomes you back.\n  Code: none\n  Shows: none\n"
        verdict = self.check(text)
        self.assertEqual(
            [finding.line() for finding in verdict.blocks],
            ["claim-unsupported: 'After missed days, the app welcomes you back.': no code supports it"],
        )
        self.assertEqual([result.problem for result in verdict.claims], [None, "no code supports it"])

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

    def test_a_visual_action_is_a_filming_note_read_only_for_social_proof_and_another_hook(self):
        clean, action = fakes.draft(3), "Open today's session and tap Start."
        notes = (
            "The score reads 87%.",
            "Timelapse of the timer at 4x.",
            "Is the START button really just simply there? Hold on it.",
        )
        for note in notes:
            with self.subTest(note):
                verdict = self.check(clean.replace(action, note))
                self.assertEqual((verdict.blocks, verdict.warnings), ([], []))
                as_copy = self.check(clean.replace("Real phone, real time.", note))
                self.assertTrue({"beat 3 on-screen text"} <= {finding.field for finding in as_copy.blocks})
        proof = self.check(clean.replace(action, "A five-star rated badge fills the screen."))
        self.assertEqual(
            [(finding.rule, finding.field, finding.detail) for finding in proof.blocks],
            [("banned_social_proof_in_hook", "beat 3 visual action", "social proof 'rated'")],
        )
        other = fakes.KIT_DAYS[4][3]
        borrowed = self.check(clean.replace(action, f"A title card reads: {other}"))
        self.assertEqual(
            [(finding.rule, finding.field, finding.detail) for finding in borrowed.blocks],
            [("hook-isolation", "beat 3 visual action", f"carries the Hook of Angle P04: {other!r}")],
        )

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


class FrozenHookExemptionTest(DraftTestCase):
    """Day 3's frozen Hook, "Skip a day and the score dips. It never resets.", against brand rules that cap a Hook
    at 5 words and ban a word it holds."""

    def strict(self, banned, exempt=None):
        data = dict(self.context.rules.data, hook_max_words=5)
        data["banned_words_in_hook"] = [*data["banned_words_in_hook"], banned]
        if exempt is not None:
            data["frozen_hooks_exempt_from"] = exempt
        self.context.rules = lint.Rules(data)

    def test_without_the_key_the_frozen_hook_is_blocked_as_before(self):
        self.strict("resets")
        verdict = self.check(fakes.draft(3))
        self.assertEqual(rules_of(verdict), ["banned_words_in_hook", "hook_max_words"])
        self.assertEqual(verdict.exempt, [])

    def test_with_the_key_the_frozen_hook_passes_and_the_verdict_says_where_the_exemption_applied(self):
        self.strict("resets", ["hook_max_words", "banned_words_in_hook"])
        verdict = self.check(fakes.draft(3))
        self.assertEqual(verdict.blocks, [])
        self.assertEqual(
            [(finding.rule, finding.field) for finding in verdict.exempt],
            [
                ("hook_max_words", "Hook"),
                ("banned_words_in_hook", "Hook"),
                ("banned_words_in_hook", "beat 1 on-screen text"),
                ("banned_words_in_hook", "TikTok caption"),
                ("banned_words_in_hook", "YouTube Shorts title"),
                ("banned_words_in_hook", "YouTube Shorts description"),
            ],
        )

    def test_a_banned_word_outside_the_frozen_hook_still_blocks(self):
        # "score" is in the frozen Hook and also in the alt text, which is not the Hook's words.
        self.strict("score", ["hook_max_words", "banned_words_in_hook"])
        verdict = self.check(fakes.draft(3))
        self.assertEqual(
            sorted((finding.rule, finding.field) for finding in verdict.blocks),
            [("banned_words_in_hook", "TikTok alt text"), ("banned_words_in_hook", "YouTube Shorts alt text")],
        )

    def test_a_hook_that_is_not_the_frozen_text_is_held_to_both_rules(self):
        self.strict("resets", ["hook_max_words", "banned_words_in_hook"])
        edited = "Skip a day and the score dips, but it never resets."
        text = fakes.draft(3).replace(
            "## Hook\n\nSkip a day and the score dips. It never resets.", f"## Hook\n\n{edited}"
        )
        verdict = self.check(text)
        self.assertIn("frozen-hook", rules_of(verdict))
        held = [finding for finding in verdict.blocks if finding.rule in lint.FROZEN_EXEMPTABLE]
        self.assertEqual(
            sorted((finding.rule, finding.field) for finding in held),
            [("banned_words_in_hook", "Hook"), ("hook_max_words", "Hook")],
        )


class RecutPairFrozenHookExemptionTest(DraftTestCase):
    """AB-1, days 1 and 8, whose leg A Hook has two sentences and a word the brand rules ban, under brand rules that
    exempt frozen Hooks: a re-cut leg may show its pair's other Hook after its hook beat, and nothing else is exempt."""

    HOOK_A = "Open it and the session is already waiting. Nothing to set up."
    FIRST = "Open it and the session is already waiting."
    CLOSE = ("Lock the phone.", "Done for today.")

    def use(self, mandu):
        for path in (mandu / "projects/RepToday/gtm/05-social-pmf").iterdir():
            path.write_text(path.read_text(encoding="utf-8").replace(fakes.KIT_DAYS[1][3], self.HOOK_A), "utf-8")
        self.context = fakes.kit_context(self.code, self.env, mandu)
        data = dict(self.context.rules.data, frozen_hooks_exempt_from=["hook_max_words", "banned_words_in_hook"])
        data["banned_words_in_hook"] = [*data["banned_words_in_hook"], "waiting"]
        self.context.rules = lint.Rules(data)

    def setUp(self):
        super().setUp()
        self.use(fakes.recut_mandu(self.root / "Mandu"))

    def leg_b(self, *later, caption="This is the history view after three missed days this month."):
        return fakes.with_beats(fakes.draft(8, caption), ("The home screen, then one tap.", self.HOOK_A), *later)

    def blocking(self, verdict):
        return sorted((finding.rule, finding.field) for finding in verdict.blocks)

    def test_a_re_cut_leg_shows_its_pair_s_other_hook_or_one_of_its_sentences_after_its_hook_beat(self):
        for shown in (self.HOOK_A, self.FIRST):
            with self.subTest(shown=shown):
                verdict = self.check(self.leg_b(("A tap.", shown), self.CLOSE))
                self.assertEqual(verdict.blocks, [])
                self.assertEqual(
                    [(finding.rule, finding.field) for finding in verdict.exempt],
                    [
                        ("banned_words_in_hook", "beat 2 on-screen text"),
                        ("banned_words_in_hook", "beat 3 on-screen text"),
                    ],
                )

    def test_any_other_text_with_the_banned_word_still_blocks_a_re_cut_leg(self):
        verdict = self.check(self.leg_b(("A tap.", "Nothing is waiting for you."), self.CLOSE))
        self.assertEqual(self.blocking(verdict), [("banned_words_in_hook", "beat 3 on-screen text")])
        captioned = self.check(self.leg_b(self.CLOSE, caption=self.FIRST))
        self.assertEqual(
            self.blocking(captioned),
            [("banned_words_in_hook", "TikTok caption"), ("banned_words_in_hook", "YouTube Shorts description")],
        )

    def test_in_an_ordinary_pair_the_other_leg_s_hook_is_not_exempt(self):
        self.use(fakes.make_mandu(self.root / "Ordinary"))
        verdict = self.check(fakes.with_beats(fakes.draft(8), ("A tap.", self.FIRST), self.CLOSE))
        self.assertEqual(self.blocking(verdict), [("banned_words_in_hook", "beat 2 on-screen text")])

    def test_an_approved_leg_this_leg_must_match_is_read_with_its_own_exemption(self):
        hook_b = fakes.KIT_DAYS[8][3]
        for shown, blocks in (
            (self.FIRST, []),
            ("Nothing is waiting for you.", [("banned_words_in_hook", "beat 3 on-screen text"), ("pair-legs", "")]),
        ):
            with self.subTest(shown=shown):
                later = (("A tap.", shown), self.CLOSE)
                leg_a = fakes.with_beats(
                    fakes.draft(1).replace(fakes.KIT_DAYS[1][3], self.HOOK_A),
                    ("Hold on the session list.", hook_b),
                    *later,
                )
                reference = drafts.parse(leg_a, "day-01.md")
                self.assertEqual(self.blocking(self.check(leg_a)), blocks[:1])
                verdict = drafts.evaluate(
                    drafts.parse(self.leg_b(*later), "day-08.md"), self.context, reference, reference_approved=True
                )
                self.assertEqual(self.blocking(verdict), blocks)


class CallToActionTest(DraftTestCase):
    """The synthetic brand rules give the line "Join the waitlist: {link}", with TikTok's link reptoday.app/tiktok and
    YouTube Shorts' reptoday.app/youtube, each naming one of the Product registry's Waitlist Source tags."""

    TIKTOK = "Join the waitlist: reptoday.app/tiktok"
    YOUTUBE = "Join the waitlist: reptoday.app/youtube"

    def blocking(self, verdict):
        return [(finding.rule, finding.field) for finding in verdict.blocks]

    def caption(self, text, old, new, platform="TikTok"):
        """The Draft with one platform's caption line old replaced by new, the other platform untouched."""
        tiktok, youtube = text.split("## YouTube Shorts")
        if platform == "TikTok":
            return tiktok.replace(old, new, 1) + "## YouTube Shorts" + youtube
        return tiktok + "## YouTube Shorts" + youtube.replace(old, new, 1)

    def test_each_caption_ends_with_its_platform_s_line_and_the_draft_passes(self):
        self.assertEqual(
            drafts.call_to_action_lines(self.context),
            ({"TikTok": self.TIKTOK, "YouTube Shorts": self.YOUTUBE}, []),
        )
        self.assertEqual(self.context.source_tags, ("tiktok", "youtube", "reddit", "network"))
        clean = fakes.draft(3)
        self.assertTrue(clean.count(self.TIKTOK) == clean.count(self.YOUTUBE) == 1)
        self.assertTrue(self.check(clean).passed)

    def test_a_caption_without_its_line_is_held_back_naming_the_line(self):
        bare = fakes.draft(3).replace(self.TIKTOK + "\n", "").replace(self.YOUTUBE + "\n", "")
        verdict = self.check(bare)
        self.assertEqual(
            self.blocking(verdict),
            [("call-to-action", "TikTok caption"), ("call-to-action", "YouTube Shorts description")],
        )
        self.assertEqual(
            [finding.detail for finding in verdict.blocks],
            [
                f"does not end with its call-to-action line; the last line of every TikTok post is `{self.TIKTOK}`",
                "does not end with its call-to-action line; the last line of every YouTube Shorts post is"
                f" `{self.YOUTUBE}`",
            ],
        )
        one = self.check(self.caption(fakes.draft(3), self.TIKTOK + "\n", ""))
        self.assertIn(("call-to-action", "TikTok caption"), self.blocking(one))

    def test_other_wording_is_held_back(self):
        for wording in (
            "Join the beta: reptoday.app/tiktok",
            "join the waitlist: reptoday.app/tiktok",
            "Join the waitlist at reptoday.app/tiktok",
            "Join the waitlist: https://reptoday.app/tiktok",
            "Join the waitlist: reptoday.app",
            "Join the waitlist.",
        ):
            with self.subTest(wording=wording):
                verdict = self.check(self.caption(fakes.draft(3), self.TIKTOK, wording))
                self.assertEqual(self.blocking(verdict), [("call-to-action", "TikTok caption")])
                self.assertIn(f"ends with {wording!r}, not the line brand-rules.json", verdict.blocks[0].detail)

    def test_another_channel_s_address_is_held_back_naming_its_source(self):
        cases = (
            ("TikTok", self.TIKTOK, self.YOUTUBE, "youtube", "TikTok caption"),
            ("YouTube Shorts", self.YOUTUBE, self.TIKTOK, "tiktok", "YouTube Shorts description"),
            ("TikTok", self.TIKTOK, "Join the waitlist: reptoday.app/reddit", "reddit", "TikTok caption"),
        )
        for platform, line, wrong, tag, field in cases:
            with self.subTest(platform=platform, wrong=wrong):
                verdict = self.check(self.caption(fakes.draft(3), line, wrong, platform))
                self.assertEqual(self.blocking(verdict), [("call-to-action", field)])
                self.assertTrue(verdict.blocks[0].detail.startswith(f"ends with the Source link for `{tag}`"))

    def test_a_second_call_to_action_or_link_in_a_caption_is_held_back(self):
        clean = fakes.draft(3)
        for extra, found in (
            (self.TIKTOK, "'reptoday.app/tiktok' and 'Join the waitlist'"),
            ("Sign up at reptoday.app/tiktok.", "'reptoday.app/tiktok'"),
            ("More at https://example.com/rep", "'https://example.com/rep'"),
            ("Tap [here](https://reptoday.app).", "'https://reptoday.app' and 'a Markdown link'"),
        ):
            with self.subTest(extra=extra):
                verdict = self.check(self.caption(clean, self.TIKTOK, extra + "\n" + self.TIKTOK))
                self.assertIn(("call-to-action", "TikTok caption"), self.blocking(verdict))
                details = [finding.detail for finding in verdict.blocks if finding.rule == "call-to-action"]
                self.assertTrue(details[0].startswith(f"carries {found} before its last line"), details)

    def test_the_line_anywhere_but_the_end_of_a_caption_is_held_back(self):
        clean = fakes.draft(3)
        cases = (
            (
                "- On-screen text: Three gaps this month. Still climbing.",
                f"- On-screen text: {self.TIKTOK}",
                "beat 2 on-screen text",
            ),
            (
                "- Spoken line: none\n- On-screen text: Real phone",
                "- Spoken line: Join the waitlist.\n- On-screen text: Real phone",
                "beat 3 spoken line",
            ),
            ("Open today's session and tap Start.", "End card shows reptoday.app/tiktok.", "beat 3 visual action"),
            ("#buildinpublic\n\n### Alt text", "#jointhewaitlist\n\n### Alt text", "TikTok hashtags"),
            ("each missed day lowers", "the reptoday.app/tiktok page; each missed day lowers", "TikTok alt text"),
        )
        for old, new, field in cases:
            with self.subTest(field=field):
                verdict = self.check(clean.replace(old, new, 1))
                self.assertIn(("call-to-action", field), self.blocking(verdict))
                detail = next(finding.detail for finding in verdict.blocks if finding.field == field)
                self.assertIn("go only at the end of each caption, never in the Hook, the video", detail)
        title = clean.replace(
            "### Title\n\nSkip a day and the score dips. It never resets.",
            f"### Title\n\nSkip a day and the score dips. It never resets. {self.YOUTUBE}",
        )
        self.assertIn(("call-to-action", "YouTube Shorts title"), self.blocking(self.check(title)))

    def test_the_platforms_captions_may_differ_only_in_the_line_s_link(self):
        clean = fakes.draft(3)
        self.assertNotIn("identical-content", rules_of(self.check(clean)))
        changed = self.caption(clean, "Built by one person.", "Built by one developer.", "YouTube Shorts")
        verdict = self.check(changed)
        self.assertEqual(rules_of(verdict), ["identical-content"])
        self.assertTrue(verdict.blocks[0].detail.endswith("apart from each caption's call-to-action line"))

    def test_both_legs_of_a_pair_carry_the_same_line(self):
        reference = drafts.parse(fakes.draft(1), "day-01.md")
        self.assertTrue(self.check(fakes.draft(8), reference).passed)
        missing = drafts.parse(self.caption(fakes.draft(1), self.TIKTOK + "\n", ""), "day-01.md")
        verdict = self.check(fakes.draft(8), missing)
        self.assertEqual(self.blocking(verdict), [("pair-legs", "TikTok caption")])

    def test_a_platform_with_no_link_or_one_that_names_no_source_or_another_s_blocks_every_draft(self):
        line = self.context.rules.data["caption_call_to_action"]
        tags = "its path must be one of the Product registry's Source tags (tiktok, youtube, reddit, network)"
        cases = (
            (
                {"TikTok": "reptoday.app/tiktok"},
                "brand-rules.json caption_call_to_action gives no Waitlist link for YouTube Shorts",
            ),
            (
                {"TikTok": "reptoday.app/tiktok", "YouTube Shorts": "reptoday.app/shorts"},
                "brand-rules.json caption_call_to_action gives YouTube Shorts `reptoday.app/shorts`, which names no"
                f" Waitlist Source: {tags}",
            ),
            (
                {"TikTok": "reptoday.app/tiktok", "YouTube Shorts": "reptoday.app/"},
                "brand-rules.json caption_call_to_action gives YouTube Shorts `reptoday.app/`, which names no"
                f" Waitlist Source: {tags}",
            ),
            (
                {"TikTok": "reptoday.app/tiktok", "YouTube Shorts": "reptoday.app/TikTok"},
                "brand-rules.json caption_call_to_action gives YouTube Shorts `reptoday.app/TikTok`, which names the"
                " same Waitlist Source as TikTok, `tiktok`, so sign-ups from the two could not be told apart",
            ),
            (
                {"TikTok": "reptoday.app/tiktok", "YouTube Shorts": "www.reptoday.app/tiktok"},
                "brand-rules.json caption_call_to_action gives YouTube Shorts `www.reptoday.app/tiktok`, which names"
                " the same Waitlist Source as TikTok, `tiktok`, so sign-ups from the two could not be told apart",
            ),
            (
                {"TikTok": "reptoday.app/tiktok", "YouTube Shorts": "other.app/tiktok"},
                "brand-rules.json caption_call_to_action gives TikTok `reptoday.app/tiktok`, which names the same"
                " Waitlist Source as YouTube Shorts, `tiktok`, so sign-ups from the two could not be told apart",
            ),
        )
        for found, problem in cases:
            with self.subTest(problem=problem):
                data = dict(self.context.rules.data, caption_call_to_action=dict(line, links=found))
                context = replace(self.context, rules=lint.Rules(data))
                verdict = drafts.evaluate(drafts.parse(fakes.draft(3), "day-03.md"), context)
                self.assertIn(problem, [finding.detail for finding in verdict.blocks])
                self.assertEqual(rules_of(verdict), ["call-to-action"])

    def test_without_the_key_a_caption_carries_no_line_and_none_is_checked(self):
        data = {key: value for key, value in self.context.rules.data.items() if key != "caption_call_to_action"}
        self.context.rules = lint.Rules(data)
        self.assertEqual(drafts.call_to_action_lines(self.context), ({}, []))
        bare = fakes.draft(3).replace(self.TIKTOK + "\n", "").replace(self.YOUTUBE + "\n", "")
        self.assertTrue(self.check(bare).passed)
        # The two lines' links differ, which the identical-content check holds against them as before.
        self.assertEqual(rules_of(self.check(fakes.draft(3))), ["identical-content"])


if __name__ == "__main__":
    unittest.main()
