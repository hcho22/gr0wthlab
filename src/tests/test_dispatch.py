"""Reviewed Dispatch requests: each is a valid item, the Waitlist request specifies what the reader reads, and the
launcher files each once and never re-asks one the Founder decided."""

import itertools
import json
import os
import re
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gr0wthlab import boundary, dispatch, exchange, settings, state, waitlist
from gr0wthlab.areas import Store
from gr0wthlab.queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger
from tests import fakes
from tests.test_boundary import CONFIG
from tests.test_waitlist import RULES

REPO = Path(__file__).resolve().parents[2]
PRODUCTS = ["RepToday", "Immerse"]
NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
VIEW_SECTION = "The anonymous view gr0wthlab reads"
ADDED_TOUCH = "- RepToday `gtm/03-site/thanks.html`: the page shown after a sign-up"
SOURCE_SECTION = "Source, from the link"


def committed_rules() -> settings.Waitlist:
    """RepToday's Waitlist as config/products.json has it."""
    registry = json.loads((REPO / "config/products.json").read_text(encoding="utf-8"))
    home = Path("/srv/home")
    resolved = boundary.resolve_boundary(home / "gr0wthlab", CONFIG, registry, {}, home, git=[])
    return settings.waitlist(registry, resolved, {}, home)


def subsections(body: str) -> dict[str, str]:
    """Each ### part of a request's body, by its heading."""
    found: dict[str, list[str]] = {}
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("### "):
            lines = found.setdefault(line[4:].strip(), [])
        else:
            lines.append(line)
    return {heading: "\n".join(lines) for heading, lines in found.items()}


def quoted(text: str) -> list[str]:
    """Every value a text puts in backticks."""
    return re.findall(r"`([^`]+)`", text)


def documented_fields(section: str) -> dict[str, list[str]]:
    """Each field a section defines as a list item, with the values its definition puts in backticks."""
    definitions = (re.fullmatch(r"- `(\w+)`: (.*)", line) for line in section.splitlines())
    return {match.group(1): quoted(match.group(2)) for match in definitions if match}


class ReviewedRequestsTest(unittest.TestCase):
    def test_every_reviewed_request_is_a_valid_dispatch_request(self):
        requests, problems = dispatch.load(REPO, PRODUCTS)
        self.assertEqual(problems, [])
        self.assertEqual([request.key for request in requests], ["reptoday-waitlist"])
        for request in requests:
            self.assertEqual((request.item.kind, request.item.fields.get("product")), ("dispatch-request", "RepToday"))


