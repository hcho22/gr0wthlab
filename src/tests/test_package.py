"""The package snapshot: fingerprints, read times, changes since the previous snapshot, and failures."""

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gr0wthlab import package
from gr0wthlab.boundary import ConfigError

REPO = Path(__file__).resolve().parents[2]
CLOCK = "2026-10-11T23:00:00+00:00"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mandu = Path(self.tmp.name)
        self.write("p/gtm/angles.md", "angles v1\n")
        self.write("p/gtm/channels/plan.md", "plan\n")
        self.write("p/gtm/channels/schema.md", "schema\n")
        self.write("p/gtm/channels/.DS_Store", "x")
        self.sources = [
            package.Source("RepToday", "p/gtm/angles.md", ("post-drafts",)),
            package.Source("RepToday", "p/gtm/channels/", ("waitlist-counts",)),
        ]

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp.name):
            for name in dirs + files:
                os.chmod(os.path.join(root, name), 0o755)
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.mandu / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def take(self, previous=None):
        return package.take(self.mandu, self.sources, previous or {}, lambda: CLOCK)

    def files(self, results):
        return {file.path: file for result in results for file in result.files}

    def test_first_snapshot_reads_every_file_with_its_fingerprint_and_time(self):
        results = self.take()
        files = self.files(results)
        self.assertEqual(sorted(files), ["p/gtm/angles.md", "p/gtm/channels/plan.md", "p/gtm/channels/schema.md"])
        angles = files["p/gtm/angles.md"]
        self.assertEqual((angles.status, angles.change), (package.READ, "first read"))
        self.assertEqual(angles.sha256, sha("angles v1\n"))
        self.assertEqual((angles.bytes, angles.read_at), (10, CLOCK))
        self.assertEqual([result.status for result in results], [package.READ, package.READ])

    def test_changes_since_the_previous_snapshot(self):
        previous = package.last_known(
            {"products": {"RepToday": {"files": [f.as_json() for f in self.files(self.take()).values()]}}}
        )
        self.write("p/gtm/angles.md", "angles v2\n")
        self.write("p/gtm/channels/new.md", "new\n")
        (self.mandu / "p/gtm/channels/schema.md").unlink()
        results = self.take(previous)
        files = self.files(results)
        self.assertEqual(
            (files["p/gtm/angles.md"].status, files["p/gtm/angles.md"].change), (package.CHANGED, "changed")
        )
        self.assertEqual(files["p/gtm/angles.md"].previous_sha256, sha("angles v1\n"))
        self.assertEqual(files["p/gtm/channels/new.md"].change, "added")
        self.assertEqual(
            (files["p/gtm/channels/plan.md"].status, files["p/gtm/channels/plan.md"].change), (package.READ, None)
        )
        self.assertEqual(results[1].removed, ["p/gtm/channels/schema.md"])
        self.assertEqual([result.status for result in results], [package.CHANGED, package.CHANGED])
        record = package.record("RUN2", datetime(2026, 10, 11, tzinfo=timezone.utc), self.mandu, results, "RUN1")
        changes = record["products"]["RepToday"]["changes"]
        self.assertEqual(
            changes,
            {
                "added": ["p/gtm/channels/new.md"],
                "changed": ["p/gtm/angles.md"],
                "removed": ["p/gtm/channels/schema.md"],
            },
        )

    def test_a_missing_or_unreadable_source_fails_alone(self):
        (self.mandu / "p/gtm/angles.md").unlink()
        results = self.take()
        self.assertEqual(results[0].status, package.FAILED)
        self.assertEqual(results[0].failure(), "angles.md: missing")
        self.assertEqual(results[1].status, package.READ)
        self.write("p/gtm/angles.md", "angles\n")
        os.chmod(str(self.mandu / "p/gtm/channels/plan.md"), 0)
        if os.access(str(self.mandu / "p/gtm/channels/plan.md"), os.R_OK):
            self.skipTest("running as a user who can read any file")
        results = self.take()
        self.assertEqual(results[0].status, package.READ)
        self.assertEqual(results[1].status, package.FAILED)
        self.assertEqual(results[1].failure(), "plan.md: Permission denied")
        self.assertEqual(self.files(results)["p/gtm/channels/schema.md"].status, package.READ)

    def test_a_missing_or_empty_directory_fails(self):
        self.sources.append(package.Source("RepToday", "p/gtm/thesis/", ()))
        self.assertEqual(self.take()[2].reason, "missing")
        (self.mandu / "p/gtm/thesis").mkdir()
        self.assertEqual(self.take()[2].reason, "holds no files")

    def snapshot(self, results):
        return package.last_known(
            package.record("RUN", datetime(2026, 10, 11, tzinfo=timezone.utc), self.mandu, results, None)
        )

    def test_a_failed_directory_keeps_its_files_fingerprints_and_removes_none(self):
        first = self.snapshot(self.take())
        channels = self.mandu / "p/gtm/channels"
        channels.rename(self.mandu / "p/gtm/elsewhere")
        missing = self.take(first)
        self.assertEqual((missing[1].reason, missing[1].removed, missing[1].files), ("missing", [], []))
        second = self.snapshot(missing)
        self.assertEqual(second, first)
        (self.mandu / "p/gtm/elsewhere").rename(channels)
        back = self.take(second)
        self.assertEqual(
            {path: (file.status, file.change) for path, file in self.files(back).items()},
            dict.fromkeys(
                ["p/gtm/angles.md", "p/gtm/channels/plan.md", "p/gtm/channels/schema.md"], (package.READ, None)
            ),
        )
        self.assertEqual(back[1].removed, [])

    def test_an_unreadable_folder_fails_with_its_reason(self):
        first = self.snapshot(self.take())
        self.write("p/gtm/channels/sub/deep.md", "deep\n")
        os.chmod(str(self.mandu / "p/gtm/channels/sub"), 0)
        if os.access(str(self.mandu / "p/gtm/channels/sub"), os.R_OK):
            self.skipTest("running as a user who can read any folder")
        results = self.take(first)
        self.assertEqual((results[1].reason, results[1].removed), ("Permission denied", []))
        self.assertEqual(self.snapshot(results), first)

    def test_a_folder_that_cannot_be_searched_fails_its_sources_with_the_reason(self):
        first = self.snapshot(self.take())
        os.chmod(str(self.mandu / "p/gtm"), 0o600)
        if os.access(str(self.mandu / "p/gtm/angles.md"), os.F_OK):
            self.skipTest("running as a user who can search any folder")
        results = self.take(first)
        self.assertEqual(results[0].failure(), "angles.md: Permission denied")
        self.assertEqual((results[1].reason, results[1].removed), ("Permission denied", []))

    def test_the_last_known_fingerprint_carries_through_a_failed_read(self):
        snapshot = {
            "products": {
                "RepToday": {
                    "files": [
                        {"path": "a.md", "status": "failed", "previous_sha256": "abc"},
                        {"path": "b.md", "status": "read", "sha256": "def"},
                        {"path": "c.md", "status": "failed"},
                    ]
                }
            }
        }
        self.assertEqual(package.last_known(snapshot), {"a.md": "abc", "b.md": "def", "c.md": ""})

    def test_latest_snapshot_is_the_newest_before_this_run(self):
        directory = self.mandu / "snapshots"
        directory.mkdir()
        for run in ("20261004T230000Z-scheduled-aaaa", "20261011T230000Z-scheduled-bbbb"):
            (directory / f"{run}.json").write_text(json.dumps({"run": run}), encoding="utf-8")
        latest = package.latest_snapshot(directory, "20261011T230000Z-scheduled-bbbb")
        self.assertEqual(latest[0], "20261004T230000Z-scheduled-aaaa")
        self.assertIsNone(package.latest_snapshot(directory, "20261001T000000Z-on-demand-cccc"))


