"""Reading the 14-day kit: the calendar, the Angle bank, the A/B pairs, the platforms, the checklist, competitors."""

import unittest

from gr0wthlab import kit
from tests import fakes

GTM = fakes.EXAMPLES / "files" / "mandu" / "projects" / "RepToday" / "gtm"


def read(relative):
    return (GTM / relative).read_text(encoding="utf-8")


def parsed():
    return kit.Kit(
        days=kit.parse_calendar(read("05-social-pmf/cadence-14-day.md")),
        angles=kit.parse_angles(read("05-social-pmf/angles.md")),
        pairs=kit.parse_pairs(read("05-social-pmf/ab-pairs.md")),
    )


class CalendarTest(unittest.TestCase):
    def test_each_day_names_its_angle_pair_leg_and_primary_platform(self):
        days = kit.parse_calendar(read("05-social-pmf/cadence-14-day.md"))
        self.assertEqual(sorted(days), list(range(1, 15)))
        first = days[1]
        self.assertEqual((first.angle, first.pair, first.leg, first.primary), ("P01", "AB-1", "A", "TikTok"))
        self.assertEqual(first.asset, "Open-to-ready demo, hook A")
        self.assertEqual(read("05-social-pmf/cadence-14-day.md").splitlines()[first.line - 1][:5], "| 1 |")
        self.assertEqual((days[2].angle, days[2].pair, days[2].leg), ("P02", None, None))
        self.assertEqual(days[3].primary, "YouTube Shorts")

    def test_the_calendar_s_own_checklist_for_every_asset_is_read_line_by_line(self):
        checks = kit.parse_asset_checks(read("05-social-pmf/cadence-14-day.md"))
        self.assertEqual(
            [(check.line, check.text) for check in checks],
            [(26, "The founder is in frame for every line said in the first person.")],
        )
        self.assertEqual(kit.parse_asset_checks("## The calendar\n\n- Not a checklist line.\n"), ())

    def test_a_day_whose_angle_is_decided_later_has_none(self):
        flex = kit.parse_calendar(read("05-social-pmf/cadence-14-day.md"))[14]
        self.assertIsNone(flex.angle)
        self.assertIn("if nothing qualifies", flex.cell)

    def test_a_parenthetical_queued_pair_is_not_a_leg(self):
        text = "| Day | Asset | Angle / pair leg | Primary platform | Notes |\n|---|---|---|---|---|\n"
        text += "| 7 | Walkthrough | P06 (one leg for now; AB-9 held back) | TikTok | |\n"
        day = kit.parse_calendar(text)[7]
        self.assertEqual((day.angle, day.pair, day.leg), ("P06", None, None))

    def test_a_calendar_that_does_not_parse_says_why(self):
        for text, why in (
            ("No table here.", "no table with the columns"),
            ("| Day | Asset | Angle | Platform |\n|---|---|---|---|\n| one | x | P01 | TikTok |\n", "is not a number"),
            ("| Day | Asset | Angle | Platform |\n|---|---|---|---|\n| \u00b2 | x | P01 | A |\n", "is not a number"),
            ("| Day | Asset | Angle | Platform |\n|---|---|---|---|\n| 1 | x | P01 |\n", "has 3 cells"),
            ("| Day | Asset | Angle | Platform |\n|---|---|---|---|\n", "has no days"),
        ):
            with self.subTest(why=why), self.assertRaisesRegex(kit.KitError, why):
                kit.parse_calendar(text)

    def test_why_a_calendar_does_not_parse_never_repeats_a_cell(self):
        text = "| Day | Asset | Angle | Platform |\n|---|---|---|---|\n| one | x | P01 | TikTok |\n"
        with self.assertRaises(kit.KitError) as raised:
            kit.parse_calendar(text)
        self.assertEqual(str(raised.exception), "calendar line 3: its day is not a number")


class AnglesAndPairsTest(unittest.TestCase):
    def test_each_angle_has_its_sourced_pain_hook_format_signal_and_kill_criterion(self):
        angles = kit.parse_angles(read("05-social-pmf/angles.md"))
        self.assertEqual(sorted(angles), [f"P0{n}" for n in range(1, 8)])
        angle = angles["P03"]
        self.assertEqual(angle.hook, "Skip a day and the score dips. It never resets.")
        self.assertEqual(angle.pain_urls, ("https://example.com/threads/103",))
        self.assertEqual(angle.signal, "Viewed rate in the top half")
        self.assertEqual(angle.kill, "Bottom quartile viewed rate on two reads")
        self.assertIn("screen record", angle.format)
        self.assertTrue(angle.row.startswith("| P03 |"))

    def test_a_hook_cell_that_is_not_one_quoted_line_has_no_frozen_text(self):
        text = read("05-social-pmf/angles.md").replace(
            '"Airplane mode on. The session still appears."', 'Founder reads aloud, then: "The session appears."'
        )
        self.assertIsNone(kit.parse_angles(text)["P04"].hook)

    def test_each_pair_has_its_angle_platform_and_two_frozen_legs(self):
        pairs = kit.parse_pairs(read("05-social-pmf/ab-pairs.md"))
        pair = pairs["AB-2"]
        self.assertEqual((pair.angle, pair.platform), ("P03", "YouTube Shorts"))
        self.assertEqual(pair.legs["A"].hook, "Skip a day and the score dips. It never resets.")
        self.assertEqual(pair.legs["B"].hook, "A skipped day never takes you back to zero.")

    def test_a_leg_hook_is_the_first_quoted_text_on_its_line(self):
        text = (
            "## AB-3: free (angle P07, TikTok, same video)\n\n"
            '- Leg A hook: the video opens with the review "you just can\'t." (source: https://x.test),'
            " promise second.\n"
            '- Leg B hook: the video opens with "Free means free.", review second.\n'
        )
        legs = kit.parse_pairs(text)["AB-3"].legs
        self.assertEqual((legs["A"].hook, legs["B"].hook), ("you just can't.", "Free means free."))

    def test_a_pair_without_both_legs_says_why(self):
        with self.assertRaisesRegex(kit.KitError, "leg A and a leg B"):
            kit.parse_pairs('## AB-1: x (angle P01, TikTok)\n\n- Leg A hook: "One."\n')

    def test_the_frozen_hook_is_the_pair_leg_s_or_else_the_angle_s(self):
        built = parsed()
        self.assertEqual(kit.frozen_hook(built.days[8], built)[0].text, "The session is on screen before you decide.")
        hook, _ = kit.frozen_hook(built.days[2], built)
        self.assertEqual((hook.text, hook.source), ("I missed five days and the app welcomed me back.", "angles"))
        self.assertEqual(kit.frozen_hook(built.days[14], built), (None, kit.frozen_hook(built.days[14], built)[1]))
        self.assertIn("decides day 14's Angle later", kit.frozen_hook(built.days[14], built)[1])

    def test_every_hook_belongs_to_one_angle(self):
        owners = dict(kit.all_hooks(parsed()))
        self.assertEqual(owners["A skipped day never takes you back to zero."], "P03")
        self.assertEqual(owners["Five minutes still counts as showing up."], "P07")


