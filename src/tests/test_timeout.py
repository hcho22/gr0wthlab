"""A run with a session whose agent stalls still ends, at that session's time limit, with an honest report, and
the stalled session's trouble stays its own workflow's (US-ME17)."""

import fcntl
import functools
import json
import shutil
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from gr0wthlab import cycle, exchange, process, report, sessions, settings
from gr0wthlab.boundary import ConfigError
from gr0wthlab.report import RunState
from tests import fakes
from tests.test_beta_cycle import BetaCycleTestCase
from tests.test_cycle import CycleTestCase
from tests.test_filming import FilmingRunCase

# Long enough for the fake agent to start and write what a test gives it to write, short enough for the suite.
LIMIT = 3
HALF_ITEM = "review-queue/incoming/half-written.md"
WHOLE_ITEM = "review-queue/incoming/name-status-stale.md"
TURN = {"input_tokens": 200000, "cached_input_tokens": 150000, "cache_write_input_tokens": 0, "output_tokens": 4000}


def incomplete_for(text, gap):
    """The outputs a run report's Outputs table marks incomplete with a gap among the reasons."""
    rows = text.split("## Outputs\n\n")[1].split("\n\n")[0].splitlines()[2:]
    cells = [[cell.strip() for cell in row.strip("|").split(" | ", 2)] for row in rows]
    return [title for title, status, detail in cells if status == "incomplete" and gap in detail.split("; ")]


class TimeLimitTestCase(CycleTestCase):
    def setUp(self):
        super().setUp()
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": LIMIT})

    def tearDown(self):
        fakes.stop_leftovers(self.codex_dir)
        super().tearDown()

    def record(self, session="package-review"):
        """What the last run's record holds of one session: the launcher's record of it, and what was read of it."""
        return self.run_record(session)

    def lock_is_free(self):
        with (self.ledger() / cycle.LOCK_FILE).open("a") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        return True

    def notices(self):
        return [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]

    def notice(self):
        [entry] = self.notices()
        return (self.ledger() / entry["file"]).read_text(encoding="utf-8")


