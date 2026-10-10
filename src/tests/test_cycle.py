"""Whole runs with a fake Codex: snapshot, decisions, Review Queue, run report, and the production clone's records."""

import fcntl
import io
import json
import os
import plistlib
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import cli, cycle, exchange, launcher, package
from gr0wthlab.areas import Store
from gr0wthlab.report import next_due
from tests import fakes


class CycleTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.env = fakes.git_env(self.root)
        self.home = self.root / "home"
        (self.home / ".codex").mkdir(parents=True)
        self.repo = fakes.make_repo(self.root / "gr0wthlab", self.env)
        self.mandu = fakes.make_mandu(self.root / "Mandu")
        self.exchange = self.root / "exchange"
        self.codex_dir = self.root / "codex-bin"
        codex = fakes.install_codex(self.codex_dir)
        self.logs = self.root / "logs"
        self.env.update(
            GR0WTHLAB_CODEX_BIN=str(codex),
            GR0WTHLAB_LOG_DIR=str(self.logs),
            GR0WTHLAB_MANDU_DIR=str(self.mandu),
            GR0WTHLAB_REPTODAY_DIR=str(self.root / "RepToday"),
            GR0WTHLAB_IMMERSE_DIR=str(self.root / "Immerse"),
            GR0WTHLAB_EXCHANGE_DIR=str(self.exchange),
            GR0WTHLAB_PRODUCTION_CLONE=str(self.root / "production"),
        )
        self.clock = fakes.Clock(fakes.SUNDAY_RUN)

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp.name):
            for name in dirs + files:
                path = os.path.join(root, name)
                if not os.path.islink(path):
                    os.chmod(path, 0o755)
        self.tmp.cleanup()

    def run_cycle(self, repo=None, trigger="on-demand", execve=None, at=None):
        if at is not None:
            self.clock.set(at)
        out = io.StringIO()
        runner = cycle.Cycle(repo or self.repo, self.env, self.home, out, self.clock)
        kwargs = {"execve": execve} if execve else {}
        code = runner.run(None, trigger, None, ["run"], **kwargs)
        return code, out.getvalue()

    def workspace(self, repo=None):
        return (repo or self.repo) / "workspace"

    def ledger(self, repo=None):
        return (repo or self.repo) / "ledger"

    def queue(self, repo=None):
        return json.loads((self.ledger(repo) / "review-queue/queue.json").read_text(encoding="utf-8"))

    def report(self, repo=None):
        reports = sorted((self.ledger(repo) / "run-reports").glob("2*Z-*.md"))
        reports = [path for path in reports if not path.name.endswith(".brief.md")]
        return reports[-1].read_text(encoding="utf-8")

    def brief(self, repo=None):
        return sorted((self.ledger(repo) / "run-reports").glob("*.brief.md"))[-1].read_text(encoding="utf-8")

    def decide(self, item, decision, reason=None, note=None):
        folder = self.exchange / "decisions"
        folder.mkdir(parents=True, exist_ok=True)
        record = {
            "exchange": exchange.EXCHANGE_VERSION,
            "item": item,
            "decision": decision,
            "reason": reason,
            "note": note,
            "decided_at": "2026-10-11T19:42:00-07:00",
            "sitting": "2026-10-11",
        }
        (folder / f"{item}.json").write_text(json.dumps(record), encoding="utf-8")

    def sit(self, day=None):
        """Mandu's record of a sitting, by default on the Mac's local date of the first run."""
        day = day or fakes.SUNDAY_RUN.astimezone().strftime("%Y-%m-%d")
        folder = self.exchange / "sittings"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{day}.json").write_text(
            json.dumps({"exchange": exchange.EXCHANGE_VERSION, "date": day, "minutes": 41}), encoding="utf-8"
        )
        return day


