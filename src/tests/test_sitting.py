"""A sitting, without the browser: what the Founder is shown and what each act writes, on whole runs with a fake Codex.

US-ME07's Validation Test runs here end to end through the sitting's own logic: one item of each kind, two approved,
two rejected with reasons, two left, a sitting recorded, and a second run. So do the Beta Build gate and its counts,
a message sent and answered, and the filming plan. test_serve.py puts the same sitting behind its page.
"""

import json
import os
import re
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gr0wthlab import exchange, founder, sitting
from gr0wthlab.sitting import COUNTS, END, ITEM, START, Refused
from tests import fakes
from tests.test_cycle import CycleTestCase

WEEK = timedelta(days=7)
SOURCES = Path(__file__).resolve().parents[1] / "gr0wthlab"
# The evening of the first run's Sunday, when the Founder sits down: Sunday 2026-10-11 19:42 on the Mac's clock.
SITTING = datetime(2026, 10, 12, 2, 42, tzinfo=timezone.utc)
DAY = "2026-10-11"
KINDS = {
    "package-change-proposal": "name-status-stale",
    "dispatch-request": "waitlist",
    "weekly-read-decision": "angle-keep",
    "notice": "example-notice",
}


class SittingTestCase(CycleTestCase):
    def setUp(self):
        super().setUp()
        self.clock.set(fakes.SUNDAY_RUN)
        self.elapsed = 0.0
        self.week = 0

    def sit_down(self, at=SITTING):
        """The Founder starts the sitting command; its clock is the test's, and so is its measure of time."""
        self.at = at
        state = sitting.Sitting(self.repo, self.env, clock=lambda: self.at, elapsed=lambda: self.elapsed)
        state.begin()
        return state

    def one_of_each(self):
        """A first run that queues one item of each kind the Review Queue holds without filming."""
        writes = {
            f"review-queue/incoming/{slug}.md": fakes.proposal(kind, "", title=slug) for kind, slug in KINDS.items()
        }
        writes[fakes.draft_path(1)] = fakes.draft(1)
        creator = fakes.KIT_CREATORS[0]
        writes[fakes.message_path("creator", creator[0])] = fakes.message("creator", creator[0], fakes.CREATOR_BODY)
        fakes.set_run(self.repo, "outreach", {"creators": fakes.creators([creator])})
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 1)
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        fakes.set_window(self.repo, fakes.QUIET_WINDOW)
        fakes.behave(self.codex_dir, {})
        return {entry["kind"]: entry["id"] for entry in self.queue()["open"]}

    def one_proposal(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        fakes.behave(self.codex_dir, {})
        return "20261011-name-status-stale"

    def next_run(self, behavior=None):
        self.week += 1
        if behavior is not None:
            fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + self.week * WEEK)
        self.assertEqual(code, 0, out)
        return self.queue()

    def record(self, kind, stem):
        return json.loads((self.exchange / kind / f"{stem}.json").read_text(encoding="utf-8"))

    def records(self, kind="decisions"):
        return sorted(path.name for path in (self.exchange / kind).glob("*.json"))

    def refused(self, act, *args):
        """An act that must write nothing: its reasons, with every record left exactly as it was."""
        before = fakes.tree_digest(self.exchange)
        with self.assertRaises(Refused) as raised:
            act(*args)
        self.assertEqual(fakes.tree_digest(self.exchange), before, "a refused act writes nothing")
        return raised.exception.reasons


class WalkTest(SittingTestCase):
    def test_the_walk_is_the_queue_s_own_order_between_a_start_and_an_end(self):
        ids = self.one_of_each()
        view = self.sit_down().look()
        queue = self.queue()
        self.assertEqual(view.steps(), [(START, "")] + [(ITEM, entry["id"]) for entry in queue["open"]] + [(END, "")])
        self.assertEqual([entry.kind for entry in view.entries], [kind for kind in exchange.KINDS if kind in ids])
        self.assertEqual(view.after((START, "")), (ITEM, ids["post"]), "posts come first")
        self.assertEqual(view.after((ITEM, ids["notice"])), (END, ""))
        self.assertEqual(view.after((END, "")), (END, ""))
        self.assertEqual(view.before((ITEM, ids["post"])), (START, ""))
        self.assertEqual((view.run, view.report), (queue["updated_by_run"], queue["run_report"]))

    def test_it_opens_with_the_run_report_s_summary_as_lines_of_text(self):
        self.one_proposal()
        view = self.sit_down().look()
        report = self.report()
        summary = report.split("## Summary\n\n")[1].split("\n\n## ")[0].splitlines()
        self.assertEqual(view.summary, [line[2:] for line in summary])
        self.assertTrue(view.summary[0].startswith("checked=17 acted=1 note="))
        self.assertEqual(view.summary_problem, "")

    def test_each_item_is_shown_whole_with_what_it_touches_and_its_evidence(self):
        item = self.one_proposal()
        (entry,) = self.sit_down().look().entries
        self.assertEqual(
            (entry.id, entry.kind, entry.decided, entry.taken_in), (item, "package-change-proposal", False, False)
        )
        self.assertEqual(entry.item.ask, "Approve package change: record the name as cleared")
        self.assertEqual(entry.item.body, "Replace the stale caveat with the cleared status.")
        self.assertEqual(entry.item.touches, "- `projects/RepToday/gtm/02-brand/brand-guidelines.md`")
        self.assertIn("Cleared and reserved", entry.item.evidence)
        self.assertEqual(entry.entry["new_angle"], "no")

    def test_it_warns_while_the_weekly_run_due_has_not_finished(self):
        self.one_proposal()
        due = datetime.fromisoformat(self.queue()["next_run"])
        on_time = self.sit_down(due - timedelta(minutes=1)).look()
        self.assertFalse(on_time.overdue)
        late = self.sit_down(due + timedelta(minutes=1)).look()
        self.assertTrue(late.overdue)
        self.assertEqual(late.next_run, self.queue()["next_run"])

    def test_it_says_when_a_run_changed_the_queue_during_the_sitting(self):
        item = self.one_proposal()
        state = self.sit_down()
        self.assertFalse(state.look().changed)
        state.decide(item, "approve", "")
        self.next_run()
        view = state.look()
        self.assertTrue(view.changed)
        self.assertEqual(view.entries, [], "the run took the decision in, so the item is no longer asked")

    def test_a_checkout_no_run_has_written_a_queue_in_says_so(self):
        view = self.sit_down().look()
        self.assertEqual(view.queue_problem, "no run has written a Review Queue in this checkout yet")
        self.assertEqual(view.steps(), [(START, ""), (END, "")])

    def test_a_queue_or_an_item_that_cannot_be_read_is_said_and_nothing_can_be_decided_blind(self):
        item = self.one_proposal()
        state = self.sit_down()
        (self.ledger() / f"review-queue/items/{item}.md").write_text("not an item", encoding="utf-8")
        (entry,) = state.look().entries
        self.assertIsNone(entry.item)
        self.assertIn("the item must start with a --- front matter line", entry.problem)
        for verdict, line in (("approve", ""), ("reject", "Cannot read it.")):
            reasons = self.refused(state.decide, item, verdict, line)
            self.assertIn("this item's file cannot be shown", reasons[0])
        (self.ledger() / "review-queue/queue.json").write_text("{", encoding="utf-8")
        view = state.look()
        self.assertIn("the Review Queue could not be read", view.queue_problem)
        self.assertEqual(view.entries, [])

    def test_a_file_among_the_records_that_is_no_record_is_shown_as_one(self):
        self.one_proposal()
        (self.exchange / "decisions" / "notes.txt").write_text("approve it all")
        view = self.sit_down().look()
        self.assertEqual(view.stray, [("`founder/decisions/notes.txt`", "only <name>.json record files belong here")])

    def test_the_sitting_is_timed_from_its_first_page_in_whole_minutes(self):
        state = sitting.Sitting(self.repo, self.env, clock=lambda: SITTING, elapsed=lambda: self.elapsed)
        self.assertEqual(state.minutes(), 1, "before any page is shown")
        self.elapsed = 100.0
        state.begin()
        self.elapsed = 100.0 + 47 * 60 + 1
        state.begin()
        self.assertEqual(state.minutes(), 48)
        self.elapsed = 100.0 + 20 * 3600
        self.assertEqual(state.minutes(), sitting.MAX_MINUTES)
        self.assertEqual(state.day, DAY, "the sitting's date is the Mac's local date when it began")


