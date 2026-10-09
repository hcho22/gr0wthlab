"""The Review Queue ledger: stable identifiers, validation before queuing, decisions, carry-over, and order."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, exchange, state
from gr0wthlab.areas import Areas, Store
from gr0wthlab.queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger, QueueError
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY

PRODUCTS = ["RepToday", "Immerse"]
NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)


def decision(item, verdict="approve", reason=None, decided_at="2026-10-11T19:42:00-07:00"):
    return exchange.Decision(item, verdict, reason, None, decided_at, "2026-10-11")


class LedgerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(os.path.realpath(self.tmp.name)) / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        resolved = boundary.resolve_boundary(
            self.repo, CONFIG, REGISTRY, {}, self.repo.parent, git=[self.repo / ".git"]
        )
        self.areas = Areas(resolved)
        self.store = Store(resolved.ledger)
        self.incoming = self.repo / "workspace/review-queue/incoming"
        self.incoming.mkdir()
        self.ledger = Ledger()

    def tearDown(self):
        self.tmp.cleanup()

    def drop(self, name, text):
        path = self.incoming / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def take(self, run="RUN1", now=NOW):
        return self.ledger.take_incoming(self.areas, self.store, PRODUCTS, run, now)


class IncomingTest(LedgerTestCase):
    def test_a_valid_item_is_queued_under_a_stable_identifier(self):
        self.drop("name-status-stale.md", fakes.PROPOSAL)
        published, set_aside = self.take()
        self.assertEqual((published, set_aside), (["20261011-name-status-stale"], []))
        item = self.repo / "ledger/review-queue/items/20261011-name-status-stale.md"
        self.assertTrue(
            item.read_text(encoding="utf-8").startswith(
                f"---\nexchange: {exchange.EXCHANGE_VERSION}\nid: 20261011-name-status-stale\n"
            )
        )
        entry = self.ledger.entries["20261011-name-status-stale"]
        self.assertEqual(entry["status"], OPEN)
        self.assertEqual(entry["file"], "review-queue/items/20261011-name-status-stale.md")
        self.assertEqual(entry["product"], "RepToday")
        self.assertEqual(list(self.incoming.iterdir()), [])

    def test_a_repeated_slug_gets_a_new_identifier(self):
        self.drop("same.md", fakes.PROPOSAL)
        self.take()
        self.drop("same.md", fakes.PROPOSAL)
        published, _ = self.take("RUN2")
        self.assertEqual(published, ["20261011-same-2"])

    def test_malformed_files_are_set_aside_with_their_problems(self):
        self.drop("broken.md", fakes.PROPOSAL.replace("## Touches", "## Changes"))
        self.drop("Bad Name.md", fakes.PROPOSAL)
        self.drop("nested/deep.md", fakes.PROPOSAL)
        self.drop(".hidden.md", fakes.PROPOSAL)
        published, set_aside = self.take()
        self.assertEqual(published, [])
        names = {item.name: item for item in set_aside}
        self.assertEqual(set(names), {"broken.md", "Bad Name.md", "nested/deep.md", ".hidden.md"})
        self.assertTrue(any("sections must be exactly" in problem for problem in names["broken.md"].problems))
        self.assertEqual(names["nested/deep.md"].moved_to, "review-queue/set-aside/RUN1/nested--deep.md")
        self.assertTrue((self.repo / "ledger" / names["broken.md"].moved_to).is_file())
        self.assertEqual(list(self.incoming.iterdir()), [])

    def test_links_are_never_followed(self):
        secret = self.repo.parent / "secret.md"
        secret.write_text(fakes.PROPOSAL, encoding="utf-8")
        os.symlink(str(secret), str(self.incoming / "linked.md"))
        os.link(str(secret), str(self.incoming / "hard.md"))
        published, set_aside = self.take()
        self.assertEqual(published, [])
        self.assertEqual({item.name: item.moved_to for item in set_aside}, {"linked.md": "", "hard.md": ""})
        self.assertTrue(secret.is_file())
        self.assertFalse(any((self.repo / "ledger/review-queue/set-aside").rglob("*.md")))

    def test_an_item_that_asks_the_same_as_another_is_never_queued(self):
        self.drop("first.md", fakes.PROPOSAL)
        self.drop("second.md", fakes.PROPOSAL.replace("line 24", "line 25").replace("cleared", "  CLEARED "))
        seen = {}
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN1", NOW, seen)
        self.assertEqual(published, ["20261011-first"])
        self.assertIn("asks the same as 20261011-first, which is open", set_aside[0].problems[0])
        self.ledger.take_decisions([decision("20261011-first", "reject", "No.")], "RUN2", NOW)
        self.drop("again.md", fakes.PROPOSAL)
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN2", NOW, seen)
        self.assertEqual(published, [])
        self.assertIn("asks the same as 20261011-first, which is rejected", set_aside[0].problems[0])
        self.drop("reworded.md", fakes.proposal(title="record the name as searched and reserved"))
        published, _ = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN2", NOW, seen)
        self.assertEqual(published, ["20261011-reworded"])

    def test_supersedes_withdraws_an_open_item_only(self):
        self.drop("first.md", fakes.PROPOSAL)
        self.take()
        self.drop("second.md", fakes.proposal(extra="supersedes: 20261011-first\n"))
        published, set_aside = self.take("RUN2")
        self.assertEqual((published, set_aside), (["20261011-second"], []))
        first = self.ledger.entries["20261011-first"]
        self.assertEqual((first["status"], first["superseded_by"]), (SUPERSEDED, "20261011-second"))
        self.drop("third.md", fakes.proposal(extra="supersedes: 20261011-first\n"))
        published, set_aside = self.take("RUN3")
        self.assertEqual(published, [])
        self.assertIn("not an open item", set_aside[0].problems[0])


class DecisionsTest(LedgerTestCase):
    def setUp(self):
        super().setUp()
        for slug in ("a", "b", "c"):
            self.drop(f"{slug}.md", fakes.proposal(title=f"fix {slug}"))
        self.take()

    def test_each_decision_closes_its_item_once(self):
        outcomes = self.ledger.take_decisions(
            [decision("20261011-a"), decision("20261011-b", "reject", "No.")], "RUN2", NOW
        )
        self.assertEqual([outcome.status for outcome in outcomes], ["taken", "taken"])
        self.assertEqual(self.ledger.entries["20261011-a"]["status"], APPROVED)
        self.assertEqual(self.ledger.entries["20261011-b"]["status"], REJECTED)
        self.assertEqual([entry["id"] for entry in self.ledger.ordered()], ["20261011-c"])
        again = self.ledger.take_decisions([decision("20261011-a")], "RUN3", NOW)
        self.assertEqual(again[0].status, "already-taken")
        changed = self.ledger.take_decisions([decision("20261011-a", "reject", "Actually no.")], "RUN3", NOW)
        self.assertEqual(changed[0].status, "conflict")
        self.assertEqual(self.ledger.entries["20261011-a"]["status"], APPROVED)

    def test_unknown_items_and_decisions_on_superseded_items(self):
        self.drop("d.md", fakes.proposal(extra="supersedes: 20261011-c\n"))
        self.take("RUN2")
        self.drop("e.md", fakes.proposal(extra="supersedes: 20261011-d\n", title="fix e"))
        self.take("RUN3")
        outcomes = self.ledger.take_decisions(
            [decision("20261011-zzz"), decision("20261011-c", "reject", "No.")], "RUN4", NOW
        )
        self.assertEqual(
            {o.decision.item: o.status for o in outcomes},
            {"20261011-zzz": "unknown-item", "20261011-c": "taken"},
        )
        superseded = self.ledger.entries["20261011-c"]
        self.assertEqual((superseded["status"], superseded["decided"]), (SUPERSEDED, REJECTED))
        self.assertEqual([entry["id"] for entry in self.ledger.ordered()], ["20261011-a", "20261011-b", "20261011-e"])
        replaced = self.ledger.decided_replaced(self.ledger.entries["20261011-e"])
        self.assertEqual([entry["id"] for entry in replaced], ["20261011-c"])
        again = self.ledger.take_decisions([decision("20261011-c", "reject", "No.")], "RUN5", NOW)
        self.assertEqual(again[0].status, "already-taken")
        changed = self.ledger.take_decisions([decision("20261011-c")], "RUN5", NOW)
        self.assertEqual(changed[0].status, "conflict")
        self.assertEqual(superseded["decided"], REJECTED)


class OrderAndPersistenceTest(LedgerTestCase):
    def test_posts_by_nearest_slot_then_each_kind_oldest_first(self):
        self.drop("notice.md", fakes.proposal("notice"))
        self.drop("later-post.md", fakes.proposal("post", "slot: 2026-10-16T19:00-07:00\n", title="day 6"))
        self.drop("proposal.md", fakes.PROPOSAL)
        self.drop("sooner-post.md", fakes.proposal("post", "slot: 2026-10-15T02:00Z\n", title="day 5"))
        self.drop("message.md", fakes.proposal("message"))
        self.take()
        self.drop("old-request.md", fakes.proposal("dispatch-request"))
        self.drop("decision.md", fakes.proposal("weekly-read-decision"))
        self.take("RUN2", NOW + timedelta(days=7))
        order = [entry["id"][9:] for entry in self.ledger.ordered()]
        self.assertEqual(
            order, ["sooner-post", "later-post", "message", "decision", "old-request", "proposal", "notice"]
        )

    def test_an_item_carries_over_only_once_a_sitting_has_left_it_undecided(self):
        self.drop("first.md", fakes.PROPOSAL)
        [first] = self.take("20261011T230000Z-scheduled-aaaa")[0]
        self.drop("rerun.md", fakes.proposal(title="queued by a re-run before the sitting"))
        self.take("20261011T233000Z-on-demand-bbbb", NOW + timedelta(minutes=30))
        self.ledger.mark_carried_over({})
        self.assertEqual([entry["carried_over"] for entry in self.ledger.ordered()], [False, False])

        sitting = NOW.astimezone().date().isoformat()
        self.drop("after.md", fakes.proposal(title="queued after the sitting"))
        [after] = self.take("20261011T234500Z-on-demand-cccc", NOW + timedelta(minutes=45))[0]
        read_by = "20261011T234500Z-on-demand-cccc"
        self.ledger.mark_carried_over({"2026-10-01": read_by, sitting: read_by})
        entry = self.ledger.entries[first]
        self.assertEqual((entry["carried_over"], entry["carried_over_from"]), (True, sitting))
        entry = self.ledger.entries[after]
        self.assertEqual((entry["carried_over"], "carried_over_from" in entry), (False, False))

        self.ledger.take_decisions([decision(first)], "20261018T230000Z-scheduled-dddd", NOW)
        self.assertNotIn("carried_over_from", self.ledger.entries[first])

    def test_queue_json_round_trips(self):
        self.drop("old.md", fakes.PROPOSAL)
        self.take("RUN1")
        self.drop("new.md", fakes.PROPOSAL)
        self.take("RUN2", NOW + timedelta(days=7))
        self.ledger.take_decisions([decision("20261011-old")], "RUN2", NOW)
        self.drop("kept.md", fakes.PROPOSAL)
        self.take("RUN1")
        next_run = datetime(2026, 10, 18, 16, 0).astimezone()
        data = self.ledger.as_json("RUN2", NOW, "run-reports/RUN2.md", next_run)
        self.assertEqual(datetime.fromisoformat(data["next_run"]), next_run)
        self.assertEqual([entry["id"] for entry in data["open"]], ["20261011-kept", "20261018-new"])
        self.assertEqual([entry["id"] for entry in data["closed"]], ["20261011-old"])
        path = self.repo / "ledger/review-queue/queue.json"
        self.store.write_json(path, data)
        loaded = Ledger.load(path)
        self.assertEqual(sorted(loaded.entries), sorted(self.ledger.entries))
        self.assertEqual(loaded.entries["20261011-old"]["status"], APPROVED)

    def test_an_unreadable_ledger_is_not_overwritten(self):
        path = self.repo / "ledger/review-queue/queue.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(QueueError):
            Ledger.load(path)
        newer = {"exchange": exchange.EXCHANGE_VERSION + 1, "open": [], "closed": []}
        path.write_text(json.dumps(newer), encoding="utf-8")
        with self.assertRaises(QueueError):
            Ledger.load(path)

    def test_a_queue_and_its_items_still_read_after_a_version_bump(self):
        self.drop("first.md", fakes.PROPOSAL)
        [first] = self.take()[0]
        path = self.repo / "ledger/review-queue/queue.json"
        self.store.write_json(path, self.ledger.as_json("RUN1", NOW, "run-reports/RUN1.md", NOW))
        with mock.patch.object(exchange, "EXCHANGE_VERSION", exchange.EXCHANGE_VERSION + 1):
            loaded = Ledger.load(path)
            hashes, problems = state.item_hashes(
                self.repo / "ledger", loaded.entries, PRODUCTS, state.ReviewQueueState()
            )
        self.assertEqual(list(loaded.entries), [first])
        self.assertEqual((list(hashes), problems), ([first], []))
        self.assertEqual(len(Ledger.load(path.with_name("absent.json")).entries), 0)


if __name__ == "__main__":
    unittest.main()
