"""Whole runs with a fake Codex: snapshot, decisions, Review Queue, run report, and the production clone's records."""

import io
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from gr0wthlab import cycle, exchange
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
                os.chmod(os.path.join(root, name), 0o755)
        self.tmp.cleanup()

    def run_cycle(self, repo=None, trigger="on-demand", weekly=None, execve=None, at=None):
        if at is not None:
            self.clock.set(at)
        out = io.StringIO()
        runner = cycle.Cycle(repo or self.repo, self.env, self.home, out, self.clock)
        kwargs = {"execve": execve} if execve else {}
        code = runner.run(None, trigger, weekly, None, ["run"], **kwargs)
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
            "exchange": 1,
            "item": item,
            "decision": decision,
            "reason": reason,
            "note": note,
            "decided_at": "2026-10-11T19:42:00-07:00",
            "sitting": "2026-10-11",
        }
        (folder / f"{item}.json").write_text(json.dumps(record), encoding="utf-8")


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
        item = (workspace / "review-queue/items/20261011-name-status-stale.md").read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(item, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertEqual(list((workspace / "review-queue/incoming").iterdir()), [])

        report = self.report()
        self.assertIn("On demand, started", report)
        self.assertIn("| RepToday package: `projects/RepToday/gtm/05-social-pmf/angles.md` | read |", report)
        self.assertIn("| Mandu decisions | skipped | no Review Queue item is waiting for a decision yet |", report)
        self.assertIn("| YouTube results | skipped | not connected until US-ME11 |", report)
        self.assertIn("First snapshot", report)
        self.assertRegex(report, r"Approximate cost: about \$0\.00[89] at API prices, for 200,000 input tokens")
        self.assertIn("> Checked the package.", report)
        self.assertNotIn("Notice:", report)
        self.assertIn("Run brief, read it first:", (self.codex_dir / "prompt.txt").read_text(encoding="utf-8"))

    def test_the_agent_sees_its_brief(self):
        self.run_cycle()
        prompt = (self.codex_dir / "prompt.txt").read_text(encoding="utf-8")
        brief = Path(prompt.split("Run brief, read it first: ")[1].split()[0])
        text = brief.read_text(encoding="utf-8")
        self.assertIn("## Package files", text)
        self.assertIn("`projects/RepToday/gtm/05-social-pmf/cadence-14-day.md` | read: first snapshot", text)
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
        (self.exchange / "sittings").mkdir()
        (self.exchange / "sittings/2026-10-11.json").write_text(
            json.dumps({"exchange": 1, "date": "2026-10-11", "minutes": 41}), encoding="utf-8"
        )
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
        self.assertIn("Sitting 2026-10-11: 41 minutes.", report)
        self.assertIn("carried over from 2026-10-11", report)

        code, _ = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        third = self.queue()
        self.assertEqual(len(third["open"]), 2)
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
        self.assertIn("| Mandu decisions | failed | Mandu's exchange folder", self.report())


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
        self.assertIn("| Package review (contradictions) | incomplete |", report)
        self.assertIn("| Package snapshot | incomplete | 1 package sources could not be read |", report)
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice"])
        notice = (self.workspace() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("could not be read, so the work that needs them is incomplete", notice)
        self.assertIn("Post Drafts", notice)
        self.assertIn("Weekly Read memo", notice)

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
        self.assertTrue(queue["open"][0]["carried_over"])
        self.assertFalse((self.workspace() / "evidence/decisions/20261011-name-status-stale.json").exists())
        self.assertTrue((self.workspace() / "drafts/README.md").is_file())
        self.assertNotEqual(queue_before, "")
        report = self.report()
        self.assertIn("restored `review-queue/queue.json`", report)
        self.assertIn("set aside `evidence/decisions/20261011-name-status-stale.json`", report)
        self.assertIn("restored `drafts/README.md`", report)

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
        late = fakes.SUNDAY_RUN + timedelta(hours=3)
        local = late.astimezone()
        due = (local - timedelta(hours=3)).strftime("%H:%M")
        day = local.strftime("%A").lower() if (local - timedelta(hours=3)).date() == local.date() else None
        if day is None:
            self.skipTest("the due time falls on another day in this time zone")
        self.run_cycle(trigger="scheduled", weekly=(day, due), at=late - timedelta(hours=3) + timedelta(minutes=1))
        self.assertIn("started on time", self.report())
        self.run_cycle(trigger="scheduled", weekly=(day, due), at=late)
        self.assertIn("Started late:", self.report())
        self.assertIn("3 h 0 min after its time", self.report())

    def test_the_run_refuses_a_task_definition_outside_src_instructions(self):
        out = io.StringIO()
        runner = cycle.Cycle(self.repo, self.env, self.home, out, self.clock)
        code = runner.run(self.repo / "workspace/instructions/x.md", "on-demand", None, None, [])
        self.assertEqual(code, 2)
        self.assertIn("src/instructions", out.getvalue())


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
