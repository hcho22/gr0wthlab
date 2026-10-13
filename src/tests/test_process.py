"""The one place the launcher starts a process: a time limit on every wait, and a stop that takes all it can find."""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from gr0wthlab import process
from tests import fakes
from tests.test_filming import DAY_1, PLAN, FilmingRunCase

# Starts what a stalled agent leaves, notes each process id, says it is ready, and waits: a shell in a session of its
# own, as Codex starts a shell command, which answers a request to stop by starting one more process and ending, so
# that process is left without its parent; and a child that ignores a request to stop.
IGNORES = (
    "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(600)"
)
SHELL = "trap '/bin/sleep 599 & echo $! > \"$0\"; exit 0' TERM; echo ready; while :; do /bin/sleep 0.2; done"
FAMILY = f"""
import os, subprocess, sys, time
shell = subprocess.Popen(
    ["/bin/sh", "-c", {SHELL!r}, sys.argv[2]],
    start_new_session=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)
stubborn = subprocess.Popen([sys.executable, "-c", {IGNORES!r}], stdout=subprocess.PIPE)
shell.stdout.readline(), stubborn.stdout.readline()
with open(sys.argv[1], "w") as noted:
    noted.write(" ".join(str(pid) for pid in [os.getpid(), shell.pid, stubborn.pid]))
print("ready", flush=True)
time.sleep(600)
"""


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.noted = Path(self.tmp.name) / "pids.txt"

    def tearDown(self):
        fakes.stop_leftovers(Path(self.tmp.name))
        self.tmp.cleanup()

    def test_a_process_that_finishes_in_time_is_returned_as_it_ended(self):
        done = process.run(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().upper()); sys.exit(3)"], 30, input="in"
        )
        self.assertEqual((done.returncode, done.stdout, done.timed_out, done.ok), (3, "IN\n", False, False))
        self.assertIsNone(done.stop)
        quiet = process.run([sys.executable, "-c", "import sys; sys.stderr.write(repr(sys.stdin.read()))"], 30)
        self.assertEqual((quiet.returncode, quiet.stderr, quiet.ok), (0, "''", True))

    def test_output_goes_to_the_files_given_for_it(self):
        with (Path(self.tmp.name) / "out").open("w+") as out, (Path(self.tmp.name) / "err").open("w+") as err:
            code = "import sys; print('to out'); print('to err', file=sys.stderr)"
            done = process.run([sys.executable, "-c", code], 30, stdout=out, stderr=err)
            out.seek(0), err.seek(0)
            self.assertEqual((out.read(), err.read(), done.stdout, done.stderr), ("to out\n", "to err\n", "", ""))

    def test_a_command_that_cannot_start_raises_as_before(self):
        with self.assertRaises(OSError):
            process.run([str(Path(self.tmp.name) / "absent")], 30)

    def test_a_stop_takes_everything_the_process_started_and_shows_nothing_is_left(self):
        late = Path(self.tmp.name) / "late.txt"
        family = subprocess.Popen(
            [sys.executable, "-c", FAMILY, str(self.noted), str(late)], stdout=subprocess.PIPE, text=True
        )
        try:
            self.assertEqual(family.stdout.readline(), "ready\n")
            root, shell, stubborn = fakes.agent_pids(Path(self.tmp.name))
            with mock.patch.object(process, "STOP_GRACE", 2):
                stopped = process.stop(family)
                said = stopped.describe()
            left_without_its_parent = int(late.read_text())
            self.assertTrue({root, shell, stubborn} <= set(stopped.asked), stopped)
            self.assertNotIn(left_without_its_parent, stopped.asked)
            self.assertEqual(set(stopped.forced), {stubborn, left_without_its_parent})
            self.assertEqual((stopped.left, stopped.proven), ((), True))
            self.assertEqual(
                said,
                f"{len(stopped.asked)} processes asked to stop, then 2 processes forced after 2 s, 1 of them found"
                " after the ask; the process table shows none of them left running",
            )
            self.assertTrue(fakes.all_gone([root, shell, stubborn, left_without_its_parent]))
        finally:
            family.stdout.close()
            if late.is_file():
                self.noted.write_text(f"{self.noted.read_text()} {late.read_text()}")

    def test_a_process_at_its_limit_is_asked_to_stop_and_what_it_wrote_is_kept(self):
        started = time.monotonic()
        waits = "import sys, time; print('up', flush=True); sys.stdin.read(); time.sleep(600)"
        done = process.run([sys.executable, "-c", waits], 3)
        self.assertEqual((done.timed_out, done.limit, done.ok, done.stdout), (True, 3, False, "up\n"))
        self.assertEqual((len(done.stop.asked), done.stop.forced, done.stop.left), (1, (), ()))
        self.assertEqual(done.returncode, -signal.SIGTERM)
        self.assertLess(time.monotonic() - started, 3 + process.STOP_GRACE)

    def test_a_process_that_ended_on_its_own_as_its_limit_passed_is_not_spoken_of_as_several(self):
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait()
        stopped = process.stop(ended)
        self.assertEqual((stopped.asked, stopped.forced, stopped.left, stopped.proven), ((), (), (), True))
        self.assertEqual(
            stopped.describe(), "0 processes asked to stop; the stop found none still running in the process table"
        )

    def test_a_process_the_mac_slept_past_its_limit_is_stopped_once_the_mac_wakes(self):
        started = time.monotonic()
        asleep = [sys.executable, "-c", "import time; time.sleep(600)"]
        done = process.run(asleep, 1800, clock=fakes.stepped_clock(7200))
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual((done.timed_out, len(done.stop.asked), done.stop.left), (True, 1, ()))
        self.assertTrue(7200 <= done.seconds < 7230 and 0 < done.awake < 30, done)

    def test_a_sleep_shorter_than_the_limit_stops_nothing_and_is_told_from_the_time_awake(self):
        done = process.run([sys.executable, "-c", "import time; time.sleep(2)"], 1800, clock=fakes.stepped_clock(600))
        self.assertEqual((done.timed_out, done.returncode), (False, 0))
        self.assertEqual(round(done.seconds - done.awake), 600)
        awake = process.run([sys.executable, "-c", "pass"], 30)
        self.assertTrue(0 <= awake.awake <= awake.seconds < 30, awake)
        self.assertLess(awake.seconds - awake.awake, 1)

    def test_a_wall_clock_set_back_cannot_extend_a_limit(self):
        started = time.monotonic()
        asleep = [sys.executable, "-c", "import time; time.sleep(600)"]
        done = process.run(asleep, 3, clock=fakes.stepped_clock(-86400))
        self.assertLess(time.monotonic() - started, 3 + process.STOP_GRACE)
        self.assertTrue(done.timed_out)
        self.assertTrue(3 <= done.awake == done.seconds < 3 + process.STOP_GRACE, done)

    def test_a_process_that_reads_its_input_late_still_gets_all_of_it(self):
        late = f"import sys, time; time.sleep({process.CHECK + 0.5}); print(len(sys.stdin.read()))"
        done = process.run([sys.executable, "-c", late], 30, input="x" * 200_000)
        self.assertEqual((done.returncode, done.stdout), (0, "200000\n"))

    def test_a_process_waiting_on_input_never_waits_on_the_launcher_s_own(self):
        done = process.run([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"], 30)
        self.assertEqual(done.stdout, "0\n")

    def test_a_table_that_cannot_be_read_still_stops_the_process_and_says_it_proved_nothing_else(self):
        with mock.patch.object(process, "table", return_value=None):
            done = process.run([sys.executable, "-c", "import time; time.sleep(600)"], 1)
        self.assertEqual((done.stop.left, done.stop.proven), ((), False))
        self.assertEqual(done.returncode, -signal.SIGTERM)

    def test_the_family_never_takes_in_the_launcher_or_its_other_children(self):
        bystander = subprocess.Popen(["/bin/sleep", "600"])
        try:
            done = process.run([sys.executable, "-c", "import time; time.sleep(600)"], 1)
            self.assertNotIn(bystander.pid, done.stop.asked)
            self.assertNotIn(os.getpid(), done.stop.asked)
            self.assertIsNone(bystander.poll())
        finally:
            bystander.kill()
            bystander.wait()

    def test_limits_read_in_minutes_where_they_are_whole(self):
        self.assertEqual(
            [process.limit_text(span) for span in (1800, 60, 90, 1.5, 10.0)],
            ["30 min", "1 min", "90 s", "1.5 s", "10 s"],
        )


class EveryWaitIsBoundedTest(FilmingRunCase):
    def test_a_whole_run_never_waits_without_a_time_limit_on_a_process_it_started(self):
        """A wait without one can last forever. This watches every process a run in the production clone starts, with
        a day's Draft and its edit record due, so the records step's git, the claim checks' reads of a Product's
        code, and the video tooling that measures the footage and cuts the day's video are among them. Each starts
        through process.run, which is what stops one at its limit with every process it started."""
        fakes.keep_days(self.mandu, 1, 8)
        fakes.git(self.repo, "commit", "--quiet", "--all", "-m", "a window with days due, and footage", env=self.env)
        remote, clone = self.root / "remote.git", self.root / "production"
        fakes.git(self.root, "init", "--quiet", "--bare", str(remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.root, "clone", "--quiet", str(remote), str(clone), env=self.env)
        code, out = self.run_cycle(repo=clone, at=fakes.SUNDAY_RUN)
        self.assertEqual(code, 0, out)
        self.exchange = clone / "ledger" / "founder"  # the Founder's records are each checkout's own
        self.decide(PLAN, "approve")
        self.clip("d01-s1.mov")
        writes = {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        fakes.behave(self.codex_dir, {"write": writes})
        started, waits, inside = [], [], []
        run = process.run

        def through(*args, **kwargs):
            inside.append(args[0])
            try:
                return run(*args, **kwargs)
            finally:
                inside.pop()

        class Watched(subprocess.Popen):
            def __init__(self, command, *args, **kwargs):
                started.append((command, bool(inside)))
                super().__init__(command, *args, **kwargs)

            def wait(self, timeout=None):
                waits.append((self.args, timeout is not None or self.returncode is not None))
                return super().wait(timeout)

        with mock.patch.object(subprocess, "Popen", Watched), mock.patch.object(process, "run", through):
            code, out = self.run_cycle(repo=clone, at=fakes.SUNDAY_RUN + timedelta(hours=1))
        self.assertEqual(code, 0, out)
        self.assertIn("records: pushed", out)
        self.assertIn("asset", next(entry for entry in self.queue(clone)["open"] if entry["kind"] == "post"))
        names = {Path(command[0]).name for command, _ in started}
        self.assertLessEqual({"codex", "git", "ffmpeg", "ffprobe"}, names)
        self.assertLessEqual({"fetch", "cat-file", "push"}, {word for command, _ in waits for word in command})
        self.assertEqual([command for command, bounded in waits if not bounded], [])
        self.assertEqual([command for command, through_run in started if not through_run], [])


if __name__ == "__main__":
    unittest.main()
