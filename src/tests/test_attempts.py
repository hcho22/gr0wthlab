"""Each week's run completes while the Mac is awake: a scheduled start is a check of the launcher's own records, a run
the Mac's sleep cut short is followed by a fresh one, nothing else is, and nothing holds the Mac awake (US-ME17)."""

import functools
import io
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import attempts, cli, cycle, exchange, process, report, schedule, settings
from gr0wthlab.areas import Store
from gr0wthlab.boundary import ConfigError
from gr0wthlab.report import RunState
from tests import fakes
from tests.test_cycle import CycleTestCase

# When the run of the week is due, as config/run.json sets it: Sunday 16:00 on the Mac's wall clock.
DUE = datetime(2026, 10, 11, 16, 0)
RECORD = "run-reports/attempts/20261011T1600.json"
ITEM = "review-queue/incoming/name-status-stale.md"
# How long the Mac sleeps in these tests when it sleeps past the agent's 30 minute time limit.
ASLEEP = 3 * 3600


def at(**after) -> datetime:
    """The moment the Mac's wall clock reads that long after the run fell due, as the launcher's clock gives it."""
    return (DUE + timedelta(**after)).astimezone().astimezone(timezone.utc)


def woken_after(seconds: float) -> process.Clock:
    """The clocks of a Mac that falls asleep as the agent starts and wakes that many seconds later, before the agent's
    time limit: every reading of the wall clock but the first is that much ahead, and awake time is real."""
    readings = []

    def wall() -> float:
        readings.append(None)
        return time.time() + (seconds if len(readings) > 1 else 0)

    return process.Clock(time.monotonic, wall)


class OwedRunTestCase(CycleTestCase):
    # What the stand-in agent does in a run a test does not set up otherwise.
    behavior: dict = {}

    def tearDown(self):
        fakes.stop_leftovers(self.codex_dir)
        super().tearDown()

    def scheduled(self, clock=None, **after):
        """One scheduled start, as the LaunchAgent makes it, that long after the run fell due."""
        run = functools.partial(cycle.launcher.run, clock=clock) if clock else cycle.launcher.run
        with mock.patch.object(cycle.launcher, "run", run):
            return self.run_cycle(trigger="scheduled", at=at(**after))

    def slept_through(self, **after):
        """A scheduled start whose agent the Mac sleeps through, past its time limit: the agent does its writing, the
        Mac sleeps two seconds in, and the wall clock reads three hours on when it wakes."""
        fakes.behave(self.codex_dir, dict(self.behavior, hang=True))
        result = self.scheduled(clock=fakes.stepped_clock(ASLEEP, after=2.0), **after)
        fakes.behave(self.codex_dir, self.behavior)
        return result

    def record(self, repo=None):
        return json.loads((self.ledger(repo) / RECORD).read_text(encoding="utf-8"))

    def endings(self, repo=None):
        return [(run["trigger"], run.get("ending")) for run in self.record(repo)["runs"]]

    def reports(self, repo=None):
        found = sorted((self.ledger(repo) / "run-reports").glob("2*Z-*.md"))
        return [path for path in found if not path.name.endswith(".brief.md")]

    def notices(self):
        return [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]

    def notice(self):
        [entry] = self.notices()
        return (self.ledger() / entry["file"]).read_text(encoding="utf-8")


class SleptThroughTest(OwedRunTestCase):
    def test_a_start_the_mac_slept_through_runs_once_the_mac_is_fully_awake_and_says_how_late(self):
        """launchd starts a calendar job the Mac slept through at the next wake, and a dark wake counts; the run
        itself waits until the Mac is fully awake."""
        self.awake.return_value = False
        for minutes in (8, 17, 21):
            self.assertEqual(self.scheduled(minutes=minutes), (0, ""))
        self.assertEqual(self.awake.call_count, 3)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())
        self.assertFalse((self.ledger() / "run-reports").exists())
        self.assertFalse((self.ledger() / "notes").exists())

        self.awake.return_value = True
        code, out = self.scheduled(hours=16)
        self.assertEqual(code, 0, out)
        late = (
            "Started late: due Sunday 2026-10-11 16:00, started Monday 2026-10-12 08:00, 16 h 0 min after its time."
            " The Mac was probably asleep or off when it was due."
        )
        self.assertIn(f"(scheduled): {late}\n", out)
        self.assertIn(f"- {late}\n- The run finished.\n", self.report())
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])

        self.assertEqual(self.scheduled(hours=16, minutes=2), (0, ""))
        self.assertEqual(len(self.reports()), 1)

    def test_a_run_the_mac_sleeps_through_is_timed_out_with_the_sleep_named_and_a_fresh_run_follows_by_itself(self):
        """The reproduction, kept. Before the launcher could tell from its records that the run was still owed, a
        run the Mac slept through ended as timed out, with a notice, and nothing followed: the Founder ran it again
        by hand."""
        self.exchange.mkdir()
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.codex_dir)))
        cut_short = self.report()
        on_time = "- Scheduled for Sunday 2026-10-11 16:00; started on time at Sunday 2026-10-11 16:01.\n"
        self.assertIn(on_time, cut_short)
        self.assertIn("- The run timed out: the agent was still running at its 30 min time limit", cut_short)
        self.assertIn("- The Mac was asleep for about 3 h 0 min 0 s while the agent ran", cut_short)
        follows = (
            "The Mac's sleep cut this run short, so it does not count as the run due Sunday 2026-10-11 16:00: a fresh,"
            " whole run starts by itself once the Mac is awake, and nothing is needed from you."
        )
        self.assertIn(f"- {follows}\n", cut_short)
        self.assertIn(f"gr0wthlab: {follows}\n", out)
        self.assertIn("| Package review (contradictions) | incomplete | the agent was stopped at its 30 min", cut_short)
        self.assertEqual(self.queue()["open"], [])
        self.assertNotIn("Problems this run are listed in the notice", cut_short)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), DUE.astimezone())
        [attempt] = self.record()["runs"]
        self.assertEqual((attempt["attempt"], attempt["ending"]), (1, attempts.SLEPT))
        self.assertTrue(ASLEEP - 60 < attempt["asleep_seconds"] <= ASLEEP, attempt)
        self.assertTrue(self.reports()[0].name.startswith(attempt["run"]))

        # A check that comes in a dark wake starts nothing; the first one with the Mac fully awake does.
        self.awake.return_value = False
        self.assertEqual(self.scheduled(hours=3, minutes=3), (0, ""))
        self.assertEqual(len(self.reports()), 1)
        self.awake.return_value = True

        code, out = self.scheduled(hours=3, minutes=5)
        self.assertEqual(code, 0, out)
        fresh = self.report()
        self.assertIn(
            "- Started late: due Sunday 2026-10-11 16:00, started Sunday 2026-10-11 19:05, 3 h 5 min after its time."
            " This is attempt 2 of at most 3: the attempt started Sunday 2026-10-11 16:01 was cut short by the Mac's"
            " sleep.\n- The run finished.\n",
            fresh,
        )
        self.assertNotIn("asleep or off", fresh)
        self.assertNotIn("starts by itself", fresh)
        self.assertIn("| Package review (contradictions) | complete | the agent finished its review |", fresh)
        self.assertEqual(self.queue()["open"], [])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])

        self.assertEqual(self.scheduled(hours=3, minutes=7), (0, ""))
        self.assertEqual(len(self.reports()), 2)

    def test_an_agent_that_ends_with_an_error_after_the_mac_slept_was_cut_short_by_sleep_too(self):
        fakes.behave(self.codex_dir, {"exit": 1})
        code, out = self.scheduled(clock=woken_after(600), minutes=1)
        self.assertEqual(code, 1, out)
        text = self.report()
        self.assertIn("- The agent stopped with exit code 1; its work this run may be incomplete.\n", text)
        self.assertIn("- The Mac was asleep for about 10 min 0 s while the agent ran", text)
        self.assertIn("- The Mac's sleep cut this run short, so it does not count as the run due", text)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT)])
        self.assertEqual(self.queue()["open"], [])

        fakes.behave(self.codex_dir, {})
        code, out = self.scheduled(minutes=12)
        self.assertEqual(code, 0, out)
        self.assertIn("started on time at Sunday 2026-10-11 16:12. This is attempt 2 of at most 3:", self.report())
        self.assertEqual(self.endings()[-1], ("scheduled", attempts.COMPLETED))

    def test_a_cut_short_run_with_another_problem_still_queues_its_notice_and_says_a_fresh_run_follows(self):
        self.behavior = {"write": {"review-queue/incoming/broken.md": "not an item\n"}}
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        [queued] = self.notices()
        self.assertRegex(queued["ask"], r"^Notice: the run timed out on \S+ and had 1 other problem$")
        notice = self.notice()
        self.assertIn(
            "Incomplete this run: Package review (contradictions). The Mac's sleep cut this run short, so it does not"
            " count as the run due Sunday 2026-10-11 16:00: a fresh, whole run starts by itself once the Mac is awake,"
            " and nothing is needed from you.\n",
            notice,
        )
        self.assertNotIn("agent.time_limit_seconds", notice)
        self.assertIn("- `broken.md`:", notice)
        self.assertEqual(exchange.check_item(notice, ["RepToday", "Immerse"], published=True).problems, [])


