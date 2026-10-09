"""Whole runs with a fake Codex: snapshot, decisions, Review Queue, run report, and the production clone's records."""

import fcntl
import io
import json
import os
import plistlib
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import cli, cycle, exchange, package
from gr0wthlab.areas import Areas
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
        if sys.platform == "darwin":
            subprocess.run(["/bin/chmod", "-R", "-N", self.tmp.name], capture_output=True, check=False)
        for root, dirs, files in os.walk(self.tmp.name):
            for name in dirs + files:
                path = os.path.join(root, name)
                if hasattr(os, "chflags"):
                    os.chflags(path, 0, follow_symlinks=False)
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

    def queue(self, repo=None):
        return json.loads((self.workspace(repo) / "review-queue/queue.json").read_text(encoding="utf-8"))

    def report(self, repo=None):
        reports = sorted((self.workspace(repo) / "run-reports").glob("2*Z-*.md"))
        reports = [path for path in reports if not path.name.endswith(".brief.md")]
        return reports[-1].read_text(encoding="utf-8")

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
        workspace = self.workspace()

        snapshots = list((workspace / "evidence/package-snapshots").glob("*.json"))
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
        item = (workspace / "review-queue/items/20261011-name-status-stale.md").read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(item, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertEqual(list((workspace / "review-queue/incoming").iterdir()), [])

        report = self.report()
        self.assertIn(
            "## Summary\n\n- checked=13 acted=1 note=package-review 12 files, 0 changed, 0 failed; 1 proposal queued\n",
            report,
        )
        self.assertIn("- listening: checked=0 acted=0 note=not built until US-ME13", report)
        for workflow in ("review-queue", "listening", "outreach"):
            self.assertTrue((workspace / f"run-reports/state/{workflow}.json").is_file(), workflow)
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
        (self.workspace() / "run-reports/state/review-queue.json").write_text("{broken", encoding="utf-8")
        day = self.sit()
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        notice = next(e for e in self.queue()["open"] if e["kind"] == "notice")
        text = (self.workspace() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn("the review-queue run state was not valid", text)
        rebuilt = json.loads((self.workspace() / "run-reports/state/review-queue.json").read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["carried"]["20261011-name-status-stale"]["carried_over_from"], day)

    def test_state_files_the_launcher_sets_aside_are_not_reported_as_the_agent_s(self):
        self.run_cycle()
        for path in (self.workspace() / "run-reports/state").iterdir():
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
        evidence = self.workspace() / "evidence/decisions"
        rejected = json.loads((evidence / f"{ids['message']}.json").read_text(encoding="utf-8"))
        self.assertEqual((rejected["decision"], rejected["reason"]), ("reject", "Too salesy for my network."))
        self.assertEqual(rejected["item_file"], f"review-queue/items/{ids['message']}.md")
        self.assertEqual(rejected["source"]["path"], str(self.exchange / f"decisions/{ids['message']}.json"))
        approved = json.loads((evidence / f"{ids['post']}.json").read_text(encoding="utf-8"))
        self.assertEqual(approved["note"], "Good hook.")
        self.assertTrue((self.workspace() / "evidence/sittings/2026-10-11.json").is_file())
        report = self.report()
        self.assertIn("| Mandu decisions | changed | 4 records, 4 new since the previous run |", report)
        self.assertIn("Reason: Wait for counsel.", report)
        self.assertIn(f"Sitting {day}: 41 minutes.", report)
        self.assertIn(f"carried over from the sitting on {day}", report)

        recorded = json.loads((self.workspace() / "run-reports/state/review-queue.json").read_text(encoding="utf-8"))
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
        notice = (self.workspace() / third["open"][2]["file"]).read_text(encoding="utf-8")
        self.assertIn(f"asks the same as {ids['package-change-proposal']}, which is rejected", notice)
        self.assertIn(f"carried over from the sitting on {day}", self.report())
        self.assertIn("4 records, 0 new since the previous run", self.report())
        brief = sorted((self.workspace() / "run-reports").glob("*.brief.md"))[-1].read_text(encoding="utf-8")
        self.assertIn("rejected: Approve package change: name-status-stale. Reason: Wait for counsel.", brief)

    def test_bad_and_unmatched_decisions_become_a_notice_and_the_item_stays_open(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide("20261011-name-status-stale", "reject")
        self.decide("20261011-unknown", "approve")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        queue = self.queue()
        kinds = [entry["kind"] for entry in queue["open"]]
        self.assertEqual(kinds, ["package-change-proposal", "notice"])
        notice = (self.workspace() / queue["open"][1]["file"]).read_text(encoding="utf-8")
        self.assertIn("reason is required", notice)
        self.assertIn("no queued item has this identifier", notice)

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
        logs = cycle.checkout_logs(self.logs, repo)
        logs.mkdir(parents=True, exist_ok=True)
        held = (logs / cycle.LOCK_FILE).open("a")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return held

    def test_a_run_started_while_another_runs_is_refused_and_the_next_report_says_so(self):
        with self.hold_lock(self.repo):
            code, out = self.run_cycle(trigger="scheduled")
        self.assertEqual(code, cycle.EXIT_BUSY)
        self.assertIn("refusing to start: another run is in progress", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())
        self.assertFalse((self.workspace() / "review-queue/queue.json").exists())

        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=5))
        self.assertEqual(code, 0, out)
        self.assertRegex(
            self.report(), r"\n- Run \S+-scheduled-\S+ \(scheduled\) was refused at .*: another run was in progress\.\n"
        )
        self.assertEqual(list((cycle.checkout_logs(self.logs, self.repo) / cycle.NOTES_DIR).iterdir()), [])
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
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice"])
        notice = (self.workspace() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("could not be read, so the work that needs them is incomplete", notice)
        self.assertIn("Post Drafts", notice)
        self.assertIn("Weekly Read memo", notice)
        brief = next((self.workspace() / "run-reports").glob("*.brief.md")).read_text(encoding="utf-8")
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
        kept = list((self.workspace() / "review-queue/set-aside").rglob("broken.md"))
        self.assertEqual(len(kept), 1)
        notice = (self.workspace() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("`broken.md`: sections must be exactly", notice)

    def test_the_agent_cannot_change_launcher_records(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        queue_before = (self.workspace() / "review-queue/queue.json").read_text(encoding="utf-8")
        forged = {"exchange": 1, "open": [], "closed": []}
        fakes.behave(
            self.codex_dir,
            {
                "write": {
                    "review-queue/queue.json": json.dumps(forged),
                    "evidence/decisions/20261011-name-status-stale.json": "{}",
                },
                "delete": ["drafts/README.md"],
            },
        )
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        queue = self.queue()
        self.assertEqual([entry["id"] for entry in queue["open"]][:1], ["20261011-name-status-stale"])
        self.assertFalse((self.workspace() / "evidence/decisions/20261011-name-status-stale.json").exists())
        self.assertTrue((self.workspace() / "drafts/README.md").is_file())
        self.assertNotEqual(queue_before, "")
        report = self.report()
        self.assertIn("restored `review-queue/queue.json`", report)
        self.assertIn("set aside `evidence/decisions/20261011-name-status-stale.json`", report)
        self.assertIn("restored `drafts/README.md`", report)

    def test_the_agent_cannot_replace_a_folder_the_launcher_writes_in(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        items = self.workspace() / "review-queue/items"
        item = items / "20261011-name-status-stale.md"
        original = item.read_bytes()
        outside = self.root / "outside"
        (outside / "empty").mkdir(parents=True)
        replacements = {
            "a file": ("review-queue/items", {"write": {"review-queue/items": "not a folder"}}),
            "a link": ("review-queue/items", {"symlink": {"review-queue/items": str(outside)}}),
            "a linked incoming folder": ("review-queue/incoming", {"symlink": {"review-queue/incoming": str(outside)}}),
        }
        for number, (case, (folder, behavior)) in enumerate(replacements.items(), 1):
            with self.subTest(case=case):
                fakes.behave(self.codex_dir, dict(behavior, rmtree=[folder]))
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10 * number))
                self.assertEqual(code, 0, out)
                self.assertTrue(items.is_dir() and not items.is_symlink())
                self.assertEqual(item.read_bytes(), original)
                report = self.report()
                self.assertIn(f"removed `{folder}`, which the agent put in place of a folder", report)
                if folder == "review-queue/items":
                    self.assertIn("restored `review-queue/items/20261011-name-status-stale.md`", report)
                self.assertEqual(sorted(path.name for path in outside.iterdir()), ["empty"])
                self.assertIn("20261011-name-status-stale", [entry["id"] for entry in self.queue()["open"]])

    def test_the_agent_cannot_replace_an_area_or_this_run_s_set_aside_folder(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        outside = self.root / "outside"
        (outside / "decisions").mkdir(parents=True)
        (outside / "decisions/20261011-name-status-stale.json").write_text('{"decision": "approve"}', encoding="utf-8")

        def tree():
            return {str(path.relative_to(outside)): path.is_dir() or path.read_bytes() for path in outside.rglob("*")}

        untouched = tree()
        replacements = {
            "evidence": {"rmtree": ["evidence"], "symlink": {"evidence": str(outside)}},
            "run-reports": {"rmtree": ["run-reports"], "symlink": {"run-reports": str(outside)}},
            "review-queue/set-aside/{run}": {
                "symlink": {"review-queue/set-aside/{run}": str(outside)},
                "write": {"review-queue/items/forged.md": "forged"},
            },
        }
        for number, (folder, behavior) in enumerate(replacements.items(), 1):
            with self.subTest(folder=folder):
                fakes.behave(self.codex_dir, behavior)
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10 * number))
                self.assertEqual(code, 0, out)
                self.assertEqual(tree(), untouched)
                reports = (self.workspace() / "run-reports").glob("2*Z-*.md")
                run_id = sorted(path.name for path in reports if not path.name.endswith(".brief.md"))[-1][: -len(".md")]
                report = self.report()
                name = folder.replace("{run}", run_id)
                self.assertIn(f"removed `{name}`, which the agent put in place of a folder", report)
                for area in ("evidence", "run-reports"):
                    path = self.workspace() / area
                    self.assertTrue(path.is_dir() and not path.is_symlink() and (path / "README.md").is_file())
                self.assertIn("20261011-name-status-stale", [entry["id"] for entry in self.queue()["open"]])
        self.assertIn("set aside `review-queue/items/forged.md`, which the agent added", report)
        snapshots = self.workspace() / "evidence/package-snapshots"
        self.assertEqual(len(list(snapshots.glob("*.json"))), 4)

    def test_a_folder_the_agent_plants_where_the_launcher_writes_is_removed(self):
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        day = fakes.SUNDAY_RUN.astimezone().strftime("%Y%m%d")
        planted = [
            "evidence/decisions/20261011-name-status-stale.json",
            "run-reports/{run}.md",
            f"review-queue/items/{day}-notice-run-problems.md",
            "run-reports/state/hidden/deeper",
        ]
        behavior = {
            "write": {"run-reports/state/hidden/note.md": "hidden"},
            "mkdir": planted,
            "chmod": {"run-reports/state/hidden": 0},
        }
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10))
        self.assertEqual(code, 0, out)
        workspace = self.workspace()
        reports = (workspace / "run-reports").glob("2*Z-*.md")
        run_id = sorted(path.name for path in reports if not path.name.endswith(".brief.md"))[-1][: -len(".md")]
        self.assertTrue((workspace / f"run-reports/{run_id}.md").is_file())
        report = self.report()
        for folder in [*planted[:3], "run-reports/state/hidden"]:
            name = folder.replace("{run}", run_id)
            self.assertIn(f"removed folder `{name}`, which the agent added", report)
        self.assertIn("set aside `run-reports/state/hidden/note.md`, which the agent added", report)
        self.assertFalse((workspace / "evidence/decisions/20261011-name-status-stale.json").exists())
        notice = next(entry for entry in self.queue()["open"] if entry["kind"] == "notice")
        self.assertEqual(notice["id"], f"{day}-notice-run-problems")
        self.assertTrue((workspace / notice["file"]).is_file())

        self.decide("20261011-name-status-stale", "approve")
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=20))
        self.assertEqual(code, 0, out)
        self.assertTrue((workspace / "evidence/decisions/20261011-name-status-stale.json").is_file())

    def assert_complete(self, code, out):
        self.assertEqual(code, 0, out)
        workspace = self.workspace()
        reports = (workspace / "run-reports").glob("2*Z-*.md")
        run_id = sorted(path.name for path in reports if not path.name.endswith(".brief.md"))[-1][: -len(".md")]
        self.assertEqual(self.queue()["updated_by_run"], run_id)
        notice = next(entry for entry in self.queue()["open"] if entry["kind"] == "notice")
        self.assertTrue((workspace / notice["file"]).is_file())
        for workflow in ("review-queue", "listening", "outreach"):
            state = json.loads((workspace / f"run-reports/state/{workflow}.json").read_text(encoding="utf-8"))
            self.assertEqual(state["updated_by_run"], run_id)
        return self.report()

    def test_a_locked_folder_in_place_of_a_record_does_not_stop_the_run(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        behavior = {
            "delete": ["review-queue/queue.json", "evidence/README.md"],
            "write": {"review-queue/queue.json/x/y.md": "hidden", "evidence/README.md/x/y.md": "hidden"},
            "chmod": {"review-queue/queue.json/x": 0, "evidence/README.md/x": 0},
        }
        fakes.behave(self.codex_dir, behavior)
        report = self.assert_complete(*self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10)))
        self.assertIn("restored `review-queue/queue.json`", report)
        self.assertIn("restored `evidence/README.md`", report)
        self.assertTrue((self.workspace() / "evidence/README.md").is_file())

    @unittest.skipUnless(sys.platform == "darwin", "BSD flags and ACLs are macOS's")
    def test_flags_and_acls_the_agent_sets_do_not_stop_the_run(self):
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        behavior = {
            "write": {"review-queue/items/forged.md": "forged", "review-queue/items/denied.md": "denied"},
            "mkdir": ["evidence/decisions/locked"],
            "acl": {
                "review-queue/items/denied.md": "everyone deny delete,writesecurity",
                "review-queue/items": "everyone deny add_file,delete_child,list,writesecurity",
            },
            "chflags": {
                "evidence/decisions/locked": stat.UF_IMMUTABLE,
                "review-queue/items/forged.md": stat.UF_IMMUTABLE,
                "run-reports": stat.UF_IMMUTABLE,
            },
        }
        fakes.behave(self.codex_dir, behavior)
        report = self.assert_complete(*self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10)))
        self.assertIn("removed folder `evidence/decisions/locked`, which the agent added", report)
        for name in ("forged", "denied"):
            self.assertIn(f"set aside `review-queue/items/{name}.md`, which the agent added", report)
            self.assertFalse((self.workspace() / f"review-queue/items/{name}.md").exists())
        self.assertEqual(os.lstat(str(self.workspace() / "run-reports")).st_flags, 0)
        self.assertNotIn("could not undo", report)
        self.assertNotIn("could not remove", report)

    def test_links_the_agent_plants_never_carry_a_launcher_write_outside_the_workspace(self):
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "kept.md").write_text("kept", encoding="utf-8")
        notice = f"review-queue/items/{fakes.SUNDAY_RUN.astimezone():%Y%m%d}-notice-run-problems.md"
        written = [
            "review-queue/queue.json",
            "drafts/README.md",
            "run-reports/{run}.md",
            "run-reports/state/review-queue.json",
            "review-queue/set-aside/{run}/review-queue--items--forged.md",
            notice,
        ]
        links = {}
        for number, record in enumerate(written):
            folder, name = record.rsplit("/", 1)
            links[f"{folder}/.{name}.tmp-{{ppid}}"] = str(outside / f"temporary-{number}")
        links.update({record: str(outside / "kept.md") for record in written})
        behavior = {
            "delete": ["review-queue/queue.json", "drafts/README.md", "run-reports/state/review-queue.json"],
            "write": {"review-queue/items/forged.md": "forged"},
            "symlink": links,
        }
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=10))
        self.assertEqual(code, 0, out)
        self.assertEqual(
            {path.name: path.read_text(encoding="utf-8") for path in outside.iterdir()}, {"kept.md": "kept"}
        )
        for record in ("review-queue/queue.json", "drafts/README.md", notice):
            path = self.workspace() / record
            self.assertTrue(path.is_file() and not path.is_symlink(), record)
        self.assertIn("set aside `review-queue/items/forged.md`, which the agent added", self.report())
        self.assertIn(notice, [entry["file"] for entry in self.queue()["open"]])

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
        plist = io.BytesIO()
        with (
            mock.patch.dict(os.environ, self.env),
            mock.patch.object(cli, "REPO_ROOT", self.repo),
            mock.patch.object(cli, "ENTRY", self.repo / "src/bin/gr0wthlab"),
            mock.patch.object(sys, "stdout", mock.Mock(buffer=plist)),
        ):
            self.assertEqual(cli.main(["launch-agent"]), 0)
        agent = plistlib.loads(plist.getvalue())
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
        original = Areas.write_text

        def refuse_reports(areas, path, text):
            if path.parent.name == "run-reports" and not path.name.endswith(".brief.md"):
                raise PermissionError(1, "Operation not permitted", str(path))
            original(areas, path, text)

        with mock.patch.object(Areas, "write_text", refuse_reports):
            code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn("could not write its report", out)
        reports = [path for path in (self.workspace() / "run-reports").glob("2*Z-*.md") if ".brief." not in path.name]
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


class ProductionCloneTest(CycleTestCase):
    """The production clone syncs from its remote before a run and pushes workspace/ after it."""

    def setUp(self):
        super().setUp()
        self.remote = self.root / "remote.git"
        fakes.git(self.root, "init", "--quiet", "--bare", str(self.remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(self.remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        self.clone = self.root / "production"
        fakes.git(self.root, "clone", "--quiet", str(self.remote), str(self.clone), env=self.env)

    def test_a_run_saves_only_workspace_to_main(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertIn("pre-run: current", out)
        self.assertIn("records: pushed", out)
        changed = fakes.git(self.remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertTrue(changed)
        self.assertTrue(all(path.startswith("workspace/") for path in changed), changed)
        self.assertIn("workspace/review-queue/queue.json", changed)
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

    def test_a_clone_off_main_or_with_code_changes_refuses_to_start(self):
        with (self.clone / "src/instructions/weekly-run.md").open("a") as handle:
            handle.write("Unreviewed line.\n")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, cycle.EXIT_RECORDS)
        self.assertIn("changes outside workspace/", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())


if __name__ == "__main__":
    unittest.main()
