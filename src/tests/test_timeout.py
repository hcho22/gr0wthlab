"""A run whose agent stalls still ends, at the agent's time limit, with an honest report (US-ME17)."""

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

from gr0wthlab import cycle, exchange, process, report, settings
from gr0wthlab.boundary import ConfigError
from gr0wthlab.report import RunState
from tests import fakes
from tests.test_cycle import CycleTestCase

# Long enough for the fake agent to start and write what a test gives it to write, short enough for the suite.
LIMIT = 3
HALF_ITEM = "review-queue/incoming/half-written.md"
WHOLE_ITEM = "review-queue/incoming/name-status-stale.md"
TURN = {"input_tokens": 200000, "cached_input_tokens": 150000, "cache_write_input_tokens": 0, "output_tokens": 4000}


class TimeLimitTestCase(CycleTestCase):
    def setUp(self):
        super().setUp()
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": LIMIT})

    def tearDown(self):
        fakes.stop_leftovers(self.codex_dir)
        super().tearDown()

    def record(self):
        return json.loads(sorted(self.logs.glob("2*Z-*.json"))[-1].read_text(encoding="utf-8"))

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
        self.assertIn("3 processes asked to stop; the process table shows none left running; logs in", done.stdout)
        self.assertIn(f"- The run timed out: the agent was still running at its {LIMIT} s time limit", self.report())
        [notice] = self.notices()
        self.assertRegex(notice["ask"], r"^Notice: the run timed out on \d{4}-\d\d-\d\d$")
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))
        self.assertTrue(self.lock_is_free())

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
        self.assertIn(f"| Post Drafts | incomplete | the agent was stopped at its {LIMIT} s time limit |", timed_out)
        self.assertRegex(queued["notice"]["ask"], r"^Notice: the run timed out on \S+ and had 2 other problems$")
        notice = self.notice()
        self.assertTrue(
            notice.split("## Notice\n\n")[1].startswith(f"The agent was still running at its {LIMIT} s time limit"),
            notice,
        )
        self.assertIn("Incomplete this run: Package review (contradictions), Post Drafts.", notice)
        self.assertIn("- `half-written.md`: sections must be exactly:", notice)
        self.assertIn("- Day 1 (`drafts/posts/window-1/day-01.md`): format:", notice)

        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(1): fakes.draft(1)}})
        done, _ = self.run_on_demand()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        clean = self.report()
        self.assertIn("- The run finished.", clean)
        self.assertNotIn("- The run timed out", clean)
        self.assertNotIn("- Timed out:", clean)
        self.assertIn("| Package review (contradictions) | complete | the agent finished its review |", clean)
        self.assertRegex(clean, rf"\n- Agent time: \d+ s; time limit {LIMIT} s\.\n")
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
        self.assertEqual(sorted(record["stopped"]["asked"]), sorted(pids))
        self.assertEqual((record["stopped"]["left"], record["stopped"]["proven"]), ([], True))
        self.assertTrue(fakes.all_gone(pids))
        self.assertTrue(self.lock_is_free())

        text = self.report()
        self.assertIn(
            f"- The run timed out: the agent was still running at its {LIMIT} s time limit, so the launcher stopped it"
            " and finished the run without it.",
            text,
        )
        self.assertIn("- Approximate cost: not available; the agent was stopped before it reported any token", text)
        self.assertNotIn("$0", text)
        gap = f"the agent was stopped at its {LIMIT} s time limit"
        self.assertIn(f"| Package review (contradictions) | incomplete | {gap} |", text)
        self.assertIn("- package-review: checked=14 acted=0 note=14 files, 0 changed, 0 failed; 0 proposals", text)
        self.assertIn(f"0 proposals queued; incomplete: {gap}\n", text)
        # No calendar day is due in this window, so the post Drafts needed nothing from the agent this run.
        self.assertIn("| Post Drafts | complete |", text)
        self.assertIn("| Package snapshot | complete |", text)
        self.assertIn("| Review Queue | complete | 1 open item |", text)
        self.assertRegex(text, rf"\n- Agent time: \d+ s; time limit {LIMIT} s\.\n")
        self.assertIn("- Timed out: 3 processes asked to stop; the process table shows none left running.", text)
        self.assertIn(f"- Exit code: {cycle.EXIT_STOPPED}, the run's own for an agent stopped at its limit", text)
        self.assertIn("- Problems this run are listed in the notice `20261011-notice-run-problems`.", text)
        self.assertNotIn("## Launcher problems", text)

        notice = self.notice()
        self.assertIn("# Notice: the run timed out on 2026-10-11\n", notice)
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
        self.assertIn("- The run timed out: the agent was still running at its 30 min time limit", text)
        self.assertIn(
            "- The Mac was asleep for about 3 h 0 min 0 s while the agent ran, which counts toward the agent's time"
            " limit.",
            text,
        )
        self.assertRegex(
            text,
            r"\n- Agent time: 3 h 0 min \d+ s, about 3 h 0 min 0 s of it with the Mac asleep; time limit 30 min\.",
        )
        self.assertIn("| Package review (contradictions) | incomplete | the agent was stopped at its 30 min", text)
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
            " 4,000 output tokens reported before the agent was stopped; what its unfinished turn used is not"
            " available.",
            text,
        )

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
        changed = fakes.git(remote, "diff", "--name-only", "HEAD~1", "HEAD", env=self.env).split()
        self.assertTrue(all(path.startswith(("workspace/", "ledger/")) for path in changed), changed)
        self.assertIn("ledger/review-queue/queue.json", changed)
        report_file = next(
            path for path in changed if path.startswith("ledger/run-reports/2") and ".brief." not in path
        )
        self.assertIn("- The run timed out:", fakes.git(remote, "show", f"HEAD:{report_file}", env=self.env))
        self.assertEqual(fakes.git(clone, "status", "--porcelain", env=self.env), "")
        self.assertEqual(
            sorted(entry["kind"] for entry in self.queue(clone)["open"]), ["notice", "package-change-proposal"]
        )


