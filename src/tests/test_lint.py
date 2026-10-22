"""The Draft lint: brand-rules.json's rules on every field of copy, the F1 rule types, and the platform limits."""

import json
import unittest
from dataclasses import replace

from gr0wthlab import lint
from tests import fakes

KIT_RULES = fakes.EXAMPLES / "files/mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
HOOK_RULES = {
    "comment": "Hook rules only, as the dry-run lint shipped.",
    "hook_max_words": 12,
    "hook_must_not_be_question": True,
    "banned_words_in_hook": ["grind", "streak", "beast mode"],
    "banned_social_proof_in_hook": ["stars", "rated", "users love"],
    "banned_characters_anywhere": ["\u2014"],
    "no_emoji_in_hook": True,
    "no_all_caps_words_in_hook": True,
    "all_caps_allowlist": ["100"],
    "required_sections": ["Hook"],
    "required_disclosure": "Screens shown are mock-ups.",
    "pain_source_url_must_start_with": "https://",
    "notes": ["n"],
}


def full_rules():
    return lint.Rules(json.loads(KIT_RULES.read_text(encoding="utf-8")))


def rules_hit(rules, text, hook=False, field="TikTok caption"):
    return [(finding.rule, finding.blocks) for finding in rules.check([lint.Copy(field, text, hook=hook)])]


class BrandRulesTest(unittest.TestCase):
    def test_every_rule_runs_on_every_field_of_copy_not_only_the_hook(self):
        rules = lint.Rules(HOOK_RULES)
        cases = {
            "No grind here.": "banned_words_in_hook",
            "Streaks are gone.": "banned_words_in_hook",
            "Rated five stars.": "banned_social_proof_in_hook",
            "Ready? Go.": "hook_must_not_be_question",
            "Open it \u2014 go.": "banned_characters_anywhere",
            "Open it \U0001f525": "no_emoji_in_hook",
            "Open it NOW.": "no_all_caps_words_in_hook",
        }
        for text, rule in cases.items():
            with self.subTest(text=text):
                self.assertIn((rule, True), rules_hit(rules, text))

    def test_words_match_whole_words_with_plural_endings_only(self):
        rules = lint.Rules(HOOK_RULES)
        self.assertEqual(rules_hit(rules, "Generated on the phone."), [])  # "rated" inside "generated"
        self.assertEqual(rules_hit(rules, "Grinding coffee."), [])
        self.assertEqual(rules_hit(rules, "Under 100 ms, a reps count."), [])
        self.assertEqual(rules_hit(rules, "Beast   Mode on."), [("banned_words_in_hook", True)])

    def test_the_word_cap_is_about_the_hook_itself(self):
        rules = lint.Rules(HOOK_RULES)
        long = "Most workout apps open with a question. This one opens with the workout."
        self.assertEqual(rules_hit(rules, long, hook=True), [("hook_max_words", True)])
        self.assertEqual(rules_hit(rules, long), [])

    def test_statuses_name_what_applies_what_does_not_and_what_is_pending(self):
        statuses = {row.rule: row.status for row in lint.Rules(HOOK_RULES).statuses()}
        self.assertEqual(statuses["banned_words_in_hook"], lint.APPLIED)
        self.assertEqual(statuses["required_sections"], lint.NOT_APPLICABLE)
        self.assertEqual(statuses["required_disclosure"], lint.NOT_APPLICABLE)
        self.assertNotIn("comment", statuses)
        self.assertEqual(
            lint.Rules(HOOK_RULES).pending(),
            [
                "stock phrases",
                "capped words per paragraph",
                "long sentences (warning)",
                "invented proof",
                "fake scarcity",
                "allowed phrases",
                "loss framing",
            ],
        )
        self.assertEqual(full_rules().pending(), [])

    def test_a_rule_gr0wthlab_does_not_know_blocks_every_draft(self):
        rules = lint.Rules(dict(HOOK_RULES, banned_hashtags=["#ad"]))
        self.assertEqual(rules.unknown, ["banned_hashtags"])
        self.assertIn(("banned_hashtags", True), rules_hit(rules, "Fine copy."))
        self.assertEqual({row.rule: row.status for row in rules.statuses()}["banned_hashtags"], "unknown")

    def test_a_malformed_rule_makes_the_rules_unusable(self):
        for key, value in (
            ("hook_max_words", "twelve"),
            ("banned_words_in_hook", "grind"),
            ("no_emoji_in_hook", "yes"),
            ("stock_phrases", [""]),
            ("stock_phrases", ["..."]),
            ("banned_words_in_hook", ["--"]),
            ("banned_characters_anywhere", [" "]),
        ):
            with self.subTest(key=key), self.assertRaises(lint.RulesError):
                lint.Rules(dict(HOOK_RULES, **{key: value}))
        with self.assertRaises(lint.RulesError):
            lint.Rules(["not", "an", "object"])