class FirstRunTest(CycleTestCase):
    def test_snapshot_proposal_queue_and_report(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        ledger = self.ledger()

        snapshots = list((ledger / "evidence/package-snapshots").glob("*.json"))
        self.assertEqual(len(snapshots), 1)
        snapshot = json.loads(snapshots[0].read_text(encoding="utf-8"))
        files = snapshot["products"]["RepToday"]["files"]
        self.assertEqual(len(files), 12)
        self.assertTrue(all(len(entry["sha256"]) == 64 and entry["read_at"] for entry in files))
        self.assertNotIn("projects/RepToday", json.dumps([entry.get("text") for entry in files]))

        queue = self.queue()
        self.assertEqual([entry["id"] for entry in queue["open"]], ["20261011-name-status-stale"])
        self.assertFalse(queue["open"][0]["carried_over"])
        next_run = datetime.fromisoformat(queue["next_run"])
        self.assertEqual(next_run, next_due(datetime.fromisoformat(queue["updated_at"]), ("sunday", "16:00")))
        self.assertTrue(timedelta(0) < next_run - datetime.fromisoformat(queue["updated_at"]) <= timedelta(days=7))
        item = (ledger / "review-queue/items/20261011-name-status-stale.md").read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(item, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertEqual(list((self.workspace() / "review-queue/incoming").iterdir()), [])

        report = self.report()
        self.assertIn(
            "## Summary\n\n- checked=13 acted=1 note=package-review 12 files, 0 changed, 0 failed; 1 proposal queued\n",
            report,
        )
        self.assertIn("- listening: checked=0 acted=0 note=not built until US-ME13", report)
        for workflow in ("review-queue", "listening", "outreach"):
            self.assertTrue((ledger / f"run-reports/state/{workflow}.json").is_file(), workflow)
        self.assertIn("On demand, started", report)
        self.assertIn("| RepToday package: `projects/RepToday/gtm/05-social-pmf/angles.md` | read |", report)
        self.assertIn("| Mandu decisions | skipped | no Review Queue item is waiting for a decision yet |", report)
        self.assertIn("| YouTube results | skipped | not connected until US-ME11 |", report)
        self.assertIn("First snapshot", report)
        self.assertRegex(report, r"Approximate cost: about \$0\.00[89] at API prices, for 200,000 input tokens")
        self.assertIn("> Checked the package.", report)
        self.assertNotIn("Notice:", report)
        self.assertIn("Run brief, read it first:", (self.codex_dir / "prompt.txt").read_text(encoding="utf-8"))

    def test_a_quiet_run_still_says_what_it_checked(self):
        self.run_cycle()
        self.assertIn("- checked=12 acted=0 note=nothing new needed action\n", self.report())

    def test_an_invalid_run_state_is_set_aside_rebuilt_and_reported(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        (self.ledger() / "run-reports/state/review-queue.json").write_text("{broken", encoding="utf-8")
        day = self.sit()
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        notice = next(e for e in self.queue()["open"] if e["kind"] == "notice")
        text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn("the review-queue run state was not valid", text)
        rebuilt = json.loads((self.ledger() / "run-reports/state/review-queue.json").read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["carried"]["20261011-name-status-stale"]["carried_over_from"], day)

    def test_state_files_the_launcher_sets_aside_are_not_reported_as_the_agent_s(self):
        self.run_cycle()
        for path in (self.ledger() / "run-reports/state").iterdir():
            path.write_text("{broken", encoding="utf-8")
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn("the review-queue run state was not valid", report)
        self.assertNotIn("which the agent", report)

    def test_the_agent_sees_its_brief(self):
        self.run_cycle()
        prompt = (self.codex_dir / "prompt.txt").read_text(encoding="utf-8")
        brief = Path(prompt.split("Run brief, read it first: ")[1].split()[0])
        text = brief.read_text(encoding="utf-8")
        self.assertIn("## Package files", text)
        cadence = self.mandu / "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
        self.assertIn(f"`{cadence}` | read: first snapshot", text)
        self.assertIn("a Product's own repository holds its code, never its package", text)
        self.assertIn("check-incoming", text)
        self.assertIn("written with your file-editing tool (apply_patch)", text)


class DecisionRoundTripTest(CycleTestCase):
    KINDS = {
        "post": ("day-3-post", "slot: 2026-10-14T19:00-07:00\n"),
        "message": ("network-ask", ""),
        "package-change-proposal": ("name-status-stale", ""),
        "dispatch-request": ("waitlist", ""),
        "weekly-read-decision": ("angle-keep", ""),
        "notice": ("example-notice", ""),
    }

    def test_one_item_of_each_kind_two_approved_two_rejected_two_undecided(self):
        writes = {
            f"review-queue/incoming/{slug}.md": fakes.proposal(kind, extra, title=slug)
            for kind, (slug, extra) in self.KINDS.items()
        }
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        first = self.queue()
        self.assertEqual([entry["kind"] for entry in first["open"]], list(exchange.KINDS))
        ids = {entry["kind"]: entry["id"] for entry in first["open"]}

        self.decide(ids["post"], "approve", note="Good hook.")
        self.decide(ids["notice"], "approve")
        self.decide(ids["message"], "reject", reason="Too salesy for my network.")
        self.decide(ids["package-change-proposal"], "reject", reason="Wait for counsel.")
        day = self.sit()
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)

        second = self.queue()
        self.assertEqual(
            [(entry["kind"], entry["carried_over"]) for entry in second["open"]],
            [("weekly-read-decision", True), ("dispatch-request", True)],
        )
        closed = {entry["id"]: entry["status"] for entry in second["closed"]}
        self.assertEqual(closed[ids["post"]], "approved")
        self.assertEqual(closed[ids["message"]], "rejected")
        evidence = self.ledger() / "evidence/decisions"
        rejected = json.loads((evidence / f"{ids['message']}.json").read_text(encoding="utf-8"))
        self.assertEqual((rejected["decision"], rejected["reason"]), ("reject", "Too salesy for my network."))
        self.assertEqual(rejected["item_file"], f"review-queue/items/{ids['message']}.md")
        self.assertEqual(rejected["source"]["path"], str(self.exchange / f"decisions/{ids['message']}.json"))
        approved = json.loads((evidence / f"{ids['post']}.json").read_text(encoding="utf-8"))
        self.assertEqual(approved["note"], "Good hook.")
        self.assertTrue((self.ledger() / "evidence/sittings/2026-10-11.json").is_file())
        report = self.report()
        self.assertIn("| Mandu decisions | changed | 4 records, 4 new since the previous run |", report)
        self.assertIn("Reason: Wait for counsel.", report)
        self.assertIn(f"Sitting {day}: 41 minutes.", report)
        self.assertIn(f"carried over from the sitting on {day}", report)

        recorded = json.loads((self.ledger() / "run-reports/state/review-queue.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {key: value["outcome"] for key, value in recorded["handled"].items()},
            {
                ids["post"]: "approved",
                ids["notice"]: "approved",
                ids["message"]: "rejected",
                ids["package-change-proposal"]: "rejected",
            },
        )
        self.assertEqual(
            {key: value["carried_over_from"] for key, value in recorded["carried"].items()},
            {ids["dispatch-request"]: day, ids["weekly-read-decision"]: day},
        )
        self.assertIn("note=review-queue 4 decisions taken in", report)

        rejected_again = {"review-queue/incoming/again.md": fakes.proposal(title="name-status-stale")}
        fakes.behave(self.codex_dir, {"write": rejected_again})
        code, _ = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        third = self.queue()
        self.assertEqual([e["kind"] for e in third["open"]], ["weekly-read-decision", "dispatch-request", "notice"])
        notice = (self.ledger() / third["open"][2]["file"]).read_text(encoding="utf-8")
        self.assertIn(f"asks the same as {ids['package-change-proposal']}, which is rejected", notice)
        self.assertIn(f"carried over from the sitting on {day}", self.report())
        self.assertIn("4 records, 0 new since the previous run", self.report())
        self.assertIn("rejected: Approve package change: name-status-stale. Reason: Wait for counsel.", self.brief())

    def test_a_decision_on_an_item_superseded_before_it_was_taken_in_is_kept(self):
        old, new = "20261011-name-status-stale", "20261011-name-status-cleared"
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        newer = fakes.proposal(extra=f"supersedes: {old}\n", title="record the name as cleared and reserved")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-cleared.md": newer}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        self.decide(old, "reject", reason="Wait for counsel.")
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)

        evidence = json.loads((self.ledger() / f"evidence/decisions/{old}.json").read_text(encoding="utf-8"))
        self.assertEqual(
            (evidence["item"], evidence["decision"], evidence["reason"], evidence["superseded_by"]),
            (old, "reject", "Wait for counsel.", new),
        )
        queue = self.queue()
        self.assertEqual([entry["id"] for entry in queue["open"]], [new])
        closed = next(entry for entry in queue["closed"] if entry["id"] == old)
        self.assertEqual(
            (closed["status"], closed["decided"], closed["evidence"]),
            ("superseded", "rejected", f"evidence/decisions/{old}.json"),
        )
        ask = "Approve package change: record the name as cleared"
        self.assertIn(
            f"- Rejected `{old}`, which `{new}` replaced before this decision was taken in: {ask}."
            " Reason: Wait for counsel.",
            self.report(),
        )
        replaced = (
            f"- `{new}` (package-change-proposal): {ask} and reserved. It replaces `{old}`, which the Founder rejected:"
            f" {ask}. Reason: Wait for counsel."
        )
        self.assertIn(replaced, self.brief())

        self.assertIn("note=review-queue 1 decision taken in,", self.report())

        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], [new])
        self.assertIn("| Mandu decisions | read | 1 record, 0 new since the previous run |", self.report())
        self.assertIn(replaced, self.brief())

    def test_records_about_no_open_item_are_reported_once_until_they_change(self):
        old = "20261011-name-status-stale"
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        newer = fakes.proposal(extra=f"supersedes: {old}\n", title="record the name as cleared and reserved")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-cleared.md": newer}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        self.decide(old, "reject")
        self.decide("20261011-unknown", "approve")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        queue = self.queue()
        kinds = [entry["kind"] for entry in queue["open"]]
        self.assertEqual(kinds, ["package-change-proposal", "notice"])
        notice = (self.ledger() / queue["open"][1]["file"]).read_text(encoding="utf-8")
        self.assertIn("# Notice: 2 Mandu records could not be used on", notice)
        self.assertIn(f"`decisions/{old}.json`: reason is required", notice)
        self.assertIn("no queued item has this identifier", notice)
        self.assertNotIn("must replace", notice)

        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual([entry["kind"] for entry in self.queue()["open"]], kinds)
        report = self.report()
        self.assertIn(
            "| Mandu decisions | read | 2 records, 0 new since the previous run, 2 could not be used |", report
        )
        self.assertIn("- Not listed again: 2 records that could not be used, reported by an earlier run", report)
        self.assertNotIn("Could not use", report)

        self.decide("20261011-unknown", "approve", note="Rewritten, still about no item.")
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], kinds + ["notice"])
        notice = (self.ledger() / queue["open"][2]["file"]).read_text(encoding="utf-8")
        self.assertIn("`decisions/20261011-unknown.json`", notice)
        self.assertNotIn(old, notice)

    def test_a_malformed_decision_on_an_item_superseded_in_the_same_run_is_reported_once(self):
        old = "20261011-name-status-stale"
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide(old, "reject")
        newer = fakes.proposal(extra=f"supersedes: {old}\n", title="record the name as cleared and reserved")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-cleared.md": newer}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["package-change-proposal", "notice"])
        self.assertEqual(queue["open"][0]["supersedes"], old)
        notice = (self.ledger() / queue["open"][1]["file"]).read_text(encoding="utf-8")
        self.assertIn("# Notice: 1 Mandu record could not be used on", notice)
        self.assertIn(f"`decisions/{old}.json`: reason is required", notice)
        self.assertNotIn("must replace", notice)
        self.assertNotIn("must replace", self.report())

        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(len(self.queue()["open"]), 2)
        self.assertNotIn("Could not use", self.report())

    def test_a_missing_exchange_folder_keeps_what_was_already_reported(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide("20261011-unknown", "approve")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertIn("- Could not use `decisions/20261011-unknown.json`", self.report())
        away = self.exchange.with_name("exchange-away")
        self.exchange.rename(away)
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertIn("| Mandu decisions | failed |", self.report())
        away.rename(self.exchange)
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        report = self.report()
        self.assertNotIn("Could not use", report)
        self.assertIn("- Not listed again: 1 record that could not be used", report)

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_unreadable_decisions_folder_fails_only_its_own_source(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide("20261011-unknown", "approve")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertIn("- Could not use `decisions/20261011-unknown.json`", self.report())
        decisions = self.exchange / "decisions"
        decisions.chmod(0o300)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(f"| Mandu decisions | failed | `{decisions}` could not be read: Permission denied. |", report)
        self.assertIn("| Mandu sittings | read |", report)
        self.assertIn("| Founder decisions taken in | incomplete | Mandu decisions could not be read |", report)
        self.assertIn("| Review Queue | incomplete | Mandu decisions could not be read |", report)
        notice = (self.ledger() / self.queue()["open"][-1]["file"]).read_text(encoding="utf-8")
        self.assertIn("could not be read, so the work that needs them is incomplete", notice)
        self.assertIn("Permission denied", notice)

        decisions.chmod(0o755)
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        report = self.report()
        self.assertNotIn("Could not use", report)
        self.assertIn("- Not listed again: 1 record that could not be used", report)

    @unittest.skipIf(os.geteuid() == 0, "root can search any folder")
    def test_an_unsearchable_exchange_folder_fails_both_its_sources_with_the_reason(self):
        item = "20261011-name-status-stale"
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide(item, "approve")
        self.sit()
        self.exchange.chmod(0o600)
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        report = self.report()
        for folder in ("decisions", "sittings"):
            detail = f"`{self.exchange / folder}` could not be read: Permission denied."
            self.assertIn(f"| Mandu {folder} | failed | {detail} |", report)
        self.assertEqual([entry["id"] for entry in self.queue()["open"] if entry["kind"] != "notice"], [item])

    def test_an_unreadable_review_queue_matches_no_decision_and_still_takes_in_sittings(self):
        item = "20261011-name-status-stale"
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide(item, "approve")
        day = self.sit()
        (self.ledger() / "review-queue/queue.json").write_text("{", encoding="utf-8")
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(
            "| Mandu decisions | skipped | the Review Queue could not be read, so no decision could be matched to its"
            " item |",
            report,
        )
        self.assertIn(
            "| Founder decisions taken in | incomplete | the ledger could not be read; no decision was matched |",
            report,
        )
        self.assertNotIn("Could not use", report)
        self.assertFalse((self.ledger() / f"evidence/decisions/{item}.json").exists())
        self.assertIn("| Mandu sittings | changed | 1 record, 1 new |", report)
        self.assertTrue((self.ledger() / f"evidence/sittings/{day}.json").is_file())

    def test_a_malformed_decision_on_an_open_item_is_reported_every_run_until_replaced(self):
        item = "20261011-name-status-stale"
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide(item, "reject")
        fakes.behave(self.codex_dir, {})
        for week in (1, 2):
            self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7 * week))
            queue = self.queue()
            self.assertEqual(
                [entry["kind"] for entry in queue["open"]], ["package-change-proposal"] + ["notice"] * week
            )
            notice = (self.ledger() / queue["open"][week]["file"]).read_text(encoding="utf-8")
            self.assertIn("# Notice: 1 decision in Mandu could not be taken in on", notice)
            self.assertIn(f"`decisions/{item}.json`, for `{item}`: reason is required", notice)
            self.assertIn("Mandu must replace each with a valid record of the same decision", notice)
            self.assertIn(f"Mandu must replace it with a valid record of the decision on `{item}`", self.report())

        self.decide(item, "reject", reason="Wait for counsel.")
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice", "notice"])
        closed = next(entry for entry in queue["closed"] if entry["id"] == item)
        self.assertEqual((closed["status"], closed["reason"]), ("rejected", "Wait for counsel."))
        report = self.report()
        self.assertIn("| Mandu decisions | changed | 1 record, 1 new since the previous run |", report)
        self.assertNotIn("Could not use", report)

    def test_a_missing_exchange_folder_fails_once_items_wait(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        report = self.report()
        self.assertIn("| Mandu decisions | failed | Mandu's exchange folder", report)
        self.assertIn("| Founder decisions taken in | incomplete | Mandu decisions could not be read |", report)
        self.assertIn("| Review Queue | incomplete | Mandu decisions could not be read |", report)


class CarryOverTest(CycleTestCase):
    def test_an_item_carries_over_only_once_a_sitting_has_left_it_undecided(self):
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        self.assertEqual([entry["carried_over"] for entry in self.queue()["open"]], [False])
        self.assertIn("(0 new this run, 0 carried over)", self.report())

        day = self.sit()
        after = {"review-queue/incoming/after.md": fakes.proposal(title="queued after the sitting")}
        fakes.behave(self.codex_dir, {"write": after})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=45))
        carried = {entry["id"]: entry.get("carried_over_from") for entry in self.queue()["open"]}
        self.assertEqual(carried, {"20261011-name-status-stale": day, "20261011-after": None})
        self.assertIn(
            f"`20261011-name-status-stale` (package-change-proposal, carried over from the sitting on {day})",
            self.report(),
        )
        self.assertIn("1 new this run, 1 carried over", self.report())

        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        carried = {entry["id"]: entry.get("carried_over_from") for entry in self.queue()["open"]}
        self.assertEqual(carried, {"20261011-name-status-stale": day, "20261011-after": None})


