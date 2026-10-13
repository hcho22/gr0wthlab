"""Each week's run completes while the Mac is awake: a weekly start is a check of the launcher's own records, a run
the Mac's sleep cut short is followed by a fresh one, nothing else is, and nothing holds the Mac awake (US-ME17)."""

import io
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import (
    attempts,
    beta,
    cli,
    cycle,
    exchange,
    messages,
    outreach,
    posts,
    process,
    report,
    schedule,
    sessions,
    settings,
)
from gr0wthlab.areas import Store
from gr0wthlab.boundary import ConfigError
from gr0wthlab.report import RunState
from tests import fakes
from tests.test_beta_cycle import BetaCycleTestCase
from tests.test_cycle import CycleTestCase
from tests.test_filming import FilmingRunCase

# When the run of the week is due, as config/run.json sets it: Sunday 16:00 on the Mac's wall clock.
DUE = datetime(2026, 10, 11, 16, 0)
RECORD = "run-reports/attempts/20261011T1600.json"
ITEM = "review-queue/incoming/name-status-stale.md"
# How long the Mac sleeps in these tests when it sleeps past a time limit, the agent's 30 minutes included.
ASLEEP = 3 * 3600
# A one-off scheduled run's time, on the Tuesday after the run of the week fell due.
ONCE = "2026-10-13T09:05"
# What the stand-in agent does when it ends without an error and without the line that confirms its work.
UNCONFIRMED = {"summary": "Read the first half of the package.\n"}
# The report's line on a run's sessions when only the package review had work due, as in most of these runs.
NOTHING_ELSE = (
    "nothing was due for Post Drafts, Filming, Beta Cohort recruiting, Listening, Outreach, Rejection reasons."
)
ONLY_THE_REVIEW = f"- Sessions: 1 ran (Package review); {NOTHING_ELSE}\n"
ASLEEP_IN_A_SESSION = (
    "while a session ran, which counts toward that session's time limit and toward the bound on all of the run's"
    " sessions together.\n"
)
FOLLOWS = (
    "The Mac's sleep cut this run short, so it does not count as the run due Sunday 2026-10-11 16:00: a fresh, whole"
    " run starts by itself once the Mac is awake, and nothing is needed from you."
)


def at(**after) -> datetime:
    """The moment the Mac's wall clock reads that long after the run fell due, as the launcher's clock gives it."""
    return (DUE + timedelta(**after)).astimezone().astimezone(timezone.utc)


class OwedRunTestCase(CycleTestCase):
    # What the stand-in agent does in a run a test does not set up otherwise.
    behavior: dict = {}

    def setUp(self):
        super().setUp()
        self.mac = fakes.Mac()

    def tearDown(self):
        fakes.stop_leftovers(self.codex_dir)
        super().tearDown()

    def scheduled(self, repo=None, once=None, **after):
        """One scheduled start, as a LaunchAgent makes it, that long after the run fell due, timed on the Mac's
        clocks; with once, the start of a one-off run due at that time."""
        return self.run_cycle(repo=repo, trigger="scheduled", at=at(**after), once=once, clocks=self.mac.clocks)

    def slept_through(self, once=None, session=None, **after):
        """A scheduled start with a session the Mac sleeps through, past its time limit: that session's agent does
        its writing, the Mac sleeps two seconds in, and the wall clock reads three hours on when it wakes. It is the
        run's first session unless one is named, and then every session before it ends by itself."""
        hang = {"hang": True} if session is None else {"sessions": {session: {"hang": True}}}
        fakes.behave(self.codex_dir, dict(self.behavior, **hang))
        with self.mac.asleep_in("exec", ASLEEP, after=2.0, session=session):
            result = self.scheduled(once=once, **after)
        fakes.behave(self.codex_dir, self.behavior)
        return result

    def production(self):
        """The remote and a production clone of the checkout, which syncs with it before a run and saves to it after."""
        remote, clone = self.root / "remote.git", self.root / "production"
        fakes.git(self.root, "init", "--quiet", "--bare", str(remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.root, "clone", "--quiet", str(remote), str(clone), env=self.env)
        return remote, clone

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
        self.assertIn(
            "- The Package review session timed out: its agent was still running at its 30 min time limit", cut_short
        )
        self.assertIn(f"- The Mac was asleep for about 3 h 0 min 0 s {ASLEEP_IN_A_SESSION}", cut_short)
        follows = (
            "The Mac's sleep cut this run short, so it does not count as the run due Sunday 2026-10-11 16:00: a fresh,"
            " whole run starts by itself once the Mac is awake, and nothing is needed from you."
        )
        self.assertIn(f"- {follows}\n", cut_short)
        self.assertIn(f"gr0wthlab: {follows}\n", out)
        self.assertIn(
            "| Package review (contradictions) | incomplete | its session was stopped at its 30 min", cut_short
        )
        self.assertEqual(self.queue()["open"], [])
        self.assertNotIn("Problems this run are listed in the notice", cut_short)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), DUE.astimezone())
        [attempt] = self.record()["runs"]
        self.assertEqual((attempt["attempt"], attempt["ending"]), (1, attempts.SLEPT))
        self.assertLess(abs(attempt["asleep_seconds"] - ASLEEP), 60, attempt)
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
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", fresh)
        self.assertEqual(self.queue()["open"], [])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])

        self.assertEqual(self.scheduled(hours=3, minutes=7), (0, ""))
        self.assertEqual(len(self.reports()), 2)

    def test_an_agent_that_ends_with_an_error_after_the_mac_slept_was_cut_short_by_sleep_too(self):
        fakes.behave(self.codex_dir, {"exit": 1})
        with self.mac.asleep_in("exec", 600):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 1, out)
        text = self.report()
        self.assertIn(
            "- The Package review session stopped with exit code 1; its work this run may be incomplete.\n", text
        )
        self.assertIn("- The Mac was asleep for about 10 min 0 s while a session ran", text)
        self.assertIn("- The Mac's sleep cut this run short, so it does not count as the run due", text)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT)])
        self.assertEqual(self.queue()["open"], [])

        fakes.behave(self.codex_dir, {})
        code, out = self.scheduled(minutes=12)
        self.assertEqual(code, 0, out)
        self.assertIn("started on time at Sunday 2026-10-11 16:12. This is attempt 2 of at most 3:", self.report())
        self.assertEqual(self.endings()[-1], ("scheduled", attempts.COMPLETED))

    def test_an_agent_that_ends_unconfirmed_and_without_an_error_after_the_mac_slept_was_cut_short_by_sleep_too(self):
        """What an agent can leave that the Mac's sleep froze in the middle of its work and a later wake let end."""
        self.exchange.mkdir()
        fakes.behave(self.codex_dir, UNCONFIRMED)
        with self.mac.asleep_in("exec", 600):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertNotIn("The run finished.", text)
        self.assertIn(
            "- Every session ended without an error, but the Mac slept during the run and the Package review session"
            f" did not confirm that it finished, so this run's work may be incomplete.\n{ONLY_THE_REVIEW}"
            f"- The Mac was asleep for about 10 min 0 s {ASLEEP_IN_A_SESSION}- {FOLLOWS}\n",
            text,
        )
        self.assertIn(f"gr0wthlab: {FOLLOWS}\n", out)
        self.assertEqual(self.queue()["open"], [])
        self.assertNotIn("Problems this run are listed in the notice", text)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), DUE.astimezone())
        [attempt] = self.record()["runs"]
        self.assertEqual((attempt["attempt"], attempt["ending"], attempt["asleep_seconds"]), (1, attempts.SLEPT, 600))

        fakes.behave(self.codex_dir, {})
        code, out = self.scheduled(minutes=12)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "started on time at Sunday 2026-10-11 16:12. This is attempt 2 of at most 3: the attempt started Sunday"
            " 2026-10-11 16:01 was cut short by the Mac's sleep.\n- The run finished.\n",
            self.report(),
        )
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])
        self.assertEqual(self.queue()["open"], [])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.scheduled(minutes=14), (0, ""))
        self.assertEqual(len(self.reports()), 2)

    def test_an_agent_that_confirms_its_review_after_the_mac_slept_completed_the_week_s_run(self):
        with self.mac.asleep_in("exec", 600):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertIn(
            f"- The run finished.\n{ONLY_THE_REVIEW}- The Mac was asleep for about 10 min 0 s while a session ran", text
        )
        self.assertNotIn("cut this run short", text + out)
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])
        self.assertEqual(self.queue()["open"], [])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.scheduled(minutes=12), (0, ""))
        self.assertEqual(len(self.reports()), 1)

    def test_an_agent_that_ends_unconfirmed_with_the_mac_awake_completed_the_run_and_its_notice_is_as_before(self):
        fakes.behave(self.codex_dir, UNCONFIRMED)
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertIn("- The run finished.\n", text)
        self.assertNotIn("asleep", text)
        self.assertNotIn("starts by itself", text + out)
        self.assertIn("| Package review (contradictions) | incomplete | the agent did not confirm that it", text)
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])
        self.assertEqual(
            [entry["ask"] for entry in self.notices()],
            ["Notice: the package review was not confirmed finished on 2026-10-11"],
        )
        told = self.notice().split("## Notice\n\n")[1].split("\n\n")[0]
        self.assertTrue(told.endswith("in the Review Queue yet; the next run reviews it again."), told)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.scheduled(minutes=5), (0, ""))
        self.assertEqual(len(self.reports()), 1)

    def test_a_cut_short_run_with_another_problem_still_queues_its_notice_and_says_a_fresh_run_follows(self):
        self.behavior = {"write": {"review-queue/incoming/broken.md": "not an item\n"}}
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        [queued] = self.notices()
        self.assertRegex(
            queued["ask"], r"^Notice: the Package review session timed out on \S+, and the run had 1 other problem$"
        )
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
        self.assertEqual(
            [entry["ask"] for entry in self.notices()], ["Notice: the Package review session timed out on 2026-10-11"]
        )
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
            "and this one had a session stop early with the Mac awake. Start one on demand once that is dealt"
            " with (`src/bin/gr0wthlab run`).",
            self.report(),
        )
        self.assertIn(
            "The Package review session stopped with exit code 1, so its work this run may be incomplete: Package"
            " review (contradictions). No run starts by itself after this one:",
            self.notice(),
        )
        self.assertEqual(self.scheduled(minutes=5), (0, ""))
        self.assertEqual(self.endings(), [("scheduled", attempts.FAILED)])

        other = fakes.make_repo(self.root / "other", self.env)
        with mock.patch.object(cycle.launcher, "run", side_effect=OSError(8, "Exec format error")):
            code, out = self.run_cycle(repo=other, trigger="scheduled", at=at(minutes=1))
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG, out)
        self.assertIn("and this one could not start one of its sessions. Start one on demand", self.report(other))
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
        _, clone = self.production()
        with (clone / "src/instructions/weekly-run/common.md").open("a") as handle:
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


