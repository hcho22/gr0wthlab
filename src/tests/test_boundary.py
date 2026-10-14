"""The boundary resolver fails closed on any configuration that could widen writes."""

import copy
import json
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
    "network": False,
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


class BoundaryTestCase(unittest.TestCase):
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


class ResolveBoundaryTest(BoundaryTestCase):
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

    def test_rejects_an_area_that_is_a_link_or_a_file(self):
        outside = self.root / "outside"
        outside.mkdir()
        area = self.repo / "workspace" / "evidence"
        area.parent.mkdir()
        area.symlink_to(outside)
        with self.assertRaisesRegex(ConfigError, "evidence .* must be a real folder"):
            self.resolve()
        area.unlink()
        area.write_text("not a folder", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "evidence .* must be a real folder"):
            self.resolve()
        area.unlink()
        area.mkdir()
        self.assertEqual(dict(self.resolve().areas)["evidence"], area)

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

    def test_rejects_network_unless_it_is_off(self):
        for value in (True, None, "false"):
            config = copy.deepcopy(CONFIG)
            config["network"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ConfigError, "network must be false"):
                self.resolve(config)

    def test_rejects_a_runtime_other_than_codex(self):
        path = self.repo / boundary.RUNTIME_CONFIG
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(dict(CONFIG, runtime="claude-code")), encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "runtime must be 'codex'"):
            boundary.load_runtime_config(self.repo)

    def test_refuses_an_unknown_or_missing_reasoning_effort_when_the_configuration_loads(self):
        path = self.repo / boundary.RUNTIME_CONFIG
        path.parent.mkdir(parents=True)

        def load(codex):
            path.write_text(json.dumps(dict(CONFIG, codex=codex)), encoding="utf-8")
            return boundary.load_runtime_config(self.repo)

        for effort in boundary.REASONING_EFFORTS:
            with self.subTest(effort=effort):
                self.assertEqual(load({"reasoning_effort": effort})["codex"]["reasoning_effort"], effort)
        unknown = ("hgih", "High", "", " high", "minimal", None, True, 3, ["high"])
        for codex in [{"reasoning_effort": value} for value in unknown] + [{}, None, "high"]:
            with (
                self.subTest(codex=codex),
                self.assertRaisesRegex(
                    ConfigError, r"codex\.reasoning_effort must be one of low, medium, high, xhigh, max; got "
                ),
            ):
                load(codex)

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
        self.assertEqual(policy[str(self.home / "RepToday")], "read")
        writes = {path for path, access in policy.items() if access == "write"}
        self.assertEqual(writes, {str(path) for path in resolved.area_paths})

    def test_policy_grants_of_mandu_only_the_package_paths_the_registry_names(self):
        mandu = self.home / "Mandu"
        self.assertNotIn(str(mandu), boundary.filesystem_policy(self.resolve()))
        resolved = self.resolve(registry=FILMING_REGISTRY)
        policy = boundary.filesystem_policy(resolved)
        package = [mandu / "projects/RepToday/gtm", mandu / "projects/RepToday/02-launch-checklist.md"]
        self.assertEqual(list(resolved.package_paths), package)
        granted = {Path(path) for path, access in policy.items() if not path.startswith(":") and access == "read"}
        self.assertEqual({path for path in granted if boundary.is_within(path, mandu)}, set(package))
        for unread in (mandu, mandu / ".git", mandu / "projects", mandu / "projects/RepToday", FOOTAGE / "window-1"):
            with self.subTest(unread=unread):
                self.assertFalse(any(boundary.is_within(self.home / unread, path) for path in granted))
        # The rule on raw footage is judged on that very table.
        self.assertEqual(boundary.read_grants(resolved), [Path(path) for path in policy if not path.startswith(":")])

    def test_a_package_path_must_stay_inside_the_mandu_checkout(self):
        def named(**package):
            registry = copy.deepcopy(FILMING_REGISTRY)
            registry["products"][0]["go_to_market_package"].update(package)
            return registry

        for path in ("/etc", "../RepToday", "projects/../..", "", ".", 7, ["projects"]):
            for registry in (named(path=path), named(launch_checklist=path), named(sources=[{"path": path}])):
                with (
                    self.subTest(path=path),
                    self.assertRaisesRegex(ConfigError, "must be relative to the Mandu checkout"),
                ):
                    self.resolve(registry=registry)
        with self.assertRaisesRegex(ConfigError, "must be relative to the Mandu checkout"):
            self.resolve(registry=named(sources=["projects/RepToday/gtm/"]))
        # A link in the checkout cannot take a grant out of it.
        (self.home / "Mandu" / "projects").mkdir(parents=True)
        (self.home / "Mandu" / "projects" / "RepToday").symlink_to(self.home)
        with self.assertRaisesRegex(ConfigError, "is not inside the Mandu checkout"):
            self.resolve(registry=FILMING_REGISTRY)


