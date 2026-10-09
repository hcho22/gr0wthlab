"""Reviewed Dispatch requests: each is a valid item, the Waitlist request specifies what the reader reads, and the
launcher files each once and never re-asks one the Founder decided."""

import json
import os
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gr0wthlab import dispatch, exchange, settings, waitlist
from gr0wthlab.areas import Store
from gr0wthlab.queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger
from tests.test_waitlist import RULES

REPO = Path(__file__).resolve().parents[2]
PRODUCTS = ["RepToday", "Immerse"]
NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)


class ReviewedRequestsTest(unittest.TestCase):
    def test_every_reviewed_request_is_a_valid_dispatch_request(self):
        requests, problems = dispatch.load(REPO, PRODUCTS)
        self.assertEqual(problems, [])
        self.assertEqual([request.key for request in requests], ["reptoday-waitlist"])
        for request in requests:
            self.assertEqual((request.item.kind, request.item.fields.get("product")), ("dispatch-request", "RepToday"))


class WaitlistRequestTest(unittest.TestCase):
    """The request is the contract RepToday's build implements and the launcher reads; they must never drift."""

    def setUp(self):
        self.text = (REPO / "src/dispatches/reptoday-waitlist.md").read_text(encoding="utf-8")
        registry = json.loads((REPO / "config/products.json").read_text(encoding="utf-8"))
        self.block = next(product for product in registry["products"] if product["name"] == "RepToday")["waitlist"]

    def test_its_example_is_a_view_the_launcher_reads(self):
        example = re.search(r"```json\n(.*?)\n```", self.text, re.S).group(1)
        view = json.loads(example)
        self.assertEqual(sorted(view), sorted(waitlist.TOP_KEYS))
        self.assertEqual(sorted(view["entries"][0]), sorted(waitlist.ENTRY_KEYS))
        checked, problems = waitlist.check_view(view, RULES, datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc))
        self.assertEqual(problems, [])
        self.assertEqual(len(checked.entries), 1)

    def test_it_names_every_field_tag_and_answer_the_reader_accepts(self):
        self.assertIn('"view": 1', self.text)
        for key in ("generated_at", *waitlist.ENTRY_KEYS):
            self.assertIn(f"- `{key}`:", self.text)
        for tag in self.block["source_tags"]:
            self.assertIn(f"`{tag}`", self.text)
            self.assertIn(f"`reptoday.app/{tag}`", self.text)
        self.assertIn("`https://reptoday.app/?utm_source=<tag>`", self.text)
        self.assertIn("Source `unknown`", self.text)
        for answer in self.block["fit_answers"]:
            self.assertIn(f"`{answer}`", self.text)
        self.assertIn(f"more than {self.block['stale_after_hours']} hours old", self.text)

    def test_it_carries_every_us_me05_criterion(self):
        for words in (
            "Exactly one low-pressure call to action",
            "Three fields and no others",
            '"I used to work out and lost the routine"',
            '"I work out regularly"',
            '''"I've never had a routine"''',
            '"Invite me to the beta before launch"',
            'No "how did you hear about us" field',
            "`landing_page_view`",
            "`waitlist_signup`",
            "`referrer_source`",
            "`reptoday.app/privacy` gains a Waitlist section",
            "What is collected",
            "Why:",
            "How long it is kept",
            "How to be removed",
            "Nothing else: no address",
            "Addresses are resolved only on your side, at send time",
            "No email-service credential",
            "Storage (including whether Kit stays), hosting, how the view is produced",
            "Once you approve, Mandu hands this request to firstmate",
        ):
            self.assertIn(words, self.text)


class FilingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(os.path.realpath(self.tmp.name))
        self.repo = root / "gr0wthlab"
        shutil.copytree(str(REPO / "src/dispatches"), str(self.repo / "src/dispatches"))
        self.store = Store(root / "gr0wthlab/ledger")
        self.ledger = Ledger()

    def tearDown(self):
        self.tmp.cleanup()

    def file(self, days=0, run="RUN1"):
        requests, problems = dispatch.load(self.repo, PRODUCTS)
        self.assertEqual(problems, [])
        hashes = {}
        for identifier, entry in self.ledger.entries.items():
            text = (self.store.root / str(entry["file"])).read_text(encoding="utf-8")
            hashes[identifier] = exchange.item_hash(exchange.check_item(text, PRODUCTS, published=True).item)
        seen = {fingerprint: identifier for identifier, fingerprint in hashes.items()}
        return dispatch.file(self.ledger, self.store, requests, hashes, seen, run, NOW + timedelta(days=days))

    def edit(self, old, new):
        path = self.repo / "src/dispatches/reptoday-waitlist.md"
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def decide(self, identifier, status):
        self.ledger.close(self.ledger.entries[identifier], status, "RUN", NOW, decided_at="2026-10-11T19:00:00-07:00")

    def test_filed_once_under_an_identifier_that_never_changes(self):
        (filing,) = self.file()
        self.assertEqual(filing.status, dispatch.FILED)
        identifier = filing.identifier
        entry = self.ledger.entries[identifier]
        self.assertEqual(
            (entry["kind"], entry["origin"], entry["status"]), ("dispatch-request", "dispatch/reptoday-waitlist", OPEN)
        )
        published = (self.store.root / str(entry["file"])).read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(published, PRODUCTS, published=True).problems, [])
        self.assertEqual(identifier, f"{NOW.astimezone().date():%Y%m%d}-reptoday-waitlist")
        for later in (7, 14):
            self.assertEqual([(f.status, f.identifier) for f in self.file(later)], [(dispatch.WAITING, identifier)])
        self.assertEqual(len(self.ledger.entries), 1)

    def test_a_reviewed_change_supersedes_the_open_request(self):
        (first,) = self.file()
        self.edit("at least once a day", "at least twice a day")
        (second,) = self.file(7)
        self.assertEqual((second.status, second.replaced), (dispatch.REPLACED, first.identifier))
        old, new = self.ledger.entries[first.identifier], self.ledger.entries[second.identifier]
        self.assertEqual((old["status"], old["superseded_by"]), (SUPERSEDED, second.identifier))
        self.assertEqual((new["status"], new["supersedes"]), (OPEN, first.identifier))
        self.assertEqual(self.file(14)[0].status, dispatch.WAITING)

    def test_never_filed_again_once_approved_even_after_a_change(self):
        (first,) = self.file()
        self.decide(first.identifier, APPROVED)
        self.edit("at least once a day", "at least twice a day")
        self.assertEqual([(f.status, f.identifier) for f in self.file(7)], [(dispatch.DONE, first.identifier)])
        self.assertEqual(len(self.ledger.entries), 1)

    def test_never_re_asked_after_a_rejection_until_its_text_changes(self):
        (first,) = self.file()
        self.decide(first.identifier, REJECTED)
        self.assertEqual([(f.status, f.identifier) for f in self.file(7)], [(dispatch.DECIDED, first.identifier)])
        self.assertEqual(len(self.ledger.entries), 1)
        self.edit("at least once a day", "at least twice a day")
        (again,) = self.file(14)
        self.assertEqual(again.status, dispatch.FILED)
        self.assertNotEqual(again.identifier, first.identifier)
        self.assertNotIn("supersedes", self.ledger.entries[again.identifier])

    def test_a_request_already_asked_by_another_item_is_not_filed(self):
        requests, _ = dispatch.load(self.repo, PRODUCTS)
        seen = {exchange.item_hash(requests[0].item): "20261004-agent-waitlist"}
        (filing,) = dispatch.file(self.ledger, self.store, requests, {}, seen, "RUN", NOW)
        self.assertEqual((filing.status, filing.identifier), (dispatch.ASKED, "20261004-agent-waitlist"))
        self.assertEqual(self.ledger.entries, {})

    def test_files_that_are_not_requests_are_named_and_never_filed(self):
        folder = self.repo / "src/dispatches"
        text = (folder / "reptoday-waitlist.md").read_text(encoding="utf-8")
        (folder / "Bad Name.md").write_text(text, encoding="utf-8")
        (folder / "a-notice.md").write_text(text.replace("kind: dispatch-request", "kind: notice"), encoding="utf-8")
        (folder / "replaces.md").write_text(
            text.replace("product: RepToday", "product: RepToday\nsupersedes: 20261011-x"), encoding="utf-8"
        )
        (folder / ".hidden.md").write_text("ignored", encoding="utf-8")
        requests, problems = dispatch.load(self.repo, PRODUCTS)
        self.assertEqual([request.key for request in requests], ["reptoday-waitlist"])
        self.assertEqual(len(problems), 3)
        self.assertIn("`src/dispatches/Bad Name.md` is not a Dispatch request", problems[0])
        self.assertIn("`src/dispatches/a-notice.md` was not filed:", problems[1])
        self.assertIn("the launcher alone decides what it supersedes", problems[2])

    def test_no_folder_means_no_requests(self):
        self.assertEqual(dispatch.load(self.repo / "absent", PRODUCTS), ([], []))


class SettingsAgreeTest(unittest.TestCase):
    def test_the_committed_waitlist_has_no_view_until_the_build_lands(self):
        from gr0wthlab import boundary
        from tests.test_boundary import CONFIG

        registry = json.loads((REPO / "config/products.json").read_text(encoding="utf-8"))
        home = Path("/srv/home")
        resolved = boundary.resolve_boundary(home / "gr0wthlab", CONFIG, registry, {}, home, git=[])
        rules = settings.waitlist(registry, resolved, {}, home)
        self.assertEqual(rules, RULES)


if __name__ == "__main__":
    unittest.main()
