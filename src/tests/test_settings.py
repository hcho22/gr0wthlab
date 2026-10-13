"""config/run.json, the exchange folder, the run's task definition, and the launcher's confined writes."""

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, cli, evidence, exchange, settings
from gr0wthlab.areas import Areas, Store, UnsafeFile, read_plain
from gr0wthlab.boundary import ConfigError
from tests import fakes
from tests.test_boundary import CONFIG

REPO = Path(__file__).resolve().parents[2]
HOME = Path("/Users/founder")


class RunSettingsTest(unittest.TestCase):
    def test_the_committed_settings(self):
        config = settings.load(REPO, {}, HOME)
        self.assertEqual(config.weekly, ("sunday", "16:00"))
        self.assertEqual(config.records.production_clone, HOME / "gr0wthlab")
        self.assertEqual((config.records.remote, config.records.branch), ("origin", "main"))
        self.assertTrue(config.records.sync_before_run and config.records.save_after_run)
        self.assertEqual(set(config.prices), {"input", "cached_input", "cache_write_input", "output"})
        self.assertEqual(config.shown_output_chars, 40000)
        override = settings.load(REPO, {"GR0WTHLAB_PRODUCTION_CLONE": "/srv/clone"}, HOME)
        self.assertEqual(override.records.production_clone, Path("/srv/clone"))
        with self.assertRaises(ConfigError):
            settings.load(REPO, {"GR0WTHLAB_PRODUCTION_CLONE": "relative"}, HOME)

    def test_how_much_output_codex_shows_is_a_whole_number_set_in_reviewed_configuration(self):
        self.assertEqual(settings.load_shown_output({"shown_output_characters": 40000}), 40000)
        for bad in (None, {}, [40000], {"shown_output_characters": None}):
            with self.subTest(work_counts=bad), self.assertRaises(ConfigError):
                settings.load_shown_output(bad)
        for value in (0, 1, -40000, 40000.0, "40000", True):
            with self.subTest(shown=value), self.assertRaisesRegex(ConfigError, "work_counts.shown_output_characters"):
                settings.load_shown_output({"shown_output_characters": value})

    def test_day_1_follows_the_window_s_first_sitting_which_only_the_founder_sets(self):
        unset = settings.load(REPO, {}, HOME).window
        self.assertEqual((unset, unset.day_1), (settings.Window(1, None, None), None))
        window = settings.load_window({"number": 1, "first_sitting": "2026-10-11", "slot": "19:00"}, "sunday")
        self.assertEqual((window.day_1.isoformat(), window.slot.isoformat()), ("2026-10-12", "19:00:00"))
        moved = settings.load_window({"number": 1, "first_sitting": "2026-10-10", "slot": None}, "saturday")
        self.assertEqual(moved.day_1.isoformat(), "2026-10-11")
        for bad in (
            {"number": 0, "first_sitting": None, "slot": None},
            {"number": 1, "first_sitting": "next Sunday", "slot": None},
            {"number": 1, "first_sitting": "2026-13-01", "slot": None},
            {"number": 1, "first_sitting": "2026-10-12", "slot": None},  # a Monday, when the sitting is on Sunday
            {"number": 1, "first_sitting": None, "slot": "7pm"},
            {"number": 1, "first_sitting": None, "slot": "24:00"},
            "sunday",
        ):
            with self.subTest(window=bad), self.assertRaises(ConfigError):
                settings.load_window(bad, "sunday")

    def test_the_waitlist_is_live_only_from_the_date_a_reviewed_change_sets(self):
        unset = settings.load(REPO, {}, HOME)
        self.assertIsNone(unset.waitlist_live_since)
        self.assertFalse(unset.waitlist_live(date(2030, 1, 1)))
        self.assertIsNone(settings.load_live_since({"live_since": None}))
        since = settings.load_live_since({"live_since": "2026-10-20", "why": "set after US-ME05"})
        self.assertEqual(since, date(2026, 10, 20))
        live = replace(unset, waitlist_live_since=since)
        self.assertEqual([live.waitlist_live(date(2026, 10, day)) for day in (19, 20, 21)], [False, True, True])
        for bad in ({"live_since": "yes"}, {"live_since": True}, {"live_since": "2026-13-01"}, "2026-10-20"):
            with self.subTest(waitlist=bad), self.assertRaises(ConfigError):
                settings.load_live_since(bad)


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


