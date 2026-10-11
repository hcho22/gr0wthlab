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
COMMIT = "1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff"


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

    def test_the_source_names_what_it_was_adapted_from_and_the_queued_item_carries_the_mit_notice(self):
        """THIRD_PARTY_NOTICES.md's contract for adapted text: the file's one-line header names each source path and
        the commit, and what reaches Mandu holds the notice itself, since the header is not part of the item."""
        source = SOURCE.read_text(encoding="utf-8")
        header = source.splitlines()[0]
        for named in ("skills/copywriting/references/ai-tells.md", COMMIT, "THIRD_PARTY_NOTICES.md"):
            self.assertIn(named, header)
        self.assertEqual(proposals.item_text(source), source[len(header) + 1 :])
        filed = self.file()
        queued = (self.store.root / self.ledger.entries[filed.item]["file"]).read_text(encoding="utf-8")
        self.assertNotIn(header, queued)
        for notice in ("Copyright (c) 2025 Corey Haines", "Permission is hereby granted, free of charge", COMMIT):
            self.assertIn(notice, queued)

    def test_it_is_filed_once_and_never_asked_again_whatever_the_founder_decides(self):
        filed = self.file()
        self.assertEqual((filed.status, filed.item), (proposals.FILED, "20261011-brand-rules-word-lists"))
        entry = self.ledger.entries[filed.item]
        self.assertEqual(entry["origin"], "proposal/brand-rules-word-lists")
        self.assertIn("filed this run: open for the Founder's decision", proposals.describe(filed, self.ledger))
        again = self.file(run="RUN2", now=NOW + timedelta(days=7))
        self.assertEqual((again.status, again.item), (proposals.QUEUED_BEFORE, filed.item))
        self.ledger.close(entry, "rejected", "RUN3", NOW, reason="Too many words.")
        entry["reason"] = "Too many words."
        later = self.file(run="RUN4", now=NOW + timedelta(days=14))
        self.assertEqual((later.status, later.item), (proposals.QUEUED_BEFORE, filed.item))
        self.assertIn("rejected: Too many words.", proposals.describe(later, self.ledger))
        self.assertEqual(len(self.ledger.entries), 1)

    def test_no_item_the_agent_writes_supersedes_it_so_the_reviewed_text_stays_the_one_asked(self):
        filed = self.file()
        incoming = self.store.root.parent / "smaller-lists.md"
        incoming.write_text(fakes.proposal(extra=f"supersedes: {filed.item}\n", title="fewer lists"), encoding="utf-8")
        item, problems = self.ledger.check_incoming(incoming, incoming.name, PRODUCTS, self.seen)
        self.assertIsNone(item)
        self.assertEqual(
            problems,
            [
                f"supersedes {filed.item}, which the launcher filed from reviewed text; only a reviewed change to that"
                " text replaces it"
            ],
        )
        self.assertEqual(self.ledger.entries[filed.item]["status"], "open")

    def test_an_approved_proposal_says_only_that_and_is_not_filed_once_mandu_holds_the_lists(self):
        filed = self.file()
        self.ledger.close(self.ledger.entries[filed.item], "approved", "RUN2", NOW)
        applied = json.loads(
            (
                fakes.EXAMPLES / "files/mandu/projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
            ).read_text()
        )
        # Whether Mandu holds the lists yet is the rule summary's to say, from Mandu's file; this line never guesses.
        for target in (None, applied):
            with self.subTest(applied=target is not None):
                again = self.file(target=target, run="RUN3")
                self.assertEqual((again.status, again.item), (proposals.QUEUED_BEFORE, filed.item))
                self.assertEqual(
                    proposals.describe(again, self.ledger),
                    f"`{proposals.BRAND_RULES}` is `{filed.item}`, filed earlier, never re-asked: approved.",
                )
        fresh = Ledger()
        self.ledger = fresh
        held = self.file(target=applied)
        self.assertEqual((held.status, held.item), (proposals.IN_MANDU, None))
        self.assertEqual(fresh.entries, {})
        self.assertIn("not filed; Mandu's file already holds every key it adds", proposals.describe(held, fresh))


if __name__ == "__main__":
    unittest.main()
