"""The Draft lint: brand-rules.json's rules on every field of copy, the F1 rule types, and the platform limits."""

import json
import unittest

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
    "required_disclosure": "Screen images simulated.",
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