class SourcesTest(unittest.TestCase):
    def test_the_registry_lists_the_prd_sources_for_active_products_only(self):
        registry = json.loads((REPO / "config/products.json").read_text(encoding="utf-8"))
        sources = package.package_sources(registry)
        self.assertEqual({source.product for source in sources}, {"RepToday"})
        names = [source.path.rstrip("/").rsplit("/", 1)[-1] for source in sources]
        for expected in (
            "cadence-14-day.md",
            "angles.md",
            "ab-pairs.md",
            "platform-assignment.md",
            "read-the-results.md",
            "brand-guidelines.md",
            "brand-rules.json",
            "pre-publication-checklist.md",
            "06-channels",
            "07-thesis",
            "02-marketing-launch-checklist_260807.md",
            "BUILD-SPEC.md",
        ):
            self.assertIn(expected, names)
        self.assertTrue(all(source.path.startswith("projects/RepToday/") for source in sources))

    def test_paths_must_stay_inside_mandu(self):
        for path in ("/etc/passwd", "../outside.md", "projects/../../x", ""):
            registry = {
                "products": [{"name": "P", "status": "active", "go_to_market_package": {"sources": [{"path": path}]}}]
            }
            with self.subTest(path=path), self.assertRaises(ConfigError):
                package.package_sources(registry)


if __name__ == "__main__":
    unittest.main()
