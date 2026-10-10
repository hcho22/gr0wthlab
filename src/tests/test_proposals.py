"""Proposals the launcher files once from src/proposals/: the brand lint's word lists (F1)."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gr0wthlab import exchange, lint, proposals
from gr0wthlab.areas import Store
from gr0wthlab.queue import Ledger
from tests import fakes

NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
PRODUCTS = ["RepToday", "Immerse"]
SOURCE = fakes.REPO / proposals.BRAND_RULES


class BrandRulesProposalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(os.path.realpath(self.tmp.name)) / "ledger")
        self.ledger = Ledger()
        self.seen = {}

    def tearDown(self):
        self.tmp.cleanup()

    def file(self, target=None, run="RUN1", now=NOW):
        return proposals.file_once(
            fakes.REPO, proposals.BRAND_RULES, target, self.store, self.ledger, PRODUCTS, run, now, self.seen
        )

    def test_it_is_a_valid_proposal_that_adds_exactly_the_lint_s_new_rule_keys(self):
        text = proposals.item_text(SOURCE.read_text(encoding="utf-8"))
        check = exchange.check_item(text, PRODUCTS)
        self.assertEqual(check.problems, [])
        self.assertEqual(check.item.kind, "package-change-proposal")
        keys = proposals.proposed_keys(check.item.body)
        self.assertEqual(sorted(keys), sorted({key for needed in lint.NEW_RULE_TYPES.values() for key in needed}))
        block = check.item.body.split("```json\n")[1].split("\n```")[0]
        lint.Rules(json.loads(block))  # the lists it proposes are rules the lint accepts
        self.assertIn("Copyright (c) 2025 Corey Haines", check.item.body)
        self.assertIn("Permission is hereby granted, free of charge", check.item.body)
        self.assertIn("1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff", check.item.body)
        self.assertTrue(SOURCE.read_text(encoding="utf-8").startswith("<!-- Adapted from skills/copywriting"))

    def test_it_is_filed_once_and_never_asked_again_whatever_the_founder_decides(self):
        filed = self.file()
        self.assertEqual((filed.status, filed.item), (proposals.FILED, "20261011-brand-rules-word-lists"))
        entry = self.ledger.entries[filed.item]
        self.assertEqual(entry["proposal_source"], str(proposals.BRAND_RULES))
        self.assertIn("filed this run: open for the Founder's decision", proposals.describe(filed, self.ledger))
        again = self.file(run="RUN2", now=NOW + timedelta(days=7))
        self.assertEqual((again.status, again.item), (proposals.QUEUED_BEFORE, filed.item))
        self.ledger.close(entry, "rejected", "RUN3", NOW, reason="Too many words.")
        entry["reason"] = "Too many words."
        later = self.file(run="RUN4", now=NOW + timedelta(days=14))
        self.assertEqual((later.status, later.item), (proposals.QUEUED_BEFORE, filed.item))
        self.assertIn("rejected: Too many words.", proposals.describe(later, self.ledger))
        self.assertEqual(len(self.ledger.entries), 1)

    def test_an_approved_proposal_waits_for_mandu_and_is_not_filed_once_mandu_holds_the_lists(self):
        filed = self.file()
        self.ledger.close(self.ledger.entries[filed.item], "approved", "RUN2", NOW)
        self.assertIn(
            "approved; it waits for Mandu to apply it", proposals.describe(self.file(run="RUN2"), self.ledger)
        )
        fresh = Ledger()
        self.ledger = fresh
        applied = json.loads(
            (
                fakes.EXAMPLES / "files/mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
            ).read_text()
        )
        held = self.file(target=applied)
        self.assertEqual((held.status, held.item), (proposals.IN_MANDU, None))
        self.assertEqual(fresh.entries, {})
        self.assertIn("not filed; Mandu's file already holds every key it adds", proposals.describe(held, fresh))


if __name__ == "__main__":
    unittest.main()