class OnlySleepEarnsAnotherRunTest(OwedRunTestCase):
    def test_a_run_that_timed_out_with_the_mac_awake_waits_for_the_founder(self):
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": 2})
        fakes.behave(self.codex_dir, {"hang": True})
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        waits = (
            "No run starts by itself after this one: only a run cut short by the Mac's sleep is run again, and this"
            " one timed out with the Mac awake. Start one on demand once that is dealt with (`src/bin/gr0wthlab run`)."
        )
        text = self.report()
        self.assertIn(f"- {waits}\n", text)
        self.assertNotIn("asleep", text)
        self.assertIn(f"gr0wthlab: {waits}\n", out)
        self.assertEqual([entry["ask"] for entry in self.notices()], ["Notice: the run timed out on 2026-10-11"])
        self.assertIn(f"in `config/run.json`. {waits}\n", self.notice())
        self.assertEqual(self.endings(), [("scheduled", attempts.TIMED_OUT)])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())

        fakes.behave(self.codex_dir, {})
        self.assertEqual(self.scheduled(minutes=5), (0, ""))
        self.assertEqual(self.scheduled(days=2), (0, ""))
        self.assertEqual(len(self.reports()), 1)

        code, out = self.run_cycle(at=at(days=2, minutes=1))
        self.assertEqual(code, 0, out)
        on_demand = "- On demand, started Tuesday 2026-10-13 16:01 (Mac local time).\n- The run finished."
        self.assertIn(on_demand, self.report())
        self.assertEqual(self.endings(), [("scheduled", attempts.TIMED_OUT), ("on-demand", attempts.COMPLETED)])

        code, out = self.scheduled(days=7, minutes=1)
        self.assertEqual(code, 0, out)
        self.assertIn("- Scheduled for Sunday 2026-10-18 16:00; started on time at Sunday 2026-10-18", self.report())

    def test_an_agent_that_fails_or_never_starts_with_the_mac_awake_waits_for_the_founder(self):
        fakes.behave(self.codex_dir, {"exit": 1})
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "and this one ended with its agent stopping early, the Mac awake. Start one on demand once that is dealt"
            " with (`src/bin/gr0wthlab run`).",
            self.report(),
        )
        self.assertIn("so this run's review may be incomplete. No run starts by itself after this one:", self.notice())
        self.assertEqual(self.scheduled(minutes=5), (0, ""))
        self.assertEqual(self.endings(), [("scheduled", attempts.FAILED)])

        other = fakes.make_repo(self.root / "other", self.env)
        with mock.patch.object(cycle.launcher, "run", side_effect=OSError(8, "Exec format error")):
            code, out = self.run_cycle(repo=other, trigger="scheduled", at=at(minutes=1))
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG, out)
        self.assertIn("and this one never started its agent. Start one on demand", self.report(other))
        self.assertEqual(self.endings(other), [("scheduled", attempts.NOT_STARTED)])
        self.assertEqual(self.run_cycle(repo=other, trigger="scheduled", at=at(minutes=5)), (0, ""))

    def test_a_start_that_is_refused_or_stopped_by_an_error_is_not_started_again_every_few_minutes(self):
        fakes.set_run(self.repo, "window", {"first_sitting": "2026-10-12"})  # a Monday, when the sitting is on Sunday
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG)
        self.assertIn("refusing to start: config/run.json", out)
        self.assertFalse((self.ledger() / RECORD).exists())

        fakes.set_run(self.repo, "window", fakes.QUIET_WINDOW)
        with mock.patch.object(cycle, "load_boundary", side_effect=ConfigError("the Mandu checkout is missing")):
            code, out = self.scheduled(minutes=3)
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG)
        self.assertIn("refusing to start: the Mandu checkout is missing", out)
        self.assertEqual(self.endings(), [("scheduled", attempts.REFUSED)])
        self.assertEqual(self.scheduled(minutes=5), (0, ""))
        self.assertFalse((self.codex_dir / "prompt.txt").exists())

        other = fakes.make_repo(self.root / "other", self.env)
        with mock.patch.object(cycle.report, "token_usage", side_effect=PermissionError(1, "Operation not permitted")):
            code, out = self.run_cycle(repo=other, trigger="scheduled", at=at(minutes=1))
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(self.endings(other), [("scheduled", attempts.STOPPED)])
        self.assertEqual(self.run_cycle(repo=other, trigger="scheduled", at=at(minutes=5)), (0, ""))
        self.run_cycle(repo=other, at=at(minutes=9))
        self.assertRegex(self.report(other), r"\n- Run \S+ \(scheduled\), started .*, stopped before it finished: ")

    def test_a_production_clone_that_refuses_to_start_is_not_fetched_again_every_few_minutes(self):
        remote, clone = self.root / "remote.git", self.root / "production"
        fakes.git(self.root, "init", "--quiet", "--bare", str(remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.root, "clone", "--quiet", str(remote), str(clone), env=self.env)
        with (clone / "src/instructions/weekly-run.md").open("a") as handle:
            handle.write("Unreviewed line.\n")
        code, out = self.run_cycle(repo=clone, trigger="scheduled", at=at(minutes=1))
        self.assertEqual(code, cycle.EXIT_RECORDS)
        self.assertIn("refusing to start; the production clone needs attention first", out)
        [refused] = self.record(clone)["runs"]
        self.assertEqual((refused["attempt"], refused["ending"], refused["run"]), (1, attempts.REFUSED, None))
        self.assertEqual(self.run_cycle(repo=clone, trigger="scheduled", at=at(minutes=3)), (0, ""))

    def test_an_attempt_that_left_no_ending_is_not_started_again_and_the_next_report_says_so(self):
        """What a run leaves that was stopped before its report, as by a restart of the Mac."""
        store = Store(self.ledger())
        attempts.claim(store, attempts.load(store, DUE), 3, at(minutes=1))
        self.assertEqual(self.endings(), [("scheduled", None)])
        self.assertEqual(self.scheduled(minutes=5), (0, ""))
        self.assertEqual(self.endings(), [("scheduled", None)])

        code, out = self.run_cycle(at=at(hours=1))
        self.assertEqual(code, 0, out)
        self.assertIn(
            "- The scheduled run started Sunday 2026-10-11 16:01, attempt 1 at the run due Sunday 2026-10-11 16:00,"
            " left no report: it was stopped before it could write one, for example by a restart of the Mac. No run"
            " started by itself after it.\n",
            self.report(),
        )
        self.assertEqual(self.endings(), [("scheduled", attempts.NO_REPORT), ("on-demand", attempts.COMPLETED)])
        self.run_cycle(at=at(hours=2))
        self.assertNotIn("left no report", self.report())


class AttemptLimitTest(OwedRunTestCase):
    def test_the_limit_ends_the_fresh_runs_with_a_notice(self):
        fakes.set_run(self.repo, "schedule", {"attempts_per_week": 2})
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(self.notices(), [])

        code, out = self.slept_through(hours=4)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        last = (
            "The Mac's sleep cut this run short, and it was attempt 2 of at most 2 at the run due Sunday 2026-10-11"
            " 16:00, so no further attempt starts by itself: start a run on demand while the Mac stays awake"
            " (`src/bin/gr0wthlab run`). The limit is `schedule.attempts_per_week` in `config/run.json`."
        )
        text = self.report()
        self.assertIn("4 h 0 min after its time. This is attempt 2 of at most 2: the attempt started Sunday", text)
        self.assertIn(f"- {last}\n", text)
        [queued] = self.notices()
        self.assertEqual(queued["ask"], "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11")
        notice = self.notice()
        self.assertIn(f"Incomplete this run: Package review (contradictions). {last}\n", notice)
        self.assertNotIn("agent.time_limit_seconds", notice)
        self.assertEqual(exchange.check_item(notice, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertIn(f"- Problems this run are listed in the notice `{queued['id']}`.", text)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT)] * 2)

        for hours in (8, 16, 40):
            self.assertEqual(self.scheduled(hours=hours), (0, ""))
        self.assertEqual(len(self.reports()), 2)
        self.assertEqual(self.notices(), [queued])

        code, out = self.scheduled(days=7, minutes=1)
        self.assertEqual(code, 0, out)
        self.assertIn("- Scheduled for Sunday 2026-10-18 16:00; started on time", self.report())

    def test_three_attempts_name_both_earlier_ones(self):
        for hours in (0, 4):
            self.assertEqual(self.slept_through(hours=hours, minutes=1)[0], cycle.EXIT_STOPPED)
        code, out = self.scheduled(hours=20)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "This is attempt 3 of at most 3: the attempts started Sunday 2026-10-11 16:01 and Sunday 2026-10-11 20:01"
            " were cut short by the Mac's sleep.\n",
            self.report(),
        )
        self.assertEqual(self.notices(), [])


