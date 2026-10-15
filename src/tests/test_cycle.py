"""Whole runs with a fake Codex: snapshot, decisions, Review Queue, run report, and the production clone's records."""

import fcntl
import hashlib
import io
import json
import os
import plistlib
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import attempts, cli, cycle, exchange, launcher, lint, package, process
from gr0wthlab.areas import PROBE_PREFIX, Store
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
        self.code = fakes.make_code(self.root / "RepToday", self.env)
        self.exchange = self.repo / "ledger" / "founder"  # the Founder's records, which only the sitting page writes
        self.codex_dir = self.root / "codex-bin"
        codex = fakes.install_codex(self.codex_dir)
        self.logs = self.root / "logs"
        self.env.update(
            GR0WTHLAB_CODEX_BIN=str(codex),
            GR0WTHLAB_LOG_DIR=str(self.logs),
            GR0WTHLAB_MANDU_DIR=str(self.mandu),
            GR0WTHLAB_REPTODAY_DIR=str(self.root / "RepToday"),
            GR0WTHLAB_IMMERSE_DIR=str(self.root / "Immerse"),
            GR0WTHLAB_PRODUCTION_CLONE=str(self.root / "production"),
        )
        self.clock = fakes.Clock(fakes.SUNDAY_RUN)
        # A scheduled start asks the Mac whether it is fully awake; the tests answer for it.
        self.ask_the_mac = attempts.fully_awake
        asked = mock.patch.object(attempts, "fully_awake", return_value=True)
        self.awake = asked.start()
        self.addCleanup(asked.stop)
        self.web = fakes.Web()  # the web a run reads; no test opens the real one
        self.github = fakes.GitHub()  # GitHub's answer to whether the repository is private; no test asks the real one

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp.name):
            for name in dirs + files:
                path = os.path.join(root, name)
                if not os.path.islink(path):
                    os.chmod(path, 0o755)
        self.tmp.cleanup()

    def run_cycle(self, repo=None, trigger="on-demand", execve=None, at=None, once=None, clocks=process.CLOCK):
        if at is not None:
            self.clock.set(at)
        out = io.StringIO()
        reader = lambda policy: fakes.client(self.web, policy)  # noqa: E731
        runner = cycle.Cycle(repo or self.repo, self.env, self.home, out, self.clock, reader, clocks, self.github)
        kwargs = {"execve": execve} if execve else {}
        code = runner.run(trigger, once, ["run"], **kwargs)
        return code, out.getvalue()

    def limit_session(self, key, seconds):
        """Give one workflow's session, in every later run of this test, a time limit of its own. No setting does
        that: every session runs under `agent.time_limit_seconds`. It is the test's way to have one session stopped
        at its limit while the sessions around it run under the configured one."""
        planned = cycle.Cycle.plan_sessions

        def plan(runner, state, config):
            planned(runner, state, config)
            state.session(key).limit = seconds

        patched = mock.patch.object(cycle.Cycle, "plan_sessions", plan)
        patched.start()
        self.addCleanup(patched.stop)

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

    def brief(self, repo=None, session=None):
        """The brief the last run wrote for one workflow's session, or, with no session named, every brief of that
        run one after another in the order of its sessions, so a test can say what the run's agents were told and
        what none of them was."""
        from gr0wthlab import sessions

        folder = self.ledger(repo) / "run-reports"
        run = sorted(folder.glob("*.brief.md"))[-1].name.split(".")[0]
        keys = sessions.KEYS if session is None else (session,)
        found = [folder / f"{run}.{key}.brief.md" for key in keys]
        return "\n".join(path.read_text(encoding="utf-8") for path in found if path.is_file())

    def run_record(self, session=None):
        """The last run's record in the log folder, or what it holds of one of its sessions."""
        runs = sorted(path for path in self.logs.glob("2*Z-*.json") if path.name.count(".") == 1)
        run = json.loads(runs[-1].read_text(encoding="utf-8"))
        if session is None:
            return run
        return next(found for found in run["sessions"] if found["workflow"] == session)

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

    def one_weekly_read_item(self) -> str:
        """A run on the day-14 Weekly Read of a window whose calendar holds day 1 alone, with the Founder's numbers for
        that post and the memo the agent writes: it queues exactly one Weekly Read decision item, the one way such an
        item is ever queued. The window, the calendar, and what the agent writes are then the caller's to set."""
        today = fakes.SUNDAY_RUN.astimezone().date()
        fakes.set_window(self.repo, {"first_sitting": (today - timedelta(days=14)).isoformat(), "slot": "19:00"})
        fakes.keep_days(self.mandu, 1)
        fakes.give_results(self.exchange, 1, read=14, read_on=today.isoformat(), views=412, watched_full_percent=31.0)
        fakes.behave(self.codex_dir, {"write": {"weekly-reads/window-1-read-14.md": fakes.WEEKLY_MEMO_DAY_14}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        (entry,) = [entry for entry in self.queue()["open"] if entry["kind"] == "weekly-read-decision"]
        return str(entry["id"])

    def sit(self, day=None):
        """The Founder's record of a sitting, by default on the Mac's local date of the first run."""
        day = day or fakes.SUNDAY_RUN.astimezone().strftime("%Y-%m-%d")
        folder = self.exchange / "sittings"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{day}.json").write_text(
            json.dumps({"exchange": exchange.EXCHANGE_VERSION, "date": day, "minutes": 41}), encoding="utf-8"
        )
        return day

    # An open item is taken back only on what a record the launcher could read says (queue.stands). Each place a
    # run withdraws, closes, or supersedes one has a test of a read that fails, which ends in these two assertions.

    def entry(self, identifier):
        queue = self.queue()
        return next(entry for entry in queue["open"] + queue["closed"] if entry["id"] == identifier)

    def notices(self):
        """The text of every notice open for the Founder."""
        return "\n".join(
            (self.ledger() / entry["file"]).read_text(encoding="utf-8")
            for entry in self.queue()["open"]
            if entry["kind"] == "notice"
        )

    def assert_stands(self, before, output, reason):
        """What a run whose read failed leaves of an open item: the item exactly as it was, under its identifier,
        with nothing taken off the queue; its output incomplete for the real reason; and a notice that names the
        item and the read."""
        queue = self.queue()
        self.assertIn(before["id"], [entry["id"] for entry in queue["open"]])
        self.assertEqual(self.entry(before["id"]), before, "the open item is exactly as it was")
        closed = [entry["id"] for entry in queue["closed"] if entry.get("closed_by_run") == queue["updated_by_run"]]
        self.assertEqual(closed, [], "the run took nothing off the queue")
        row = next(line for line in self.report().splitlines() if line.startswith(f"| {output} | "))
        self.assertIn(f"| {output} | incomplete | ", row)
        self.assertIn(reason, row)
        notices = self.notices()
        self.assertIn("so each was left exactly as it is: nothing was withdrawn or replaced on that account", notices)
        named = [line for line in notices.splitlines() if line.startswith(f"- `{before['id']}` ({output}): ")]
        self.assertTrue(named and reason in named[-1], notices)

    def assert_never_asked_again(self, before):
        """What the first run with the read restored leaves: the item as it was before the failed run, and nothing
        queued in its place under another identifier."""
        queue = self.queue()
        self.assertEqual(self.entry(before["id"]), before, "as if the failed run had not happened")
        ever = [entry for entry in queue["open"] + queue["closed"] if entry["id"].startswith(before["id"])]
        self.assertEqual([entry["id"] for entry in ever], [before["id"]], "it was never queued again")
        self.assertEqual(
            [entry["id"] for entry in queue["open"] + queue["closed"] if entry.get("supersedes") == before["id"]], []
        )


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
        self.assertEqual(len(files), 16)
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
            "## Summary\n\n- checked=17 acted=1 note=package-review 16 files, 0 changed, 0 failed; 1 proposal queued\n",
            report,
        )
        self.assertIn("- listening: checked=0 acted=0 note=0 of 0 sources read, 0 documents;", report)
        self.assertIn("## Listening\n\nNo Listening source is configured, so nothing was read.", report)
        self.assertIn("| Listening Evidence | complete |", report)
        self.assertEqual(self.web.requests, [], "a run with no source configured asks the network for nothing")
        for workflow in ("review-queue", "listening", "outreach"):
            self.assertTrue((ledger / f"run-reports/state/{workflow}.json").is_file(), workflow)
        self.assertIn("On demand, started", report)
        self.assertIn("| RepToday package: `projects/RepToday/gtm/05-social-pmf/angles.md` | read |", report)
        self.assertIn("| Founder decisions | read | 0 records, 0 new since the previous run |", report)
        self.assertIn("| Sittings | read | 0 records, 0 new |", report)
        # Posting is manual, so the scheduling service is not used by the Founder's choice, never a source that failed.
        self.assertIn(
            "| Scheduling service | not used | posting is manual, the Founder's choice of 2026-10-11"
            " (docs/adr/0004-posting-is-manual.md) |",
            report,
        )
        self.assertIn("| Scheduling-service drafts | not used | posting is manual,", report)
        self.assertRegex(report, r"- Sources: 0 failed, \d+ changed, \d+ read, \d+ skipped, 1 not used\.")
        self.assertIn("| Weekly Read numbers (sitting page) | skipped | no Weekly Read is due:", report)
        self.assertNotIn("YouTube results", report)
        self.assertIn("First snapshot", report)
        self.assertRegex(report, r"Approximate cost: about \$0\.00[89] at API prices, for 200,000 input tokens")
        self.assertIn("> Checked the package.", report)
        self.assertNotIn("Notice:", report)
        self.assertIn("Run brief, read it first:", (self.codex_dir / "prompt.txt").read_text(encoding="utf-8"))

    def test_a_quiet_run_still_says_what_it_checked(self):
        self.run_cycle()
        self.assertIn("- checked=16 acted=0 note=nothing new needed action\n", self.report())

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