class RecutTest(unittest.TestCase):
    CALENDAR = "05-social-pmf/cadence-14-day.md"
    PAIRS = "05-social-pmf/ab-pairs.md"
    HOOKS = ("Open it and the session is already waiting.", "The session is on screen before you decide.")

    def hooks(self, calendar, pairs, day):
        found = kit.Kit(days=kit.parse_calendar(calendar), pairs=kit.parse_pairs(pairs))
        return kit.recut_hooks(found.days[day], found)

    def test_a_pair_is_a_re_cut_only_where_the_kit_says_so(self):
        calendar, pairs = read(self.CALENDAR), read(self.PAIRS)
        for day in (1, 2, 8, 14):
            self.assertEqual(self.hooks(calendar, pairs, day), ())
        in_calendar = calendar.replace("with only its hook swapped", "Re-cut opening")
        in_pairs = pairs.replace("same screen record)", "same screen record, recut)", 1)
        for where, marked in (("calendar", (in_calendar, pairs)), ("pairs", (calendar, in_pairs))):
            with self.subTest(marked_in=where):
                self.assertEqual(self.hooks(*marked, 1), self.HOOKS)
                self.assertEqual(self.hooks(*marked, 8), self.HOOKS)
                self.assertEqual(self.hooks(*marked, 3), ())  # the other pair is not marked


class PlatformsChecklistCompetitorsTest(unittest.TestCase):
    def test_the_test_platforms_in_order(self):
        self.assertEqual(
            kit.parse_platforms(read("05-social-pmf/platform-assignment.md")), ("TikTok", "YouTube Shorts")
        )
        with self.assertRaises(kit.KitError):
            kit.parse_platforms("## Other\n\n### 1. TikTok (primary)\n")

    def test_each_checklist_item_says_whether_it_is_done_and_what_it_blocks(self):
        items = {item.line: item for item in kit.parse_checklist(read("08-redteam/pre-publication-checklist.md"))}
        trademark, domain, benchmark, voiceover = items[7], items[8], items[12], items[16]
        self.assertTrue(trademark.checked)
        self.assertEqual((trademark.scope, trademark.gates_social), (("everything public",), True))
        self.assertEqual((domain.scope, domain.gates_social), (None, False))
        self.assertEqual((benchmark.claim, benchmark.gates_social), ("under 100 milliseconds", True))
        self.assertEqual((voiceover.scope, voiceover.gates_social), (("video publication",), False))
        self.assertEqual(benchmark.title, 'Device benchmark record for the "under 100 milliseconds" claim')

    def test_competitors_from_titles_sourced_sections_and_the_scope_list(self):
        files = {path.name: path.read_text(encoding="utf-8") for path in (GTM / "01-research").glob("competitor*.md")}
        found = {competitor.name: (competitor.source, competitor.line) for competitor in kit.parse_competitors(files)}
        self.assertEqual(
            found,
            {
                "IronFit": ("competitor-ironfit.md", 1),
                "Pulseday": ("competitors-additional.md", 4),
                "Stretchly": ("competitors-additional.md", 6),
            },
        )

    def test_a_competitor_name_is_cut_before_its_description(self):
        self.assertEqual(kit.competitor_name("Iron Fit (Ironworks Co.) - incl. cardio | Iron Fit"), ["Iron Fit"])
        self.assertEqual(
            kit.competitor_name("Pulseday App (app subscription, not the band)"), ["Pulseday App", "Pulseday"]
        )
        self.assertEqual(kit.competitor_name("Stretchly! Move Every Hour (Stretchly, LLC)"), ["Stretchly"])
        self.assertEqual(kit.competitor_name("Nine: 9 Minute Circuit (Northfold)"), ["Nine"])
        numbered = {"a.md": "## 7. Wedge contrast: us vs them\n\nNo source line.\n"}
        with self.assertRaisesRegex(kit.KitError, "no competitor names"):
            kit.parse_competitors(numbered)


if __name__ == "__main__":
    unittest.main()
