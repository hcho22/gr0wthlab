"""The filming workflow, in whole runs with a fake Codex and fake video tooling: the plan as one Review Queue item,
the footage place only ever read, and each edit record checked, rendered, measured, and shown in its day's post."""

import io
import json
import os
import shutil
import subprocess
import unittest
from datetime import date, timedelta
from unittest import mock

from gr0wthlab import boundary, cli, cycle, exchange, filming, footage, video
from gr0wthlab.boundary import ConfigError
from tests import fakes
from tests.test_cycle import CycleTestCase

PLAN = "20261011-filming-plan-w1"
ANGLES = "projects/RepToday/gtm/05-social-pmf/angles.md"
CALENDAR = "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
DAY_1 = ("d01-s1", "d01-s1.mov", 2, 12)


class FilmingRunCase(CycleTestCase):
    def setUp(self):
        super().setUp()
        fakes.set_filming(self.repo, True)
        shutil.copytree(str(fakes.FILMING / "files" / "mandu"), str(self.mandu), dirs_exist_ok=True)
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        # The canvas's font ships with macOS; the fake tooling draws nothing, so any file stands in for it elsewhere.
        platforms = self.repo / "config" / "platforms.json"
        data = json.loads(platforms.read_text(encoding="utf-8"))
        data["video"]["text"]["font_file"] = str(self.root / "font.ttf")
        (self.root / "font.ttf").write_text("a font")
        platforms.write_text(json.dumps(data), encoding="utf-8")
        self.footage = self.root / "footage"
        self.tools = self.root / "video-tools"
        self.env.update(fakes.install_video_tools(self.tools), GR0WTHLAB_FOOTAGE_DIR=str(self.footage))
        self.runs = 0

    def run_ok(self, writes=None, days=None):
        """One more run, an hour after the last; writes is what the agent writes, days the calendar days kept."""
        if days is not None:
            fakes.keep_days(self.mandu, *days)
        fakes.behave(self.codex_dir, {"write": writes or {}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=self.runs))
        self.runs += 1
        self.assertEqual(code, 0, out)
        return self.queue()

    def entries(self, kind="post", status=None):
        queue = self.queue()
        found = [entry for entry in queue["open"] + queue["closed"] if entry["kind"] == kind]
        return [entry for entry in found if status is None or entry["status"] == status]

    def item(self, entry):
        return (self.ledger() / entry["file"]).read_text(encoding="utf-8")

    def clip(self, name, duration=14.0, *shape, **more):
        return fakes.fake_clip(self.footage / "window-1" / name, duration, *shape, **more)

    def approved_plan(self, days=(1, 8)):
        """A run that files the plan for the kept days, then the Founder's approval of it."""
        self.run_ok(days=days)
        self.decide(PLAN, "approve")

    def notice(self):
        """The notice of the latest run with problems."""
        notices = [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]
        return self.item(max(notices, key=lambda entry: entry["published_at"]))

    def asset(self, entry):
        """What the fake ffmpeg wrote for a post's video: the facts, inputs, and text of the render."""
        return json.loads((self.ledger() / entry["asset"]).read_text(encoding="utf-8"))

    def check_edits(self, run_id):
        out = io.StringIO()
        with mock.patch.object(cli, "REPO_ROOT", self.repo), mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"):
            return cli.check_edits(run_id, out), out.getvalue()