class TakeInTest(CycleTestCase):
    def test_an_item_that_supersedes_an_open_one_whose_file_cannot_be_read_is_set_aside_and_the_open_one_stands(self):
        """The open item's file could not be read, so it stands and nothing replaces it in that run."""
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        (first,) = [entry for entry in self.queue()["open"] if entry["kind"] == "package-change-proposal"]
        file = self.ledger() / first["file"]
        text = file.read_text(encoding="utf-8")
        file.write_text("no item\n", encoding="utf-8")
        (self.ledger() / "run-reports/state/review-queue.json").unlink()
        again = fakes.proposal(extra=f"supersedes: {first['id']}\n")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-again.md": again}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        unread = f"`{first['file']}`, its item file, could not be read"
        self.assert_stands(first, "Review Queue", unread)
        self.assertIn(
            f"`name-status-again.md`: supersedes {first['id']}: {unread}, so the open item stands and nothing replaces"
            " it in this run",
            self.report(),
        )
        file.write_text(text, encoding="utf-8")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-again.md": again}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        self.assert_never_asked_again(first)
        self.assertIn(f"`name-status-again.md`: asks the same as {first['id']}, which is open", self.report())

    def test_an_item_with_the_kind_and_ask_of_a_decided_one_whose_file_cannot_be_read_is_not_queued(self):
        """Nothing then shows it is not the ask the Founder decided, which is never asked again."""
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        (first,) = [entry for entry in self.queue()["open"] if entry["kind"] == "package-change-proposal"]
        self.decide(first["id"], "reject", reason="The caveat stays.")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        rejected = self.entry(first["id"])
        self.assertEqual(rejected["status"], "rejected")
        file = self.ledger() / first["file"]
        text = file.read_text(encoding="utf-8")
        file.write_text("no item\n", encoding="utf-8")
        (self.ledger() / "run-reports/state/review-queue.json").unlink()
        written = {
            "review-queue/incoming/name-status-again.md": fakes.PROPOSAL,
            "review-queue/incoming/name-status-other.md": fakes.proposal(title="record the name as searched"),
        }
        fakes.behave(self.codex_dir, {"write": written})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        unread = f"`{first['file']}`, its item file, could not be read"
        report = self.report()
        self.assertIn(
            f"`name-status-again.md`: has the kind and ask of {first['id']}, which is rejected: {unread}, so nothing"
            " shows this item asks anything else",
            report,
        )
        self.assertRegex(report, rf"\| Review Queue \| incomplete \| [^|\n]*{re.escape(unread)}")
        self.assertIn(f"`name-status-again.md`: has the kind and ask of {first['id']}", self.notices())
        self.assertEqual(self.entry(first["id"]), rejected)
        (other,) = [entry for entry in self.queue()["open"] if entry["kind"] == "package-change-proposal"]
        self.assertEqual(other["ask"], "Approve package change: record the name as searched")
        file.write_text(text, encoding="utf-8")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-again.md": fakes.PROPOSAL}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        self.assertEqual(code, 0, out)
        self.assertIn(f"`name-status-again.md`: asks the same as {first['id']}, which is rejected", self.report())

    def test_an_item_that_supersedes_an_open_one_the_launcher_could_read_still_takes_its_place(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        (first,) = [entry for entry in self.queue()["open"] if entry["kind"] == "package-change-proposal"]
        newer = fakes.proposal(extra=f"supersedes: {first['id']}\n", title="record the name as searched and reserved")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-newer.md": newer}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        (second,) = [entry for entry in self.queue()["open"] if entry["kind"] == "package-change-proposal"]
        old = self.entry(first["id"])
        self.assertEqual((old["status"], old["superseded_by"]), ("superseded", second["id"]))


class DecisionRoundTripTest(CycleTestCase):
    KINDS = {
        "package-change-proposal": ("name-status-stale", ""),
        "dispatch-request": ("waitlist", ""),
        "notice": ("example-notice", ""),
    }

    def test_one_item_of_each_kind_two_approved_two_rejected_two_undecided(self):
        self.one_weekly_read_item()  # queued only from a Weekly Read memo that passed its checks
        writes = {
            f"review-queue/incoming/{slug}.md": fakes.proposal(kind, extra, title=slug)
            for kind, (slug, extra) in self.KINDS.items()
        }
        writes[fakes.draft_path(1)] = fakes.draft(1)  # a post is queued only from its Draft
        creator = fakes.KIT_CREATORS[0]
        writes[fakes.message_path("creator", creator[0])] = fakes.message("creator", creator[0], fakes.CREATOR_BODY)
        fakes.set_run(self.repo, "outreach", {"creators": fakes.creators([creator])})  # and so is a message
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 1)
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        first = self.queue()
        # Every kind but the filming plan, which only the launcher files, and only when a Product films
        # (test_filming).
        self.assertEqual(
            [entry["kind"] for entry in first["open"]], [kind for kind in exchange.KINDS if kind != "filming-plan"]
        )
        ids = {entry["kind"]: entry["id"] for entry in first["open"]}
        self.assertEqual(ids["post"], "20261011-post-w1-day-01")

        self.decide(ids["post"], "approve", note="Good hook.")
        self.decide(ids["notice"], "approve")
        self.decide(ids["message"], "reject", reason="Too salesy for my network.")
        self.decide(ids["package-change-proposal"], "reject", reason="Wait for counsel.")
        day = self.sit()
        fakes.set_window(self.repo, fakes.QUIET_WINDOW)
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
        self.assertEqual(rejected["source"]["path"], f"founder/decisions/{ids['message']}.json")
        approved = json.loads((evidence / f"{ids['post']}.json").read_text(encoding="utf-8"))
        self.assertEqual(approved["note"], "Good hook.")
        self.assertTrue((self.ledger() / "evidence/sittings/2026-10-11.json").is_file())
        report = self.report()
        self.assertIn("| Founder decisions | changed | 4 records, 4 new since the previous run |", report)
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
        self.assertIn("review-queue 4 decisions taken in", report)

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
        self.assertIn("| Founder decisions | read | 1 record, 0 new since the previous run |", self.report())
        self.assertIn(replaced, self.brief())

    def test_records_about_no_open_item_are_reported_once_until_they_change(self):
        old = "20261011-name-status-stale"
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
        self.assertIn("# Notice: 2 records of yours could not be used on", notice)
        self.assertIn(f"`founder/decisions/{old}.json`: reason is required", notice)
        self.assertIn("no queued item has this identifier", notice)
        self.assertNotIn("again on the sitting page", notice)

        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual([entry["kind"] for entry in self.queue()["open"]], kinds)
        report = self.report()
        self.assertIn(
            "| Founder decisions | read | 2 records, 0 new since the previous run, 2 could not be used |", report
        )
        self.assertIn("- Not listed again: 2 records that could not be used, reported by an earlier run", report)
        self.assertNotIn("Could not use", report)

        self.decide("20261011-unknown", "approve", note="Rewritten, still about no item.")
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], kinds + ["notice"])
        notice = (self.ledger() / queue["open"][2]["file"]).read_text(encoding="utf-8")
        self.assertIn("`founder/decisions/20261011-unknown.json`", notice)
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
        self.assertIn("# Notice: 1 record of yours could not be used on", notice)
        self.assertIn(f"`founder/decisions/{old}.json`: reason is required", notice)
        self.assertNotIn("again on the sitting page", notice)
        self.assertNotIn("again on the sitting page", self.report())

        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(len(self.queue()["open"]), 2)
        self.assertNotIn("Could not use", self.report())

    def test_a_missing_records_folder_stops_the_run_before_it_starts(self):
        """A folder of the Founder's records that is not there cannot be proven refused, so nothing starts."""
        item = "20261011-name-status-stale"
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        fakes.behave(self.codex_dir, {})
        self.decide(item, "approve")
        away = self.exchange / "decisions-away"
        (self.exchange / "decisions").rename(away)
        reports = sorted((self.ledger() / "run-reports").glob("*.md"))
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, launcher.EXIT_CONFIG, out)
        self.assertIn("refusing to start: the Founder's records folder", out)
        self.assertIn("founder/decisions must be a real folder", out)
        self.assertEqual(sorted((self.ledger() / "run-reports").glob("*.md")), reports, "no run was made")
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], [item])

        away.rename(self.exchange / "decisions")
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=5))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.queue()["open"], [])

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_unreadable_decisions_folder_fails_only_its_own_source(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide("20261011-unknown", "approve")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertIn("- Could not use `founder/decisions/20261011-unknown.json`", self.report())
        decisions = self.exchange / "decisions"
        decisions.chmod(0o300)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(
            "| Founder decisions | failed | `founder/decisions/` could not be read: Permission denied. |", report
        )
        self.assertIn("| Sittings | read |", report)
        self.assertIn("| Founder decisions taken in | incomplete | Founder decisions could not be read |", report)
        self.assertIn("| Review Queue | incomplete | Founder decisions could not be read |", report)
        notice = (self.ledger() / self.queue()["open"][-1]["file"]).read_text(encoding="utf-8")
        self.assertIn("could not be read, so the work that needs them is incomplete", notice)
        self.assertIn("Permission denied", notice)

        decisions.chmod(0o755)
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        report = self.report()
        self.assertNotIn("Could not use", report)
        self.assertIn("- Not listed again: 1 record that could not be used", report)

    @unittest.skipIf(os.geteuid() == 0, "root can search any folder")
    def test_an_unsearchable_records_area_stops_the_run_before_it_starts(self):
        """Folders that cannot be examined cannot be shown to be real folders, so nothing starts, and nothing is
        taken back: the item stays open."""
        item = "20261011-name-status-stale"
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide(item, "approve")
        self.sit()
        self.exchange.chmod(0o600)
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, launcher.EXIT_CONFIG, out)
        self.assertIn("must be a real folder that can be read", out)
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], [item])

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
            "| Founder decisions | skipped | the Review Queue could not be read, so no decision could be matched to"
            " its item |",
            report,
        )
        self.assertIn(
            "| Founder decisions taken in | incomplete | the ledger could not be read; no decision was matched |",
            report,
        )
        self.assertNotIn("Could not use", report)
        self.assertIn("- No change to any Instructions was offered: the Review Queue could not be read.", report)
        self.assertFalse((self.ledger() / f"evidence/decisions/{item}.json").exists())
        self.assertIn("| Sittings | changed | 1 record, 1 new |", report)
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
            self.assertIn("# Notice: 1 decision could not be taken in on", notice)
            self.assertIn(f"`founder/decisions/{item}.json`, for `{item}`: reason is required", notice)
            self.assertIn("Decide each item again on the sitting page, which replaces its record", notice)
            self.assertIn(
                f"It is not a decision, so `{item}` stays undecided: decide it again on the sitting page",
                self.report(),
            )

        self.decide(item, "reject", reason="Wait for counsel.")
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["notice", "notice"])
        closed = next(entry for entry in queue["closed"] if entry["id"] == item)
        self.assertEqual((closed["status"], closed["reason"]), ("rejected", "Wait for counsel."))
        report = self.report()
        self.assertIn("| Founder decisions | changed | 1 record, 1 new since the previous run |", report)
        self.assertNotIn("Could not use", report)

    def test_items_that_wait_with_no_decision_are_a_quiet_read(self):
        """An undecided item needs nothing written, so a week with no decision is no failed source."""
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        report = self.report()
        self.assertIn("| Founder decisions | read | 0 records, 0 new since the previous run |", report)
        self.assertIn("| Founder decisions taken in | complete |", report)
        self.assertNotIn("Notice:", report)