class NewRuleTypesTest(unittest.TestCase):
    def test_stock_phrases_capped_words_scarcity_and_invented_proof_block(self):
        rules = full_rules()
        self.assertIn(("stock_phrases", True), rules_hit(rules, "Studies show it works."))
        self.assertIn(("capped_words", True), rules_hit(rules, "It is simply seamless."))
        self.assertEqual(rules_hit(rules, "It is simply there.\n\nAnd seamless."), [])  # one per paragraph
        self.assertIn(("fake_scarcity", True), rules_hit(rules, "Only 3 left this week."))
        self.assertIn(("fake_scarcity", True), rules_hit(rules, "Last chance."))
        for text in (
            "Join 10,000 users.",
            "Thousands of reviews agree.",
            "Loved by 2k+ people.",
            "87% stick.",
            "3x faster.",
        ):
            with self.subTest(text=text):
                self.assertIn(("invented_proof_terms", True), rules_hit(rules, text))
        self.assertEqual(rules_hit(rules, "Five minutes counts. 5 to 60 minutes."), [])

    def test_a_capped_word_counts_every_time_it_is_used(self):
        rules = full_rules()
        self.assertEqual(rules_hit(rules, "It just works."), [])
        [finding] = rules.check([lint.Copy("TikTok caption", "It just works. You just open it. Just start.")])
        self.assertEqual(
            (finding.rule, finding.detail),
            ("capped_words", "3 capped words in one paragraph (just, just, just); at most 1"),
        )

    def test_a_number_joined_to_its_term_by_a_hyphen_is_invented_proof(self):
        rules = full_rules()
        for text in ("A 4.8-star rating.", "A 10k-user beta.", "Countless reviews."):
            with self.subTest(text=text):
                self.assertEqual(rules_hit(rules, text), [("invented_proof_terms", True)])

    def test_a_number_ends_on_a_digit_and_never_takes_in_the_punctuation_after_it(self):
        rules = full_rules()
        for text in (
            "Day 3 of 14. People keep asking.",
            "Pick 5, 10, or 20. Reviews vary.",
            "In 2026, people still open apps.",
            "Only 3. Left behind.",
        ):
            with self.subTest(text=text):
                self.assertEqual(rules_hit(rules, text), [])
        for text in ("Join 10,000 users.", "Loved by 2k+ people.", "A 1.5k user beta."):
            with self.subTest(text=text):
                self.assertEqual(rules_hit(rules, text), [("invented_proof_terms", True)])
        self.assertEqual(rules_hit(rules, "Only 3 left."), [("fake_scarcity", True)])

    def test_the_quantity_words_come_from_brand_rules_and_wait_for_them(self):
        data = json.loads(KIT_RULES.read_text(encoding="utf-8"))
        del data["invented_proof_quantities"]
        rules = lint.Rules(data)
        self.assertEqual(rules.pending(), ["invented proof"])
        self.assertEqual(rules_hit(rules, "Thousands of reviews agree."), [])
        self.assertEqual(rules_hit(rules, "Join 10,000 users."), [("invented_proof_terms", True)])
        rules = lint.Rules(dict(data, invented_proof_quantities=["a wave of"]))
        self.assertEqual(rules_hit(rules, "A wave of reviews."), [("invented_proof_terms", True)])

    def test_a_typographic_apostrophe_reads_as_a_plain_one_in_the_copy_and_in_the_rules(self):
        data = json.loads(KIT_RULES.read_text(encoding="utf-8"))
        rules = lint.Rules(
            dict(
                data,
                fake_scarcity=["don't miss out"],
                stock_phrases=["here\u2019s the thing"],
                banned_words_in_hook=["can't stop"],
                lint_allow_phrases=["it\u2019s simply there"],
            )
        )
        self.assertEqual(rules_hit(rules, "Don\u2019t miss out."), [("fake_scarcity", True)])
        self.assertEqual(rules_hit(rules, "Here's the thing."), [("stock_phrases", True)])
        self.assertEqual(rules_hit(rules, "Here\u2019s the thing."), [("stock_phrases", True)])
        self.assertEqual(rules_hit(rules, "You can\u2019t stop."), [("banned_words_in_hook", True)])
        self.assertEqual(rules_hit(rules, "It's simply there, and really."), [])

    def test_a_term_is_caught_anywhere_inside_a_hashtag(self):
        data = json.loads(KIT_RULES.read_text(encoding="utf-8"))
        rules = lint.Rules(dict(data, capped_words=["in order to", "cutting-edge"], stock_phrases=["level up"]))
        cases = {
            "#beastmode #NoExcuses": [("banned_words_in_hook", True)] * 2,
            "#beast_mode #no_excuses": [("banned_words_in_hook", True)] * 2,
            "#nobeastmode #beastmodeoff": [("banned_words_in_hook", True)],
            "#dailygrind": [("banned_words_in_hook", True)],
            "#transformation": [("banned_words_in_hook", True)],
            "#userslove": [("banned_social_proof_in_hook", True)],
            "#levelup": [("stock_phrases", True)],
            "#inorderto #cuttingedge": [("capped_words", True)],
            "#lastchance #only3left": [("fake_scarcity", True)] * 2,
            "#10kusers": [("invented_proof_terms", True)],
            "#over10kusers #trustedby10k_users": [("invented_proof_terms", True)] * 2,
            "#thousandsofreviews": [("invented_proof_terms", True)],
        }
        for text, hits in cases.items():
            with self.subTest(text=text):
                self.assertEqual(sorted(rules_hit(rules, text, field="TikTok hashtags")), sorted(hits))
        lines = [finding.line() for finding in rules.check([lint.Copy("TikTok hashtags", "#nogrind #over10kusers")])]
        self.assertEqual(
            lines,
            [
                "banned_words_in_hook: banned word 'grind' (TikTok hashtags)",
                "invented_proof_terms: unsourced proof '#over10kusers' (TikTok hashtags)",
            ],
        )
        # Only a hashtag runs a term's words together, and a hashtag that holds no term passes.
        self.assertEqual(rules_hit(rules, "Beastmode is one word here, and so is levelup."), [])
        self.assertEqual(rules_hit(rules, "#buildinpublic #homeworkout", field="TikTok hashtags"), [])

    def test_an_allowed_phrase_is_blanked_in_a_hashtag_only_when_it_is_the_whole_hashtag(self):
        data = json.loads(KIT_RULES.read_text(encoding="utf-8"))
        rules = lint.Rules(dict(data, banned_words_in_hook=["weight loss", "grind", "card"]))
        self.assertEqual(rules_hit(rules, "No card required."), [])
        self.assertEqual(rules_hit(rules, "#nocardrequired #no_card_required", field="TikTok hashtags"), [])
        # A longer hashtag is checked in full, the allowed phrase's own words included.
        longer = {
            "#nocardrequireddailygrind": ["banned word 'grind'", "banned word 'card'"],
            "#nocardrequiredweightloss": ["banned word 'weight loss'", "banned word 'card'"],
            "#nocardrequired10kusers": ["banned word 'card'", "unsourced proof '#nocardrequired10kusers'"],
            "#no_card_required_dailygrind": ["banned word 'grind'", "banned word 'card'"],
            "#dailygrindnocardrequired": ["banned word 'grind'", "banned word 'card'"],
        }
        for text, details in longer.items():
            with self.subTest(text=text):
                found = rules.check([lint.Copy("TikTok hashtags", text)])
                self.assertEqual([finding.detail for finding in found], details)

    def test_a_term_s_words_match_whatever_sets_them_apart(self):
        data = json.loads(KIT_RULES.read_text(encoding="utf-8"))
        rules = lint.Rules(
            dict(
                data,
                banned_words_in_hook=["weight loss", "grind", "card"],
                capped_words=["cutting-edge", "world-class"],
                fake_scarcity=["last chance", "{n}-day sale"],
            )
        )
        cases = {
            "This is not a weight-loss app.": [("banned_words_in_hook", True)],
            "Weight_loss, again.": [("banned_words_in_hook", True)],
            "Weight \u2013 loss.": [("banned_words_in_hook", True)],
            "The weight_loss_plan and my_grind_plan.": [("banned_words_in_hook", True)] * 2,
            "A real game changer.": [("stock_phrases", True)],
            "A real game-changer.": [("stock_phrases", True)],
            "Say-goodbye-to planning.": [("stock_phrases", True)],
            "Cutting edge and world class.": [("capped_words", True)],
            "Last-chance sign-up.": [("fake_scarcity", True)],
            "A 3 day sale.": [("fake_scarcity", True)],
            "Thousands-of people.": [("invented_proof_terms", True)],
            "A 10k_user beta.": [("invented_proof_terms", True)],
            "10k_really_happy_users.": [("invented_proof_terms", True)],
        }
        for text, hits in cases.items():
            with self.subTest(text=text):
                self.assertEqual(sorted(rules_hit(rules, text)), sorted(hits))
        self.assertEqual(rules_hit(rules, "No-card-required beta."), [])
        self.assertEqual(rules_hit(rules, "A weightloss app, a postcard, and grinding."), [])
        self.assertEqual(rules_hit(rules, "10k_really_very_happy_users."), [])

    def test_a_need_marker_blocks_since_a_draft_never_fills_in_proof(self):
        self.assertIn(("need-marker", True), rules_hit(lint.Rules(HOOK_RULES), "Used by [NEED: source] people."))

    def test_long_sentences_only_warn_and_skip_descriptions(self):
        rules = full_rules()
        sentence = (
            "This sentence runs on, and on, and on, well past the point where anyone would read it at nine at night."
        )
        self.assertEqual(rules_hit(rules, sentence), [("long_sentence_words", False), ("long_sentence_commas", False)])
        alt = [lint.Copy("TikTok alt text", sentence, description=True)]
        self.assertEqual(rules.check(alt), [])

    def test_allowed_phrases_are_never_counted(self):
        rules = lint.Rules(dict(json.loads(KIT_RULES.read_text()), lint_allow_phrases=["simply seamless"]))
        self.assertEqual(rules_hit(rules, "It is simply seamless."), [])