class FilmingPlanTest(FilmingRunCase):
    def test_the_plan_is_one_item_with_a_shot_list_for_every_asset_in_the_fewest_sittings(self):
        queue = self.run_ok()
        plans = [entry for entry in queue["open"] if entry["kind"] == "filming-plan"]
        self.assertEqual([entry["id"] for entry in plans], [PLAN])
        entry = plans[0]
        self.assertEqual(entry["ask"], "Approve the filming plan for RepToday window 1: 10 assets in 3 sittings")
        self.assertEqual(entry["origin"], "filming-plan/RepToday/window-1")
        self.assertEqual(
            sorted(entry["filming_jobs"]), ["d01", "d02", "d03", "d04", "d05", "d06", "d07", "d11", "d12", "d13"]
        )
        text = self.item(entry)
        check = exchange.check_item(text, ["RepToday", "Immerse"], published=True)
        self.assertEqual(check.problems, [])
        self.assertIn("exchange: 4\n", text)
        self.assertIn("## Plan\n", text)
        self.assertIn(
            "RepToday window 1 needs footage for 10 assets, filmed in 3 sittings, for calendar days 1, 2, 3, 4, 5, 6,"
            " 7, 8, 9, 10, 11, 12, and 13. Days 8, 9, and 10 are cut from an earlier day's footage with only the"
            " opening changed, so they film nothing new.",
            text,
        )
        self.assertIn("No video is cut from a shot's footage until a plan that holds the shot is approved.", text)
        self.assertIn("**Sitting 1: device screen recordings**, for days 1, 2, 3, 4, 8, 9, 10, and 11\n", text)
        self.assertIn("**Sitting 2: on camera**, for days 2, 6, 7, 9, 12, and 13\n", text)
        self.assertIn("**Sitting 3: setup not stated**, for day 5\n", text)
        # One beat-sheet shape for every shot, in the Format's own words.
        header = (
            "| Shot | For | Time | What to record | Device | Real time | On-screen text | Caption | May not be cut |"
        )
        self.assertEqual(text.count(header), 3)
        self.assertIn(
            "| d01-s1 | days 1 and 8 | 10s | screen record, no cuts | The real device running RepToday, screen"
            " recording | Yes | The Hook, then the Draft's | None unless a line is spoken | Yes |",
            text,
        )
        self.assertIn(
            "| d02-s1 | days 2 and 9 | part of 20s | founder-on-camera line | Camera, the Founder in frame | Not stated"
            " | The Hook, then the Draft's | The spoken lines | Not stated |",
            text,
        )
        self.assertIn(
            "| d02-s2 | days 2 and 9 | part of 20s | a screen record of the app opening | The real device running"
            " RepToday, screen recording | Yes | The Draft's | None unless a line is spoken | Yes |",
            text,
        )
        self.assertIn(
            "| d07-s1 | day 7 | 15-20s | timelapse of one five-minute session | Camera | No: timelapse |", text
        )
        self.assertIn("| d05-s1 | day 5 | 15s | slow-motion capture | Not stated | No: slow-motion capture |", text)
        # Each shot list cites the Angle's Format, and each day the frozen Hook it opens on.
        self.assertIn(
            '- d01, days 1 and 8 (P01, AB-1): Format in `angles.md` line 8. Day 1 opens on "Open it and the session'
            ' is already waiting." (`ab-pairs.md` line 8). Day 8 opens on "The session is on screen before you'
            ' decide." (`ab-pairs.md` line 9).',
            text,
        )
        self.assertIn(
            '- d02, days 2 and 9 (P02, AB-3, opening re-cut): Format in `angles.md` line 9. Day 2 opens on "I open my'
            ' own app and the session is already there." (`ab-pairs.md` line 18).',
            text,
        )
        self.assertIn(
            " Each leg opens on its own Hook, so record the opening once for each: name the takes `d02-s1a` for day 2"
            " and `d02-s1b` for day 9.",
            text,
        )
        self.assertIn('- d04, day 4 (P04): Format in `angles.md` line 11. Day 4 opens on "Airplane mode on.', text)
        self.assertIn(
            f"- Each Angle's Format, quoted in the shot lists: `{ANGLES}` lines 8, 9, 10, 11, 12, 13, and 14", text
        )
        self.assertIn("Not planned: day 14, since the calendar decides its Angle later", text)
        self.assertIn(f"- What holds for every screen recording: `{CALENDAR}` line 28", text)
        self.assertIn("Every asset is finished at 1080x1920 (9:16), so film upright.", text)
        # Nothing but the kit text a shot list uses: no pain, signal, or kill criterion is copied.
        for strategy in ("Pain 1", "Watched-full rate", "Bottom quartile", "holds viewers"):
            self.assertNotIn(strategy, text)
        self.assertLess(len(text), exchange.MAX_ITEM_CHARS)

    def test_a_plan_for_one_asset_or_one_day_reads_in_the_singular(self):
        queue = self.run_ok(days=(1, 4, 8))
        text = self.item(next(entry for entry in queue["open"] if entry["kind"] == "filming-plan"))
        self.assertIn(
            "RepToday window 1 needs footage for 2 assets, filmed in 1 sitting, for calendar days 1, 4, and 8. Day 8"
            " is cut from an earlier day's footage with only the opening changed, so it films nothing new.\n",
            text,
        )
        self.assertIn(f"- Each Angle's Format, quoted in the shot lists: `{ANGLES}` lines 8 and 11\n", text)
        queue = self.run_ok(days=(4,))
        text = self.item(next(entry for entry in queue["open"] if entry["kind"] == "filming-plan"))
        self.assertIn("needs footage for 1 asset, filmed in 1 sitting, for calendar day 4.\n", text)
        self.assertIn(f"- Each Angle's Format, quoted in the shot lists: `{ANGLES}` line 11\n", text)

    def test_the_report_and_the_brief_say_where_the_plan_the_tooling_and_the_footage_stand(self):
        queue = self.run_ok()
        report = self.report()
        self.assertIn(f"- Filming plan: filed this run as `{PLAN}`.", report)
        self.assertIn("- 10 assets to film in 3 sittings: Device screen recordings (d01-s1, d02-s2,", report)
        self.assertIn("- Not planned: day 14, since the calendar decides its Angle later", report)
        self.assertIn(f"| Video tooling | read | {fakes.FAKE_FFMPEG_VERSION} at `{self.tools}/ffmpeg` |", report)
        self.assertIn(f"| Footage place | skipped | `{self.footage}/window-1` does not exist yet |", report)
        self.assertIn(
            f"- filming: checked=10 acted=1 note=plan filed this run as `{PLAN}`; 10 assets planned, 0 footage"
            f" files measured",
            report,
        )
        self.assertIn("| Filming plan and edits | complete | plan filed this run", report)
        self.assertIn(f"| 1 | d01-s1 | no edit record | the filming plan `{PLAN}` is not approved yet |", report)
        self.assertIn(
            f"- Every file measured and every edit checked: `evidence/filming/{queue['updated_by_run']}.json`.", report
        )
        brief = self.brief()
        self.assertIn("## Filming", brief)
        self.assertIn(
            f"- Filming plan: filed this run as `{PLAN}`. The launcher files it from the kit; never write one.", brief
        )
        self.assertIn(f"- `{PLAN}` (filming-plan, filed by the launcher): Approve the filming plan", brief)
        self.assertIn("- No day is ready for an edit record this run.", brief)
        self.assertIn(
            "| 1 | d01-s1 (screen recording; one unbroken range, never cut; no speed change) | 10s; the same source"
            f" ranges as day 8 from the first frame to the last | none yet | not ready: the filming plan `{PLAN}` is"
            " not approved yet |",
            brief,
        )
        self.assertIn("| 7 | d07-s1 (timelapse; may run at another speed) | 15-20s | none yet |", brief)
        self.assertIn("| 2 | d02-s1 (founder on camera; no speed change); d02-s2 (screen recording;", brief)
        self.assertIn(f"check-edits --run {queue['updated_by_run']}`", brief)
        evidence = json.loads((self.ledger() / f"evidence/filming/{queue['updated_by_run']}.json").read_text())
        self.assertEqual(evidence["plan"]["item"], PLAN)
        self.assertEqual(
            [sitting["setup"] for sitting in evidence["plan"]["sittings"]], ["device", "camera", "not stated"]
        )
        self.assertEqual(len(evidence["plan"]["jobs"]), 10)

    def test_an_open_plan_is_never_filed_again_and_an_approved_one_is_never_asked_again(self):
        self.run_ok()
        queue = self.run_ok()
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "filming-plan"], [PLAN])
        self.assertIn(f"- Filming plan: open as `{PLAN}`.", self.report())
        self.assertIn("- filming: checked=10 acted=0 note=plan open as", self.report())
        self.decide(PLAN, "approve", note="Filming on Saturday.")
        for _ in range(2):
            queue = self.run_ok()
            self.assertEqual(len(self.entries("filming-plan")), 1)
            self.assertEqual(self.entries("filming-plan")[0]["status"], "approved")
            self.assertIn(f"- Filming plan: approved as `{PLAN}`; never asked again.", self.report())
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "filming-plan"], [])

    def test_a_rejected_plan_is_not_asked_again_and_nothing_is_cut_from_its_footage(self):
        self.run_ok(days=(1, 8))
        self.decide(PLAN, "reject", reason="Split the screen recordings over two evenings.")
        self.clip("d01-s1.mov")
        writes = {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        self.run_ok(writes)
        self.run_ok()
        self.assertEqual(len(self.entries("filming-plan")), 1)
        report = self.report()
        self.assertIn(
            f"- Filming plan: rejected as `{PLAN}`: Split the screen recordings over two evenings.; not asked again"
            " until the kit changes what must be filmed.",
            report,
        )
        self.assertIn(
            f"| 1 | d01-s1 | not cut | the filming plan was rejected as `{PLAN}`, so nothing is cut from its footage |",
            report,
        )
        self.assertFalse((self.ledger() / "assets").exists())

    def test_only_a_kit_change_to_what_must_be_filmed_replaces_the_plan(self):
        self.run_ok()
        angles = self.mandu / ANGLES
        original = angles.read_text(encoding="utf-8")
        angles.write_text(original.replace("Watched-full rate in the top half", "Watched-full rate in the top third"))
        queue = self.run_ok()
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "filming-plan"], [PLAN])
        angles.write_text(
            original.replace("10s screen record, no cuts | TikTok", "12s screen record, no cuts | TikTok")
        )
        queue = self.run_ok()
        plans = [entry for entry in queue["open"] if entry["kind"] == "filming-plan"]
        self.assertEqual([entry["id"] for entry in plans], [f"{PLAN}-2"])
        self.assertEqual(plans[0]["supersedes"], PLAN)
        closed = next(entry for entry in queue["closed"] if entry["id"] == PLAN)
        self.assertEqual((closed["status"], closed["superseded_by"]), ("superseded", f"{PLAN}-2"))
        text = self.item(plans[0])
        self.assertIn(f"This plan replaces `{PLAN}`, because the kit changed what must be filmed: d01 changed.", text)
        self.assertIn("| d01-s1 | days 1 and 8 | 12s | screen record, no cuts |", text)
        self.assertIn(
            f"- Filming plan: filed as `{PLAN}-2` in place of `{PLAN}`, as the kit changed what must be filmed.",
            self.report(),
        )
        self.assertEqual(len(self.run_ok()["open"]), len(queue["open"]))

    def test_a_kit_change_after_approval_asks_again_only_for_the_jobs_it_changed(self):
        self.approved_plan(days=(1, 3, 8, 10))
        self.clip("d01-s1.mov")
        self.clip("d03-s1.mov")
        angles = self.mandu / ANGLES
        angles.write_text(
            angles.read_text(encoding="utf-8").replace(
                "10s screen record, no cuts | TikTok", "12s screen record, no cuts | TikTok"
            )
        )
        queue = self.run_ok()
        plans = [entry for entry in queue["open"] if entry["kind"] == "filming-plan"]
        self.assertEqual([entry["id"] for entry in plans], [f"{PLAN}-2"])
        self.assertIn(
            f"This plan replaces `{PLAN}`, which you approved, because the kit changed what must be filmed: d01"
            f" changed.",
            self.item(plans[0]),
        )
        self.assertEqual(self.entries("filming-plan", "approved")[0]["id"], PLAN)
        brief = self.brief()
        self.assertIn(
            f"not ready: the kit changed what day 1 films since a filming plan was approved, and the plan `{PLAN}-2`"
            " that holds it now is not approved yet",
            brief,
        )
        self.assertRegex(brief, r"\| 3 \|[^\n]*\| ready \|")
        # The kit goes back to what was approved: the plan filed for the change has nothing left to ask.
        angles.write_text(
            angles.read_text(encoding="utf-8").replace(
                "12s screen record, no cuts | TikTok", "10s screen record, no cuts | TikTok"
            )
        )
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "filming-plan"], [])
        self.assertIn(f"- Filming plan: approved as `{PLAN}`; never asked again.", self.report())

    def test_no_item_the_agent_writes_is_or_replaces_the_filming_plan(self):
        self.run_ok()
        own = fakes.proposal("filming-plan", title="film everything in one evening")
        replacing = fakes.proposal(extra=f"supersedes: {PLAN}\n", title="replace the filming plan")
        queue = self.run_ok(
            {"review-queue/incoming/my-plan.md": own, "review-queue/incoming/replace-plan.md": replacing}
        )
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "filming-plan"], [PLAN])
        report = self.report()
        self.assertIn(
            "`my-plan.md`: the filming plan is filed only by the launcher, from the kit; never write one here", report
        )
        self.assertIn(f"`replace-plan.md`: supersedes {PLAN}, which the launcher filed from reviewed text", report)

    def test_a_kit_that_cannot_be_read_plans_nothing_and_says_so(self):
        (self.mandu / ANGLES).write_text("# Angle bank\n\nNo table here.\n", encoding="utf-8")
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "filming-plan"], [])
        report = self.report()
        self.assertIn(f"Nothing could be planned this run: the kit could not be read: `{ANGLES}` (", report)
        self.assertIn("| Filming plan and edits | incomplete | the kit could not be read:", report)

    def test_a_run_whose_product_does_not_film_files_no_plan(self):
        fakes.set_filming(self.repo, False)
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "filming-plan"], [])
        report = self.report()
        self.assertIn("| Filming plan and edits | skipped | no active Product films |", report)
        self.assertIn("- filming: checked=0 acted=0 note=no active Product films", report)
        self.assertNotIn("## Filming", report)

    def test_a_product_that_films_with_no_post_plan_is_incomplete_with_the_reason_never_skipped(self):
        path = self.repo / "config" / "products.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        product = next(product for product in registry["products"] if product["name"] == "RepToday")
        del product["go_to_market_package"]["post_drafts"]
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "filming-plan"], [])
        why = "not planned: the post Drafts, whose calendar the plan reads, were not prepared"
        report = self.report()
        self.assertIn(f"| Filming plan and edits | incomplete | {why} |", report)
        self.assertIn(f"## Filming\n\n{why}", report)
        self.assertIn(f"- filming: checked=0 acted=0 note={why}", report)
        self.assertNotIn("no active Product films", report)


