"""Per-workflow run state: validation, the Review Queue reconciliation, Listening dedupe, and outreach cooldowns."""

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gr0wthlab import boundary, state
from gr0wthlab.areas import Areas
from gr0wthlab.state import ListeningState, OutreachState, ReviewQueueState, StateError, Tally
from tests.test_boundary import CONFIG, REGISTRY

H1, H2, H3 = "a" * 64, "b" * 64, "c" * 64


def entry(status, carried_over_from=None):
    record = {"status": status, "published_by_run": "RUN1", "published_at": "2026-10-11T23:00:00+00:00"}
    if carried_over_from:
        record.update(carried_over=True, carried_over_from=carried_over_from)
    return record


class KeysTest(unittest.TestCase):
    def test_a_thread_is_keyed_by_its_normalized_address(self):
        key = state.thread_key("https://www.reddit.com/r/fitness30plus/comments/abc/title/")
        self.assertEqual(key, state.thread_key("http://WWW.reddit.com/r/fitness30plus/comments/abc/title?utm=x#c1"))
        self.assertNotEqual(key, state.thread_key("https://www.reddit.com/r/fitness30plus/comments/abd/title/"))
        self.assertRegex(key, r"^[0-9a-f]{64}$")
        for bad in ("reddit.com/r/x", "ftp://host/x", ""):
            with self.subTest(bad=bad), self.assertRaises(StateError):
                state.thread_key(bad)

    def test_a_target_is_keyed_by_its_identifier_alone(self):
        self.assertEqual(state.target_key("creator:gmb-fitness"), state.target_key("  Creator:GMB-Fitness "))
        with self.assertRaises(StateError):
            state.target_key("   ")


class ListeningTest(unittest.TestCase):
    def test_each_thread_is_taken_once(self):
        listening = ListeningState()
        url = "https://www.reddit.com/r/getdisciplined/comments/xyz/lost_my_routine/"
        self.assertFalse(listening.seen(url))
        self.assertTrue(listening.mark(url, date(2026, 10, 11)))
        self.assertFalse(listening.mark(url + "?share=1", date(2026, 10, 18)))
        self.assertTrue(listening.seen(url))
        record = listening.as_json()
        self.assertEqual(list(record["read"].values()), [{"first_read": "2026-10-11", "last_read": "2026-10-18"}])
        self.assertNotIn("reddit", json.dumps(record))
        self.assertEqual(ListeningState.from_json(record).as_json(), record)

    def test_invalid_records_are_refused(self):
        for read in (
            {"x": {"first_read": "2026-10-11", "last_read": "2026-10-11"}},
            {H1: {"first_read": "2026-10-12", "last_read": "2026-10-11"}},
            {H1: {"first_read": "Oct 11", "last_read": "2026-10-11"}},
        ):
            with self.subTest(read=read), self.assertRaises(StateError):
                ListeningState.from_json({"read": read})


class OutreachTest(unittest.TestCase):
    TARGET = "creator:the-bioneer"

    def test_one_contact_then_at_most_one_follow_up_to_a_non_reply_after_the_wait(self):
        outreach = OutreachState()
        self.assertEqual(outreach.may_follow_up(self.TARGET, date(2026, 10, 20)), (False, "never contacted"))
        outreach.record_contact(self.TARGET, date(2026, 10, 12), wait_days=7)
        self.assertFalse(outreach.may_contact(self.TARGET)[0])
        with self.assertRaises(StateError):
            outreach.record_contact(self.TARGET, date(2026, 10, 13), wait_days=7)
        self.assertEqual(outreach.may_follow_up(self.TARGET, date(2026, 10, 18)), (False, "waiting until 2026-10-19"))
        self.assertTrue(outreach.may_follow_up(self.TARGET, date(2026, 10, 19))[0])
        outreach.record_follow_up(self.TARGET, date(2026, 10, 19))
        self.assertIn("no further contact", outreach.may_follow_up(self.TARGET, date(2026, 11, 30))[1])
        with self.assertRaises(StateError):
            outreach.record_follow_up(self.TARGET, date(2026, 11, 30))

    def test_a_reply_means_no_follow_up(self):
        outreach = OutreachState()
        outreach.record_contact(self.TARGET, date(2026, 10, 12), wait_days=7)
        outreach.record_reply(self.TARGET)
        self.assertIn("replied", outreach.may_follow_up(self.TARGET, date(2026, 11, 1))[1])
        with self.assertRaises(StateError):
            outreach.record_reply("creator:someone-else")

    def test_records_hold_hashes_and_never_a_second_follow_up(self):
        outreach = OutreachState()
        outreach.record_contact(self.TARGET, date(2026, 10, 12), wait_days=7)
        record = outreach.as_json()
        self.assertNotIn("bioneer", json.dumps(record))
        self.assertEqual(OutreachState.from_json(record).as_json(), record)
        good = {"contacted_on": "2026-10-12", "follow_up_after": "2026-10-19", "follow_ups": 0, "replied": False}
        for change in ({"follow_ups": 2}, {"follow_ups": True}, {"replied": "no"}, {"follow_up_after": "2026-10-01"}):
            with self.subTest(change=change), self.assertRaises(StateError):
                OutreachState.from_json({"targets": {H1: dict(good, **change)}})