class SleepAnywhereTest(OwedRunTestCase):
    """An attempt that did not complete was cut short by the Mac's sleep wherever in it the Mac slept, before its agent
    started as much as while the agent ran; one the Mac stayed awake through still waits for the Founder."""

    FOLLOWS = f"- {FOLLOWS}\n"

    def fresh_run_follows(self, repo=None):
        """The next start with the Mac fully awake is a whole run that names the attempt before it, and the last."""
        code, out = self.scheduled(repo=repo, hours=3, minutes=5)
        self.assertEqual(code, 0, out)
        self.assertIn(
            " This is attempt 2 of at most 3: the attempt started Sunday 2026-10-11 16:01 was cut short by the Mac's"
            " sleep.\n- The run finished.\n",
            self.report(repo),
        )
        self.assertEqual(self.endings(repo), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])
        self.assertEqual(self.scheduled(repo=repo, hours=3, minutes=7), (0, ""))

    def test_a_start_the_mac_sleeps_through_in_its_pre_run_fetch_is_run_again(self):
        """The fetch is stopped at its time limit when the Mac wakes, and the production clone refuses to start."""
        _, clone = self.production()
        with self.mac.asleep_in("fetch", ASLEEP):
            code, out = self.scheduled(repo=clone, minutes=1)
        self.assertEqual(code, cycle.EXIT_RECORDS, out)
        self.assertIn("pre-run: refused: git fetch --quiet origin main failed: timed out after 120s\n", out)
        self.assertIn("refusing to start; the production clone needs attention first", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists())
        [cut_short] = self.record(clone)["runs"]
        self.assertEqual((cut_short["attempt"], cut_short["ending"], cut_short["run"]), (1, attempts.SLEPT, None))
        self.assertLess(abs(cut_short["asleep_seconds"] - ASLEEP), 60, cut_short)
        self.fresh_run_follows(clone)

    def test_an_attempt_the_mac_sleeps_through_while_git_is_asked_for_its_boundary_is_run_again(self):
        """The attempt is already claimed when the launcher asks git where the checkout keeps its git directories."""
        with self.mac.asleep_in("--git-dir", ASLEEP):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG, out)
        self.assertIn("refusing to start: git did not answer for", out)
        [cut_short] = self.record()["runs"]
        self.assertEqual((cut_short["attempt"], cut_short["ending"]), (1, attempts.SLEPT))
        self.assertRegex(cut_short["run"], r"-scheduled-")
        self.assertEqual(self.reports(), [])
        self.fresh_run_follows()

    def test_an_attempt_the_mac_sleeps_through_before_its_agent_starts_is_run_again_and_its_report_says_so(self):
        self.exchange.mkdir()
        other = fakes.make_repo(self.root / "other", self.env)
        for word, repo, code, why in (
            ("--version", self.repo, cycle.launcher.EXIT_CONFIG, "--version did not finish within 1 min"),
            ("sandbox", other, cycle.launcher.EXIT_BOUNDARY, "codex sandbox did not finish within 1 min"),
        ):
            with self.subTest(asleep_in=word):
                with self.mac.asleep_in(word, ASLEEP):
                    ended, out = self.scheduled(repo=repo, minutes=1)
                self.assertEqual(ended, code, out)
                self.assertIn(why, out)
                self.assertIn(
                    "- The Package review session did not start; see Sessions below. Everything the launcher does"
                    f" alone still ran.\n- Sessions: none ran; {NOTHING_ELSE}\n"
                    "- The Mac was asleep for about 3 h 0 min 0 s of this run outside its sessions' time.\n"
                    + self.FOLLOWS,
                    self.report(repo),
                )
                # The report's row for the session that never started gives the real reason.
                self.assertRegex(self.report(repo), rf"\| Package review \| did not start: [^|]*{re.escape(why)}")
                self.assertIn(f"gr0wthlab: {self.FOLLOWS[2:]}", out)
                self.assertEqual(self.queue(repo)["open"], [])
                self.assertEqual(datetime.fromisoformat(self.queue(repo)["next_run"]), DUE.astimezone())
                [cut_short] = self.record(repo)["runs"]
                self.assertEqual((cut_short["attempt"], cut_short["ending"]), (1, attempts.SLEPT))
                self.assertLess(abs(cut_short["asleep_seconds"] - ASLEEP), 60, cut_short)
                self.fresh_run_follows(repo)

    def test_a_start_refused_with_the_mac_awake_throughout_still_earns_no_further_attempt(self):
        """Refused where the attempt above was, with the Mac asleep before this start and never during it."""
        (self.repo / ".git").rename(self.root / "git-moved-away")
        self.mac.slept += ASLEEP
        code, out = self.scheduled(hours=3)
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG, out)
        self.assertIn("is not a git checkout", out)
        [refused] = self.record()["runs"]
        self.assertEqual((refused["attempt"], refused["ending"]), (1, attempts.REFUSED))
        self.assertNotIn("asleep_seconds", refused)
        self.assertEqual(self.scheduled(hours=3, minutes=2), (0, ""))
        self.assertEqual(self.scheduled(days=2), (0, ""))
        self.assertFalse((self.codex_dir / "prompt.txt").exists())