class FootagePlaceTest(FilmingRunCase):
    def test_the_footage_place_is_unset_until_the_founder_sets_it(self):
        registry = json.loads((fakes.REPO / "config" / "products.json").read_text(encoding="utf-8"))
        block = next(product for product in registry["products"] if product["name"] == "RepToday")["filming"]["footage"]
        self.assertEqual(
            (block["local_path"], block["access"], block["env"]), (None, "read-only", "GR0WTHLAB_FOOTAGE_DIR")
        )
        del self.env["GR0WTHLAB_FOOTAGE_DIR"]
        self.run_ok()
        report = self.report()
        self.assertIn("| Footage place | skipped | the footage place is not set in config/products.json |", report)
        self.assertIn(f"- Filming plan: filed this run as `{PLAN}`.", report)

    def place(self, path, **registry_changes):
        registry = json.loads((self.repo / "config" / "products.json").read_text(encoding="utf-8"))
        product = next(product for product in registry["products"] if product["name"] == "RepToday")
        product["filming"]["footage"].update(registry_changes)
        runtime = json.loads((self.repo / "config" / "guardrails" / "runtime.json").read_text(encoding="utf-8"))
        env = (
            dict(self.env, GR0WTHLAB_FOOTAGE_DIR=str(path))
            if path
            else {k: v for k, v in self.env.items() if k != "GR0WTHLAB_FOOTAGE_DIR"}
        )
        resolved = boundary.resolve_boundary(self.repo, runtime, registry, env, self.home)
        return filming.place(registry, resolved, env, self.home)

    def test_a_footage_place_the_sandbox_can_read_stops_the_run_before_it_starts(self):
        for inside in (
            self.repo / "workspace" / "drafts" / "footage",
            self.repo / "ledger" / "assets",
            self.repo,
            self.root,
            self.mandu / "projects" / "RepToday" / "footage",
            self.mandu.parent,
            self.code / "footage",
        ):
            with (
                self.subTest(place=inside),
                self.assertRaisesRegex(
                    ConfigError,
                    "which the sandboxed agent can read; raw footage lives outside every location the run reads",
                ),
            ):
                self.place(inside)
        self.env["GR0WTHLAB_FOOTAGE_DIR"] = str(self.repo / "workspace" / "evidence")
        code, out = self.run_cycle()
        self.assertEqual(code, cycle.launcher.EXIT_CONFIG, out)
        self.assertIn("refusing to start: RepToday's footage place", out)

    def test_the_footage_place_is_declared_read_only_with_an_override_name(self):
        self.assertEqual(self.place(self.footage).path, self.footage)
        self.assertEqual(
            self.place(None, local_path="~/Movies/gr0wthlab-footage").path, self.home / "Movies/gr0wthlab-footage"
        )
        self.assertIsNone(self.place(None).path)
        with self.assertRaisesRegex(ConfigError, "must be declared read-only"):
            self.place(self.footage, access="read-write")
        with self.assertRaisesRegex(ConfigError, "needs an env override name"):
            self.place(self.footage, env="")
        with self.assertRaisesRegex(ConfigError, "must start with ~/ or be absolute"):
            self.place(None, local_path="Movies/footage")

    def test_the_inventory_only_reads_and_names_what_it_leaves_alone(self):
        tooling = video.find(self.env)
        self.clip("d01-s1.mov")
        self.clip("D01-S1-take-2.MOV", 9.5)
        self.clip("d02-s1b-opening.mp4", 6.0, 1080, 1920, 30, sound=True)
        self.clip("holiday.mov", 30.0)
        self.clip("d44-s1.mov", 5.0)
        (self.footage / "window-1" / "notes.txt").write_text("shot notes")
        (self.footage / "window-1" / "d01-s1-broken.mov").write_text("not a video")
        (self.footage / "window-1" / ".DS_Store").write_text("finder")
        (self.footage / "window-1" / "takes").mkdir()
        outside = self.root / "elsewhere.mov"
        fakes.fake_clip(outside, 12.0)
        (self.footage / "window-1" / "d03-s1.mov").symlink_to(outside)
        before = fakes.tree_digest(self.footage)
        found = footage.read(self.footage, 1, {"d01-s1", "d02-s1", "d03-s1"}, tooling, self.env)
        self.assertEqual(fakes.tree_digest(self.footage), before)
        self.assertEqual(found.status, footage.READ)
        self.assertEqual(
            sorted(found.clips),
            [
                "window-1/D01-S1-take-2.MOV",
                "window-1/d01-s1-broken.mov",
                "window-1/d01-s1.mov",
                "window-1/d02-s1b-opening.mp4",
                "window-1/d44-s1.mov",
                "window-1/holiday.mov",
            ],
        )
        first = found.clips["window-1/d01-s1.mov"]
        self.assertEqual(
            (first.shot, first.leg, first.facts.duration, first.facts.width, first.problem),
            ("d01-s1", None, 14.0, 886, ""),
        )
        self.assertEqual(len(first.sha256), 64)
        self.assertEqual(first.bytes, (self.footage / "window-1" / "d01-s1.mov").stat().st_size)
        self.assertEqual(
            (found.clips["window-1/d02-s1b-opening.mp4"].shot, found.clips["window-1/d02-s1b-opening.mp4"].leg),
            ("d02-s1", "B"),
        )
        self.assertEqual(found.clips["window-1/holiday.mov"].problem, "its name starts with no shot, such as d01-s1")
        self.assertEqual(
            found.clips["window-1/d44-s1.mov"].problem,
            "its name starts with d44-s1, which is not a shot of the filming plan",
        )
        self.assertIn("ffprobe could not read it", found.clips["window-1/d01-s1-broken.mov"].problem)
        self.assertEqual(
            found.ignored,
            [
                ("window-1/d03-s1.mov", "a link, which is never followed"),
                ("window-1/notes.txt", "not a .mov, .mp4, .m4v file"),
                ("window-1/takes", "a folder; footage files sit directly in window-1/"),
            ],
        )
        self.assertEqual(
            [clip.name for clip in found.for_shot("d01-s1")], ["window-1/D01-S1-take-2.MOV", "window-1/d01-s1.mov"]
        )
        self.assertEqual(found.for_shot("d02-s1", "A"), [])
        self.assertEqual(len(found.for_shot("d02-s1", "B")), 1)
        self.assertEqual(found.for_shot("d03-s1"), [])
        self.assertEqual(found.path(first), self.footage / "window-1" / "d01-s1.mov")
        with self.assertRaises(KeyError):
            found.path(first.__class__("window-1/../../elsewhere.mov", 1, "0" * 64, "d01-s1", None, first.facts))

    def test_a_window_folder_that_is_a_link_or_missing_is_never_read_through(self):
        tooling = video.find(self.env)
        self.assertEqual(footage.read(self.footage, 1, set(), tooling, self.env).status, footage.EMPTY)
        self.assertEqual(footage.read(None, 1, set(), tooling, self.env).status, footage.NOT_SET)
        elsewhere = self.root / "elsewhere"
        fakes.fake_clip(elsewhere / "d01-s1.mov", 14.0)
        self.footage.mkdir()
        (self.footage / "window-1").symlink_to(elsewhere)
        linked = footage.read(self.footage, 1, {"d01-s1"}, tooling, self.env)
        self.assertEqual((linked.status, linked.clips), (footage.FAILED, {}))
        self.assertIn("is not a real folder, so nothing in it was read", linked.detail)
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn(f"| Footage place | failed | `{self.footage}/window-1` is not a real folder", self.report())
        self.assertIn("| Filming plan and edits | incomplete | Footage place could not be read;", self.report())


