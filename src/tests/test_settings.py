"""config/run.json, the exchange folder, the run's task definition, and the launcher's confined writes."""

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gr0wthlab import boundary, cli, settings
from gr0wthlab.areas import Areas, UnsafeFile, read_plain
from gr0wthlab.boundary import ConfigError
from tests import fakes
from tests.test_boundary import CONFIG

REPO = Path(__file__).resolve().parents[2]
HOME = Path("/Users/founder")


class RunSettingsTest(unittest.TestCase):
    def test_the_committed_settings(self):
        config = settings.load(REPO, {}, HOME)
        self.assertEqual(config.weekly, ("sunday", "16:00"))
        self.assertEqual(config.instruction, REPO / "src/instructions/weekly-run.md")
        self.assertEqual(config.records.production_clone, HOME / "gr0wthlab")
        self.assertEqual((config.records.remote, config.records.branch), ("origin", "main"))
        self.assertTrue(config.records.sync_before_run and config.records.save_after_run)
        self.assertEqual(set(config.prices), {"input", "cached_input", "cache_write_input", "output"})
        override = settings.load(REPO, {"GR0WTHLAB_PRODUCTION_CLONE": "/srv/clone"}, HOME)
        self.assertEqual(override.records.production_clone, Path("/srv/clone"))
        with self.assertRaises(ConfigError):
            settings.load(REPO, {"GR0WTHLAB_PRODUCTION_CLONE": "relative"}, HOME)

    def test_the_task_definition_must_be_reviewed_code(self):
        self.assertEqual(
            settings.instruction_path(REPO, Path("src/instructions/weekly-run.md")),
            REPO / "src/instructions/weekly-run.md",
        )
        for path in ("workspace/instructions/package-review.md", "src/checks/boundary-probe.md", "README.md"):
            with self.subTest(path=path), self.assertRaises(ConfigError):
                settings.instruction_path(REPO, Path(path))
        with self.assertRaises(ConfigError):
            settings.instruction_path(REPO, Path("src/instructions/absent.md"))


class ExchangeFolderTest(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((REPO / "config/products.json").read_text(encoding="utf-8"))
        self.boundary = boundary.resolve_boundary(
            Path("/srv/home/gr0wthlab"), CONFIG, self.registry, {}, Path("/srv/home"), git=[]
        )

    def test_inside_mandu_unless_overridden(self):
        folder = settings.exchange_dir(self.registry, self.boundary, {}, Path("/srv/home"))
        self.assertEqual(folder, Path("/srv/home/Mandu/projects/gr0wthlab/exchange"))
        env = {"GR0WTHLAB_EXCHANGE_DIR": "/srv/tmp/exchange"}
        self.assertEqual(
            settings.exchange_dir(self.registry, self.boundary, env, Path("/srv/home")),
            Path(env["GR0WTHLAB_EXCHANGE_DIR"]),
        )

    def test_never_inside_the_repository_where_the_agent_writes(self):
        for override in ("/srv/home/gr0wthlab/workspace/evidence", "/srv/home"):
            with self.subTest(override=override), self.assertRaises(ConfigError):
                settings.exchange_dir(
                    self.registry, self.boundary, {"GR0WTHLAB_EXCHANGE_DIR": override}, Path("/srv/home")
                )
        registry = copy.deepcopy(self.registry)
        registry["mandu"]["exchange"]["path"] = "../escape"
        with self.assertRaises(ConfigError):
            settings.exchange_dir(registry, self.boundary, {}, Path("/srv/home"))


class AreasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(os.path.realpath(self.tmp.name)) / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        self.areas = Areas(
            boundary.resolve_boundary(
                self.repo,
                CONFIG,
                {"mandu": {"local_checkout": "/srv/Mandu", "access": "read-only"}},
                {},
                self.repo.parent,
                git=[],
            )
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_stay_inside_the_areas(self):
        target = self.repo / "workspace/evidence/sub/record.json"
        self.areas.write_json(target, {"a": 1})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})
        for outside in (
            self.repo / "src/x.py",
            self.repo / "workspace/x.md",
            self.repo / "workspace/evidence",
            self.repo / "workspace/evidence/../../config/x.json",
        ):
            with self.subTest(path=outside), self.assertRaises(ConfigError):
                self.areas.write_text(outside, "x")

    def test_a_symbolic_link_inside_an_area_cannot_redirect_a_write(self):
        elsewhere = self.repo.parent / "elsewhere"
        elsewhere.mkdir()
        os.symlink(str(elsewhere), str(self.repo / "workspace/drafts/link"))
        with self.assertRaises(ConfigError):
            self.areas.write_text(self.repo / "workspace/drafts/link/x.md", "x")
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_read_plain_refuses_links(self):
        target = self.repo / "workspace/drafts/real.md"
        target.write_text("x", encoding="utf-8")
        self.assertEqual(read_plain(target), b"x")
        os.symlink(str(target), str(self.repo / "workspace/drafts/sym.md"))
        os.link(str(target), str(self.repo / "workspace/drafts/hard.md"))
        for name in ("sym.md", "hard.md"):
            with self.subTest(name=name), self.assertRaises(UnsafeFile):
                read_plain(self.repo / "workspace/drafts" / name)


