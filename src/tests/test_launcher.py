"""The launcher's prompt, run ids, and fail-closed start."""

import io
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, cli, launcher
from tests import fakes
from tests.test_boundary import CONFIG, FILMING_REGISTRY, REGISTRY

REPO = Path(__file__).resolve().parents[2]


class PromptTest(unittest.TestCase):
    def test_run_id(self):
        run_id = launcher.new_run_id("scheduled", datetime(2026, 10, 12, 14, 0, 5, tzinfo=timezone.utc))
        self.assertRegex(run_id, r"^20261012T140005Z-scheduled-[0-9a-f]{4}$")

    def test_prompt_states_the_run_facts_then_the_instruction(self):
        resolved = boundary.resolve_boundary(
            Path("/srv/gr0wthlab"), CONFIG, REGISTRY, {}, Path("/srv/home/f"), git=[Path("/srv/gr0wthlab/.git")]
        )
        prompt = launcher.compose_prompt(
            resolved,
            "RUN1",
            "scheduled",
            "2026-10-12T14:00:05+00:00",
            Path("/srv/i.md"),
            "Do the thing.\n",
            ["Local listener localhost-tcp: 127.0.0.1:5"],
        )
        self.assertTrue(prompt.startswith("# gr0wthlab run RUN1\n"))
        self.assertIn("- Trigger: scheduled, started 2026-10-12T14:00:05+00:00.", prompt)
        self.assertIn("(git directory /srv/gr0wthlab/.git)", prompt)
        self.assertIn("  - drafts: /srv/gr0wthlab/workspace/drafts", prompt)
        self.assertIn(
            "  - Mandu: /srv/home/f/Mandu, of which only these paths; the runtime refuses the rest:\n", prompt
        )
        self.assertIn("  - RepToday: /srv/home/f/RepToday\n", prompt)
        self.assertIn("\n- Local listener localhost-tcp: 127.0.0.1:5\n- Instruction: /srv/i.md\n", prompt)
        self.assertTrue(prompt.endswith("---\n\nDo the thing.\n"))

    def test_prompt_names_what_the_run_reads_of_mandu(self):
        resolved = boundary.resolve_boundary(
            Path("/srv/gr0wthlab"), CONFIG, FILMING_REGISTRY, {}, Path("/srv/f"), git=[Path("/srv/gr0wthlab/.git")]
        )
        prompt = launcher.compose_prompt(resolved, "RUN1", "scheduled", "now", Path("/srv/i.md"), "Do the thing.\n")
        self.assertIn(
            "  - Mandu: /srv/f/Mandu, of which only these paths; the runtime refuses the rest:\n"
            "    - /srv/f/Mandu/projects/RepToday/gtm\n"
            "    - /srv/f/Mandu/projects/RepToday/02-launch-checklist.md\n"
            "  - RepToday: /srv/f/RepToday\n",
            prompt,
        )


class FailClosedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self, env, instruction):
        out = io.StringIO()
        env = dict(env, GR0WTHLAB_LOG_DIR=str(self.logs))
        record = launcher.run(REPO, instruction, "on-demand", env, Path(self.tmp.name), out=out, time_limit=60)
        return record, out.getvalue()

    def test_missing_codex_refuses_to_start_and_records_why(self):
        record, out = self.run_launcher({"PATH": self.tmp.name}, REPO / "src/checks/boundary-probe.md")
        self.assertEqual(record["exit_code"], launcher.EXIT_CONFIG)
        self.assertIn("codex executable not found", out)
        saved = json.loads((self.logs / f"{record['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["exit_code"], launcher.EXIT_CONFIG)

    def test_missing_instruction_refuses_to_start(self):
        record, out = self.run_launcher({}, self.logs / "absent.md")
        self.assertEqual(record["exit_code"], launcher.EXIT_CONFIG)
        self.assertIn("refusing to start", out)

    def test_unknown_trigger_is_rejected(self):
        with self.assertRaises(boundary.ConfigError):
            launcher.run(REPO, Path("x"), "hourly", {}, Path(self.tmp.name), time_limit=60)


class LeftoverTest(unittest.TestCase):
    """A boundary check that was killed mid-run cannot clean up; the next run of any kind does, before its agent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.home = root / "home"
        self.repo = fakes.make_repo(self.home / "gr0wthlab", fakes.git_env(root))
        self.env = {
            "GR0WTHLAB_LOG_DIR": str(root / "logs"),
            "GR0WTHLAB_CODEX_BIN": str(fakes.install_codex(root / "bin")),
        }
        for name in ("Mandu", "RepToday", "Immerse"):
            (self.home / name).mkdir()
            self.env[f"GR0WTHLAB_{name.upper()}_DIR"] = str(self.home / name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_run_removes_what_a_stopped_boundary_check_left_before_its_agent_starts(self):
        stale = (
            self.repo / "workspace/instructions/gr0wthlab-boundary-probe-20261001T000000Z-on-demand-0001-shell-steps.sh"
        )
        stale.write_text("#!/bin/sh\n", encoding="utf-8")
        mine = (
            self.repo / "workspace/instructions/gr0wthlab-boundary-probe-20261009T000000Z-on-demand-abcd-shell-steps.sh"
        )
        mine.write_text("#!/bin/sh\n", encoding="utf-8")
        task = self.repo / "src/instructions/weekly-run.md"
        facts = [f"Run brief, read it first: {self.repo / 'ledger/run-reports/brief.md'}"]
        out = io.StringIO()
        record = launcher.run(
            self.repo,
            task,
            "on-demand",
            self.env,
            self.home,
            out,
            None,
            facts,
            "20261009T000000Z-on-demand-abcd",
            time_limit=60,
        )
        self.assertEqual((record["exit_code"], record["agent_started"]), (0, True))
        self.assertEqual(record["probe_files_removed"], [str(stale.relative_to(self.repo))])
        self.assertIn(f"removed boundary probe files left in the areas: {stale.relative_to(self.repo)}", out.getvalue())
        self.assertLess(out.getvalue().index("removed boundary probe files"), out.getvalue().index("preflight refused"))
        self.assertFalse(stale.exists())
        self.assertTrue(mine.is_file(), "the run in progress keeps its own files")

    def test_a_run_with_nothing_left_behind_says_nothing_of_it(self):
        task = self.repo / "src/instructions/weekly-run.md"
        facts = [f"Run brief, read it first: {self.repo / 'ledger/run-reports/brief.md'}"]
        out = io.StringIO()
        record = launcher.run(self.repo, task, "on-demand", self.env, self.home, out, None, facts, time_limit=60)
        self.assertEqual(record["exit_code"], 0)
        self.assertNotIn("probe_files_removed", record)
        self.assertNotIn("removed boundary probe files", out.getvalue())


class FootagePreflightTest(unittest.TestCase):
    """Before every run, with no model, the sandbox is shown unable to list the footage place and each footage
    folder in it; one it can list stops the run before the agent starts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.home = root / "home"
        self.repo = fakes.make_repo(self.home / "gr0wthlab", fakes.git_env(root), films=True)
        self.codex_dir = root / "bin"
        self.logs = root / "logs"
        self.env = {
            "GR0WTHLAB_LOG_DIR": str(self.logs),
            "GR0WTHLAB_CODEX_BIN": str(fakes.install_codex(self.codex_dir)),
        }
        for name in ("Mandu", "RepToday", "Immerse"):
            (self.home / name).mkdir()
            self.env[f"GR0WTHLAB_{name.upper()}_DIR"] = str(self.home / name)
        # The Founder's place, as the registry names it: the Product's folder in Mandu, beside its package.
        self.place = self.home / "Mandu" / "projects" / "RepToday"
        (self.place / "gtm").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self):
        task = self.repo / "src/instructions/weekly-run.md"
        facts = [f"Run brief, read it first: {self.repo / 'ledger/run-reports/brief.md'}"]
        out = io.StringIO()
        record = launcher.run(self.repo, task, "on-demand", self.env, self.home, out, None, facts, time_limit=60)
        saved = json.loads((self.logs / f"{record['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["preflight"], record["preflight"])
        return record, out.getvalue()

    def test_each_footage_folder_is_shown_refused_before_the_agent_starts(self):
        for name in ("window-1", "window-2"):
            (self.place / name).mkdir()
        record, out = self.run_launcher()
        self.assertEqual((record["exit_code"], record["agent_started"]), (0, True))
        footage = record["preflight"]["footage"]
        self.assertEqual(
            [entry["target"] for entry in footage["refused"]],
            [str(self.place), str(self.place / "window-1"), str(self.place / "window-2")],
        )
        self.assertEqual((footage["ok"], footage["listed"], footage["failures"]), (True, [], []))
        line = "gr0wthlab: preflight refused a listing of the footage place and of 2 footage folders in it\n"
        self.assertIn(line, out)
        self.assertLess(out.index("paths and allowed"), out.index(line))

    def test_a_place_with_no_footage_folder_yet_is_shown_refused_itself(self):
        record, out = self.run_launcher()
        self.assertEqual([entry["target"] for entry in record["preflight"]["footage"]["refused"]], [str(self.place)])
        self.assertIn("preflight refused a listing of the footage place and of 0 footage folders in it\n", out)

    def test_a_place_that_does_not_exist_yet_has_nothing_to_show(self):
        (self.place / "gtm").rmdir()
        self.place.rmdir()
        record, out = self.run_launcher()
        self.assertEqual((record["exit_code"], record["agent_started"]), (0, True))
        self.assertEqual(record["preflight"]["footage"], {"ok": True, "refused": [], "listed": [], "failures": []})
        self.assertNotIn("refused a listing", out)

    def test_a_sandbox_that_can_list_a_footage_folder_stops_the_run_before_the_agent_starts(self):
        (self.place / "window-1").mkdir()
        fakes.behave(self.codex_dir, {"sandbox_reads_footage": True})
        record, out = self.run_launcher()
        self.assertEqual((record["exit_code"], record["agent_started"]), (launcher.EXIT_BOUNDARY, False))
        self.assertEqual(record["preflight"]["footage"]["listed"], [str(self.place), str(self.place / "window-1")])
        self.assertIn("gr0wthlab: the sandbox could read where raw footage is kept; the agent was not started\n", out)
        self.assertIn(f"  listed {self.place / 'window-1'}\n", out)
        self.assertFalse((self.codex_dir / "prompt.txt").exists(), "the agent was never handed its prompt")
        self.assertNotIn("network", record["preflight"])


class CliTest(unittest.TestCase):
    def test_commands_parse(self):
        parser = cli.parser()
        args = parser.parse_args(["run", "--instruction", "i.md", "--trigger", "scheduled"])
        self.assertEqual((args.command, args.trigger), ("run", "scheduled"))
        self.assertEqual(parser.parse_args(["run", "--instruction", "i.md"]).trigger, "on-demand")
        args = parser.parse_args(["launch-agent", "--instruction", "i.md", "--once", "2026-10-11T16:00"])
        self.assertEqual(args.once, "2026-10-11T16:00")
        self.assertEqual(parser.parse_args(["boundary-check", "--verify", "R"]).verify, "R")
        self.assertEqual(parser.parse_args(["boundary-check", "--trigger", "scheduled"]).trigger, "scheduled")
        args = parser.parse_args(["run", "--trigger", "scheduled"])
        self.assertEqual((args.instruction, args.once), (None, None))
        for command in (["run"], ["launch-agent"]):
            with self.subTest(command=command), self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                parser.parse_args([*command, "--weekly", "sunday", "16:00"])
        self.assertTrue(
            parser.parse_args(["launch-agent", "--boundary-check", "--once", "2026-10-11T16:00"]).boundary_check
        )
        self.assertEqual(parser.parse_args(["check-incoming"]).command, "check-incoming")

    def test_launch_agent_defaults_to_the_configured_weekly_run(self):
        out = io.TextIOWrapper(io.BytesIO())
        with tempfile.TemporaryDirectory() as directory:
            codex = Path(directory) / "codex"
            codex.write_text("#!/bin/sh\n")
            codex.chmod(0o755)
            env = {"GR0WTHLAB_CODEX_BIN": str(codex), "GR0WTHLAB_PRE_RUN": "{}", "GR0WTHLAB_LOG_DIR": directory}
            with mock.patch.dict(os.environ, env), mock.patch.object(sys, "stdout", out):
                self.assertEqual(cli.main(["launch-agent"]), 0)
        agent = plistlib.loads(out.buffer.getvalue())
        self.assertEqual(agent["StartCalendarInterval"], {"Weekday": 0, "Hour": 16, "Minute": 0})
        self.assertEqual(agent["ProgramArguments"][1:4], ["run", "--trigger", "scheduled"])
        self.assertEqual(
            agent["ProgramArguments"][-2:], ["--instruction", str(cli.REPO_ROOT / "src/instructions/weekly-run.md")]
        )
        self.assertNotIn("GR0WTHLAB_PRE_RUN", agent["EnvironmentVariables"])

    def test_entry_point_starts_through_its_shebang(self):
        completed = subprocess.run([str(cli.ENTRY), "--help"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage: gr0wthlab", completed.stdout)


if __name__ == "__main__":
    unittest.main()
