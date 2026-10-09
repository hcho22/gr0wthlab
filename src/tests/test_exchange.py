"""The Mandu exchange formats: items gr0wthlab writes, decision and sitting records Mandu writes."""

import unittest

from gr0wthlab import exchange

PRODUCTS = ["RepToday", "Immerse"]


def item(kind="package-change-proposal", heading=None, extra_fields="", body="Change the line.", evidence=None):
    heading = heading or exchange.KINDS[kind]
    evidence = evidence or "- The checklist records it done: `projects/RepToday/02-checklist.md` line 24"
    options = "\n".join(f"- {option}" for option in exchange.options(kind))
    return (
        f"---\nkind: {kind}\nproduct: RepToday\n{extra_fields}---\n\n# Approve package change: fix the status\n\n"
        f"## {heading}\n\n{body}\n\n## Touches\n\n- `projects/RepToday/gtm/README.md`\n\n"
        f"## Evidence\n\n{evidence}\n\n## Options\n\n{options}\n"
    )


class ItemCheckTest(unittest.TestCase):
    def test_a_well_formed_item_of_every_kind_passes(self):
        for kind in exchange.KINDS:
            fields = "slot: 2026-10-14T19:00-07:00\n" if kind == "post" else ""
            with self.subTest(kind=kind):
                check = exchange.check_item(item(kind, extra_fields=fields), PRODUCTS)
                self.assertEqual(check.problems, [])
                self.assertEqual(check.item.kind, kind)
                self.assertEqual(check.item.ask, "Approve package change: fix the status")
                self.assertEqual(check.item.body, "Change the line.")

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
        self.assertEqual(exchange.check_item(item(extra_fields="exchange: 1\n"), PRODUCTS).problems, [])
        self.assertTrue(exchange.check_item(item(), PRODUCTS, published=True).problems)
        published = item(extra_fields="exchange: 1\nid: 20261011-fix-status\n")
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

    def test_render_writes_a_published_item_that_passes(self):
        check = exchange.check_item(item(extra_fields="supersedes: 20261004-old\n"), PRODUCTS)
        fields = dict(check.item.fields, exchange="1", id="20261011-fix-status")
        text = exchange.render_item(fields, check.item.ask, check.item.body, check.item.touches, check.item.evidence)
        self.assertTrue(text.startswith("---\nexchange: 1\nid: 20261011-fix-status\nkind: package-change-proposal\n"))
        again = exchange.check_item(text, PRODUCTS, published=True)
        self.assertEqual(again.problems, [])
        self.assertEqual(again.item.fields["supersedes"], "20261004-old")


DECISION = {
    "exchange": 1,
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

    def test_a_rejection_needs_a_one_line_reason(self):
        self.assertTrue(self.parse(reason=None)[1])
        self.assertTrue(self.parse(reason="")[1])
        self.assertTrue(self.parse(reason="line one\nline two")[1])
        self.assertTrue(self.parse(reason="x" * 301)[1])

    def test_malformed_records_are_refused(self):
        self.assertTrue(self.parse(decision="approve")[1], "an approval has no reason")
        self.assertTrue(self.parse(decision="maybe")[1])
        self.assertTrue(self.parse(item="20261011-other")[1])
        self.assertTrue(self.parse(decided_at="2026-10-11T19:42:00")[1])
        self.assertTrue(self.parse(exchange=2)[1])
        self.assertTrue(self.parse(sitting="Oct 11")[1])
        self.assertTrue(exchange.parse_decision("x", ["not", "an", "object"])[1])

    def test_mandu_may_add_its_own_fields(self):
        self.assertEqual(self.parse(presented_at="2026-10-11T19:40:00-07:00")[1], [])


class SittingTest(unittest.TestCase):
    def test_minutes_and_date(self):
        sitting, problems = exchange.parse_sitting("2026-10-11", {"exchange": 1, "date": "2026-10-11", "minutes": 48})
        self.assertEqual(problems, [])
        self.assertEqual(sitting.minutes, 48)
        for bad in ({"minutes": 0}, {"minutes": True}, {"minutes": "48"}, {"date": "2026-10-12"}):
            with self.subTest(bad=bad):
                record = dict({"exchange": 1, "date": "2026-10-11", "minutes": 48}, **bad)
                self.assertTrue(exchange.parse_sitting("2026-10-11", record)[1])


if __name__ == "__main__":
    unittest.main()
