"""The Codex command line, environment, fingerprint, and preflight evaluation."""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, codex, process
from gr0wthlab.boundary import ConfigError
from tests.test_boundary import CONFIG, REGISTRY

CODEX_CONFIG = dict(
    CONFIG,
    codex={
        "permission_profile": "gr0wthlab",
        "model": "model-a",
        "reasoning_effort": "high",
        "approval_policy": "never",
        "sub_agents": False,
        "session_flags": ["--ignore-user-config", "--ignore-rules", "--ephemeral"],
        "disabled_features": ["apps", "hooks"],
        "shell_environment": {"GIT_CONFIG_GLOBAL": "/dev/null"},
    },
)

# Stands in for `codex sandbox ... -- CMD...` without any sandbox, so every forbidden write lands.
# It records the CODEX_HOME it was started with next to itself.
FAKE_UNSANDBOXED_CODEX = """#!/bin/sh
printf '%s' "$CODEX_HOME" > "$(dirname "$0")/codex-home"
while [ "$1" != "--" ]; do shift; done
shift
exec "$@"
"""


class CodexTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.repo = root / "home" / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        for name in ("src", "config/guardrails", ".git", "ledger"):
            (self.repo / name).mkdir(parents=True)
        self.home = root / "home"
        (self.home / ".codex").mkdir()
        self.temp_dir = root / "T"
        self.temp_dir.mkdir()
        self.boundary = boundary.resolve_boundary(
            self.repo, CODEX_CONFIG, REGISTRY, {}, self.home, git=[self.repo / ".git"]
        )
        self.codex_bin = root / "bin" / "codex"
        self.environment = codex.child_environment(self.home, self.codex_bin, str(self.temp_dir))

    def tearDown(self):
        self.tmp.cleanup()

    def install_fake_codex(self, script):
        self.codex_bin.parent.mkdir()
        self.codex_bin.write_text(script, encoding="utf-8")
        self.codex_bin.chmod(self.codex_bin.stat().st_mode | stat.S_IXUSR)