class DecideTest(SittingTestCase):
    def test_what_the_founder_gives_is_exactly_what_is_written_and_read_back(self):
        item = self.one_proposal()
        state = self.sit_down()
        saved = state.decide(item, "approve", "  Good, go on.  ")
        expected = {
            "exchange": exchange.EXCHANGE_VERSION,
            "item": item,
            "decision": "approve",
            "reason": None,
            "note": "Good, go on.",
            "decided_at": "2026-10-11T19:42:00-07:00",
            "sitting": DAY,
        }
        self.assertEqual((saved.kind, saved.stem, saved.path), ("decisions", item, f"founder/decisions/{item}.json"))
        self.assertEqual(saved.record, expected)
        self.assertEqual(self.record("decisions", item), expected)
        self.assertEqual(self.records(), [f"{item}.json"])
        self.assertEqual(exchange.parse_decision(item, saved.record)[1], [], "a run reads it as it stands")
        (entry,) = state.look().entries
        self.assertEqual(
            (entry.decision.decision, entry.decision.note, entry.taken_in), ("approve", "Good, go on.", False)
        )

    def test_an_approval_needs_no_note_and_a_rejection_needs_its_reason(self):
        item = self.one_proposal()
        state = self.sit_down()
        self.assertIsNone(state.decide(item, "approve", "").record["note"])
        self.assertEqual(self.refused(state.decide, item, "reject", "   "), ["The reason is needed, in one line"])
        saved = state.decide(item, "reject", "Wait for counsel.")
        self.assertEqual(
            (saved.record["decision"], saved.record["reason"], saved.record["note"]),
            ("reject", "Wait for counsel.", None),
        )

    def test_every_limit_of_a_line_holds_at_entry_with_a_plain_reason(self):
        item = self.one_proposal()
        state = self.sit_down()
        self.assertEqual(len(state.decide(item, "reject", "r" * 300).record["reason"]), 300)
        cases = {
            "r" * 301: "The reason is 301 characters long; one line holds at most 300",
            "first\nsecond": "The reason must be one line",
            "first\rsecond": "The reason must be one line",
            f"Ask {fakes.ADDRESS} first.": f"The reason was refused: {sitting.HOLDS_ADDRESS}",
            "ping a@b": f"The reason was refused: {sitting.HOLDS_ADDRESS}",
        }
        for line, why in cases.items():
            with self.subTest(line=line[:20]):
                self.assertEqual(self.refused(state.decide, item, "reject", line), [why])
        self.assertEqual(
            self.refused(state.decide, item, "approve", f"cc {fakes.ADDRESS}"),
            [f"The note was refused: {sitting.HOLDS_ADDRESS}"],
        )
        self.assertEqual(self.record("decisions", item)["reason"], "r" * 300, "the last thing saved still stands")
        self.assertEqual(
            sitting.HOLDS_ADDRESS,
            "it holds something that looks like an email address; no record may hold an address or anything else about"
            " a person",
        )

    def test_only_approve_or_reject_of_an_open_item_is_a_decision(self):
        item = self.one_proposal()
        state = self.sit_down()
        for verdict in ("", "yes", "approved", "APPROVE", "approve ", "acknowledge"):
            with self.subTest(verdict=verdict):
                self.assertEqual(self.refused(state.decide, item, verdict, "x"), ["choose approve or reject"])
        for other in ("20261011-no-such-item", "../../evidence/x", "", f"{item}.json"):
            with self.subTest(item=other):
                self.assertEqual(
                    self.refused(state.decide, other, "approve", ""),
                    ["this item is not open in the Review Queue any more, so nothing was saved"],
                )

    def test_a_notice_is_acknowledged_with_the_same_record_as_an_approval(self):
        ids = self.one_of_each()
        saved = self.sit_down().decide(ids["notice"], "approve", "")
        self.assertEqual((saved.record["decision"], saved.record["note"]), ("approve", None))

    def test_a_decision_can_be_changed_or_taken_back_until_a_run_takes_it_in_and_never_after(self):
        item = self.one_proposal()
        state = self.sit_down()
        state.decide(item, "approve", "Fine.")
        self.at += timedelta(minutes=3)
        changed = state.decide(item, "reject", "On second thought, wait for counsel.")
        self.assertEqual(
            (
                changed.record["decision"],
                changed.record["reason"],
                changed.record["note"],
                changed.record["decided_at"],
            ),
            ("reject", "On second thought, wait for counsel.", None, "2026-10-11T19:45:00-07:00"),
        )
        state.take_back(item)
        self.assertEqual(self.records(), [], "taken back, the item is undecided again")
        self.assertFalse(state.look().entries[0].decided)
        state.take_back(item)
        state.decide(item, "approve", "After all.")

        queue = self.next_run()
        self.assertEqual([entry["status"] for entry in queue["closed"]], ["approved"])
        self.assertEqual(
            self.refused(state.decide, item, "reject", "Too late."),
            ["this item is not open in the Review Queue any more, so nothing was saved"],
        )
        self.assertEqual(
            self.refused(state.take_back, item),
            ["this item is not open in the Review Queue any more, so nothing was saved"],
        )
        self.assertEqual(self.record("decisions", item)["note"], "After all.")

    def test_a_decision_a_run_in_progress_has_taken_in_can_no_longer_be_changed(self):
        """A run takes a decision in before its agent starts and writes the queue only when it ends: in between, the
        queue still lists the item as open, and the decision's Evidence is what says it was taken in."""
        item = self.one_proposal()
        state = self.sit_down()
        state.decide(item, "approve", "Fine.")
        evidence = self.ledger() / "evidence" / "decisions" / f"{item}.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("{}", encoding="utf-8")
        (entry,) = state.look().entries
        self.assertTrue(entry.taken_in)
        why = ["a run has already taken in your decision on this item, so it can no longer be changed"]
        self.assertEqual(self.refused(state.decide, item, "reject", "Changed my mind."), why)
        self.assertEqual(self.refused(state.take_back, item), why)
        self.assertEqual(self.record("decisions", item)["decision"], "approve")

    def test_the_page_and_a_run_cannot_both_hold_the_records_at_once(self):
        item = self.one_proposal()
        state = self.sit_down()
        with founder.locked(self.ledger()):
            founder.LOCK_WAIT, kept = 0.2, founder.LOCK_WAIT
            try:
                reasons = self.refused(state.decide, item, "approve", "")
                self.assertEqual(
                    reasons, ["the Founder's records were locked for 0.2 seconds, so nothing was saved; try again"]
                )
                self.assertIn("so nothing was changed; try again", self.refused(state.take_back, item)[0])
            finally:
                founder.LOCK_WAIT = kept
        state.decide(item, "approve", "")

    def test_a_record_changed_by_hand_is_not_a_decision_and_deciding_again_replaces_it(self):
        item = self.one_proposal()
        state = self.sit_down()
        path = self.exchange / "decisions" / f"{item}.json"
        for damage, problem in (
            ("{", "it is not JSON"),
            (json.dumps({"exchange": 7, "item": item, "decision": "reject"}), "reason is required"),
            (json.dumps({"note": fakes.ADDRESS}), founder.HOLDS_ADDRESS),
        ):
            with self.subTest(damage=damage[:20]):
                path.write_text(damage, encoding="utf-8")
                (entry,) = state.look().entries
                self.assertFalse(entry.decided)
                self.assertIn(problem, entry.record_problem)
                saved = state.decide(item, "reject", "Wait for counsel.")
                self.assertEqual(saved.record["reason"], "Wait for counsel.")
                (entry,) = state.look().entries
                self.assertEqual((entry.decided, entry.record_problem), (True, ""))

    def test_a_decision_given_while_a_run_replaced_its_item_is_kept_under_the_rule_that_stood(self):
        """The page read the queue before a late run replaced the item, and the Founder decided what was shown. The
        record is kept on the replaced item, and the newer item stays open with the decision beside it."""
        old, new = self.one_proposal(), "20261011-name-status-cleared"
        state = self.sit_down()
        state.look()
        newer = fakes.proposal(extra=f"supersedes: {old}\n", title="record the name as cleared and reserved")
        # The run reads the Founder's records, then its agent works for minutes; the decision arrives meanwhile.
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-cleared.md": newer}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        (self.exchange / "decisions" / f"{old}.json").write_text(
            json.dumps(
                {
                    "exchange": exchange.EXCHANGE_VERSION,
                    "item": old,
                    "decision": "reject",
                    "reason": "Wait for counsel.",
                    "decided_at": "2026-10-11T16:20:00-07:00",
                    "sitting": DAY,
                }
            )
        )
        view = state.look()
        self.assertTrue(view.changed)
        self.assertEqual([entry.id for entry in view.entries], [new], "the page now shows the item that replaced it")
        self.assertEqual(
            self.refused(state.decide, old, "approve", ""),
            ["this item is not open in the Review Queue any more, so nothing was saved"],
        )
        queue = self.next_run({})
        closed = next(entry for entry in queue["closed"] if entry["id"] == old)
        self.assertEqual((closed["status"], closed["decided"]), ("superseded", "rejected"))
        self.assertEqual([entry["id"] for entry in queue["open"]], [new])
        evidence = json.loads((self.ledger() / f"evidence/decisions/{old}.json").read_text(encoding="utf-8"))
        self.assertEqual((evidence["reason"], evidence["superseded_by"]), ("Wait for counsel.", new))


