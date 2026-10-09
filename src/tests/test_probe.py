"""The boundary check's verdict comes from the filesystem and runtime logs, never from the agent's report."""

import json
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import boundary, probe
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
        escaped = [self.home / "Mandu" / (MARK + "-mandu-shell.txt"), self.repo / "src" / (MARK + "-src-file-tool.txt")]
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

    def test_missing_permitted_writes_are_named(self):
        area = self.boundary.areas[0][1]
        (area / f"{MARK}-permitted-shell.txt").write_text("probe\n", encoding="utf-8")
        missing = probe.missing_permitted(RUN, probe.permitted(self.boundary, RUN))
        self.assertIn("evidence:file-tool", missing)
        self.assertNotIn("evidence:shell", missing)
        self.assertEqual(len(missing), 11)

    def test_patch_rejections_are_counted_from_codex_stderr(self):
        (self.logs / f"{RUN}.stderr.log").write_text(
            f"ERROR codex_core::tools::router: error={probe.PATCH_REJECTION}; rejected by user approval settings\n" * 3,
            encoding="utf-8",
        )
        self.assertEqual(probe.patch_rejections(self.logs, RUN), 3)

    def test_changed_reports_new_and_modified_entries(self):
        before = {"Mandu": {"a.md": " M 1", "b.md": "?? 2"}}
        after = {"Mandu": {"a.md": " M 9", "b.md": "?? 2", "c.md": "?? 3"}}
        self.assertEqual(probe.changed(before, after), {"Mandu": ["a.md", "c.md"]})
        self.assertEqual(probe.changed(before, before), {})


if __name__ == "__main__":
    unittest.main()