class RunLockTest(CycleTestCase):
    def hold_lock(self, repo):
        held = (self.ledger(repo) / cycle.LOCK_FILE).open("a")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return held

    def test_a_run_started_while_another_runs_is_refused_and_the_next_report_says_so(self):
        with self.hold_lock(self.repo):
            code, out = self.run_cycle(trigger="scheduled")
        self.assertEqual(code, cycle.EXIT_BUSY)
        self.assertIn("refusing to start: another run is in progress", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())
        self.assertFalse((self.ledger() / "review-queue/queue.json").exists())

        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=5))
        self.assertEqual(code, 0, out)
        self.assertRegex(
            self.report(), r"\n- Run \S+-scheduled-\S+ \(scheduled\) was refused at .*: another run was in progress\.\n"
        )
        self.assertEqual(list((self.ledger() / cycle.NOTES_DIR).iterdir()), [])
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10))
        self.assertNotIn("was refused", self.report())

    def test_each_checkout_has_its_own_lock_and_refused_runs(self):
        other = fakes.make_repo(self.root / "worktree", self.env)
        with self.hold_lock(other):
            code, out = self.run_cycle(trigger="scheduled")
            self.assertEqual(code, 0, out)
            self.assertEqual(self.run_cycle(repo=other, at=fakes.SUNDAY_RUN + timedelta(minutes=5))[0], cycle.EXIT_BUSY)
        with self.hold_lock(self.repo):
            refused, _ = self.run_cycle(trigger="scheduled", at=fakes.SUNDAY_RUN + timedelta(minutes=10))
            self.assertEqual(refused, cycle.EXIT_BUSY)
        self.run_cycle(repo=other, at=fakes.SUNDAY_RUN + timedelta(minutes=15))
        self.assertEqual(re.findall(r"\(([a-z-]+)\) was refused", self.report(other)), ["on-demand"])
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=20))
        self.assertEqual(re.findall(r"\(([a-z-]+)\) was refused", self.report()), ["scheduled"])