class EditRunTest(FilmingRunCase):
    """US-ME09's Validation Test on the synthetic kit: the day 1 and day 8 assets follow the shot list, measure 9:16,
    and differ only in the Hook; a record that breaks a rule renders nothing."""

    def day_1(self, edit=DAY_1):
        self.approved_plan()
        self.clip("d01-s1.mov")
        return self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, edit)}
        )

    def day_8(self, edit=DAY_1):
        """Day 8 a week on: the window's first sitting was a week ago, so this run prepares days 8 to 14."""
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        return self.run_ok(
            {fakes.draft_path(8): fakes.filming_draft(8), fakes.edit_path(8): fakes.edit_record(8, edit)}
        )

    def test_footage_of_an_approved_shot_becomes_a_finished_asset_in_the_day_s_post(self):
        before_any = self.day_1
        queue = before_any()
        before = fakes.tree_digest(self.footage)
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual((post["day"], post["id"]), (1, "20261011-post-w1-day-01"))
        self.assertRegex(post["asset"], r"^assets/window-1/day-01-[0-9a-f]{12}\.mp4$")
        self.assertEqual(post["edit"], "drafts/edits/window-1/day-01.json")
        self.assertEqual(len(post["asset_sha256"]), 64)
        made = self.asset(post)
        self.assertEqual(made["inputs"], [str(self.footage / "window-1" / "d01-s1.mov")])
        self.assertEqual((made["width"], made["height"], made["fps"], made["duration"]), (1080, 1920, 30, 10.0))
        self.assertIn(
            "Dialogue: 0,0:00:00.00,0:00:03.00,Text,,0,0,0,,Open it and the session is already waiting.", made["text"]
        )
        self.assertIn("Dialogue: 0,0:00:08.00,0:00:10.00,Text,,0,0,0,,Real phone, no cuts.", made["text"])
        text = self.item(post)
        self.assertEqual(exchange.check_item(text, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertIn(f"asset: {post['asset']}\n", text)
        self.assertIn("**Video file**\n", text)
        self.assertIn(
            f"- `{post['asset']}`, under gr0wthlab's `ledger/`: 10.00s, 1080x1920 (9:16), 30 frames a second, no"
            f" sound. SHA-256 `{post['asset_sha256']}`.",
            text,
        )
        self.assertIn(
            "- Cut by `drafts/edits/window-1/day-01.json` from the Founder's footage; nothing in it is generated:", text
        )
        self.assertIn("| 0-10s | d01-s1 | `window-1/d01-s1.mov` | 2s | 12s | as recorded |", text)
        self.assertIn(
            "- Checked: measured 1080x1920 (9:16) at 30 frames a second; d01-s1, which may not be cut, is one unbroken"
            " source range; every cut plays at the speed it was recorded at; day 8, its pair's other leg, has no video"
            " to compare with yet.",
            text,
        )
        self.assertIn(
            f"- Its video: `{post['asset']}`, in gr0wthlab's ledger, cut by `drafts/edits/window-1/day-01.json`", text
        )
        report = self.report()
        self.assertIn(
            f"| 1 | d01-s1 | finished | `{post['asset']}`, 10.00s, 1080x1920, 30 fps, no sound, rendered this run |",
            report,
        )
        self.assertIn("- Post Drafts: 1 queued.", report)
        self.assertIn("| 1 | P01 / AB-1 leg A | queued | `20261011-post-w1-day-01`; with its finished video |", report)
        self.assertRegex(
            report,
            r"- filming: checked=3 acted=1 note=plan approved as [^\n]*; 1 asset planned, 1 footage file measured;"
            r" edits: 1 finished",
        )
        # The asset's own record holds everything needed to rebuild it, and the footage place is as it was.
        record = json.loads((self.ledger() / post["asset_record"]).read_text(encoding="utf-8"))
        self.assertEqual((record["asset"], record["sha256"], record["day"]), (post["asset"], post["asset_sha256"], 1))
        self.assertEqual(
            record["edit"]["record"]["segments"],
            [
                {
                    "shot": "d01-s1",
                    "source": "window-1/d01-s1.mov",
                    "in": 2.0,
                    "out": 12.0,
                    "speed": 1.0,
                    "fit": "contain",
                    "mute": False,
                }
            ],
        )
        self.assertEqual(record["cuts"][0]["sha256"], before["window-1/d01-s1.mov"][0])
        self.assertEqual(
            [overlay["text"] for overlay in record["overlays"]][0], "Open it and the session is already waiting."
        )
        self.assertEqual(record["tooling"], fakes.FAKE_FFMPEG_VERSION)
        self.assertEqual(fakes.tree_digest(self.footage), before)
        # Finished video never enters git: the folder is ignored.
        ignored = fakes.git(self.repo, "status", "--porcelain", "--ignored", "--", "ledger/assets", env=self.env)
        self.assertEqual(ignored, "!! ledger/assets/")

    def test_the_legs_of_a_pair_are_cut_from_the_same_source_ranges_and_differ_only_in_the_hook(self):
        self.day_1()
        before = fakes.tree_digest(self.footage)
        queue = self.day_8()
        day_1, day_8 = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 8))
        first, second = self.asset(day_1), self.asset(day_8)
        for key in ("inputs", "seeks", "graph", "width", "height", "fps", "duration", "sound"):
            self.assertEqual(first[key], second[key], key)
        ours, theirs = first["text"].splitlines(), second["text"].splitlines()
        differing = [(a, b) for a, b in zip(ours, theirs) if a != b]
        self.assertEqual(len(ours), len(theirs))
        self.assertEqual(
            differing,
            [
                (
                    "Dialogue: 0,0:00:00.00,0:00:03.00,Text,,0,0,0,,Open it and the session is already waiting.",
                    "Dialogue: 0,0:00:00.00,0:00:03.00,Text,,0,0,0,,The session is on screen before you decide.",
                )
            ],
        )
        self.assertNotEqual(day_1["asset_sha256"], day_8["asset_sha256"])
        self.assertIn("the same source ranges as day 1's leg from the first frame to the last", self.item(day_8))
        self.assertEqual(fakes.tree_digest(self.footage), before)

    def test_a_leg_that_differs_beyond_the_opening_has_no_asset_and_no_post(self):
        self.day_1()
        queue = self.day_8(("d01-s1", "d01-s1.mov", 3, 13))
        self.assertEqual([entry["day"] for entry in queue["open"] if entry["kind"] == "post"], [1])
        self.assertEqual(len(list((self.ledger() / "assets" / "window-1").glob("day-08-*"))), 0)
        report = self.report()
        self.assertIn("| 8 | P01 / AB-1 leg B | blocked |", report)
        self.assertIn(
            "- pair-legs: its source ranges differ from day 1's leg (`drafts/edits/window-1/day-01.json`) from its"
            " first frame: this leg shows `window-1/d01-s1.mov` 3-13s, that leg `window-1/d01-s1.mov` 2-12s",
            report,
        )
        notice = self.notice()
        self.assertIn(
            "- Day 8 (`drafts/posts/window-1/day-08.md`): pair-legs: its source ranges differ from day 1's leg", notice
        )
        self.assertEqual(notice.count("pair-legs"), 1)  # named once, with the day's post
        # Corrected, the leg is cut and offered.
        queue = self.run_ok({fakes.edit_path(8): fakes.edit_record(8, DAY_1)})
        self.assertEqual(sorted(entry["day"] for entry in queue["open"] if entry["kind"] == "post"), [1, 8])

    def test_a_cut_inside_a_shot_that_may_not_be_cut_renders_nothing_and_withdraws_the_day_s_post(self):
        self.approved_plan()
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        self.assertIn(
            "**Video file**: none yet (no footage yet for shot d01-s1). Approving this item approves its copy and its"
            " beat plan; the finished video comes back with this copy for approval.",
            self.item(post),
        )
        self.clip("d01-s1.mov")
        cut = fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 1, 5), ("d01-s1", "d01-s1.mov", 7, 13))
        queue = self.run_ok({fakes.edit_path(1): cut})
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertFalse((self.ledger() / "assets").exists())
        withdrawn = next(entry for entry in queue["closed"] if entry["id"] == post["id"])
        self.assertTrue(withdrawn["withdrawn"])
        notice = self.notice()
        self.assertIn(
            "no-cut: shot d01-s1 may not be cut (the Format: no cuts), and this edit shows it as 2 source ranges, not"
            " one unbroken range",
            notice,
        )
        self.assertIn(
            f"- The open post `{post['id']}` for day 1 is withdrawn, since its edit record does not pass.", notice
        )
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        posts_open = [entry for entry in queue["open"] if entry["kind"] == "post"]
        self.assertEqual(len(posts_open), 1)
        self.assertIn("asset", posts_open[0])

    def test_a_shot_with_no_footage_has_no_asset_and_is_named_in_the_report_and_a_notice(self):
        self.approved_plan(days=(2, 9))
        self.clip("d02-s1a-take-1.mov", 6.0, 1080, 1920, 30, sound=True)
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2)})
        self.assertFalse((self.ledger() / "assets").exists())
        # Its copy is still offered, saying there is no video yet.
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual((post["day"], "asset" in post), (2, False))
        self.assertIn("**Video file**: none yet (no footage yet for shot d02-s2).", self.item(post))
        report = self.report()
        self.assertIn("| 2 | d02-s1, d02-s2 | no edit record | no footage yet for shot d02-s2 |", report)
        notice = self.notice()
        self.assertIn("- Day 2 has no video: shot d02-s2 has no footage, and nothing is substituted.", notice)
        self.assertIn("not ready: no footage yet for shot d02-s2", self.brief())
        self.assertNotIn("Day 9", notice)  # not due this run
        # An edit record written all the same, without the shot, is blocked: nothing stands in for the shot.
        only = fakes.edit_record(2, ("d02-s1", "d02-s1a-take-1.mov", 0, 6))
        self.run_ok({fakes.edit_path(2): only})
        self.assertIn("| 2 | d02-s1, d02-s2 | not cut | no footage yet for shot d02-s2 |", self.report())
        self.assertFalse((self.ledger() / "assets").exists())

    def test_a_day_with_no_footage_at_all_is_named_once_footage_has_begun_to_arrive(self):
        self.approved_plan(days=(1, 3, 8, 10))
        writes = {fakes.draft_path(1): fakes.filming_draft(1)}
        self.run_ok(writes)
        self.assertNotIn("has no video", self.notice())  # nothing is filmed yet, so nothing is missing
        self.clip("d01-s1.mov")
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        notice = self.notice()
        self.assertIn("- Day 3 has no video: shot d03-s1 has no footage, and nothing is substituted.", notice)
        self.assertNotIn("Day 1 has no video", notice)
        evidence = json.loads(sorted((self.ledger() / "evidence/filming").glob("2*.json"))[-1].read_text())
        self.assertEqual(evidence["plan"]["jobs"][0]["format"], f"{ANGLES} line 8")
        self.assertEqual([day["status"] for day in evidence["days"]], ["finished", "no edit record"])

    def test_a_rendered_asset_that_does_not_measure_9_16_is_not_kept(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        (self.tools / "ffmpeg.json").write_text(json.dumps({"facts": {"width": 1920, "height": 1080}}))
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertEqual(list((self.ledger() / "assets" / "window-1").iterdir()), [])
        self.assertIn(
            "asset-shape: the rendered asset was not kept: it measures 1920x1080 (16:9), which is not 9:16",
            self.report(),
        )
        (self.tools / "ffmpeg.json").write_text(json.dumps({"facts": {"width": 720, "height": 1280}}))
        self.run_ok()
        self.assertIn("it measures 720x1280, not the expected 1080x1920", self.report())
        (self.tools / "ffmpeg.json").unlink()
        queue = self.run_ok()
        self.assertEqual(len([entry for entry in queue["open"] if entry["kind"] == "post"]), 1)

    def test_an_edit_record_cannot_bring_in_anything_from_outside_the_footage_place(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        outside = fakes.fake_clip(self.root / "elsewhere" / "d01-s1.mov", 14.0)
        (self.footage / "window-1" / "d01-s1-linked.mov").symlink_to(outside)
        for source in (str(outside), "window-1/../../elsewhere/d01-s1.mov", "window-1/d01-s1-linked.mov"):
            with self.subTest(source=source):
                edit = fakes.edit_record(1, ("d01-s1", source, 2, 12))
                queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): edit})
                self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
                self.assertFalse((self.ledger() / "assets").exists())
                self.assertIn("footage-place:", self.report())
        self.assertIn(
            "- Left alone in the footage place: `window-1/d01-s1-linked.mov` (a link, which is never followed).",
            self.report(),
        )

    def test_missing_tooling_skips_the_edit_with_the_reason_and_the_run_still_finishes(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.root / "no-ffmpeg")
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        problem = f"ffmpeg is not an executable at `{self.root}/no-ffmpeg`"
        report = self.report()
        self.assertIn(f"| Video tooling | skipped | {problem}; every edit is skipped until it can be used |", report)
        self.assertIn(f"| 1 | d01-s1 | not cut | the video tooling cannot be used ({problem}) |", report)
        self.assertIn("- The run finished.", report)
        self.assertIn("| Filming plan and edits | complete |", report)
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        self.assertIn(f"**Video file**: none yet (the video tooling cannot be used ({problem})).", self.item(post))
        notice = self.notice()
        self.assertIn(f"- The edit of day 1 was skipped: {problem}.", notice)
        self.assertIn("not ready: the video tooling cannot be used", self.brief())
        # Once the tooling is back, the same record is cut and the post replaced by one that shows the video.
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.tools / "ffmpeg")
        queue = self.run_ok()
        shown = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual((shown["supersedes"], "asset" in shown), (post["id"], True))

    def test_missing_tooling_names_every_day_whose_edit_was_skipped(self):
        self.approved_plan(days=(1, 2, 8, 9))
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.root / "no-ffmpeg")
        day_2 = fakes.edit_record(
            2,
            ("d02-s1", "d02-s1a-take-1.mov", 1, 4),
            ("d02-s2", "d02-s2.mov", 2, 13),
            ("d02-s1", "d02-s1-closing.mov", 5, 11),
        )
        self.run_ok(
            {
                fakes.draft_path(1): fakes.filming_draft(1),
                fakes.edit_path(1): fakes.edit_record(1, DAY_1),
                fakes.draft_path(2): fakes.filming_draft(2),
                fakes.edit_path(2): day_2,
            }
        )
        problem = f"ffmpeg is not an executable at `{self.root}/no-ffmpeg`"
        self.assertIn(f"- The edits of days 1 and 2 were skipped: {problem}.", self.notice())

    def test_tooling_that_goes_missing_leaves_a_post_that_already_shows_its_video_as_it_is(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.root / "no-ffmpeg")
        queue = self.run_ok()
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "post"], [post["id"]])
        self.assertIn("its video was not cut again (the video tooling cannot be used", self.report())

    def test_nothing_is_cut_before_the_plan_is_approved(self):
        self.run_ok(days=(1, 8))
        self.clip("d01-s1.mov")
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        self.assertFalse((self.ledger() / "assets").exists())
        self.assertIn(f"| 1 | d01-s1 | not cut | the filming plan `{PLAN}` is not approved yet |", self.report())
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn(f"**Video file**: none yet (the filming plan `{PLAN}` is not approved yet).", self.item(post))
        self.decide(PLAN, "approve")
        queue = self.run_ok()
        self.assertIn("asset", next(entry for entry in queue["open"] if entry["kind"] == "post"))

    def test_an_unchanged_asset_is_kept_not_rendered_again_and_its_post_stands(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        asset = self.ledger() / post["asset"]
        stamp = asset.stat().st_mtime_ns
        queue = self.run_ok()
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "post"], [post["id"]])
        self.assertEqual(asset.stat().st_mtime_ns, stamp)
        report = self.report()
        self.assertIn("kept from an earlier run", report)
        self.assertIn(
            "| 1 | P01 / AB-1 leg A | kept | `20261011-post-w1-day-01`; its Draft is unchanged and passes, and so"
            " is its video |",
            report,
        )
        self.assertRegex(report, r"- filming: checked=3 acted=0 ")
        # A changed edit is another asset under another name, and replaces the post; the earlier file is left.
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13))})
        replaced = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual(replaced["supersedes"], post["id"])
        self.assertNotEqual(replaced["asset"], post["asset"])
        self.assertTrue(asset.is_file())

    def test_a_day_whose_copy_was_approved_before_its_video_is_offered_once_more_with_the_video(self):
        self.approved_plan()
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        copy = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(copy["id"], "approve")
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertIn(
            "| 1 | P01 / AB-1 leg A | approved earlier | `20261011-post-w1-day-01`; the Founder approved it, so it"
            " is not asked again |",
            self.report(),
        )
        self.clip("d01-s1.mov")
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        video_post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotEqual(video_post["id"], copy["id"])
        self.assertIn("asset", video_post)
        self.assertNotIn("supersedes", video_post)
        self.assertIn(
            f"- You approved this day's copy as `{copy['id']}` before its video existed; this item adds the video.",
            self.item(video_post),
        )
        self.assertIn(f"with its finished video, its copy was approved as `{copy['id']}`", self.report())
        self.assertEqual(self.run_ok()["open"][0]["id"], video_post["id"])
        self.decide(video_post["id"], "approve")
        for _ in range(2):
            queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13))})
            self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertEqual(len(list((self.ledger() / "assets" / "window-1").iterdir())), 1)
        self.assertIn("the Founder approved its post with its video, so nothing is cut again", self.report())

    def test_a_draft_changed_after_its_copy_was_approved_holds_the_day_and_cuts_no_video(self):
        self.approved_plan()
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        copy = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(copy["id"], "approve")
        self.clip("d01-s1.mov")
        changed = fakes.filming_draft(1).replace("Real phone, no cuts.", "One real phone, no cuts.")
        self.assertNotEqual(changed, fakes.filming_draft(1))
        queue = self.run_ok({fakes.draft_path(1): changed, fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertFalse((self.ledger() / "assets").exists())
        why = f"the Founder approved its copy as `{copy['id']}`, and its Draft is no longer that copy"
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | approved earlier | `{copy['id']}`; the Founder approved its copy; its Draft is"
            " no longer that copy, so no video is cut for it |",
            report,
        )
        self.assertIn(f"| 1 | d01-s1 | not cut | {why} |", report)
        self.assertIn(f"- Day 1's video was not cut: {why}.", self.notice())
        # A Draft that is gone is not the approved copy either.
        (self.workspace() / fakes.draft_path(1)).unlink()
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertIn(
            f"| 1 | d01-s1 | not cut | the Founder approved its copy as `{copy['id']}`, and its Draft is gone |",
            self.report(),
        )
        self.assertFalse((self.ledger() / "assets").exists())
        # With the approved copy back, its video is cut and offered with it.
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        video_post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn("asset", video_post)
        self.assertEqual(video_post["draft_sha256"], copy["draft_sha256"])

    def test_a_post_rejected_with_its_video_is_asked_again_only_once_something_changes(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(post["id"], "reject", reason="Start the recording a second later.")
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertIn("the Founder rejected this Draft, so it is not asked again until it changes", self.report())
        # A run that cannot cut the video has nothing new to ask: the same copy alone is the Draft the Founder
        # rejected, whether the tooling is missing, the footage is away for filming again, or the edit record is gone.
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.root / "no-ffmpeg")
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | not queued again | `{post['id']}`; the Founder rejected", self.report()
        )
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.tools / "ffmpeg")
        clip = self.footage / "window-1" / "d01-s1.mov"
        held = clip.read_bytes()
        clip.unlink()
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        clip.write_bytes(held)
        record = self.workspace() / fakes.edit_path(1)
        record.unlink()
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertIn("| 1 | P01 / AB-1 leg A | not queued again |", self.report())
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13))})
        again = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotEqual(again["asset_sha256"], post["asset_sha256"])

    def test_footage_that_changes_while_the_run_works_is_not_cut(self):
        self.approved_plan()
        clip = self.clip("d01-s1.mov")
        launch = cycle.launcher.run

        def agent(*args, **kwargs):
            result = launch(*args, **kwargs)
            fakes.fake_clip(clip, 20.0)
            return result

        fakes.behave(
            self.codex_dir,
            {"write": {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}},
        )
        with mock.patch.object(cycle.launcher, "run", agent):
            code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=5))
        self.assertEqual(code, 0, out)
        changed = "`window-1/d01-s1.mov` changed while the run was working, so nothing was cut from it"
        self.assertIn(f"| 1 | d01-s1 | not cut | {changed}; the next run measures it again |", self.report())
        self.assertIn(f"- Day 1's video was not cut: {changed}; the next run measures it again.", self.notice())
        self.assertFalse((self.ledger() / "assets").exists())
        # The record passed, so nothing is blocked: the copy is offered, saying why it has no video yet.
        post = next(entry for entry in self.queue()["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        self.assertIn(f"**Video file**: none yet ({changed}; the next run measures it again).", self.item(post))
        self.assertNotIn("blocked", self.report().split("## Post Drafts")[1].split("## Filming")[0])

    def test_a_render_that_fails_holds_the_day_names_the_failure_and_leaves_an_open_post_standing(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        kept = (self.ledger() / post["asset"]).read_bytes()
        failure = "ffmpeg did not finish the render (Error opening output files)"
        (self.tools / "ffmpeg.json").write_text(json.dumps({"fail": "Error opening output files"}))
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13))})
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "post"], [post["id"]])
        self.assertEqual([path.read_bytes() for path in (self.ledger() / "assets" / "window-1").iterdir()], [kept])
        report = self.report()
        self.assertIn(f"| 1 | d01-s1 | not cut | {failure} |", report)
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; its video was not cut again ({failure}); the open item"
            " stands |",
            report,
        )
        self.assertIn("- The run finished.", report)
        notice = self.notice()
        self.assertIn(f"- Day 1's video was not cut: {failure}.", notice)
        self.assertNotIn("withdrawn", notice)
        self.assertNotIn("edit record does not pass", notice)
        # Once the tooling renders again, the same record is cut and its post replaces the one that stood.
        (self.tools / "ffmpeg.json").unlink()
        queue = self.run_ok()
        shown = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual(shown["supersedes"], post["id"])
        self.assertNotEqual(shown["asset_sha256"], post["asset_sha256"])

    def test_a_render_that_fails_before_any_post_is_open_offers_the_copy_with_the_failure_named(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        (self.tools / "ffmpeg.json").write_text(json.dumps({"fail": "Error opening output files"}))
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        failure = "ffmpeg did not finish the render (Error opening output files)"
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        self.assertIn(f"**Video file**: none yet ({failure}).", self.item(post))
        self.assertIn(f"- Day 1's video was not cut: {failure}.", self.notice())
        self.assertIn("- The run finished.", self.report())
        self.assertEqual(list((self.ledger() / "assets" / "window-1").iterdir()), [])

    def test_an_asset_whose_record_cannot_be_written_holds_the_day_and_blocks_nothing(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        (self.ledger() / "evidence" / "filming" / "assets").write_text("in the way of the asset records")
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        failure = "a file could not be read or written while it was cut ("
        self.assertIn(f"| 1 | d01-s1 | not cut | {failure}", self.report())
        self.assertIn(f"- Day 1's video was not cut: {failure}", self.notice())
        self.assertIn("**Video file**: none yet (a file could not be read or written", self.item(post))

    def test_footage_that_cannot_be_measured_is_named_and_never_called_missing(self):
        self.approved_plan()
        broken = self.footage / "window-1" / "d01-s1.mov"
        broken.parent.mkdir(parents=True)
        broken.write_text("half of a file still being copied")
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        why = "the footage of shot d01-s1 could not be measured"
        report = self.report()
        self.assertIn(f"| 1 | d01-s1 | no edit record | {why} |", report)
        self.assertIn(
            "- Footage that could not be measured: `window-1/d01-s1.mov` (ffprobe could not read it (", report
        )
        brief = self.brief().split("## Filming")[1]
        self.assertIn(f"| `window-1/d01-s1.mov` for d01-s1: could not be measured | not ready: {why} |", brief)
        self.assertIn("- `window-1/d01-s1.mov` could not be measured (ffprobe could not read it (", brief)
        notice = self.notice()
        self.assertIn(f"- Day 1 has no video: {why}, and nothing is substituted.", notice)
        self.assertIn(
            "- `window-1/d01-s1.mov` in the footage place could not be measured: ffprobe could not read it (", notice
        )
        for text in (report, brief, notice):
            self.assertNotIn("no footage yet", text)
            self.assertNotIn("has no footage", text)
            self.assertNotIn("none yet |", text)
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn(f"**Video file**: none yet ({why}).", self.item(post))
        # An edit record written all the same cannot use the file.
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        self.assertIn(f"| 1 | d01-s1 | not cut | {why} |", self.report())
        self.assertFalse((self.ledger() / "assets").exists())

    def test_a_video_is_cut_only_from_a_draft_that_passes(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        blocked = fakes.filming_draft(1).replace("From the home screen", "No grind: from the home screen")
        self.run_ok({fakes.draft_path(1): blocked, fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        self.assertFalse((self.ledger() / "assets").exists())
        self.assertIn(
            "| 1 | d01-s1 | not cut | its post Draft did not pass its checks, and a video is cut only from a Draft"
            " that passes |",
            self.report(),
        )

    def test_a_day_with_an_edit_record_and_no_checked_draft_gets_the_reason_its_post_got(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        report = self.report()
        self.assertIn("| no Draft | no Draft at `drafts/posts/window-1/day-01.md` |", report)
        self.assertIn(
            "| 1 | d01-s1 | not cut | its post Draft was not checked (no Draft at `drafts/posts/window-1/day-01.md`),"
            " and a video is cut only from a Draft that passes |",
            report,
        )
        self.assertNotIn("did not pass its checks", report)
        with mock.patch.object(cycle.posts, "take", side_effect=OSError("the disk is full")):
            self.run_ok()
        report = self.report()
        self.assertIn("- Post Drafts: not taken in: the disk is full", report)
        self.assertIn(
            "| 1 | d01-s1 | not cut | the post Drafts were not taken in this run, and a video is cut only from a Draft"
            " that passes |",
            report,
        )
        self.assertNotIn("did not pass its checks", report)
        self.assertFalse((self.ledger() / "assets").exists())

    def test_a_day_whose_open_post_is_kept_unchecked_gets_that_reason_for_its_video_too(self):
        self.approved_plan()
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.clip("d01-s1.mov")
        rules = self.mandu / "projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
        rules.write_text("not the brand rules", encoding="utf-8")
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "post"], [post["id"]])
        kept = "not checked again, since brand-rules.json could not be used; the open item stands"
        report = self.report()
        self.assertIn(f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; {kept} |", report)
        self.assertIn(
            f"| 1 | d01-s1 | not cut | its post Draft was not checked ({kept}), and a video is cut only from a Draft"
            " that passes |",
            report,
        )
        self.assertNotIn("did not pass its checks", report)
        self.assertFalse((self.ledger() / "assets").exists())

    def test_a_day_approved_with_its_video_is_settled_for_the_agent_and_never_named_as_unfilmed(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(post["id"], "approve")
        queue = self.run_ok()
        settled = (
            "the Founder approved its post with its video, so nothing is cut again and its edit record stays as it is"
        )
        brief = self.brief().split("## Filming")[1]
        self.assertIn(f"| not ready: {settled} |", brief)
        self.assertNotIn("| ready |", brief)
        self.assertIn("- No day is ready for an edit record this run.", brief)
        code, text = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 0, text)
        self.assertIn(f"SKIP day 1: no edit record is due: {settled}", text)
        self.assertIn("1 day checked, 0 with problems", text)
        self.assertIn(f"| 1 | d01-s1 | not cut | {settled} |", self.report())
        # Its footage put away afterwards, with another leg's take still there, leaves no video missing.
        clip = self.footage / "window-1" / "d01-s1.mov"
        clip.rename(clip.with_name("d01-s1b.mov"))
        queue = self.run_ok()
        told = [entry for entry in queue["open"] if entry["published_by_run"] == queue["updated_by_run"]]
        self.assertEqual(told, [])
        self.assertIn(f"| 1 | d01-s1 | not cut | {settled} |", self.report())
        self.assertNotIn("has no video", self.report())

    def test_check_edits_gives_the_agent_the_launcher_s_verdict_without_opening_the_footage(self):
        self.approved_plan(days=(1, 2, 8, 9))
        self.clip("d01-s1.mov")
        self.clip("d02-s1a-take-1.mov", 6.0, 1080, 1920, 30, sound=True)
        launch, seen = cycle.launcher.run, []

        def agent(*args, **kwargs):
            result = launch(*args, **kwargs)
            shutil.move(str(self.footage), str(self.root / "footage-away"))  # the sandbox cannot open it either
            seen.append(self.check_edits(kwargs["run_id"]))
            shutil.move(str(self.root / "footage-away"), str(self.footage))
            return result

        writes = {
            fakes.draft_path(1): fakes.filming_draft(1),
            fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 1, 5), ("d01-s1", "d01-s1.mov", 7, 13)),
        }
        fakes.behave(self.codex_dir, {"write": writes})
        with mock.patch.object(cycle.launcher, "run", agent):
            code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=3))
        self.assertEqual(code, 0, out)
        code, text = seen[0]
        self.assertEqual(code, 1, text)
        self.assertIn("BLOCKED day 1: drafts/edits/window-1/day-01.json", text)
        self.assertIn("  - no-cut: shot d01-s1 may not be cut", text)
        self.assertIn("SKIP day 2: no edit record is due: no footage yet for shot d02-s2", text)
        self.assertIn("2 days checked, 1 with problems", text)
        fakes.behave(self.codex_dir, {"write": {fakes.edit_path(1): fakes.edit_record(1, DAY_1)}})
        seen.clear()
        with mock.patch.object(cycle.launcher, "run", agent):
            code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=4))
        code, text = seen[0]
        self.assertEqual(code, 0, text)
        self.assertIn(
            "OK day 1: drafts/edits/window-1/day-01.json: it passes; the launcher renders and measures it", text
        )
        code, text = self.check_edits("20990101T000000Z-on-demand-0000")
        self.assertEqual(code, 1)
        self.assertIn("PROBLEM the filming record of run 20990101T000000Z-on-demand-0000 could not be read", text)

    def test_check_edits_says_when_a_ready_day_has_no_edit_record(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        code, text = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1)
        self.assertIn("PROBLEM day 1: it is ready for an edit record and has none", text)
        self.assertIn("| 1 | d01-s1 | no edit record | it is ready for an edit record and has none |", self.report())
        self.assertRegex(
            self.brief(), r"`window-1/d01-s1.mov` for d01-s1: 14.00s, 886x1920, 60 fps, no sound \| ready \|"
        )

    def test_a_finished_asset_can_be_rebuilt_from_its_record_and_the_footage(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        asset = self.ledger() / post["asset"]
        original = asset.read_bytes()
        asset.unlink()
        before = fakes.tree_digest(self.footage)
        out = io.StringIO()
        with (
            mock.patch.object(cli, "REPO_ROOT", self.repo),
            mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"),
        ):
            code = cli.rebuild_asset(post["asset_record"], self.env, self.home, out)
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(asset.read_bytes(), original)
        self.assertIn(f"`{post['asset']}` rebuilt with {fakes.FAKE_FFMPEG_VERSION}", out.getvalue())
        self.assertIn("It is byte for byte the asset its record names.", out.getvalue())
        self.assertEqual(fakes.tree_digest(self.footage), before)
        # A render that is not the file the record names never takes the asset's place: one other tooling encodes
        # differently, one that measures wrong, and one that does not finish all leave what is there as it was.
        for behavior, said in (
            ({"facts": {"encoder": "another build"}}, f"not the {post['asset_sha256']} its record names"),
            ({"facts": {"width": 1920, "height": 1080}}, "PROBLEM it measures 1920x1080 (16:9), which is not 9:16"),
            ({"fail": "Error opening output files"}, "was not rebuilt: ffmpeg did not finish the render"),
        ):
            with self.subTest(behavior=behavior):
                (self.tools / "ffmpeg.json").write_text(json.dumps(behavior))
                out = io.StringIO()
                with (
                    mock.patch.object(cli, "REPO_ROOT", self.repo),
                    mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"),
                ):
                    self.assertEqual(cli.rebuild_asset(post["asset_record"], self.env, self.home, out), 1)
                self.assertIn(said, out.getvalue())
                self.assertIn("was not rebuilt", out.getvalue())
                self.assertEqual([path.name for path in asset.parent.iterdir()], [asset.name])
                self.assertEqual(asset.read_bytes(), original)
        asset.unlink()
        (self.tools / "ffmpeg.json").write_text(json.dumps({"facts": {"encoder": "another build"}}))
        out = io.StringIO()
        with mock.patch.object(cli, "REPO_ROOT", self.repo), mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"):
            self.assertEqual(cli.rebuild_asset(post["asset_record"], self.env, self.home, out), 1)
        self.assertEqual(list(asset.parent.iterdir()), [])
        (self.tools / "ffmpeg.json").unlink()
        with mock.patch.object(cli, "REPO_ROOT", self.repo), mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"):
            self.assertEqual(cli.rebuild_asset(post["asset_record"], self.env, self.home, out), 0)
        self.assertEqual(asset.read_bytes(), original)
        self.assertEqual(fakes.tree_digest(self.footage), before)
        # Footage that is no longer what the asset was cut from is refused, and so is a record outside the ledger.
        self.clip("d01-s1.mov", 15.0)
        out = io.StringIO()
        with mock.patch.object(cli, "REPO_ROOT", self.repo), mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"):
            self.assertEqual(cli.rebuild_asset(post["asset_record"], self.env, self.home, out), 1)
            self.assertIn("`window-1/d01-s1.mov` is no longer the footage this asset was cut from", out.getvalue())
            self.assertEqual(cli.rebuild_asset("../config/run.json", self.env, self.home, out), 1)


class RecutRunTest(FilmingRunCase):
    def test_the_legs_of_a_re_cut_pair_open_on_their_own_takes_and_share_everything_after(self):
        self.approved_plan(days=(2, 9))
        for name, seconds in (("d02-s1a-take-1.mov", 6.0), ("d02-s1b-take-1.mov", 6.0), ("d02-s1-closing.mov", 15.0)):
            self.clip(name, seconds, 1080, 1920, 30, sound=True)
        self.clip("d02-s2.mov", 16.0)
        tail = (("d02-s2", "d02-s2.mov", 2, 13), ("d02-s1", "d02-s1-closing.mov", 5, 11))
        day_2 = fakes.edit_record(2, ("d02-s1", "d02-s1a-take-1.mov", 1, 4), *tail)
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2), fakes.edit_path(2): day_2})
        first = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn("asset", first)
        self.assertIn("| 0-3s | d02-s1 | `window-1/d02-s1a-take-1.mov` | 1s | 4s | as recorded |", self.item(first))
        self.assertIn("with sound", self.item(first))
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        moved = fakes.edit_record(
            9, ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5), ("d02-s2", "d02-s2.mov", 4, 15), tail[1]
        )
        queue = self.run_ok({fakes.draft_path(9): fakes.filming_draft(9), fakes.edit_path(9): moved})
        self.assertEqual([entry["day"] for entry in queue["open"] if entry["kind"] == "post"], [2])
        self.assertIn(
            "pair-legs: its source ranges differ from day 2's leg (`drafts/edits/window-1/day-02.json`) after the"
            " re-cut opening",
            self.report(),
        )
        day_9 = fakes.edit_record(9, ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5), *tail)
        queue = self.run_ok({fakes.edit_path(9): day_9})
        second = next(entry for entry in queue["open"] if entry.get("day") == 9)
        self.assertIn("the same source ranges as day 2's leg after the re-cut opening", self.item(second))
        ours, theirs = self.asset(first), self.asset(second)
        self.assertEqual(ours["inputs"][1:], theirs["inputs"][1:])
        self.assertEqual(ours["seeks"][1:], theirs["seeks"][1:])
        self.assertNotEqual(ours["inputs"][0], theirs["inputs"][0])
        brief = self.brief()
        self.assertIn("20s; the same source ranges as day 2 after its opening", brief)
        day_9 = brief.split("## Filming")[1].split("| 9 |")[1].split("\n")[0]
        self.assertIn("`window-1/d02-s1b-take-1.mov` for d02-s1", day_9)
        self.assertNotIn("d02-s1a-take-1.mov", day_9)

    def test_a_reference_leg_whose_edit_record_changed_since_its_video_cannot_be_compared_with(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        writes = {
            fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13)),
            fakes.draft_path(8): fakes.filming_draft(8),
            fakes.edit_path(8): fakes.edit_record(8, DAY_1),
        }
        queue = self.run_ok(writes)
        self.assertEqual([entry["day"] for entry in queue["open"] if entry["kind"] == "post"], [1])
        self.assertIn(
            "pair-legs: day 1's edit record is no longer the one the video of `20261011-post-w1-day-01` was cut from,"
            " so this leg cannot be compared with it",
            self.report(),
        )