class EntryPointTest(TimeLimitTestCase):
    """The reproduction, kept: an on-demand run through src/bin/gr0wthlab, as the Founder starts one, against a
    stand-in agent that never exits. Before the launcher had a time limit, the run never ended and wrote no report."""

    def setUp(self):
        super().setUp()
        ignore = shutil.ignore_patterns("__pycache__")
        shutil.copytree(str(fakes.REPO / "src" / "gr0wthlab"), str(self.repo / "src" / "gr0wthlab"), ignore=ignore)
        shutil.copytree(str(fakes.REPO / "src" / "bin"), str(self.repo / "src" / "bin"))

    def run_on_demand(self):
        """Start the run as its own process and give it far longer than its limit to end."""
        command = [sys.executable, str(self.repo / "src" / "bin" / "gr0wthlab"), "run"]
        started = time.monotonic()
        try:
            done = subprocess.run(
                command, env=dict(self.env, HOME=str(self.home)), capture_output=True, text=True, timeout=90
            )
        except subprocess.TimeoutExpired as error:
            self.fail(f"the run did not end: no report after {error.timeout} s with a {LIMIT} s agent time limit")
        return done, time.monotonic() - started

    def test_a_run_whose_agent_never_exits_ends_at_the_limit_with_its_report(self):
        fakes.behave(self.codex_dir, {"hang": True, "children": 2})
        done, took = self.run_on_demand()
        self.assertEqual(done.returncode, cycle.EXIT_STOPPED, done.stdout + done.stderr)
        self.assertLess(took, LIMIT + process.STOP_GRACE + 30)
        self.assertIn(
            f"timed out: the agent was still running at its {LIMIT} s time limit and was stopped", done.stdout
        )
        self.assertIn(
            "3 processes asked to stop; the process table shows none of them left running; logs in", done.stdout
        )
        self.assertIn(
            f"- The Package review session timed out: its agent was still running at its {LIMIT} s time limit",
            self.report(),
        )
        [notice] = self.notices()
        self.assertRegex(notice["ask"], r"^Notice: the Package review session timed out on \d{4}-\d\d-\d\d$")
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))
        self.assertTrue(self.lock_is_free())

    def test_the_run_speaks_only_for_the_processes_its_stop_found(self):
        """A process the agent detached from a command that has finished, in a session of its own with no parent left,
        is not found by the stop, so the run must not say that nothing is left running."""
        fakes.behave(self.codex_dir, {"hang": True, "children": 1, "detach": True})
        done, _ = self.run_on_demand()
        self.assertEqual(done.returncode, cycle.EXIT_STOPPED, done.stdout + done.stderr)
        *found, detached = fakes.agent_pids(self.codex_dir)
        stopped = self.record()["stopped"]
        self.assertEqual((sorted(stopped["asked"]), stopped["left"], stopped["proven"]), (sorted(found), [], True))
        self.assertTrue(fakes.all_gone(found))
        self.assertTrue(fakes.running(detached))
        said = "2 processes asked to stop; the process table shows none of them left running"
        self.assertIn(f"{said}; logs in", done.stdout)
        self.assertIn(f"- Timed out: {said}.", self.report())

    def test_an_agent_that_goes_silent_mid_work_leaves_nothing_half_written_queued_and_the_next_run_is_clean(self):
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        fakes.keep_days(self.mandu, 1, 2)
        self.exchange.mkdir()
        writes = {
            HALF_ITEM: fakes.PROPOSAL[: len(fakes.PROPOSAL) // 2],
            WHOLE_ITEM: fakes.PROPOSAL,
            fakes.draft_path(1): fakes.draft(1)[: len(fakes.draft(1)) // 2],
            fakes.draft_path(2): fakes.draft(2),
        }
        said = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Writing day 1."}})
        fakes.behave(self.codex_dir, {"write": writes, "events": [said], "children": 1, "hang": True})
        done, _ = self.run_on_demand()
        self.assertEqual(done.returncode, cycle.EXIT_STOPPED, done.stdout + done.stderr)
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))

        queued = {entry["kind"]: entry for entry in self.queue()["open"]}
        self.assertEqual(sorted(queued), ["notice", "package-change-proposal", "post"])
        self.assertEqual(len(self.queue()["open"]), 3)
        self.assertEqual(queued["post"]["day"], 2)
        self.assertTrue(queued["package-change-proposal"]["id"].endswith("-name-status-stale"))
        timed_out = self.report()
        self.assertIn("- Set aside, not queued: `half-written.md`: sections must be exactly:", timed_out)
        self.assertIn("| 1 | P01 / AB-1 leg A | blocked | 1 failing check, listed below |", timed_out)
        self.assertIn("- format: the Draft needs exactly one ## Claims section", timed_out)
        gap = f"its session was stopped at its {LIMIT} s time limit"
        self.assertIn(f"| Post Drafts | incomplete | {gap} |", timed_out)
        # Both of the run's sessions went silent, each at its own limit, so each is named, the first in the title.
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "post-drafts"])
        self.assertRegex(
            queued["notice"]["ask"],
            r"^Notice: the Package review session timed out on \S+, and the run had 3 other problems$",
        )
        notice = self.notice()
        said = f"session was still running at its {LIMIT} s time limit"
        self.assertTrue(notice.split("## Notice\n\n")[1].startswith(f"The Package review {said}"), notice)
        self.assertIn(f"\n\nThe Post Drafts {said}", notice)
        self.assertEqual(incomplete_for(timed_out, gap), ["Package review (contradictions)", "Post Drafts"])
        self.assertIn("Incomplete this run: Package review (contradictions).", notice)
        self.assertIn("Incomplete this run: Post Drafts.", notice)
        self.assertIn("- `half-written.md`: sections must be exactly:", notice)
        self.assertIn("- Day 1 (`drafts/posts/window-1/day-01.md`): format:", notice)

        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(1): fakes.draft(1)}})
        done, _ = self.run_on_demand()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        clean = self.report()
        self.assertIn("- The run finished.", clean)
        self.assertNotIn("- The Package review session timed out", clean)
        self.assertNotIn("- Timed out:", clean)
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", clean)
        self.assertRegex(
            clean, rf"\n- Agent time: \d+ s of its {LIMIT} s limit, with `\S+` at `high` reasoning effort\."
        )
        self.assertEqual(sorted(entry.get("day", 0) for entry in self.queue()["open"]), [0, 0, 1, 2])
        self.assertEqual(self.notices(), [queued["notice"]])
        self.assertTrue(self.lock_is_free())