class FailuresTest(CycleTestCase):
    def test_a_failed_source_becomes_a_notice_and_marks_its_outputs_incomplete(self):
        angles = self.mandu / "projects/RepToday/gtm/05-social-pmf/angles.md"
        angles.unlink()
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(
            "| RepToday package: `projects/RepToday/gtm/05-social-pmf/angles.md` | failed | missing. |", report
        )
        angles = "RepToday package: `projects/RepToday/gtm/05-social-pmf/angles.md` could not be read"
        self.assertIn(f"| Package review (contradictions) | incomplete | {angles} |", report)
        self.assertIn(f"| Package snapshot | incomplete | {angles} |", report)
        self.assertIn("| Founder decisions taken in | complete |", report)
        self.assertIn("- review-queue: checked=0 acted=1 note=0 decisions taken in, 1 other item queued,", report)
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice"])
        notice = (self.ledger() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("could not be read, so the work that needs them is incomplete", notice)
        self.assertIn("Post Drafts", notice)
        self.assertIn("Weekly Read memo", notice)
        brief = next((self.ledger() / "run-reports").glob("*.brief.md")).read_text(encoding="utf-8")
        self.assertIn("A failed source blocks only the work that needs it", brief)
        self.assertIn("Review every other package file as usual", brief)
        self.assertIn(
            "angles.md`: missing. Incomplete without it: Package snapshot, Package review (contradictions), Post",
            brief,
        )

    def test_the_same_problems_are_not_queued_twice(self):
        (self.mandu / "projects/RepToday/gtm/05-social-pmf/angles.md").unlink()
        self.exchange.mkdir()
        self.run_cycle()
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        self.assertEqual([entry["kind"] for entry in self.queue()["open"]], ["notice"])
        self.assertIn("are listed in the notice `20261011-notice-run-problems`", self.report())

    def test_a_malformed_item_is_set_aside_as_a_notice_not_dropped(self):
        broken = fakes.PROPOSAL.replace("## Evidence", "## Sources")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/broken.md": broken}})
        self.run_cycle()
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice"])
        kept = list((self.ledger() / "review-queue/set-aside").rglob("broken.md"))
        self.assertEqual(len(kept), 1)
        notice = (self.ledger() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("`broken.md`: sections must be exactly", notice)

    def test_look_alikes_in_the_agent_s_areas_never_change_the_launcher_s_records(self):
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        forged = {"exchange": exchange.EXCHANGE_VERSION, "open": [], "closed": []}
        writes = {
            "review-queue/queue.json": json.dumps(forged),
            "evidence/decisions/20261011-name-status-stale.json": "{}",
        }
        fakes.behave(self.codex_dir, {"write": writes})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], ["20261011-name-status-stale"])
        self.assertFalse((self.ledger() / "evidence/decisions/20261011-name-status-stale.json").exists())

    def test_a_link_or_file_in_place_of_incoming_is_noted_and_repaired(self):
        self.exchange.mkdir()
        outside = self.root / "outside"
        (outside / "empty").mkdir(parents=True)
        replacements = {
            "a link": {"symlink": {"review-queue/incoming": str(outside)}},
            "a file": {"write": {"review-queue/incoming": "not a folder"}},
        }
        incoming = self.workspace() / "review-queue/incoming"
        day = f"{fakes.SUNDAY_RUN.astimezone():%Y%m%d}"
        for number, (case, behavior) in enumerate(replacements.items()):
            with self.subTest(case=case):
                fakes.behave(self.codex_dir, dict(behavior, rmtree=["review-queue/incoming"]))
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=20 * number))
                self.assertEqual(code, 0, out)
                self.assertEqual(sorted(path.name for path in outside.iterdir()), ["empty"])
                self.assertTrue(incoming.is_dir() and not incoming.is_symlink())
                report = self.report()
                problem = "`review-queue/incoming` was not a folder"
                self.assertIn(f"- {problem}", report.partition("\n## Launcher problems\n")[2])
                named = re.search(r"listed in the notice `([^`]+)`", report)
                self.assertIsNotNone(named, report)
                notice = next(entry for entry in self.queue()["open"] if entry["id"] == named.group(1))
                self.assertIn(problem, (self.ledger() / notice["file"]).read_text(encoding="utf-8"))

                slug = f"after-{number}"
                write = {f"review-queue/incoming/{slug}.md": fakes.proposal(title=f"queued after {case}")}
                fakes.behave(self.codex_dir, {"write": write})
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=20 * number + 10))
                self.assertEqual(code, 0, out)
                self.assertIn(f"{day}-{slug}", [entry["id"] for entry in self.queue()["open"]])

    def test_an_area_replaced_by_a_link_is_never_followed_and_stops_the_next_run(self):
        outside = self.root / "outside"
        (outside / "decisions").mkdir(parents=True)
        (outside / "decisions/20261011-x.json").write_text("{}", encoding="utf-8")
        fakes.behave(self.codex_dir, {"rmtree": ["evidence"], "symlink": {"evidence": str(outside)}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(
            sorted(str(path.relative_to(outside)) for path in outside.rglob("*")),
            ["decisions", "decisions/20261011-x.json"],
        )
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10))
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG)
        self.assertIn("writable area evidence", out)

    @unittest.skipIf(os.geteuid() == 0, "root can search any folder")
    def test_an_unsearchable_package_folder_fails_only_its_own_sources(self):
        for folder in ("gtm/06-channels", "gtm/02-brand"):
            (self.mandu / "projects/RepToday" / folder).chmod(0o600)
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        for path in ("gtm/06-channels/plan.md", "gtm/02-brand/brand-guidelines.md"):
            self.assertIn(f"| RepToday package: `projects/RepToday/{path}` | failed | Permission denied. |", report)
        self.assertIn("| RepToday package: `projects/RepToday/gtm/07-thesis/plan.md` | read |", report)
        self.assertIn("| Package review (contradictions) | incomplete |", report)
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice"])
        notice = (self.ledger() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("brand-guidelines.md`: Permission denied.", notice)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_access_the_agent_removed_is_restored_and_reported_before_anything_is_taken_in(self):
        behavior = {
            "write": {
                "review-queue/incoming/name-status-stale.md": fakes.PROPOSAL,
                "drafts/sub/draft.md": "a draft\n",
                "instructions/README.md": "edited\n",
            },
            "chmod": {"review-queue/incoming": "300", "drafts/sub": "000", "instructions/README.md": "000"},
        }
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        problems = self.report().partition("\n## Launcher problems\n")[2]
        restored = "was left without its owner's read and write access, so the launcher restored it"
        for entry in ("workspace/drafts/sub", "workspace/instructions/README.md", "workspace/review-queue/incoming"):
            self.assertIn(f"- `{entry}` {restored}", problems)
        self.assertEqual((self.workspace() / "drafts/sub/draft.md").read_text(encoding="utf-8"), "a draft\n")
        self.assertEqual((self.workspace() / "instructions/README.md").read_text(encoding="utf-8"), "edited\n")
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["package-change-proposal", "notice"])
        notice = (self.ledger() / queue["open"][1]["file"]).read_text(encoding="utf-8")
        self.assertIn(f"`workspace/drafts/sub` {restored}", notice)

    def test_a_named_pipe_the_agent_leaves_does_not_stall_the_run(self):
        incoming = self.workspace() / "review-queue/incoming"
        incoming.mkdir()
        os.mkfifo(str(incoming / "pipe.md"))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.lexists(str(incoming / "pipe.md")))
        self.assertIn("Set aside, not queued: `pipe.md`: unreadable", self.report())

    def test_an_agent_failure_is_reported_and_its_valid_items_still_queue(self):
        fakes.behave(
            self.codex_dir,
            {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}, "exit": 1},
        )
        code, _ = self.run_cycle()
        self.assertEqual(code, 1)
        kinds = [entry["kind"] for entry in self.queue()["open"]]
        self.assertEqual(kinds, ["package-change-proposal", "notice"])
        self.assertIn("The agent stopped with exit code 1", self.report())

    def test_a_review_the_agent_did_not_finish_is_incomplete_and_never_a_quiet_week(self):
        summary = "I could not complete this run's review, and I queued nothing."
        accounts = {
            "says it did not finish": (
                f"{summary}\n\nReview: incomplete: the rules pass is unfinished.\n",
                "the agent did not finish its review: the rules pass is unfinished",
                "did not finish reviewing the Go-To-Market Package (the rules pass is unfinished), so",
            ),
            "never says it finished": (
                summary,
                "the agent did not confirm that it finished every pass",
                "did not confirm that it finished every pass of its review of the Go-To-Market Package, so",
            ),
        }
        for number, (case, (text, gap, told)) in enumerate(accounts.items()):
            with self.subTest(case=case):
                fakes.behave(self.codex_dir, {"summary": text})
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7 * number))
                self.assertEqual(code, 0, out)
                report = self.report()
                self.assertIn(f"| Package review (contradictions) | incomplete | {gap} |", report)
                self.assertIn(
                    " acted=1 note=package-review 12 files, 0 changed, 0 failed; 0 proposals queued;"
                    f" incomplete: {gap}; review-queue 0 decisions taken in, 1 other item queued,",
                    report.partition("\n- ")[2].partition("\n")[0],
                )
                named = re.search(r"listed in the notice `([^`]+)`", report)
                self.assertIsNotNone(named, report)
                notice = next(entry for entry in self.queue()["open"] if entry["id"] == named.group(1))
                self.assertEqual(notice["kind"], "notice")
                text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
                self.assertIn(told, text)

    def test_a_finished_review_is_complete_however_long_the_summary(self):
        summary = "Traced every recorded outcome.\n\n" + "x" * cycle.SUMMARY_LIMIT + "\n\nReview: complete\n"
        fakes.behave(self.codex_dir, {"summary": summary})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn("| Package review (contradictions) | complete | the agent finished its review |", report)
        self.assertIn("- checked=12 acted=0 note=nothing new needed action\n", report)
        self.assertEqual(self.queue()["open"], [])

    def test_a_late_scheduled_run_says_so(self):
        due = datetime(2026, 10, 11, 16, 0).astimezone()
        self.run_cycle(trigger="scheduled", at=(due + timedelta(minutes=1)).astimezone(timezone.utc))
        self.assertIn("started on time", self.report())
        self.run_cycle(trigger="scheduled", at=(due + timedelta(hours=3)).astimezone(timezone.utc))
        self.assertIn("Started late:", self.report())
        self.assertIn("3 h 0 min after its time", self.report())

    def test_the_launch_agent_lateness_and_next_run_all_follow_run_json(self):
        path = self.repo / "config/run.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["schedule"].update(day="wednesday", time="09:30")
        path.write_text(json.dumps(config), encoding="utf-8")
        stdout = io.TextIOWrapper(io.BytesIO())
        with (
            mock.patch.dict(os.environ, self.env),
            mock.patch.object(cli, "REPO_ROOT", self.repo),
            mock.patch.object(cli, "ENTRY", self.repo / "src/bin/gr0wthlab"),
            mock.patch.object(sys, "stdout", stdout),
        ):
            self.assertEqual(cli.main(["launch-agent"]), 0)
        agent = plistlib.loads(stdout.buffer.getvalue())
        self.assertEqual(agent["StartCalendarInterval"], {"Weekday": 3, "Hour": 9, "Minute": 30})
        command = cli.parser().parse_args(agent["ProgramArguments"][1:])
        self.assertEqual((command.command, command.trigger, command.once), ("run", "scheduled", None))

        code, out = self.run_cycle(trigger="scheduled", at=datetime(2026, 10, 14, 12, 30).astimezone(timezone.utc))
        self.assertEqual(code, 0, out)
        self.assertIn("Started late: due Wednesday 2026-10-14 09:30", self.report())
        next_run = datetime.fromisoformat(self.queue()["next_run"])
        self.assertEqual(next_run, datetime(2026, 10, 21, 9, 30).astimezone())

    def test_the_run_refuses_a_task_definition_outside_src_instructions(self):
        out = io.StringIO()
        runner = cycle.Cycle(self.repo, self.env, self.home, out, self.clock)
        code = runner.run(self.repo / "workspace/instructions/x.md", "on-demand", None, [])
        self.assertEqual(code, 2)
        self.assertIn("src/instructions", out.getvalue())


