"""The Mandu exchange formats: items gr0wthlab writes, decision and sitting records Mandu writes."""

import unittest
from unittest import mock

from gr0wthlab import exchange

PRODUCTS = ["RepToday", "Immerse"]


def item(
    kind="package-change-proposal",
    heading=None,
    extra_fields="",
    body="Change the line.",
    evidence=None,
    declared="new_angle: no\n",
):
    heading = heading or exchange.KINDS[kind]
    evidence = evidence or "- The checklist records it done: `projects/RepToday/02-checklist.md` line 24"
    options = "\n".join(f"- {option}" for option in exchange.options(kind))
    declared = declared if kind == "package-change-proposal" else ""
    return (
        f"---\nkind: {kind}\nproduct: RepToday\n{declared}{extra_fields}---\n\n"
        "# Approve package change: fix the status\n\n"
        f"## {heading}\n\n{body}\n\n## Touches\n\n- `projects/RepToday/gtm/README.md`\n\n"
        f"## Evidence\n\n{evidence}\n\n## Options\n\n{options}\n"
    )


class ItemCheckTest(unittest.TestCase):
    def test_a_well_formed_item_of_every_kind_passes(self):
        for kind in exchange.KINDS:
            fields = "window: 1\nday: 3\nslot: 2026-10-14T19:00-07:00\n" if kind == "post" else ""
            with self.subTest(kind=kind):
                check = exchange.check_item(item(kind, extra_fields=fields), PRODUCTS)
                self.assertEqual(check.problems, [])
                self.assertEqual(check.item.kind, kind)
                self.assertEqual(check.item.ask, "Approve package change: fix the status")
                self.assertEqual(check.item.body, "Change the line.")

    def test_a_post_names_its_window_and_day_and_has_a_slot_once_the_window_has_one(self):
        cases = {
            "window: 1\nday: 3\n": [],
            "window: 1\nday: 3\nslot: 2026-10-14T19:00-07:00\n": [],
            "day: 3\n": ["a post needs window: a whole number from 1"],
            "window: 1\nday: 0\n": ["a post needs day: a whole number from 1"],
            "window: 1\nday: 3\nslot: tomorrow\n": [
                "slot must be the publishing time with its UTC offset, such as 2026-10-14T19:00-07:00"
            ],
        }
        for fields, problems in cases.items():
            with self.subTest(fields=fields):
                self.assertEqual(exchange.check_item(item("post", extra_fields=fields), PRODUCTS).problems, problems)

    def test_a_version_2_post_always_had_a_slot(self):
        published = "exchange: 2\nid: 20261011-day-three\n"
        check = exchange.check_item(item("post", extra_fields=published), PRODUCTS, published=True)
        self.assertEqual(
            check.problems, ["a version 2 post needs slot: its publishing time, such as 2026-10-14T19:00-07:00"]
        )
        slotted = published + "slot: 2026-10-14T19:00-07:00\n"
        self.assertEqual(exchange.check_item(item("post", extra_fields=slotted), PRODUCTS, published=True).problems, [])

    def test_a_post_whose_video_is_finished_names_it_under_the_ledger_s_assets(self):
        post = "window: 1\nday: 3\n"
        named = post + "asset: assets/window-1/day-03-0a1b2c3d4e5f.mp4\n"
        check = exchange.check_item(item("post", extra_fields=named), PRODUCTS)
        self.assertEqual(check.problems, [])
        self.assertEqual(check.item.fields["asset"], "assets/window-1/day-03-0a1b2c3d4e5f.mp4")
        rendered = exchange.render_item(
            dict(check.item.fields, exchange=str(exchange.EXCHANGE_VERSION), id="20261011-post-w1-day-03"),
            "Ask",
            "B",
            "T",
            "E",
        )
        self.assertIn("day: 3\nasset: assets/window-1/day-03-0a1b2c3d4e5f.mp4\n---", rendered)
        for elsewhere in (
            "/Users/founder/Movies/day-03.mp4",
            "assets/../../Movies/day-03.mp4",
            "review-queue/items/day-03.mp4",
            "assets/window-1/day-03.mov",
            "assets/.hidden/day-03.mp4",
        ):
            with self.subTest(asset=elsewhere):
                check = exchange.check_item(item("post", extra_fields=post + f"asset: {elsewhere}\n"), PRODUCTS)
                self.assertEqual(
                    check.problems,
                    ["asset must be the finished video's path under ledger/, such as assets/window-1/day-03.mp4"],
                )
        other = exchange.check_item(item(extra_fields="asset: assets/window-1/day-03.mp4\n"), PRODUCTS)
        self.assertEqual(other.problems, ["only a post has an asset"])

    def test_the_filming_plan_is_its_own_kind_presented_after_the_posts(self):
        self.assertEqual(list(exchange.KINDS)[:3], ["post", "filming-plan", "message"])
        self.assertEqual(exchange.KINDS["filming-plan"], "Plan")
        check = exchange.check_item(item("filming-plan"), PRODUCTS)
        self.assertEqual(check.problems, [])
        self.assertEqual(exchange.options("filming-plan")[0], "Approve, optionally with a note")
        self.assertEqual(
            exchange.check_item(item("filming-plan", extra_fields="day: 3\n"), PRODUCTS).problems,
            ["only a post has a day"],
        )

    def test_only_a_post_has_a_window_a_day_or_a_slot(self):
        for key, value in (("window", "1"), ("day", "3"), ("slot", "2026-10-14T19:00-07:00")):
            with self.subTest(key=key):
                check = exchange.check_item(item(extra_fields=f"{key}: {value}\n"), PRODUCTS)
                self.assertEqual(check.problems, [f"only a post has a {key}"])

    def test_each_kind_needs_its_own_body_heading(self):
        check = exchange.check_item(
            item("post", heading="Proposal", extra_fields="slot: 2026-10-14T19:00Z\n"), PRODUCTS
        )
        self.assertIsNone(check.item)
        self.assertTrue(any("sections must be exactly" in problem for problem in check.problems))

    def test_unknown_kind_product_and_front_matter_keys_are_refused(self):
        self.assertTrue(exchange.check_item(item().replace("package-change-proposal", "tweet"), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item().replace("RepToday\n", "Purvia\n", 1), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item(extra_fields="priority: high\n"), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item(extra_fields="kind: post\n"), PRODUCTS).problems)

    def test_only_posts_have_a_slot_with_an_offset(self):
        self.assertTrue(exchange.check_item(item("post"), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item("post", extra_fields="slot: 2026-10-14T19:00\n"), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item(extra_fields="slot: 2026-10-14T19:00Z\n"), PRODUCTS).problems)

    def test_the_agent_leaves_out_the_id_and_a_published_item_has_one(self):
        self.assertTrue(exchange.check_item(item(extra_fields="id: 20261011-x\n"), PRODUCTS).problems)
        self.assertEqual(
            exchange.check_item(item(extra_fields=f"exchange: {exchange.EXCHANGE_VERSION}\n"), PRODUCTS).problems, []
        )
        self.assertTrue(exchange.check_item(item(), PRODUCTS, published=True).problems)
        published = item(extra_fields=f"exchange: {exchange.EXCHANGE_VERSION}\nid: 20261011-fix-status\n")
        self.assertEqual(exchange.check_item(published, PRODUCTS, published=True).problems, [])

    def test_nothing_else_is_allowed(self):
        stray = item().replace("# Approve", "Some preface.\n\n# Approve")
        self.assertTrue(exchange.check_item(stray, PRODUCTS).problems)
        extra_section = item().replace("## Options", "## Notes\n\nmore\n\n## Options")
        self.assertTrue(exchange.check_item(extra_section, PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item().replace("---\nkind", "kind", 1), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item(body=""), PRODUCTS).problems)

    def test_every_evidence_line_names_its_source(self):
        self.assertTrue(exchange.check_item(item(evidence="- The checklist says so"), PRODUCTS).problems)
        self.assertTrue(exchange.check_item(item(evidence="Plain text"), PRODUCTS).problems)
        linked = "- A thread: https://www.reddit.com/r/x/1\n- A file: `gtm/README.md`\n  continued"
        self.assertEqual(exchange.check_item(item(evidence=linked), PRODUCTS).problems, [])

    def test_options_are_fixed_per_kind(self):
        notice = item("notice")
        self.assertIn("- Acknowledge, optionally with a note", notice)
        self.assertEqual(exchange.check_item(notice, PRODUCTS).problems, [])
        wrong = item().replace("- Reject, with a one-line reason", "- Maybe")
        self.assertTrue(exchange.check_item(wrong, PRODUCTS).problems)

    def test_an_item_too_long_to_decide_fast_is_refused(self):
        self.assertTrue(exchange.check_item(item(body="x " * 7000), PRODUCTS).problems)

    def test_the_length_limit_gives_the_same_answer_before_and_after_publication(self):
        short = exchange.check_item(item(body="x"), PRODUCTS).item
        at_limit = "x" * (exchange.MAX_ITEM_CHARS - len(item(body="")))
        over = "x" * (
            exchange.MAX_ITEM_CHARS
            - len(exchange.render_content(short.kind, short.ask, "", short.touches, short.evidence))
            + 1
        )
        for body, fits in ((at_limit, True), (over, False)):
            with self.subTest(fits=fits):
                self.assertEqual(exchange.check_item(item(body=body), PRODUCTS).item is not None, fits)
                fields = dict(short.fields, exchange=str(exchange.EXCHANGE_VERSION), id="20261011-fix-status")
                published = exchange.render_item(fields, short.ask, body, short.touches, short.evidence)
                self.assertEqual(exchange.check_item(published, PRODUCTS, published=True).item is not None, fits)

    def test_render_writes_a_published_item_that_passes(self):
        check = exchange.check_item(item(extra_fields="supersedes: 20261004-old\n"), PRODUCTS)
        fields = dict(check.item.fields, exchange=str(exchange.EXCHANGE_VERSION), id="20261011-fix-status")
        text = exchange.render_item(fields, check.item.ask, check.item.body, check.item.touches, check.item.evidence)
        self.assertTrue(
            text.startswith(
                f"---\nexchange: {exchange.EXCHANGE_VERSION}\nid: 20261011-fix-status\nkind: package-change-proposal\n"
            )
        )
        again = exchange.check_item(text, PRODUCTS, published=True)
        self.assertEqual(again.problems, [])
        self.assertEqual(again.item.fields["supersedes"], "20261004-old")

    def test_a_package_change_proposal_declares_whether_it_adds_or_changes_an_angle_or_hook(self):
        needs = "a package-change proposal needs new_angle: yes when it adds or changes an Angle or Hook"
        for value in ("yes", "no"):
            check = exchange.check_item(item(declared=f"new_angle: {value}\n"), PRODUCTS)
            self.assertEqual((check.problems, check.item.fields["new_angle"]), ([], value))
        for declared in ("", "new_angle: maybe\n", "new_angle:\n", "new_angle: Yes\n"):
            with self.subTest(declared=declared):
                check = exchange.check_item(item(declared=declared), PRODUCTS)
                self.assertIsNone(check.item)
                self.assertTrue(any(needs in problem for problem in check.problems), check.problems)
        stated_older = item(declared="", extra_fields="exchange: 3\n")
        self.assertIsNone(exchange.check_item(stated_older, PRODUCTS).item, "an item the agent writes always declares")
        for kind in ("notice", "message", "dispatch-request"):
            with self.subTest(kind=kind):
                problems = exchange.check_item(item(kind, extra_fields="new_angle: no\n"), PRODUCTS).problems
                self.assertEqual(problems, ["only a package-change proposal has new_angle"])

    def test_the_declaration_is_on_the_queued_item_and_an_item_of_an_earlier_version_reads_without_one(self):
        check = exchange.check_item(item(declared="new_angle: yes\n"), PRODUCTS)
        fields = dict(check.item.fields, exchange=str(exchange.EXCHANGE_VERSION), id="20261011-fix-status")
        text = exchange.render_item(fields, check.item.ask, check.item.body, check.item.touches, check.item.evidence)
        self.assertIn("\nkind: package-change-proposal\nproduct: RepToday\nnew_angle: yes\n---\n", text)
        self.assertEqual(exchange.check_item(text, PRODUCTS, published=True).item.fields["new_angle"], "yes")
        undeclared = text.replace("new_angle: yes\n", "")
        self.assertIsNone(exchange.check_item(undeclared, PRODUCTS, published=True).item)
        for version in exchange.UNDECLARED_VERSIONS:
            earlier = undeclared.replace(f"exchange: {exchange.EXCHANGE_VERSION}\n", f"exchange: {version}\n")
            self.assertEqual(exchange.check_item(earlier, PRODUCTS, published=True).problems, [], version)
        # Version 5 added the declaration, so a proposal of that version or a later one needs it.
        for version in range(len(exchange.UNDECLARED_VERSIONS) + 1, exchange.EXCHANGE_VERSION + 1):
            later = undeclared.replace(f"exchange: {exchange.EXCHANGE_VERSION}\n", f"exchange: {version}\n")
            self.assertIsNone(exchange.check_item(later, PRODUCTS, published=True).item, version)

    def test_evidence_names_each_record_exactly_as_it_is_written_in_backticks(self):
        text = (
            "- One: `evidence/listening/quotes/d-0123456789ab.json` line 2\n"
            "- Two, see evidence/listening/quotes/d-aaaaaaaaaaaa.json: `notes/evidence/decisions/x.json.txt`\n"
            "  and `evidence/decisions/x.json`, at https://example.com/a"
        )
        self.assertEqual(
            exchange.references(text),
            {
                "evidence/listening/quotes/d-0123456789ab.json",
                "notes/evidence/decisions/x.json.txt",
                "evidence/decisions/x.json",
            },
        )


