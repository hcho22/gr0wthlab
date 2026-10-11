"""The one place the launcher starts a process: a time limit on every wait, and a stop that leaves nothing behind."""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gr0wthlab import process
from tests import fakes
from tests.test_cycle import CycleTestCase

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
            left_without_its_parent = int(late.read_text())
            self.assertTrue({root, shell, stubborn} <= set(stopped.asked), stopped)
            self.assertEqual(set(stopped.forced), {stubborn, left_without_its_parent})
            self.assertEqual((stopped.left, stopped.proven, stopped.clean), ((), True, True))
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

    def test_a_process_waiting_on_input_never_waits_on_the_launcher_s_own(self):
        done = process.run([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"], 30)
        self.assertEqual(done.stdout, "0\n")

    def test_a_table_that_cannot_be_read_still_stops_the_process_and_says_it_proved_nothing_else(self):
        with mock.patch.object(process, "table", return_value=None):
            done = process.run([sys.executable, "-c", "import time; time.sleep(600)"], 1)
        self.assertEqual((done.stop.left, done.stop.proven, done.stop.clean), ((), False, False))
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


class EveryWaitIsBoundedTest(CycleTestCase):
    def test_a_whole_run_never_waits_without_a_time_limit_on_a_process_it_started(self):
        """A wait without one can last forever. This watches every process a run in the production clone starts, with
        a day's Draft due, so the records step's git and the claim checks' reads of a Product's code are among them."""
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        fakes.git(self.repo, "commit", "--quiet", "--all", "-m", "a window with days due", env=self.env)
        remote, clone = self.root / "remote.git", self.root / "production"
        fakes.git(self.root, "init", "--quiet", "--bare", str(remote), env=self.env)
        fakes.git(self.repo, "remote", "add", "origin", str(remote), env=self.env)
        fakes.git(self.repo, "push", "--quiet", "origin", "main", env=self.env)
        fakes.git(self.root, "clone", "--quiet", str(remote), str(clone), env=self.env)
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(1): fakes.draft(1)}})
        waits = []

        class Watched(subprocess.Popen):
            def wait(self, timeout=None):
                waits.append((self.args, timeout is not None or self.returncode is not None))
                return super().wait(timeout)

        with mock.patch.object(subprocess, "Popen", Watched):
            code, out = self.run_cycle(repo=clone)
        self.assertEqual(code, 0, out)
        self.assertIn("records: pushed", out)
        self.assertLessEqual({"codex", "git"}, {Path(command[0]).name for command, _ in waits})
        self.assertLessEqual({"fetch", "cat-file", "push"}, {word for command, _ in waits for word in command})
        self.assertEqual([command for command, bounded in waits if not bounded], [])


if __name__ == "__main__":
    unittest.main()