class NotesTest(CycleTestCase):
    def test_a_report_that_cannot_be_written_is_named_in_the_next_one(self):
        original = Store.write_text

        def refuse_reports(store, path, text):
            if path.parent.name == "run-reports" and not path.name.endswith(".brief.md"):
                raise PermissionError(1, "Operation not permitted", str(path))
            original(store, path, text)

        with mock.patch.object(Store, "write_text", refuse_reports):
            code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn("could not write its report", out)
        reports = [path for path in (self.ledger() / "run-reports").glob("2*Z-*.md") if ".brief." not in path.name]
        self.assertEqual(reports, [])
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10))
        self.assertRegex(self.report(), r"\n- Run \S+ could not write its report `run-reports/\S+\.md`: ")
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=20))
        self.assertNotIn("could not write its report", self.report())

    def test_a_run_that_cannot_finish_stops_and_the_next_report_says_so(self):
        def fail_after_the_agent(events):
            self.clock.set(self.clock.moment + timedelta(minutes=20))
            raise PermissionError(1, "Operation not permitted")

        with mock.patch.object(cycle.report, "token_usage", fail_after_the_agent):
            code, out = self.run_cycle(trigger="scheduled")
        self.assertEqual(code, cycle.EXIT_STOPPED)
        self.assertIn("the run stopped: [Errno 1] Operation not permitted", out)
        [record] = self.logs.glob("2*Z-*.json")
        started = datetime.fromisoformat(json.loads(record.read_text(encoding="utf-8"))["started_at"])
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        self.assertIn(
            f"Run {record.stem} (scheduled), started {cycle.report.wall_clock(started):%A %Y-%m-%d %H:%M}, stopped"
            " before it finished: [Errno 1] Operation not permitted.",
            self.report(),
        )

    def test_a_run_that_stops_before_its_snapshot_is_named_too(self):
        with mock.patch.object(package, "record", side_effect=PermissionError(1, "Operation not permitted")):
            code, _ = self.run_cycle()
        self.assertEqual(code, cycle.EXIT_STOPPED)
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10))
        self.assertRegex(self.report(), r"\n- Run \S+-on-demand-\S+ \(on-demand\), started .*, stopped before it")