FOOTAGE = Path("Mandu/projects/RepToday")
FILMING_REGISTRY = {
    "mandu": REGISTRY["mandu"],
    "products": [
        {
            "name": "RepToday",
            "status": "active",
            "repository": REGISTRY["products"][0]["repository"],
            "go_to_market_package": {
                "path": "projects/RepToday/gtm/",
                "launch_checklist": "projects/RepToday/02-launch-checklist.md",
                "sources": [
                    {"path": "projects/RepToday/gtm/05-social-pmf/angles.md"},
                    {"path": "projects/RepToday/02-launch-checklist.md"},
                    {"path": "projects/RepToday/gtm/06-channels/"},
                ],
            },
            "filming": {"footage": {"local_path": None, "env": "GR0WTHLAB_FOOTAGE_DIR", "access": "read-only"}},
        }
    ],
}


class FootagePlaceTest(BoundaryTestCase):
    """The one rule of where raw footage may be: the sandbox reads nothing in a footage folder."""

    def place(self, path, registry=FILMING_REGISTRY, **block):
        registry = copy.deepcopy(registry)
        registry["products"][0]["filming"]["footage"].update(block)
        env = {"GR0WTHLAB_FOOTAGE_DIR": str(path)} if path else {}
        return self.resolve(registry=registry, env=env, git=[self.repo / ".git", self.root / "primary" / ".git"])

    def test_the_founders_place_inside_mandu_beside_the_package_is_accepted(self):
        resolved = self.place(None, local_path="~/Mandu/projects/RepToday")
        self.assertEqual(
            resolved.footage, boundary.FootagePlace("RepToday", self.home / FOOTAGE, "GR0WTHLAB_FOOTAGE_DIR")
        )
        policy = boundary.filesystem_policy(resolved)
        for number in (1, 2, 14, 100):
            folder = self.home / FOOTAGE / f"window-{number}"
            with self.subTest(folder=folder):
                self.assertTrue(boundary.FOOTAGE_FOLDER.fullmatch(folder.name))
                granted = [Path(path) for path in policy if not path.startswith(":") and policy[path] != "deny"]
                self.assertFalse(
                    any(boundary.is_within(folder, path) or boundary.is_within(path, folder) for path in granted)
                )

    def test_a_place_outside_everything_the_run_reads_is_accepted_as_before(self):
        for outside in (self.root / "footage", self.home / "Movies" / "gr0wthlab-footage", self.home / "Mandu-footage"):
            with self.subTest(place=outside):
                self.assertEqual(self.place(outside).footage.path, outside)
        # Elsewhere in Mandu, where the sandbox reads nothing, and Mandu itself: no grant is in a footage folder.
        for inside in (self.home / "Mandu" / "footage", self.home / "Mandu" / "projects", self.home / "Mandu"):
            with self.subTest(place=inside):
                self.assertEqual(self.place(inside).footage.path, inside)

    def test_a_place_the_sandbox_can_read_is_refused(self):
        mandu = self.home / "Mandu"
        for readable in (
            self.repo,
            self.repo / "workspace" / "drafts" / "footage",
            self.repo / "ledger" / "assets",
            self.repo / ".git" / "footage",
            self.root / "primary" / ".git",
            self.home / "RepToday" / "footage",
            mandu / "projects/RepToday/gtm",
            mandu / "projects/RepToday/gtm/footage",
            mandu / "projects/RepToday/02-launch-checklist.md",
            # The Mac's volume takes a name in any case, so the rule does too.
            mandu / "Projects/reptoday/GTM/footage",
            Path(str(self.repo).upper()) / "footage",
        ):
            with (
                self.subTest(place=readable),
                self.assertRaisesRegex(
                    ConfigError,
                    r"RepToday's footage place \S+ is inside \S+, which the sandboxed agent can read, so the agent"
                    " could open the raw footage",
                ),
            ):
                self.place(readable)

    def test_only_a_place_inside_mandu_may_hold_anything_the_run_reads(self):
        for holding in (self.root, self.home, self.repo.parent, self.root / "primary"):
            with (
                self.subTest(place=holding),
                self.assertRaisesRegex(
                    ConfigError,
                    r"RepToday's footage place \S+ holds \S+, which the sandboxed agent can read; only a place inside"
                    " the Mandu checkout may hold anything the run reads",
                ),
            ):
                self.place(holding)

    def test_a_grant_in_a_footage_folder_is_refused(self):
        for granted, folder in (
            ("projects/RepToday/window-1/", "window-1"),
            ("projects/RepToday/window-2/kit/notes.md", "window-2"),
            ("projects/RepToday/Window-14", "window-14"),
        ):
            registry = copy.deepcopy(FILMING_REGISTRY)
            registry["products"][0]["go_to_market_package"]["sources"].append({"path": granted})
            with (
                self.subTest(granted=granted),
                self.assertRaisesRegex(
                    ConfigError,
                    rf"RepToday's footage place \S+ is refused: the sandboxed agent can read \S+, which is in its"
                    rf" footage folder {folder}/, so the agent could open the raw footage",
                ),
            ):
                self.place(self.home / FOOTAGE, registry)
        # The same paths are no footage folder of a place elsewhere.
        registry["products"][0]["go_to_market_package"]["sources"].append({"path": "projects/RepToday/window-1/"})
        self.assertEqual(self.place(self.root / "footage", registry).footage.path, self.root / "footage")

    def test_the_place_is_declared_read_only_with_an_override_name_and_stays_unset_until_set(self):
        self.assertIsNone(self.resolve().footage)
        self.assertEqual(self.place(None).footage, boundary.FootagePlace("RepToday", None, "GR0WTHLAB_FOOTAGE_DIR"))
        self.assertEqual(
            self.place(None, local_path="~/Movies/gr0wthlab-footage").footage.path,
            self.home / "Movies/gr0wthlab-footage",
        )
        with self.assertRaisesRegex(ConfigError, "must be declared read-only"):
            self.place(self.root / "footage", access="read-write")
        with self.assertRaisesRegex(ConfigError, "needs an env override name"):
            self.place(self.root / "footage", env="")
        with self.assertRaisesRegex(ConfigError, "must start with ~/ or be absolute"):
            self.place(None, local_path="Movies/footage")
        with self.assertRaisesRegex(ConfigError, "GR0WTHLAB_FOOTAGE_DIR must be an absolute path"):
            self.resolve(registry=FILMING_REGISTRY, env={"GR0WTHLAB_FOOTAGE_DIR": "footage"})
        two = copy.deepcopy(FILMING_REGISTRY)
        two["products"].append(dict(two["products"][0], name="Immerse"))
        with self.assertRaisesRegex(ConfigError, "only one Product may film"):
            self.resolve(registry=two)

    def test_the_folders_no_run_may_read_are_the_place_and_each_footage_folder_in_it(self):
        place = self.home / FOOTAGE
        self.assertEqual(boundary.footage_dirs(self.resolve()), {})
        self.assertEqual(boundary.footage_dirs(self.place(None)), {})
        self.assertEqual(boundary.footage_dirs(self.place(place)), {})
        for name in ("gtm", "window-2", "window-1", "Window-10", "window-x", "windows-3", "window-4.bak"):
            (place / name).mkdir(parents=True)
        (place / "window-5").write_text("a file", encoding="utf-8")
        (place / "window-6").symlink_to(place / "gtm")
        (place / "window-1" / "window-7").mkdir()
        (place / "window-1" / "d01-s1.mov").write_text("stand-in", encoding="utf-8")
        self.assertEqual(
            boundary.footage_dirs(self.place(place)),
            {
                "footage-place": place,
                "footage-Window-10": place / "Window-10",
                "footage-window-1": place / "window-1",
                "footage-window-2": place / "window-2",
            },
        )


if __name__ == "__main__":
    unittest.main()