class FrozenHookExemptionTest(unittest.TestCase):
    """brand-rules.json's frozen_hooks_exempt_from: the frozen Hooks a post's field may show, in their own words, pass
    the Hook rules it names, and nothing else does."""

    FROZEN = "I built a workout app with no streaks, on purpose. Watch what happens when I miss a day."
    BOTH = ["hook_max_words", "banned_words_in_hook"]

    def rules(self, exempt=BOTH):
        return lint.Rules(dict(HOOK_RULES, frozen_hooks_exempt_from=exempt))

    def planned(self, copies, *frozen):
        """The copies as a post Draft's checks give them, each field showing the given frozen Hooks."""
        return [replace(copy, frozen=frozen or (self.FROZEN,)) for copy in copies]

    def blocking(self, rules, copies, *frozen):
        return sorted(
            {(finding.rule, finding.field) for finding in rules.check(self.planned(copies, *frozen)) if finding.blocks}
        )

    def test_without_the_key_the_frozen_hook_is_held_to_every_rule_as_before(self):
        rules = lint.Rules(HOOK_RULES)
        copies = [lint.Copy("Hook", self.FROZEN, hook=True), lint.Copy("beat 1 on-screen text", self.FROZEN)]
        self.assertEqual(rules.check(self.planned(copies)), rules.check(copies))
        self.assertEqual(
            self.blocking(rules, copies),
            [
                ("banned_words_in_hook", "Hook"),
                ("banned_words_in_hook", "beat 1 on-screen text"),
                ("hook_max_words", "Hook"),
            ],
        )
        self.assertEqual(rules.exemptions(self.planned(copies)), [])
        self.assertNotIn("frozen_hooks_exempt_from", {row.rule for row in rules.statuses()})

    def test_the_frozen_hook_word_for_word_passes_the_word_cap_and_the_banned_words(self):
        rules = self.rules()
        copies = [
            lint.Copy("Hook", self.FROZEN, hook=True),
            lint.Copy("beat 1 on-screen text", self.FROZEN),
            lint.Copy("beat 1 spoken line", "I built a workout app with no streaks, on purpose."),
            lint.Copy("TikTok caption", self.FROZEN + "\nBuilt by one person. Not released yet."),
            lint.Copy("YouTube Shorts title", self.FROZEN),
        ]
        self.assertEqual(self.blocking(rules, copies), [])
        self.assertEqual(
            [(finding.rule, finding.field, finding.blocks) for finding in rules.exemptions(self.planned(copies))],
            [
                ("hook_max_words", "Hook", False),
                ("banned_words_in_hook", "Hook", False),
                ("banned_words_in_hook", "beat 1 on-screen text", False),
                ("banned_words_in_hook", "beat 1 spoken line", False),
                ("banned_words_in_hook", "TikTok caption", False),
                ("banned_words_in_hook", "YouTube Shorts title", False),
            ],
        )
        self.assertEqual(
            rules.exemptions(self.planned(copies))[0].line(),
            "hook_max_words: frozen test Hook, exempt by brand-rules.json frozen_hooks_exempt_from: the Hook has 18"
            " words; at most 12 (Hook)",
        )
        self.assertEqual(
            {row.rule: row.detail for row in rules.statuses()}["frozen_hooks_exempt_from"],
            "a post's frozen Hooks, in their own words, are exempt from these Hook rules: hook_max_words,"
            " banned_words_in_hook",
        )

    def test_a_hook_that_is_not_frozen_text_is_held_to_both_rules(self):
        rules = self.rules()
        hook = "Most workout apps open with a question and no streak. This one opens with it."
        for frozen in ("", self.FROZEN, "Most workout apps open with a question. This one opens with the workout."):
            with self.subTest(frozen=frozen):
                self.assertEqual(
                    self.blocking(rules, [lint.Copy("Hook", hook, hook=True)], frozen),
                    [("banned_words_in_hook", "Hook"), ("hook_max_words", "Hook")],
                )
        thirteen = "Most workout apps open with a question. This one opens with the workout."
        self.assertEqual(
            self.blocking(rules, [lint.Copy("Hook", thirteen, hook=True)], ""), [("hook_max_words", "Hook")]
        )
        self.assertEqual(rules.exemptions(self.planned([lint.Copy("Hook", hook, hook=True)])), [])

    def test_an_edited_frozen_hook_keeps_the_word_cap_and_its_own_case(self):
        rules = self.rules()
        for edited in (self.FROZEN + " Really.", self.FROZEN.lower(), self.FROZEN.replace("I miss", "I skip")):
            with self.subTest(edited=edited):
                self.assertIn(("hook_max_words", "Hook"), self.blocking(rules, [lint.Copy("Hook", edited, hook=True)]))
        lowered = [lint.Copy("TikTok caption", self.FROZEN.lower())]
        self.assertEqual(self.blocking(rules, lowered), [("banned_words_in_hook", "TikTok caption")])

    def test_a_banned_word_outside_the_frozen_words_still_blocks_in_the_same_field(self):
        rules = self.rules()
        caption = lint.Copy("TikTok caption", self.FROZEN + "\nNo streak to keep, no grind.")
        self.assertEqual(self.blocking(rules, [caption]), [("banned_words_in_hook", "TikTok caption")])
        self.assertEqual(
            sorted(finding.detail for finding in rules.check(self.planned([caption])) if finding.blocks),
            ["banned word 'grind'", "banned word 'streak'"],
        )
        self.assertEqual(rules.exemptions(self.planned([caption])), [])
        hashtags = lint.Copy("TikTok hashtags", "#nostreaks")
        self.assertEqual(self.blocking(rules, [hashtags]), [("banned_words_in_hook", "TikTok hashtags")])
        note = lint.Copy("beat 1 visual action", self.FROZEN + " Five stars on screen.", note=True)
        self.assertEqual(self.blocking(rules, [note]), [("banned_social_proof_in_hook", "beat 1 visual action")])

    def test_every_other_hook_rule_still_applies_to_the_frozen_hook(self):
        rules = lint.Rules(dict(full_rules().data, frozen_hooks_exempt_from=self.BOTH))
        frozen = "Rated five stars by thousands of users? Try it NOW \U0001f525"
        found = {finding.rule for finding in rules.check([lint.Copy("Hook", frozen, hook=True, frozen=(frozen,))])}
        self.assertEqual(
            found,
            {
                "hook_must_not_be_question",
                "banned_social_proof_in_hook",
                "no_emoji_in_hook",
                "no_all_caps_words_in_hook",
                "invented_proof_terms",
            },
        )

    def test_a_field_s_other_frozen_hooks_are_exempt_only_where_the_field_may_show_them(self):
        rules = self.rules()
        other = "Watch what happens in my app when I miss a day."
        beat = lint.Copy("beat 2 spoken line", "I built a workout app with no streaks, on purpose.")
        self.assertEqual(self.blocking(rules, [beat], other, self.FROZEN), [])
        self.assertEqual(
            [finding.line() for finding in rules.exemptions(self.planned([beat], other, self.FROZEN))],
            [
                "banned_words_in_hook: frozen test Hook, exempt by brand-rules.json frozen_hooks_exempt_from: banned"
                " word 'streak' (beat 2 spoken line)"
            ],
        )
        self.assertEqual(self.blocking(rules, [beat], other), [("banned_words_in_hook", "beat 2 spoken line")])
        self.assertEqual(self.blocking(rules, [beat], ""), [("banned_words_in_hook", "beat 2 spoken line")])
        hook = lint.Copy("Hook", self.FROZEN, hook=True)
        self.assertEqual(
            self.blocking(rules, [hook], other), [("banned_words_in_hook", "Hook"), ("hook_max_words", "Hook")]
        )

    def test_only_the_rules_the_key_names_are_exempt(self):
        copies = [lint.Copy("Hook", self.FROZEN, hook=True)]
        self.assertEqual(self.blocking(self.rules(["hook_max_words"]), copies), [("banned_words_in_hook", "Hook")])
        self.assertEqual(self.blocking(self.rules(["banned_words_in_hook"]), copies), [("hook_max_words", "Hook")])
        self.assertEqual(
            self.blocking(self.rules([]), copies), [("banned_words_in_hook", "Hook"), ("hook_max_words", "Hook")]
        )

    def test_a_malformed_key_or_any_other_rule_name_makes_the_rules_unusable(self):
        for value in (
            "hook_max_words",
            ["hook_must_not_be_question"],
            ["banned_words_in_hook", "stock_phrases"],
            ["Hook_Max_Words"],
            [12],
            {"hook_max_words": True},
            None,
            True,
        ):
            with self.subTest(value=value), self.assertRaisesRegex(lint.RulesError, "frozen_hooks_exempt_from"):
                lint.Rules(dict(HOOK_RULES, frozen_hooks_exempt_from=value))