DECISION = {
    "exchange": exchange.EXCHANGE_VERSION,
    "item": "20261011-fix-status",
    "decision": "reject",
    "reason": "Keep the legal line until counsel confirms.",
    "note": None,
    "decided_at": "2026-10-11T19:42:00-07:00",
    "sitting": "2026-10-11",
}


class DecisionTest(unittest.TestCase):
    def parse(self, **changes):
        return exchange.parse_decision("20261011-fix-status", dict(DECISION, **changes))

    def test_a_rejection_with_its_reason(self):
        decision, problems = self.parse()
        self.assertEqual(problems, [])
        self.assertEqual(
            (decision.decision, decision.reason), ("reject", "Keep the legal line until counsel confirms.")
        )

    def test_an_approval_with_an_optional_note(self):
        decision, problems = self.parse(decision="approve", reason=None, note="Ship it.")
        self.assertEqual(problems, [])
        self.assertEqual(decision.note, "Ship it.")
        self.assertEqual(self.parse(decision="approve", reason=None, sitting=None)[1], [])
        self.assertIsNone(self.parse(decision="approve", reason=None, note="  ")[0].note)

    def test_a_rejection_needs_a_one_line_reason(self):
        self.assertTrue(self.parse(reason=None)[1])
        self.assertTrue(self.parse(reason="")[1])
        self.assertIn("reason is required", self.parse(reason="   ")[1])
        self.assertTrue(self.parse(reason="line one\nline two")[1])
        self.assertTrue(self.parse(reason="x" * 301)[1])

    def test_malformed_records_are_refused(self):
        self.assertTrue(self.parse(decision="approve")[1], "an approval has no reason")
        self.assertTrue(self.parse(decision="maybe")[1])
        self.assertTrue(self.parse(item="20261011-other")[1])
        self.assertTrue(self.parse(decided_at="2026-10-11T19:42:00")[1])
        self.assertTrue(self.parse(sitting="Oct 11")[1])
        self.assertTrue(exchange.parse_decision("x", ["not", "an", "object"])[1])

    def test_mandu_may_add_its_own_fields(self):
        self.assertEqual(self.parse(presented_at="2026-10-11T19:40:00-07:00")[1], [])