class AttemptLimitTest(OwedRunTestCase):
    # What the second of two attempts says when the Mac's sleep cut it short as well.
    LAST = (
        "The Mac's sleep cut this run short, and it was attempt 2 of at most 2 at the run due Sunday 2026-10-11"
        " 16:00, so no further attempt starts by itself: start a run on demand while the Mac stays awake"
        " (`src/bin/gr0wthlab run`). The limit is `schedule.attempts_per_week` in `config/run.json`."
    )

    def test_the_limit_ends_the_fresh_runs_with_a_notice(self):
        fakes.set_run(self.repo, "schedule", {"attempts_per_week": 2})
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(self.notices(), [])

        code, out = self.slept_through(hours=4)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        last = self.LAST
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

    def test_a_last_attempt_that_ends_unconfirmed_after_the_mac_slept_reads_as_any_exhausted_attempt(self):
        fakes.set_run(self.repo, "schedule", {"attempts_per_week": 2})
        self.assertEqual(self.slept_through(minutes=1)[0], cycle.EXIT_STOPPED)
        fakes.behave(self.codex_dir, UNCONFIRMED)
        with self.mac.asleep_in("exec", 600):
            code, out = self.scheduled(hours=4)
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertNotIn("The run finished.", text)
        self.assertIn("4 h 0 min after its time. This is attempt 2 of at most 2: the attempt started Sunday", text)
        self.assertIn(f"- {self.LAST}\n", text)
        self.assertIn(f"gr0wthlab: {self.LAST}\n", out)
        [queued] = self.notices()
        self.assertEqual(queued["ask"], "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11")
        notice = self.notice()
        self.assertIn(f"in the Review Queue yet; the next run reviews it again. {self.LAST}\n", notice)
        self.assertEqual(exchange.check_item(notice, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertIn(f"- Problems this run are listed in the notice `{queued['id']}`.", text)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT)] * 2)

        fakes.behave(self.codex_dir, {})
        for hours in (8, 16, 40):
            self.assertEqual(self.scheduled(hours=hours), (0, ""))
        self.assertEqual(len(self.reports()), 2)
        self.assertEqual(self.notices(), [queued])

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
        code, out = self.slept_through(minutes=1, session="post-drafts")
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), [])  # reset by the helper; the report names both
        self.assertIn("- Sessions: 2 ran (Package review, Post Drafts);", self.report())
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", self.report())
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
        code, out = self.slept_through(minutes=1, session="post-drafts")
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual([entry["kind"] for entry in self.queue()["open"]], ["notice"])

        self.behavior = {"write": whole}
        fakes.behave(self.codex_dir, self.behavior)
        code, out = self.scheduled(hours=5)
        self.assertEqual(code, 0, out)
        kinds = sorted(entry["kind"] for entry in self.queue()["open"])
        self.assertEqual(kinds, ["notice", "package-change-proposal", "post"])
        self.assertIn("| Post Drafts | complete |", self.report())


class UnreachedWorkTest(OwedRunTestCase):
    """While a fresh run follows by itself, a cut-short attempt's notice leaves out the work its agent did not reach,
    which that run does again and reports on itself; everything else is told as in any run."""

    def setUp(self):
        super().setUp()
        self.exchange.mkdir()

    def first_batch(self):
        """The week of the window's first sitting, when days 1 to 7 are due, with the kit's one blocking checklist
        line checked off so that every day's Draft can pass; returns the seven Drafts as the agent writes them."""
        fakes.set_window(self.repo, fakes.window_from(DUE.date()))
        checklist = self.mandu / "projects/RepToday/gtm/08-redteam/pre-publication-checklist.md"
        lines = checklist.read_text(encoding="utf-8")
        self.assertIn("- [ ] **Device benchmark", lines)
        checklist.write_text(lines.replace("- [ ] **Device benchmark", "- [x] **Device benchmark"), encoding="utf-8")
        return {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}

    def fresh_run(self, writes):
        """The fresh run that follows by itself, in which the agent writes what the cut-short attempt's did not."""
        self.behavior = {"write": writes}
        fakes.behave(self.codex_dir, self.behavior)
        code, out = self.scheduled(hours=3, minutes=5)
        self.assertEqual(code, 0, out)
        self.assertIn("This is attempt 2 of at most 3:", self.report())
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])

    def test_a_first_batch_the_mac_slept_through_queues_no_notice_and_the_fresh_run_queues_its_seven_posts(self):
        drafts = self.first_batch()
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        cut_short = self.report()
        self.assertIn("- Post Drafts: 7 no Draft.\n", cut_short)
        self.assertIn(
            "| Post Drafts | incomplete | no Draft for day 1, 2, 3, 4, 5, 6, 7; its session did not start: the 60 min"
            " that bounds all of a run's sessions together was used up before its turn |",
            cut_short,
        )
        self.assertIn("| Post Drafts | did not start: the 60 min that bounds all of a run's sessions", cut_short)
        self.assertIn(f"- {FOLLOWS}\n", cut_short)
        self.assertNotIn("Problems this run are listed in the notice", cut_short)
        self.assertEqual(self.queue()["open"], [])

        self.fresh_run(drafts)
        queue = self.queue()
        self.assertEqual([entry["kind"] for entry in queue["open"]], ["post"] * 7)
        self.assertEqual(sorted(entry["day"] for entry in queue["open"]), list(range(1, 8)))
        self.assertIn("| Post Drafts | complete | 7 days: 7 queued |", self.report())

    def test_a_cut_short_attempt_with_a_failed_source_queues_a_notice_that_names_the_source_and_not_the_drafts(self):
        self.first_batch()
        (self.mandu / "projects/RepToday/gtm/05-social-pmf/read-the-results.md").unlink()
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        [queued] = self.notices()
        self.assertEqual(
            queued["ask"],
            "Notice: the Package review session timed out on 2026-10-11, and the run had 2 other problems",
        )
        notice = self.notice()
        self.assertIn("read-the-results.md`: missing. Incomplete: ", notice)
        # What follows is said once, with the first session that fell short; the second has its own part.
        self.assertIn(f"Incomplete this run: Package review (contradictions). {FOLLOWS}\n", notice)
        self.assertEqual(notice.count("a fresh, whole run starts by itself"), 1)
        self.assertIn("The Post Drafts session did not start: the 60 min that bounds all of a run's sessions", notice)
        self.assertIn("used up before its turn. Incomplete this run: Post Drafts.\n", notice)
        self.assertNotIn("agent.run_time_limit_seconds", notice)
        self.assertNotIn("has no Draft", notice)
        self.assertNotIn("not offered", notice)
        self.assertEqual(exchange.check_item(notice, ["RepToday", "Immerse"], published=True).problems, [])
        # The attempt's own report still lists every day.
        self.assertIn("- Post Drafts: 7 no Draft.\n", self.report())
        self.assertIn("| 7 | P07 | no Draft |", self.report())

    def test_the_last_attempt_s_notice_lists_every_draft_its_agent_did_not_reach(self):
        self.first_batch()
        fakes.set_run(self.repo, "schedule", {"attempts_per_week": 1})
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        [queued] = self.notices()
        self.assertEqual(queued["ask"], "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11")
        notice = self.notice()
        for day in range(1, 8):
            self.assertIn(f"- Day {day} has no Draft, so it has no post this run.\n", notice)
        self.assertIn("it was attempt 1 of at most 1 at the run due Sunday 2026-10-11 16:00, so no further", notice)

    def test_outreach_messages_the_mac_slept_through_queue_no_notice_and_the_fresh_run_queues_them(self):
        fakes.add_dispatches(self.repo, self.env)
        fakes.set_run(self.repo, "outreach", {"network_ask_source": "network", "creators": fakes.creators()})
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        cut_short = self.report()
        self.assertIn("| Slow Strength | first message | no Draft |", cut_short)
        self.assertIn("| Outreach Drafts | incomplete | no Draft for ", cut_short)
        self.assertEqual(self.notices(), [])

        writes = {fakes.message_path("network-ask"): fakes.message("network-ask", "network", fakes.NETWORK_BODY)}
        for key, _ in fakes.KIT_CREATORS:
            writes[fakes.message_path("creator", key)] = fakes.message("creator", key, fakes.CREATOR_BODY)
        self.fresh_run(writes)
        queue = self.queue()
        self.assertEqual(
            sorted(entry["id"] for entry in queue["open"] if entry["kind"] == "message"),
            [
                "20261011-message-creator-desk-reset",
                "20261011-message-creator-hallway-moves",
                "20261011-message-creator-slow-strength",
                "20261011-message-network-ask",
            ],
        )
        self.assertEqual(self.notices(), [])