class ValidationTest(SittingTestCase):
    """US-ME07's Validation Test, with the Founder's part done by the sitting and nothing written by hand."""

    def test_one_item_of_each_kind_two_approved_two_rejected_two_left_a_sitting_and_a_second_run(self):
        ids = self.one_of_each()
        self.assertEqual(sorted(ids), sorted(kind for kind in exchange.KINDS if kind != "filming-plan"))
        state = self.sit_down()
        self.assertEqual([entry.id for entry in state.look().entries][0], ids["post"])
        state.decide(ids["post"], "approve", "Good hook.")
        state.decide(ids["notice"], "approve", "")
        state.decide(ids["message"], "reject", "Too salesy for my network.")
        state.decide(ids["package-change-proposal"], "reject", "Wait for counsel.")
        self.elapsed = 41 * 60
        saved = state.record_sitting(str(state.minutes()), "")
        self.assertEqual(
            saved.record, {"exchange": exchange.EXCHANGE_VERSION, "date": DAY, "minutes": 41, "note": None}
        )
        view = state.look()
        self.assertEqual(
            {entry.kind: entry.decision.decision if entry.decision else None for entry in view.entries},
            {
                "post": "approve",
                "message": "reject",
                "weekly-read-decision": None,
                "dispatch-request": None,
                "package-change-proposal": "reject",
                "notice": "approve",
            },
        )

        second = self.next_run()
        self.assertEqual(
            [(entry["kind"], entry["carried_over"], entry.get("carried_over_from")) for entry in second["open"]],
            [("weekly-read-decision", True, DAY), ("dispatch-request", True, DAY)],
        )
        closed = {entry["id"]: entry for entry in second["closed"]}
        self.assertEqual(
            {kind: closed[ids[kind]]["status"] for kind in ("post", "notice", "message", "package-change-proposal")},
            {"post": "approved", "notice": "approved", "message": "rejected", "package-change-proposal": "rejected"},
        )
        evidence = self.ledger() / "evidence/decisions"
        rejected = json.loads((evidence / f"{ids['message']}.json").read_text(encoding="utf-8"))
        self.assertEqual(
            (rejected["decision"], rejected["reason"], rejected["sitting"], rejected["source"]["path"]),
            ("reject", "Too salesy for my network.", DAY, f"founder/decisions/{ids['message']}.json"),
        )
        self.assertEqual(
            json.loads((evidence / f"{ids['post']}.json").read_text(encoding="utf-8"))["note"], "Good hook."
        )
        report = self.report()
        self.assertIn("| Founder decisions | changed | 4 records, 4 new since the previous run |", report)
        self.assertIn("Reason: Wait for counsel.", report)
        self.assertIn(f"Sitting {DAY}: 41 minutes.", report)
        self.assertIn("rejected: Approve package change: name-status-stale. Reason: Wait for counsel.", self.brief())

        # Nothing decided is asked again: not at the next sitting, and not when the agent writes it again.
        later = self.sit_down(SITTING + WEEK)
        self.assertEqual(
            [entry.id for entry in later.look().entries], [ids["weekly-read-decision"], ids["dispatch-request"]]
        )
        self.assertTrue(all(entry.entry["carried_over"] for entry in later.look().entries))
        again = {"review-queue/incoming/again.md": fakes.proposal(title="name-status-stale")}
        third = self.next_run({"write": again})
        self.assertEqual(
            [entry["kind"] for entry in third["open"]], ["weekly-read-decision", "dispatch-request", "notice"]
        )
        notice = (self.ledger() / third["open"][2]["file"]).read_text(encoding="utf-8")
        self.assertIn(f"asks the same as {ids['package-change-proposal']}, which is rejected", notice)
        self.assertEqual(
            self.records(),
            sorted(f"{ids[kind]}.json" for kind in ("post", "notice", "message", "package-change-proposal")),
        )