class VersionTest(unittest.TestCase):
    def test_records_and_items_of_earlier_versions_still_read_after_a_bump(self):
        current = exchange.EXCHANGE_VERSION
        sitting = {"exchange": current, "date": "2026-10-11", "minutes": 48}
        published = item(extra_fields=f"exchange: {current}\nid: 20261011-fix-status\n")
        with mock.patch.object(exchange, "EXCHANGE_VERSION", current + 1):
            self.assertEqual(exchange.parse_decision("20261011-fix-status", DECISION)[1], [])
            self.assertEqual(exchange.parse_decision("20261011-fix-status", dict(DECISION, exchange=1))[1], [])
            self.assertEqual(exchange.parse_sitting("2026-10-11", sitting)[1], [])
            self.assertEqual(exchange.check_item(published, PRODUCTS, published=True).problems, [])

    def test_a_newer_or_malformed_version_is_reported_never_guessed_at(self):
        newer = exchange.EXCHANGE_VERSION + 1
        self.assertEqual(
            exchange.parse_decision("20261011-fix-status", dict(DECISION, exchange=newer))[1],
            [f"exchange version {newer} is newer than gr0wthlab can read (up to {exchange.EXCHANGE_VERSION})"],
        )
        for bad in (0, "2", True, None):
            with self.subTest(bad=bad):
                self.assertTrue(exchange.parse_decision("20261011-fix-status", dict(DECISION, exchange=bad))[1])
        newer_item = item(extra_fields=f"exchange: {newer}\nid: 20261011-fix-status\n")
        self.assertTrue(exchange.check_item(newer_item, PRODUCTS, published=True).problems)
        self.assertTrue(exchange.check_item(item(extra_fields="exchange: two\n"), PRODUCTS).problems)
        self.assertEqual(exchange.check_item(item(), PRODUCTS).problems, [])


class SittingTest(unittest.TestCase):
    def test_minutes_and_date(self):
        good = {"exchange": exchange.EXCHANGE_VERSION, "date": "2026-10-11", "minutes": 48}
        sitting, problems = exchange.parse_sitting("2026-10-11", good)
        self.assertEqual(problems, [])
        self.assertEqual(sitting.minutes, 48)
        for bad in ({"minutes": 0}, {"minutes": True}, {"minutes": "48"}, {"date": "2026-10-12"}):
            with self.subTest(bad=bad):
                record = dict(good, **bad)
                self.assertTrue(exchange.parse_sitting("2026-10-11", record)[1])


if __name__ == "__main__":
    unittest.main()