class ReviewQueueTest(unittest.TestCase):
    def test_validation(self):
        good = {
            "handled": {"20261011-a": {"outcome": "rejected", "hash": H1}},
            "carried": {"20261011-b": {"hash": H2, "carried_over_from": "2026-10-11"}},
        }
        self.assertEqual(ReviewQueueState.from_json(good).as_json(), good)
        bad_cases = [
            {"handled": {"not-an-id": {"outcome": "rejected", "hash": H1}}},
            {"handled": {"20261011-a": {"outcome": "maybe", "hash": H1}}},
            {"handled": {"20261011-a": {"outcome": "approved", "hash": "short"}}},
            {"carried": {"20261011-b": {"hash": H2}}},
            {"carried": {"20261011-b": {"hash": H2, "carried_over_from": "Oct 11"}}},
            {
                "handled": {"20261011-a": {"outcome": "approved", "hash": H1}},
                "carried": {"20261011-a": {"hash": H1, "carried_over_from": "2026-10-11"}},
            },
            {"handled": ["20261011-a"]},
        ]
        for bad in bad_cases:
            with self.subTest(bad=bad), self.assertRaises(StateError):
                ReviewQueueState.from_json(bad)

    def test_reconcile_follows_the_ledger_and_carries_only_what_it_marks_carried_over(self):
        ledger = {
            "20261011-a": entry("rejected"),
            "20261011-b": entry("open", carried_over_from="2026-10-11"),
            "20261011-c": entry("open"),
        }
        hashes = {"20261011-a": H1, "20261011-b": H2, "20261011-c": H3}
        current, differences = state.reconcile(ReviewQueueState(), ledger, hashes)
        self.assertEqual(differences, [])
        self.assertEqual(current.handled, {"20261011-a": {"outcome": "rejected", "hash": H1}})
        self.assertEqual(current.carried, {"20261011-b": {"hash": H2, "carried_over_from": "2026-10-11"}})

    def test_the_ledger_wins_every_disagreement(self):
        previous = ReviewQueueState(
            handled={
                "20261011-a": {"outcome": "approved", "hash": H1},
                "20261011-gone": {"outcome": "approved", "hash": H3},
            },
            carried={"20261011-b": {"hash": H3, "carried_over_from": "2026-10-11"}},
        )
        ledger = {
            "20261011-a": entry("open", carried_over_from="2026-10-11"),
            "20261011-b": entry("open", carried_over_from="2026-10-11"),
        }
        current, differences = state.reconcile(previous, ledger, {"20261011-a": H1, "20261011-b": H2})
        self.assertEqual(current.handled, {})
        self.assertEqual(set(current.carried), {"20261011-a", "20261011-b"})
        joined = " | ".join(differences)
        self.assertIn("state had `20261011-a` approved; the Review Queue has it open", joined)
        self.assertIn("another fingerprint for `20261011-b`", joined)
        self.assertIn("`20261011-gone`, which the Review Queue does not hold", joined)


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(os.path.realpath(self.tmp.name)) / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        resolved = boundary.resolve_boundary(self.repo, CONFIG, REGISTRY, {}, self.repo.parent, git=[])
        self.areas = Areas(resolved)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_files_are_empty_states_and_saved_files_round_trip(self):
        states, invalid = state.load(self.areas)
        self.assertEqual(invalid, [])
        states.listening.mark("https://example.com/t/1", date(2026, 10, 11))
        state.save(self.areas, states, "RUN1", "2026-10-11T23:00:00+00:00")
        for workflow in state.WORKFLOWS:
            record = json.loads(state.state_path(self.areas, workflow).read_text(encoding="utf-8"))
            self.assertEqual((record["format"], record["workflow"], record["updated_by_run"]), (1, workflow, "RUN1"))
        again, invalid = state.load(self.areas)
        self.assertEqual(invalid, [])
        self.assertTrue(again.listening.seen("https://example.com/t/1"))

    def test_an_invalid_or_linked_file_is_reported_not_trusted(self):
        directory = self.repo / "workspace/run-reports/state"
        directory.mkdir(parents=True)
        (directory / "review-queue.json").write_text("{not json", encoding="utf-8")
        (directory / "listening.json").write_text(json.dumps({"format": 1, "workflow": "outreach"}), encoding="utf-8")
        elsewhere = self.repo.parent / "outreach.json"
        elsewhere.write_text(json.dumps({"format": 1, "workflow": "outreach", "targets": {}}), encoding="utf-8")
        os.symlink(str(elsewhere), str(directory / "outreach.json"))
        states, invalid = state.load(self.areas)
        self.assertEqual([workflow for workflow, _, _ in invalid], ["review-queue", "listening", "outreach"])
        self.assertEqual(states.outreach.targets, {})


class TallyTest(unittest.TestCase):
    def test_every_run_has_one_line_even_when_nothing_happened(self):
        quiet = [Tally("package-review", 15, 0, "15 files"), Tally("listening", 0, 0, "not built until US-ME13")]
        self.assertEqual(state.run_tally(quiet).line(), "checked=15 acted=0 note=nothing new needed action")
        busy = quiet + [Tally("review-queue", 6, 3, "2 decisions taken in, 1 queued")]
        self.assertEqual(
            state.run_tally(busy).line(), "checked=21 acted=3 note=review-queue 2 decisions taken in, 1 queued"
        )


if __name__ == "__main__":
    unittest.main()