class OneRunAtATimeTest(OwedRunTestCase):
    def test_a_start_that_gets_the_lock_after_another_completed_the_run_begins_nothing(self):
        store = Store(self.ledger())
        original = cycle.Cycle.lock

        def another_start_wins(runner, trigger):
            """What the lock's holder leaves by the time this start gets the lock: the run, completed."""
            attempts.finish(store, DUE, "scheduled", at(seconds=5), "the-other-run", attempts.COMPLETED, at(minutes=1))
            return original(runner, trigger)

        with mock.patch.object(cycle.Cycle, "lock", another_start_wins):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out, "gr0wthlab: nothing to start: the run due Sunday 2026-10-11 16:00 completed as run the-other-run\n"
        )
        self.assertFalse((self.codex_dir / "prompt.txt").exists())
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])
        self.assertEqual(self.reports(), [])

    def test_two_starts_at_once_through_the_entry_point_leave_one_run(self):
        ignore = shutil.ignore_patterns("__pycache__")
        shutil.copytree(str(fakes.REPO / "src" / "gr0wthlab"), str(self.repo / "src" / "gr0wthlab"), ignore=ignore)
        shutil.copytree(str(fakes.REPO / "src" / "bin"), str(self.repo / "src" / "bin"))
        fakes.behave(self.codex_dir, {"work": 3})
        # The entry point itself, as the LaunchAgent starts it, with the one answer a test must give for the Mac.
        start = (
            "import runpy, sys; sys.path.insert(0, sys.argv[1] + '/src'); from gr0wthlab import attempts;"
            " attempts.fully_awake = lambda: True;"
            " sys.argv = [sys.argv[1] + '/src/bin/gr0wthlab', 'run', '--trigger', 'scheduled'];"
            " runpy.run_path(sys.argv[0], run_name='__main__')"
        )
        command = [sys.executable, "-c", start, str(self.repo)]
        env = dict(self.env, HOME=str(self.home))
        both = [
            subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(2)
        ]
        results = [(done.communicate(timeout=120), done.returncode) for done in both]
        said = "\n".join(out + err for (out, err), _ in results)
        self.assertIn(sorted(code for _, code in results), ([0, 0], [0, cycle.EXIT_BUSY]), said)
        self.assertEqual(len(self.reports()), 1, said)
        self.assertEqual(said.count("run report:"), 1, said)
        [record] = (self.ledger() / "run-reports/attempts").glob("*.json")
        runs = json.loads(record.read_text(encoding="utf-8"))["runs"]
        self.assertEqual([(run["attempt"], run["ending"]) for run in runs], [(1, attempts.COMPLETED)], said)