class UnreachedRecruitingTest(BetaCycleTestCase, OwedRunTestCase):
    def test_recruiting_drafts_the_mac_slept_through_queue_no_notice_and_the_fresh_run_queues_them(self):
        fakes.write_view(self.view, fakes.waitlist_view((at() - timedelta(hours=1)).isoformat()))
        self.approve_build()
        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        cut_short = self.report()
        self.assertIn("| Beta invitation | no Draft |", cut_short)
        self.assertIn("| Waitlist ask | no Draft |", cut_short)
        self.assertIn(f"- {FOLLOWS}\n", cut_short)
        self.assertEqual(self.queue()["open"], [])

        self.behavior = {
            "write": {fakes.INVITATION: fakes.beta_draft(), fakes.WAITLIST_ASK: fakes.beta_draft("waitlist-ask-clean")}
        }
        fakes.behave(self.codex_dir, self.behavior)
        code, out = self.scheduled(hours=3, minutes=5)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])
        self.assertEqual(sorted(entry["beta"] for entry in self.messages()), ["beta-invitation", "waitlist-ask"])
        self.assertEqual(self.notices(), [])


class UnreachedFilmingTest(FilmingRunCase, OwedRunTestCase):
    def test_a_ready_filming_day_the_mac_slept_through_queues_no_notice_and_the_fresh_run_cuts_its_video(self):
        # The week before: a run files the filming plan, the Founder approves it, and the footage of day 1 arrives.
        fakes.keep_days(self.mandu, 1, 8)
        code, out = self.run_cycle(at=at(days=-1))
        self.assertEqual(code, 0, out)
        [plan] = [entry["id"] for entry in self.queue()["open"] if entry["kind"] == "filming-plan"]
        self.decide(plan, "approve")
        self.clip("d01-s1.mov")
        before = self.notices()

        code, out = self.slept_through(minutes=1)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        cut_short = self.report()
        self.assertIn("| 1 | d01-s1 | no edit record | it is ready for an edit record and has none |", cut_short)
        self.assertIn("- Post Drafts: 1 no Draft.\n", cut_short)
        self.assertIn(f"- {FOLLOWS}\n", cut_short)
        self.assertEqual(self.notices(), before)

        cut = ("d01-s1", "d01-s1.mov", 2, 12)
        self.behavior = {
            "write": {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, cut)}
        }
        fakes.behave(self.codex_dir, self.behavior)
        code, out = self.scheduled(hours=3, minutes=5)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])
        [post] = [entry for entry in self.queue()["open"] if entry["kind"] == "post"]
        self.assertEqual((post["day"], bool(post.get("asset"))), (1, True))
        self.assertEqual(self.notices(), before)


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
        with self.mac.asleep_in("exec", ASLEEP, after=2.0):
            code, out = self.run_cycle(at=at(minutes=1), clocks=self.mac.clocks)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        text = self.report()
        self.assertIn("- The Mac was asleep for about 3 h 0 min 0 s while a session ran", text)
        self.assertNotIn("starts by itself", text + out)
        self.assertEqual(
            [entry["ask"] for entry in self.notices()], ["Notice: the Package review session timed out on 2026-10-11"]
        )
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
        self.assertEqual(runner.run("scheduled", None, ["run"]), 0)
        self.assertRegex(
            out.getvalue(),
            r"^gr0wthlab: nothing to start: the run due Sunday 2026-10-11 16:00 completed as run \S+-scheduled-\S+\n$",
        )
        self.awake.return_value = False
        out = Terminal()
        self.clock.set(at(days=7, minutes=1))
        runner = cycle.Cycle(self.repo, self.env, self.home, out, self.clock)
        self.assertEqual(runner.run("scheduled", None, ["run"]), 0)
        self.assertEqual(
            out.getvalue(),
            "gr0wthlab: nothing to start: the Mac is not fully awake, and a run starts only while it is\n",
        )

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


class OneOffTest(OwedRunTestCase):
    """A one-off scheduled run always runs, as a run on demand does, and is never an attempt at the week's run."""

    ON_TIME = "- Scheduled for Tuesday 2026-10-13 09:05; started on time at Tuesday 2026-10-13 09:06.\n"

    def test_a_one_off_start_runs_in_a_dark_wake_and_every_time_it_is_started(self):
        """launchd starts a one-off job the Mac slept through in a dark wake, and nothing starts it a second time."""
        self.awake.return_value = False
        code, out = self.scheduled(once=ONCE, days=1, hours=17, minutes=6)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.awake.call_count, 0)
        self.assertIn(f"{self.ON_TIME}- The run finished.\n", self.report())
        self.assertNotIn("attempt", self.report())

        code, out = self.scheduled(once=ONCE, days=1, hours=20)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "- Started late: due Tuesday 2026-10-13 09:05, started Tuesday 2026-10-13 12:00, 2 h 55 min after its time."
            " The Mac was probably asleep or off when it was due.\n- The run finished.\n",
            self.report(),
        )
        self.assertEqual(len(self.reports()), 2)
        self.assertEqual(self.awake.call_count, 0)
        self.assertEqual(self.endings(), [("one-off", attempts.COMPLETED)] * 2)
        records = [path.name for path in (self.ledger() / "run-reports/attempts").iterdir()]
        self.assertEqual(records, ["20261011T1600.json"])

    def test_a_one_off_run_the_mac_sleeps_through_reports_as_a_run_on_demand_does_and_claims_no_attempt(self):
        self.exchange.mkdir()
        code, out = self.slept_through(once=ONCE, days=1, hours=17, minutes=6)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        text = self.report()
        self.assertIn(
            f"{self.ON_TIME}- The Package review session timed out: its agent was still running at its 30 min time"
            " limit, so the",
            text,
        )
        self.assertIn("- The Mac was asleep for about 3 h 0 min 0 s while a session ran", text)
        self.assertNotIn("starts by itself", text + out)
        self.assertNotIn("attempt", text + out)
        self.assertEqual(
            [entry["ask"] for entry in self.notices()], ["Notice: the Package review session timed out on 2026-10-13"]
        )
        self.assertTrue(
            self.notice().split("## Notice\n\n")[1].split("\n\n")[0].endswith("in `config/run.json`."), self.notice()
        )
        self.assertIn(f"- Problems this run are listed in the notice `{self.notices()[0]['id']}`.", text)
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())
        [noted] = self.record()["runs"]
        self.assertEqual((noted["trigger"], noted["ending"], "attempt" in noted), ("one-off", attempts.SLEPT, False))

        # Nothing follows the one-off run by itself, and the week's run is owed as before: its first attempt.
        code, out = self.scheduled(days=1, hours=21)
        self.assertEqual(code, 0, out)
        self.assertIn("- Started late: due Sunday 2026-10-11 16:00, started Tuesday 2026-10-13 13:00,", self.report())
        self.assertNotIn("This is attempt", self.report())
        self.assertEqual(self.endings(), [("one-off", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])
        self.assertEqual(self.record()["runs"][1]["attempt"], 1)

    def test_a_one_off_run_that_completes_counts_as_the_week_s_run_so_the_weekly_start_owes_nothing(self):
        code, out = self.scheduled(once=ONCE, days=1, hours=17, minutes=6)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.endings(), [("one-off", attempts.COMPLETED)])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), (DUE + timedelta(days=7)).astimezone())

        self.assertEqual(self.scheduled(days=1, hours=18), (0, ""))
        self.assertEqual(len(self.reports()), 1)
        self.assertEqual(self.endings(), [("one-off", attempts.COMPLETED)])