class TimedOutRunTest(TimeLimitTestCase):
    def test_the_report_says_timed_out_marks_what_needed_the_agent_incomplete_and_never_states_a_zero_cost(self):
        fakes.behave(self.codex_dir, {"hang": True, "children": 2})
        started = time.monotonic()
        code, out = self.run_cycle()
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertLess(time.monotonic() - started, LIMIT + process.STOP_GRACE)

        record = self.record()
        pids = fakes.agent_pids(self.codex_dir)
        self.assertEqual((record["timed_out"], record["exit_code"]), (True, cycle.EXIT_STOPPED))
        self.assertEqual((record["time_limit_seconds"], record["cost_usd"], record["usage"]), (LIMIT, None, None))
        whole = self.run_record()
        self.assertEqual((whole["timed_out"], whole["exit_code"], whole["cost_usd"]), (True, cycle.EXIT_STOPPED, None))
        self.assertEqual(sorted(record["stopped"]["asked"]), sorted(pids))
        self.assertEqual((record["stopped"]["left"], record["stopped"]["proven"]), ([], True))
        self.assertTrue(fakes.all_gone(pids))
        self.assertTrue(self.lock_is_free())

        text = self.report()
        self.assertIn(
            f"- The Package review session timed out: its agent was still running at its {LIMIT} s time limit, so the"
            " launcher stopped it and went on with the run.",
            text,
        )
        self.assertIn("- Approximate cost: not available; the agent was stopped before it reported any token", text)
        self.assertNotIn("$0", text)
        gap = f"its session was stopped at its {LIMIT} s time limit"
        self.assertIn(f"| Package review (contradictions) | incomplete | {gap} |", text)
        self.assertIn("- package-review: checked=16 acted=0 note=16 files, 0 changed, 0 failed; 0 proposals", text)
        self.assertIn(f"0 proposals queued; incomplete: {gap}\n", text)
        # No calendar day is due in this window, so the post Drafts needed nothing from the agent this run.
        self.assertIn("| Post Drafts | complete |", text)
        self.assertIn("| Package snapshot | complete |", text)
        self.assertIn("| Review Queue | complete | 1 open item |", text)
        self.assertRegex(
            text, rf"\n- Agent time: \d+ s of its {LIMIT} s limit, with `\S+` at `high` reasoning effort\."
        )
        self.assertIn(
            "- Timed out: 3 processes asked to stop; the process table shows none of them left running.", text
        )
        self.assertIn(f"- Exit code: {cycle.EXIT_STOPPED}, the launcher's own for a session stopped at its limit", text)
        self.assertIn(f"| Package review | stopped at its {LIMIT} s time limit |", text)
        self.assertIn("- Problems this run are listed in the notice `20261011-notice-run-problems`.", text)
        self.assertNotIn("## Launcher problems", text)

        notice = self.notice()
        self.assertIn("# Notice: the Package review session timed out on 2026-10-11\n", notice)
        self.assertEqual(incomplete_for(text, gap), ["Package review (contradictions)"])
        self.assertIn("Incomplete this run: Package review (contradictions). The next run does this work again", notice)
        self.assertEqual(exchange.check_item(notice, ["RepToday", "Immerse"], published=True).problems, [])

    def test_a_run_the_mac_slept_past_its_limit_ends_once_the_mac_wakes_and_says_how_long_it_slept(self):
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": 1800})
        fakes.behave(self.codex_dir, {"hang": True, "children": 1})
        slept = functools.partial(cycle.launcher.run, clock=fakes.stepped_clock(3 * 3600, after=LIMIT))
        started = time.monotonic()
        with mock.patch.object(cycle.launcher, "run", slept):
            code, out = self.run_cycle()
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertLess(time.monotonic() - started, LIMIT + process.STOP_GRACE + 30)

        record = self.record()
        self.assertEqual((record["timed_out"], record["time_limit_seconds"]), (True, 1800))
        self.assertTrue(3 * 3600 <= record["agent_seconds"] < 3 * 3600 + 60, record["agent_seconds"])
        self.assertTrue(LIMIT <= record["agent_awake_seconds"] < 60, record["agent_awake_seconds"])
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))
        self.assertTrue(self.lock_is_free())

        text = self.report()
        self.assertIn(
            "- The Package review session timed out: its agent was still running at its 30 min time limit", text
        )
        self.assertIn(
            "- The Mac was asleep for about 3 h 0 min 0 s while a session ran, which counts toward that session's time"
            " limit and toward the bound on all of the run's sessions together.",
            text,
        )
        self.assertRegex(
            text,
            r"\n- Agent time: 3 h 0 min \d+ s of its 30 min limit, about 3 h 0 min 0 s of it with the Mac asleep, with",
        )
        self.assertIn("| Package review (contradictions) | incomplete | its session was stopped at its 30 min", text)
        self.assertEqual(len(self.notices()), 1)

    def test_a_second_timed_out_run_the_same_day_does_not_queue_the_notice_twice(self):
        fakes.behave(self.codex_dir, {"hang": True})
        self.exchange.mkdir()
        self.assertEqual(self.run_cycle()[0], cycle.EXIT_STOPPED)
        first = self.notices()
        self.assertEqual(self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(minutes=30))[0], cycle.EXIT_STOPPED)
        self.assertEqual(self.notices(), first)
        self.assertEqual([entry["kind"] for entry in self.queue()["open"]], ["notice"])
        self.assertIn("- Problems this run are listed in the notice `20261011-notice-run-problems`.", self.report())
        self.assertIn(
            "- review-queue: checked=1 acted=0 note=0 decisions taken in, 0 other items queued,", self.report()
        )

    def test_an_agent_that_ignores_the_request_to_stop_is_forced_and_its_reported_tokens_are_a_floor(self):
        turn = json.dumps({"type": "turn.completed", "usage": TURN})
        fakes.behave(self.codex_dir, {"hang": True, "ignore_stop": True, "children": 1, "events": [turn]})
        with mock.patch.object(process, "STOP_GRACE", 1):
            code, out = self.run_cycle()
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        agent, child = fakes.agent_pids(self.codex_dir)
        stopped = self.record()["stopped"]
        self.assertEqual((sorted(stopped["asked"]), stopped["forced"], stopped["left"]), ([agent, child], [agent], []))
        self.assertTrue(fakes.all_gone([agent, child]))
        self.assertIn("2 processes asked to stop, 1 of them forced after 1 s; the process table shows none", out)
        text = self.report()
        self.assertIn("- Timed out: 2 processes asked to stop, 1 of them forced after 1 s; the process table", text)
        self.assertIn(
            "- Approximate cost: at least $0.009 at API prices, for the 200,000 input tokens (150,000 cached) and"
            " 4,000 output tokens that Codex reported; what the Package review session used beyond that is not"
            " available.",
            text,
        )
        self.assertIn(f"| Package review | stopped at its {LIMIT} s time limit | ", text)
        self.assertIn(" | at least $0.009 | none; the agent left no summary |", text)

    def test_an_invalid_limit_refuses_the_run_before_anything_starts(self):
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": 0})
        code, out = self.run_cycle()
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG)
        self.assertIn(
            "refusing to start: config/run.json: agent.time_limit_seconds must be a number of seconds above zero and"
            " at most 86400, a day; got 0",
            out,
        )
        self.assertFalse((self.codex_dir / "prompt.txt").exists())
        self.assertFalse((self.ledger() / "run-reports").exists())