class LimitSettingTest(unittest.TestCase):
    def test_the_committed_limit_has_headroom_over_every_recorded_run(self):
        config = settings.load(fakes.REPO, {}, Path("/Users/founder"))
        self.assertEqual(config.agent, settings.Agent(1800.0))
        self.assertGreaterEqual(config.agent.time_limit, 8 * 218)

    def test_a_limit_is_a_number_of_seconds_above_zero_and_at_most_a_day(self):
        self.assertEqual(settings.load_agent({"time_limit_seconds": 2.5}), settings.Agent(2.5))
        self.assertEqual(settings.load_agent({"time_limit_seconds": 86400}).time_limit, 86400.0)
        for bad in (None, {}, {"time_limit_seconds": None}, "1800", ["1800"]):
            with self.subTest(agent=bad), self.assertRaises(ConfigError):
                settings.load_agent(bad)
        for value in (0, -5, 86401, 10**400, "1800", True, [1800], float("nan"), float("inf")):
            with self.subTest(limit=value), self.assertRaises(ConfigError) as refused:
                settings.load_agent({"time_limit_seconds": value})
            self.assertIn(
                "config/run.json: agent.time_limit_seconds must be a number of seconds", str(refused.exception)
            )


class TimedOutReportTest(unittest.TestCase):
    def state(self, **stopped):
        state = RunState("R", "on-demand", datetime(2026, 10, 11, 16).astimezone(), "i.md")
        stop = dict({"asked": [11, 12], "forced": [], "left": [], "proven": True}, **stopped)
        state.agent = {
            "agent_started": True,
            "exit_code": 6,
            "timed_out": True,
            "time_limit_seconds": 1800.0,
            "agent_seconds": 1803.4,
            "agent_awake_seconds": 1803.2,
            "stopped": stop,
        }
        return state

    def test_a_timed_out_run_leaves_every_output_that_needs_the_agent_incomplete(self):
        state = self.state()
        self.assertEqual(state.agent_gap(), "the agent was stopped at its 30 min time limit")
        self.assertEqual(state.review_gap(), state.agent_gap())
        state.agent = {"agent_started": True, "exit_code": 1}
        self.assertEqual((state.timed_out, state.agent_gap()), (False, "the agent did not finish"))
        state.agent = {"agent_started": True, "exit_code": 0}
        self.assertEqual(state.agent_gap(), "")

    def test_the_agent_section_names_a_process_that_could_not_be_stopped(self):
        clean = report.render_report(self.state())
        self.assertIn("- Agent time: 30 min 3 s; time limit 30 min.", clean)
        self.assertIn("- Timed out: 2 processes asked to stop; the process table shows none left running.", clean)
        self.assertIsNone(report.left_running(self.state().stop))
        left = self.state(forced=[12], left=[12])
        self.assertIn(
            "- Timed out: 2 processes asked to stop, 1 of them forced after 10 s; still running after that: process"
            " 12.",
            report.render_report(left),
        )
        self.assertEqual(
            report.left_running(left.stop),
            "1 process the agent started could not be stopped and may still be running; the run report's Agent section"
            " names each",
        )
        unproven = self.state(asked=[11], proven=False)
        self.assertIn(
            "- Timed out: 1 process asked to stop; the process table could not be read to confirm that nothing is left"
            " running.",
            report.render_report(unproven),
        )
        self.assertIn("the process table could not be read", report.left_running(unproven.stop))

    def test_the_report_says_the_mac_slept_while_the_agent_ran_only_when_it_did_and_for_about_how_long(self):
        state = self.state()
        self.assertNotIn("asleep", report.render_report(state))
        state.agent = {
            "agent_started": True,
            "exit_code": 0,
            "time_limit_seconds": 1800.0,
            "agent_seconds": 723.0,
            "agent_awake_seconds": 143.0,
        }
        slept = report.render_report(state)
        self.assertIn(
            "- The run finished.\n- The Mac was asleep for about 9 min 40 s while the agent ran, which counts toward"
            " the agent's time limit.\n",
            slept,
        )
        self.assertIn(
            "- Agent time: 12 min 3 s, about 9 min 40 s of it with the Mac asleep; time limit 30 min.", slept
        )
        state.agent = dict(state.agent, agent_seconds=143.0 + report.ASLEEP_AT_LEAST - 1)
        self.assertNotIn("asleep", report.render_report(state))

    def test_the_agent_time_line_reads_right_at_a_limit_that_starts_with_a_vowel_sound(self):
        for seconds, limit in ((8, "8 s"), (480, "8 min"), (660, "11 min"), (1080, "18 min"), (4800, "80 min")):
            state = self.state()
            state.agent = dict(state.agent, time_limit_seconds=float(seconds))
            with self.subTest(limit=limit):
                self.assertIn(f"\n- Agent time: 30 min 3 s; time limit {limit}.\n", report.render_report(state))

    def test_a_notice_about_a_timed_out_run_reads_the_same_at_every_run_of_the_day(self):
        notices = []
        for run, pids in (("R1", [11, 12]), ("R2", [808, 909, 1010])):
            state = self.state(asked=pids, forced=pids[1:])
            state.run_id, state.agent_incomplete = run, ("Package review",)
            title, body, touches, evidence = report.problems_notice(state, f"run-reports/{run}.md")
            notices.append(exchange.item_hash(exchange.Item({"kind": "notice"}, title, body, touches, evidence)))
            self.assertEqual(title, "Notice: the run timed out on 2026-10-11")
            self.assertNotRegex(body, r"\d{2,}(?<!1800)(?<!30)")
        self.assertEqual(notices[0], notices[1])


if __name__ == "__main__":
    unittest.main()