class CheckIncomingTest(unittest.TestCase):
    def test_reports_each_item_as_the_launcher_would(self):
        with tempfile.TemporaryDirectory() as directory:
            queue_dir = Path(directory) / "workspace" / "review-queue"
            incoming = queue_dir / "incoming"
            (queue_dir / "items").mkdir(parents=True)
            incoming.mkdir()
            queued = fakes.proposal(extra="exchange: 1\nid: 20261011-queued\n")
            (queue_dir / "items" / "20261011-queued.md").write_text(queued, encoding="utf-8")
            entry = {
                "id": "20261011-queued",
                "kind": "package-change-proposal",
                "ask": "x",
                "status": "rejected",
                "file": "review-queue/items/20261011-queued.md",
                "published_at": "2026-10-11T23:00:00+00:00",
            }
            (queue_dir / "queue.json").write_text(
                json.dumps({"exchange": 1, "open": [], "closed": [entry]}), encoding="utf-8"
            )
            (incoming / "good.md").write_text(fakes.proposal(title="a new ask"), encoding="utf-8")
            (incoming / "twin.md").write_text(fakes.proposal(title="a new ask"), encoding="utf-8")
            (incoming / "again.md").write_text(fakes.PROPOSAL, encoding="utf-8")
            (incoming / "bad.md").write_text("# no front matter\n", encoding="utf-8")
            rejected_again = fakes.proposal(extra="supersedes: 20261011-queued\n", title="supersede a decided one")
            (incoming / "supersede.md").write_text(rejected_again, encoding="utf-8")
            (incoming / f"{'long-' * 13}name.md").write_text(fakes.proposal(title="a long name"), encoding="utf-8")
            original = cli.INCOMING
            cli.INCOMING = incoming
            try:
                out = io.StringIO()
                with redirect_stdout(out):
                    code = cli.check_incoming(out)
            finally:
                cli.INCOMING = original
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("OK good.md", text)
        self.assertIn("PROBLEM bad.md", text)
        self.assertIn("PROBLEM again.md\n  - asks the same as 20261011-queued, which is rejected", text)
        self.assertIn("PROBLEM twin.md\n  - asks the same as good.md, which is also in incoming/", text)
        self.assertIn("PROBLEM supersede.md\n  - supersedes 20261011-queued, which is not an open item", text)
        self.assertIn(f"PROBLEM {'long-' * 13}name.md\n  - name it <slug>.md directly in incoming/", text)
        self.assertIn("6 items checked, 5 with problems", text)


if __name__ == "__main__":
    unittest.main()
