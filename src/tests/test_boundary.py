"""The boundary resolver fails closed on any configuration that could widen writes."""

import copy
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import boundary
from gr0wthlab.boundary import ConfigError

AREAS = {
    "evidence": "workspace/evidence",
    "drafts": "workspace/drafts",
    "review_queue": "workspace/review-queue",
    "weekly_reads": "workspace/weekly-reads",
    "run_reports": "workspace/run-reports",
    "instructions": "workspace/instructions",
}
CONFIG = {
    "runtime": "codex",
    "working_directory": "workspace",
    "writable_areas": AREAS,
    "filesystem": {
        "default": "deny",
        "read_repository": True,
        "read_registry_locations": True,
        "read_system": [":minimal"],
        "deny": [":slash_tmp"],
    },
    "network": True,
}
REGISTRY = {
    "mandu": {"local_checkout": "~/Mandu", "env": "GR0WTHLAB_MANDU_DIR", "access": "read-only"},
    "products": [
        {
            "name": "RepToday",
            "repository": {"local_checkout": "~/RepToday", "env": "GR0WTHLAB_REPTODAY_DIR", "access": "read-only"},
        }
    ],
}


class ResolveBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "home" / "gr0wthlab"
        self.home = self.root / "home"
        self.repo.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def resolve(self, config=CONFIG, registry=REGISTRY, env=None, git=None):
        return boundary.resolve_boundary(
            self.repo, config, registry, env or {}, self.home, git=git if git is not None else [self.repo / ".git"]
        )

    def with_area(self, key, value):
        config = copy.deepcopy(CONFIG)
        config["writable_areas"][key] = value
        return config

    def test_resolves_six_areas_under_workspace(self):
        resolved = self.resolve()
        self.assertEqual([key for key, _ in resolved.areas], list(boundary.REQUIRED_AREAS))
        for _, path in resolved.areas:
            self.assertEqual(path.parent, self.repo / "workspace")
        self.assertEqual(resolved.working_directory, self.repo / "workspace")

    def test_rejects_a_missing_or_extra_area(self):
        config = copy.deepcopy(CONFIG)
        del config["writable_areas"]["drafts"]
        with self.assertRaises(ConfigError):
            self.resolve(config)
        with self.assertRaises(ConfigError):
            self.resolve(self.with_area("scratch", "workspace/scratch"))

    def test_rejects_areas_outside_workspace(self):
        for value in (
            "src",
            "config/guardrails",
            "workspace",
            "workspace/drafts/nested",
            "workspace/../src",
            "/tmp/drafts",
            "",
            ".",
        ):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                self.resolve(self.with_area("drafts", value))

    def test_rejects_duplicate_areas(self):
        with self.assertRaises(ConfigError):
            self.resolve(self.with_area("drafts", "workspace/evidence"))

    def test_rejects_a_working_directory_outside_the_repository(self):
        config = copy.deepcopy(CONFIG)
        config["working_directory"] = ".."
        with self.assertRaises(ConfigError):
            self.resolve(config)

    def test_rejects_a_filesystem_default_other_than_deny(self):
        config = copy.deepcopy(CONFIG)
        config["filesystem"]["default"] = "read"
        with self.assertRaises(ConfigError):
            self.resolve(config)

    def test_rejects_a_system_entry_that_covers_an_area(self):
        config = copy.deepcopy(CONFIG)
        config["filesystem"]["read_system"] = [str(self.root)]
        with self.assertRaises(ConfigError):
            self.resolve(config)

    def test_rejects_a_registry_location_overlapping_the_repository(self):
        for override in (str(self.home), str(self.repo), str(self.repo / "workspace" / "drafts")):
            with self.subTest(override=override), self.assertRaises(ConfigError):
                self.resolve(env={"GR0WTHLAB_MANDU_DIR": override})

    def test_rejects_a_relative_override(self):
        with self.assertRaises(ConfigError):
            self.resolve(env={"GR0WTHLAB_MANDU_DIR": "Mandu"})

    def test_rejects_a_registry_location_not_declared_read_only(self):
        registry = copy.deepcopy(REGISTRY)
        registry["products"][0]["repository"]["access"] = "read-write"
        with self.assertRaises(ConfigError):
            self.resolve(registry=registry)

    def test_rejects_a_runtime_other_than_codex(self):
        with self.assertRaises(ConfigError):
            boundary.load_runtime_config(self.repo)

    def test_policy_grants_writes_only_to_areas(self):
        external_git = self.root / "primary" / ".git"
        resolved = self.resolve(git=[self.repo / ".git", external_git])
        policy = boundary.filesystem_policy(resolved)
        self.assertEqual(list(policy)[0], ":root")
        self.assertEqual(policy[":root"], "deny")
        self.assertEqual(policy[":slash_tmp"], "deny")
        self.assertEqual(policy[str(self.repo)], "read")
        self.assertEqual(policy[str(external_git)], "read")
        self.assertNotIn(str(self.repo / ".git"), policy)
        self.assertEqual(policy[str(self.home / "Mandu")], "read")
        self.assertEqual(policy[str(self.home / "RepToday")], "read")
        writes = {path for path, access in policy.items() if access == "write"}
        self.assertEqual(writes, {str(path) for path in resolved.area_paths})


if __name__ == "__main__":
    unittest.main()
