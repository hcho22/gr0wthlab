"""The committed configuration: the Product registry parses and the runtime grants writes only to the six areas."""

import json
import unittest
from pathlib import Path

from gr0wthlab import boundary, sessions

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


class RunConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = load("config/run.json")
        self.registry = load("config/products.json")

    def test_every_package_source_and_unconnected_source_feeds_a_known_output(self):
        outputs = set(self.config["outputs"])
        reptoday = next(p for p in self.registry["products"] if p["name"] == "RepToday")
        sources = reptoday["go_to_market_package"]["sources"]
        self.assertEqual(len(sources), 14)
        for source in sources + self.config["sources_not_connected"]:
            self.assertLessEqual(set(source["needed_by"]), outputs, source)

    def test_every_kit_role_is_a_snapshotted_package_source(self):
        from gr0wthlab import posts

        product, roles = posts.kit_config(self.registry)
        self.assertEqual(product, "RepToday")
        self.assertEqual(sorted(role for role in roles if role != "note"), sorted(posts.ROLES))

    def test_the_window_waits_for_the_founder(self):
        window = self.config["window"]
        self.assertEqual((window["number"], window["first_sitting"], window["slot"]), (1, None, None))
        self.assertTrue(self.config["outputs"]["post-drafts"]["built"])
        self.assertNotIn("RepToday repository", [source["name"] for source in self.config["sources_not_connected"]])

    def test_the_platform_facts_name_both_test_platforms(self):
        from gr0wthlab import lint

        platforms = lint.load_platforms(load("config/platforms.json"))
        self.assertEqual(sorted(platforms), ["TikTok", "YouTube Shorts"])
        self.assertEqual(platforms["TikTok"].max_hashtags, 5)
        self.assertEqual(platforms["YouTube Shorts"].hashtags_void_above, 15)
        caption = platforms["TikTok"].field("body")
        self.assertEqual((caption.name, caption.max_chars, caption.visible_chars), ("Caption", 4000, 150))
        title = platforms["YouTube Shorts"].field("title")
        self.assertEqual((title.name, title.max_chars, title.visible_chars), ("Title", 100, 70))

    def test_the_exchange_folder_is_read_only_and_overridable(self):
        exchange = self.registry["mandu"]["exchange"]
        self.assertEqual(exchange["access"], "read-only")
        self.assertEqual(exchange["env"], "GR0WTHLAB_EXCHANGE_DIR")
        self.assertTrue((REPO / exchange["spec"]).is_file())

    def test_filming_is_built_and_its_footage_place_waits_for_the_founder(self):
        from gr0wthlab import video

        self.assertEqual(
            self.config["outputs"]["filming-plan"],
            {"title": "Filming plan and edits", "story": "US-ME09", "built": True},
        )
        reptoday = next(p for p in self.registry["products"] if p["name"] == "RepToday")
        footage = reptoday["filming"]["footage"]
        self.assertEqual((footage["local_path"], footage["access"]), (None, "read-only"))
        self.assertRegex(footage["env"], r"^GR0WTHLAB_[A-Z]+_DIR$")
        self.assertNotIn("filming", next(p for p in self.registry["products"] if p["name"] == "Immerse"))
        # The plan reads the calendar, the Angle bank, and the pairs: each is a snapshotted source that feeds it.
        feeding = {
            Path(source["path"]).name
            for source in reptoday["go_to_market_package"]["sources"]
            if "filming-plan" in source["needed_by"]
        }
        self.assertEqual(feeding, {"cadence-14-day.md", "angles.md", "ab-pairs.md"})
        canvas = video.load_canvas(load("config/platforms.json"))
        self.assertEqual((canvas.width, canvas.height, canvas.fps), (1080, 1920, 30))
        self.assertEqual(canvas.ratio.numerator * 16, canvas.ratio.denominator * 9)

    def test_no_task_definition_is_chosen_in_configuration(self):
        # The weekly run's task definitions are the reviewed files the launcher puts together for each session
        # (sessions.py); configuration names none, so no setting can swap one out.
        self.assertNotIn("instruction", self.config)

    def test_every_session_limit_is_inside_the_bound_on_the_whole_run(self):
        agent = self.config["agent"]
        self.assertLessEqual(set(agent["session_time_limit_seconds"]), set(sessions.KEYS))
        limits = [agent["time_limit_seconds"], *agent["session_time_limit_seconds"].values()]
        self.assertGreaterEqual(agent["run_time_limit_seconds"], max(limits))


class RuntimeConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = load("config/guardrails/runtime.json")

    def test_runtime_is_codex(self):
        self.assertEqual(self.config["runtime"], "codex")

    def test_every_area_exists_with_a_readme(self):
        for area in self.config["writable_areas"].values():
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

    def test_the_agent_runs_at_high_reasoning_effort(self):
        self.assertEqual(boundary.load_runtime_config(REPO)["codex"]["reasoning_effort"], "high")

    def test_features_that_act_outside_the_sandbox_are_disabled(self):
        disabled = set(self.config["codex"]["disabled_features"])
        for feature in ("apps", "plugins", "hooks", "browser_use", "computer_use", "multi_agent", "multi_agent_v2"):
            self.assertIn(feature, disabled)
        self.assertIs(self.config["codex"]["sub_agents"], False)
        self.assertEqual(
            self.config["codex"]["session_flags"], ["--ignore-user-config", "--ignore-rules", "--ephemeral"]
        )

    def test_image_generation_stays_disabled_so_no_run_can_generate_a_frame(self):
        self.assertIn("image_generation", self.config["codex"]["disabled_features"])
        self.assertIs(self.config["network"], False)


if __name__ == "__main__":
    unittest.main()