class TimedOutRecruitingTest(BetaCycleTestCase, TimeLimitTestCase):
    def test_a_timed_out_run_that_asked_for_recruiting_drafts_marks_recruiting_incomplete_and_its_notice_names_it(self):
        self.approve_build()
        behavior = {"write": {fakes.INVITATION: fakes.beta_draft()}, "sessions": {"beta-recruiting": {"hang": True}}}
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle()
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "beta-recruiting"])
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))

        # The invitation the agent had written passes its checks and is queued with its batch; the ask it never
        # reached is missing.
        self.assertEqual(self.invitation()["candidates"], fakes.GOOD_FIT_OPT_INS + fakes.OTHER_OPT_INS)
        self.assertEqual(self.asks(), [])
        text = self.report()
        gap = f"its session was stopped at its {LIMIT} s time limit"
        self.assertIn(f"| Beta Cohort recruiting | incomplete | no Waitlist ask Draft; {gap} |", text)
        self.assertRegex(text, rf"\n- beta-recruiting: checked=8 acted=1 .*; incomplete: .*; {gap}\n")
        notice = self.notice()
        # The package review's session had finished, so its output is complete: the trouble stays recruiting's.
        self.assertEqual(incomplete_for(text, gap), ["Beta Cohort recruiting"])
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", text)
        self.assertIn("# Notice: the Beta Cohort recruiting session timed out on 2026-10-11, and the run had", notice)
        self.assertIn("Incomplete this run: Beta Cohort recruiting.", notice)
        self.assertNotIn("Package review", notice)
        self.assertIn("- The Waitlist ask has no Draft, so it was not offered this run.", notice)


