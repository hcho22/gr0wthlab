"""The boundary check's verdict comes from the filesystem and runtime logs, never from the agent's report."""

import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import boundary, probe
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY

RUN = "20261009T000000Z-on-demand-abcd"
MARK = probe.PREFIX + RUN


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.repo = root / "home" / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        (self.repo / "src").mkdir()
        (self.repo / "ledger").mkdir()
        (self.home / "Mandu").mkdir(parents=True)
        self.logs = root / "logs"
        self.logs.mkdir()
        self.boundary = boundary.resolve_boundary(self.repo, CONFIG, REGISTRY, {}, self.home, git=[self.repo / ".git"])

    @property
    def home(self):
        return Path(self.tmp.name).resolve() / "home"

    def tearDown(self):
        self.tmp.cleanup()

    def write_record(self, **fields):
        (self.logs / f"{RUN}.json").write_text(json.dumps(dict(run_id=RUN, **fields)), encoding="utf-8")

    def write_permitted(self):
        for _, path in self.boundary.areas:
            for tool in probe.PERMITTED_TOOLS:
                (path / f"{MARK}-permitted-{tool}.txt").write_text("probe\n", encoding="utf-8")

    def test_an_escaped_sentinel_fails_the_check_and_is_removed(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        escaped = [
            self.home / "Mandu" / (MARK + "-mandu-shell.txt"),
            self.repo / "src" / (MARK + "-src-file-tool.txt"),
            self.repo / "ledger" / (MARK + "-ledger-shell.txt"),
        ]
        for path in escaped:
            path.write_text("probe\n", encoding="utf-8")
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertFalse(result["passed"])
        self.assertEqual(sorted(result["escaped_and_removed"]), sorted(str(path) for path in escaped))
        for path in escaped:
            self.assertFalse(path.exists())

    def test_permitted_files_are_counted_then_removed(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        (self.repo / "workspace/run-reports" / (MARK + "-report.md")).write_text("report\n", encoding="utf-8")
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertEqual(result["permitted_missing"], [])
        self.assertEqual((self.logs / (MARK + "-report.md")).read_text(encoding="utf-8"), "report\n")
        self.assertEqual(result["agent_report"], str(self.logs / (MARK + "-report.md")))
        for _, path in self.boundary.areas:
            self.assertEqual(list(path.iterdir()), [])

    def test_no_evidence_of_refused_attempts_fails_the_check(self):
        # A run that never attempted the forbidden writes leaves nothing behind but proves nothing.
        self.write_record(exit_code=0)
        self.write_permitted()
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertFalse(result["passed"])
        self.assertEqual(result["shell_targets_without_kernel_denial"], list(probe.PROBE_TARGETS))
        self.assertEqual(result["codex_patch_rejections"], 0)

    def test_verify_without_a_snapshot_says_the_snapshot_was_not_checked(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertIsNone(result["changed_outside_areas"])
        self.assertIsNone(result["local_listeners"])
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("changes outside the areas: not checked", out.getvalue())
        self.assertIn("local connections: not checked", out.getvalue())

    def test_a_connection_to_a_local_listener_fails_the_check(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        with probe.local_listeners() as listeners:
            unix, tcp = listeners
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(unix.address)
            host, port = tcp.address.rsplit(":", 1)
            with socket.create_connection((host, int(port))):
                pass
            result = probe.verify(self.boundary, RUN, self.logs, listeners=listeners)
        self.assertFalse(result["passed"])
        connections = {label: entry["connections"] for label, entry in result["local_listeners"].items()}
        self.assertEqual(connections, {"unix-socket": 1, "localhost-tcp": 1})
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("local connections that got through: unix-socket, localhost-tcp", out.getvalue())

    def test_an_unreached_listener_still_needs_a_kernel_denial(self):
        # No connection arrived, but without the kernel's denial the run may simply never have tried.
        self.write_record(exit_code=0)
        self.write_permitted()
        with probe.local_listeners() as listeners:
            result = probe.verify(self.boundary, RUN, self.logs, listeners=listeners)
        self.assertEqual(result["local_listeners"]["unix-socket"]["connections"], 0)
        self.assertEqual(result["shell_targets_without_kernel_denial"][-2:], ["unix-socket", "localhost-tcp"])
        self.assertFalse(result["passed"])

    def test_a_listener_matches_only_the_kernel_denial_of_its_own_endpoint(self):
        with probe.local_listeners() as (unix, tcp):
            port = tcp.address.rsplit(":", 1)[1]
            self.assertTrue(tcp.refused_in(f"Sandbox: nc(41405) deny(1) network-outbound remote:*:{port}"))
            self.assertFalse(tcp.refused_in(f"Sandbox: nc(41405) deny(1) network-outbound remote:*:{port}0"))
            self.assertTrue(unix.refused_in(f"Sandbox: nc(41404) deny(1) network-outbound {unix.address}"))
            self.assertFalse(unix.refused_in(f"Sandbox: nc(41404) deny(1) file-read-data {unix.address}"))

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_area_that_cannot_be_listed_is_reported_not_fatal(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        area = dict(self.boundary.areas)["drafts"]
        area.chmod(0)
        try:
            result = probe.verify(self.boundary, RUN, self.logs)
        finally:
            area.chmod(0o755)
        self.assertEqual(result["unlistable_areas"], {"drafts": "Permission denied"})
        self.assertFalse(result["passed"])
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("areas that could not be listed: drafts (Permission denied)", out.getvalue())

    def test_missing_permitted_writes_are_named(self):
        area = self.boundary.areas[0][1]
        (area / f"{MARK}-permitted-shell.txt").write_text("probe\n", encoding="utf-8")
        missing = probe.missing_permitted(RUN, probe.permitted(self.boundary, RUN)[0])
        self.assertIn("evidence:file-tool", missing)
        self.assertNotIn("evidence:shell", missing)
        self.assertEqual(len(missing), 11)

    def test_patch_rejections_are_counted_from_codex_stderr(self):
        (self.logs / f"{RUN}.stderr.log").write_text(
            f"ERROR codex_core::tools::router: error={probe.PATCH_REJECTION}; rejected by user approval settings\n" * 3,
            encoding="utf-8",
        )
        self.assertEqual(probe.patch_rejections(self.logs, RUN), 3)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_changed_file_is_marked_and_changes_are_still_seen(self):
        fakes.git(self.repo, "init", "--quiet")
        locked = self.repo / "workspace/drafts/locked.md"
        locked.write_text("kept from me\n", encoding="utf-8")
        locked.chmod(0)
        before = {"repository": probe.snapshot(self.repo)}
        self.assertEqual(before["repository"]["workspace/drafts/locked.md"], "?? unreadable")
        (self.repo / "workspace/drafts/new.md").write_text("new\n", encoding="utf-8")
        after = {"repository": probe.snapshot(self.repo)}
        self.assertEqual(probe.changed(before, after), {"repository": ["workspace/drafts/new.md"]})

    def test_changed_reports_new_and_modified_entries(self):
        before = {"Mandu": {"a.md": " M 1", "b.md": "?? 2"}}
        after = {"Mandu": {"a.md": " M 9", "b.md": "?? 2", "c.md": "?? 3"}}
        self.assertEqual(probe.changed(before, after), {"Mandu": ["a.md", "c.md"]})
        self.assertEqual(probe.changed(before, before), {})


if __name__ == "__main__":
    unittest.main()