class CallToActionTest(unittest.TestCase):
    LINE = {"line": "Join the waitlist: {link}", "sources": {"TikTok": "tiktok", "YouTube Shorts": "youtube"}}

    def test_without_the_key_no_line_is_given(self):
        self.assertIsNone(lint.Rules(HOOK_RULES).call_to_action)
        self.assertNotIn("caption_call_to_action", [row.rule for row in lint.Rules(HOOK_RULES).statuses()])

    def test_the_line_and_each_platform_s_source_are_read_and_reported_as_applied(self):
        rules = lint.Rules(dict(HOOK_RULES, caption_call_to_action=self.LINE))
        action = rules.call_to_action
        self.assertEqual(action.with_link("reptoday.app/tiktok"), "Join the waitlist: reptoday.app/tiktok")
        self.assertEqual(action.wording(), ["Join the waitlist"])
        self.assertEqual(dict(action.sources), {"TikTok": "tiktok", "YouTube Shorts": "youtube"})
        self.assertIn(
            lint.RuleStatus("caption_call_to_action", lint.APPLIED, lint.KNOWN_RULES["caption_call_to_action"]),
            rules.statuses(),
        )
        self.assertEqual(rules.check([lint.Copy("TikTok caption", "Join the waitlist: reptoday.app/tiktok")]), [])

    def test_the_line_with_any_link_is_told_from_other_lines(self):
        action = lint.Rules(dict(HOOK_RULES, caption_call_to_action=self.LINE)).call_to_action
        for line, matches in (
            ("Join the waitlist: reptoday.app/tiktok", True),
            ("Join  the waitlist:  https://reptoday.app/youtube/", True),
            ("Join the waitlist: reptoday.app/tiktok.", True),
            ("join the waitlist: reptoday.app/tiktok", False),
            ("Join the waitlist: soon", False),
            ("Join the beta: reptoday.app/tiktok", False),
        ):
            with self.subTest(line=line):
                self.assertEqual(action.any_link(line), matches)

    def test_a_malformed_key_makes_the_rules_unusable(self):
        for value in (
            "Join the waitlist: {link}",
            {"line": "Join the waitlist"},
            {"line": "Join the waitlist: reptoday.app/tiktok", "sources": self.LINE["sources"]},
            {"line": "{link}", "sources": self.LINE["sources"]},
            {"line": "Join {link} or {link}", "sources": self.LINE["sources"]},
            {"line": "Join the waitlist:\n{link}", "sources": self.LINE["sources"]},
            {"line": "Join the waitlist: {link}", "sources": {}},
            {"line": "Join the waitlist: {link}", "sources": {"TikTok": "TikTok"}},
            {"line": "Join the waitlist: {link}", "sources": ["tiktok"]},
            dict(self.LINE, extra=True),
            None,
            [],
            5,
        ):
            with self.subTest(value=value), self.assertRaisesRegex(lint.RulesError, "caption_call_to_action"):
                lint.Rules(dict(HOOK_RULES, caption_call_to_action=value))