class WaitlistRunTest(CycleTestCase):
    """US-ME06's validation test through the launcher, with the view in a temporary folder outside every checkout."""

    def setUp(self):
        super().setUp()
        self.view = self.root / "RepToday-exports" / "waitlist-view.json"
        self.env["GR0WTHLAB_WAITLIST_VIEW"] = str(self.view)
        self.exchange.mkdir()
        fakes.mac_time_zone(self)

    def assert_no_address_anywhere(self):
        """Every output of every run so far: the records, the agent's areas, the logs, and what the agent was told."""
        for place in (self.ledger(), self.workspace(), self.logs, self.codex_dir):
            for path in place.rglob("*"):
                if path.is_file():
                    data = path.read_bytes()
                    for part in (fakes.ADDRESS, "jane", "example.com"):
                        self.assertNotIn(part.encode(), data, path)

    def test_the_clean_seed_is_counted_then_the_address_bearing_variant_is_refused(self):
        fakes.write_view(self.view, fakes.waitlist_view())
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        (evidence,) = (self.ledger() / "evidence/waitlist").glob("*.json")
        record = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(len(record["entries"]), 12)
        self.assertEqual(record["progress"], {"good_fit_opt_ins": 5, "bar": 50})
        self.assertEqual([week["sign_ups"] for week in record["weeks"]], [5, 7])
        self.assertEqual(record["cumulative"]["by_source"]["tiktok"]["good_fit_opt_ins"], 2)
        report = self.report()
        for line in (
            "| Waitlist anonymous view | read | generated 2026-10-11T22:00:00+00:00: sign-ups 12, good-Fit opt-ins 5"
            " of about 50 |",
            "- Waitlist: 12 sign-ups, 7 of them in the week of 2026-10-05; 5 good-Fit opt-ins of about 50, 10% of the"
            " way.",
            "| 2026-09-28 | 5 | 3 | 3 | 2 |",
            "| 2026-10-05 | 7 | 3 | 5 | 3 |",
            "| All weeks | 12 | 6 | 8 | 5 |",
            "| tiktok | 2 | 4 | 3 | 3 | 2 |",
            "| unknown | 1 | 1 | 0 | 1 | 0 |",
            "| lost-the-routine | 3 | 6 | 5 |",
            "| unknown | 2 | 2 | 1 |",
            "Read the view generated 2026-10-11T22:00:00+00:00, 1 h 0 min before this run started; Waitlist Evidence:"
            f" `evidence/waitlist/{evidence.name}`.",
            f"| Waitlist counts | complete | `evidence/waitlist/{evidence.name}` |",
            "- waitlist: checked=12 acted=0 note=12 sign-ups counted; 5 good-Fit opt-ins of about 50, 10% of the way",
        ):
            self.assertIn(line, report)
        self.assertIn(f"`{evidence}`", self.brief())
        prompt = (self.codex_dir / "prompt.txt").read_text(encoding="utf-8")
        self.assertNotIn(str(self.view), prompt + self.brief())
        self.assert_no_address_anywhere()

        fakes.write_view(self.view, fakes.address_variant())
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        self.assertEqual(list((self.ledger() / "evidence/waitlist").glob("*.json")), [evidence])
        report = self.report()
        self.assertIn(
            "| Waitlist anonymous view | refused | something in the view looked like an email address"
            " (entry 3, a field outside the format); the whole read was discarded and nothing from it was kept |",
            report,
        )
        self.assertIn("- Waitlist refused, a Guardrail breach (G6): the view held something", report)
        self.assertIn("## Waitlist\n\nRefused, a Guardrail breach (G6):", report)
        self.assertIn("| Waitlist counts | incomplete | the read was refused, as the view held what looks like", report)
        (notice,) = [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]
        self.assertEqual(notice["ask"][:56], "Notice: Guardrail breach, the Waitlist view held an emai")
        self.assertIn(
            f"- waitlist: checked=0 acted=1 note=read refused; breach notice `{notice['id']}` queued;", report
        )
        text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn("it recorded no Waitlist count or other Waitlist Evidence, and no address was stored", text)
        self.assertIn("- entry 3, a field outside the format", text)
        self.assertEqual(exchange.check_item(text, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertIn("- Refused: the view held something that looks like an email address", self.brief())
        self.assert_no_address_anywhere()

        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=2))
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], [notice["id"]])

    def test_no_view_yet_is_skipped_because_the_build_has_not_landed(self):
        del self.env["GR0WTHLAB_WAITLIST_VIEW"]
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        reason = "RepToday's Waitlist build has not landed, so no view location is configured yet (US-ME05)"
        report = self.report()
        self.assertIn(f"| Waitlist anonymous view | skipped | {reason} |", report)
        self.assertIn(f"| Waitlist counts | skipped | {reason} |", report)
        self.assertIn(f"- Waitlist skipped: {reason}.", report)
        self.assertIn(f"## Waitlist\n\nSkipped: {reason}.", report)
        self.assertIn(f"- Skipped: {reason}; there are no counts yet.", self.brief())
        self.assertEqual(self.queue()["open"], [])
        self.assertFalse((self.ledger() / "evidence/waitlist").exists())

    def test_an_unusable_view_fails_with_a_notice(self):
        self.view.parent.mkdir()
        self.view.write_text("{not json", encoding="utf-8")
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(f"| Waitlist anonymous view | failed | `{self.view}` is not valid JSON (line 1). |", report)
        self.assertIn("| Waitlist counts | incomplete | Waitlist anonymous view could not be read |", report)
        (notice,) = self.queue()["open"]
        text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn("Incomplete: Waitlist counts, Weekly Read memo, Beta Cohort recruiting.", text)
        self.assertFalse((self.ledger() / "evidence/waitlist").exists())

    def test_an_old_view_is_counted_and_the_report_says_how_old_it_is(self):
        early = [entry for entry in fakes.WAITLIST_ENTRIES if entry[4] <= "2026-10-08"]
        fakes.write_view(self.view, fakes.waitlist_view("2026-10-08T22:00:00+00:00", early))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn("- Waitlist: 9 sign-ups, 4 of them in the week of 2026-10-05;", report)
        self.assertIn("generated 2026-10-08T22:00:00+00:00, 3 d 1 h 0 min before this run started;", report)
        self.assertEqual(len(list((self.ledger() / "evidence/waitlist").glob("*.json"))), 1)

    def test_a_winter_sunday_run_reports_the_week_ending_at_that_sitting(self):
        """From November the Sunday 16:00 run starts at 00:00 UTC on Monday, and so may the view it reads."""
        entries = [(f"Entry{n:02d}", "tiktok", "lost-the-routine", True, f"2026-11-0{2 + n % 7}") for n in range(30)]
        fakes.write_view(self.view, fakes.waitlist_view("2026-11-09T00:00:05+00:00", entries))
        code, out = self.run_cycle(at=datetime(2026, 11, 9, 0, 0, 10, tzinfo=timezone.utc))
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn("- Waitlist: 30 sign-ups, 30 of them in the week of 2026-11-02;", report)
        self.assertIn("| Source | Week of 2026-11-02 | All weeks | Good Fit | Opted in | Good-Fit opt-ins |", report)
        self.assertIn("| tiktok | 30 | 30 | 30 | 30 | 30 |", report)

    def test_a_view_the_sandbox_could_read_stops_the_run_before_it_starts(self):
        self.env["GR0WTHLAB_WAITLIST_VIEW"] = str(self.mandu / "exports/waitlist-view.json")
        code, out = self.run_cycle()
        self.assertEqual(code, launcher.EXIT_CONFIG)
        self.assertIn("which the sandboxed agent can read", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())