class TimedOutFilmingTest(FilmingRunCase, TimeLimitTestCase):
    def test_a_timed_out_run_with_a_day_ready_for_an_edit_record_marks_filming_incomplete_and_its_notice_names_it(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        behavior = {"write": {fakes.draft_path(1): fakes.filming_draft(1)}, "sessions": {"filming": {"hang": True}}}
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=self.runs))
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "post-drafts", "filming"])
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))
        # The Filming session came after the post Drafts session, and was told that day 1's Draft is in place.
        self.assertIn("- Day 1: `day-01.md` is in place", self.brief(session="filming"))

        # The Draft the agent had written is queued with no video; the edit record it never reached is missing.
        text = self.report()
        gap = f"its session was stopped at its {LIMIT} s time limit"
        self.assertIn("| 1 | d01-s1 | no edit record | it is ready for an edit record and has none |", text)
        self.assertIn(f"| Filming plan and edits | incomplete | {gap} |", text)
        self.assertRegex(text, rf"\n- filming: checked=2 acted=0 note=plan approved as [^\n]*; incomplete: {gap}\n")
        self.assertEqual(incomplete_for(text, gap), ["Filming plan and edits"])
        self.assertIn("| Post Drafts | complete |", text)
        self.assertIn("Incomplete this run: Filming plan and edits. The next run does this work again", self.notice())