class SittingRecordTest(SittingTestCase):
    def test_the_minutes_are_a_whole_number_the_founder_can_correct(self):
        self.one_proposal()
        state = self.sit_down()
        for minutes, why in (
            ("", "the minutes are needed, as a whole number from 1 to 600"),
            ("0", "The minutes must be a whole number from 1 to 600"),
            ("601", "The minutes must be a whole number from 1 to 600"),
            ("forty", "The minutes must be a whole number, written in digits"),
            ("4.5", "The minutes must be a whole number, written in digits"),
            ("-3", "The minutes must be a whole number, written in digits"),
            ("１２", "The minutes must be a whole number, written in digits"),
        ):
            with self.subTest(minutes=minutes):
                self.assertEqual(self.refused(state.record_sitting, minutes, ""), [why])
        self.assertEqual(
            self.refused(state.record_sitting, "40", f"call {fakes.ADDRESS}")[0][:20], "The note was refused"
        )
        self.assertEqual(state.record_sitting("48", "Short one.").record["minutes"], 48)
        corrected = state.record_sitting("52", "")
        self.assertEqual(
            corrected.record, {"exchange": exchange.EXCHANGE_VERSION, "date": DAY, "minutes": 52, "note": None}
        )
        self.assertEqual(self.records("sittings"), [f"{DAY}.json"])
        self.assertEqual(state.look().sitting.minutes, 52)

    def test_an_item_left_at_a_recorded_sitting_is_carried_over_from_it(self):
        self.one_proposal()
        state = self.sit_down()
        state.record_sitting("12", "")
        queue = self.next_run()
        self.assertEqual(
            [(entry["carried_over"], entry["carried_over_from"]) for entry in queue["open"]], [(True, DAY)]
        )
        self.assertIn(f"Sitting {DAY}: 12 minutes.", self.report())
        # A correction after the run changes the minutes it keeps, not which sitting the item was left at.
        state.record_sitting("15", "")
        queue = self.next_run()
        self.assertEqual(queue["open"][0]["carried_over_from"], DAY)
        kept = json.loads((self.ledger() / f"evidence/sittings/{DAY}.json").read_text(encoding="utf-8"))
        self.assertEqual((kept["minutes"], kept["source"]["path"]), (15, f"founder/sittings/{DAY}.json"))