class DispatchRunTest(CycleTestCase):
    def setUp(self):
        super().setUp()
        fakes.add_dispatches(self.repo, self.env)

    def test_the_waitlist_request_is_filed_once_and_never_asked_again(self):
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        (entry,) = self.queue()["open"]
        identifier = f"{fakes.SUNDAY_RUN.astimezone():%Y%m%d}-reptoday-waitlist"
        self.assertEqual(
            (entry["id"], entry["kind"], entry["origin"], entry["product"]),
            (identifier, "dispatch-request", "dispatch/reptoday-waitlist", "RepToday"),
        )
        text = (self.ledger() / entry["file"]).read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(text, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertIn(
            f"- `{identifier}` (dispatch-request, filed by the launcher): Approve Dispatch: build RepToday's Waitlist",
            self.brief(),
        )
        report = self.report()
        self.assertIn(f"- dispatch-requests: checked=1 acted=1 note=reptoday-waitlist filed as `{identifier}`", report)
        self.assertIn("1 item open for the next sitting (1 new this run, 0 carried over)", report)

        again = (fakes.REPO / "src/dispatches/reptoday-waitlist.md").read_text(encoding="utf-8")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/waitlist-again.md": again}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        queue = self.queue()
        self.assertEqual([e["id"] for e in queue["open"] if e["kind"] == "dispatch-request"], [identifier])
        report = self.report()
        self.assertIn(f"note=reptoday-waitlist open as `{identifier}`", report)
        self.assertIn(f"`waitlist-again.md`: asks the same as {identifier}, which is open", report)

        self.decide(identifier, "approve", note="Go ahead.")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        queue = self.queue()
        self.assertEqual([e for e in queue["open"] if e["kind"] == "dispatch-request"], [])
        self.assertEqual(next(e for e in queue["closed"] if e["id"] == identifier)["status"], "approved")
        self.assertIn(f"note=reptoday-waitlist approved as `{identifier}`; never filed again", self.report())
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        ids = [entry["id"] for entry in self.queue()["open"] + self.queue()["closed"] if "waitlist" in entry["id"]]
        self.assertEqual(ids, [identifier])

    def test_an_item_the_agent_writes_never_withdraws_the_request(self):
        self.run_cycle()
        (entry,) = self.queue()["open"]
        identifier = entry["id"]
        smaller = fakes.proposal("dispatch-request", f"supersedes: {identifier}\n", "build a smaller Waitlist")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/waitlist-smaller.md": smaller}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertIn(
            f"- Set aside, not queued: `waitlist-smaller.md`: supersedes {identifier}, which the launcher filed from"
            " reviewed text; only a reviewed change to that text replaces it",
            self.report(),
        )
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual([e["id"] for e in self.queue()["open"] if e["kind"] == "dispatch-request"], [identifier])
        self.assertIn(f"note=reptoday-waitlist open as `{identifier}`", self.report())