class WaitlistRequestTest(unittest.TestCase):
    """The request is the view's format, the contract RepToday's build implements and the launcher reads, so it is
    read here as the build would read it and checked through the launcher's own reader under the committed rules."""

    def setUp(self):
        (request,), _ = dispatch.load(REPO, PRODUCTS)
        self.parts = subsections(request.item.body)
        self.fields = documented_fields(self.parts[VIEW_SECTION])
        self.example = json.loads(re.search(r"```json\n(.*?)\n```", self.parts[VIEW_SECTION], re.S).group(1))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rules = replace(committed_rules(), view=Path(os.path.realpath(self.tmp.name)) / "waitlist-view.json")

    def read(self, view):
        fakes.write_view(self.rules.view, view)
        return waitlist.read(self.rules, NOW)

    def test_its_example_is_a_view_the_launcher_reads(self):
        reading = self.read(self.example)
        self.assertEqual((reading.status, len(reading.entries)), (waitlist.READ, 1), reading.detail)

    def test_it_defines_every_field_of_the_view_and_no_other(self):
        (entry,) = self.example["entries"]
        self.assertEqual((set(self.example), set(entry)), (set(waitlist.TOP_KEYS), set(waitlist.ENTRY_KEYS)))
        self.assertEqual(set(self.fields), (set(self.example) | set(entry)) - {"view", "entries"})

    def test_the_reader_counts_exactly_the_sources_and_fit_answers_it_lists(self):
        fits = [None if answer == "null" else answer for answer in self.fields["fit"]]
        pairs = itertools.product(self.fields["source"], fits)
        entries = [(f"entry{n}", source, fit, True, "2026-10-05") for n, (source, fit) in enumerate(pairs)]
        reading = self.read(fakes.waitlist_view(entries=entries))
        self.assertEqual(reading.status, waitlist.READ, reading.detail)
        self.assertEqual(sorted(reading.cumulative["by_source"]), sorted(self.fields["source"]))
        self.assertEqual(sorted(reading.cumulative["by_fit"]), sorted(fit or settings.UNKNOWN for fit in fits))

    def test_it_gives_one_link_per_source_whose_path_is_the_source_s_tag(self):
        mentions = [text for text in quoted(self.parts[SOURCE_SECTION]) if "reptoday.app" in text]
        links = [text for text in mentions if text != "reptoday.app"]
        self.assertEqual(sorted(links), sorted(f"reptoday.app/{tag}" for tag in self.rules.source_tags))


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

    def file(self, days=0, run="RUN1", remembered=None):
        """File as a run does; remembered is the fingerprint the run state holds for each closed item, if any."""
        requests, problems = dispatch.load(self.repo, PRODUCTS)
        self.assertEqual(problems, [])
        previous = state.ReviewQueueState(
            {identifier: {"outcome": REJECTED, "hash": known} for identifier, known in (remembered or {}).items()}
        )
        hashes, _ = state.item_hashes(self.store.root, self.ledger.entries, PRODUCTS, previous)
        seen = {fingerprint: identifier for identifier, fingerprint in hashes.items()}
        at = NOW + timedelta(days=days)
        return dispatch.file(self.ledger, self.store, requests, PRODUCTS, seen, run, at, hashes)

    def fingerprint(self, identifier):
        return exchange.item_hash(exchange.check_item(self.published(identifier), PRODUCTS, published=True).item)

    def lose(self, identifier):
        """Leave a queued item's file unreadable as an item, and return what restores it."""
        path = self.store.root / str(self.ledger.entries[identifier]["file"])
        text = path.read_text(encoding="utf-8")
        path.write_text("no item\n", encoding="utf-8")
        return lambda: path.write_text(text, encoding="utf-8")

    def published(self, identifier):
        """A queued item as Mandu reads it when the Founder, having approved it, asks for a ready-to-send message."""
        return (self.store.root / str(self.ledger.entries[identifier]["file"])).read_text(encoding="utf-8")

    def revise(self):
        """A reviewed change to what the request asks."""
        path = self.repo / "src/dispatches/reptoday-waitlist.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("\n## Touches\n", "\nA revised ask.\n\n## Touches\n"), encoding="utf-8")

    def retouch(self):
        """A reviewed change to the request's Touches alone."""
        path = self.repo / "src/dispatches/reptoday-waitlist.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("\n## Evidence\n", f"{ADDED_TOUCH}\n\n## Evidence\n"), encoding="utf-8")

    def revert(self):
        """A reviewed change that puts the request's first text back."""
        shutil.copy(str(REPO / "src/dispatches/reptoday-waitlist.md"), str(self.repo / "src/dispatches"))

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
        self.assertEqual(exchange.check_item(self.published(identifier), PRODUCTS, published=True).problems, [])
        self.assertEqual(identifier, f"{NOW.astimezone().date():%Y%m%d}-reptoday-waitlist")
        for later in (7, 14):
            self.assertEqual([(f.status, f.identifier) for f in self.file(later)], [(dispatch.WAITING, identifier)])
        self.assertEqual(len(self.ledger.entries), 1)

    def test_a_reviewed_change_supersedes_the_open_request(self):
        (first,) = self.file()
        self.revise()
        (second,) = self.file(7)
        self.assertEqual((second.status, second.replaced), (dispatch.REPLACED, first.identifier))
        old, new = self.ledger.entries[first.identifier], self.ledger.entries[second.identifier]
        self.assertEqual((old["status"], old["superseded_by"]), (SUPERSEDED, second.identifier))
        self.assertEqual((new["status"], new["supersedes"]), (OPEN, first.identifier))
        self.assertEqual(self.file(14)[0].status, dispatch.WAITING)

    def test_a_change_to_touches_alone_supersedes_the_open_request(self):
        (first,) = self.file()
        self.retouch()
        (second,) = self.file(7)
        self.assertEqual((second.status, second.replaced), (dispatch.REPLACED, first.identifier))
        self.assertEqual(self.ledger.entries[first.identifier]["status"], SUPERSEDED)
        self.assertNotIn(ADDED_TOUCH, self.published(first.identifier))
        self.assertIn(ADDED_TOUCH, self.published(second.identifier))
        self.assertEqual([(f.status, f.identifier) for f in self.file(14)], [(dispatch.WAITING, second.identifier)])

    def test_a_change_to_touches_alone_is_asked_anew_after_a_rejection(self):
        (first,) = self.file()
        self.decide(first.identifier, REJECTED)
        self.retouch()
        (again,) = self.file(7)
        self.assertEqual(again.status, dispatch.FILED)
        self.assertNotEqual(again.identifier, first.identifier)
        self.assertIn(ADDED_TOUCH, self.published(again.identifier))
        self.assertEqual([(f.status, f.identifier) for f in self.file(14)], [(dispatch.WAITING, again.identifier)])

    def test_never_filed_again_once_approved_even_after_a_change(self):
        (first,) = self.file()
        self.decide(first.identifier, APPROVED)
        self.revise()
        self.assertEqual([(f.status, f.identifier) for f in self.file(7)], [(dispatch.DONE, first.identifier)])
        self.assertEqual(len(self.ledger.entries), 1)

    def test_never_re_asked_after_a_rejection_until_its_text_changes(self):
        (first,) = self.file()
        self.decide(first.identifier, REJECTED)
        self.assertEqual([(f.status, f.identifier) for f in self.file(7)], [(dispatch.DECIDED, first.identifier)])
        self.assertEqual(len(self.ledger.entries), 1)
        self.revise()
        (again,) = self.file(14)
        self.assertEqual(again.status, dispatch.FILED)
        self.assertNotEqual(again.identifier, first.identifier)
        self.assertNotIn("supersedes", self.ledger.entries[again.identifier])

    def test_a_rejected_request_whose_item_file_cannot_be_read_is_never_filed_again(self):
        """The fingerprint the run state holds settles it as rejected; with neither record the request is held."""
        (first,) = self.file()
        remembered = {first.identifier: self.fingerprint(first.identifier)}
        self.decide(first.identifier, REJECTED)
        rejected = dict(self.ledger.entries[first.identifier])
        restore = self.lose(first.identifier)
        self.assertEqual(
            [(f.status, f.identifier) for f in self.file(7, remembered=remembered)],
            [(dispatch.DECIDED, first.identifier)],
        )
        (held,) = self.file(14)
        self.assertEqual((held.status, held.identifier, held.acted), (dispatch.HELD, None, False))
        unread = f"`{rejected['file']}`, the item file of `{first.identifier}`, could not be read ("
        self.assertTrue(held.unread.startswith(unread), held.unread)
        self.assertEqual(
            held.account(),
            f"reptoday-waitlist not filed, since {held.unread}, so nothing shows whether the Founder rejected this"
            " text; the next run compares them again",
        )
        self.assertEqual(dispatch.unread([], [held]), [held.unread])
        self.assertEqual(self.ledger.entries, {first.identifier: rejected}, "nothing filed, nothing withdrawn")
        restore()
        self.assertEqual([(f.status, f.identifier) for f in self.file(21)], [(dispatch.DECIDED, first.identifier)])
        self.assertEqual(len(self.ledger.entries), 1)

    def test_a_changed_request_is_held_only_while_nothing_shows_what_its_rejected_item_asked(self):
        (first,) = self.file()
        remembered = {first.identifier: self.fingerprint(first.identifier)}
        self.decide(first.identifier, REJECTED)
        self.revise()
        self.lose(first.identifier)
        self.assertEqual([f.status for f in self.file(7)], [dispatch.HELD])
        self.assertEqual(len(self.ledger.entries), 1)
        (again,) = self.file(14, remembered=remembered)
        self.assertEqual(again.status, dispatch.FILED, "the run state shows the rejected item asked something else")
        self.assertNotEqual(again.identifier, first.identifier)

    def test_a_text_replaced_before_any_decision_is_filed_again_when_it_comes_back(self):
        (first,) = self.file()
        self.revise()
        (second,) = self.file(7)
        self.decide(second.identifier, REJECTED)
        self.revert()
        (third,) = self.file(14)
        self.assertEqual(third.status, dispatch.FILED)
        self.assertNotIn(third.identifier, (first.identifier, second.identifier))
        self.assertEqual(self.ledger.entries[third.identifier]["status"], OPEN)
        self.assertEqual([(f.status, f.identifier) for f in self.file(21)], [(dispatch.WAITING, third.identifier)])
        self.decide(third.identifier, REJECTED)
        (fourth,) = self.file(28)
        self.assertEqual((fourth.status, fourth.identifier), (dispatch.DECIDED, third.identifier))
        self.assertIn(f"rejected as `{third.identifier}`", fourth.account())

    def test_a_rejected_text_brought_back_while_another_is_open_is_filed_in_its_place(self):
        (first,) = self.file()
        self.decide(first.identifier, REJECTED)
        self.revise()
        (second,) = self.file(7)
        self.assertEqual(second.status, dispatch.FILED)
        self.revert()
        (third,) = self.file(14)
        self.assertEqual((third.status, third.replaced), (dispatch.REPLACED, second.identifier))
        texts = [
            dispatch.queued_text(self.store, self.ledger.entries[filing.identifier], PRODUCTS)[0]
            for filing in (first, third)
        ]
        self.assertEqual(texts[0], texts[1])
        self.assertTrue(texts[0])

    def test_an_approval_of_an_item_already_replaced_counts_and_leaves_the_replacement_open(self):
        (first,) = self.file()
        self.revise()
        (second,) = self.file(7)
        late = exchange.Decision(first.identifier, exchange.APPROVE, None, None, "2026-10-18T19:00:00-07:00", None)
        self.ledger.take_decisions([late], "RUN2", NOW + timedelta(days=7))
        self.retouch()
        (filing,) = self.file(14)
        self.assertEqual(
            (filing.status, filing.identifier, filing.still_open), (dispatch.DONE, first.identifier, second.identifier)
        )
        self.assertEqual(
            filing.account(),
            f"reptoday-waitlist approved as `{first.identifier}`; never filed again; `{second.identifier}`, filed in"
            " its place before that approval was taken in, stays open, and no reviewed change replaces it",
        )
        self.assertEqual(self.ledger.entries[second.identifier]["status"], OPEN)
        self.decide(second.identifier, REJECTED)
        (after,) = self.file(21)
        self.assertEqual((after.status, after.identifier, after.still_open), (dispatch.DONE, first.identifier, None))
        self.assertEqual(len(self.ledger.entries), 2)

    def test_a_request_already_asked_by_another_item_is_not_filed(self):
        requests, _ = dispatch.load(self.repo, PRODUCTS)
        seen = {exchange.item_hash(requests[0].item): "20261004-agent-waitlist"}
        (filing,) = dispatch.file(self.ledger, self.store, requests, PRODUCTS, seen, "RUN", NOW)
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
        self.assertEqual(committed_rules(), RULES)


if __name__ == "__main__":
    unittest.main()