class RecruitingTest(SittingTestCase):
    def setUp(self):
        super().setUp()
        fakes.beta_mandu(self.mandu)
        self.view = self.root / "RepToday-exports" / "waitlist-view.json"
        self.env["GR0WTHLAB_WAITLIST_VIEW"] = str(self.view)
        fakes.write_view(self.view, fakes.waitlist_view())

    def week_run(self, **drafts):
        self.week += 1
        at = fakes.SUNDAY_RUN + self.week * WEEK
        view = json.loads(self.view.read_text(encoding="utf-8"))
        view["generated_at"] = (at - timedelta(hours=1)).isoformat()
        fakes.write_view(self.view, view)
        paths = {"invitation": fakes.INVITATION, "ask": fakes.WAITLIST_ASK}
        fakes.behave(self.codex_dir, {"write": {paths[key]: text for key, text in drafts.items()}})
        code, out = self.run_cycle(at=at)
        self.assertEqual(code, 0, out)
        return self.queue()

    def test_the_gate_is_the_founders_own_word_on_the_page_and_nothing_before_it_starts_recruiting(self):
        """US-ME15's Validation Test: a run before the approval, the approval on the page, then a run."""
        fakes.behave(self.codex_dir, {"write": {fakes.INVITATION: fakes.beta_draft()}})
        self.run_cycle()
        self.assertEqual([entry for entry in self.queue()["open"] if entry["kind"] == "message"], [])
        self.assertIn("| Beta Build approval | skipped | not recorded", self.report())

        state = self.sit_down()
        view = state.look()
        self.assertEqual(
            [(found.product, found.build, found.open) for found in view.recruiting], [("RepToday", None, False)]
        )
        self.assertEqual(view.steps(), [(START, ""), (END, "")], "no counts are asked before recruiting")
        saved = state.record_beta_build("RepToday", "2026-10-09", "1.0 (42)")
        self.assertEqual(
            saved.record,
            {
                "exchange": exchange.EXCHANGE_VERSION,
                "product": "RepToday",
                "approved_on": "2026-10-09",
                "build": "1.0 (42)",
                "recruiting": "open",
                "stopped_on": None,
                "recorded_at": "2026-10-11T19:42:00-07:00",
            },
        )
        self.assertEqual(self.records("beta-builds"), ["RepToday.json"])
        self.assertIn((COUNTS, "RepToday"), state.look().steps())

        queue = self.week_run(invitation=fakes.beta_draft())
        (invitation,) = [entry for entry in queue["open"] if entry.get("beta") == "beta-invitation"]
        self.assertEqual(invitation["candidates"], fakes.GOOD_FIT_OPT_INS + fakes.OTHER_OPT_INS)
        report = self.report()
        self.assertIn("| Beta Build approval | changed | approved on 2026-10-09, build 1.0 (42), recorded", report)
        text = (self.ledger() / invitation["file"]).read_text(encoding="utf-8")
        self.assertIn("- The Beta Build approval the Founder recorded: `founder/beta-builds/RepToday.json`", text)
        self.assertNotIn("Mandu's exchange folder", text)
        self.assertNotIn("@", text.replace("@RepToday", ""))

    def test_an_approval_is_recorded_once_for_a_product_that_recruits_on_a_day_that_has_come(self):
        state = self.sit_down()
        for product, day, build, why in (
            ("Immerse", "2026-10-09", "", "Immerse is not a Product whose Beta Cohort gr0wthlab recruits"),
            ("NoSuch", "2026-10-09", "", "NoSuch is not a Product whose Beta Cohort gr0wthlab recruits"),
            ("RepToday", "", "", "The day Apple approved it is needed, as a date such as 2026-10-11"),
            ("RepToday", "2026-10-12", "", "The day Apple approved it is 2026-10-12, which has not come yet"),
            (
                "RepToday",
                "2026-02-30",
                "",
                "The day Apple approved it must be a real date written as YYYY-MM-DD, such as 2026-10-11",
            ),
            (
                "RepToday",
                "10/09/2026",
                "",
                "The day Apple approved it must be a real date written as YYYY-MM-DD, such as 2026-10-11",
            ),
            (
                "RepToday",
                "2026-10-09",
                "b" * 301,
                "The build's label is 301 characters long; one line holds at most 300",
            ),
        ):
            with self.subTest(product=product, day=day):
                self.assertEqual(self.refused(state.record_beta_build, product, day, build), [why])
        self.assertIn(
            "looks like an email address",
            self.refused(state.record_beta_build, "RepToday", "2026-10-09", f"ask {fakes.ADDRESS}")[0],
        )
        self.assertIsNone(state.record_beta_build("RepToday", "2026-10-11", "").record["build"])
        self.assertEqual(
            self.refused(state.record_beta_build, "RepToday", "2026-10-09", ""),
            ["a Beta Build is already recorded for RepToday; stop or reopen recruiting instead"],
        )

    def test_recruiting_is_stopped_and_reopened_with_the_approval_left_as_it_was(self):
        state = self.sit_down()
        self.assertEqual(
            self.refused(state.set_recruiting, "RepToday", True, DAY),
            ["no Beta Build is recorded for RepToday, so there is no recruiting to stop or reopen"],
        )
        state.record_beta_build("RepToday", "2026-10-09", "1.0 (42)")
        for day, why in (
            ("", "The day recruiting stopped is needed, as a date such as 2026-10-11"),
            ("2026-10-08", "recruiting cannot have stopped before the Beta Build was approved"),
            ("2026-10-12", "The day recruiting stopped is 2026-10-12, which has not come yet"),
        ):
            with self.subTest(day=day):
                self.assertEqual(self.refused(state.set_recruiting, "RepToday", True, day), [why])
        self.at += timedelta(minutes=5)
        stopped = state.set_recruiting("RepToday", True, DAY)
        self.assertEqual(
            (
                stopped.record["recruiting"],
                stopped.record["stopped_on"],
                stopped.record["approved_on"],
                stopped.record["build"],
            ),
            ("stopped", DAY, "2026-10-09", "1.0 (42)"),
        )
        self.assertEqual(stopped.record["recorded_at"], "2026-10-11T19:47:00-07:00")
        view = state.look()
        self.assertFalse(view.product("RepToday").open)
        self.assertNotIn((COUNTS, "RepToday"), view.steps(), "no counts are asked in the walk once recruiting stopped")
        reopened = state.set_recruiting("RepToday", False)
        self.assertEqual((reopened.record["recruiting"], reopened.record["stopped_on"]), ("open", None))
        self.assertEqual(self.records("beta-builds"), ["RepToday.json"])

    def test_a_count_left_blank_is_not_reported_and_never_zero(self):
        state = self.sit_down()
        self.assertEqual(
            self.refused(state.report_counts, "RepToday", {"accepted": "3"}),
            ["no Beta Build is recorded for RepToday, so there is no Beta Cohort to count"],
        )
        state.record_beta_build("RepToday", "2026-10-09", "")
        saved = state.report_counts("RepToday", {"invitations_sent": "10", "accepted": "", "sessions_booked": "   "})
        self.assertEqual(
            saved.record,
            {
                "exchange": exchange.EXCHANGE_VERSION,
                "product": "RepToday",
                "date": DAY,
                "invitations_sent": 10,
                "accepted": None,
                "sessions_booked": None,
                "recorded_at": "2026-10-11T19:42:00-07:00",
            },
        )
        text = (self.exchange / "beta-reports" / f"RepToday-{DAY}.json").read_text(encoding="utf-8")
        self.assertIn('"accepted": null', text)
        self.assertNotIn('"accepted": 0', text)
        # A field the request leaves out altogether is not reported either, and a typed zero is a zero.
        self.assertEqual(state.report_counts("RepToday", {"accepted": "0"}).record["invitations_sent"], None)
        self.assertEqual(self.record("beta-reports", f"RepToday-{DAY}")["accepted"], 0)
        for given, why in (
            ({}, "give at least one count; a count you leave blank is recorded as not reported, never zero"),
            (
                {"accepted": "", "invitations_sent": " "},
                "give at least one count; a count you leave blank is recorded as not reported, never zero",
            ),
            ({"accepted": "three"}, "Accepted must be a whole number, written in digits"),
            ({"accepted": "-1"}, "Accepted must be a whole number, written in digits"),
            ({"sessions_booked": "2.5"}, "Sessions booked must be a whole number, written in digits"),
            ({"invitations_sent": "1e3"}, "Invitations sent must be a whole number, written in digits"),
        ):
            with self.subTest(given=given):
                self.assertEqual(self.refused(state.report_counts, "RepToday", given), [why])
        today = state.look().product("RepToday").today
        self.assertEqual(dict(today.counts), {"invitations_sent": None, "accepted": 0, "sessions_booked": None})

    def test_the_counts_reach_the_run_as_the_founder_gave_them(self):
        state = self.sit_down()
        state.record_beta_build("RepToday", "2026-10-09", "1.0 (42)")
        self.week_run(invitation=fakes.beta_draft())
        later = self.sit_down(SITTING + WEEK)
        self.assertIn((COUNTS, "RepToday"), later.look().steps())
        later.report_counts("RepToday", {"invitations_sent": "2", "accepted": "1", "sessions_booked": ""})
        self.week_run(invitation=fakes.beta_draft())
        kept = json.loads((self.ledger() / "evidence/beta-recruiting/reports/RepToday-2026-10-18.json").read_text())
        self.assertEqual((kept["invitations_sent"], kept["accepted"], kept["sessions_booked"]), (2, 1, None))
        self.assertEqual(kept["not_reported"], ["sessions_booked"])
        self.assertEqual(kept["source"]["path"], "founder/beta-reports/RepToday-2026-10-18.json")
        self.assertIn(
            "- The Founder's counts, as reported on 2026-10-18: invitations sent 2, accepted 1, sessions booked not"
            " reported.",
            self.report(),
        )
        # A stop on the page withdraws what is open at the next run.
        later.set_recruiting("RepToday", True, "2026-10-18")
        queue = self.week_run()
        self.assertEqual([entry for entry in queue["open"] if entry.get("beta")], [])
        self.assertIn("the Founder stopped recruiting on 2026-10-18", self.report())