class TimedOutRejectionCodingTest(TimeLimitTestCase):
    def test_a_timed_out_run_with_a_reason_to_code_marks_the_coding_incomplete_and_its_notice_names_it(self):
        fakes.behave(self.codex_dir, {"write": {WHOLE_ITEM: fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        rejected = "20261011-name-status-stale"
        self.decide(rejected, "reject", reason="Too long to read in a minute.")
        fakes.behave(self.codex_dir, {"sessions": {"learning": {"hang": True}}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "learning"])
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))

        text = self.report()
        gap = f"its session was stopped at its {LIMIT} s time limit"
        self.assertIn(f'- `{rejected}` (package-review): "Too long to read in a minute."', self.brief())
        self.assertIn(f"| Rejection reasons coded | incomplete | no accepted code for `{rejected}`; {gap} |", text)
        self.assertIn(
            f"- learning: checked=0 acted=0 note=1 rejection reason, 0 of 1 coded; incomplete: no accepted code for"
            f" `{rejected}`; {gap}\n",
            text,
        )
        self.assertEqual(incomplete_for(text, gap), ["Rejection reasons coded"])
        self.assertIn("Incomplete this run: Rejection reasons coded.", self.notice())
        self.assertIn("# Notice: the Rejection reasons session timed out on", self.notice())


class TimedOutProductionRunTest(TimeLimitTestCase):
    def test_a_timed_out_run_in_the_production_clone_still_saves_its_records(self):
        fakes.git(self.repo, "commit", "--quiet", "--all", "-m", "a short agent time limit", env=self.env)
        remote, clone = self.root / "remote.git", self.root / "production"
        fakes.git(self.root, "init", "--quiet", "--bare", str(remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.root, "clone", "--quiet", str(remote), str(clone), env=self.env)
        fakes.behave(self.codex_dir, {"write": {WHOLE_ITEM: fakes.PROPOSAL}, "hang": True})
        code, out = self.run_cycle(repo=clone)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertIn("records: pushed", out)
        said = "1 process asked to stop; the process table shows it is no longer running"
        self.assertIn(f"{said}; logs in", out)
        changed = fakes.git(remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertTrue(all(path.startswith(("workspace/", "ledger/")) for path in changed), changed)
        self.assertIn("ledger/review-queue/queue.json", changed)
        report_file = next(
            path for path in changed if path.startswith("ledger/run-reports/2") and ".brief." not in path
        )
        pushed = fakes.git(remote, "show", f"HEAD:{report_file}", env=self.env)
        self.assertIn("- The Package review session timed out:", pushed)
        self.assertIn(f"- Timed out: {said}.", pushed)
        self.assertEqual(fakes.git(clone, "status", "--porcelain", env=self.env), "")
        self.assertEqual(
            sorted(entry["kind"] for entry in self.queue(clone)["open"]), ["notice", "package-change-proposal"]
        )


class LimitSettingTest(unittest.TestCase):
    def test_the_committed_limits_have_headroom_over_every_recorded_run(self):
        config = settings.load(fakes.REPO, {}, Path("/Users/founder"))
        self.assertEqual(config.agent.time_limit, 1800.0)
        # The longest single session recorded at high reasoning effort took 1,122 seconds, when one session did the
        # package review and the post Drafts together; at medium, 218.
        for key in sessions.KEYS:
            self.assertGreaterEqual(config.agent.limit(key), 1.5 * 1122, key)
        # The bound on a whole run leaves room for more than its longest session.
        self.assertGreater(config.agent.run_time_limit, config.agent.time_limit)

    def test_a_limit_is_a_number_of_seconds_above_zero_and_at_most_a_day(self):
        loaded = settings.load_agent({"time_limit_seconds": 2.5, "run_time_limit_seconds": 10})
        self.assertEqual(loaded, settings.Agent(2.5, {}, 10.0))
        whole_day = {"time_limit_seconds": 86400, "run_time_limit_seconds": 86400}
        self.assertEqual(settings.load_agent(whole_day).time_limit, 86400.0)
        for bad in (None, {}, {"time_limit_seconds": None}, "1800", ["1800"]):
            with self.subTest(agent=bad), self.assertRaises(ConfigError):
                settings.load_agent(bad)
        for name in ("time_limit_seconds", "run_time_limit_seconds"):
            for value in (0, -5, 86401, 10**400, "1800", True, [1800], float("nan"), float("inf"), None):
                agent = dict({"time_limit_seconds": 60, "run_time_limit_seconds": 600}, **{name: value})
                with self.subTest(name=name, limit=value), self.assertRaises(ConfigError) as refused:
                    settings.load_agent(agent)
                self.assertIn(f"config/run.json: agent.{name} must be a number of seconds", str(refused.exception))

    def test_a_workflow_s_session_can_have_a_limit_of_its_own(self):
        agent = {
            "time_limit_seconds": 600,
            "session_time_limit_seconds": {"package-review": 1800, "outreach": 300},
            "run_time_limit_seconds": 3600,
        }
        loaded = settings.load_agent(agent)
        self.assertEqual([loaded.limit(key) for key in ("package-review", "post-drafts", "outreach")], [1800, 600, 300])
        self.assertEqual(loaded.run_time_limit, 3600.0)
        for own, said in (
            ({"weekly-read": 600}, "names weekly-read, which is no workflow with a session"),
            ({"outreach": 0}, "agent.session_time_limit_seconds.outreach must be a number of seconds above zero"),
            ({"outreach": "600"}, "agent.session_time_limit_seconds.outreach must be a number of seconds"),
            ([600], "agent.session_time_limit_seconds must map a workflow to its seconds"),
        ):
            with self.subTest(own=own), self.assertRaises(ConfigError) as refused:
                settings.load_agent(dict(agent, session_time_limit_seconds=own))
            self.assertIn(said, str(refused.exception))

    def test_the_bound_on_a_whole_run_is_never_less_than_one_session_may_take(self):
        for agent in (
            {"time_limit_seconds": 1800, "run_time_limit_seconds": 900},
            {
                "time_limit_seconds": 600,
                "session_time_limit_seconds": {"package-review": 1800},
                "run_time_limit_seconds": 900,
            },
        ):
            with self.subTest(agent=agent), self.assertRaises(ConfigError) as refused:
                settings.load_agent(agent)
            self.assertIn(
                "agent.run_time_limit_seconds, 900, is less than one session's limit, 1800", str(refused.exception)
            )


class TimedOutReportTest(unittest.TestCase):
    def state(self, **stopped):
        state = RunState("R", "on-demand", datetime(2026, 10, 11, 16).astimezone(), "i.md")
        stop = dict({"asked": [11, 12], "forced": [], "left": [], "proven": True}, **stopped)
        late = fakes.session(
            closing="", timed_out=True, exit_code=6, agent_seconds=1803.4, agent_awake_seconds=1803.2, stopped=stop
        )
        state.sessions, state.run_limit = [late], 5400.0
        return state

    def test_a_session_that_fell_short_leaves_only_its_own_workflow_s_outputs_incomplete(self):
        state = self.state()
        state.sessions.append(fakes.session("post-drafts"))
        self.assertEqual(state.agent_gap("package-review"), "its session was stopped at its 30 min time limit")
        self.assertEqual(state.review_gap(), state.agent_gap("package-review"))
        self.assertEqual((state.agent_gap("post-drafts"), state.agent_gap("outreach")), ("", ""))
        self.assertTrue(state.timed_out)
        failed = fakes.session(closing="", exit_code=1)
        state.sessions = [failed]
        self.assertEqual(
            (state.timed_out, state.agent_gap("package-review")), (False, "its session ended with exit code 1")
        )
        failed.error = "exceeded retry limit, last status: 429 Too Many Requests"
        self.assertEqual(
            state.agent_gap("package-review"),
            "the model's provider refused its session (exceeded retry limit, last status: 429 Too Many Requests)",
        )
        failed.error = "the model is not supported"
        self.assertEqual(
            state.agent_gap("package-review"), "its session ended with exit code 1 (the model is not supported)"
        )
        state.sessions = [
            fakes.session(closing="", agent_started=False, exit_code=3, error="the boundary preflight failed")
        ]
        self.assertEqual(state.agent_gap("package-review"), "its session did not start: the boundary preflight failed")
        state.sessions = [fakes.session()]
        self.assertEqual(state.agent_gap("package-review"), "")

    def test_a_session_cut_by_the_bound_on_the_whole_run_says_so(self):
        state = self.state()
        state.sessions[0].record = dict(state.sessions[0].record, time_limit_seconds=420.0)
        self.assertEqual(
            state.agent_gap("package-review"),
            "its session was stopped at its 7 min time limit (what the run's bound on all its sessions left it)",
        )
        text = report.render_report(state)
        self.assertIn(
            "- The Package review session timed out: its agent was still running at its 7 min time limit (what the"
            " run's bound on all its sessions left it), so the launcher stopped it",
            text,
        )
        unreached = fakes.session("outreach", closing="", agent_started=False, out_of_time=True, exit_code=6)
        unreached.record["error"] = (
            "the 90 min that bounds all of a run's sessions together was used up before its turn"
        )
        unreached.incomplete = ("Outreach Drafts",)
        state.sessions.append(unreached)
        self.assertEqual(
            state.agent_gap("outreach"),
            "its session did not start: the 90 min that bounds all of a run's sessions together was used up before its"
            " turn",
        )
        text = report.render_report(state)
        self.assertIn(
            "- The Outreach session did not start: the 90 min that bounds all of a run's sessions together was used up"
            " before its turn, so each output that needed it is incomplete; see Outputs and Sessions below.",
            text,
        )
        self.assertIn("| Outreach | did not start: the 90 min that bounds all of a run's sessions", text)
        title, body, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(
            title, "Notice: the Package review session timed out on 2026-10-11, and the run had 1 other problem"
        )
        self.assertIn(
            "The Outreach session did not start: the 90 min that bounds all of a run's sessions together was used up"
            " before its turn. Incomplete this run: Outreach Drafts. The next run does this work again; if runs keep"
            " reaching that bound, it is `agent.run_time_limit_seconds` in `config/run.json`.",
            body,
        )

    def test_the_session_s_part_names_a_process_that_could_not_be_stopped(self):
        clean = report.render_report(self.state())
        self.assertIn("- Agent time: 30 min 3 s of its 30 min limit.", clean)
        self.assertIn(
            "- Timed out: 2 processes asked to stop; the process table shows none of them left running.", clean
        )
        self.assertIsNone(report.left_running(self.state().sessions[0]))
        left = self.state(forced=[12], left=[12])
        self.assertIn(
            "- Timed out: 2 processes asked to stop, 1 of them forced after 10 s; still running after that: process"
            " 12.",
            report.render_report(left),
        )
        self.assertEqual(
            report.left_running(left.sessions[0]),
            "1 process the Package review session started could not be stopped and may still be running; the run"
            " report's Sessions section names each",
        )
        unproven = self.state(asked=[11], proven=False)
        self.assertIn(
            "- Timed out: 1 process asked to stop; the process table could not be read to confirm that nothing is left"
            " running.",
            report.render_report(unproven),
        )
        self.assertIn("the process table could not be read", report.left_running(unproven.sessions[0]))

    def test_the_stop_line_agrees_with_how_many_processes_were_asked_to_stop(self):
        for stopped, said in (
            ({"asked": [11]}, "1 process asked to stop; the process table shows it is no longer running"),
            (
                {"asked": [11], "forced": [11]},
                "1 process asked to stop, then forced after 10 s; the process table shows it is no longer running",
            ),
            ({"asked": [11], "forced": [11], "left": [11]}, "1 process asked to stop, then forced after 10 s; still"),
            ({"asked": []}, "0 processes asked to stop; the stop found none still running in the process table"),
        ):
            with self.subTest(**stopped):
                text = report.render_report(self.state(**stopped))
                self.assertIn(f"- Timed out: {said}", text)
                self.assertNotIn("of them", text)

    def test_the_stop_line_counts_a_process_found_after_the_ask_among_the_forced_and_not_among_the_asked(self):
        none_left = "the process table shows none of them left running"
        for stopped, said in (
            (
                {"asked": [11, 12, 13], "forced": [13, 14]},
                "3 processes asked to stop, then 2 processes forced after 10 s, 1 of them found after the ask;"
                f" {none_left}.",
            ),
            (
                {"asked": [11], "forced": [11, 12]},
                "1 process asked to stop, then 2 processes forced after 10 s, 1 of them found after the ask;"
                f" {none_left}.",
            ),
            (
                {"asked": [11, 12], "forced": [11, 12, 13]},
                "2 processes asked to stop, then 3 processes forced after 10 s, 1 of them found after the ask;"
                f" {none_left}.",
            ),
            (
                {"asked": [11, 12], "forced": [13]},
                f"2 processes asked to stop, then 1 process forced after 10 s, found after the ask; {none_left}.",
            ),
            (
                {"asked": [11], "forced": [11, 12], "left": [12]},
                "1 process asked to stop, then 2 processes forced after 10 s, 1 of them found after the ask; still"
                " running after that: process 12.",
            ),
            (
                {"asked": [11, 12, 13], "forced": [12, 13]},
                f"3 processes asked to stop, 2 of them forced after 10 s; {none_left}.",
            ),
        ):
            with self.subTest(**stopped):
                self.assertIn(f"- Timed out: {said}\n", report.render_report(self.state(**stopped)))

    def test_the_report_says_the_mac_slept_while_a_session_ran_only_when_it_did_and_for_about_how_long(self):
        state = self.state()
        self.assertNotIn("asleep", report.render_report(state))
        state.sessions = [fakes.session(agent_seconds=723.0, agent_awake_seconds=143.0)]
        slept = report.render_report(state)
        self.assertIn(
            "- The run finished.\n- Sessions: 1 ran (Package review).\n- The Mac was asleep for about 9 min 40 s while"
            " a session ran, which counts toward that session's time limit and toward the bound on all of the run's"
            " sessions together.\n",
            slept,
        )
        self.assertIn(
            "- Agent time: 12 min 3 s of its 30 min limit, about 9 min 40 s of it with the Mac asleep.", slept
        )
        state.sessions = [fakes.session(agent_seconds=143.0 + report.ASLEEP_AT_LEAST - 1, agent_awake_seconds=143.0)]
        self.assertNotIn("asleep", report.render_report(state))

    def test_the_agent_time_line_gives_the_limit_the_session_ran_with(self):
        for seconds, limit in ((8, "8 s"), (480, "8 min"), (660, "11 min"), (1080, "18 min"), (4800, "80 min")):
            state = self.state()
            state.sessions[0].limit = float(seconds)
            state.sessions[0].record = dict(state.sessions[0].record, time_limit_seconds=float(seconds))
            with self.subTest(limit=limit):
                text = report.render_report(state)
                self.assertIn(f"\n- Agent time: 30 min 3 s of its {limit} limit.\n", text)
                self.assertIn(f"| Package review | stopped at its {limit} time limit | 30 min 3 s | {limit} |", text)

    def test_a_notice_about_a_timed_out_session_reads_the_same_at_every_run_of_the_day(self):
        notices = []
        for run, pids in (("R1", [11, 12]), ("R2", [808, 909, 1010])):
            state = self.state(asked=pids, forced=pids[1:])
            state.run_id, state.sessions[0].incomplete = run, ("Package review",)
            title, body, touches, evidence = report.problems_notice(state, f"run-reports/{run}.md")
            notices.append(exchange.item_hash(exchange.Item({"kind": "notice"}, title, body, touches, evidence)))
            self.assertEqual(title, "Notice: the Package review session timed out on 2026-10-11")
            self.assertNotRegex(body, r"\d{2,}(?<!1800)(?<!30)")
        self.assertEqual(notices[0], notices[1])


if __name__ == "__main__":
    unittest.main()