class RestartTest(OwedRunTestCase):
    def restarting(self, **kwargs):
        """A scheduled start in a production clone that finds new reviewed code on its remote: the clone, the remote,
        and what the start handed the code it restarted on."""
        remote, clone = self.production()
        (self.repo / "config" / "note.txt").write_text("reviewed change\n")
        fakes.git(self.repo, "add", "--all", env=self.env)
        fakes.git(self.repo, "commit", "--quiet", "-m", "reviewed", env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        calls = []
        self.clock.set(at(minutes=1))
        code, out = self.run_cycle(repo=clone, trigger="scheduled", execve=lambda *args: calls.append(args), **kwargs)
        self.assertEqual(len(calls), 1, out)
        self.assertEqual(calls[0][1][1:], ["run"])
        self.assertFalse((self.ledger(clone) / RECORD).exists())
        return clone, remote, calls

    def test_a_scheduled_run_that_restarts_on_new_reviewed_code_is_one_attempt(self):
        clone, remote, calls = self.restarting()

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

    def test_the_mac_s_sleep_before_the_restart_counts_in_the_attempt_that_restarted(self):
        """The Mac sleeps a minute and a half in the fetch, which still finishes within its time limit."""
        with self.mac.asleep_in("fetch", 90):
            clone, _, calls = self.restarting(clocks=self.mac.clocks)
        self.env[cycle.PRE_RUN_ENV] = calls[0][2][cycle.PRE_RUN_ENV]
        fakes.behave(self.codex_dir, {"exit": 1})
        code, out = self.run_cycle(repo=clone, trigger="scheduled", clocks=self.mac.clocks)
        self.assertEqual(code, 1, out)
        text = self.report(clone)
        self.assertIn(
            "- The Package review session stopped with exit code 1; its work this run may be incomplete.\n", text
        )
        self.assertIn("- The Mac was asleep for about 1 min 30 s of this run outside its sessions' time.\n", text)
        self.assertIn("- The Mac's sleep cut this run short, so it does not count as the run due", text)
        [attempt] = self.record(clone)["runs"]
        self.assertEqual((attempt["attempt"], attempt["ending"], attempt["asleep_seconds"]), (1, attempts.SLEPT, 90))


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
        self.assertEqual(attempts.waiting(attempts.Record(DUE), 3), "")
        self.assertEqual(attempts.waiting(self.record(attempts.SLEPT), 3), "")
        self.assertEqual(attempts.waiting(self.record(attempts.SLEPT, attempts.SLEPT), 3), "")
        self.assertEqual(
            attempts.waiting(self.record(attempts.SLEPT, attempts.SLEPT, attempts.SLEPT), 3),
            "the Mac's sleep cut short all of the 3 attempts this run may take",
        )
        self.assertEqual(
            attempts.waiting(self.record(attempts.SLEPT, attempts.COMPLETED), 3),
            "the run due Sunday 2026-10-11 16:00 completed as run R1",
        )
        self.assertEqual(
            attempts.waiting(self.record(None), 3),
            "attempt 1 is in progress, or was stopped before it could note how it ended",
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
                said = attempts.waiting(self.record(attempts.SLEPT, ending), 3)
                self.assertEqual(
                    said,
                    f"attempt 2 {attempts.SAID[ending]}, and only an attempt cut short by the Mac's sleep is run again",
                )

    def test_a_run_on_demand_or_a_one_off_run_never_counts_as_an_attempt_and_completes_the_run_when_it_finishes(self):
        for trigger in (attempts.ON_DEMAND, attempts.ONE_OFF):
            for ending in (attempts.SLEPT, attempts.TIMED_OUT, attempts.FAILED, attempts.NOT_STARTED):
                with self.subTest(trigger=trigger, ending=ending):
                    other = self.record(ending, ending, ending, ending, trigger=trigger)
                    self.assertEqual((other.attempts, attempts.waiting(other, 3)), ([], ""))
            done = self.record(attempts.COMPLETED, trigger=trigger)
            self.assertIn("completed as run R0", attempts.waiting(done, 3))

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
        attempts.finish(self.store, DUE, "one-off", at(hours=4, minutes=30), "R3", attempts.SLEPT, at(hours=8), 12600.0)
        second = attempts.claim(self.store, attempts.load(self.store, DUE), 3, at(hours=9))
        self.assertEqual(second, attempts.Attempt(DUE, 2, 3, (at(minutes=1),)))
        attempts.finish(self.store, DUE, "scheduled", at(hours=9), "R4", attempts.COMPLETED, at(hours=9, minutes=2))
        runs = attempts.load(self.store, DUE).runs
        self.assertEqual(
            [(run["trigger"], run.get("attempt"), run["run"], run["ending"]) for run in runs],
            [
                ("scheduled", 1, "R1", attempts.SLEPT),
                ("on-demand", None, "R2", attempts.FAILED),
                ("one-off", None, "R3", attempts.SLEPT),
                ("scheduled", 2, "R4", attempts.COMPLETED),
            ],
        )
        self.assertEqual((runs[0]["asleep_seconds"], runs[0]["ended_at"]), (10740, at(hours=3).isoformat()))
        self.assertNotIn("asleep_seconds", runs[3])

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
                "not a scheduled attempt, a run on demand, or a one-off run",
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

    def test_how_a_run_ended_follows_from_its_sessions_whether_the_mac_slept_and_whether_they_confirmed(self):
        # None: every session the run had work for started and ended without an error.
        self.assertEqual(attempts.ending(None, 0.0, confirmed=False), attempts.COMPLETED)
        self.assertEqual(attempts.ending(None, 600.0, confirmed=False), attempts.SLEPT)
        self.assertEqual(attempts.ending(None, 600.0, confirmed=True), attempts.COMPLETED)
        for shortfall, asleep, ending in (
            (None, 0.0, attempts.COMPLETED),
            (None, 600.0, attempts.COMPLETED),
            (attempts.TIMED_OUT, 10800.0, attempts.SLEPT),
            (attempts.TIMED_OUT, 0.0, attempts.TIMED_OUT),
            (attempts.FAILED, 600.0, attempts.SLEPT),
            (attempts.FAILED, 0.0, attempts.FAILED),
            (attempts.NOT_STARTED, 10800.0, attempts.SLEPT),
            (attempts.NOT_STARTED, 0.0, attempts.NOT_STARTED),
        ):
            with self.subTest(shortfall=shortfall, asleep=asleep):
                self.assertEqual(attempts.ending(shortfall, asleep), ending)
                if shortfall is not None:
                    self.assertEqual(attempts.ending(shortfall, asleep, confirmed=False), ending)
        self.assertEqual(set(attempts.SAID), {value for name, value in vars(attempts).items() if name in ENDINGS})

    def test_a_session_s_shortfall_is_how_the_record_names_an_ending(self):
        for record, shortfall in (
            ({"agent_started": True, "exit_code": 0}, None),
            ({"agent_started": True, "exit_code": 6, "timed_out": True}, attempts.TIMED_OUT),
            ({"agent_started": True, "exit_code": 1}, attempts.FAILED),
            ({"agent_started": False, "exit_code": 3}, attempts.NOT_STARTED),
            ({"agent_started": False, "exit_code": 6, "out_of_time": True}, attempts.TIMED_OUT),
            ({}, attempts.NOT_STARTED),
        ):
            with self.subTest(record=record):
                session = sessions.Session(sessions.workflow("outreach"), True, "", 1800.0, record)
                self.assertEqual(session.shortfall, shortfall)
        # A workflow with nothing due is no part of how a run ended.
        self.assertIsNone(sessions.Session(sessions.workflow("outreach"), False, "no message is due").shortfall)


ENDINGS = ("COMPLETED", "SLEPT", "TIMED_OUT", "FAILED", "NOT_STARTED", "REFUSED", "STOPPED", "NO_REPORT")


class ReportTest(unittest.TestCase):
    def state(self, number=1, limit=3, earlier=(), slept=0.0, **agent):
        state = RunState("R", "scheduled", (DUE + timedelta(minutes=1)).astimezone(), "i.md", due=DUE)
        state.attempt = attempts.Attempt(DUE, number, limit, tuple(earlier))
        state.sessions = [fakes.session(**agent)]
        state.slept = slept
        return state

    def slept(self, **kwargs):
        """A run whose agent the Mac slept through, past its time limit."""
        agent = {"exit_code": 6, "timed_out": True, "agent_seconds": 10805.0, "agent_awake_seconds": 5.0}
        return self.state(slept=10800.0, **agent, **kwargs)

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
        noise = self.state(exit_code=1, slept=report.asleep_for(1803.0 + report.ASLEEP_AT_LEAST - 1, 1803.0))
        self.assertEqual((noise.again, noise.ending), (False, attempts.FAILED))
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
        self.assertEqual(
            title, "Notice: the Package review session timed out on 2026-10-11, and the run had 1 other problem"
        )
        self.assertIn("a fresh, whole run starts by itself once the Mac is awake", body)

    def unconfirmed(self, **kwargs):
        """A run whose agent ended without an error and without confirming its review, ten minutes of its eleven
        with the Mac asleep."""
        state = self.state(slept=600.0, agent_seconds=660.0, agent_awake_seconds=60.0, **kwargs)
        state.sessions[0].closing = "Read the first half of the package."
        return state

    def test_an_agent_that_ends_unconfirmed_after_the_mac_slept_did_not_complete_a_scheduled_attempt(self):
        state = self.unconfirmed()
        self.assertEqual((state.ending, state.again), (attempts.SLEPT, True))
        text = report.render_report(state)
        self.assertNotIn("The run finished.", text)
        self.assertIn(
            "- Every session ended without an error, but the Mac slept during the run and the Package review session"
            " did not confirm that it finished, so this run's work may be incomplete.\n- Sessions: 1 ran (Package"
            f" review).\n- The Mac was asleep for about 10 min 0 s {ASLEEP_IN_A_SESSION}- {FOLLOWS}\n",
            text,
        )
        self.assertIsNone(report.problems_notice(state, "run-reports/R.md"))
        with_more = self.unconfirmed()
        with_more.problems.append("a file could not be read")
        title, body, _, _ = report.problems_notice(with_more, "run-reports/R.md")
        self.assertEqual(title, "Notice: the run on 2026-10-11 had 2 problems")
        self.assertIn(f"in the Review Queue yet; the next run reviews it again. {FOLLOWS}\n", body)

        unfinished = self.unconfirmed()
        unfinished.sessions[0].closing = "Session: incomplete: the brand files were not reached."
        self.assertEqual((unfinished.ending, unfinished.again), (attempts.SLEPT, True))
        text = report.render_report(unfinished)
        self.assertIn("the Mac slept during the run and the Package review session did not confirm that it", text)
        self.assertIn('"Session: incomplete: the brand files were not reached."', text)
        self.assertIsNone(report.problems_notice(unfinished, "run-reports/R.md"))

        # Whichever session the sleep froze, its word is asked: one unconfirmed session of several is enough.
        several = self.state(slept=600.0, agent_seconds=660.0, agent_awake_seconds=60.0)
        several.sessions += [fakes.session("post-drafts"), fakes.session("outreach", closing="Wrote two of four.")]
        self.assertEqual((several.ending, several.again), (attempts.SLEPT, True))
        self.assertIn(
            "the Mac slept during the run and the Outreach session did not confirm that it finished",
            report.render_report(several),
        )
        self.assertIsNone(report.problems_notice(several, "run-reports/R.md"))
        several.sessions[2].closing = sessions.COMPLETE
        self.assertEqual((several.ending, several.again), (attempts.COMPLETED, False))
        # A session that was never reached, or fell short another way, leaves the run cut short as well.
        several.sessions.append(fakes.session("learning", closing="", exit_code=1))
        self.assertEqual((several.ending, several.again), (attempts.SLEPT, True))
        several.slept = several.sessions[0].record["agent_awake_seconds"] = 0.0
        several.sessions[0].record["agent_seconds"] = 0.0
        self.assertEqual((several.ending, several.again), (attempts.FAILED, False))

        last = self.unconfirmed(number=3, earlier=(at(minutes=1), at(hours=4)))
        self.assertEqual((last.ending, last.again), (attempts.SLEPT, False))
        self.assertNotIn("The run finished.", report.render_report(last))
        title, body, _, _ = report.problems_notice(last, "run-reports/R.md")
        self.assertEqual(title, "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11")
        self.assertIn(
            "the next run reviews it again. The Mac's sleep cut this run short, and it was attempt 3 of at most 3 at"
            " the run due Sunday 2026-10-11 16:00, so no further attempt starts by itself: start a run on demand",
            body,
        )

    def test_an_agent_that_ends_without_an_error_completed_when_it_confirmed_or_the_mac_stayed_awake(self):
        confirmed = self.state(slept=600.0, agent_seconds=660.0, agent_awake_seconds=60.0)
        self.assertEqual((confirmed.ending, confirmed.again), (attempts.COMPLETED, False))
        self.assertEqual(report.what_follows(confirmed), "")
        self.assertIn(
            "- The run finished.\n- Sessions: 1 ran (Package review).\n- The Mac was asleep for about 10 min",
            report.render_report(confirmed),
        )
        self.assertIsNone(report.problems_notice(confirmed, "run-reports/R.md"))

        awake = self.state()
        awake.sessions[0].closing = "Read the first half of the package."
        self.assertEqual((awake.ending, awake.again, report.what_follows(awake)), (attempts.COMPLETED, False, ""))
        self.assertIn("- The run finished.\n", report.render_report(awake))
        title, body, _, _ = report.problems_notice(awake, "run-reports/R.md")
        self.assertEqual(title, "Notice: the package review was not confirmed finished on 2026-10-11")
        self.assertTrue(body.split("\n\n")[0].endswith("the next run reviews it again."), body)

        # A run on demand and a one-off scheduled run are never asked: each reads and notifies as before.
        for trigger in ("on-demand", "scheduled"):
            other = self.unconfirmed()
            other.trigger, other.attempt = trigger, None
            self.assertEqual((other.ending, other.again, report.what_follows(other)), (attempts.COMPLETED, False, ""))
            self.assertIn("- The run finished.\n", report.render_report(other))
            title, body, _, _ = report.problems_notice(other, "run-reports/R.md")
            self.assertEqual(title, "Notice: the package review was not confirmed finished on 2026-10-11")
            self.assertTrue(body.split("\n\n")[0].endswith("the next run reviews it again."), body)

    def unreached(self, state):
        """A run whose agent wrote none of what it was asked for: seven post Drafts, the recruiting invitation, and
        the first message to a creator."""
        state.post_outcome = posts.Outcome([posts.DayResult(day, posts.MISSING) for day in range(1, 8)])
        state.beta_outcome = beta.Outcome([beta.DraftResult(beta.INVITATION, beta.MISSING)])
        state.outreach = outreach.Plan("RepToday", "R", "channel-plan.md", messages.Limits(), Path("drafts"))
        creator = messages.Target(messages.CREATOR, *fakes.KIT_CREATORS[0])
        state.outreach_result = outreach.Result([messages.Outcome(creator, messages.MISSING)])
        return state

    def test_a_cut_short_attempt_s_notice_leaves_out_what_its_agent_did_not_reach_while_a_fresh_run_follows(self):
        missing = (
            "- Day 7 has no Draft, so it has no post this run.",
            "- The Beta invitation has no Draft, so it was not offered this run.",
            "- Slow Strength, first message: no Draft was written, so nothing is offered.",
        )
        self.assertIsNone(report.problems_notice(self.unreached(self.slept()), "run-reports/R.md"))
        self.assertIsNone(report.problems_notice(self.unreached(self.unconfirmed()), "run-reports/R.md"))

        with_more = self.unreached(self.slept())
        with_more.problems.append("a file could not be read")
        with_more.post_outcome.results[0] = posts.DayResult(1, posts.BLOCKED, "its Draft could not be read")
        with_more.beta_outcome.results[0].withdrawn = "20261004-message-beta-invitation-1"
        title, body, _, _ = report.problems_notice(with_more, "run-reports/R.md")
        self.assertEqual(
            title, "Notice: the Package review session timed out on 2026-10-11, and the run had 3 other problems"
        )
        self.assertIn("- Day 1: its Draft could not be read\n", body)
        self.assertIn("- The open `20261004-message-beta-invitation-1` is withdrawn, since it no longer stands.", body)
        self.assertIn("- a file could not be read", body)
        self.assertIn("a fresh, whole run starts by itself once the Mac is awake", body)
        for line in missing:
            self.assertNotIn(line, body)
        self.assertNotIn("has no Draft", body)

        # Once no fresh run follows, and in a run that is no attempt, the notice lists everything, as before.
        last = self.unreached(self.slept(number=3, earlier=(at(minutes=1), at(hours=4))))
        on_demand = self.unreached(self.slept())
        on_demand.trigger, on_demand.attempt, on_demand.due = "on-demand", None, None
        awake = self.unreached(self.state(exit_code=6, timed_out=True))
        for state, title in (
            (last, "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11"),
            (on_demand, "Notice: the Package review session timed out on 2026-10-11, and the run had 9 other problems"),
            (awake, "Notice: the Package review session timed out on 2026-10-11, and the run had 9 other problems"),
        ):
            with self.subTest(title=title, trigger=state.trigger):
                told, body, _, _ = report.problems_notice(state, "run-reports/R.md")
                self.assertEqual(told, title)
                for line in missing:
                    self.assertIn(line, body)

    def test_sleep_outside_the_agent_s_time_cuts_a_scheduled_run_short_and_the_report_says_for_how_long(self):
        before = self.state(exit_code=3, agent_started=False, slept=600.0)
        self.assertEqual((before.again, before.ending), (True, attempts.SLEPT))
        self.assertIsNone(report.problems_notice(before, "run-reports/R.md"))
        outside = "- The Mac was asleep for about 10 min 0 s of this run outside its sessions' time.\n"
        self.assertIn(f"{outside}- The Mac's sleep cut this run short, so it does not", report.render_report(before))

        both = self.slept()
        both.slept += 600.0
        text = report.render_report(both)
        self.assertIn("- The Mac was asleep for about 3 h 0 min 0 s while a session ran, which counts toward", text)
        self.assertIn(outside, text)
        self.assertNotIn("outside its sessions' time", report.render_report(self.slept()))

        last = self.state(number=3, exit_code=3, agent_started=False, slept=600.0)
        title, body, _, _ = report.problems_notice(last, "run-reports/R.md")
        self.assertEqual(title, "Notice: the Mac's sleep cut short every attempt at the run due 2026-10-11")
        self.assertIn(
            "The Package review session did not start: see the run report. Incomplete this run: nothing. The Mac's"
            " sleep cut this run short, and it",
            body,
        )

        for trigger in ("on-demand", "scheduled"):
            other = self.state(exit_code=3, agent_started=False, slept=600.0)
            other.trigger, other.attempt = trigger, None
            self.assertEqual((other.again, other.ending, report.what_follows(other)), (False, attempts.SLEPT, ""))
            self.assertNotIn("asleep", report.render_report(other))
            self.assertEqual(
                report.problems_notice(other, "r.md")[0],
                "Notice: the Package review session did not start on 2026-10-11",
            )

    def test_a_run_on_demand_reads_and_notifies_as_before(self):
        state = self.slept()
        state.trigger, state.attempt, state.due = "on-demand", None, None
        state.sessions[0].incomplete = ("Package review",)
        title, body, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: the Package review session timed out on 2026-10-11")
        self.assertTrue(
            body.split("\n\n")[0].endswith(
                "its limit is `agent.time_limit_seconds`, or the one `agent.session_time_limit_seconds` gives its"
                " workflow, in `config/run.json`."
            ),
            body,
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


class SeveralSessionsTest(OwedRunTestCase):
    """The same rules across a run's several sessions: the package review's, the post Drafts', and outreach's."""

    SESSIONS = ["package-review", "post-drafts", "outreach"]

    def setUp(self):
        super().setUp()
        self.exchange.mkdir()
        fakes.set_window(self.repo, fakes.window_from(DUE.date()))
        fakes.keep_days(self.mandu, 2)
        creator = fakes.KIT_CREATORS[0][0]
        fakes.set_run(self.repo, "outreach", {"creators": fakes.creators(fakes.KIT_CREATORS[:1])})
        writes = {
            ITEM: fakes.PROPOSAL,
            fakes.draft_path(2): fakes.draft(2),
            fakes.message_path("creator", creator): fakes.message("creator", creator, fakes.CREATOR_BODY),
        }
        self.behavior = {"write": writes}
        fakes.behave(self.codex_dir, self.behavior)

    def kinds(self):
        return sorted(entry["kind"] for entry in self.queue()["open"])

    def test_sleep_through_one_session_of_several_cuts_the_attempt_short_and_a_fresh_whole_run_follows(self):
        launch, started = cycle.launcher.run, []

        def watched(*args, **kwargs):
            started.append(kwargs["session"])
            return launch(*args, **kwargs)

        with mock.patch.object(cycle.launcher, "run", watched):
            code, out = self.slept_through(minutes=1, session="post-drafts")
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        # The Mac slept through the second session, past its limit and past the bound on the whole run, so the third
        # was never started; the first had ended by itself and confirmed its work before the Mac slept.
        self.assertEqual(started, ["package-review", "post-drafts"])
        cut_short = self.report()
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", cut_short)
        self.assertIn("- The Post Drafts session timed out: its agent was still running at its 30 min time", cut_short)
        self.assertIn("- The Outreach session did not start: the 60 min that bounds all of a run's sessions", cut_short)
        self.assertIn(f"- The Mac was asleep for about 3 h 0 min 0 s {ASLEEP_IN_A_SESSION}- {FOLLOWS}\n", cut_short)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT)])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), DUE.astimezone())
        # What the sessions had written was taken in as in any run, and the cut-short attempt alone queues no notice.
        self.assertEqual(self.kinds(), ["package-change-proposal", "post"])

        # A check in a dark wake starts nothing; the fresh run is a whole run, and starts every session again, the
        # one that finished in the cut-short attempt included.
        self.awake.return_value = False
        self.assertEqual(self.scheduled(hours=3, minutes=3), (0, ""))
        self.awake.return_value = True
        code, out = self.scheduled(hours=3, minutes=5)
        self.assertEqual(code, 0, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), self.SESSIONS)
        fresh = self.report()
        self.assertIn(
            "This is attempt 2 of at most 3: the attempt started Sunday 2026-10-11 16:01 was cut short", fresh
        )
        self.assertIn("- The run finished.\n- Sessions: 3 ran (Package review, Post Drafts, Outreach);", fresh)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])
        # Repeating the finished session queued nothing twice. The stand-in agent writes its proposal again word for
        # word, where a real one is told it is open, so the launcher sets it aside as asking the same and says so.
        self.assertEqual(self.kinds(), ["message", "notice", "package-change-proposal", "post"])
        self.assertIn("- Set aside, not queued: `name-status-stale.md`: asks the same as", fresh)
        items = [path.name for path in (self.ledger() / "review-queue/items").iterdir() if "notice" not in path.name]
        self.assertEqual(len(items), 3)
        self.assertEqual(self.scheduled(hours=3, minutes=7), (0, ""))
        self.assertEqual(len(self.reports()), 2)

    def test_a_session_the_sleep_froze_that_ends_unconfirmed_cuts_the_attempt_short_whatever_the_others_said(self):
        fakes.behave(self.codex_dir, dict(self.behavior, sessions={"post-drafts": UNCONFIRMED}))
        with self.mac.asleep_in("exec", 600, session="post-drafts"):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        # Ten minutes of sleep leave the run's bound room, so the session after the frozen one still ran.
        self.assertEqual(fakes.sessions_started(self.codex_dir), self.SESSIONS)
        text = self.report()
        self.assertNotIn("The run finished.", text)
        self.assertIn(
            "- Every session ended without an error, but the Mac slept during the run and the Post Drafts session did"
            " not confirm that it finished, so this run's work may be incomplete.\n",
            text,
        )
        self.assertIn(f"- {FOLLOWS}\n", text)
        self.assertIn("| Post Drafts | ended by itself, exit code 0 | 10 min", text)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT)])
        self.assertEqual(datetime.fromisoformat(self.queue()["next_run"]), DUE.astimezone())
        self.assertNotIn("notice", self.kinds())

        fakes.behave(self.codex_dir, self.behavior)
        code, out = self.scheduled(minutes=15)
        self.assertEqual(code, 0, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), self.SESSIONS)
        self.assertEqual(self.endings(), [("scheduled", attempts.SLEPT), ("scheduled", attempts.COMPLETED)])

    def test_a_run_the_mac_slept_during_completed_when_every_session_ended_without_an_error_and_confirmed(self):
        with self.mac.asleep_in("exec", 600, session="outreach"):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertIn("- The run finished.\n", text)
        self.assertIn("- The Mac was asleep for about 10 min 0 s while a session ran", text)
        self.assertNotIn("cut this run short", text + out)
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])
        self.assertEqual(self.scheduled(minutes=15), (0, ""))
        self.assertEqual(len(self.reports()), 1)

    def test_with_the_mac_awake_no_session_s_closing_line_decides_whether_the_run_completed(self):
        fakes.behave(self.codex_dir, dict(self.behavior, sessions={"outreach": UNCONFIRMED}))
        code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertIn("- The run finished.\n", text)
        self.assertIn("| Outreach | ended by itself, exit code 0 |", text)
        self.assertIn('its last line, "Read the first half of the package.", is neither of the closing lines', text)
        self.assertEqual(self.endings(), [("scheduled", attempts.COMPLETED)])
        # Only the package review's output reads a closing line, so nothing here is marked incomplete or told.
        self.assertNotIn("| incomplete |", text)
        self.assertNotIn("notice", self.kinds())

    def test_one_session_that_falls_short_with_the_mac_awake_waits_for_the_founder_though_the_others_finished(self):
        for number, (behavior, ending, said) in enumerate(
            (
                ({"exit": 1}, attempts.FAILED, "had a session stop early with the Mac awake"),
                ({"refused": True}, attempts.FAILED, "had a session stop early with the Mac awake"),
                ({"hang": True}, attempts.TIMED_OUT, "timed out with the Mac awake"),
            )
        ):
            with self.subTest(behavior=behavior):
                repo = fakes.make_repo(self.root / f"clone-{number}", self.env, fakes.window_from(DUE.date()))
                limits = {"session_time_limit_seconds": {"outreach": 2}}
                fakes.set_run(repo, "agent", limits)
                fakes.set_run(repo, "outreach", {"creators": fakes.creators(fakes.KIT_CREATORS[:1])})
                fakes.behave(self.codex_dir, dict(self.behavior, sessions={"outreach": behavior}))
                code, out = self.scheduled(repo=repo, minutes=1)
                self.assertNotEqual(code, 0, out)
                self.assertEqual(fakes.sessions_started(self.codex_dir), self.SESSIONS)
                self.assertEqual(self.endings(repo), [("scheduled", ending)])
                self.assertIn(
                    f"No run starts by itself after this one: only a run cut short by the Mac's sleep is run again, and"
                    f" this one {said}.",
                    self.report(repo),
                )
                self.assertEqual(self.scheduled(repo=repo, minutes=5), (0, ""))
                self.assertEqual(len(self.reports(repo)), 1)
                fakes.stop_leftovers(self.codex_dir)

    def test_a_scheduled_run_of_several_sessions_starts_no_process_that_holds_the_mac_awake(self):
        started = []

        class Watched(subprocess.Popen):
            def __init__(self, args, *rest, **kwargs):
                started.append([str(word) for word in args])
                super().__init__(args, *rest, **kwargs)

        with mock.patch.object(subprocess, "Popen", Watched):
            code, out = self.scheduled(minutes=1)
        self.assertEqual(code, 0, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), self.SESSIONS)
        agents = [command for command in started if Path(command[0]).name == "codex" and command[1] == "exec"]
        self.assertEqual(len(agents), 3)
        self.assertLessEqual({Path(command[0]).name for command in started}, {"codex", "getconf", "git", "ps"})
        for command in started:
            forbidden = "|".join(NothingHoldsTheMacAwakeTest.FORBIDDEN)
            self.assertFalse(re.search(forbidden, " ".join(command), re.IGNORECASE), command)


class NothingHoldsTheMacAwakeTest(OwedRunTestCase):
    """The run happens when the Mac is awake; the launcher never keeps it awake, wakes it, or schedules a wake."""

    # What would hold a Mac awake or wake it: the command-line tools, and the power assertions, activities, and wake
    # requests of the system frameworks, by the names a process would have to be started with.
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

    def test_the_launch_agents_hold_nothing_awake_and_keep_no_process_running(self):
        entry = Path("/srv/gr0wthlab/src/bin/gr0wthlab")
        run = schedule.run_arguments(entry, None)
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