class OutreachTest(SittingTestCase):
    SLOW, DESK = "slow-strength", "desk-reset"

    def first_messages(self):
        creators = [fakes.KIT_CREATORS[0], fakes.KIT_CREATORS[2]]
        fakes.set_run(self.repo, "outreach", {"creators": fakes.creators(creators)})
        writes = {
            fakes.message_path("creator", key): fakes.message("creator", key, fakes.CREATOR_BODY) for key, _ in creators
        }
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        return {entry["message"]["to"]: entry["id"] for entry in self.queue()["open"] if entry["kind"] == "message"}

    def test_only_a_message_the_founder_approved_can_be_recorded_as_sent(self):
        ids = self.first_messages()
        state = self.sit_down()
        self.assertEqual(state.look().messages, [])
        why = ["this is not a message you approved, so nothing was saved"]
        self.assertEqual(self.refused(state.record_sent, ids[self.SLOW], DAY, "", "", ""), why)
        self.assertEqual(self.refused(state.record_sent, "20261011-no-such-item", DAY, "", "", ""), why)
        state.decide(ids[self.SLOW], "approve", "")
        state.decide(ids[self.DESK], "reject", "Not this one.")
        self.assertEqual(
            [message.id for message in state.look().messages], [ids[self.SLOW]], "approved at this sitting"
        )
        self.assertEqual(self.refused(state.record_sent, ids[self.DESK], DAY, "", "", ""), why)
        saved = state.record_sent(ids[self.SLOW], DAY, "", "", "")
        self.assertEqual(
            saved.record,
            {
                "exchange": exchange.EXCHANGE_VERSION,
                "item": ids[self.SLOW],
                "sent_on": DAY,
                "replied_on": None,
                "follow_up_wait_days": None,
                "note": None,
            },
        )

    def test_a_wait_is_set_only_on_the_message_a_follow_up_can_come_after(self):
        fakes.add_dispatches(self.repo, self.env)
        fakes.set_run(
            self.repo,
            "outreach",
            {"network_ask_source": "network", "creators": fakes.creators([fakes.KIT_CREATORS[0]])},
        )
        writes = {
            fakes.message_path("network-ask"): fakes.message("network-ask", "network", fakes.NETWORK_BODY),
            fakes.message_path("creator", self.SLOW): fakes.message("creator", self.SLOW, fakes.CREATOR_BODY),
        }
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        ids = {entry["message"]["purpose"]: entry["id"] for entry in self.queue()["open"] if entry["kind"] == "message"}
        state = self.sit_down()
        for item in ids.values():
            state.decide(item, "approve", "")
        self.assertEqual(
            {message.id: message.followed_up for message in state.look().messages},
            {ids["creator"]: True, ids["network-ask"]: False},
        )
        self.assertEqual(
            self.refused(state.record_sent, ids["network-ask"], DAY, "", "7", ""),
            ["no follow-up comes after this message, so it has no wait to set"],
        )
        self.assertIsNone(state.record_sent(ids["network-ask"], DAY, "", "", "").record["follow_up_wait_days"])
        self.assertEqual(state.record_sent(ids["creator"], DAY, "", "7", "").record["follow_up_wait_days"], 7)

    def test_every_limit_of_an_outreach_record_holds_at_entry(self):
        ids = self.first_messages()
        state = self.sit_down()
        item = ids[self.SLOW]
        state.decide(item, "approve", "")
        for given, why in (
            (("", "", "", ""), "The day it was sent is needed, as a date such as 2026-10-11"),
            (("2026-10-12", "", "", ""), "The day it was sent is 2026-10-12, which has not come yet"),
            (
                ("2026-13-01", "", "", ""),
                "The day it was sent must be a real date written as YYYY-MM-DD, such as 2026-10-11",
            ),
            (("2026-10-10", "2026-10-09", "", ""), "a reply cannot come before the message was sent"),
            (("2026-10-10", "2026-10-12", "", ""), "The day a reply came is 2026-10-12, which has not come yet"),
            (("2026-10-10", "", "0", ""), "The wait before a follow-up must be a whole number from 1 to 90"),
            (("2026-10-10", "", "91", ""), "The wait before a follow-up must be a whole number from 1 to 90"),
            (("2026-10-10", "", "a week", ""), "The wait before a follow-up must be a whole number, written in digits"),
            (("2026-10-10", "", "", "n" * 301), "The note is 301 characters long; one line holds at most 300"),
        ):
            with self.subTest(given=given):
                self.assertEqual(self.refused(state.record_sent, item, *given), [why])
        self.assertIn(
            "looks like an email address", self.refused(state.record_sent, item, DAY, "", "", f"to {fakes.ADDRESS}")[0]
        )
        saved = state.record_sent(item, "2026-10-10", "2026-10-11", "14", "Replied by video.")
        self.assertEqual(
            (
                saved.record["sent_on"],
                saved.record["replied_on"],
                saved.record["follow_up_wait_days"],
                saved.record["note"],
            ),
            ("2026-10-10", "2026-10-11", 14, "Replied by video."),
        )

    def test_a_follow_up_is_offered_only_for_the_message_sent_and_not_answered(self):
        """US-ME14's Validation Test: one creator who replied, one who did not, past the waiting period."""
        ids = self.first_messages()
        state = self.sit_down()
        for item in ids.values():
            state.decide(item, "approve", "")
        body = "Hello again. The early access offer stands, with nothing asked in return."
        follow_ups = {
            fakes.message_path("creator-follow-up", key): fakes.message("creator-follow-up", key, body, claims="none")
            for key in (self.SLOW, self.DESK)
        }
        queue = self.next_run({"write": follow_ups})
        self.assertEqual(
            [entry for entry in queue["open"] if entry["kind"] == "message"], [], "nothing shows either was sent"
        )
        self.assertIn("| Outreach records | skipped | no message has been recorded as sent yet |", self.report())

        after = self.sit_down(SITTING + WEEK)
        self.assertEqual(sorted(message.id for message in after.look().messages), sorted(ids.values()))
        after.record_sent(ids[self.SLOW], "2026-10-12", "", "", "")
        after.record_sent(ids[self.DESK], "2026-10-12", "2026-10-14", "", "")
        queue = self.next_run({"write": follow_ups})
        offered = [entry["message"] for entry in queue["open"] if entry["kind"] == "message"]
        self.assertEqual([(found["purpose"], found["to"]) for found in offered], [("creator-follow-up", self.SLOW)])
        report = self.report()
        self.assertIn("| Outreach records | read | 2 records |", report)
        self.assertIn("Desk Reset replied on 2026-10-14; a follow-up goes only to a non-reply", report)
        kept = [message.record.sent_on for message in after.look().messages]
        self.assertEqual(kept, ["2026-10-12", "2026-10-12"])