class RealToolingRunTest(FilmingRunCase):
    """One whole run with the real ffmpeg, where it is installed: stand-in test footage becomes two real assets."""

    def test_day_1_and_day_8_are_real_9_16_files_cut_from_the_same_frames(self):
        tooling, canvas, why = fakes.real_video_tools()
        if why:
            self.skipTest(why)
        shutil.copy(str(fakes.REPO / "config" / "platforms.json"), str(self.repo / "config" / "platforms.json"))
        for name in ("GR0WTHLAB_FFMPEG_BIN", "GR0WTHLAB_FFPROBE_BIN"):
            del self.env[name]
        self.env["PATH"] = os.environ["PATH"]
        self.approved_plan()
        fakes.make_test_clip(tooling, self.footage / "window-1" / "d01-s1.mov", 14, 886, 1920, 60)
        before = fakes.tree_digest(self.footage)
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        queue = self.run_ok(
            {fakes.draft_path(8): fakes.filming_draft(8), fakes.edit_path(8): fakes.edit_record(8, DAY_1)}
        )
        day_1, day_8 = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 8))
        for entry in (day_1, day_8):
            facts = video.probe(tooling, self.ledger() / entry["asset"], self.env)
            self.assertEqual(video.verify(facts, canvas, 10.0), [])
            self.assertEqual((facts.width, facts.height, facts.fps), (1080, 1920, 30.0))
        self.assertNotEqual(day_1["asset_sha256"], day_8["asset_sha256"])

        # Frame for frame: after the 3-second hook beat the two legs are the same picture, and before it they differ.
        def likeness(start, length):
            command = [str(tooling.ffmpeg), "-nostdin", "-hide_banner", "-ss", str(start), "-t", str(length)]
            command += ["-i", str(self.ledger() / day_1["asset"]), "-ss", str(start), "-t", str(length)]
            command += ["-i", str(self.ledger() / day_8["asset"]), "-lavfi", "ssim", "-f", "null", "-"]
            said = subprocess.run(command, capture_output=True, text=True).stderr
            return float(said.rsplit("All:", 1)[1].split()[0])

        self.assertGreater(likeness(3.2, 6.5), 0.995)
        self.assertLess(likeness(0, 2.8), 0.99)
        self.assertEqual(fakes.tree_digest(self.footage), before)


if __name__ == "__main__":
    unittest.main()