class ProductionCloneTest(CycleTestCase):
    """The production clone syncs from its remote before a run and pushes workspace/ and ledger/ after it."""

    def setUp(self):
        super().setUp()
        self.remote = self.root / "remote.git"
        fakes.git(self.root, "init", "--quiet", "--bare", str(self.remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(self.remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        self.clone = self.root / "production"
        fakes.git(self.root, "clone", "--quiet", str(self.remote), str(self.clone), env=self.env)

    def test_a_run_saves_only_workspace_and_ledger_to_main(self):
        writes = {
            "review-queue/incoming/name-status-stale.md": fakes.PROPOSAL,
            "drafts/README.md": "rewritten by the agent\n",
            "drafts/day-3.md": "a Draft\n",
        }
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertIn("pre-run: current", out)
        self.assertIn("records: pushed", out)
        changed = fakes.git(self.remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertTrue(all(path.startswith(("workspace/", "ledger/")) for path in changed), changed)
        self.assertIn("ledger/review-queue/queue.json", changed)
        self.assertIn("workspace/drafts/day-3.md", changed)
        self.assertNotIn("workspace/drafts/README.md", changed)
        self.assertNotIn("ledger/run.lock", changed)
        self.assertEqual((self.clone / "workspace/drafts/README.md").read_text(encoding="utf-8"), "# drafts\n")
        self.assertEqual(fakes.git(self.clone, "status", "--porcelain", env=self.env), "")

    def test_new_reviewed_code_is_fast_forwarded_and_the_run_restarts_on_it(self):
        (self.repo / "config" / "note.txt").write_text("reviewed change\n")
        fakes.git(self.repo, "add", "--all", env=self.env)
        fakes.git(self.repo, "commit", "--quiet", "-m", "reviewed", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        calls = []
        code, out = self.run_cycle(repo=self.clone, execve=lambda *args: calls.append(args))
        self.assertEqual(len(calls), 1, out)
        entry, argv, env = calls[0]
        self.assertEqual(argv[1:], ["run"])
        self.assertTrue((self.clone / "config" / "note.txt").is_file())
        self.env[cycle.PRE_RUN_ENV] = env[cycle.PRE_RUN_ENV]
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertIn("fast-forwarded main", self.report(self.clone))

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_access_removed_in_the_workspace_never_stops_a_code_update_or_the_records_step(self):
        (self.repo / "workspace/instructions/README.md").write_text("# instructions, reviewed\n")
        fakes.git(self.repo, "commit", "--quiet", "-am", "reviewed", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        (self.clone / "workspace/drafts/README.md").chmod(0)
        (self.clone / "workspace/instructions").chmod(0)
        calls = []
        code, out = self.run_cycle(repo=self.clone, execve=lambda *args: calls.append(args))
        self.assertEqual(len(calls), 1, out)
        readme = self.clone / "workspace/instructions/README.md"
        self.assertEqual(readme.read_text(encoding="utf-8"), "# instructions, reviewed\n")

        self.env[cycle.PRE_RUN_ENV] = calls[0][2][cycle.PRE_RUN_ENV]
        behavior = {"write": {"drafts/day-3.md": "a Draft\n"}, "chmod": {"drafts/day-3.md": "000", "drafts": "000"}}
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertIn("records: pushed", out)
        report = self.report(self.clone)
        self.assertIn("fast-forwarded main", report)
        problems = report.partition("\n## Launcher problems\n")[2]
        restored = "was left without its owner's read and write access, so the launcher restored it"
        entries = (
            "workspace/instructions",
            "workspace/drafts/README.md",
            "workspace/drafts",
            "workspace/drafts/day-3.md",
        )
        for entry in entries:
            self.assertIn(f"- `{entry}` {restored}", problems)
        changed = fakes.git(self.remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertIn("workspace/drafts/day-3.md", changed)
        notice = next(entry for entry in self.queue(self.clone)["open"] if entry["kind"] == "notice")
        self.assertIn(f"`workspace/instructions` {restored}", (self.ledger(self.clone) / notice["file"]).read_text())

    def test_a_clone_off_main_or_with_code_changes_refuses_to_start(self):
        with (self.clone / "src/instructions/weekly-run.md").open("a") as handle:
            handle.write("Unreviewed line.\n")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, cycle.EXIT_RECORDS)
        self.assertIn("changes outside workspace/ and ledger/", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())


if __name__ == "__main__":
    unittest.main()