class CommandTest(CodexTestCase):
    def test_inline_table_escapes_keys_and_values(self):
        table = codex.toml_inline_table({'/a "b"\\c': "write"})
        self.assertEqual(table, '{"/a \\"b\\"\\\\c" = "write"}')
        if sys.version_info >= (3, 11):
            import tomllib

            self.assertEqual(tomllib.loads("t = " + table)["t"], {'/a "b"\\c': "write"})

    def test_overrides_define_and_select_the_profile(self):
        args = codex.config_overrides(CODEX_CONFIG, self.boundary)
        overrides = [args[i + 1] for i, arg in enumerate(args) if arg == "-c"]
        self.assertIn('default_permissions="gr0wthlab"', overrides)
        self.assertIn("permissions.gr0wthlab.network.enabled=false", overrides)
        self.assertIn('approval_policy="never"', overrides)
        self.assertIn("agents.enabled=false", overrides)
        self.assertIn('shell_environment_policy.set={"GIT_CONFIG_GLOBAL" = "/dev/null"}', overrides)
        filesystem = [o for o in overrides if o.startswith("permissions.gr0wthlab.filesystem=")]
        self.assertEqual(len(filesystem), 1)
        for path in self.boundary.area_paths:
            self.assertIn(f'"{path}" = "write"', filesystem[0])
        disabled = [args[i + 1] for i, arg in enumerate(args) if arg == "--disable"]
        self.assertEqual(disabled, ["apps", "hooks"])

    def test_exec_command_reads_the_prompt_from_stdin_and_never_widens_the_sandbox(self):
        command = codex.build_exec_command(CODEX_CONFIG, self.boundary, self.codex_bin, Path("/logs/run.md"))
        self.assertEqual(command[:4], [str(self.codex_bin), "exec", "--cd", str(self.repo / "workspace")])
        self.assertEqual(command[-1], "-")
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--json"):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index("--model") + 1], "model-a")
        self.assertIn(
            'model_reasoning_effort="high"', [command[i + 1] for i, part in enumerate(command) if part == "-c"]
        )
        for widening in (
            "--sandbox",
            "-s",
            "--add-dir",
            "--full-auto",
            "--yolo",
            "--dangerously-bypass-approvals-and-sandbox",
            "--approve-for-me",
        ):
            self.assertNotIn(widening, command)

    def test_the_agent_runs_at_the_configured_reasoning_effort_and_the_preflight_takes_none(self):
        for effort in boundary.REASONING_EFFORTS:
            config = dict(CODEX_CONFIG, codex=dict(CODEX_CONFIG["codex"], reasoning_effort=effort))
            command = codex.build_exec_command(config, self.boundary, self.codex_bin, Path("/logs/run.md"))
            overrides = [command[i + 1] for i, part in enumerate(command) if part == "-c"]
            with self.subTest(effort=effort):
                self.assertEqual(
                    [o for o in overrides if o.startswith("model_reasoning_effort")],
                    [f'model_reasoning_effort="{effort}"'],
                )
                self.assertLess(command.index(f'model_reasoning_effort="{effort}"'), command.index("-"))
        self.assertNotIn("model_reasoning_effort", " ".join(codex.config_overrides(CODEX_CONFIG, self.boundary)))

    def test_fingerprint_ignores_the_run_output_path_only(self):
        env = {"HOME": "/h"}
        other_config = dict(CODEX_CONFIG, codex=dict(CODEX_CONFIG["codex"], model="model-b"))
        other_effort = dict(CODEX_CONFIG, codex=dict(CODEX_CONFIG["codex"], reasoning_effort="medium"))
        first = codex.build_exec_command(CODEX_CONFIG, self.boundary, self.codex_bin, Path("/l/a.md"))
        second = codex.build_exec_command(CODEX_CONFIG, self.boundary, self.codex_bin, Path("/l/b.md"))
        other_model = codex.build_exec_command(other_config, self.boundary, self.codex_bin, Path("/l/a.md"))
        medium = codex.build_exec_command(other_effort, self.boundary, self.codex_bin, Path("/l/a.md"))
        self.assertEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(second, env, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(other_model, env, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(medium, env, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(first, {"HOME": "/x"}, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(first, env, "v2"))


class EnvironmentTest(CodexTestCase):
    def test_environment_is_built_from_scratch(self):
        env = codex.child_environment(self.home, self.codex_bin, "/tmp/user")
        names = {"HOME", "USER", "LOGNAME", "SHELL", "LANG", "TMPDIR", "PATH", "CODEX_HOME", "RUST_LOG"}
        self.assertEqual(set(env), names)
        # Every run has Codex keep its record of each tool call, which the boundary check reads.
        self.assertEqual(env["RUST_LOG"], "error,codex_otel.log_only=info")
        self.assertEqual(env["PATH"].split(os.pathsep), [str(self.codex_bin.parent)] + list(codex.SYSTEM_PATH))
        self.assertEqual(env["TMPDIR"], "/tmp/user")
        self.assertEqual(env["CODEX_HOME"], str(self.home / ".codex"))

    def test_codex_binary_resolution(self):
        with self.assertRaises(ConfigError):
            codex.resolve_codex_binary({"GR0WTHLAB_CODEX_BIN": "bin/codex"})
        with self.assertRaises(ConfigError):
            codex.resolve_codex_binary({"PATH": str(self.home)})
        self.install_fake_codex("#!/bin/sh\n")
        self.assertEqual(codex.resolve_codex_binary({"PATH": str(self.codex_bin.parent)}), self.codex_bin)
        self.assertEqual(codex.resolve_codex_binary({"GR0WTHLAB_CODEX_BIN": str(self.codex_bin)}), self.codex_bin)


CLOSING = (
    " mcp_server= mcp_server_origin= event.timestamp=2026-10-09T00:00:01.000Z conversation.id=c app.version=0.160.0"
    ' auth_mode="Chatgpt" originator=codex_exec terminal.type=unknown model=model-a slug=model-a'
)


def tool_result(seq, tool="apply_patch", success="false", body="patch output=refused" + CLOSING):
    return (
        f'2026-10-09T00:00:0{seq}.000000Z  INFO codex_otel.log_only: event.name="codex.tool_result"'
        f" tool_result_seq={seq} tool_name={tool} tool_namespace=functions call_id=call-{seq} duration_ms=0"
        f" success={success} output_truncated=false agent_name=/root arguments={body}\n"
    )


class ToolRecordTest(unittest.TestCase):
    """Reading the record Codex keeps of each tool call, whose arguments and output are free text on many lines."""

    def test_calls_are_read_in_order_among_the_log_s_other_records(self):
        patch = "*** Begin Patch\n*** Add File: /r/x.txt\n+probe\n*** End Patch"
        log = (
            '2026-10-09T00:00:00.000000Z  INFO codex_otel.log_only: event.name="codex.conversation_starts" a=b\n'
            + tool_result(1, body=f"{patch} output=refused{CLOSING}")
            + "2026-10-09T00:00:01.500000Z ERROR codex_core::tools::router: error=refused\n"
            + tool_result(2, "exec_command", "true", '{"cmd":"pwd"} output=Output:\n/r\n' + CLOSING)
        )
        calls, problems = codex.tool_results(log)
        self.assertEqual(problems, [])
        self.assertEqual(
            [(call.seq, call.tool, call.success) for call in calls],
            [(1, "apply_patch", False), (2, "exec_command", True)],
        )
        self.assertEqual(calls[0].gave("refused"), patch)
        self.assertEqual(calls[0].said(), "refused")
        self.assertEqual(calls[1].gave("Output:\n/r\n"), '{"cmd":"pwd"}')
        self.assertEqual(calls[1].said(), "Output: /r")

    def test_a_call_gave_an_output_only_when_its_record_ends_with_exactly_that(self):
        call = codex.tool_results(tool_result(1, body=f"patch output=refused{CLOSING}"))[0][0]
        self.assertEqual(call.gave("refused"), "patch")
        self.assertIsNone(call.gave("fused"), "the output must be whole")
        self.assertIsNone(call.gave("refuse"))
        # Arguments that end with the words of an output are still arguments: the real output follows them.
        quoting = codex.tool_results(tool_result(1, body=f"patch output=refused output=invalid patch{CLOSING}"))[0][0]
        self.assertIsNone(quoting.gave("refused"))
        self.assertEqual(quoting.gave("invalid patch"), "patch output=refused")
        # A record that does not end with Codex's closing fields was cut off or is not a record.
        cut = codex.tool_results(tool_result(1, body="patch output=refused"))[0][0]
        self.assertIsNone(cut.gave("refused"))
        self.assertEqual(cut.said(), "refused")

    def test_calls_written_out_of_order_are_whole_and_a_missing_or_repeated_number_is_not(self):
        swapped = tool_result(2) + tool_result(1) + tool_result(3)
        self.assertEqual(codex.tool_results(swapped)[1], [])
        for numbers in ((1, 3), (1, 2, 2), (2, 3)):
            calls, problems = codex.tool_results("".join(tool_result(seq) for seq in numbers))
            self.assertEqual(len(calls), len(numbers))
            self.assertIn(f"numbered {list(numbers)}, not 1 to {len(numbers)} once each", problems[0])
        self.assertEqual(codex.tool_results("no records here\n"), ([], []))

    def test_a_line_inside_a_record_that_only_looks_like_a_tool_call_is_not_read_as_one(self):
        # A record starts at a line that starts with a timestamp and a level; text further along a line never does.
        inside = tool_result(7).rstrip("\n")
        log = tool_result(1, "exec_command", "true", f'{{"cmd":"echo"}} output=said: {inside}{CLOSING}')
        calls, problems = codex.tool_results(log)
        self.assertEqual(([call.seq for call in calls], problems), ([1], []))


class EventStreamTest(unittest.TestCase):
    """Reading Codex's own last error out of the event stream a run keeps."""

    def test_the_last_error_codex_reported_is_read_on_one_line(self):
        refusal = "exceeded retry limit, last status: 429 Too Many Requests"
        events = [
            {"type": "thread.started", "thread_id": "t"},
            {"type": "item.completed", "item": {"type": "error", "message": "a warning about the model's metadata"}},
            {"type": "error", "message": "stream disconnected\n  before completion"},
            {"type": "turn.failed", "error": {"message": refusal}},
        ]
        stream = "\n".join(json.dumps(event) for event in events)
        self.assertEqual(codex.last_error(stream), refusal)
        self.assertEqual(
            codex.last_error("\n".join(json.dumps(event) for event in events[:3])),
            "stream disconnected before completion",
        )

    def test_a_stream_without_an_error_has_none(self):
        events = [{"type": "turn.completed", "usage": {}}, {"type": "error"}, {"type": "turn.failed", "error": "text"}]
        stream = "not json\n[1]\n" + "\n".join(json.dumps(event) for event in events)
        self.assertIsNone(codex.last_error(stream))
        self.assertIsNone(codex.last_error(""))

    def test_a_long_error_is_cut_short(self):
        self.assertEqual(len(codex.last_error(json.dumps({"type": "error", "message": "x" * 1000}))), 300)


class PreflightTest(CodexTestCase):
    def test_targets_exclude_registry_locations(self):
        allowed, forbidden = codex.preflight_targets(self.boundary, self.environment)
        self.assertEqual(allowed, list(self.boundary.area_paths))
        self.assertIn(self.repo, forbidden)
        self.assertIn(self.repo / "src", forbidden)
        self.assertIn(self.repo / ".git", forbidden)
        self.assertIn(self.repo / "ledger", forbidden)
        self.assertNotIn(self.home / "Mandu", forbidden)

    def test_targets_include_the_directories_each_environment_names(self):
        sandbox_home = self.temp_dir / "empty-codex-home"
        sandbox_home.mkdir()
        sandbox_environment = dict(self.environment, CODEX_HOME=str(sandbox_home))
        _, forbidden = codex.preflight_targets(self.boundary, self.environment, sandbox_environment)
        for path in (self.home, self.temp_dir, self.home / ".codex", sandbox_home):
            self.assertEqual(forbidden.count(path), 1, path)

    def test_evaluate_outcomes(self):
        area, other_area, root, src = Path("/a"), Path("/b"), Path("/r"), Path("/r/src")
        output = "WROTE /a\nREFUSED /b\nREFUSED /r\nWROTE /r/src\n"
        result = codex.evaluate_preflight(output, "probe", [area, other_area], [root, src])
        self.assertEqual(result.allowed, (area,))
        self.assertEqual(result.refused, (root,))
        self.assertEqual(result.breaches, (src / "probe",))
        self.assertEqual(len(result.failures), 1)
        self.assertFalse(result.ok)
        silent = codex.evaluate_preflight("", "probe", [area], [root])
        self.assertEqual(len(silent.failures), 2)
        stale = codex.evaluate_preflight("WROTE /a\nEXISTS /r\n", "probe", [area], [root])
        self.assertFalse(stale.ok)

    def test_an_unenforced_sandbox_is_caught_and_its_sentinels_removed(self):
        self.install_fake_codex(FAKE_UNSANDBOXED_CODEX)
        result = codex.run_preflight(CODEX_CONFIG, self.boundary, self.codex_bin, self.environment, "t1")
        self.assertFalse(result.ok)
        self.assertIn(self.repo / "src" / ".gr0wthlab-preflight-t1", result.breaches)
        self.assertIn(self.temp_dir / ".gr0wthlab-preflight-t1", result.breaches)
        self.assertIn(self.home / ".codex" / ".gr0wthlab-preflight-t1", result.breaches)
        sandbox_home = boundary.canonical(Path((self.codex_bin.parent / "codex-home").read_text(encoding="utf-8")))
        self.assertNotEqual(sandbox_home, self.home / ".codex")
        self.assertIn(sandbox_home / ".gr0wthlab-preflight-t1", result.breaches)
        for path in result.breaches:
            self.assertFalse(path.exists())
        for path in self.boundary.area_paths:
            self.assertEqual(os.listdir(str(path)), [])

    def test_a_failing_sandbox_command_fails_the_preflight(self):
        self.install_fake_codex("#!/bin/sh\necho 'policy error' >&2\nexit 2\n")
        result = codex.run_preflight(CODEX_CONFIG, self.boundary, self.codex_bin, self.environment, "t2")
        self.assertFalse(result.ok)
        self.assertTrue(any("policy error" in failure for failure in result.failures))
        self.assertTrue(json.dumps(result.failures))

    def test_a_sandbox_probe_that_never_finishes_is_stopped_and_fails_the_preflight(self):
        self.install_fake_codex('#!/bin/sh\necho "WROTE $9"\nexec /bin/sleep 600\n')
        with mock.patch.object(process, "QUICK", 1):
            result = codex.run_preflight(CODEX_CONFIG, self.boundary, self.codex_bin, self.environment, "t3")
        self.assertFalse(result.ok)
        self.assertIn("codex sandbox did not finish within 1 s and was stopped", result.failures)

    def test_a_codex_that_never_answers_its_version_refuses_the_run(self):
        self.install_fake_codex("#!/bin/sh\nexec /bin/sleep 600\n")
        with mock.patch.object(process, "QUICK", 1), self.assertRaises(ConfigError) as refused:
            codex.codex_version(self.codex_bin, self.environment)
        self.assertIn("--version did not finish within 1 s", str(refused.exception))
        self.codex_bin.write_text("#!/bin/sh\necho 'no such option' >&2\nexit 64\n", encoding="utf-8")
        with self.assertRaises(ConfigError) as refused:
            codex.codex_version(self.codex_bin, self.environment)
        self.assertIn("--version exited 64: no such option", str(refused.exception))
        self.codex_bin.write_text("#!/bin/sh\necho 'codex-cli 1.2.3'\n", encoding="utf-8")
        self.assertEqual(codex.codex_version(self.codex_bin, self.environment), "codex-cli 1.2.3")


class NetworkProbeTest(unittest.TestCase):
    TARGETS = ["www.reddit.com:443", "itunes.apple.com:443", "forum.example.com:443"]

    def test_the_probe_s_output_is_read_target_by_target(self):
        output = "UNREACHABLE www.reddit.com:443 101\nREACHED itunes.apple.com:443 102\nnoise\nUNREACHABLE x 1 2\n"
        result = codex.evaluate_network(output, self.TARGETS)
        self.assertEqual(result.unreachable, (("www.reddit.com:443", 101),))
        self.assertEqual(result.reached, ("itunes.apple.com:443",))
        self.assertEqual(result.failures, ("forum.example.com:443 was not probed",))
        self.assertFalse(result.ok)
        self.assertEqual(result.as_json()["unreachable"], ["www.reddit.com:443"])

    def test_only_a_probe_that_tried_every_target_and_reached_none_passes(self):
        output = "".join(f"UNREACHABLE {target} {pid}\n" for pid, target in enumerate(self.TARGETS, 200))
        self.assertTrue(codex.evaluate_network(output, self.TARGETS).ok)
        self.assertFalse(codex.evaluate_network("", self.TARGETS).ok)
        self.assertTrue(codex.evaluate_network("", []).ok)

    def test_the_probe_tries_each_target_once_sending_nothing_and_names_the_process_that_tried(self):
        targets = ["open.example:443", "closed.example:8443"]
        with tempfile.TemporaryDirectory() as folder:
            # Stands in for nc: records how it was called and by which process, and opens only open.example.
            tool = Path(folder) / "nc"
            tool.write_text('#!/bin/sh\necho "$$ $*" >> "$0.calls"\n[ "$6" = open.example ]\n', encoding="utf-8")
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
            with mock.patch.object(codex, "NETCAT", str(tool)):
                result = codex.run_network_probe({}, None, tool, dict(os.environ), targets, sandboxed=False)
            calls = [line.split() for line in Path(f"{tool}.calls").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(result.reached, ("open.example:443",))
        self.assertEqual(result.failures, ())
        zero_io = ["-z", "-G", "3", "-w", "3"]
        self.assertEqual(
            [call[1:] for call in calls], [zero_io + ["open.example", "443"], zero_io + ["closed.example", "8443"]]
        )
        self.assertEqual(result.unreachable, (("closed.example:8443", int(calls[1][0])),))


if __name__ == "__main__":
    unittest.main()
