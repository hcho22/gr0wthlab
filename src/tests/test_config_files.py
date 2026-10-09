"""The committed configuration: the Product registry parses and the runtime grants writes only to the six areas."""

import json
import re
import unittest
from pathlib import Path

from gr0wthlab import boundary

REPO = Path(__file__).resolve().parents[2]
HOME = Path("/Users/founder")


def load(relative):
    with (REPO / relative).open(encoding="utf-8") as handle:
        return json.load(handle)


class ProductRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = load("config/products.json")

    def test_every_location_is_read_only_with_an_override(self):
        locations = [self.registry["mandu"]] + [p["repository"] for p in self.registry["products"]]
        for location in locations:
            self.assertEqual(location["access"], "read-only")
            self.assertRegex(location["env"], r"^GR0WTHLAB_[A-Z]+_DIR$")
            self.assertTrue(location["local_checkout"].startswith("~/"))

    def test_products_and_gates(self):
        products = {p["name"]: p for p in self.registry["products"]}
        self.assertEqual(products["RepToday"]["status"], "active")
        self.assertEqual(products["Immerse"]["status"], "listening-only")
        self.assertEqual(products["Immerse"]["gate"], {"story": "US-ME18"})

    def test_locations_resolve_against_home_and_overrides(self):
        env = {"GR0WTHLAB_REPTODAY_DIR": "/srv/RepToday"}
        locations = {loc.label: loc.path for loc in boundary.registry_locations(self.registry, env, HOME)}
        self.assertEqual(locations["Mandu"], HOME / "Mandu")
        self.assertEqual(locations["RepToday"], Path("/srv/RepToday"))
        self.assertEqual(locations["Immerse"], HOME / "Developer/FM_Private/firstmate-private/projects/Immerse")


class RuntimeConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = load("config/guardrails/runtime.json")

    def test_runtime_is_codex(self):
        self.assertEqual(self.config["runtime"], "codex")

    def test_areas_are_the_readme_writable_areas(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        writable = set(re.findall(r"^\| \[`(workspace/[a-z-]+)/`\]\([^)]*\) \| [^|]+ \| Yes \|$", readme, re.M))
        self.assertEqual(writable, set(self.config["writable_areas"].values()))
        self.assertEqual(len(writable), 6)
        for area in writable:
            self.assertTrue((REPO / area / "README.md").is_file(), area)

    def test_the_real_configuration_writes_only_in_the_areas(self):
        registry = load("config/products.json")
        resolved = boundary.resolve_boundary(REPO, self.config, registry, {}, HOME, git=[REPO / ".git"])
        policy = boundary.filesystem_policy(resolved)
        writes = sorted(path for path, access in policy.items() if access == "write")
        self.assertEqual(writes, sorted(str(path) for path in resolved.area_paths))
        self.assertEqual(policy[":root"], "deny")
        self.assertEqual(policy[":slash_tmp"], "deny")
        self.assertEqual(policy["/private/var/tmp"], "deny")
        self.assertEqual(policy[str(resolved.repo_root)], "read")
        self.assertEqual(policy[str(HOME / "Mandu")], "read")

    def test_features_that_act_outside_the_sandbox_are_disabled(self):
        disabled = set(self.config["codex"]["disabled_features"])
        for feature in ("apps", "plugins", "hooks", "browser_use", "computer_use", "multi_agent", "multi_agent_v2"):
            self.assertIn(feature, disabled)
        self.assertIs(self.config["codex"]["sub_agents"], False)
        self.assertEqual(
            self.config["codex"]["session_flags"], ["--ignore-user-config", "--ignore-rules", "--ephemeral"]
        )


if __name__ == "__main__":
    unittest.main()