class PlatformTest(unittest.TestCase):
    def setUp(self):
        self.platforms = lint.load_platforms(json.loads((fakes.REPO / "config/platforms.json").read_text()))

    def check(self, platform, **values):
        defaults = {"Caption": "Hook.", "Title": "Hook.", "Description": "Hook.", "Hashtags": "none", "Alt text": "A."}
        return [
            (finding.rule, finding.blocks)
            for finding in lint.check_platform(self.platforms[platform], dict(defaults, **values))
        ]

    def test_tiktok_allows_five_hashtags_and_4000_characters_with_them(self):
        self.assertEqual(self.check("TikTok", Hashtags="#a #b #c #d #e"), [])
        self.assertIn(
            ("config/platforms.json TikTok max_hashtags", True), self.check("TikTok", Hashtags="#a #b #c #d #e #f")
        )
        self.assertIn(
            ("config/platforms.json TikTok Caption max_chars", True),
            self.check("TikTok", Caption="x" * 3996, Hashtags="#ab #cd"),
        )
        self.assertEqual(
            self.check("TikTok", Caption="x" * 3990, Hashtags="#ab")[0][0],
            "config/platforms.json TikTok Caption visible_chars",
        )

    def test_youtube_titles_and_the_hashtag_void(self):
        self.assertIn(
            ("config/platforms.json YouTube Shorts Title max_chars", True),
            self.check("YouTube Shorts", Title="x" * 101),
        )
        self.assertEqual(
            self.check("YouTube Shorts", Title="x" * 75),
            [("config/platforms.json YouTube Shorts Title visible_chars", False)],
        )
        tags = " ".join(f"#t{n}" for n in range(16))
        self.assertIn(
            ("config/platforms.json YouTube Shorts hashtags_void_above", True),
            self.check("YouTube Shorts", Hashtags=tags),
        )

    def test_hashtags_belong_in_their_own_field(self):
        self.assertIn(("hashtags", True), self.check("TikTok", Caption="Hook. #inline"))
        self.assertIn(("hashtags", True), self.check("TikTok", Hashtags="#ok notatag"))

    def test_platform_facts_need_a_body_and_a_hashtags_field(self):
        with self.assertRaises(lint.PlatformError):
            lint.load_platforms({"platforms": {"X": {"fields": {"Text": {}}}}})
        with self.assertRaises(lint.PlatformError):
            lint.load_platforms({})


if __name__ == "__main__":
    unittest.main()