class AcrossAttemptsTest(OwedRunTestCase):
    """A fresh run is a whole run, and the launcher's rules hold across attempts as across any two runs."""

    def setUp(self):
        super().setUp()
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        fakes.keep_days(self.mandu, 2)
        self.exchange.mkdir()
        self.behavior = {"write": {ITEM: fakes.PROPOSAL, fakes.draft_path(2): fakes.draft(2)}}

    def test_a_fresh_run_queues_nothing_the_cut_short_attempt_queued_and_asks_nothing_the_founder_decided(self):
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        first = {entry["kind"]: entry for entry in self.queue()["open"]}
        self.assertEqual(sorted(first), ["package-change-proposal", "post"])
        self.assertEqual(first["post"]["day"], 2)
        proposal, post = first["package-change-proposal"]["id"], first["post"]["id"]
        self.assertIn("so it does not count as the run due Sunday 2026-10-11 16:00", self.report())

        # The Founder sits before the fresh run: the proposal is approved, and the post is left undecided.
        self.decide(proposal, "approve")
        day = self.sit(f"{DUE:%Y-%m-%d}")

        code, out = self.scheduled(hours=5)
        self.assertEqual(code, 0, out)
        queue = self.queue()
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] != "notice"], [post])
        [carried] = [entry for entry in queue["open"] if entry["id"] == post]
        self.assertEqual((carried["carried_over"], carried["carried_over_from"]), (True, day))
        self.assertEqual([(entry["id"], entry["status"]) for entry in queue["closed"]], [(proposal, "approved")])
        fresh = self.report()
        self.assertIn(f"- Approved `{proposal}`", fresh)
        self.assertIn("- Set aside, not queued: `name-status-stale.md`:", fresh)
        self.assertIn("This is attempt 2 of at most 3:", fresh)
        self.assertIn("1 carried over); 1 Founder decision taken in.", fresh)
        # Neither item was queued a second time: each has the one item file the cut-short attempt wrote.
        items = [path.name for path in (self.ledger() / "review-queue/items").iterdir()]
        self.assertEqual(
            sorted(name for name in items if "notice" not in name), sorted([f"{proposal}.md", f"{post}.md"])
        )

    def test_a_fresh_run_finishes_what_the_cut_short_attempt_left_half_written(self):
        whole = self.behavior["write"]
        half = {path: text[: len(text) // 2] for path, text in whole.items()}
        self.behavior = {"write": half}
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual([entry["kind"] for entry in self.queue()["open"]], ["notice"])

        self.behavior = {"write": whole}
        fakes.behave(self.codex_dir, self.behavior)
        code, out = self.scheduled(hours=5)
        self.assertEqual(code, 0, out)
        kinds = sorted(entry["kind"] for entry in self.queue()["open"])
        self.assertEqual(kinds, ["notice", "package-change-proposal", "post"])
        self.assertIn("| Post Drafts | complete |", self.report())


class OnDemandTest(OwedRunTestCase):
    def test_a_run_on_demand_is_as_before_and_one_that_completes_counts_as_the_week_s_run(self):
        self.awake.return_value = False
        code, out = self.run_cycle(at=at(minutes=5))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.awake.call_count, 0)
        self.awake.return_value = True
        text = self.report()
        self.assertIn("- On demand, started Sunday 2026-10-11 16:05 (Mac local time).\n- The run finished.\n", text)
        self.assertNotIn("attempt", text)
        self.assertEqual(self.endings(), [("on-demand", attempts.COMPLETED)])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())

        self.assertEqual(self.scheduled(minutes=7), (0, ""))
        code, out = self.run_cycle(at=at(minutes=9))
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.reports()), 2)
        self.assertEqual(self.endings(), [("on-demand", attempts.COMPLETED)] * 2)

    def test_a_run_on_demand_the_mac_sleeps_through_reads_as_before_and_leaves_the_week_s_run_owed(self):
        fakes.behave(self.codex_dir, {"hang": True})
        slept = functools.partial(cycle.launcher.run, clock=fakes.stepped_clock(ASLEEP, after=2.0))
        with mock.patch.object(cycle.launcher, "run", slept):
            code, out = self.run_cycle(at=at(minutes=1))
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        text = self.report()
        self.assertIn("- The Mac was asleep for about 3 h 0 min 0 s while the agent ran", text)
        self.assertNotIn("starts by itself", text + out)
        self.assertEqual([entry["ask"] for entry in self.notices()], ["Notice: the run timed out on 2026-10-11"])
        self.assertTrue(
            self.notice().split("## Notice\n\n")[1].split("\n\n")[0].endswith("in `config/run.json`."), self.notice()
        )
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.endings(), [("on-demand", attempts.SLEPT)])

        fakes.behave(self.codex_dir, {})
        code, out = self.scheduled(hours=4)
        self.assertEqual(code, 0, out)
        self.assertIn("- Started late: due Sunday 2026-10-11 16:00, started Sunday 2026-10-11 20:00,", self.report())
        self.assertNotIn("attempt 2", self.report())
        self.assertEqual(self.endings(), [("on-demand", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])


class StartTest(OwedRunTestCase):
    def test_a_start_at_a_terminal_says_why_it_begins_nothing(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True

        self.assertEqual(self.scheduled(minutes=1)[0], 0)
        out = Terminal()
        self.clock.set(at(minutes=3))
        runner = cycle.Cycle(self.repo, self.env, self.home, out, self.clock)
        self.assertEqual(runner.run(None, "scheduled", None, ["run"]), 0)
        self.assertRegex(
            out.getvalue(),
            r"^gr0wthlab: nothing to start: the run due Sunday 2026-10-11 16:00 completed as run \S+-scheduled-\S+\n$",
        )
        self.awake.return_value = False
        out = Terminal()
        self.clock.set(at(days=7, minutes=1))
        runner = cycle.Cycle(self.repo, self.env, self.home, out, self.clock)
        self.assertEqual(runner.run(None, "scheduled", None, ["run"]), 0)
        self.assertEqual(
            out.getvalue(),
            "gr0wthlab: nothing to start: the Mac is not fully awake, and a run starts only while it is\n",
        )

    def test_a_one_off_run_starts_once_its_time_has_come_and_only_once(self):
        def once(moment, **after):
            self.clock.set(at(**after))
            out = io.StringIO()
            runner = cycle.Cycle(self.repo, self.env, self.home, out, self.clock)
            return runner.run(None, "scheduled", moment, ["run"]), out.getvalue()

        self.assertEqual(once("2026-10-13T09:05", days=1), (0, ""))
        self.assertFalse((self.ledger() / "run-reports").exists())
        code, out = once("2026-10-13T09:05", days=1, hours=17, minutes=6)
        self.assertEqual(code, 0, out)
        self.assertIn("- Scheduled for Tuesday 2026-10-13 09:05; started on time at Tuesday 2026-10-13", self.report())
        self.assertTrue((self.ledger() / "run-reports/attempts/20261013T0905.json").is_file())
        self.assertEqual(once("2026-10-13T09:05", days=1, hours=17, minutes=8), (0, ""))
        self.assertEqual(len(self.reports()), 1)

    def test_a_mac_that_does_not_say_whether_it_is_awake_still_runs_and_the_report_says_so(self):
        self.awake.return_value = None
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "- the Mac did not say whether it was fully awake, so this run started without knowing; a run started in"
            " a dark wake is likely to be cut short by sleep\n",
            self.report().partition("## Launcher problems")[2],
        )

    def test_a_record_that_cannot_be_used_is_set_aside_and_the_run_starts(self):
        record = self.ledger() / RECORD
        record.parent.mkdir(parents=True)
        record.write_text("{not json", encoding="utf-8")
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        self.assertEqual(record.with_suffix(".unreadable").read_text(encoding="utf-8"), "{not json")
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])
        self.assertRegex(
            self.report().partition("## Launcher problems")[2],
            r"- the record of the attempts at the run due Sunday 2026-10-11 16:00 could not be used \(.*\); it was set"
            r" aside and started again, so this run may repeat one already made\n",
        )
        self.assertEqual(self.scheduled(minutes=3), (0, ""))


