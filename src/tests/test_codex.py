"""The Codex command line, environment, fingerprint, and preflight evaluation."""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import boundary, codex
from gr0wthlab.boundary import ConfigError
from tests.test_boundary import CONFIG, REGISTRY

CODEX_CONFIG = dict(
    CONFIG,
    codex={
        "permission_profile": "gr0wthlab",
        "model": "model-a",
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

    def test_fingerprint_ignores_the_run_output_path_only(self):
        env = {"HOME": "/h"}
        other_config = dict(CODEX_CONFIG, codex=dict(CODEX_CONFIG["codex"], model="model-b"))
        first = codex.build_exec_command(CODEX_CONFIG, self.boundary, self.codex_bin, Path("/l/a.md"))
        second = codex.build_exec_command(CODEX_CONFIG, self.boundary, self.codex_bin, Path("/l/b.md"))
        other_model = codex.build_exec_command(other_config, self.boundary, self.codex_bin, Path("/l/a.md"))
        self.assertEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(second, env, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(other_model, env, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(first, {"HOME": "/x"}, "v1"))
        self.assertNotEqual(codex.fingerprint(first, env, "v1"), codex.fingerprint(first, env, "v2"))


class EnvironmentTest(CodexTestCase):
    def test_environment_is_built_from_scratch(self):
        env = codex.child_environment(self.home, self.codex_bin, "/tmp/user")
        self.assertEqual(set(env), {"HOME", "USER", "LOGNAME", "SHELL", "LANG", "TMPDIR", "PATH", "CODEX_HOME"})
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


if __name__ == "__main__":
    unittest.main()
