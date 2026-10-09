"""The launcher's prompt, run ids, and fail-closed start."""

import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gr0wthlab import boundary, cli, launcher
from tests.test_boundary import CONFIG, REGISTRY

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
        self.assertIn("  - Mandu: /srv/home/f/Mandu", prompt)
        self.assertIn("\n- Local listener localhost-tcp: 127.0.0.1:5\n- Instruction: /srv/i.md\n", prompt)
        self.assertTrue(prompt.endswith("---\n\nDo the thing.\n"))


class FailClosedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_launcher(self, env, instruction):
        out = io.StringIO()
        env = dict(env, GR0WTHLAB_LOG_DIR=str(self.logs))
        record = launcher.run(REPO, instruction, "on-demand", env, Path(self.tmp.name), out=out)
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
            launcher.run(REPO, Path("x"), "hourly", {}, Path(self.tmp.name))


class CliTest(unittest.TestCase):
    def test_commands_parse(self):
        parser = cli.parser()
        args = parser.parse_args(["run", "--instruction", "i.md", "--trigger", "scheduled"])
        self.assertEqual((args.command, args.trigger), ("run", "scheduled"))
        self.assertEqual(parser.parse_args(["run", "--instruction", "i.md"]).trigger, "on-demand")
        args = parser.parse_args(["launch-agent", "--instruction", "i.md", "--weekly", "monday", "07:30"])
        self.assertEqual(args.weekly, ["monday", "07:30"])
        self.assertEqual(parser.parse_args(["boundary-check", "--verify", "R"]).verify, "R")

    def test_entry_point_starts_through_its_shebang(self):
        completed = subprocess.run([str(cli.ENTRY), "--help"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage: gr0wthlab", completed.stdout)


if __name__ == "__main__":
    unittest.main()