class FilmingTest(SittingTestCase):
    """The filming plan is decided like any item, and a post that shows a video is approved with the file it shows."""

    def setUp(self):
        super().setUp()
        # The filming fixture of test_filming, on this case's own checkout.
        fakes.set_filming(self.repo, True)
        shutil.copytree(str(fakes.FILMING / "files" / "mandu"), str(self.mandu), dirs_exist_ok=True)
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        platforms = self.repo / "config" / "platforms.json"
        data = json.loads(platforms.read_text(encoding="utf-8"))
        data["video"]["text"]["font_file"] = str(self.root / "font.ttf")
        (self.root / "font.ttf").write_text("a font")
        platforms.write_text(json.dumps(data), encoding="utf-8")
        self.footage = self.root / "footage"
        self.env.update(fakes.install_video_tools(self.root / "video-tools"), GR0WTHLAB_FOOTAGE_DIR=str(self.footage))
        self.runs = 0

    def run_ok(self, writes=None, days=None):
        if days is not None:
            fakes.keep_days(self.mandu, *days)
        fakes.behave(self.codex_dir, {"write": writes or {}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=self.runs))
        self.runs += 1
        self.assertEqual(code, 0, out)
        return self.queue()

    def test_the_plan_is_approved_on_the_page_and_the_video_it_allows_is_approved_with_its_copy(self):
        from tests.test_filming import DAY_1, PLAN

        queue = self.run_ok(days=(1, 8))
        self.assertIn("filming-plan", [entry["kind"] for entry in queue["open"]])
        state = self.sit_down()
        (plan,) = [entry for entry in state.look().entries if entry.kind == "filming-plan"]
        self.assertEqual((plan.id, plan.kind, plan.video), (PLAN, "filming-plan", None))
        self.assertIn("## Plan", (self.ledger() / plan.entry["file"]).read_text(encoding="utf-8"))
        state.decide(PLAN, "approve", "Film it Saturday.")

        fakes.fake_clip(self.footage / "window-1" / "d01-s1.mov", 14.0)
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        self.assertEqual(next(entry for entry in queue["closed"] if entry["id"] == PLAN)["status"], "approved")
        (post,) = [entry for entry in queue["open"] if entry["kind"] == "post"]
        self.assertTrue(post["asset"].startswith("assets/window-1/day-01-"))

        (shown,) = [entry for entry in state.look().entries if entry.kind == "post"]
        self.assertEqual(shown.video.path, self.ledger() / post["asset"])
        self.assertEqual((shown.video.problem, shown.may_approve()), ("", ""))
        saved = state.decide(post["id"], "approve", "")
        self.assertEqual(saved.record["decision"], "approve")
        state.take_back(post["id"])

        # The file the Founder would watch must be the file the run measured: anything else cannot be approved.
        video = self.ledger() / post["asset"]
        kept = video.read_bytes()
        video.write_bytes(kept + b"another cut")
        (shown,) = [entry for entry in state.look().entries if entry.kind == "post"]
        self.assertEqual(shown.video.problem, f"`{post['asset']}` is not the file this post was queued with")
        reasons = self.refused(state.decide, post["id"], "approve", "")
        self.assertIn("so the video and its copy cannot be approved", reasons[0])
        self.assertEqual(state.decide(post["id"], "reject", "The cut is wrong.").record["decision"], "reject")
        state.take_back(post["id"])
        video.unlink()
        (shown,) = [entry for entry in state.look().entries if entry.kind == "post"]
        self.assertIn("could not be read: No such file or directory", shown.video.problem)
        self.refused(state.decide, post["id"], "approve", "")
        video.write_bytes(kept)
        (shown,) = [entry for entry in state.look().entries if entry.kind == "post"]
        self.assertEqual(shown.video.problem, "")

    def test_a_video_is_only_ever_a_plain_file_of_the_ledger_s_own_assets(self):
        state = self.sit_down()
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"x")
        assets = self.ledger() / "assets" / "window-1"
        assets.mkdir(parents=True)
        (assets / "linked.mp4").symlink_to(outside)
        for asset, why in (
            ("../outside.mp4", "the Review Queue names no file of the finished videos for it"),
            ("/etc/passwd", "the Review Queue names no file of the finished videos for it"),
            ("review-queue/queue.json", "the Review Queue names no file of the finished videos for it"),
            ("assets/../founder/decisions/x.mp4", "the Review Queue names no file of the finished videos for it"),
            ("assets/window-1/linked.mp4", "its file is not a plain file in the finished videos"),
        ):
            with self.subTest(asset=asset):
                found = state.video({"kind": "post", "asset": asset, "asset_sha256": "0" * 64})
                self.assertEqual((found.path, found.problem), (None, why))
        self.assertIsNone(state.video({"kind": "post"}))
        self.assertIsNone(state.video({"kind": "message", "asset": "assets/window-1/linked.mp4"}))