class WaitlistSettingsTest(unittest.TestCase):
    HOME = Path("/srv/home")

    def setUp(self):
        self.registry = json.loads((REPO / "config/products.json").read_text(encoding="utf-8"))
        config = dict(CONFIG, filesystem=dict(CONFIG["filesystem"], read_system=[":minimal", "/opt/tools"]))
        self.boundary = boundary.resolve_boundary(
            self.HOME / "gr0wthlab", config, self.registry, {}, self.HOME, git=[Path("/srv/git/gr0wthlab.git")]
        )

    def rules(self, env=None, registry=None):
        return settings.waitlist(registry or self.registry, self.boundary, env or {}, self.HOME)

    def block(self, registry):
        return next(product for product in registry["products"] if product["name"] == "RepToday")["waitlist"]

    def test_no_view_until_the_build_lands_then_the_reviewed_path_or_an_override(self):
        self.assertIsNone(self.rules().view)
        registry = copy.deepcopy(self.registry)
        self.block(registry)["view"]["local_path"] = "~/Library/RepToday/waitlist-view.json"
        self.assertEqual(self.rules(registry=registry).view, self.HOME / "Library/RepToday/waitlist-view.json")
        env = {"GR0WTHLAB_WAITLIST_VIEW": "/srv/exports/waitlist-view.json"}
        self.assertEqual(self.rules(env).view, Path("/srv/exports/waitlist-view.json"))
        with self.assertRaises(ConfigError):
            self.rules({"GR0WTHLAB_WAITLIST_VIEW": "relative/view.json"})

    def test_a_view_the_sandbox_could_read_stops_the_run(self):
        for inside in (
            "/srv/home/gr0wthlab/ledger/view.json",
            "/srv/home/gr0wthlab/workspace/evidence/view.json",
            "/srv/home/Mandu/projects/RepToday/view.json",
            "/srv/home/Developer/FM_Private/firstmate-private/projects/RepToday/view.json",
            "/srv/home/Developer/FM_Private/firstmate-private/projects/Immerse/view.json",
            "/srv/git/gr0wthlab.git/view.json",
            "/opt/tools/view.json",
            "/srv/home",
        ):
            with self.subTest(inside=inside), self.assertRaises(ConfigError) as caught:
                self.rules({"GR0WTHLAB_WAITLIST_VIEW": inside})
            self.assertIn("which the sandboxed agent can read", str(caught.exception))

    def test_counting_rules_are_validated(self):
        breaks = {
            "good_fit": ["not-an-answer"],
            "source_tags": ["tiktok", "unknown"],
            "fit_answers": ["Lost The Routine"],
            "beta_cohort_bar": 0,
        }
        for key, value in breaks.items():
            registry = copy.deepcopy(self.registry)
            self.block(registry)[key] = value
            with self.subTest(key=key), self.assertRaises(ConfigError):
                self.rules(registry=registry)
        registry = copy.deepcopy(self.registry)
        del self.block(registry)["view"]["access"]
        with self.assertRaises(ConfigError):
            self.rules(registry=registry)
        registry = copy.deepcopy(self.registry)
        registry["products"][1]["waitlist"] = self.block(registry)
        with self.assertRaises(ConfigError):
            self.rules(registry=registry)
        registry = copy.deepcopy(self.registry)
        del registry["products"][0]["waitlist"]
        self.assertIsNone(self.rules(registry=registry))


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

    def test_the_store_writes_only_inside_the_ledger(self):
        store = Store(self.repo / "ledger")
        target = store.path("evidence", "sub", "record.json")
        store.write_json(target, {"a": 1})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})
        for outside in (("..", "src", "x.py"), ("..", "workspace", "x.md")):
            with self.subTest(path=outside), self.assertRaises(ConfigError):
                store.path(*outside)

    def test_a_link_at_a_temporary_s_name_cannot_redirect_a_store_write(self):
        store = Store(self.repo / "ledger")
        elsewhere = self.repo.parent / "elsewhere"
        elsewhere.mkdir()
        folder = self.repo / "ledger/review-queue"
        folder.mkdir(parents=True)
        os.symlink(str(elsewhere / "captured"), str(folder / f".queue.json.tmp-{os.getpid()}"))
        store.write_text(folder / "queue.json", "{}")
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertTrue((folder / "queue.json").is_file() and not (folder / "queue.json").is_symlink())

    def test_an_area_replaced_by_a_link_is_never_read_or_removed_through(self):
        elsewhere = self.repo.parent / "elsewhere"
        (elsewhere / "incoming").mkdir(parents=True)
        (elsewhere / "incoming/item.md").write_text("{}", encoding="utf-8")
        area = self.repo / "workspace/review-queue"
        area.rmdir()
        area.symlink_to(elsewhere)
        self.assertEqual(list(self.areas.files(area / "incoming")), [])
        self.areas.remove_empty_folders(area / "incoming")
        self.assertEqual((elsewhere / "incoming/item.md").read_text(encoding="utf-8"), "{}")

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
    def test_a_linked_incoming_folder_is_never_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            elsewhere = Path(directory) / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "item.md").write_text(fakes.PROPOSAL, encoding="utf-8")
            incoming = Path(directory) / "workspace" / "review-queue" / "incoming"
            incoming.parent.mkdir(parents=True)
            incoming.symlink_to(elsewhere)
            out = io.StringIO()
            with mock.patch.object(cli, "INCOMING", incoming), redirect_stdout(out):
                code = cli.check_incoming(out)
        self.assertEqual(code, 1)
        self.assertIn("is not a real folder; the launcher removes it and takes in nothing from it", out.getvalue())
        self.assertNotIn("item.md", out.getvalue())

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_unreadable_incoming_folder_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            incoming = Path(directory) / "workspace" / "review-queue" / "incoming"
            incoming.mkdir(parents=True)
            (incoming / "item.md").write_text(fakes.PROPOSAL, encoding="utf-8")
            incoming.chmod(0o300)
            out = io.StringIO()
            try:
                with mock.patch.object(cli, "INCOMING", incoming), redirect_stdout(out):
                    code = cli.check_incoming(out)
            finally:
                incoming.chmod(0o700)
        self.assertEqual(code, 1)
        self.assertIn("could not be read (Permission denied); the launcher takes in nothing from it", out.getvalue())

    def test_reports_each_item_as_the_launcher_would(self):
        with tempfile.TemporaryDirectory() as directory:
            queue_dir = Path(directory) / "ledger" / "review-queue"
            incoming = Path(directory) / "workspace" / "review-queue" / "incoming"
            (queue_dir / "items").mkdir(parents=True)
            incoming.mkdir(parents=True)
            queued = fakes.proposal(extra=f"exchange: {exchange.EXCHANGE_VERSION}\nid: 20261011-queued\n")
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
                json.dumps({"exchange": exchange.EXCHANGE_VERSION, "open": [], "closed": [entry]}), encoding="utf-8"
            )
            (incoming / "good.md").write_text(fakes.proposal(title="a new ask"), encoding="utf-8")
            (incoming / "twin.md").write_text(fakes.proposal(title="a new ask"), encoding="utf-8")
            (incoming / "again.md").write_text(fakes.PROPOSAL, encoding="utf-8")
            (incoming / "bad.md").write_text("# no front matter\n", encoding="utf-8")
            rejected_again = fakes.proposal(extra="supersedes: 20261011-queued\n", title="supersede a decided one")
            (incoming / "supersede.md").write_text(rejected_again, encoding="utf-8")
            (incoming / f"{'long-' * 13}name.md").write_text(fakes.proposal(title="a long name"), encoding="utf-8")
            quote = evidence.Quote(
                "d-0123456789ab",
                "RepToday",
                "https://www.reddit.com/r/fitness30plus/comments/abc123/an_example/",
                "2026-10-11",
                "Three words here.",
                "A thread.",
                "lost-the-routine",
                "strong",
                "venting",
                True,
                "reddit:fitness30plus",
                "post",
                "",
                "0" * 64,
                True,
                "an-earlier-run",
            )
            evidence.keep(Store(Path(os.path.realpath(directory)) / "ledger"), quote)
            for name, cited in (("sourced.md", quote.id), ("unsourced.md", "d-000000000000")):
                angle = fakes.proposal(title=f"give P03 a second Hook ({name})", new_angle="yes").replace(
                    "- Cleared and reserved:",
                    f"- Sourced pain: `{evidence.file_of(cited)}`\n- Cleared and reserved:",
                )
                (incoming / name).write_text(angle, encoding="utf-8")
            out = io.StringIO()
            with (
                mock.patch.object(cli, "INCOMING", incoming),
                mock.patch.object(cli, "LEDGER_DIR", Path(directory) / "ledger"),
                redirect_stdout(out),
            ):
                code = cli.check_incoming(out)
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("OK good.md", text)
        self.assertIn("PROBLEM bad.md", text)
        self.assertIn("PROBLEM again.md\n  - asks the same as 20261011-queued, which is rejected", text)
        self.assertIn("PROBLEM twin.md\n  - asks the same as good.md, which is also in incoming/", text)
        self.assertIn("PROBLEM supersede.md\n  - supersedes 20261011-queued, which is not an open item", text)
        self.assertIn(f"PROBLEM {'long-' * 13}name.md\n  - name it <slug>.md directly in incoming/", text)
        self.assertIn("OK sourced.md", text)
        self.assertIn("PROBLEM unsourced.md\n  - it declares new_angle: yes, and a proposal that adds or changes", text)
        self.assertIn("8 items checked, 6 with problems", text)


if __name__ == "__main__":
    unittest.main()