class RestartTest(OwedRunTestCase):
    def test_a_scheduled_run_that_restarts_on_new_reviewed_code_is_one_attempt(self):
        remote, clone = self.root / "remote.git", self.root / "production"
        fakes.git(self.root, "init", "--quiet", "--bare", str(remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.root, "clone", "--quiet", str(remote), str(clone), env=self.env)
        (self.repo / "config" / "note.txt").write_text("reviewed change\n")
        fakes.git(self.repo, "add", "--all", env=self.env)
        fakes.git(self.repo, "commit", "--quiet", "-m", "reviewed", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        calls = []
        self.clock.set(at(minutes=1))
        code, out = self.run_cycle(repo=clone, trigger="scheduled", execve=lambda *args: calls.append(args))
        self.assertEqual(len(calls), 1, out)
        self.assertEqual(calls[0][1][1:], ["run"])
        self.assertFalse((self.ledger(clone) / RECORD).exists())

        # The restarted launcher is not asked whether the run is owed again: the start it continues already was.
        self.env[cycle.PRE_RUN_ENV] = calls[0][2][cycle.PRE_RUN_ENV]
        self.awake.reset_mock()
        self.awake.return_value = False
        code, out = self.run_cycle(repo=clone, trigger="scheduled")
        self.assertEqual((code, self.awake.call_count), (0, 0), out)
        self.assertIn("records: pushed", out)
        self.assertIn("fast-forwarded main", self.report(clone))
        [attempt] = self.record(clone)["runs"]
        self.assertEqual((attempt["attempt"], attempt["ending"]), (1, attempts.COMPLETED))
        self.assertEqual(fakes.git(clone, "status", "--porcelain", env=self.env), "")
        pushed = fakes.git(remote, "show", f"HEAD:ledger/{RECORD}", env=self.env)
        self.assertEqual(json.loads(pushed)["runs"], [attempt])


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "ledger")
        self.addCleanup(self.tmp.cleanup)

    def record(self, *endings, trigger="scheduled"):
        runs = [
            dict({"trigger": trigger, "started_at": at(hours=number).isoformat(), "run": f"R{number}"}, ending=ending)
            for number, ending in enumerate(endings)
        ]
        return attempts.Record(DUE, runs)

    def test_a_run_is_owed_only_while_none_completed_and_every_attempt_was_cut_short_by_sleep(self):
        now = DUE + timedelta(hours=1)
        self.assertEqual(attempts.waiting(attempts.Record(DUE), 3, now), "")
        self.assertEqual(attempts.waiting(self.record(attempts.SLEPT), 3, now), "")
        self.assertEqual(attempts.waiting(self.record(attempts.SLEPT, attempts.SLEPT), 3, now), "")
        self.assertEqual(
            attempts.waiting(self.record(attempts.SLEPT, attempts.SLEPT, attempts.SLEPT), 3, now),
            "the Mac's sleep cut short all of the 3 attempts this run may take",
        )
        self.assertEqual(
            attempts.waiting(self.record(attempts.SLEPT, attempts.COMPLETED), 3, now),
            "the run due Sunday 2026-10-11 16:00 completed as run R1",
        )
        self.assertEqual(
            attempts.waiting(self.record(None), 3, now),
            "attempt 1 is in progress, or was stopped before it could note how it ended",
        )
        self.assertEqual(
            attempts.waiting(attempts.Record(DUE), 3, DUE - timedelta(minutes=1)),
            "the run is not due until Sunday 2026-10-11 16:00",
        )
        for ending in (
            attempts.TIMED_OUT,
            attempts.FAILED,
            attempts.NOT_STARTED,
            attempts.REFUSED,
            attempts.STOPPED,
            attempts.NO_REPORT,
        ):
            with self.subTest(ending=ending):
                said = attempts.waiting(self.record(attempts.SLEPT, ending), 3, now)
                self.assertEqual(
                    said,
                    f"attempt 2 {attempts.SAID[ending]}, and only an attempt cut short by the Mac's sleep is run again",
                )

    def test_a_run_on_demand_never_counts_as_an_attempt_and_completes_the_run_when_it_finishes(self):
        now = DUE + timedelta(hours=1)
        for ending in (attempts.SLEPT, attempts.TIMED_OUT, attempts.FAILED, attempts.NOT_STARTED):
            with self.subTest(ending=ending):
                on_demand = self.record(ending, ending, ending, ending, trigger="on-demand")
                self.assertEqual((on_demand.attempts, attempts.waiting(on_demand, 3, now)), ([], ""))
        done = self.record(attempts.COMPLETED, trigger="on-demand")
        self.assertIn("completed as run R0", attempts.waiting(done, 3, now))

    def test_an_attempt_is_noted_before_it_does_anything_and_its_ending_goes_in_the_same_entry(self):
        first = attempts.claim(self.store, attempts.load(self.store, DUE), 3, at(minutes=1))
        self.assertEqual(first, attempts.Attempt(DUE, 1, 3, ()))
        saved = json.loads(attempts.path(self.store, DUE).read_text(encoding="utf-8"))
        self.assertEqual(
            saved,
            {
                "format": 1,
                "due": "2026-10-11T16:00",
                "runs": [{"trigger": "scheduled", "attempt": 1, "started_at": at(minutes=1).isoformat()}],
            },
        )
        attempts.finish(self.store, DUE, "scheduled", at(minutes=1), "R1", attempts.SLEPT, at(hours=3), 10740.4)
        attempts.finish(self.store, DUE, "on-demand", at(hours=4), "R2", attempts.FAILED, at(hours=4, minutes=1))
        second = attempts.claim(self.store, attempts.load(self.store, DUE), 3, at(hours=5))
        self.assertEqual(second, attempts.Attempt(DUE, 2, 3, (at(minutes=1),)))
        attempts.finish(self.store, DUE, "scheduled", at(hours=5), "R3", attempts.COMPLETED, at(hours=5, minutes=2))
        runs = attempts.load(self.store, DUE).runs
        self.assertEqual(
            [(run["trigger"], run.get("attempt"), run["run"], run["ending"]) for run in runs],
            [
                ("scheduled", 1, "R1", attempts.SLEPT),
                ("on-demand", None, "R2", attempts.FAILED),
                ("scheduled", 2, "R3", attempts.COMPLETED),
            ],
        )
        self.assertEqual((runs[0]["asleep_seconds"], runs[0]["ended_at"]), (10740, at(hours=3).isoformat()))
        self.assertNotIn("asleep_seconds", runs[2])

    def test_a_scheduled_start_that_never_claimed_an_attempt_is_noted_as_one(self):
        attempts.finish(self.store, DUE, "scheduled", at(minutes=1), None, attempts.REFUSED, at(minutes=1))
        [run] = attempts.load(self.store, DUE).runs
        self.assertEqual((run["attempt"], run["ending"], run["run"]), (1, attempts.REFUSED, None))

    def test_a_file_that_is_not_such_a_record_counts_as_empty_and_says_why(self):
        file = attempts.path(self.store, DUE)
        file.parent.mkdir(parents=True)
        run = {"trigger": "scheduled", "started_at": at().isoformat(), "ending": None}
        for content, why in (
            ("{not json", "Expecting property name"),
            ("[]", "it is not a format 1 record of attempts"),
            (json.dumps({"format": 2, "due": "2026-10-11T16:00", "runs": []}), "it is not a format 1 record"),
            (json.dumps({"format": 1, "due": "2026-10-04T16:00", "runs": []}), "not the record of the run due 2026-"),
            (json.dumps({"format": 1, "due": "2026-10-11T16:00", "runs": {}}), "runs must list records"),
            (
                json.dumps({"format": 1, "due": "2026-10-11T16:00", "runs": [dict(run, trigger="hourly")]}),
                "neither scheduled nor on demand",
            ),
            (
                json.dumps({"format": 1, "due": "2026-10-11T16:00", "runs": [dict(run, ending="fine")]}),
                "the unknown ending 'fine'",
            ),
            (
                json.dumps({"format": 1, "due": "2026-10-11T16:00", "runs": [dict(run, started_at="2026-10-11T16")]}),
                "carries no UTC offset",
            ),
            (json.dumps({"format": 1, "due": "2026-10-11T16:00", "runs": [{"trigger": "scheduled"}]}), "started_at"),
        ):
            with self.subTest(content=content):
                file.write_text(content, encoding="utf-8")
                record = attempts.load(self.store, DUE)
                self.assertEqual(record.runs, [])
                self.assertIn(why, record.problem)
        self.assertEqual(attempts.load_to_write(self.store, DUE).runs, [])
        self.assertFalse(file.exists())
        self.assertTrue(file.with_suffix(".unreadable").is_file())
        self.assertEqual(attempts.load(self.store, DUE), attempts.Record(DUE))
        target = Path(self.tmp.name) / "elsewhere.json"
        target.write_text(json.dumps({"format": 1, "due": "2026-10-11T16:00", "runs": []}), encoding="utf-8")
        file.symlink_to(target)
        self.assertIn("cannot open without following links", attempts.load(self.store, DUE).problem)

    def test_attempts_left_without_an_ending_are_closed_once_and_named(self):
        self.assertEqual(attempts.left_without_ending(self.store), [])
        attempts.claim(self.store, attempts.load(self.store, DUE), 3, at(minutes=1))
        earlier = DUE - timedelta(days=7)
        week_before = at(days=-7)
        attempts.finish(self.store, earlier, "scheduled", week_before, "R0", attempts.COMPLETED, week_before)
        (attempts.path(self.store, DUE).parent / "notes.json").write_text("{}", encoding="utf-8")
        [(name, line)] = attempts.left_without_ending(self.store)
        self.assertEqual(name, "20261011T1600-attempt-1")
        self.assertTrue(line.startswith("The scheduled run started Sunday 2026-10-11 16:01, attempt 1 at the run due"))
        self.assertEqual(attempts.load(self.store, DUE).runs[0]["ending"], attempts.NO_REPORT)
        self.assertEqual(attempts.left_without_ending(self.store), [])
        self.assertEqual(attempts.load(self.store, earlier).runs[0]["ending"], attempts.COMPLETED)

    def test_how_a_run_ended_follows_from_its_agent_and_whether_the_mac_slept(self):
        for agent, asleep, ending in (
            ({"agent_started": True, "exit_code": 0}, 0.0, attempts.COMPLETED),
            ({"agent_started": True, "exit_code": 0}, 600.0, attempts.COMPLETED),
            ({"agent_started": True, "exit_code": 6, "timed_out": True}, 10800.0, attempts.SLEPT),
            ({"agent_started": True, "exit_code": 6, "timed_out": True}, 0.0, attempts.TIMED_OUT),
            ({"agent_started": True, "exit_code": 1}, 600.0, attempts.SLEPT),
            ({"agent_started": True, "exit_code": 1}, 0.0, attempts.FAILED),
            ({"agent_started": False, "exit_code": 3}, 0.0, attempts.NOT_STARTED),
            ({}, 0.0, attempts.NOT_STARTED),
        ):
            with self.subTest(agent=agent, asleep=asleep):
                self.assertEqual(attempts.ending(agent, asleep), ending)
        self.assertEqual(set(attempts.SAID), {value for name, value in vars(attempts).items() if name in ENDINGS})


ENDINGS = ("COMPLETED", "SLEPT", "TIMED_OUT", "FAILED", "NOT_STARTED", "REFUSED", "STOPPED", "NO_REPORT")


class ReportTest(unittest.TestCase):
    def state(self, number=1, limit=3, earlier=(), **agent):
        state = RunState("R", "scheduled", (DUE + timedelta(minutes=1)).astimezone(), "i.md", due=DUE)
        state.attempt = attempts.Attempt(DUE, number, limit, tuple(earlier))
        state.agent = dict({"agent_started": True, "exit_code": 0, "time_limit_seconds": 1800.0}, **agent)
        state.review = report.REVIEW_COMPLETE
        return state

    def slept(self, **kwargs):
        return self.state(exit_code=6, timed_out=True, agent_seconds=10805.0, agent_awake_seconds=5.0, **kwargs)

    def test_a_first_attempt_that_completes_reads_as_any_scheduled_run(self):
        state = self.state()
        on_time = "Scheduled for Sunday 2026-10-11 16:00; started on time at Sunday 2026-10-11 16:01."
        self.assertEqual(report.start_line(state), on_time)
        self.assertEqual((report.what_follows(state), state.again, state.ending), ("", False, attempts.COMPLETED))
        self.assertIsNone(report.problems_notice(state, "run-reports/R.md"))

    def test_only_a_scheduled_run_cut_short_by_sleep_with_an_attempt_left_is_followed_by_another(self):
        self.assertTrue(self.slept().again)
        self.assertTrue(self.slept(number=2).again)
        self.assertFalse(self.slept(number=3).again)
        self.assertFalse(self.slept(number=1, limit=1).again)
        awake = self.state(exit_code=6, timed_out=True, agent_seconds=1803.0, agent_awake_seconds=1803.0)
        self.assertEqual((awake.again, awake.ending), (False, attempts.TIMED_OUT))
        on_demand = self.slept()
        on_demand.trigger, on_demand.attempt, on_demand.due = "on-demand", None, None
        self.assertEqual((on_demand.again, on_demand.ending), (False, attempts.SLEPT))
        self.assertEqual(report.what_follows(on_demand), "")

    def test_a_cut_short_run_alone_queues_no_notice_until_the_last_attempt(self):
        self.assertIsNone(report.problems_notice(self.slept(), "run-reports/R.md"))
        self.assertIsNone(report.problems_notice(self.slept(number=2), "run-reports/R.md"))
        last = self.slept(number=3, earlier=(at(minutes=1), at(hours=4)))
        title, body, _, _ = report.problems_notice(last, "run-reports/R.md")
        self.assertEqual(title, "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11")
        self.assertIn("it was attempt 3 of at most 3 at the run due Sunday 2026-10-11 16:00, so no further", body)
        only = self.slept(limit=1)
        self.assertIn("it was attempt 1 of at most 1 at", report.problems_notice(only, "run-reports/R.md")[1])
        with_more = self.slept()
        with_more.problems.append("a file could not be read")
        title, body, _, _ = report.problems_notice(with_more, "run-reports/R.md")
        self.assertEqual(title, "Notice: the run timed out on 2026-10-11 and had 1 other problem")
        self.assertIn("a fresh, whole run starts by itself once the Mac is awake", body)

    def test_a_run_on_demand_reads_and_notifies_as_before(self):
        state = self.slept()
        state.trigger, state.attempt, state.due = "on-demand", None, None
        state.agent_incomplete = ("Package review",)
        title, body, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: the run timed out on 2026-10-11")
        self.assertTrue(
            body.split("\n\n")[0].endswith("the limit is `agent.time_limit_seconds` in `config/run.json`."), body
        )
        self.assertNotIn("attempt", report.render_report(state))


class SettingsTest(unittest.TestCase):
    def test_the_committed_check_and_limit(self):
        config = settings.load(fakes.REPO, {}, Path("/Users/founder"))
        self.assertEqual((config.check_every_minutes, config.attempts_per_week), (2, 3))

    def test_each_is_a_whole_number_within_its_bounds(self):
        self.assertEqual(settings.load_count({"check_every_minutes": 60}, "check_every_minutes", 60, "minutes"), 60)
        self.assertEqual(settings.load_count({"attempts_per_week": 1}, "attempts_per_week", 7, "attempts"), 1)
        for value in (0, -1, 8, 2.0, "3", True, None, [3]):
            with self.subTest(value=value), self.assertRaises(ConfigError) as refused:
                settings.load_count({"attempts_per_week": value}, "attempts_per_week", 7, "the attempts")
            self.assertIn(
                "config/run.json: schedule.attempts_per_week must be a whole number from 1 to 7, the attempts; got",
                str(refused.exception),
            )
        with self.assertRaises(ConfigError):
            settings.load_count({}, "check_every_minutes", 60, "minutes")
        with self.assertRaises(ConfigError):
            settings.load_count("often", "check_every_minutes", 60, "minutes")

    def test_a_run_refuses_to_start_without_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = fakes.make_repo(root / "gr0wthlab", fakes.git_env(root))
            path = repo / "config/run.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["schedule"]["attempts_per_week"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ConfigError) as refused:
                settings.load(repo, {}, root)
            self.assertIn("schedule.attempts_per_week must be a whole number from 1 to 7", str(refused.exception))


class LaunchAgentTest(unittest.TestCase):
    def render(self, *arguments):
        out = io.TextIOWrapper(io.BytesIO())
        with tempfile.TemporaryDirectory() as directory:
            codex = Path(directory) / "codex"
            codex.write_text("#!/bin/sh\n")
            codex.chmod(0o755)
            env = {"GR0WTHLAB_CODEX_BIN": str(codex), "GR0WTHLAB_LOG_DIR": directory}
            with mock.patch.dict("os.environ", env), mock.patch.object(sys, "stdout", out):
                self.assertEqual(cli.main(["launch-agent", *arguments]), 0)
        return plistlib.loads(out.buffer.getvalue())

    def test_the_weekly_agent_also_starts_the_launcher_at_the_check_interval_with_the_same_command(self):
        agent = self.render()
        self.assertEqual(agent["StartCalendarInterval"], {"Weekday": 0, "Hour": 16, "Minute": 0})
        self.assertEqual(agent["StartInterval"], 120)
        self.assertEqual(agent["ProgramArguments"][1:4], ["run", "--trigger", "scheduled"])
        self.assertIs(agent["RunAtLoad"], False)
        self.assertEqual(cli.parser().parse_args(agent["ProgramArguments"][1:]).once, None)

    def test_a_one_off_job_starts_once(self):
        self.assertNotIn("StartInterval", self.render("--once", "2026-10-12T09:05", "--label", "gr0wthlab.try"))
        check = self.render("--boundary-check", "--once", "2026-10-12T09:05", "--label", "gr0wthlab.boundary-check")
        self.assertNotIn("StartInterval", check)
        self.assertNotIn("StartInterval", self.render("--boundary-check"))


class NothingHoldsTheMacAwakeTest(OwedRunTestCase):
    """The run happens when the Mac is awake; the launcher never keeps it awake, wakes it, or schedules a wake."""

    # What would hold a Mac awake or wake it: the command-line tools, and the power assertions, activities, and wake
    # requests of the system frameworks, by the names code would have to use.
    FORBIDDEN = (
        "caffeinate",
        "systemsetup",
        "IOPMAssertion",
        "IOPMSchedulePowerEvent",
        "IOPMRequestSysWake",
        "PreventUserIdleSystemSleep",
        "PreventUserIdleDisplaySleep",
        "PreventSystemSleep",
        "NoIdleSleepAssertion",
        "NoDisplaySleepAssertion",
        "NSProcessInfo",
        "beginActivity",
        "UpdateSystemActivity",
        "disablesleep",
        "sleepnow",
        "wakeorpoweron",
    )
    # Everything the launcher, the agent's task, or a LaunchAgent is made from; the docs and the tests only describe.
    SOURCES = (
        "src/gr0wthlab",
        "src/bin",
        "src/instructions",
        "src/checks",
        "src/dispatches",
        "src/proposals",
        "config",
    )
    # Every key a rendered LaunchAgent may hold: none keeps a job running, wakes the Mac, or starts a job at login.
    LAUNCH_AGENT_KEYS = {
        "EnvironmentVariables",
        "Label",
        "ProcessType",
        "ProgramArguments",
        "RunAtLoad",
        "StandardErrorPath",
        "StandardOutPath",
        "StartCalendarInterval",
        "StartInterval",
        "WorkingDirectory",
    }

    def sources(self):
        found = [path for folder in self.SOURCES for path in sorted((fakes.REPO / folder).rglob("*"))]
        files = [path for path in found if path.is_file() and "__pycache__" not in path.parts]
        self.assertGreater(len(files), 30)
        return [(str(path.relative_to(fakes.REPO)), path.read_text(encoding="utf-8")) for path in files]

    def test_no_launcher_code_configuration_or_task_definition_names_a_way_to_hold_the_mac_awake(self):
        for name, text in self.sources():
            for word in self.FORBIDDEN:
                with self.subTest(file=name, word=word):
                    self.assertNotIn(word.lower(), text.lower())

    def test_the_one_thing_the_launcher_asks_about_the_mac_s_power_only_reads_it(self):
        lines = [(name, line.strip()) for name, text in self.sources() for line in text.splitlines()]
        self.assertEqual(
            [found for found in lines if "pmset" in found[1].lower()],
            [
                ("src/gr0wthlab/attempts.py", 'PMSET = "/usr/bin/pmset"'),
                ("src/gr0wthlab/attempts.py", 'asked = process.run([PMSET, "-g", "systemstate"], process.QUICK)'),
            ],
        )

    def test_the_launch_agents_hold_nothing_awake_and_keep_no_process_running(self):
        entry = Path("/srv/gr0wthlab/src/bin/gr0wthlab")
        run = schedule.run_arguments(entry, Path("/srv/gr0wthlab/src/instructions/weekly-run.md"), None)
        root, logs = entry.parents[2], Path("/logs")
        rendered = (
            schedule.launch_agent("gr0wthlab.weekly-run", run, root, schedule.weekly("sunday", "16:00"), {}, logs, 120),
            schedule.launch_agent("gr0wthlab.once", run, root, schedule.once("2026-10-12T09:05"), {}, logs),
            schedule.launch_agent(
                "gr0wthlab.boundary-check",
                schedule.boundary_check_arguments(entry),
                root,
                schedule.once("2026-10-12T09:05"),
                {},
                logs,
            ),
        )
        for agent in map(plistlib.loads, rendered):
            with self.subTest(label=agent["Label"]):
                self.assertLessEqual(set(agent), self.LAUNCH_AGENT_KEYS)
                self.assertIs(agent["RunAtLoad"], False)
                self.assertEqual(agent["ProcessType"], "Background")
                self.assertEqual(agent["ProgramArguments"][0], str(entry))

    def test_a_whole_scheduled_run_starts_no_process_that_holds_the_mac_awake(self):
        """Watches every process a scheduled run starts, the question whether the Mac is fully awake among them."""
        pmset = self.root / "pmset"
        pmset.write_text("#!/bin/sh\necho 'Current System Capabilities are: CPU Graphics Audio Network '\n")
        pmset.chmod(0o755)
        started = []

        class Watched(subprocess.Popen):
            def __init__(self, args, *rest, **kwargs):
                started.append([str(word) for word in args])
                super().__init__(args, *rest, **kwargs)

        self.awake.side_effect = self.ask_the_mac
        with mock.patch.object(attempts, "PMSET", str(pmset)), mock.patch.object(subprocess, "Popen", Watched):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        self.assertIn("- The run finished.", self.report())
        self.assertEqual([command for command in started if "pmset" in command[0]], [[str(pmset), "-g", "systemstate"]])
        names = {Path(command[0]).name for command in started}
        self.assertLessEqual({"pmset", "codex"}, names)
        self.assertLessEqual(names, {"pmset", "codex", "getconf", "git", "ps"})
        for command in started:
            self.assertFalse(re.search("|".join(self.FORBIDDEN), " ".join(command), re.IGNORECASE), command)


class FullyAwakeTest(unittest.TestCase):
    def ask(self, stdout="", returncode=0):
        completed = process.Completed(returncode, stdout, "", process.QUICK)
        with mock.patch.object(attempts.process, "run", return_value=completed) as run:
            answer = attempts.fully_awake()
        self.assertEqual(run.call_args.args, (["/usr/bin/pmset", "-g", "systemstate"], process.QUICK))
        return answer

    def test_a_mac_someone_woke_is_fully_awake_and_a_dark_wake_is_not(self):
        full = "Current System Capabilities are: CPU Graphics Audio Network \nCurrent Power State: 4\n"
        self.assertIs(self.ask(full), True)
        self.assertIs(self.ask("Current System Capabilities are: CPU Network \nCurrent Power State: 4\n"), False)
        self.assertIs(self.ask("Current System Capabilities are: CPU \n"), False)

    def test_a_mac_that_does_not_say_is_neither(self):
        self.assertIsNone(self.ask("pmset: unknown argument\n"))
        self.assertIsNone(self.ask("Current System Capabilities are: CPU Graphics Audio Network \n", returncode=1))
        with mock.patch.object(attempts.process, "run", side_effect=FileNotFoundError(2, "No such file")):
            self.assertIsNone(attempts.fully_awake())
        stopped = process.Completed(None, "", "", process.QUICK, stop=process.Stop((1,), (), (), True))
        with mock.patch.object(attempts.process, "run", return_value=stopped):
            self.assertIsNone(attempts.fully_awake())


if __name__ == "__main__":
    unittest.main()