class OnlyTheSittingWritesTest(unittest.TestCase):
    """The first rule of the invariant, read from the source: one module makes a Writer, and no other code reaches
    into the Founder's records to write, move, or remove anything."""

    def sources(self):
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(SOURCES.glob("*.py"))}

    def test_only_the_sitting_command_makes_a_writer(self):
        makers = [name for name, text in self.sources().items() if re.search(r"\bWriter\(", text)]
        self.assertEqual(makers, ["sitting.py"], "founder.Writer is made in sitting.py and nowhere else")
        self.assertEqual(len(re.findall(r"\bWriter\(", self.sources()["sitting.py"])), 1)

    def test_only_the_sitting_command_asks_the_writer_to_write_or_remove(self):
        users = [name for name, text in self.sources().items() if re.search(r"\bwriter\.(write|remove)\(", text)]
        self.assertEqual(users, ["sitting.py"])

    def test_the_run_never_imports_the_sitting_command(self):
        """The weekly run, its checks, and the boundary check hold no code that could write a record: the modules a
        run is made of never import sitting, page, or serve."""
        for name, text in self.sources().items():
            if name in ("sitting.py", "page.py", "serve.py", "cli.py"):
                continue
            with self.subTest(module=name):
                self.assertIsNone(re.search(r"^\s*(from|import)\b.*\b(sitting|serve|page)\b", text, re.MULTILINE))

    def test_the_sitting_command_starts_no_process_and_opens_no_connection(self):
        """No model, no agent, and no network in a sitting: its three modules import nothing that could reach one."""
        for name in ("sitting.py", "page.py", "serve.py"):
            text = self.sources()[name]
            with self.subTest(module=name):
                for banned in ("subprocess", "urllib.request", "http.client", "fetch", "codex", "launcher", "process"):
                    self.assertIsNone(
                        re.search(rf"^\s*(from|import)\b.*\b{re.escape(banned)}\b", text, re.MULTILINE), banned
                    )
        self.assertNotIn("connect(", self.sources()["serve.py"])


class StartTest(SittingTestCase):
    def test_a_sitting_refuses_to_start_where_a_run_would(self):
        from gr0wthlab.boundary import ConfigError

        self.env["GR0WTHLAB_EXCHANGE_DIR"] = str(self.root / "exchange")
        with self.assertRaises(ConfigError) as raised:
            self.sit_down()
        self.assertIn("GR0WTHLAB_EXCHANGE_DIR is set", str(raised.exception))
        del self.env["GR0WTHLAB_EXCHANGE_DIR"]
        os.rename(self.exchange / "sittings", self.exchange / "sittings-away")
        with self.assertRaises(ConfigError) as raised:
            self.sit_down()
        self.assertIn("founder/sittings must be a real folder", str(raised.exception))