class CarryOverTest(CycleTestCase):
    def test_an_item_carries_over_only_once_a_sitting_has_left_it_undecided(self):
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

    def two_items_one_decided_at_a_sitting_that_left_no_record(self):
        """Two items queued, and the Founder's decision on one of them, which carries the date of its sitting; the
        page was stopped without the sitting's own record."""
        two = {f"review-queue/incoming/{name}.md": fakes.proposal(title=name) for name in ("decided", "left")}
        fakes.behave(self.codex_dir, {"write": two})
        self.run_cycle()
        self.decide("20261011-decided", "approve")
        return "2026-10-11"

    def sitting_evidence(self, day):
        return json.loads((self.ledger() / f"evidence/sittings/{day}.json").read_text(encoding="utf-8"))

    def carried(self):
        return {entry["id"]: entry.get("carried_over_from") for entry in self.queue()["open"]}

    def test_a_sitting_that_left_no_record_is_known_from_a_decision_given_at_it(self):
        day = self.two_items_one_decided_at_a_sitting_that_left_no_record()
        after = {"review-queue/incoming/after.md": fakes.proposal(title="queued after the sitting")}
        fakes.behave(self.codex_dir, {"write": after})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=45))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.carried(), {"20261011-left": day, "20261011-after": None})
        report = self.report()
        self.assertIn(f"- Sitting {day}: its time was not recorded.", report)
        self.assertIn("| Sittings | read | 0 records, 0 new |", report)
        self.assertIn("1 new this run, 1 carried over", report)
        kept = self.sitting_evidence(day)
        self.assertEqual(
            kept,
            {
                "date": day,
                "minutes": None,
                "note": None,
                "source": None,
                "shown_by": ["founder/decisions/20261011-decided.json"],
                "taken_in_by_run": self.queue()["updated_by_run"],
            },
        )

        # A later sitting of the same date is ended on the page: its time is kept from then on, and the date is
        # still first known at the run that took the decision in, so nothing queued since is carried over from it.
        self.sit(day)
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        report = self.report()
        self.assertIn(f"- Sitting {day}: 41 minutes.", report)
        self.assertNotIn("its time was not recorded", report)
        later = self.sitting_evidence(day)
        self.assertEqual(
            (later["minutes"], later["source"]["path"], later["taken_in_by_run"]),
            (41, f"founder/sittings/{day}.json", kept["taken_in_by_run"]),
        )
        self.assertEqual(self.carried(), {"20261011-left": day, "20261011-after": None})

    def test_a_sitting_whose_record_cannot_be_used_is_never_said_to_have_gone_unrecorded(self):
        """A report says what a record shows: with a file for the date that is no record, the run knows the sitting
        took place and does not know that no time was recorded."""
        day = self.two_items_one_decided_at_a_sitting_that_left_no_record()
        (self.exchange / "sittings" / f"{day}.json").write_text("{", encoding="utf-8")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        report = self.report()
        self.assertEqual(self.carried()["20261011-left"], day)
        self.assertIsNone(self.sitting_evidence(day)["minutes"])
        self.assertIn(f"- Could not use `founder/sittings/{day}.json`: it is not JSON (line 1)", report)
        self.assertNotIn("- Sitting ", report)

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_a_sittings_folder_that_cannot_be_read_is_never_said_to_hold_no_record(self):
        day = self.two_items_one_decided_at_a_sitting_that_left_no_record()
        (self.exchange / "sittings").chmod(0o300)
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        report = self.report()
        self.assertEqual(self.carried()["20261011-left"], day)
        self.assertIsNone(self.sitting_evidence(day)["minutes"])
        self.assertIn("| Sittings | failed | `founder/sittings/` could not be read: Permission denied. |", report)
        self.assertNotIn("- Sitting ", report)

    def test_a_decision_that_was_not_taken_in_shows_no_sitting(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        self.run_cycle()
        self.decide("20261011-unknown", "approve")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        carried = self.carried()
        self.assertIn("20261011-name-status-stale", carried)
        self.assertEqual(set(carried.values()), {None})
        self.assertFalse((self.ledger() / "evidence/sittings").exists())
        self.assertNotIn("- Sitting ", self.report())


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
            code, out = self.run_cycle()
            self.assertEqual(code, 0, out)
            self.assertEqual(self.run_cycle(repo=other, at=fakes.SUNDAY_RUN + timedelta(minutes=5))[0], cycle.EXIT_BUSY)
        # The run due a week later is still owed in this checkout, so its scheduled start reaches the lock.
        with self.hold_lock(self.repo):
            refused, _ = self.run_cycle(trigger="scheduled", at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=10))
            self.assertEqual(refused, cycle.EXIT_BUSY)
        self.run_cycle(repo=other, at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=15))
        self.assertEqual(re.findall(r"\(([a-z-]+)\) was refused", self.report(other)), ["on-demand"])
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=20))
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
        (kept,) = (self.ledger() / "review-queue/set-aside").iterdir()
        self.assertEqual(kept.name, f"{queue['updated_by_run']}.json")
        record = json.loads(kept.read_text(encoding="utf-8"))
        self.assertEqual([entry["name"] for entry in record["items"]], ["broken.md"])
        notice = (self.ledger() / queue["open"][0]["file"]).read_text(encoding="utf-8")
        self.assertIn("`broken.md`: sections must be exactly", notice)

    def test_look_alikes_in_the_agent_s_areas_never_change_the_launcher_s_records(self):
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
        self.assertEqual((self.workspace() / "instructions/README.md").read_text(encoding="utf-8"), "# instructions\n")
        self.assertIn(
            "- after the Package review session: `instructions/README.md` was changed during the run and put back as"
            " it was; only the rejection reasons' session may propose an Instructions change, and only the launcher"
            " changes the Instructions in force\n",
            problems,
        )
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
        report = self.report()
        self.assertIn("- The Package review session stopped with exit code 1; its work this run may be", report)
        self.assertIn("| Package review | ended with exit code 1 |", report)
        self.assertIn("| Package review (contradictions) | incomplete | its session ended with exit code 1 |", report)

    def test_a_review_the_agent_did_not_finish_is_incomplete_and_never_a_quiet_week(self):
        summary = "I could not complete this run's review, and I queued nothing."
        accounts = {
            "says it did not finish": (
                f"{summary}\n\nSession: incomplete: the rules pass is unfinished.\n",
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
                    " acted=1 note=package-review 16 files, 0 changed, 0 failed; 0 proposals queued;"
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
        summary = "Traced every recorded outcome.\n\n" + "x" * cycle.SUMMARY_LIMIT + "\n\nSession: complete\n"
        fakes.behave(self.codex_dir, {"summary": summary})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", report)
        self.assertIn("- checked=16 acted=0 note=nothing new needed action\n", report)
        self.assertEqual(self.queue()["open"], [])

    def test_a_late_scheduled_run_says_so(self):
        due = datetime(2026, 10, 11, 16, 0).astimezone()
        self.run_cycle(trigger="scheduled", at=(due + timedelta(minutes=1)).astimezone(timezone.utc))
        self.assertIn("started on time", self.report())
        week_later = datetime(2026, 10, 18, 19, 0).astimezone()
        self.run_cycle(trigger="scheduled", at=week_later.astimezone(timezone.utc))
        self.assertIn("Started late: due Sunday 2026-10-18 16:00,", self.report())
        self.assertIn("3 h 0 min after its time. The Mac was probably asleep or off when it was due.", self.report())

    def test_the_launch_agent_lateness_and_next_run_all_follow_run_json(self):
        path = self.repo / "config/run.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["schedule"].update(day="wednesday", time="09:30")
        config["window"].update(first_sitting="2099-01-07")  # a first sitting falls on the sitting's day
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

    def test_the_run_refuses_to_start_when_a_part_of_a_task_definition_is_missing(self):
        # Every session's definition is put together before anything else is done, so a run never starts some
        # sessions and then finds another's definition gone.
        (self.repo / "src/instructions/weekly-run/outreach.md").unlink()
        code, out = self.run_cycle()
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG)
        self.assertIn("refusing to start: the task definition part", out)
        self.assertIn("src/instructions/weekly-run/outreach.md could not be read", out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), [])
        self.assertFalse((self.ledger() / "run-reports").exists())


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
        [record] = self.logs.glob("2*Z-*.package-review.json")
        started = datetime.fromisoformat(json.loads(record.read_text(encoding="utf-8"))["started_at"])
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))
        run = record.name.split(".")[0]
        self.assertIn(
            f"Run {run} (scheduled), started {cycle.report.wall_clock(started):%A %Y-%m-%d %H:%M}, stopped"
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

    def test_the_open_request_stands_under_its_id_while_its_item_file_cannot_be_read(self):
        """A request is compared with its open item by that item's file; unread, it shows no reviewed change."""
        self.run_cycle()
        (request,) = self.queue()["open"]
        file = self.ledger() / request["file"]
        text = file.read_text(encoding="utf-8")
        fakes.behave(self.codex_dir, {})
        damages = (("not in its format", lambda: file.write_text("no item\n")), ("missing", file.unlink))
        for week, (name, damage) in enumerate(damages):
            with self.subTest(name):
                damage()
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14 * week + 7))
                self.assertEqual(code, 0, out)
                unread = f"`{request['file']}`, the item file of `{request['id']}`, could not be read ("
                self.assert_stands(request, "Review Queue", unread)
                self.assertIn(
                    f"note=reptoday-waitlist open as `{request['id']}`, left as it is, since {unread}", self.report()
                )
                self.assertRegex(self.report(), r"- dispatch-requests: checked=1 acted=0 note=.*; incomplete: `review")
                file.write_text(text, encoding="utf-8")
                code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14 * week + 14))
                self.assertEqual(code, 0, out)
                self.assert_never_asked_again(request)
                self.assertIn(f"note=reptoday-waitlist open as `{request['id']}`\n", self.report())

    def test_the_open_request_stands_while_its_reviewed_text_cannot_be_read(self):
        self.run_cycle()
        (request,) = self.queue()["open"]
        reviewed = self.repo / "src/dispatches/reptoday-waitlist.md"
        reviewed.chmod(0)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.entry(request["id"]), request)
        unread = "`src/dispatches/reptoday-waitlist.md` could not be read ("
        self.assertRegex(self.report(), rf"\| Review Queue \| incomplete \| [^|\n]*{re.escape(unread)}")
        self.assertIn(f"- {unread}", self.notices())
        reviewed.chmod(0o644)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        self.assert_never_asked_again(request)
        self.assertIn(f"note=reptoday-waitlist open as `{request['id']}`\n", self.report())

    def test_a_rejected_request_is_never_filed_again_while_its_item_file_cannot_be_read(self):
        """The fingerprint the run state holds of the rejected item settles it; with neither, the request is held."""
        self.run_cycle()
        (request,) = self.queue()["open"]
        self.decide(request["id"], "reject", reason="Not before the build.")
        fakes.behave(self.codex_dir, {})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        rejected = self.entry(request["id"])
        self.assertEqual(rejected["status"], "rejected")
        file = self.ledger() / request["file"]
        text = file.read_text(encoding="utf-8")
        file.write_text("no item\n", encoding="utf-8")

        def requests():
            queue = self.queue()
            return [entry for entry in queue["open"] + queue["closed"] if entry["kind"] == "dispatch-request"]

        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        self.assertEqual(requests(), [rejected], "the run state shows this text is the one the Founder rejected")
        self.assertIn(f"note=reptoday-waitlist rejected as `{request['id']}`; not asked again unless", self.report())

        (self.ledger() / "run-reports/state/review-queue.json").unlink()
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=21))
        self.assertEqual(code, 0, out)
        self.assertEqual(requests(), [rejected], "nothing filed and nothing withdrawn")
        unread = f"`{request['file']}`, the item file of `{request['id']}`, could not be read ("
        report = self.report()
        self.assertRegex(report, rf"\| Review Queue \| incomplete \| [^|\n]*{re.escape(unread)}")
        self.assertRegex(
            report,
            rf"- dispatch-requests: checked=1 acted=0 note=reptoday-waitlist not filed, since {re.escape(unread)}",
        )
        self.assertRegex(
            self.notices(),
            rf"- reptoday-waitlist not filed, since {re.escape(unread)}[^\n]*\), so nothing shows whether the Founder"
            " rejected this text; the next run compares them again",
        )
        self.assertNotIn("left exactly as it is", self.notices())

        file.write_text(text, encoding="utf-8")
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=28))
        self.assertEqual(code, 0, out)
        self.assertEqual(requests(), [rejected])
        self.assertIn(f"note=reptoday-waitlist rejected as `{request['id']}`; not asked again unless", self.report())

    def test_a_reviewed_change_to_the_request_s_text_still_replaces_its_open_item(self):
        self.run_cycle()
        (request,) = self.queue()["open"]
        reviewed = self.repo / "src/dispatches/reptoday-waitlist.md"
        text = reviewed.read_text(encoding="utf-8")
        reviewed.write_text(text.replace("## Touches", "One more reviewed line.\n\n## Touches", 1), encoding="utf-8")
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        (replaced,) = [entry for entry in self.queue()["open"] if entry["kind"] == "dispatch-request"]
        self.assertEqual(replaced["supersedes"], request["id"])
        old = self.entry(request["id"])
        self.assertEqual((old["status"], old["superseded_by"]), ("superseded", replaced["id"]))

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

    def test_an_item_with_the_kind_and_ask_of_a_request_filed_in_the_same_run_is_queued_as_always(self):
        """The request's item file was written this run and no read of it failed, so it is no unread item."""
        reviewed = (fakes.REPO / "src/dispatches/reptoday-waitlist.md").read_text(encoding="utf-8")
        another = reviewed.replace("\n## Touches\n", "\nBuild it another way.\n\n## Touches\n", 1)
        self.assertNotEqual(another, reviewed)
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/waitlist-another-way.md": another}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        day = f"{fakes.SUNDAY_RUN.astimezone():%Y%m%d}"
        filed, written = f"{day}-reptoday-waitlist", f"{day}-waitlist-another-way"
        queue = self.queue()
        self.assertEqual(sorted(entry["id"] for entry in queue["open"]), sorted([filed, written]), "no notice either")
        self.assertEqual(self.entry(filed)["ask"], self.entry(written)["ask"])
        report = self.report()
        self.assertIn("| Review Queue | complete | 2 open items |", report)
        self.assertNotIn("Set aside, not queued", report)
        self.assertNotIn(f"`{self.entry(filed)['file']}`, its item file, could not be read", report)


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

    def test_what_the_founder_recorded_at_a_sitting_is_saved_with_the_next_run_s_records(self):
        """The Founder's records are kept and saved with the launcher's own: the next run's first records step commits
        what a sitting wrote, the run takes it in, and both reach main."""
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        item = "20261011-name-status-stale"
        self.exchange = self.clone / "ledger" / "founder"  # the Founder's records are each checkout's own
        self.decide(item, "reject", reason="Wait for counsel.")
        day = self.sit()
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        self.assertIn("records left before this run, an earlier run's or a sitting's, were committed first", out)
        self.assertIn("records: pushed: pushed 2 records commits", out)
        subjects = fakes.git(self.remote, "log", "--format=%s", "-2", env=self.env).splitlines()
        self.assertTrue(subjects[1].startswith("chore(records): records left before the run of "), subjects)
        before = fakes.git(self.remote, "show", "--name-only", "--format=", "HEAD~1", env=self.env).split()
        self.assertEqual(
            sorted(before), [f"ledger/founder/decisions/{item}.json", f"ledger/founder/sittings/{day}.json"]
        )
        after = fakes.git(self.remote, "show", "--name-only", "--format=", "HEAD", env=self.env).split()
        self.assertIn(f"ledger/evidence/decisions/{item}.json", after)
        self.assertEqual([path for path in after if path.startswith("ledger/founder/")], [], "a run writes none")
        saved = fakes.git(self.remote, "show", f"HEAD:ledger/founder/decisions/{item}.json", env=self.env)
        self.assertEqual(json.loads(saved)["reason"], "Wait for counsel.")
        self.assertEqual(self.queue(self.clone)["closed"][0]["status"], "rejected")
        self.assertEqual(fakes.git(self.clone, "status", "--porcelain", env=self.env), "")

    def test_a_missing_records_folder_stops_the_run_before_its_removal_is_committed(self):
        """The refusal says to restore the folder from git, so the pre-run records step must not commit its removal
        first: git can still restore it, and nothing about it reaches main."""
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        head = fakes.git(self.clone, "rev-parse", "HEAD", env=self.env)
        shutil.rmtree(str(self.clone / "ledger/founder/outreach"))
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, launcher.EXIT_CONFIG, out)
        self.assertIn("founder/outreach must be a real folder that can be read", out)
        self.assertIn("restore it from git", out)
        self.assertEqual(fakes.git(self.clone, "rev-parse", "HEAD", env=self.env), head, "nothing was committed")
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), head, "nothing was pushed")

        fakes.git(self.clone, "restore", "ledger/founder/outreach", env=self.env)
        self.assertEqual(fakes.git(self.clone, "status", "--porcelain", env=self.env), "")
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=5))
        self.assertEqual(code, 0, out)
        saved = fakes.git(self.remote, "ls-tree", "-r", "--name-only", "HEAD", env=self.env).split()
        self.assertIn("ledger/founder/outreach/.gitkeep", saved)

    def test_a_public_repository_refuses_the_run_before_it_does_anything(self):
        """From the first real run on, a run pushes the Drafts, the Evidence, and the Founder's records, so while the
        repository is public nothing is fetched, snapshotted, started, or saved."""
        left, _ = self.leave_probe_files(self.clone)
        draft = self.clone / "workspace/drafts/day-3.md"
        draft.write_text("a Draft\n", encoding="utf-8")
        head = fakes.git(self.clone, "rev-parse", "HEAD", env=self.env)
        self.github = fakes.GitHub("public")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, cycle.EXIT_RECORDS, out)
        self.assertEqual(
            out,
            "gr0wthlab: refusing to start: the GitHub repository `example/gr0wthlab` is public: a real run would"
            " publish its Drafts, its Evidence, and the Founder's records there, so the repository must be made"
            " private first\n",
        )
        self.assertEqual(self.github.asked, [(self.clone, "origin")])
        self.assertFalse((self.codex_dir / "prompt.txt").exists(), "no session started")
        self.assertFalse((self.clone / ".git" / "FETCH_HEAD").exists(), "nothing was fetched")
        self.assertEqual(list((self.ledger(self.clone) / "evidence" / "package-snapshots").glob("*.json")), [])
        self.assertEqual(list((self.ledger(self.clone) / "run-reports").glob("2*")), [])
        self.assertEqual([path for path in left if not path.exists()], [], "nothing was removed")
        self.assertEqual(fakes.git(self.clone, "rev-parse", "HEAD", env=self.env), head, "nothing was committed")
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), head, "nothing was pushed")
        self.assertIn("?? workspace/drafts/day-3.md", fakes.git(self.clone, "status", "--porcelain", env=self.env))
        self.assertEqual(draft.read_text(encoding="utf-8"), "a Draft\n")

    def test_a_repository_that_cannot_be_confirmed_private_runs_and_keeps_its_records_local(self):
        """A passing network failure costs no run: the run goes ahead, its commit stays local, and its own report and
        notice say why."""
        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "a Draft\n"}})
        head = fakes.git(self.remote, "rev-parse", "HEAD", env=self.env)
        self.github = fakes.GitHub("unconfirmed")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.codex_dir / "prompt.txt").exists(), "the session ran")
        self.assertIn("pre-run: current", out)
        refusal = (
            "could not confirm that the GitHub repository is private (gh api exited with 1: error connecting to"
            " api.github.com), and a real run would publish its Drafts, its Evidence, and the Founder's records there"
        )
        self.assertIn(f"records: withheld: not pushed: {refusal}; the commits stay local for the next run\n", out)
        self.assertEqual(self.github.asked, [(self.clone, "origin")] * 2)
        self.assert_kept_local(head, refusal)

    def test_a_private_repository_is_asked_about_before_the_run_and_again_before_the_push(self):
        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "a Draft\n"}})
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertIn("records: pushed", out)
        self.assertEqual(self.github.asked, [(self.clone, "origin")] * 3)
        self.assertNotIn("kept local", self.report(self.clone))
        changed = fakes.git(self.remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertIn("workspace/drafts/day-3.md", changed)

    def test_a_repository_made_public_during_the_run_is_not_pushed_to(self):
        """The commit stays local, as after a failed push, and the run's own report and notice say why; the first run
        that finds the repository private pushes it. Made public after the report was written, and before the push
        retried once the remote moved, it is not pushed to either, and the next run's report says why."""
        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "a Draft\n"}})
        head = fakes.git(self.remote, "rev-parse", "HEAD", env=self.env)
        self.github = fakes.GitHub("private", "public")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        refusal = (
            "the GitHub repository `example/gr0wthlab` is public: a real run would publish its Drafts, its Evidence,"
            " and the Founder's records there, so the repository must be made private first"
        )
        self.assertIn(f"records: withheld: not pushed: {refusal}; the commits stay local for the next run\n", out)
        kept = self.assert_kept_local(head, refusal)

        self.github = fakes.GitHub("public")
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, cycle.EXIT_RECORDS, out)
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), head, "nothing was pushed")

        self.github = fakes.GitHub()
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=5))
        self.assertEqual(code, 0, out)
        self.assertIn("records: pushed", out)
        fakes.git(self.remote, "merge-base", "--is-ancestor", kept, "HEAD", env=self.env)

        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "another Draft\n"}})
        answers, landed = fakes.GitHub("private", "private", "private", "public"), []

        def github(repo, remote, env):
            if len(answers.asked) == 2:
                landed.append(self.land_on_remote())
            return answers(repo, remote, env)

        self.github = github
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=10))
        self.assertEqual(code, 0, out)
        withheld = f"not pushed: {refusal}; the commits stay local for the next run"
        self.assertIn(f"records: withheld: {withheld}\n", out)
        self.assertEqual(len(answers.asked), 4, "the retried push was asked about again")
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), landed[0], "nothing was pushed")
        late = fakes.git(self.clone, "rev-parse", "HEAD", env=self.env)
        self.assertEqual(fakes.git(self.clone, "rev-parse", "HEAD~1", env=self.env), landed[0], "replayed on top")
        self.assertNotIn("kept local", self.report(self.clone), "the report was written before the answer")
        run_id = re.search(r"^gr0wthlab: run (\S+) \(", out, re.M).group(1)

        self.github = fakes.GitHub()
        code, out = self.run_cycle(repo=self.clone, at=fakes.SUNDAY_RUN + timedelta(days=7, minutes=15))
        self.assertEqual(code, 0, out)
        self.assertIn("records: pushed", out)
        self.assertIn(f"\n- Run {run_id}'s records were committed and {withheld}.\n", self.report(self.clone))
        fakes.git(self.remote, "merge-base", "--is-ancestor", late, "HEAD", env=self.env)

    def land_on_remote(self):
        """A commit another clone pushes to the remote while a run is going; returns it."""
        other = self.root / "elsewhere"
        fakes.git(self.root, "clone", "--quiet", str(self.remote), str(other), env=self.env)
        (other / "landed.md").write_text("landed meanwhile\n", encoding="utf-8")
        fakes.git(other, "add", "landed.md", env=self.env)
        fakes.git(other, "commit", "--quiet", "-m", "landed meanwhile", env=self.env)
        fakes.git(other, "push", "--quiet", "origin", "main", env=self.env)
        return fakes.git(other, "rev-parse", "HEAD", env=self.env)

    def assert_kept_local(self, head, refusal):
        """Nothing reached the remote, the run's records are committed in the clone, and the run's own report and its
        notice say they were kept local, with GitHub's answer; returns the kept commit."""
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), head, "nothing was pushed")
        kept = fakes.git(self.clone, "rev-parse", "HEAD", env=self.env)
        self.assertNotEqual(kept, head)
        self.assertIn("workspace/drafts/day-3.md", fakes.git(self.clone, "show", "--name-only", kept, env=self.env))
        self.assertEqual(fakes.git(self.clone, "status", "--porcelain", env=self.env), "")
        told = (
            f"this run's records were kept local, not pushed: {refusal}; a later run pushes them once GitHub says the"
            " repository is private"
        )
        report = self.report(self.clone)
        self.assertIn(f"- {told}", report.partition("\n## Launcher problems\n")[2])
        named = re.search(r"listed in the notice `([^`]+)`", report)
        self.assertIsNotNone(named, report)
        notice = next(entry for entry in self.queue(self.clone)["open"] if entry["id"] == named.group(1))
        self.assertIn(told, (self.ledger(self.clone) / notice["file"]).read_text(encoding="utf-8"))
        return kept

    def test_a_run_that_saves_nothing_starts_while_the_repository_is_public(self):
        """With records.save_after_run off a run pushes nothing, so it asks GitHub nothing and starts as any run
        does."""
        fakes.set_run(self.clone, "records", {"save_after_run": False})
        fakes.git(self.clone, "commit", "--quiet", "-am", "save no records", env=self.env)
        fakes.git(self.clone, "push", "--quiet", "origin", "main", env=self.env)
        head = fakes.git(self.remote, "rev-parse", "HEAD", env=self.env)
        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "a Draft\n"}})
        self.github = fakes.GitHub("public")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.codex_dir / "prompt.txt").exists(), "the session ran")
        self.assertIn("pre-run: current", out)
        self.assertIsNone(re.search(r"^gr0wthlab: records:", out, re.M), out)
        self.assertEqual(self.github.asked, [])
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), head, "nothing was pushed")
        self.assertNotIn("kept local", self.report(self.clone))

    def test_a_run_restarted_on_a_configuration_that_saves_asks_again_and_refuses_while_public(self):
        """The process that runs the sessions asks by its own configuration, so a reviewed change the sync brings in
        that turns saving on, while the repository is public, stops the restarted run before any session."""
        fakes.set_run(self.repo, "records", {"save_after_run": False})
        fakes.git(self.repo, "commit", "--quiet", "-am", "save no records", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.clone, "pull", "--quiet", env=self.env)
        fakes.set_run(self.repo, "records", {"save_after_run": True})
        fakes.git(self.repo, "commit", "--quiet", "-am", "save records again", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        head = fakes.git(self.remote, "rev-parse", "HEAD", env=self.env)
        self.github = fakes.GitHub("public")
        calls = []
        code, out = self.run_cycle(repo=self.clone, execve=lambda *args: calls.append(args))
        self.assertEqual(len(calls), 1, out)
        self.assertEqual(self.github.asked, [], "the configuration before the sync saved nothing")

        self.env[cycle.PRE_RUN_ENV] = calls[0][2][cycle.PRE_RUN_ENV]
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, cycle.EXIT_RECORDS, out)
        self.assertEqual(
            out,
            "gr0wthlab: refusing to start: the GitHub repository `example/gr0wthlab` is public: a real run would"
            " publish its Drafts, its Evidence, and the Founder's records there, so the repository must be made"
            " private first\n",
        )
        self.assertEqual(self.github.asked, [(self.clone, "origin")])
        self.assertFalse((self.codex_dir / "prompt.txt").exists(), "no session started")
        self.assertEqual(list((self.ledger(self.clone) / "evidence" / "package-snapshots").glob("*.json")), [])
        self.assertEqual(list((self.ledger(self.clone) / "run-reports").glob("2*")), [])
        self.assertEqual(fakes.git(self.clone, "rev-parse", "HEAD", env=self.env), head, "nothing was committed")
        self.assertEqual(fakes.git(self.remote, "rev-parse", "HEAD", env=self.env), head, "nothing was pushed")

    def test_a_run_outside_the_production_clone_asks_github_nothing(self):
        self.github = fakes.GitHub("public")
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn("not the production clone", self.report())
        self.assertEqual(self.github.asked, [])

    def leave_probe_files(self, repo):
        """What a boundary check killed mid-run leaves at the top of the areas: its script and a sentinel."""
        left = [
            repo / "workspace/drafts" / f"{PROBE_PREFIX}20261001T000000Z-on-demand-0001-permitted-shell.txt",
            repo / "workspace/instructions" / f"{PROBE_PREFIX}20261001T000000Z-on-demand-0001-shell-steps.sh",
        ]
        for path in left:
            path.write_text("left behind\n", encoding="utf-8")
        return left, ", ".join(str(path.relative_to(repo)) for path in left)

    def committed_probe_files(self):
        """Every path any commit holds, in the clone or on the remote, that a boundary check names its files by."""
        for repo in (self.clone, self.remote):
            history = fakes.git(repo, "log", "--all", "--name-only", "--format=", env=self.env).split("\n")
            yield from (path for path in history if PROBE_PREFIX in path)

    def test_what_a_stopped_boundary_check_left_is_removed_before_a_records_step_can_commit_it(self):
        left, names = self.leave_probe_files(self.clone)
        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "a Draft\n"}})
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertIn(f"pre-run: removed boundary probe files left in the areas: {names}\n", out)
        self.assertLess(out.index("pre-run: removed boundary probe files"), out.index("pre-run: current"))
        self.assertEqual(out.count("removed boundary probe files"), 1, "nothing was left for the run's own clearing")
        self.assertEqual([path for path in left if path.exists()], [])
        self.assertIn("records: pushed: pushed 1 records commit", out)
        changed = fakes.git(self.remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertIn("workspace/drafts/day-3.md", changed)
        self.assertEqual(list(self.committed_probe_files()), [])
        quoted = ", ".join(f"`{path.relative_to(self.clone)}`" for path in left)
        self.assertIn(
            "## Agent\n\n- Removed boundary probe files left in the areas, before any agent could find them: "
            f"{quoted}\n- Boundary preflight: passed",
            self.report(self.clone),
        )

    def test_a_run_restarted_on_new_code_reports_what_was_removed_before_the_sync(self):
        (self.repo / "config" / "note.txt").write_text("reviewed change\n")
        fakes.git(self.repo, "add", "--all", env=self.env)
        fakes.git(self.repo, "commit", "--quiet", "-m", "reviewed", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        left, names = self.leave_probe_files(self.clone)
        calls = []
        code, out = self.run_cycle(repo=self.clone, execve=lambda *args: calls.append(args))
        self.assertEqual(len(calls), 1, out)
        self.assertIn(f"pre-run: removed boundary probe files left in the areas: {names}\n", out)
        self.assertEqual([path for path in left if path.exists()], [])
        self.env[cycle.PRE_RUN_ENV] = calls[0][2][cycle.PRE_RUN_ENV]
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertNotIn("removed boundary probe files", out)
        self.assertIn(
            "- Removed boundary probe files left in the areas, before any agent could find them: `workspace/drafts/",
            self.report(self.clone),
        )
        self.assertEqual(list(self.committed_probe_files()), [])

    def test_with_the_sync_off_the_run_itself_removes_it_before_the_agent_and_the_save(self):
        fakes.set_run(self.repo, "records", {"sync_before_run": False})
        fakes.git(self.repo, "commit", "--quiet", "-am", "reviewed", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.clone, "pull", "--quiet", env=self.env)
        left, names = self.leave_probe_files(self.clone)
        fakes.behave(self.codex_dir, {"write": {"drafts/day-3.md": "a Draft\n"}})
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, 0, out)
        self.assertNotIn("pre-run:", out)
        self.assertIn(f"gr0wthlab: removed boundary probe files left in the areas: {names}\n", out)
        self.assertLess(out.index("removed boundary probe files"), out.index("preflight refused"))
        self.assertIn("records: pushed", out)
        self.assertEqual(list(self.committed_probe_files()), [])
        self.assertIn(
            "- Removed boundary probe files left in the areas, before any agent could find them: `workspace/drafts/",
            self.report(self.clone),
        )

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
        with (self.clone / "src/instructions/weekly-run/common.md").open("a") as handle:
            handle.write("Unreviewed line.\n")
        code, out = self.run_cycle(repo=self.clone)
        self.assertEqual(code, cycle.EXIT_RECORDS)
        self.assertIn("changes outside workspace/ and ledger/", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())


class PostDraftsTest(CycleTestCase):
    """US-ME08's Validation Test, on the synthetic kit: the first batch matches the calendar, and a banned word put
    into one caption blocks that Draft, naming the rule, so it never reaches the Review Queue."""

    def check_drafts(self, run_id):
        out = io.StringIO()
        with (
            mock.patch.object(cli, "REPO_ROOT", self.repo),
            mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"),
            mock.patch.dict(os.environ, self.env),
        ):
            return cli.check_drafts(run_id, out), out.getvalue()

    def run_with_check_drafts(self, at=None, meanwhile=None):
        """Run a cycle whose post Drafts session, once it has written its files, runs check-drafts for its run while
        the run is still in progress, as its brief tells it to; returns check-drafts's exit code and its output.
        meanwhile is what happens outside the run while that agent works, before it runs check-drafts."""
        launch, seen = cycle.launcher.run, []

        def agent(*args, **kwargs):
            result = launch(*args, **kwargs)
            if kwargs["session"] == "post-drafts":
                if meanwhile:
                    meanwhile()
                seen.append(self.check_drafts(kwargs["run_id"]))
            return result

        with mock.patch.object(cycle.launcher, "run", agent):
            code, out = self.run_cycle(at=at)
        self.assertEqual(code, 0, out)
        return seen[0]

    def first_batch(self):
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        return self.queue()

    def test_the_first_batch_is_days_1_to_7_and_each_passing_draft_is_one_post(self):
        queue = self.first_batch()
        posts_open = [entry for entry in queue["open"] if entry["kind"] == "post"]
        self.assertEqual([entry["day"] for entry in posts_open], [1, 2, 3, 4, 6, 7])
        self.assertTrue(all("slot" not in entry for entry in posts_open))
        self.assertEqual(posts_open[0]["ask"], "Approve day 1 post: open-to-ready demo, hook A")
        for entry in posts_open:
            text = (self.ledger() / entry["file"]).read_text(encoding="utf-8")
            angle = fakes.KIT_DAYS[entry["day"]][0]
            self.assertIn(f"- Angle {angle},", text)
            self.assertIn(fakes.KIT_DAYS[entry["day"]][3], text)
            self.assertIn("Nothing can be published until the RepToday Waitlist is live.", text)

        report = self.report()
        self.assertIn("so this run prepares days 1 to 7 as the first batch", report)
        self.assertIn("| 5 | P05 | blocked |", report)
        self.assertIn(
            "- projects/RepToday/gtm/08-redteam/pre-publication-checklist.md line 12: Device benchmark record for the"
            ' "under 100 milliseconds" claim: Angle P05 depends on the claim',
            report,
        )
        self.assertIn("- Post Drafts: 6 queued, 1 blocked.", report)
        self.assertIn("| RepToday repository | read |", report)
        self.assertIn("| Post Drafts | complete | 7 days: 6 queued, 1 blocked |", report)
        notice = next(entry for entry in queue["open"] if entry["kind"] == "notice")
        self.assertIn("Day 5 (`drafts/posts/window-1/day-05.md`)", (self.ledger() / notice["file"]).read_text())
        evidence = json.loads((self.ledger() / f"evidence/post-drafts/{queue['updated_by_run']}.json").read_text())
        self.assertEqual([day["status"] for day in evidence["days"]], ["queued"] * 4 + ["blocked"] + ["queued"] * 2)
        self.assertNotIn("brand-rules-word-lists", json.dumps(queue))

        brief = self.brief()
        self.assertIn("## Post Drafts", brief)
        self.assertIn(
            "| 3 | Score dip demo | P03 / AB-2 leg A | YouTube Shorts | Skip a day and the score dips. It never resets."
            " (`projects/RepToday/gtm/05-social-pmf/ab-pairs.md` line 13) | nothing yet |",
            brief,
        )
        self.assertIn(f"is commit `{fakes.git(self.code, 'rev-parse', 'main', env=self.env)}`", brief)
        self.assertIn("- Competitors the research names, which no Draft may name: IronFit, Pulseday, Stretchly.", brief)
        self.assertIn(
            "run on every field a viewer reads: hook_max_words, hook_must_not_be_question, banned_words_in_hook,", brief
        )
        self.assertIn(
            "  Of these rules, each beat's visual action, a filming note, is read only for social-proof phrases; it is"
            " also checked for another Hook.\n",
            brief,
        )
        self.assertIn(
            f"`GR0WTHLAB_MANDU_DIR={self.mandu} GR0WTHLAB_REPTODAY_DIR={self.code} /usr/bin/python3"
            f" {self.repo}/src/bin/gr0wthlab check-drafts --run {queue['updated_by_run']}`",
            brief,
        )

    def test_a_banned_word_put_into_one_caption_blocks_that_draft_naming_the_rule(self):
        first = self.first_batch()
        day_3 = next(entry["id"] for entry in first["open"] if entry.get("day") == 3)
        caption = "No grind here, only a score that forgives."
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3, caption=caption)}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        queue = self.queue()
        self.assertNotIn(3, [entry.get("day") for entry in queue["open"]])
        self.assertNotIn(
            "grind", json.dumps([(self.ledger() / e["file"]).read_text() for e in queue["open"] if e["kind"] == "post"])
        )
        withdrawn = next(entry for entry in queue["closed"] if entry["id"] == day_3)
        self.assertEqual((withdrawn["status"], withdrawn["withdrawn"]), ("superseded", True))
        notice = next(
            entry for entry in queue["open"] if entry["kind"] == "notice" and entry["id"] != first["open"][-1]["id"]
        )
        text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn("banned_words_in_hook: banned word 'grind' (TikTok caption, YouTube Shorts description)", text)
        self.assertEqual(withdrawn["superseded_by"], notice["id"])
        report = self.report()
        self.assertIn("| 3 | P03 / AB-2 leg A | blocked |", report)
        self.assertIn("| 1 | P01 / AB-1 leg A | kept |", report)

    def test_a_refused_item_leaves_its_name_and_reasons_and_a_draft_waiting_for_a_fix_stays_as_written(self):
        """Of what the launcher refuses, only a Draft waiting for a fix keeps the agent's words: each item set aside
        from incoming/, of every kind, leaves its name and reasons, and nothing of its text anywhere."""
        marker = "zqxstranger"
        refused = fakes.refused_items(marker)
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        waiting = fakes.draft(3, caption="No grind here, only what zqxdraftwords said.")
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        writes[fakes.draft_path(3)] = waiting
        writes.update({f"review-queue/incoming/{name}": text for name, text in refused.items()})
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        queue = self.queue()
        run = queue["updated_by_run"]
        record = json.loads((self.ledger() / f"review-queue/set-aside/{run}.json").read_text(encoding="utf-8"))
        self.assertEqual({entry["name"] for entry in record["items"]}, set(refused))
        self.assertTrue(all(set(entry) == {"name", "reasons"} and entry["reasons"] for entry in record["items"]))
        self.assertEqual(os.listdir(self.ledger() / "review-queue/set-aside"), [f"{run}.json"])
        self.assertEqual(os.listdir(self.workspace() / "review-queue/incoming"), [])
        report, notices = self.report(), self.notices()
        for name in refused:
            self.assertIn(f"- Set aside, not queued: `{name}`: ", report)
            self.assertIn(f"- `{name}`: ", notices)
        # Nothing the run left anywhere holds the refused files' words: the ledger, the workspace, and the run's
        # record in the log folder. Only the fake agent's own instructions, in its folder, hold them.
        for path in self.root.rglob("*"):
            if path.is_file() and self.codex_dir not in path.parents and ".git" not in path.parts:
                self.assertNotIn(marker.encode(), path.read_bytes(), path)
        self.assertNotIn(marker, fakes.git(self.repo, "log", "--all", "-p", env=self.env))
        # The Draft waiting for a fix is blocked and stays exactly as the agent wrote it.
        self.assertIn("| 3 | P03 / AB-2 leg A | blocked |", report)
        self.assertEqual((self.workspace() / fakes.draft_path(3)).read_text(encoding="utf-8"), waiting)

    def lose_the_claim_file(self):
        """Make git's read of the one file every claim cites fail, as a damaged object does, while the branch still
        resolves to its commit; returns what puts the object back."""
        blob = fakes.git(self.code, "rev-parse", "main:Engine/ConsistencyScore.swift", env=self.env).strip()
        loose, away = self.code / ".git/objects" / blob[:2] / blob[2:], self.root / "object-set-aside"
        shutil.move(str(loose), str(away))
        return lambda: shutil.move(str(away), str(loose))

    def test_an_open_post_stands_under_its_id_while_git_cannot_read_the_file_its_claim_cites(self):
        """The defect as the Founder met it: a single-file git read that failed took every open post back as
        "there is no file", with the Post Drafts reading complete, and the next run asked each again under a new
        identifier."""
        first = self.first_batch()
        open_posts = [entry for entry in first["open"] if entry["kind"] == "post"]
        self.assertEqual(len(open_posts), 6)
        restore = self.lose_the_claim_file()
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        unread = "git could not read `Engine/ConsistencyScore.swift` in RepToday's code"
        for post in open_posts:
            self.assert_stands(post, "Post Drafts", unread)
        report = self.report()
        day_3 = open_posts[2]["id"]
        self.assertIn(
            f"| 3 | P03 / AB-2 leg A | kept | `{day_3}`; not checked again, since {unread}; the open item stands |",
            report,
        )
        self.assertIn("| RepToday repository | read |", report)
        self.assertIn("- post-drafts: checked=7 acted=0 note=7 days: 6 kept, 1 blocked; incomplete: git could", report)
        self.assertNotIn("there is no file", report + self.notices())
        self.assertNotIn("was withdrawn", report)
        self.assertNotIn("is withdrawn", self.notices())
        # Day 5 has no open post, so its Draft is blocked, and the block names the read, never a missing file.
        self.assertRegex(report, r"- claim-location: .*: git could not read it \(fatal: .*ConsistencyScore\.swift")
        restore()
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=2))
        self.assertEqual(code, 0, out)
        for post in open_posts:
            self.assert_never_asked_again(post)
        report = self.report()
        self.assertIn(f"| 3 | P03 / AB-2 leg A | kept | `{day_3}`; its Draft is unchanged and passes |", report)
        self.assertIn("| Post Drafts | complete | 7 days: 6 kept, 1 blocked |", report)

    def test_an_open_post_is_still_withdrawn_once_the_file_its_claim_cites_is_gone_from_the_code(self):
        first = self.first_batch()
        day_3 = next(entry["id"] for entry in first["open"] if entry.get("day") == 3)
        fakes.git(self.code, "rm", "--quiet", "Engine/ConsistencyScore.swift", env=self.env)
        fakes.git(self.code, "commit", "--quiet", "-m", "the score moved", env=self.env)
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        withdrawn = self.entry(day_3)
        self.assertEqual((withdrawn["status"], withdrawn["withdrawn"]), ("superseded", True))
        report = self.report()
        self.assertRegex(
            report, r"- claim-location: .*: there is no file Engine/ConsistencyScore\.swift at [0-9a-f]{7}"
        )
        self.assertIn(f"| 3 | P03 / AB-2 leg A | blocked | 1 failing check, listed below; the open `{day_3}`", report)
        self.assertIn("| Post Drafts | complete | 7 days: 7 blocked; 6 withdrawn |", report)
        self.assertIn(
            f"- The open post `{day_3}` for day 3 is withdrawn, since its Draft no longer passes.", self.notices()
        )
        self.assertNotIn("not checked again", report + self.notices())

    def test_an_open_post_stands_under_its_id_while_its_draft_cannot_be_read(self):
        first = self.first_batch()
        post = next(entry for entry in first["open"] if entry.get("day") == 3)
        path = self.workspace() / fakes.draft_path(3)
        written = path.read_bytes()
        path.write_bytes(b"\xff\xfe not text")
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        self.assert_stands(post, "Post Drafts", "`drafts/posts/window-1/day-03.md` could not be read (")
        self.assertNotIn("was withdrawn", self.report())
        path.write_bytes(written)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=2))
        self.assertEqual(code, 0, out)
        self.assert_never_asked_again(post)
        self.assertIn("| Post Drafts | complete | 7 days: 6 kept, 1 blocked |", self.report())

    def test_no_item_the_agent_writes_takes_a_post_off_the_queue(self):
        first = self.first_batch()
        day_3 = next(entry["id"] for entry in first["open"] if entry.get("day") == 3)
        instead = fakes.proposal("notice", f"supersedes: {day_3}\n", "day 3 is off")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/day-3-off.md": instead}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        self.assertIn(day_3, [entry["id"] for entry in self.queue()["open"]])
        report = self.report()
        self.assertIn(
            f"- Set aside, not queued: `day-3-off.md`: supersedes {day_3}, a post the launcher queued from its Draft;"
            " only a change to that Draft in drafts/posts/ replaces it",
            report,
        )
        self.assertIn("| 3 | P03 / AB-2 leg A | kept |", report)
        self.assertIn(
            "and a post or a message only through its Draft, so an item that supersedes any of them is refused.",
            self.brief(),
        )

    def test_a_withdrawn_post_is_counted_once_and_leaves_the_report_s_count_of_open_items(self):
        self.first_batch()
        caption = "No grind here, only a score that forgives."
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3, caption=caption)}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        # Five posts stand, with the first run's notice and this run's.
        self.assertEqual(len(self.queue()["open"]), 7)
        report = self.report()
        self.assertIn("- Review Queue: 7 items open for the next sitting", report)
        self.assertIn("| Review Queue | complete | 7 open items |", report)
        self.assertRegex(report, r"- review-queue: checked=\d+ acted=1 note=.* 1 other item queued, 0 superseded,")
        self.assertIn("- post-drafts: checked=7 acted=1 note=7 days: 5 kept, 2 blocked; 1 withdrawn\n", report)
        self.assertRegex(report, r"## Summary\n\n- checked=\d+ acted=2 note=")

    def test_a_draft_restored_after_its_post_was_withdrawn_is_offered_again(self):
        first = self.first_batch()
        day_3 = next(entry["id"] for entry in first["open"] if entry.get("day") == 3)
        caption = "No grind here, only a score that forgives."
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3, caption=caption)}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertNotIn(3, [entry.get("day") for entry in self.queue()["open"]])
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3)}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=2))
        self.assertEqual(code, 0, out)
        queue = self.queue()
        [restored] = [entry for entry in queue["open"] if entry.get("day") == 3]
        self.assertEqual(restored["id"], f"{day_3}-2")
        self.assertIn("| 3 | P03 / AB-2 leg A | queued |", self.report())

    def test_a_rejected_draft_left_unchanged_is_not_asked_again_when_the_product_s_code_moves_on(self):
        first = self.first_batch()
        day_4 = next(entry["id"] for entry in first["open"] if entry.get("day") == 4)
        self.decide(day_4, "reject", reason="Too flat.")
        (self.code / "App/Later.swift").write_text("struct Later {}\n", encoding="utf-8")
        fakes.git(self.code, "add", "--all", env=self.env)
        fakes.git(self.code, "commit", "--quiet", "-m", "later", env=self.env)
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        queue = self.queue()
        self.assertNotIn(4, [entry.get("day") for entry in queue["open"]])
        self.assertEqual([entry["id"] for entry in queue["closed"] if entry.get("day") == 4], [day_4])
        self.assertIn(
            f"| 4 | P04 | not queued again | `{day_4}`; the Founder rejected this Draft, so it is not asked again"
            " until it changes |",
            self.report(),
        )

    def test_a_post_says_the_waitlist_is_live_only_from_the_date_config_sets(self):
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        fakes.set_run(self.repo, "waitlist", {"live_since": "2026-10-12"})
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(1): fakes.draft(1)}})
        self.run_cycle()
        [ahead] = [entry for entry in self.queue()["open"] if entry["kind"] == "post"]
        waiting = "Nothing can be published until the RepToday Waitlist is live."
        self.assertIn(waiting, (self.ledger() / ahead["file"]).read_text(encoding="utf-8"))
        self.assertIn("The RepToday Waitlist is not live, so nothing can be published yet", self.brief())
        self.assertIn("- Nothing can be published until the RepToday Waitlist is live", self.report())

        fakes.set_run(self.repo, "waitlist", {"live_since": "2026-10-11"})
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(2): fakes.draft(2)}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        live = next(entry for entry in self.queue()["open"] if entry.get("day") == 2)
        text = (self.ledger() / live["file"]).read_text(encoding="utf-8")
        self.assertIn("The Waitlist is live.", text)
        self.assertNotIn(waiting, text)
        self.assertNotIn("Waitlist is not live", self.brief())
        self.assertNotIn("Nothing can be published until", self.report())

    def test_check_drafts_checks_two_legs_drafted_in_one_run_as_the_launcher_will(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 3, 10)
        writes = {
            fakes.draft_path(3): fakes.draft(3),
            fakes.draft_path(10): fakes.draft(10, caption="A different second line."),
        }
        fakes.behave(self.codex_dir, {"write": writes})
        # A Monday run has both legs due.
        code, text = self.run_with_check_drafts(at=fakes.SUNDAY_RUN + timedelta(days=1))
        self.assertEqual(code, 1, text)
        self.assertIn("OK day 3: drafts/posts/window-1/day-03.md", text)
        self.assertIn("BLOCKED day 10: drafts/posts/window-1/day-10.md", text)
        self.assertIn("  - pair-legs: differs from day 3's leg beyond the Hook", text)
        self.assertIn("2 days due, 1 with problems", text)
        report = self.report()
        self.assertIn("| 3 | P03 / AB-2 leg A | queued |", report)
        self.assertIn("| 10 | P03 / AB-2 leg B | blocked |", report)

    def test_check_drafts_reads_the_standing_the_launcher_recorded_after_taking_in_decisions(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 1, 8)
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(1): fakes.draft(1)}})
        self.run_cycle()
        [day_1] = [entry["id"] for entry in self.queue()["open"] if entry["kind"] == "post"]
        self.decide(day_1, "reject", reason="The second line is flat.")
        answer = fakes.draft(8, caption="One tap, and the first movement is on screen.")
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(8): answer}})
        # The queue saved by the last run still holds day 1 as open while this run's agent works.
        code, text = self.run_with_check_drafts(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(
            (code, text.splitlines()[1:]),
            (0, ["OK day 8: drafts/posts/window-1/day-08.md", "1 day due, 0 with problems"]),
        )
        queue = self.queue()
        self.assertEqual([entry["day"] for entry in queue["open"] if entry["kind"] == "post"], [8])
        record = json.loads((self.ledger() / f"run-reports/{queue['updated_by_run']}.post-plan.json").read_text())
        self.assertEqual((record["run"], record["posted"]), (queue["updated_by_run"], {}))
        self.assertEqual([(due["day"], due["open"], due["rejected"]) for due in record["due"]], [(8, None, [])])
        self.assertIn(f"check-drafts --run {queue['updated_by_run']}`", self.brief())

    def test_check_drafts_checks_claims_at_the_commit_the_launcher_fixed_whatever_lands_on_main_since(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 3)
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3)}})
        fixed = fakes.git(self.code, "rev-parse", "main", env=self.env)

        def a_commit_lands():
            score = self.code / "Engine/ConsistencyScore.swift"
            score.write_text(score.read_text().replace("value - missPenalty", "value - penalty"))
            fakes.git(self.code, "commit", "--quiet", "--all", "-m", "rename the penalty", env=self.env)

        code, text = self.run_with_check_drafts(meanwhile=a_commit_lands)
        self.assertNotEqual(fakes.git(self.code, "rev-parse", "main", env=self.env), fixed)
        self.assertEqual(
            (code, text.splitlines()[1:]),
            (0, ["OK day 3: drafts/posts/window-1/day-03.md", "1 day due, 0 with problems"]),
        )
        queue = self.queue()
        record = json.loads((self.ledger() / f"run-reports/{queue['updated_by_run']}.post-plan.json").read_text())
        self.assertEqual(record["code"], {"commit": fixed, "problem": None})
        report = self.report()
        self.assertIn(
            f"- Claims checked against RepToday `main` at `{fixed[:7]}` (`{self.code}`). Only the claims a Draft lists"
            " are checked; each post item says so.",
            report,
        )
        self.assertIn("| 3 | P03 / AB-2 leg A | queued |", report)

    def test_check_drafts_keeps_the_launcher_s_reason_when_it_could_not_read_the_code_before_the_agent_started(self):
        shutil.rmtree(self.code)
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 3)
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3)}})
        code, text = self.run_with_check_drafts(meanwhile=lambda: fakes.make_code(self.code, self.env))
        self.assertEqual(code, 1, text)
        missing = f"the RepToday checkout {self.code} does not exist"
        self.assertIn(f"PROBLEM RepToday's code could not be read: {missing}", text)
        self.assertIn("BLOCKED day 3: drafts/posts/window-1/day-03.md", text)
        self.assertIn(
            f"  - claim-location: 'A missed day lowers the score, and nothing resets it to zero.': {missing}", text
        )
        self.assertIn("| 3 | P03 / AB-2 leg A | blocked |", self.report())

    def test_check_drafts_names_a_kit_file_that_is_no_longer_as_the_launcher_read_it(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 3)
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): fakes.draft(3)}})
        checklist = "projects/RepToday/gtm/08-redteam/pre-publication-checklist.md"

        def the_trademark_line_is_reopened():
            path = self.mandu / checklist
            path.write_text(path.read_text().replace("- [x] **Trademark", "- [ ] **Trademark"))

        code, text = self.run_with_check_drafts(meanwhile=the_trademark_line_is_reopened)
        self.assertEqual(code, 1, text)
        self.assertEqual(
            text.splitlines()[1],
            f"Kit files in Mandu that are no longer as the launcher read them for this run: `{checklist}`. The"
            " launcher checks every Draft against what it read then, so its verdict may differ from the ones below,"
            " which use what Mandu holds now.",
        )
        self.assertIn("BLOCKED day 3: drafts/posts/window-1/day-03.md", text)
        self.assertIn(f"  - {checklist} line 7: Trademark search for the name", text)
        queue = self.queue()
        record = json.loads((self.ledger() / f"run-reports/{queue['updated_by_run']}.post-plan.json").read_text())
        self.assertEqual(record["kit"]["checklist"]["path"], checklist)
        self.assertNotEqual(
            record["kit"]["checklist"]["sha256"], hashlib.sha256((self.mandu / checklist).read_bytes()).hexdigest()
        )
        self.assertIn("| 3 | P03 / AB-2 leg A | queued |", self.report())

    def test_check_drafts_names_a_day_due_that_the_calendar_no_longer_holds_and_checks_the_rest(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.keep_days(self.mandu, 3, 4)
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(day): fakes.draft(day) for day in (3, 4)}})
        calendar = "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
        changed = (
            f"Kit files in Mandu that are no longer as the launcher read them for this run: `{calendar}`. The"
            " launcher checks every Draft against what it read then, so its verdict may differ from the ones below,"
            " which use what Mandu holds now."
        )
        gone = "PROBLEM day {0}: the calendar as Mandu holds it now has no day {0}, so its Draft was not checked"
        code, text = self.run_with_check_drafts(meanwhile=lambda: fakes.keep_days(self.mandu, 4))
        self.assertEqual(
            (code, text.splitlines()[1:]),
            (
                1,
                [changed, gone.format(3), "OK day 4: drafts/posts/window-1/day-04.md", "2 days due, 1 with problems"],
            ),
        )
        report = self.report()
        self.assertIn("| 3 | P03 / AB-2 leg A | queued |", report)
        self.assertIn("| 4 | P04 | queued |", report)
        (self.mandu / calendar).write_text("No table here.\n", encoding="utf-8")
        code, text = self.check_drafts(self.queue()["updated_by_run"])
        self.assertEqual(
            (code, text.splitlines()[1:]), (1, [changed, gone.format(3), gone.format(4), "2 days due, 2 with problems"])
        )

    def test_check_drafts_names_a_draft_the_founder_rejected_and_skips_a_day_the_founder_approved(self):
        first = self.first_batch()
        ids = {entry["day"]: entry["id"] for entry in first["open"] if entry["kind"] == "post"}
        self.decide(ids[4], "reject", reason="Too flat.")
        self.decide(ids[6], "approve")
        fakes.behave(self.codex_dir, {})
        code, text = self.run_with_check_drafts(at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 1, text)
        self.assertIn(
            f"REJECTED day 4: drafts/posts/window-1/day-04.md: the Founder rejected this Draft as {ids[4]}, so it is"
            " not asked again until it changes",
            text,
        )
        self.assertIn(f"SKIP day 6: approved as {ids[6]}; it is not asked again", text)
        self.assertIn("OK day 1: drafts/posts/window-1/day-01.md", text)
        report = self.report()
        self.assertIn(f"| 4 | P04 | not queued again | `{ids[4]}`;", report)
        self.assertIn(f"| 6 | P06 | approved earlier | `{ids[6]}`;", report)

    def test_check_drafts_checks_no_draft_without_the_run_s_recorded_plan(self):
        run_id = "20261011T230001Z-on-demand-0000"
        record = self.ledger() / "run-reports" / f"{run_id}.post-plan.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        cases = {
            None: "No such file or directory",
            "{not json": "Expecting property name",
            json.dumps({"run": run_id, "reason": ""}): "it does not hold a run's post plan (KeyError: 'waitlist_live')",
            '["a list"]': "it does not hold a run's post plan (TypeError:",
        }
        for content, why in cases.items():
            with self.subTest(record=content):
                if content is not None:
                    record.write_text(content, encoding="utf-8")
                code, text = self.check_drafts(run_id)
                self.assertEqual(code, 1, text)
                self.assertIn(f"PROBLEM the post plan of run {run_id} could not be read (", text)
                self.assertIn(why, text)
                self.assertIn("so no Draft was checked; the launcher checks every Draft once you finish.", text)
                self.assertEqual(len(text.splitlines()), 1)
        code, text = self.check_drafts("../../workspace/drafts/posts")
        self.assertEqual(code, 1, text)
        self.assertIn("could not be read (refusing to touch", text)
        self.run_cycle()
        taken = self.ledger() / "run-reports" / f"{self.queue()['updated_by_run']}.post-plan.json"
        self.assertEqual(self.check_drafts(self.queue()["updated_by_run"])[0], 0)
        for code_read in ({"commit": "main", "problem": None}, {"commit": None, "problem": None}):
            with self.subTest(code=code_read):
                record.write_text(json.dumps(dict(json.loads(taken.read_text()), code=code_read)), encoding="utf-8")
                code, text = self.check_drafts(run_id)
                self.assertEqual(code, 1, text)
                self.assertIn("it names neither a commit of the Product's code nor why there is none", text)
                self.assertIn("so no Draft was checked", text)

    def test_the_brand_rules_proposal_is_filed_once_and_its_lists_are_pending_until_mandu_has_them(self):
        rules = self.mandu / "projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
        data = json.loads(rules.read_text())
        for keys in lint.NEW_RULE_TYPES.values():
            for key in keys:
                data.pop(key, None)
        rules.write_text(json.dumps(data))
        self.run_cycle()
        queue = self.queue()
        [filed] = [entry for entry in queue["open"] if entry.get("origin") == "proposal/brand-rules-word-lists"]
        self.assertEqual(filed["id"], "20261011-brand-rules-word-lists")
        report = self.report()
        self.assertIn("Pending, until Mandu adds their lists: stock phrases, capped words per paragraph", report)
        self.assertIn("is `20261011-brand-rules-word-lists`, filed this run: open for the Founder's decision.", report)
        self.assertIn("post-drafts 0 days: none due; the brand-rules proposal filed", report)
        fewer = fakes.proposal(extra=f"supersedes: {filed['id']}\n", title="fewer lists")
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/fewer-lists.md": fewer}})
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        again = [entry for entry in self.queue()["open"] if entry.get("origin")]
        self.assertEqual([entry["id"] for entry in again], [filed["id"]])
        report = self.report()
        self.assertIn("filed earlier, never re-asked", report)
        self.assertIn(f"- `{filed['id']}` (package-change-proposal, filed by the launcher): ", self.brief())
        self.assertIn(
            f"- Set aside, not queued: `fewer-lists.md`: supersedes {filed['id']}, which the launcher filed from"
            " reviewed text; only a reviewed change to that text replaces it",
            report,
        )

    def test_the_proposal_filed_in_a_run_that_took_in_no_draft_still_counts_as_acted_on(self):
        path = self.repo / "config/products.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        for product in registry["products"]:
            (product.get("go_to_market_package") or {}).pop("post_drafts", None)
        path.write_text(json.dumps(registry), encoding="utf-8")
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], ["20261011-brand-rules-word-lists"])
        report = self.report()
        self.assertIn(
            "- post-drafts: checked=0 acted=1 note=no calendar day was prepared; the brand-rules proposal filed\n",
            report,
        )
        self.assertRegex(report, r"## Summary\n\n- checked=\d+ acted=1 note=")

    def test_the_report_never_says_an_approved_proposal_waits_for_mandu_once_mandu_holds_its_lists(self):
        rules = self.mandu / "projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
        applied = rules.read_text()
        data = json.loads(applied)
        for keys in lint.NEW_RULE_TYPES.values():
            for key in keys:
                data.pop(key, None)
        rules.write_text(json.dumps(data))
        self.run_cycle()
        self.decide("20261011-brand-rules-word-lists", "approve")
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        approved = "is `20261011-brand-rules-word-lists`, filed earlier, never re-asked: approved.\n"
        report = self.report()
        self.assertIn(approved, report)
        self.assertIn("Pending, until Mandu adds their lists: stock phrases, capped words per paragraph", report)
        rules.write_text(applied)
        self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        report = self.report()
        self.assertIn(approved, report)
        self.assertNotIn("Pending, until Mandu adds their lists", report)
        self.assertNotIn("waits for Mandu", report)

    def test_code_that_cannot_be_read_is_a_failed_source_and_blocks_every_draft(self):
        shutil.rmtree(self.code)
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(1): fakes.draft(1)}})
        self.run_cycle()
        report = self.report()
        self.assertIn(f"| RepToday repository | failed | the RepToday checkout {self.code} does not exist. |", report)
        self.assertIn("| 1 | P01 / AB-1 leg A | blocked |", report)
        self.assertIn("RepToday's code could not be read", report)
        self.assertNotIn("post", [entry["kind"] for entry in self.queue()["open"]])

    def test_once_the_first_sitting_is_set_day_1_is_the_next_day_and_each_post_has_its_slot(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        writes = {fakes.draft_path(day): fakes.draft(day) for day in (1, 2)}
        fakes.behave(self.codex_dir, {"write": writes})
        self.run_cycle()
        posts_open = [entry for entry in self.queue()["open"] if entry["kind"] == "post"]
        self.assertEqual([entry["slot"][:16] for entry in posts_open], ["2026-10-12T19:00", "2026-10-13T19:00"])
        report = self.report()
        self.assertIn("Window 1 begins on Monday 2026-10-12, the day after its first sitting", report)
        self.assertIn("this run prepares days 1 to 7", report)

    def test_the_flex_day_is_named_as_not_prepared_with_its_reason(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date() - timedelta(days=7)))
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(13): fakes.draft(13)}})
        self.run_cycle()
        report = self.report()
        self.assertIn("this run prepares days 8 to 14", report)
        self.assertIn(
            "| 14 | - | not prepared | the calendar decides its Angle later (Re-cut of the day-7 review's", report
        )
        self.assertEqual([entry["day"] for entry in self.queue()["open"] if entry["kind"] == "post"], [13])
        self.assertIn("- Not prepared: day 14: the calendar decides its Angle later", self.brief())

    def test_check_drafts_gives_the_agent_the_launcher_s_verdict(self):
        fakes.set_window(self.repo, fakes.window_from(fakes.SUNDAY_RUN.date()))
        writes = {
            fakes.draft_path(1): fakes.draft(1),
            fakes.draft_path(2): fakes.draft(2, caption="Join 10,000 people."),
        }
        fakes.behave(self.codex_dir, {"write": writes})
        code, text = self.run_with_check_drafts()
        self.assertEqual(code, 1, text)
        self.assertIn("OK day 1: drafts/posts/window-1/day-01.md", text)
        self.assertIn("BLOCKED day 2: drafts/posts/window-1/day-02.md", text)
        self.assertIn(
            "  - invented_proof_terms: unsourced proof '10,000 people' (TikTok caption, YouTube Shorts description)",
            text,
        )
        self.assertIn("PROBLEM day 3: no Draft", text)
        self.assertIn("7 days due, 6 with problems", text)


if __name__ == "__main__":
    unittest.main()
