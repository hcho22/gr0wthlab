"""The filming workflow, in whole runs with a fake Codex and fake video tooling: the plan as one Review Queue item,
the footage place only ever read, and each edit record checked, rendered, measured, and shown in its day's post."""

import collections
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, cli, cycle, exchange, filming, footage, posts, shots, video
from gr0wthlab.areas import Store
from gr0wthlab.boundary import ConfigError
from tests import fakes
from tests.test_cycle import CycleTestCase

PLAN = "20261011-filming-plan-w1"
ANGLES = "projects/RepToday/gtm/05-social-pmf/angles.md"
CALENDAR = "projects/RepToday/gtm/05-social-pmf/cadence-14-day.md"
DAY_1 = ("d01-s1", "d01-s1.mov", 2, 12)
LATER = ("d01-s1", "d01-s1.mov", 3, 13)
LEAVE = "its post keeps the video it shows while its Draft stays as it is, so leave its edit record as it is"
WHOLE = "from the first frame to the last"
OWN_CHECKS = [
    "measured 1080x1920 (9:16) at 30 frames a second",
    "d01-s1, which may not be cut, is one unbroken source range",
    "every cut plays at the speed it was recorded at",
]
FAILURE = "ffmpeg did not finish the render (Error opening output files)"


def shows(day, start):
    """What the pair check says a day's video shows of the one file of days 1, 4, and 8, from a start point on."""
    return f"day {day}'s shows `window-1/d01-s1.mov` {start}-{start + 10}s"


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
        """One more run, an hour after the last; writes is what the agent writes, days the calendar days kept.
        Whatever the run was given, it leaves the two posts of no A/B pair showing videos that differ."""
        if days is not None:
            fakes.keep_days(self.mandu, *days)
        fakes.behave(self.codex_dir, {"write": writes or {}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=self.runs))
        self.runs += 1
        self.assertEqual(code, 0, out)
        self.matched = self.pairs_shown()
        return self.queue()

    def videos(self):
        """Each calendar day whose standing post shows a video, with that post: its open one, otherwise the one the
        Founder approved."""
        queue = self.queue()
        found = {}
        for status, entries in (("approved", queue["closed"]), ("open", queue["open"])):
            for entry in entries:
                if entry["kind"] == "post" and entry["status"] == status and (status == "open" or entry.get("asset")):
                    found[entry["day"]] = entry
        return {day: entry for day, entry in found.items() if entry.get("asset")}

    def footage_shown(self, entry):
        """Every quarter second of a post's video outside its opening, as the footage file, known by its fingerprint,
        and the moment of it shown there, read from the record of the very file the post names."""
        record = json.loads((self.ledger() / entry["asset_record"]).read_text(encoding="utf-8"))
        self.assertEqual(
            (record["asset"], record["sha256"], record["day"]), (entry["asset"], entry["asset_sha256"], entry["day"])
        )
        found, clock = [], 0.0
        for cut in record["cuts"]:
            steps = round((cut["out"] - cut["in"]) / cut["speed"] * 4)
            for step in range(steps):
                at = clock + step / 4
                if not any(start <= at < end for start, end in record["opening"]):
                    found.append((cut["sha256"], cut["in"] + step / 4 * cut["speed"]))
            clock += steps / 4
        return found

    def pairs_shown(self):
        """The one rule of an A/B pair's videos, asserted on what a run left: the two posts of a pair never both
        show a video unless the two videos show the same footage outside each one's opening. Returns the pairs both
        of whose posts show a video."""
        registry = json.loads((self.repo / "config" / "products.json").read_text(encoding="utf-8"))
        kit = posts.kit_config(registry)
        legs = collections.defaultdict(list)
        for day in posts.read_kit(self.mandu, kit[1])[0].days.values() if kit else ():
            if day.pair:
                legs[day.pair].append(day.day)
        shown = self.videos()
        both = [days for days in legs.values() if len(days) == 2 and all(day in shown for day in days)]
        for first, second in both:
            self.assertEqual(
                self.footage_shown(shown[first]),
                self.footage_shown(shown[second]),
                f"the posts of days {first} and {second} show videos that differ outside their openings",
            )
        return both

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

    def check_drafts(self, run_id):
        out = io.StringIO()
        with (
            mock.patch.object(cli, "REPO_ROOT", self.repo),
            mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"),
            mock.patch.dict(os.environ, self.env),
        ):
            return cli.check_drafts(run_id, out), out.getvalue()

    def posts_open(self):
        return {entry["day"]: entry for entry in self.queue()["open"] if entry["kind"] == "post"}

    def checks_of(self, day):
        """What the latest run's filming Evidence says it checked of a day's video."""
        run = self.queue()["updated_by_run"]
        filmed = json.loads((self.ledger() / f"evidence/filming/{run}.json").read_text(encoding="utf-8"))
        return next(entry for entry in filmed["days"] if entry["day"] == day)["checks"]

    def one_week_pair(self):
        """A kit that posts both legs of AB-1 in one week, days 1 and 4, so one run can cut both, with its plan
        approved and its footage there; returns the two legs' Drafts as the agent writes them."""
        calendar = self.mandu / CALENDAR
        rows = calendar.read_text(encoding="utf-8").splitlines()
        leg_b = next(row for row in rows if row.startswith("| 8 |")).replace("| 8 |", "| 4 |", 1)
        moved = "\n".join(leg_b if row.startswith("| 4 |") else row for row in rows)
        calendar.write_text(moved + "\n", encoding="utf-8")
        self.approved_plan(days=(1, 4))
        self.clip("d01-s1.mov")
        return {
            fakes.draft_path(1): fakes.filming_draft(1),
            fakes.draft_path(4): fakes.filming_draft(8).replace("day: 8", "day: 4"),
        }

    def filming_row(self, day):
        """A day's row of the Filming table in the latest brief, which is what the agent is told of the day."""
        return self.brief().split("## Filming")[1].split(f"\n| {day} |")[1].split("\n")[0]

    def day_1_beside_other_footage(self):
        """Day 1's post, open with its video, in a window whose footage place also holds footage of day 2, so that
        footage has begun to arrive whatever becomes of day 1's own file."""
        self.approved_plan(days=(1, 2, 8))
        self.clip("d01-s1.mov")
        self.clip("d02-s2.mov", 16.0)
        self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        post = self.posts_open()[1]
        self.assertIn("asset", post)
        return post

    @staticmethod
    def both(edit):
        return {fakes.edit_path(1): fakes.edit_record(1, edit), fakes.edit_path(4): fakes.edit_record(4, edit)}


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
        self.assertIn(f"exchange: {exchange.EXCHANGE_VERSION}\n", text)
        self.assertIn("## Plan\n", text)
        self.assertIn(
            "RepToday window 1 needs footage for 10 assets, filmed in 3 sittings, for calendar days 1, 2, 3, 4, 5, 6,"
            " 7, 8, 9, 10, 11, 12, and 13. Days 8, 9, and 10 are cut from an earlier day's footage with only the"
            " opening changed, so they add no shot of their own to film; any opening take a leg records for itself is"
            " named with its shot list below.\n",
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
            "| d02-s1 | days 2 and 9 | part of 20s | founder-on-camera greeting | Camera, the Founder in frame | Not"
            " stated | The Hook, then the Draft's | The spoken lines | Not stated |",
            text,
        )
        self.assertIn(
            "| d02-s2 | days 2 and 9 | part of 20s | a screen record of the app opening | The real device running"
            " RepToday, screen recording | Yes | The Draft's | None unless a line is spoken | Yes |",
            text,
        )
        self.assertIn(
            "| d07-s1 | day 7 | 15-20s | timelapse of a whole five-minute session | Camera | No: timelapse |", text
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
            " and `d02-s1b` for day 9. The Founder is on camera in it, so a leg has no video until its own take is"
            " there. Everything after the opening is shared by both legs: record it once, in a take named without a"
            " leg letter, such as `d02-s1.mov`.",
            text,
        )
        self.assertIn('- d04, day 4 (P04): Format in `angles.md` line 11. Day 4 opens on "Airplane mode on.', text)
        self.assertIn(
            f"- Each Angle's Format, quoted in the shot lists: `{ANGLES}` lines 8, 9, 10, 11, 12, 13, and 14", text
        )
        self.assertIn("Not planned: day 14, since the calendar decides its Angle later", text)
        self.assertIn(f"- What holds for every screen recording: `{CALENDAR}` line 28", text)
        self.assertIn("Every asset is finished at 1080x1920 (9:16), so film upright.", text)
        self.assertIn("A recording of another shape is shown whole, with black beside it, and never cropped.\n", text)
        self.assertIn(
            "- Sound is not chosen in the edit: a cut that plays at the speed it was recorded at keeps its recording's"
            " sound, and a cut that plays at another speed, such as a timelapse, is silent.\n",
            text,
        )
        # Nothing but the kit text a shot list uses: no pain, signal, or kill criterion is copied.
        for strategy in ("Pain 1", "Watched-full rate", "Bottom quartile", "holds viewers"):
            self.assertNotIn(strategy, text)
        self.assertLess(len(text), exchange.MAX_ITEM_CHARS)

    def test_a_plan_for_one_asset_or_one_day_reads_in_the_singular(self):
        queue = self.run_ok(days=(1, 4, 8))
        text = self.item(next(entry for entry in queue["open"] if entry["kind"] == "filming-plan"))
        self.assertIn(
            "RepToday window 1 needs footage for 2 assets, filmed in 1 sitting, for calendar days 1, 4, and 8. Day 8"
            " is cut from an earlier day's footage with only the opening changed, so it adds no shot of its own to"
            " film; any opening take a leg records for itself is named with its shot list below.\n",
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
        # Its reason is counted as filming's own, in the brief, the run report, and the learning ledger.
        self.assertIn(f'- `{PLAN}` (filming): "Split the screen recordings over two evenings."', self.brief())
        self.assertIn("- filming: 1 rejection, 0 of 1 coded.", report)
        learned = json.loads((self.ledger() / "evidence/learning/ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(list(learned["workflows"]), ["filming"])
        self.assertEqual([(reason["item"], reason["workflow"]) for reason in learned["reasons"]], [(PLAN, "filming")])

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

    def test_a_plan_filed_in_other_words_stands_since_a_plan_is_compared_by_what_must_be_filmed(self):
        now = (
            "so they add no shot of their own to film; any opening take a leg records for itself is named with its"
            " shot list below."
        )
        before = "so they film nothing new."
        current = filming.plan_item

        def earlier(made, previous=None):
            item = current(made, previous)
            self.assertIn(now, item.body)
            return exchange.Item(item.fields, item.ask, item.body.replace(now, before), item.touches, item.evidence)

        with mock.patch.object(filming, "plan_item", earlier):
            queue = self.run_ok()
        entry = next(entry for entry in queue["open"] if entry["kind"] == "filming-plan")
        filed = self.item(entry)
        self.assertIn(before, filed)
        self.assertNotIn(now, filed)
        # The launcher words the plan differently now, and what must be filmed is the same: nothing is filed again.
        queue = self.run_ok()
        self.assertEqual([entry["id"] for entry in self.entries("filming-plan")], [PLAN])
        standing = next(entry for entry in queue["open"] if entry["kind"] == "filming-plan")
        self.assertEqual(standing["filming_sha256"], entry["filming_sha256"])
        self.assertEqual(standing["filming_jobs"], entry["filming_jobs"])
        self.assertEqual(self.item(standing), filed)
        self.assertIn(f"- Filming plan: open as `{PLAN}`.", self.report())
        # Approved in its earlier words, it is the approval of every job it holds.
        self.decide(PLAN, "approve")
        self.clip("d01-s1.mov")
        self.run_ok()
        self.assertEqual([entry["status"] for entry in self.entries("filming-plan")], ["approved"])
        self.assertIn(f"- Filming plan: approved as `{PLAN}`; never asked again.", self.report())
        self.assertRegex(self.brief().split("## Filming")[1], r"\| 1 \|[^\n]*\| ready \|")

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
        # The kit then changes another Format. The plan filed for it replaces the plan the Founder approved, and
        # says what changed since that one, not since the plan that was withdrawn before it was decided.
        other = "12s screen record, on-screen text only"
        self.assertEqual(angles.read_text(encoding="utf-8").count(other), 1)
        angles.write_text(angles.read_text(encoding="utf-8").replace(other, "14s screen record, on-screen text only"))
        queue = self.run_ok()
        plans = [entry for entry in queue["open"] if entry["kind"] == "filming-plan"]
        self.assertEqual([entry["supersedes"] for entry in plans], [PLAN])
        self.assertNotIn(plans[0]["id"], (PLAN, f"{PLAN}-2"))
        self.assertIn(
            f"This plan replaces `{PLAN}`, which you approved, because the kit changed what must be filmed: d03"
            " changed.",
            self.item(plans[0]),
        )

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

    def test_a_pair_leg_needs_a_take_both_legs_can_use_wherever_the_legs_share_their_footage(self):
        tooling = video.find(self.env)
        parsed, roles = fakes.filming_kit(self.root / "kit")
        jobs = {job.key: job for job in shots.requirements(parsed, roles["calendar"]).jobs}
        for name in ("d01-s1a.mov", "d02-s1a.mov", "d02-s2a.mov", "d04-s1a.mov"):
            self.clip(name)
        known = {"d01-s1", "d02-s1", "d02-s2", "d04-s1"}
        found = footage.read(self.footage, 1, known, tooling, self.env)
        self.assertEqual(filming.lacking(found, jobs["d01"].shots, "A", False), ([], [], ["d01-s1"], []))
        self.assertEqual(filming.lacking(found, jobs["d01"].shots, "B", False), (["d01-s1"], [], [], []))
        # In a re-cut pair the first shot of several can be the leg's own opening take; every other shot is shared.
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "A", True), ([], [], ["d02-s2"], []))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], "A", True), ([], [], ["d02-s1"], []))
        self.assertEqual(filming.lacking(found, jobs["d04"].shots, None, False), ([], [], [], []))
        self.clip("d02-s2.mov")
        self.clip("d01-s1-take-2.mov")
        found = footage.read(self.footage, 1, known, tooling, self.env)
        self.assertEqual(filming.lacking(found, jobs["d01"].shots, "A", False), ([], [], [], []))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "A", True), ([], [], [], []))
        # A shared take that is there and could not be measured is unmeasured footage, never a file still to film.
        (self.footage / "window-1" / "d02-s1.mov").write_text("half of a file still being copied")
        found = footage.read(self.footage, 1, known, tooling, self.env)
        self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], "A", True), ([], ["d02-s1"], [], []))
        # The other leg has no take of its own beside it, so it is told of that take as well.
        self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], "B", True), ([], ["d02-s1"], [], ["d02-s1"]))

    def test_a_re_cut_leg_needs_its_own_opening_take_only_where_the_founder_is_on_camera_in_it(self):
        tooling = video.find(self.env)
        parsed, roles = fakes.filming_kit(self.root / "kit")
        jobs = {job.key: job for job in shots.requirements(parsed, roles["calendar"]).jobs}
        self.assertEqual([shot.kind for shot in jobs["d02"].shots], ["founder on camera", "screen recording"])
        self.assertEqual([shot.kind for shot in jobs["d01"].shots], ["screen recording"])
        for name in ("d01-s1.mov", "d02-s1.mov", "d02-s2.mov"):
            self.clip(name)
        known = {"d01-s1", "d02-s1", "d02-s2"}
        found = footage.read(self.footage, 1, known, tooling, self.env)
        # Each leg's Hook is said in the first shot, so each leg needs its own take of it, whatever follows.
        for leg in ("A", "B"):
            self.assertEqual(filming.lacking(found, jobs["d02"].shots, leg, True), ([], [], [], ["d02-s1"]))
            self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], leg, True), ([], [], [], ["d02-s1"]))
            # A pair that is not re-cut, and one that opens on a screen recording, need the shared take alone.
            self.assertEqual(filming.lacking(found, jobs["d02"].shots, leg, False), ([], [], [], []))
            self.assertEqual(filming.lacking(found, jobs["d01"].shots, leg, True), ([], [], [], []))
        self.clip("d02-s1a.mov")
        found = footage.read(self.footage, 1, known, tooling, self.env)
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "A", True), ([], [], [], []))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "B", True), ([], [], [], ["d02-s1"]))
        # A leg's own take that is there and could not be measured is unmeasured footage, never a take still to film.
        (self.footage / "window-1" / "d02-s1b.mov").write_text("half of a file still being copied")
        found = footage.read(self.footage, 1, known, tooling, self.env)
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "B", True), ([], ["d02-s1"], [], []))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "A", True), ([], [], [], []))
        # Only the other leg's take of the shot is there: the leg is still told which take of its own it lacks, and
        # where the shot is the pair's only one, that the take both legs share is not there either.
        for name in ("d02-s1.mov", "d02-s1b.mov", "d01-s1.mov"):
            (self.footage / "window-1" / name).unlink()
        self.clip("d01-s1a.mov")
        found = footage.read(self.footage, 1, known, tooling, self.env)
        self.assertEqual(sorted(found.clips), ["window-1/d01-s1a.mov", "window-1/d02-s1a.mov", "window-1/d02-s2.mov"])
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "A", True), ([], [], [], []))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots, "B", True), ([], [], [], ["d02-s1"]))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], "A", True), ([], [], ["d02-s1"], []))
        self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], "B", True), ([], [], ["d02-s1"], ["d02-s1"]))
        # A pair that opens on a screen recording is asked for no take per leg, whatever is there.
        self.assertEqual(filming.lacking(found, jobs["d01"].shots, "B", True), (["d01-s1"], [], [], []))
        # A shot with no take of any kind has no footage, and no take of it is singled out.
        (self.footage / "window-1" / "d02-s1a.mov").unlink()
        found = footage.read(self.footage, 1, known, tooling, self.env)
        for leg in ("A", "B"):
            self.assertEqual(filming.lacking(found, jobs["d02"].shots, leg, True), (["d02-s1"], [], [], []))
            self.assertEqual(filming.lacking(found, jobs["d02"].shots[:1], leg, True), (["d02-s1"], [], [], []))

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
        self.approved_plan()
        self.clip("d01-s1.mov")
        before = fakes.tree_digest(self.footage)
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
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
            [{"shot": "d01-s1", "source": "window-1/d01-s1.mov", "in": 2.0, "out": 12.0, "speed": 1.0}],
        )
        self.assertEqual(
            {key: record["cuts"][0][key] for key in ("shot", "source", "in", "out", "speed")},
            record["edit"]["record"]["segments"][0],
        )
        self.assertEqual(
            sorted(record["cuts"][0]), ["bytes", "facts", "in", "out", "sha256", "shot", "source", "speed"]
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
        self.assertEqual(self.pairs_shown(), [[1, 8]])
        # Each video's own record says where its opening is: a pair the kit does not mark as a re-cut has none.
        for entry in (day_1, day_8):
            record = json.loads((self.ledger() / entry["asset_record"]).read_text(encoding="utf-8"))
            self.assertEqual((record["opening"], record["checks"]), ([], OWN_CHECKS))
        # The slot moves, so day 8's post is replaced by one that shows the same video. No leg counts as compared
        # without being compared: it is checked against day 1's video again, and the item says so.
        fakes.set_window(self.repo, {"slot": "20:00"})
        queue = self.run_ok()
        moved = next(entry for entry in queue["open"] if entry.get("day") == 8)
        self.assertEqual(moved["supersedes"], day_8["id"])
        self.assertIn("T20:00", moved["slot"])
        self.assertEqual((moved["asset"], moved["asset_sha256"]), (day_8["asset"], day_8["asset_sha256"]))
        same = "the same source ranges as day 1's leg from the first frame to the last"
        text = self.item(moved)
        self.assertIn(
            "- Checked: measured 1080x1920 (9:16) at 30 frames a second; d01-s1, which may not be cut, is one unbroken"
            f" source range; every cut plays at the speed it was recorded at; {same}.",
            text,
        )
        self.assertNotIn("has no video to compare with yet", text)
        # The run's own records of the leg say the same.
        run = queue["updated_by_run"]
        filmed = json.loads((self.ledger() / f"evidence/filming/{run}.json").read_text(encoding="utf-8"))
        drafted = json.loads((self.ledger() / f"evidence/post-drafts/{run}.json").read_text(encoding="utf-8"))
        for checks in (filmed["days"][0]["checks"], drafted["days"][0]["video"]["checks"]):
            self.assertEqual(checks[-1], same)
        self.assertEqual((filmed["days"][0]["day"], drafted["days"][0]["day"]), (8, 8))

    def test_a_leg_offered_again_from_the_same_edit_record_is_compared_with_its_other_leg_s_video_again(self):
        self.day_1()
        queue = self.day_8()
        day_8 = next(entry for entry in queue["open"] if entry.get("day") == 8)
        same = f"the same source ranges as day 1's leg {WHOLE}"
        # The Draft is written again, the same words in other bytes: a new post that shows the same video.
        queue = self.run_ok({fakes.draft_path(8): fakes.filming_draft(8) + "\n"})
        again = next(entry for entry in queue["open"] if entry.get("day") == 8)
        self.assertEqual(again["supersedes"], day_8["id"])
        self.assertNotEqual(again["draft_sha256"], day_8["draft_sha256"])
        self.assertEqual((again["asset"], again["asset_sha256"]), (day_8["asset"], day_8["asset_sha256"]))
        self.assertIn(f"; {same}.", self.item(again))
        self.assertNotIn("has no video to compare with yet", self.item(again))
        # The canvas changes, so the same edit record is rendered again as another file, which is compared with day
        # 1's video before the post that shows it is queued. A video's own record holds the checks of that video
        # alone; the comparison is the run's, and the post and the run's Evidence say it.
        platforms = self.repo / "config" / "platforms.json"
        data = json.loads(platforms.read_text(encoding="utf-8"))
        data["video"]["text"]["size"] = 60
        platforms.write_text(json.dumps(data), encoding="utf-8")
        queue = self.run_ok()
        rendered = next(entry for entry in queue["open"] if entry.get("day") == 8)
        self.assertEqual(rendered["supersedes"], again["id"])
        self.assertNotIn(rendered["asset"], (day_8["asset"], again["asset"]))
        self.assertNotEqual(rendered["asset_sha256"], day_8["asset_sha256"])
        self.assertEqual(rendered["edit_sha256"], day_8["edit_sha256"])
        record = json.loads((self.ledger() / rendered["asset_record"]).read_text(encoding="utf-8"))
        self.assertEqual(record["made_by_run"], queue["updated_by_run"])
        self.assertEqual(record["checks"], OWN_CHECKS)
        self.assertIn(f"; {same}.", self.item(rendered))
        self.assertEqual(self.checks_of(8), [*OWN_CHECKS, same])
        self.assertNotIn("has no video to compare with yet", self.item(rendered))

    def test_a_leg_whose_video_differs_from_its_other_leg_s_is_not_offered_and_the_pair_is_named(self):
        queue = self.day_1()
        day_1 = next(entry for entry in queue["open"] if entry["kind"] == "post")
        queue = self.day_8(LATER)
        self.assertEqual({day: entry["id"] for day, entry in self.posts_open().items()}, {1: day_1["id"]})
        differ = f"do not show the same footage {WHOLE} ({shows(8, 3)}, and {shows(1, 2)})"
        why = f"the video cut for it and the video in day 1's post `{day_1['id']}` {differ}"
        named = (
            f"- Pair AB-1, days 1 and 8: the video in day 1's post `{day_1['id']}` and the video cut for day 8"
            f" {differ}. Nothing this run changed for either day is offered, and what stood before stays."
        )
        report, notice = self.report(), self.notice()
        self.assertIn(f"| 8 | P01 / AB-1 leg B | not offered | {why} |", report)
        self.assertIn(f"| 8 | d01-s1 | not offered | {why} |", report)
        self.assertIn("- Post Drafts: 1 not offered.", report)
        self.assertIn(f"A/B pairs whose two videos differ:\n\n{named}", report)
        self.assertIn(f"These videos were not made or are not offered, or these files not used:\n{named}", notice)
        # Nothing is blocked or withdrawn, and nothing says the two were compared and found alike.
        self.assertNotIn("withdrawn", notice)
        self.assertNotIn("blocked", report.split("## Post Drafts")[1].split("## Filming")[0])
        self.assertEqual(self.checks_of(8), OWN_CHECKS)
        for said in (report, notice):
            self.assertNotIn("the same source ranges as day 1's leg", said)
        # check-edits tells the agent the same of the files as they are, before a run ends.
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(f"PROBLEM day 8: drafts/edits/window-1/day-08.json would not be offered: {why}", said)
        # Corrected, the leg is offered, and check-edits passes it.
        queue = self.run_ok({fakes.edit_path(8): fakes.edit_record(8, DAY_1)})
        day_8 = self.posts_open()[8]
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(day_8))
        self.assertEqual(self.pairs_shown(), [[1, 8]])
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn("OK day 8: drafts/edits/window-1/day-08.json: it passes", said)
        # A record changed while the leg's post is open is not offered either, and the post that stood stays.
        self.run_ok({fakes.edit_path(8): fakes.edit_record(8, LATER)})
        standing = self.posts_open()
        self.assertEqual({day: entry["id"] for day, entry in standing.items()}, {1: day_1["id"], 8: day_8["id"]})
        self.assertEqual(standing[8]["asset_sha256"], day_8["asset_sha256"])
        report = self.report()
        self.assertIn(
            f"| 8 | P01 / AB-1 leg B | kept | `{day_8['id']}`; what this run changed is not offered, since {why}; the"
            " open item stands |",
            report,
        )
        self.assertIn(named, self.notice())
        self.assertNotIn("withdrawn", self.notice())

    def test_a_leg_cut_from_another_file_under_the_same_name_is_not_offered_beside_its_other_leg(self):
        queue = self.day_1()
        day_1 = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(day_1["id"], "approve")
        # Another recording takes the file's place under its name: a retake as long as the first.
        clip = self.footage / "window-1" / "d01-s1.mov"
        first = clip.read_bytes()
        self.clip("d01-s1.mov", take=2)
        self.assertNotEqual(clip.read_bytes(), first)
        # A week on, day 8's edit record names the same file and the same range, and shows other footage.
        queue = self.day_8()
        self.assertEqual(self.posts_open(), {})
        differ = (
            f"do not show the same footage {WHOLE} (both show `window-1/d01-s1.mov` 2-12s, but `window-1/d01-s1.mov`"
            " is no longer the file day 1's video was cut from)"
        )
        why = f"the video cut for it and the video in day 1's post `{day_1['id']}` {differ}"
        self.assertIn(f"| 8 | P01 / AB-1 leg B | not offered | {why} |", self.report())
        self.assertIn(
            f"- Pair AB-1, days 1 and 8: the video in day 1's post `{day_1['id']}` and the video cut for day 8"
            f" {differ}. Nothing this run changed for either day is offered, and what stood before stays.",
            self.notice(),
        )
        self.assertEqual(self.checks_of(8), OWN_CHECKS)
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(f"PROBLEM day 8: drafts/edits/window-1/day-08.json would not be offered: {why}", said)
        # With the first recording back in its place, day 8 is cut from the file day 1 was cut from, and offered.
        clip.write_bytes(first)
        queue = self.run_ok()
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(self.posts_open()[8]))
        self.assertEqual(self.pairs_shown(), [[1, 8]])
        self.assertEqual(self.check_edits(queue["updated_by_run"])[0], 0)

    def test_a_leg_cut_from_the_same_file_under_another_name_shows_the_footage_its_other_leg_shows(self):
        queue = self.day_1()
        day_1 = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(day_1["id"], "approve")
        clip = self.footage / "window-1" / "d01-s1.mov"
        clip.rename(clip.with_name("d01-s1-take-1.mov"))
        queue = self.day_8(("d01-s1", "d01-s1-take-1.mov", 2, 12))
        day_8 = self.posts_open()[8]
        text = self.item(day_8)
        self.assertIn("| 0-10s | d01-s1 | `window-1/d01-s1-take-1.mov` | 2s | 12s | as recorded |", text)
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", text)
        cuts = [
            json.loads((self.ledger() / entry["asset_record"]).read_text(encoding="utf-8"))["cuts"][0]
            for entry in (day_1, day_8)
        ]
        self.assertEqual([cut["source"] for cut in cuts], ["window-1/d01-s1.mov", "window-1/d01-s1-take-1.mov"])
        self.assertEqual(cuts[0]["sha256"], cuts[1]["sha256"])
        self.assertEqual(self.pairs_shown(), [[1, 8]])
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn("OK day 8: drafts/edits/window-1/day-08.json: it passes", said)

    def test_a_post_the_pair_check_s_line_takes_over_the_item_limit_is_blocked_and_never_queued(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        added = "; day 8, its pair's other leg, has no video to compare with yet"
        self.assertIn(f"{added}.", self.item(post))
        held = exchange.check_item(self.item(post), ["RepToday", "Immerse"], published=True).item
        size = len(exchange.render_content("post", held.ask, held.body, held.touches, held.evidence))
        limit = exchange.MAX_ITEM_CHARS

        def grown(by):
            """Day 1's Draft with a filming note that makes its item that many characters longer."""
            note = "Hold on the session list and the one Start button."
            more = ("steady " * by)[: by - 2] + "y"
            self.assertEqual((len(more), "  " in more), (by - 1, False))
            draft = fakes.filming_draft(1)
            self.assertEqual(draft.count(note), 1)
            return draft.replace(note, f"{note} {more}")

        # The Draft grows until its item fits the limit as it is checked before the pair check, and is ten
        # characters over it with the line that check adds. The item that would be queued is the one that counts.
        self.assertLess(10, len(added))
        self.run_ok({fakes.draft_path(1): grown(limit + 10 - size)})
        self.assertEqual(self.posts_open(), {})
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | blocked | 1 failing check, listed below; the open `{post['id']}` was"
            " withdrawn |",
            report,
        )
        self.assertIn(f"- item: the item is {limit + 10} characters; keep it under {limit}", report)
        self.assertIn(
            f"- The open post `{post['id']}` for day 1 is withdrawn, since its Draft no longer passes.", self.notice()
        )
        # One character under the limit with that line, it is queued, and the queued item follows the format.
        queue = self.run_ok({fakes.draft_path(1): grown(limit - 1 - size)})
        again = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn(f"{added}.", self.item(again))
        self.assertEqual(exchange.check_item(self.item(again), ["RepToday", "Immerse"], published=True).problems, [])

    def test_a_leg_is_not_offered_while_the_record_of_its_other_leg_s_video_cannot_be_read(self):
        queue = self.day_1()
        day_1 = next(entry for entry in queue["open"] if entry["kind"] == "post")
        record = self.ledger() / day_1["asset_record"]
        held = record.read_text(encoding="utf-8")
        record.write_text("{}", encoding="utf-8")
        # What day 1's video shows cannot be told, so day 8's cannot be compared with it and is not offered.
        self.day_8()
        self.assertEqual({day: entry["id"] for day, entry in self.posts_open().items()}, {1: day_1["id"]})
        apart = "could not be compared, since the ledger's record of one of them does not say what footage it shows"
        self.assertIn(
            f"- Pair AB-1, days 1 and 8: the video in day 1's post `{day_1['id']}` and the video cut for day 8 {apart}."
            " Nothing this run changed for either day is offered, and what stood before stays.",
            self.notice(),
        )
        self.assertIn(
            f"| 8 | P01 / AB-1 leg B | not offered | the video cut for it and the video in day 1's post"
            f" `{day_1['id']}` {apart} |",
            self.report(),
        )
        self.assertEqual(self.checks_of(8), OWN_CHECKS)
        # With the record back, the two are compared, and day 8 is offered.
        record.write_text(held, encoding="utf-8")
        self.run_ok()
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(self.posts_open()[8]))
        self.assertEqual(self.pairs_shown(), [[1, 8]])

    def test_a_leg_is_judged_against_the_video_the_founder_approved_for_its_other_leg(self):
        queue = self.day_1()
        day_1 = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(day_1["id"], "approve")
        # A week on, day 8's record shows other footage than the video the Founder approved for day 1.
        self.day_8(LATER)
        self.assertEqual(self.posts_open(), {})
        why = (
            f"the video cut for it and the video in day 1's post `{day_1['id']}` do not show the same footage {WHOLE}"
            f" ({shows(8, 3)}, and {shows(1, 2)})"
        )
        self.assertIn(f"| 8 | P01 / AB-1 leg B | not offered | {why} |", self.report())
        approved = self.entries(status="approved")
        self.assertEqual(
            [(entry["id"], entry["asset_sha256"]) for entry in approved], [(day_1["id"], day_1["asset_sha256"])]
        )
        # Day 1 is settled, so nothing is cut for it again whatever is written in its place; day 8, corrected, is
        # compared with the approved video and offered.
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, LATER), fakes.edit_path(8): fakes.edit_record(8, DAY_1)})
        day_8 = self.posts_open()[8]
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(day_8))
        self.assertEqual(len(list((self.ledger() / "assets" / "window-1").glob("day-01-*"))), 1)
        self.assertEqual(self.pairs_shown(), [[1, 8]])

    def one_week_recut_pair(self):
        """A kit that posts both legs of the re-cut pair AB-3 in one week, days 2 and 5, with its plan approved and
        its footage there, and one run that cuts both; returns the two open posts, day 2's and day 5's."""
        calendar = self.mandu / CALENDAR
        rows = calendar.read_text(encoding="utf-8").splitlines()
        leg_b = next(row for row in rows if row.startswith("| 9 |")).replace("| 9 |", "| 5 |", 1)
        moved = "\n".join(leg_b if row.startswith("| 5 |") else row for row in rows)
        calendar.write_text(moved + "\n", encoding="utf-8")
        self.approved_plan(days=(2, 5))
        for name, seconds in (("d02-s1a-take-1.mov", 6.0), ("d02-s1b-take-1.mov", 6.0), ("d02-s1-closing.mov", 15.0)):
            self.clip(name, seconds, 1080, 1920, 30, sound=True)
        self.clip("d02-s2.mov", 16.0)
        tail = (("d02-s2", "d02-s2.mov", 2, 13), ("d02-s1", "d02-s1-closing.mov", 5, 11))
        queue = self.run_ok(
            {
                fakes.draft_path(2): fakes.filming_draft(2),
                fakes.draft_path(5): fakes.filming_draft(9).replace("day: 9", "day: 5"),
                fakes.edit_path(2): fakes.edit_record(2, ("d02-s1", "d02-s1a-take-1.mov", 1, 4), *tail),
                fakes.edit_path(5): fakes.edit_record(5, ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5), *tail),
            }
        )
        first, second = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (2, 5))
        self.assertIn("; the same source ranges as day 5's leg after the re-cut opening.", self.item(first))
        self.assertIn("; the same source ranges as day 2's leg after the re-cut opening.", self.item(second))
        self.assertEqual(self.pairs_shown(), [[2, 5]])
        for entry in (first, second):
            record = json.loads((self.ledger() / entry["asset_record"]).read_text(encoding="utf-8"))
            self.assertEqual(record["opening"], [[0.0, 3.0]])
        return first, second

    def test_a_broken_draft_of_one_leg_does_not_withdraw_the_other_leg_of_a_plain_pair(self):
        drafts = self.one_week_pair()
        queue = self.run_ok(dict(drafts, **self.both(DAY_1)))
        first, second = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        # The agent breaks day 1's Draft and touches nothing else. Day 1's post is withdrawn, so one video is left:
        # day 4's open post stands with it, and nothing says the two were compared in this run.
        self.run_ok({fakes.draft_path(1): "not a Draft\n"})
        standing = self.posts_open()
        self.assertEqual({day: entry["id"] for day, entry in standing.items()}, {4: second["id"]})
        self.assertEqual(standing[4]["asset_sha256"], second["asset_sha256"])
        self.assertEqual(self.checks_of(4), OWN_CHECKS)
        report = self.report()
        self.assertIn("| 1 | P01 / AB-1 leg A | blocked |", report)
        self.assertIn(
            f"| 4 | P01 / AB-1 leg B | kept | `{second['id']}`; its Draft is unchanged and passes, and so is its"
            " video |",
            report,
        )
        notice = self.notice()
        self.assertIn(f"- The open post `{first['id']}` for day 1 is withdrawn", notice)
        self.assertNotIn(second["id"], notice)
        self.assertNotIn("Day 4", notice)
        self.assertNotIn("Pair AB-1", notice)

    def kept_beside(self, draft):
        """Both legs of the re-cut pair stand with videos that match; the agent then leaves day 2 the given Draft and
        touches nothing else. Day 2 is blocked for it and its post withdrawn, so one video is left: day 5 keeps its
        open post and its video, no Draft in day 2's place judges it, and nothing says the two were compared."""
        first, second = self.one_week_recut_pair()
        self.run_ok({fakes.draft_path(2): draft})
        standing = self.posts_open()
        self.assertEqual({day: entry["id"] for day, entry in standing.items()}, {5: second["id"]})
        self.assertEqual(standing[5]["asset_sha256"], second["asset_sha256"])
        self.assertEqual(
            self.checks_of(5),
            [
                "measured 1080x1920 (9:16) at 30 frames a second",
                "d02-s2, which may not be cut, is one unbroken source range",
                "every cut plays at the speed it was recorded at",
            ],
        )
        report = self.report()
        self.assertIn("| 2 | P02 / AB-3 leg A | blocked |", report)
        self.assertIn(
            f"| 5 | P02 / AB-3 leg B | kept | `{second['id']}`; its Draft is unchanged and passes, and so is its"
            " video |",
            report,
        )
        notice = self.notice()
        self.assertIn(f"- The open post `{first['id']}` for day 2 is withdrawn", notice)
        self.assertNotIn(second["id"], notice)
        self.assertNotIn("Day 5", notice)
        self.assertNotIn("Pair AB-3", notice)
        # check-edits gives the agent the same verdict of the leg it did not touch, so nothing steers it to change it.
        _, said = self.check_edits(self.queue()["updated_by_run"])
        self.assertIn(
            "OK day 5: drafts/edits/window-1/day-05.json: it passes; the launcher renders and measures it", said
        )
        self.assertNotIn("BLOCKED day 5", said)
        self.assertNotIn("PROBLEM day 5", said)
        return report

    def test_a_changed_draft_of_one_re_cut_leg_that_does_not_pass_does_not_withdraw_the_other_leg(self):
        longer = fakes.filming_draft(2).replace("### Beat 1 (hook): 0-3s", "### Beat 1 (hook): 0-4s")
        longer = longer.replace("### Beat 2: 3-14s", "### Beat 2: 4-14s")
        self.assertEqual(longer.count("0-4s") + longer.count("4-14s"), 2)
        self.kept_beside(longer)

    def test_a_changed_draft_of_one_re_cut_leg_that_passes_while_its_edit_no_longer_fits_does_not_withdraw_the_other(
        self,
    ):
        # The hook beat runs a second longer and the later beats move with it, each as long as before, so the Draft
        # passes the post-Draft checks; the leg's own edit record no longer runs as long as its beats.
        shifted = fakes.filming_draft(2)
        beats = (("1 (hook): 0-3s", "1 (hook): 0-4s"), ("2: 3-14s", "2: 4-15s"), ("3: 14-20s", "3: 15-21s"))
        for before, after in beats:
            self.assertEqual(shifted.count(f"### Beat {before}"), 1)
            shifted = shifted.replace(f"### Beat {before}", f"### Beat {after}")
        report = self.kept_beside(shifted)
        self.assertIn(
            "- length: the edit runs 20.00s, and the beats of `drafts/posts/window-1/day-02.md` end at 21s", report
        )
        self.assertNotIn("do not show the same footage", report)

    def test_an_unreadable_draft_of_one_re_cut_leg_does_not_withdraw_the_other_leg(self):
        self.kept_beside("not a Draft\n")

    def test_re_cut_legs_whose_drafts_change_are_compared_again_as_their_videos_are_then(self):
        first, second = self.one_week_recut_pair()
        after = "after the re-cut opening"
        again = fakes.filming_draft(9).replace("day: 9", "day: 5") + "\n"
        # Day 5's Draft is written again, the same words in other bytes: its post is replaced by one that shows the
        # same video, compared with the video day 2's post shows, and day 2's post stands as it was.
        self.run_ok({fakes.draft_path(5): again})
        standing = self.posts_open()
        self.assertEqual((standing[2]["id"], standing[5]["supersedes"]), (first["id"], second["id"]))
        self.assertEqual(standing[5]["asset_sha256"], second["asset_sha256"])
        self.assertIn(f"; the same source ranges as day 2's leg {after}.", self.item(standing[5]))
        self.assertIn(
            f"| 2 | P02 / AB-3 leg A | kept | `{first['id']}`; its Draft is unchanged and passes, and so is its"
            " video |",
            self.report(),
        )
        # Both Drafts are written again: both posts are replaced, and each video is compared with the other.
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2) + "\n", fakes.draft_path(5): again + "\n"})
        third, fourth = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (2, 5))
        self.assertEqual((third["supersedes"], fourth["supersedes"]), (first["id"], standing[5]["id"]))
        self.assertEqual(
            (third["asset_sha256"], fourth["asset_sha256"]), (first["asset_sha256"], second["asset_sha256"])
        )
        self.assertIn(f"; the same source ranges as day 5's leg {after}.", self.item(third))
        self.assertIn(f"; the same source ranges as day 2's leg {after}.", self.item(fourth))
        self.assertEqual(self.pairs_shown(), [[2, 5]])
        # Day 5 changes what it shows after its opening: it is not offered, and both posts stand.
        moved = fakes.edit_record(
            5,
            ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5),
            ("d02-s2", "d02-s2.mov", 4, 15),
            ("d02-s1", "d02-s1-closing.mov", 5, 11),
        )
        self.run_ok({fakes.edit_path(5): moved})
        standing = self.posts_open()
        self.assertEqual({day: entry["id"] for day, entry in standing.items()}, {2: third["id"], 5: fourth["id"]})
        self.assertIn(
            f"- Pair AB-3, days 2 and 5: the video in day 2's post `{third['id']}` and the video cut for day 5 do not"
            " show the same footage after each one's opening (day 5's shows `window-1/d02-s2.mov` 4-15s,"
            " `window-1/d02-s1-closing.mov` 5-11s, and day 2's shows `window-1/d02-s2.mov` 2-13s,"
            " `window-1/d02-s1-closing.mov` 5-11s). Nothing this run changed for either day is offered, and what stood"
            " before stays.",
            self.notice(),
        )

    def test_both_legs_cut_in_one_run_are_compared_with_each_other_and_each_post_says_so(self):
        drafts = self.one_week_pair()
        queue = self.run_ok(dict(drafts, **self.both(DAY_1)))
        first, second = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        self.assertIn(f"; the same source ranges as day 4's leg {WHOLE}.", self.item(first))
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(second))
        self.assertEqual(self.pairs_shown(), [[1, 4]])
        # Both records change alike: both posts are replaced, each video compared with the other's new one.
        queue = self.run_ok(self.both(LATER))
        third, fourth = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        self.assertEqual((third["supersedes"], fourth["supersedes"]), (first["id"], second["id"]))
        self.assertIn(f"; the same source ranges as day 4's leg {WHOLE}.", self.item(third))
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(fourth))
        self.assertEqual((self.asset(third)["seeks"], self.asset(fourth)["seeks"]), (["3.000000"], ["3.000000"]))
        # With nothing changed both posts stand, and a run that compared nothing says of neither leg that it did.
        self.run_ok()
        standing = self.posts_open()
        self.assertEqual({day: entry["id"] for day, entry in standing.items()}, {1: third["id"], 4: fourth["id"]})
        self.assertEqual((self.checks_of(1), self.checks_of(4)), (OWN_CHECKS, OWN_CHECKS))
        # With nothing changed but the slot, both posts are replaced and each video is compared with the other again.
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 11)))
        queue = self.run_ok()
        fifth, sixth = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        self.assertEqual((fifth["supersedes"], sixth["supersedes"]), (third["id"], fourth["id"]))
        self.assertEqual(
            (fifth["asset_sha256"], sixth["asset_sha256"]), (third["asset_sha256"], fourth["asset_sha256"])
        )
        self.assertIn(f"; the same source ranges as day 4's leg {WHOLE}.", self.item(fifth))
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(sixth))
        for entry in (fifth, sixth):
            self.assertNotIn("has no video to compare with yet", self.item(entry))

    def test_legs_cut_in_one_run_whose_videos_differ_are_both_left_as_they_stood(self):
        drafts = self.one_week_pair()
        differ = f"do not show the same footage {WHOLE} ({shows(1, 2)}, and {shows(4, 3)})"
        named = (
            f"- Pair AB-1, days 1 and 4: the video cut for day 1 and the video cut for day 4 {differ}. Nothing this run"
            " changed for either day is offered, and what stood before stays."
        )
        # No post stood before, so none stands after: neither leg is offered, not even its copy.
        writes = {fakes.edit_path(1): fakes.edit_record(1, DAY_1), fakes.edit_path(4): fakes.edit_record(4, LATER)}
        queue = self.run_ok(dict(drafts, **writes))
        self.assertEqual(self.posts_open(), {})
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | not offered | the video cut for it and the video cut for day 4 {differ} |",
            report,
        )
        self.assertIn(
            f"| 4 | P01 / AB-1 leg B | not offered | the video cut for it and the video cut for day 1 {differ} |",
            report,
        )
        self.assertIn(named, report)
        self.assertIn(named, self.notice())
        self.assertRegex(report, r"- filming: checked=4 acted=2 note=[^\n]*; edits: 2 not offered")
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        for day in (1, 4):
            self.assertIn(f"PROBLEM day {day}: drafts/edits/window-1/day-{day:02d}.json would not be offered", said)
        # Made alike, both are offered: day 1's video was kept from the run before, and nothing is rendered twice.
        queue = self.run_ok({fakes.edit_path(4): fakes.edit_record(4, DAY_1)})
        first, second = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        self.assertIn(f"| 1 | d01-s1 | finished | `{first['asset']}`", self.report())
        self.assertIn("kept from an earlier run", self.report().split("| 1 | d01-s1 |")[1].split("\n")[0])
        self.assertEqual(self.pairs_shown(), [[1, 4]])
        # Both posts stand and both records change, each to other footage than the other's: both posts stay.
        writes = {
            fakes.edit_path(1): fakes.edit_record(1, LATER),
            fakes.edit_path(4): fakes.edit_record(4, ("d01-s1", "d01-s1.mov", 4, 14)),
        }
        self.run_ok(writes)
        standing = self.posts_open()
        self.assertEqual({day: entry["id"] for day, entry in standing.items()}, {1: first["id"], 4: second["id"]})
        self.assertEqual(
            (standing[1]["asset_sha256"], standing[4]["asset_sha256"]), (first["asset_sha256"], second["asset_sha256"])
        )
        differ = f"do not show the same footage {WHOLE} ({shows(1, 3)}, and {shows(4, 4)})"
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{first['id']}`; what this run changed is not offered, since the video"
            f" cut for it and the video cut for day 4 {differ}; the open item stands |",
            report,
        )
        self.assertIn(
            f"| 4 | P01 / AB-1 leg B | kept | `{second['id']}`; what this run changed is not offered, since the video"
            f" cut for it and the video cut for day 1 {differ}; the open item stands |",
            report,
        )

    def test_a_leg_cut_alone_is_offered_only_when_its_video_matches_the_one_its_other_leg_s_post_shows(self):
        drafts = self.one_week_pair()
        queue = self.run_ok(dict(drafts, **self.both(DAY_1)))
        first, second = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))

        def standing():
            return {day: (entry["id"], entry["asset_sha256"]) for day, entry in self.posts_open().items()}

        before = standing()
        differ = f"do not show the same footage {WHOLE} ({shows(1, 3)}, and {shows(4, 2)})"
        why = f"the video cut for it and the video in day 4's post `{second['id']}` {differ}"
        named = (
            f"- Pair AB-1, days 1 and 4: the video cut for day 1 and the video in day 4's post `{second['id']}`"
            f" {differ}. Nothing this run changed for either day is offered, and what stood before stays."
        )
        # Both edit records change alike and only day 4's render fails. Day 1's new video shows other footage than
        # the video day 4's post still shows, so it is not offered, and both posts stand as they were.
        (self.tools / "ffmpeg.json").write_text(json.dumps({"fail": "Error opening output files", "only": "day-04"}))
        self.run_ok(self.both(LATER))
        self.assertEqual(standing(), before)
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{first['id']}`; what this run changed is not offered, since {why}; the"
            " open item stands |",
            report,
        )
        self.assertIn(
            f"| 4 | P01 / AB-1 leg B | kept | `{second['id']}`; its video was not cut again ({FAILURE}); the open item"
            " stands |",
            report,
        )
        self.assertIn(f"| 1 | d01-s1 | not offered | {why} |", report)
        self.assertIn(f"| 4 | d01-s1 | not cut | {FAILURE}; its post keeps the video it shows |", report)
        notice = self.notice()
        self.assertIn(f"- Day 4's video could not be cut again: {FAILURE}; its post keeps the video it shows.", notice)
        self.assertIn(named, notice)
        # The tooling works again and day 4's edit record goes back to the one its video was cut from. Day 1's new
        # video still differs from it, so both posts stand again.
        (self.tools / "ffmpeg.json").unlink()
        queue = self.run_ok({fakes.edit_path(4): fakes.edit_record(4, DAY_1)})
        self.assertEqual(standing(), before)
        self.assertIn(named, self.notice())
        # check-edits says the same of the files as they are: day 1's record is the problem, and day 4's passes.
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(f"PROBLEM day 1: drafts/edits/window-1/day-01.json would not be offered: {why}", said)
        self.assertIn("OK day 4: drafts/edits/window-1/day-04.json: it passes", said)
        # Day 4's record changes as day 1's did and its render finishes: both legs are offered.
        queue = self.run_ok({fakes.edit_path(4): fakes.edit_record(4, LATER)})
        third, fourth = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        self.assertEqual((third["supersedes"], fourth["supersedes"]), (first["id"], second["id"]))
        self.assertEqual((self.asset(third)["seeks"], self.asset(fourth)["seeks"]), (["3.000000"], ["3.000000"]))
        self.assertIn(f"; the same source ranges as day 4's leg {WHOLE}.", self.item(third))
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(fourth))

    def test_a_leg_whose_other_leg_has_no_video_yet_is_offered_alone_and_the_other_is_compared_with_it_later(self):
        drafts = self.one_week_pair()
        # Day 4 has an edit record and no Draft, so no video is cut from it: day 1's is offered alone, and says so.
        queue = self.run_ok({fakes.draft_path(1): drafts[fakes.draft_path(1)], **self.both(DAY_1)})
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual((post["day"], "asset" in post), (1, True))
        self.assertIn("; day 4, its pair's other leg, has no video to compare with yet.", self.item(post))
        self.assertEqual(self.pairs_shown(), [])
        # Day 4's Draft arrives and its render fails: its copy is offered with no video, and day 1's post stands.
        (self.tools / "ffmpeg.json").write_text(json.dumps({"fail": "Error opening output files", "only": "day-04"}))
        self.run_ok({fakes.draft_path(4): drafts[fakes.draft_path(4)]})
        standing = self.posts_open()
        self.assertEqual((standing[1]["id"], "asset" in standing[4]), (post["id"], False))
        self.assertIn(f"**Video file**: none yet ({FAILURE}).", self.item(standing[4]))
        self.assertEqual(self.pairs_shown(), [])
        # The render works: day 4's video is compared with the one day 1's post shows, and offered.
        (self.tools / "ffmpeg.json").unlink()
        queue = self.run_ok()
        first, second = (next(entry for entry in queue["open"] if entry.get("day") == day) for day in (1, 4))
        self.assertEqual((first["id"], second["supersedes"]), (post["id"], standing[4]["id"]))
        self.assertIn(f"; the same source ranges as day 1's leg {WHOLE}.", self.item(second))
        self.assertEqual(self.asset(first)["seeks"], self.asset(second)["seeks"])
        self.assertEqual(self.pairs_shown(), [[1, 4]])

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

    def test_an_edit_record_with_a_number_too_large_or_nested_too_deep_blocks_its_day_and_the_run_goes_on(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        deep = fakes.edit_record(1, DAY_1).replace('"day": 1', '"day": ' + "[" * 100000 + "]" * 100000)
        for edit, problem in (
            (fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 2, 10**400)), "segment 1: in, out, and speed are numbers"),
            # How deep a record is read is the interpreter's limit. A parser that refuses this one leaves only its
            # depth to name; on an interpreter whose parser reads this deep, the nesting sits where the day is held.
            (deep, "(it is nested too deep to read|day must be a whole number from 1)"),
        ):
            with self.subTest(problem=problem):
                queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): edit})
                self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
                self.assertFalse((self.ledger() / "assets").exists())
                report = self.report()
                self.assertIn("- The run finished.", report)
                self.assertRegex(report, re.escape("| 1 | d01-s1 | blocked | edit-format: ") + problem)
                self.assertRegex(self.notice(), f"edit-format: {problem}")
                code, text = self.check_edits(queue["updated_by_run"])
                self.assertEqual(code, 1, text)
                self.assertRegex(text, f"  - edit-format: {problem}")
                # check-drafts reads the same record for its digest, and still gives the Draft its own verdict.
                code, text = self.check_drafts(queue["updated_by_run"])
                self.assertEqual(code, 0, text)
                self.assertIn("OK day 1: drafts/posts/window-1/day-01.md", text)

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
        # The agent is never asked to change or remove the record of a day whose post keeps its video.
        why = f"the video tooling cannot be used (ffmpeg is not an executable at `{self.root / 'no-ffmpeg'}`)"
        self.assertEqual(self.filming_row(1).split(" | ")[-1], f"not ready: {why}; {LEAVE} |")
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn(
            f"KEPT day 1: drafts/edits/window-1/day-01.json: it cannot be cut this run ({why}), so leave it as it is:"
            " the day's post keeps the video it shows",
            said,
        )
        self.assertIn("1 day checked, 0 with problems", said)

    def slot_set_while_the_video_cannot_be_cut(self, stop):
        """Day 1's post is open with its video, and another day's footage is in the footage place too; the
        window's first sitting and slot are then set, and the next run cannot cut the video again, for the reason
        stop brings about and returns the words of. The post that replaces day 1's shows the new slot and the same
        video, carried over from its own record."""
        post = self.day_1_beside_other_footage()
        self.assertNotIn("slot", post)
        why = stop()
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 11)))
        self.run_ok()
        moved = self.posts_open()[1]
        self.assertEqual(moved["supersedes"], post["id"])
        self.assertIn("T", moved["slot"])
        for key in ("asset", "asset_sha256", "asset_record", "edit", "edit_sha256", "draft_sha256"):
            self.assertEqual(moved[key], post[key], key)
        text = self.item(moved)
        self.assertEqual(exchange.check_item(text, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertIn(f"slot: {moved['slot']}\n", text)
        self.assertIn(
            f"- `{post['asset']}`, under gr0wthlab's `ledger/`: 10.00s, 1080x1920 (9:16), 30 frames a second, no"
            f" sound. SHA-256 `{post['asset_sha256']}`.",
            text,
        )
        self.assertIn("| 0-10s | d01-s1 | `window-1/d01-s1.mov` | 2s | 12s | as recorded |", text)
        self.assertIn(
            "- Checked: measured 1080x1920 (9:16) at 30 frames a second; d01-s1, which may not be cut, is one unbroken"
            " source range; every cut plays at the speed it was recorded at; day 8, its pair's other leg, has no video"
            " to compare with yet.",
            text,
        )
        self.assertNotIn("none yet", text)
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | queued | `{moved['id']}`; replaces `{post['id']}`, with the video that one"
            f" showed, which was not cut again this run ({why}) |",
            report,
        )
        self.assertIn(f"| 1 | d01-s1 | not cut | {why}; its post keeps the video it shows |", report)
        self.assertEqual(len(list((self.ledger() / "assets" / "window-1").iterdir())), 1)
        self.assertNotIn("Day 1 has no video", self.notice())
        self.assertEqual(self.filming_row(1).split(" | ")[-1], f"not ready: {why}; {LEAVE} |")
        code, said = self.check_edits(self.queue()["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn(
            f"KEPT day 1: drafts/edits/window-1/day-01.json: it cannot be cut this run ({why}), so leave it as it is:"
            " the day's post keeps the video it shows",
            said,
        )
        return post, moved

    def test_a_slot_set_while_the_footage_is_away_keeps_the_post_s_video_and_shows_the_new_slot(self):
        def footage_away():
            (self.footage / "window-1" / "d01-s1.mov").unlink()
            return "no footage yet for shot d01-s1"

        self.slot_set_while_the_video_cannot_be_cut(footage_away)
        notice = self.notice()
        self.assertIn(
            "- Day 1's video could not be cut again: shot d01-s1 has no footage; its post keeps the video it shows.",
            notice,
        )
        self.assertIn("- Day 2 has no video: shot d02-s1 has no footage", notice)

    def test_a_slot_set_while_ffmpeg_is_missing_keeps_the_post_s_video_and_shows_the_new_slot(self):
        def no_ffmpeg():
            self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.root / "no-ffmpeg")
            return f"the video tooling cannot be used (ffmpeg is not an executable at `{self.root / 'no-ffmpeg'}`)"

        self.slot_set_while_the_video_cannot_be_cut(no_ffmpeg)
        self.assertIn(
            f"- The edit of day 1 was skipped: ffmpeg is not an executable at `{self.root / 'no-ffmpeg'}`; the post"
            " of day 1 keeps the video it shows.",
            self.notice(),
        )

    def test_footage_that_goes_away_leaves_the_post_its_video_and_the_notice_says_the_post_keeps_it(self):
        post = self.day_1_beside_other_footage()
        (self.footage / "window-1" / "d01-s1.mov").unlink()
        self.run_ok()
        self.assertEqual(self.posts_open()[1], post)
        report, notice = self.report(), self.notice()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; its video was not cut again (no footage yet for shot"
            " d01-s1); the open item stands |",
            report,
        )
        self.assertIn(
            "| 1 | d01-s1 | not cut | no footage yet for shot d01-s1; its post keeps the video it shows |", report
        )
        self.assertIn(
            "- Day 1's video could not be cut again: shot d01-s1 has no footage; its post keeps the video it shows.",
            notice,
        )
        self.assertNotIn("Day 1 has no video", notice)
        # The agent is told the same before it writes anything, and by check-edits before it finishes: the record
        # of a day whose post keeps its video is no problem to fix, and it stays as it is.
        brief = self.brief().split("## Filming")[1]
        self.assertIn(
            "Where the table says to leave a day's edit record as it is, change nothing in it and do not remove it.",
            brief,
        )
        self.assertEqual(self.filming_row(1).split(" | ")[-1], f"not ready: no footage yet for shot d01-s1; {LEAVE} |")
        self.assertNotIn("leave its edit record", self.filming_row(2))
        code, said = self.check_edits(self.queue()["updated_by_run"])
        self.assertEqual(code, 0, said)
        kept = (
            "KEPT day 1: drafts/edits/window-1/day-01.json: it cannot be cut this run (no footage yet for shot"
            " d01-s1), so leave it as it is:"
        )
        self.assertIn(f"{kept} the day's post keeps the video it shows", said)
        self.assertNotIn("PROBLEM", said)
        self.assertIn("2 days checked, 0 with problems", said)
        # Day 2, whose post shows no video, is still said to have none, in the notice and in the report alike.
        self.assertIn("- Day 2 has no video: shot d02-s1 has no footage", notice)
        day_2 = next(line for line in report.splitlines() if line.startswith("| 2 | d02-s1, d02-s2 |"))
        self.assertNotIn("keeps the video", day_2)
        # A Draft changed while the footage is away is queued without a video, and the day is then said to have none.
        changed = fakes.filming_draft(1).replace("Real phone, no cuts.", "One real phone, no cuts.")
        self.assertNotEqual(changed, fakes.filming_draft(1))
        self.run_ok({fakes.draft_path(1): changed})
        self.assertNotIn("asset", self.posts_open()[1])
        self.assertIn("- Day 1 has no video: shot d01-s1 has no footage, and nothing is substituted.", self.notice())
        self.assertIn("| 1 | d01-s1 | not cut | no footage yet for shot d01-s1 |", self.report())
        # Its edit record is still no problem to fix: check-edits says to leave it, to be cut once it can be.
        code, said = self.check_edits(self.queue()["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn(f"{kept} the day's video is cut from it again once it can be", said)

    def test_a_slot_set_while_the_video_cannot_be_cut_and_its_file_is_gone_is_shown_by_a_post_without_a_video(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        clip = self.footage / "window-1" / "d01-s1.mov"
        held = clip.read_bytes()
        clip.unlink()
        (self.ledger() / post["asset"]).unlink()
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 11)))
        self.run_ok()
        bare = self.posts_open()[1]
        self.assertEqual((bare["supersedes"], "asset" in bare, "asset_sha256" in bare), (post["id"], False, False))
        self.assertIn("T", bare["slot"])
        why = (
            f"no footage yet for shot d01-s1, and the finished file `{post['asset']}` of the video `{post['id']}`"
            " named is gone"
        )
        self.assertIn(f"**Video file**: none yet ({why}).", self.item(bare))
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | queued | `{bare['id']}`; replaces `{post['id']}`, without the video that one"
            f" named, which was not cut again this run ({why}) |",
            self.report(),
        )
        # With the footage back the video is cut again, and the post that shows it has the slot too.
        clip.write_bytes(held)
        self.run_ok()
        moved = self.posts_open()[1]
        self.assertEqual((moved["supersedes"], moved["asset_sha256"]), (bare["id"], post["asset_sha256"]))
        self.assertEqual(moved["slot"], bare["slot"])
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | queued | `{moved['id']}`; replaces `{bare['id']}`, with its finished video |",
            self.report(),
        )

    def test_a_slot_set_while_a_changed_edit_record_cannot_be_cut_leaves_the_open_post_standing(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        (self.footage / "window-1" / "d01-s1.mov").unlink()
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 11)))
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, LATER)})
        self.assertEqual(self.posts_open()[1], post)
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; its video was not cut again (no footage yet for shot"
            " d01-s1); the open item stands, and its new slot reaches it once the video is cut again |",
            self.report(),
        )

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
        # check-edits tells the agent so of the files as they are, though the edit record itself passes.
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(
            "PROBLEM day 1: drafts/edits/window-1/day-01.json will not be cut this run: the Founder approved its copy"
            f" as {copy['id']}, and its Draft is no longer that copy",
            said,
        )
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
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn("OK day 1: drafts/edits/window-1/day-01.json: it passes", said)

    def test_a_post_rejected_with_its_video_is_asked_again_only_once_something_changes(self):
        queue = self.day_1()
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.decide(post["id"], "reject", reason="Start the recording a second later.")
        queue = self.run_ok()
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertIn("the Founder rejected this Draft, so it is not asked again until it changes", self.report())
        # Both checks tell the agent so before a run ends, while the Draft and the edit record are as they were.
        code, said = self.check_drafts(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(
            f"REJECTED day 1: drafts/posts/window-1/day-01.md: the Founder rejected this Draft as {post['id']}, so it"
            " is not asked again until the Draft or its edit record changes",
            said,
        )
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(
            "REJECTED day 1: drafts/edits/window-1/day-01.json: the Founder rejected the post made from this edit"
            f" record and its Draft as {post['id']}, so it is not asked again until the Draft or the edit record"
            " changes",
            said,
        )
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
        code, said = self.check_drafts(queue["updated_by_run"])
        self.assertEqual(code, 1, said)
        self.assertIn(
            f"REJECTED day 1: drafts/posts/window-1/day-01.md: the Founder rejected this Draft as {post['id']}", said
        )
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13))})
        again = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotEqual(again["asset_sha256"], post["asset_sha256"])
        # With the edit record changed, neither check holds the rejection against the Draft or the record.
        code, said = self.check_drafts(queue["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn("OK day 1: drafts/posts/window-1/day-01.md", said)
        code, said = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn("OK day 1: drafts/edits/window-1/day-01.json: it passes", said)

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
        self.assertIn(f"| 1 | d01-s1 | not cut | {failure}; its post keeps the video it shows |", report)
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; its video was not cut again ({failure}); the open item"
            " stands |",
            report,
        )
        self.assertIn("- The run finished.", report)
        notice = self.notice()
        self.assertIn(f"- Day 1's video could not be cut again: {failure}; its post keeps the video it shows.", notice)
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
        # The half-written file the failed render left is gone with it.
        folder = self.ledger() / "assets" / "window-1"
        left = [Path(line) for line in (self.tools / "partial.log").read_text().splitlines()]
        self.assertEqual([path.parent for path in left], [folder])
        self.assertEqual(list(folder.iterdir()), [])

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

    def test_a_ready_day_with_no_edit_record_is_a_gap_only_when_the_agent_did_not_finish(self):
        self.approved_plan()
        writes = {fakes.draft_path(1): fakes.filming_draft(1)}
        none = "| 1 | d01-s1 | no edit record | it is ready for an edit record and has none |"
        line = r"\n- filming: checked=2 acted=0 note=plan approved as [^\n]*, 1 footage file measured"

        def agent_fails(more=None):
            fakes.behave(self.codex_dir, {"write": dict(writes, **(more or {})), "exit": 1})
            code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(hours=self.runs))
            self.runs += 1
            self.assertEqual(code, 1, out)
            return self.report()

        # No day is ready before its footage is there, so the agent was asked for no edit record.
        report = agent_fails()
        self.assertIn("| 1 | d01-s1 | no edit record | no footage yet for shot d01-s1 |", report)
        self.assertIn("| Post Drafts | incomplete | the agent did not finish |", report)
        self.assertIn("| Filming plan and edits | complete | plan approved as", report)
        # A ready day the agent finished without an edit record for is named, and is not a gap on its own.
        self.clip("d01-s1.mov")
        self.run_ok(writes)
        report = self.report()
        self.assertIn(none, report)
        self.assertIn("| Filming plan and edits | complete | plan approved as", report)
        self.assertRegex(report, line + r"\n")
        # The same day left without one by an agent that ended with an error is.
        report = agent_fails()
        self.assertIn(none, report)
        self.assertIn("| Filming plan and edits | incomplete | the agent did not finish |", report)
        self.assertRegex(report, line + r"; incomplete: the agent did not finish\n")
        # Once the record is there, the agent's not finishing leaves nothing of filming's undone.
        report = agent_fails({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        self.assertIn("| 1 | d01-s1 | finished |", report)
        self.assertIn("| Filming plan and edits | complete | plan approved as", report)

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
            out = io.StringIO()
            self.assertEqual(cli.rebuild_asset("../config/run.json", self.env, self.home, out), 1)
            self.assertEqual(
                out.getvalue(),
                f"`../config/run.json` cannot be rebuilt: refusing to touch {self.repo}/config/run.json: it is outside"
                f" {self.repo}/ledger\n",
            )


class LostVideoTest(FilmingRunCase):
    """The launcher never says a post shows or keeps a video unless the finished file is on disk and is the file the
    video's record and the post's entry name. Each place that speaks of a video the run does not cut is met here with
    the file gone, changed, and unreadable; the file in place is what every other test of those places holds."""

    GONE = "is gone"
    CHANGED = "is no longer the file its record names"
    UNREAD = "could not be read (Permission denied)"
    AWAY = "no footage yet for shot d01-s1"

    def day_1(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        return self.posts_open()[1]

    def unreadable(self, post):
        """Make the finished file of a post's video one the launcher cannot read, until the returned call."""
        real, asset = footage.fingerprint, self.ledger() / post["asset"]

        def refuse(path):
            if Path(path) == asset:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path)

        patch = mock.patch.object(footage, "fingerprint", refuse)
        patch.start()
        self.addCleanup(patch.stop)
        return patch.stop

    def lost(self, post, how, due=True):
        """What the report and the notice say of an open post whose video's finished file is not the file it names,
        in a run its day is due in or not."""
        said = (
            f"Day {post['day']}'s open post `{post['id']}`: the finished file `{post['asset']}` of the video it names"
            f" {how}"
        )
        if how == self.UNREAD:
            return f"- {said}, so nothing is said of whether the post keeps the video, and the post is left as it is."
        said += ", so the post is not said to keep the video: nothing is substituted, and"
        if due:
            return f"- {said} it is cut again once it can be."
        return f"- {said} day {post['day']} is not due this run, so nothing is cut for it and the post stands as it is."

    def row(self, post, how):
        """What a day's row says of the video its post names, in the report, the brief, and check-edits."""
        said = f"the finished file `{post['asset']}` of the video its post names {how}"
        if how == self.UNREAD:
            return f"{said}, so nothing is said of whether the post keeps it, and the post is left as it is"
        return f"{said}, so the post is not said to keep it: nothing is substituted, and it is cut again once it can be"

    def told(self, post, how, why, skipped=""):
        """One run with day 1's video not cut again for why and its finished file not intact: the open post is as it
        was, and the report rows, the notice, the brief, and check-edits say where the file stands, never that the
        post keeps the video."""
        self.run_ok()
        self.assertEqual(self.posts_open()[1], post)
        report, notice = self.report(), self.notice()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; its video was not cut again ({why}), and the finished"
            f" file `{post['asset']}` of the video it names {how}; the open item stands |",
            report,
        )
        self.assertIn(f"| 1 | d01-s1 | not cut | {why}; {self.row(post, how)} |", report)
        self.assertIn(
            "Posts whose video's finished file was not confirmed as the file they name:\n\n" + self.lost(post, how),
            report,
        )
        self.assertIn(self.lost(post, how), notice)
        self.assertIn(skipped or "- Day 1's video could not be cut again: shot d01-s1 has no footage.\n", notice)
        for text in (report, notice, self.brief()):
            self.assertNotIn("keeps the video it shows", text.replace("the post of day 2 keeps", ""))
        output = next(line for line in report.splitlines() if line.startswith("| Filming plan and edits |"))
        if how == self.UNREAD:
            self.assertIn(
                f"| incomplete | the finished file `{post['asset']}` of the video day 1's post names {how} |", output
            )
        else:
            self.assertIn("| complete |", output)
        self.assertEqual(
            self.filming_row(1).split(" | ")[-1],
            f"not ready: {why}; {self.row(post, how)}; leave its edit record as it is |",
        )
        code, said = self.check_edits(self.queue()["updated_by_run"])
        self.assertEqual(code, 0, said)
        self.assertIn(
            f"KEPT day 1: drafts/edits/window-1/day-01.json: it cannot be cut this run ({why}), so leave it as it is:"
            f" {self.row(post, how)}\n",
            said,
        )
        self.assertNotIn("keeps the video it shows", said)

    def keeps(self, post, why):
        """One run with the finished file intact again: everything says the post keeps its video, as before."""
        self.run_ok()
        self.assertEqual(self.posts_open()[1], post)
        report = self.report()
        self.assertIn(f"| 1 | d01-s1 | not cut | {why}; its post keeps the video it shows |", report)
        self.assertNotIn("finished file", report)
        self.assertIn("| Filming plan and edits | complete |", report)
        self.assertEqual(self.filming_row(1).split(" | ")[-1], f"not ready: {why}; {LEAVE} |")
        self.assertIn("the day's post keeps the video it shows", self.check_edits(self.queue()["updated_by_run"])[1])

    def gives_way(self, post, how, why, skipped=""):
        """One run with day 1's video not cut again for why and its finished file gone or changed: the same post is
        queued in the open one's place without a video, and the item, the report rows, and the notice give the real
        reason. Returns the post that shows no video."""
        self.run_ok()
        bare = self.posts_open()[1]
        self.assertEqual(bare["supersedes"], post["id"])
        for key in ("asset", "asset_sha256", "asset_record"):
            self.assertNotIn(key, bare)
        self.assertEqual((bare["draft"], bare["draft_sha256"]), (post["draft"], post["draft_sha256"]))
        closed = next(entry for entry in self.queue()["closed"] if entry["id"] == post["id"])
        self.assertEqual((closed["status"], closed["superseded_by"]), ("superseded", bare["id"]))
        self.assertNotIn("withdrawn", closed)
        lost = f"{why}, and the finished file `{post['asset']}` of the video `{post['id']}` named {how}"
        text = self.item(bare)
        self.assertEqual(exchange.check_item(text, ["RepToday", "Immerse"], published=True).problems, [])
        self.assertNotIn("asset:", text.split("---")[1])
        self.assertIn(
            f"**Video file**: none yet ({lost}). Approving this item approves its copy and its beat plan; the"
            " finished video comes back with this copy for approval.",
            text,
        )
        # Its copy is the copy the Founder was shown: only what it says of its video differs.
        before = self.ledger() / next(e for e in self.queue()["closed"] if e["id"] == post["id"])["file"]
        copy = [words.split("**TikTok**")[1].split("## Touches")[0] for words in (text, before.read_text("utf-8"))]
        self.assertEqual(copy[0], copy[1])
        report, notice = self.report(), self.notice()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | queued | `{bare['id']}`; replaces `{post['id']}`, without the video that one"
            f" named, which was not cut again this run ({lost}) |",
            report,
        )
        self.assertIn(f"| 1 | d01-s1 | not cut | {lost} |", report)
        told = (
            f"- Day 1's post `{post['id']}` gave way to `{bare['id']}`, which shows no video: {lost}. Approving it"
            " approves the copy alone, and the video comes back for approval once it is cut again."
        )
        self.assertIn("Posts that lost the video they named:\n\n" + told, report)
        self.assertIn(told, notice)
        self.assertIn(
            skipped or "- Day 1 has no video: shot d01-s1 has no footage, and nothing is substituted.", notice
        )
        self.assertNotIn("keeps the video it shows", (report + notice).replace("the post of day 2 keeps", ""))
        self.assertNotIn("Posts whose video's finished file was not confirmed as the file they name", report)
        self.assertIn("| Filming plan and edits | complete |", report)
        # The next run has nothing more to say of it: the post that shows no video stands.
        self.run_ok()
        self.assertEqual(self.posts_open()[1], bare)
        self.assertNotIn("gave way", self.report() + self.notice())
        self.assertNotIn("finished file", self.report())
        return bare

    def cut_again(self, post, bare):
        """One run with the video cut again: it comes back for approval in a post that takes the bare one's place."""
        self.run_ok()
        shown = self.posts_open()[1]
        self.assertEqual((shown["supersedes"], shown["asset"]), (bare["id"], post["asset"]))
        self.assertEqual((shown["asset_sha256"], shown["draft_sha256"]), (post["asset_sha256"], post["draft_sha256"]))
        self.assertEqual(footage.fingerprint(self.ledger() / post["asset"])[0], post["asset_sha256"])
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | queued | `{shown['id']}`; replaces `{bare['id']}`, with its finished video |",
            report,
        )
        self.assertNotIn("finished file", report)
        return shown

    def test_footage_away_and_the_finished_file_deleted_gives_way_to_a_post_that_shows_no_video(self):
        # As the Founder meets it: a post shows its video, the footage is put away, the finished file is deleted.
        post = self.day_1_beside_other_footage()
        clip, asset = self.footage / "window-1" / "d01-s1.mov", self.ledger() / post["asset"]
        held = clip.read_bytes()
        clip.unlink()
        self.keeps(post, self.AWAY)
        self.assertIn("could not be cut again: shot d01-s1 has no footage; its post keeps the video", self.notice())
        asset.unlink()
        bare = self.gives_way(post, self.GONE, self.AWAY)
        self.assertFalse(asset.exists())
        clip.write_bytes(held)
        self.cut_again(post, bare)

    def test_footage_away_and_the_finished_file_changed_gives_way_and_the_file_is_left_until_it_is_cut_again(self):
        post = self.day_1_beside_other_footage()
        clip, asset = self.footage / "window-1" / "d01-s1.mov", self.ledger() / post["asset"]
        held = clip.read_bytes()
        clip.unlink()
        asset.write_text("another file")
        bare = self.gives_way(post, self.CHANGED, self.AWAY)
        self.assertEqual(asset.read_text(), "another file")
        clip.write_bytes(held)
        self.cut_again(post, bare)

    def test_footage_away_and_the_finished_file_unreadable_leaves_the_open_post_and_reads_incomplete(self):
        post = self.day_1_beside_other_footage()
        (self.footage / "window-1" / "d01-s1.mov").unlink()
        readable = self.unreadable(post)
        self.told(post, self.UNREAD, self.AWAY)
        readable()
        self.keeps(post, self.AWAY)

    def no_ffmpeg(self):
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.root / "no-ffmpeg")
        problem = f"ffmpeg is not an executable at `{self.root / 'no-ffmpeg'}`"
        return (
            problem,
            f"the video tooling cannot be used ({problem})",
            f"- The edit of day 1 was skipped: {problem}.\n",
        )

    def ffmpeg_away(self, how):
        post = self.day_1()
        asset = self.ledger() / post["asset"]
        _, why, skipped = self.no_ffmpeg()
        asset.unlink()
        if how == self.CHANGED:
            asset.write_text("another file")
        bare = self.gives_way(post, how, why, skipped)
        self.env["GR0WTHLAB_FFMPEG_BIN"] = str(self.tools / "ffmpeg")
        self.cut_again(post, bare)

    def test_ffmpeg_away_and_the_finished_file_gone_gives_way_to_a_post_that_shows_no_video(self):
        self.ffmpeg_away(self.GONE)

    def test_ffmpeg_away_and_the_finished_file_changed_gives_way_to_a_post_that_shows_no_video(self):
        self.ffmpeg_away(self.CHANGED)

    def test_ffmpeg_away_and_the_finished_file_unreadable_leaves_the_open_post_and_reads_incomplete(self):
        post = self.day_1()
        problem, why, skipped = self.no_ffmpeg()
        readable = self.unreadable(post)
        self.told(post, self.UNREAD, why, skipped)
        readable()
        self.keeps(post, why)
        self.assertIn(
            f"- The edit of day 1 was skipped: {problem}; the post of day 1 keeps the video it", self.notice()
        )

    def left_the_queue(self, post, why):
        """One run after which a post that lost its video is off the queue with nothing asked in its place."""
        queue = self.run_ok()
        self.assertEqual(self.posts_open(), {})
        closed = next(entry for entry in queue["closed"] if entry["id"] == post["id"])
        self.assertEqual((closed["status"], closed["withdrawn"]), ("superseded", True))
        told = (
            f"- Day 1's post `{post['id']}` left the queue: {why}, and the finished file `{post['asset']}` of the"
            f" video `{post['id']}` named is gone. Nothing is asked in its place, since the Founder already decided"
            " this day's copy, and the video comes back for approval once it is cut again."
        )
        self.assertIn(told, self.report())
        self.assertIn(told, self.notice())
        self.assertEqual(closed["superseded_by"], max(e["id"] for e in queue["open"] if e["kind"] == "notice"))
        self.assertIn(f"the open `{post['id']}` was withdrawn", self.report())

    def test_a_post_that_adds_a_lost_video_to_an_approved_copy_leaves_the_queue_and_the_copy_is_not_asked_again(self):
        self.approved_plan()
        self.run_ok({fakes.draft_path(1): fakes.filming_draft(1)})
        copy = self.posts_open()[1]
        self.decide(copy["id"], "approve")
        clip = self.clip("d01-s1.mov")
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        post = self.posts_open()[1]
        self.assertIn("asset", post)
        clip = self.footage / "window-1" / "d01-s1.mov"
        held = clip.read_bytes()
        clip.unlink()
        (self.ledger() / post["asset"]).unlink()
        self.left_the_queue(post, self.AWAY)
        self.assertEqual([entry["id"] for entry in self.entries(status="approved")], [copy["id"]])
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | approved earlier | `{copy['id']}`; the Founder approved its copy;", self.report()
        )
        # The video comes back for approval beside the approved copy once it is cut again.
        clip.write_bytes(held)
        self.run_ok()
        again = self.posts_open()[1]
        self.assertEqual(again["asset_sha256"], post["asset_sha256"])
        self.assertIn(f"`{copy['id']}` before its video existed; this item adds the video.", self.item(again))

    def test_a_post_of_a_draft_the_founder_rejected_that_loses_its_video_leaves_the_queue_and_is_not_asked_alone(self):
        first = self.day_1()
        self.decide(first["id"], "reject", reason="Start the recording a second later.")
        self.run_ok({fakes.edit_path(1): fakes.edit_record(1, LATER)})
        post = self.posts_open()[1]
        self.assertNotEqual(post["asset"], first["asset"])
        (self.footage / "window-1" / "d01-s1.mov").unlink()
        (self.ledger() / post["asset"]).unlink()
        self.left_the_queue(post, self.AWAY)
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | not queued again | `{first['id']}`; the Founder rejected", self.report()
        )

    def test_one_leg_that_loses_its_video_shows_none_and_is_compared_with_the_other_leg_once_it_is_cut_again(self):
        drafts = self.one_week_pair()
        self.run_ok({**drafts, **self.both(DAY_1)})
        day_1, day_4 = self.posts_open()[1], self.posts_open()[4]
        self.assertEqual(self.matched, [[1, 4]])
        clip = self.footage / "window-1" / "d01-s1.mov"
        held = clip.read_bytes()
        clip.unlink()
        (self.ledger() / day_1["asset"]).unlink()
        # The pair check sees day 1 about to show no video, so the pair's rule has nothing to compare: day 4, whose
        # finished file is intact, keeps its video, and no pair is named as differing.
        self.run_ok()
        bare = self.posts_open()[1]
        self.assertEqual((bare["supersedes"], "asset" in bare), (day_1["id"], False))
        self.assertEqual(self.posts_open()[4], day_4)
        self.assertEqual(self.matched, [])
        report = self.report()
        self.assertIn(f"| 4 | d01-s1 | not cut | {self.AWAY}; its post keeps the video it shows |", report)
        self.assertNotIn("A/B pairs whose two videos differ", report)
        # Cut again, day 1's video is judged against the video day 4's post shows, as any leg cut alone is.
        clip.write_bytes(held)
        self.run_ok()
        shown = self.posts_open()[1]
        self.assertEqual((shown["supersedes"], shown["asset_sha256"]), (bare["id"], day_1["asset_sha256"]))
        self.assertEqual(self.posts_open()[4], day_4)
        self.assertEqual(self.matched, [[1, 4]])
        self.assertIn(f"the same source ranges as day 4's leg {WHOLE}", self.item(shown))
        # A leg cut again from other footage than its other leg shows is not offered, and what stood stays.
        clip.unlink()
        (self.ledger() / day_4["asset"]).unlink()
        self.run_ok()
        bare_4 = self.posts_open()[4]
        self.assertNotIn("asset", bare_4)
        clip.write_bytes(held)
        self.run_ok({fakes.edit_path(4): fakes.edit_record(4, LATER)})
        self.assertEqual(self.posts_open()[4], bare_4)
        self.assertEqual(self.posts_open()[1], shown)
        self.assertIn("A/B pairs whose two videos differ", self.report())

    def test_a_slot_set_while_the_finished_file_cannot_be_read_leaves_the_open_post_and_carries_nothing_over(self):
        post = self.day_1()
        (self.footage / "window-1" / "d01-s1.mov").unlink()
        readable = self.unreadable(post)
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 11)))
        self.run_ok()
        self.assertEqual(self.posts_open()[1], post)
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{post['id']}`; its video was not cut again ({self.AWAY}), and the"
            f" finished file `{post['asset']}` of the video it names {self.UNREAD}; the open item stands, and its new"
            " slot reaches it once the video is cut again |",
            report,
        )
        self.assertIn(f"| incomplete | the finished file `{post['asset']}` of the video day 1's post names", report)
        self.assertIn(self.lost(post, self.UNREAD), self.notice())
        # Once it can be read it is the file its record names, so the post that carries the slot shows it again.
        readable()
        self.run_ok()
        moved = self.posts_open()[1]
        self.assertEqual((moved["supersedes"], moved["asset_sha256"]), (post["id"], post["asset_sha256"]))
        self.assertIn(f"| 1 | d01-s1 | not cut | {self.AWAY}; its post keeps the video it shows |", self.report())

    def test_nothing_is_said_of_the_finished_file_of_a_post_the_founder_approved(self):
        post = self.day_1()
        self.decide(post["id"], "approve")
        self.run_ok()
        approved = self.entries(status="approved")[0]
        asset = self.ledger() / post["asset"]
        held = asset.read_bytes()

        def run():
            queue = self.run_ok()
            self.assertEqual(self.entries(status="approved"), [approved])
            self.assertEqual(self.posts_open(), {})
            self.assertNotIn("finished file", self.report())
            self.assertIn("| Filming plan and edits | complete |", self.report())
            self.assertEqual([e for e in queue["open"] if e["published_by_run"] == queue["updated_by_run"]], [])

        asset.unlink()
        run()
        asset.write_text("another file")
        run()
        asset.write_bytes(held)
        self.unreadable(post)
        run()

    def test_a_post_of_a_day_no_longer_due_is_named_and_never_said_to_be_cut_again(self):
        post = self.day_1()
        (self.ledger() / post["asset"]).unlink()
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        self.run_ok()
        self.assertEqual(self.posts_open()[1], post)
        self.assertNotIn("| 1 | d01-s1 |", self.report())
        # No run cuts a day that is not due, so the one line that names the post says it stands, and no more.
        told = self.lost(post, self.GONE, due=False)
        for text in (self.report(), self.notice()):
            self.assertIn(told, text)
            named = [line for line in text.splitlines() if f"post `{post['id']}`" in line]
            self.assertEqual(len(named), 1, named)
            self.assertNotIn("cut again", named[0])

    def test_a_run_that_could_not_queue_the_post_without_a_video_still_ends_with_its_report(self):
        post = self.day_1_beside_other_footage()
        (self.footage / "window-1" / "d01-s1.mov").unlink()
        (self.ledger() / post["asset"]).unlink()
        publish = posts.Ledger.publish

        def full(ledger, store, item, slug, *more, **named):
            if slug.startswith("post-"):
                raise OSError("the disk is full")
            return publish(ledger, store, item, slug, *more, **named)

        # The day's open post was settled to give way, and then nothing could be queued in its place.
        with mock.patch.object(posts.Ledger, "publish", full):
            self.run_ok()
        self.assertEqual(self.posts_open()[1], post)
        report, lost = self.report(), self.lost(post, self.GONE)
        self.assertIn("- Post Drafts: not taken in: the disk is full", report)
        self.assertNotIn("gave way", report + self.notice())
        self.assertIn("Posts whose video's finished file was not confirmed as the file they name:\n\n" + lost, report)
        self.assertIn(lost, self.notice())
        # The next run queues what that one could not.
        self.gives_way(post, self.GONE, self.AWAY)

    def test_the_one_check_reads_no_link_and_needs_the_record_and_the_entry_to_name_the_same_file(self):
        post = self.day_1()
        store = Store(self.ledger())
        asset, record = self.ledger() / post["asset"], self.ledger() / post["asset_record"]
        self.assertEqual(filming.posted_file(post, store), filming.OnDisk(filming.INTACT, post["asset"]))
        self.assertIsNone(filming.posted_file({"id": "a post with no video"}, store))
        self.assertIsNone(filming.posted_file(None, store))
        # A link is never read through, even to the very bytes the record names, and neither is a folder.
        moved = asset.with_name("elsewhere.mp4")
        asset.rename(moved)
        asset.symlink_to(moved)
        self.assertEqual(filming.posted_file(post, store).state, filming.UNREAD)
        asset.unlink()
        asset.mkdir()
        self.assertEqual(filming.posted_file(post, store).state, filming.UNREAD)
        asset.rmdir()
        moved.rename(asset)
        # The entry and the record must name one file with one digest.
        other = dict(post, asset_sha256="0" * 64)
        unrecorded = filming.OnDisk(filming.UNRECORDED, post["asset_record"])
        self.assertEqual(filming.posted_file(other, store), unrecorded)
        self.assertEqual(filming.posted_file(dict(post, asset_record="../config/run.json"), store).state, "no record")
        text = record.read_text(encoding="utf-8")
        record.unlink()
        self.assertEqual(filming.posted_file(post, store), unrecorded)
        self.assertTrue(unrecorded.unknown)
        self.assertEqual(
            unrecorded.told(" of the video it names"),
            f"the record `{post['asset_record']}` of the video it names cannot be read or does not name that video",
        )
        record.write_text(text, encoding="utf-8")
        self.assertTrue(filming.posted_file(post, store).intact)


class RecutRunTest(FilmingRunCase):
    def one_shot_pair(self):
        """AB-3, days 2 and 9, as one founder-on-camera shot whose opening is re-cut, with its plan approved."""
        angles = self.mandu / ANGLES
        text = angles.read_text(encoding="utf-8")
        whole = "20s founder-on-camera greeting, then a screen record of the app opening"
        self.assertIn(whole, text)
        angles.write_text(text.replace(whole, "20s founder-on-camera greeting"), encoding="utf-8")
        self.approved_plan(days=(2, 9))

    def test_a_re_cut_pair_filmed_only_as_lettered_takes_has_no_video_and_the_shared_take_is_named(self):
        self.one_shot_pair()
        self.clip("d02-s1a.mov", 20.0, 1080, 1920, 30, sound=True)
        self.clip("d02-s1b.mov", 6.0, 1080, 1920, 30, sound=True)
        why = (
            "shot d02-s1 has no take both legs can use (the legs share everything after the opening, so it needs a"
            " file named without a leg letter, such as `d02-s1.mov`)"
        )
        whole = fakes.edit_record(2, ("d02-s1", "d02-s1a.mov", 0, 20))
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2), fakes.edit_path(2): whole})
        self.assertFalse((self.ledger() / "assets").exists())
        brief = self.brief().split("## Filming")[1]
        self.assertIn(
            f"| `window-1/d02-s1a.mov` for d02-s1: 20.00s, 1080x1920, 30 fps, with sound | not ready: {why} |", brief
        )
        self.assertIn("- No day is ready for an edit record this run.", brief)
        self.assertIn(f"| 2 | d02-s1 | not cut | {why} |", self.report())
        self.assertIn(f"- Day 2 has no video: {why}, and nothing is substituted.", self.notice())
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        self.assertIn(f"**Video file**: none yet ({why}).", self.item(post))
        code, text = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, text)
        self.assertIn(f"PROBLEM day 2: drafts/edits/window-1/day-02.json will not be cut this run: {why}", text)
        # The later leg is not ready either: its own opening take is there, and nothing it can share with day 2.
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        self.run_ok()
        self.assertIn(f"| not ready: {why} |", self.brief().split("## Filming")[1].split("| 9 |")[1].split("\n")[0])
        self.assertIn(f"- Day 9 has no video: {why}, and nothing is substituted.", self.notice())
        self.assertFalse((self.ledger() / "assets").exists())

    def test_a_re_cut_leg_whose_hook_is_said_on_camera_has_no_video_until_its_own_opening_take_is_there(self):
        self.one_shot_pair()
        self.clip("d02-s1.mov", 20.0, 1080, 1920, 30, sound=True)

        def why(leg):
            take = f"d02-s1{leg.lower()}"
            return (
                f"shot d02-s1 has no opening take of leg {leg}'s own (the Founder is on camera in it and each leg opens"
                f" on its own Hook, so it needs a file named `{take}`, such as `{take}.mov`)"
            )

        # Only the take both legs share is there: neither leg is ready, though an edit record names every shot.
        whole = fakes.edit_record(2, ("d02-s1", "d02-s1.mov", 0, 20))
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2), fakes.edit_path(2): whole})
        self.assertFalse((self.ledger() / "assets").exists())
        brief = self.brief().split("## Filming")[1]
        self.assertIn(
            f"| `window-1/d02-s1.mov` for d02-s1: 20.00s, 1080x1920, 30 fps, with sound | not ready: {why('A')} |",
            brief,
        )
        self.assertIn("- No day is ready for an edit record this run.", brief)
        self.assertIn(f"| 2 | d02-s1 | not cut | {why('A')} |", self.report())
        self.assertIn(f"- Day 2 has no video: {why('A')}, and nothing is substituted.", self.notice())
        post = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertNotIn("asset", post)
        self.assertIn(f"**Video file**: none yet ({why('A')}).", self.item(post))
        code, text = self.check_edits(queue["updated_by_run"])
        self.assertEqual(code, 1, text)
        self.assertIn(f"PROBLEM day 2: drafts/edits/window-1/day-02.json will not be cut this run: {why('A')}", text)
        # With leg A's own take there the day is ready, and a record that opens on the shared take is refused.
        self.clip("d02-s1a.mov", 6.0, 1080, 1920, 30, sound=True)
        queue = self.run_ok()
        self.assertRegex(self.brief().split("## Filming")[1], r"\| 2 \|[^\n]*\| ready \|")
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertFalse((self.ledger() / "assets" / "window-1").exists())
        self.assertIn(
            "pair-legs: the Founder is on camera in shot d02-s1, where each leg of AB-3 opens on its own Hook, so"
            " under its opening leg A shows that shot only from its own take, a file named `d02-s1a`; this edit shows"
            " `window-1/d02-s1.mov` there",
            self.report(),
        )
        # The later leg is not ready either, with leg A's take and the shared one there: its own is still to film.
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        self.run_ok()
        self.assertIn(
            f"| not ready: {why('B')} |", self.brief().split("## Filming")[1].split("| 9 |")[1].split("\n")[0]
        )
        self.assertIn(f"| 9 | d02-s1 | no edit record | {why('B')} |", self.report())
        self.assertIn(f"- Day 9 has no video: {why('B')}, and nothing is substituted.", self.notice())
        self.assertFalse((self.ledger() / "assets" / "window-1").exists())

    def test_a_leg_with_only_the_other_leg_s_opening_take_is_told_which_take_of_its_own_it_lacks(self):
        self.approved_plan(days=(2, 9))
        self.clip("d02-s1a.mov", 6.0, 1080, 1920, 30, sound=True)
        self.clip("d02-s2.mov", 20.0)
        day_2 = fakes.edit_record(2, ("d02-s1", "d02-s1a.mov", 0, 3), ("d02-s2", "d02-s2.mov", 1, 18))
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2), fakes.edit_path(2): day_2})
        self.assertIn("asset", next(entry for entry in queue["open"] if entry["kind"] == "post"))
        # Day 9 can use neither file's opening: leg A's take is in the folder, and its own is the one named.
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        self.run_ok()
        why = (
            "shot d02-s1 has no opening take of leg B's own (the Founder is on camera in it and each leg opens on its"
            " own Hook, so it needs a file named `d02-s1b`, such as `d02-s1b.mov`)"
        )
        row = self.brief().split("## Filming")[1].split("| 9 |")[1].split("\n")[0]
        files = "`window-1/d02-s2.mov` for d02-s2: 20.00s, 886x1920, 60 fps, no sound"
        self.assertIn(f"| {files} | not ready: {why} |", row)
        self.assertIn(f"| 9 | d02-s1, d02-s2 | no edit record | {why} |", self.report())
        notice = self.notice()
        self.assertIn(f"- Day 9 has no video: {why}, and nothing is substituted.", notice)
        for text in (row, notice):
            self.assertNotIn("no footage", text)

    def test_a_re_cut_pair_that_opens_on_a_screen_recording_is_cut_from_the_take_both_legs_share(self):
        calendar = self.mandu / CALENDAR
        text = calendar.read_text(encoding="utf-8")
        plain = "Day 1's asset again, with only its hook swapped"
        self.assertIn(plain, text)
        calendar.write_text(text.replace(plain, "Day 1's asset again, with a re-cut start"), encoding="utf-8")
        self.approved_plan()
        plan = self.item(self.entries("filming-plan")[0])
        self.assertIn("- d01, days 1 and 8 (P01, AB-1, opening re-cut): Format in `angles.md` line 8.", plan)
        self.assertNotIn("The Founder is on camera in it", plan)
        self.clip("d01-s1.mov")
        queue = self.run_ok(
            {fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)}
        )
        brief = self.brief().split("## Filming")[1]
        self.assertIn("10s; the same source ranges as day 8 after its opening", brief)
        self.assertRegex(brief, r"\| 1 \|[^\n]*\| ready \|")
        first = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn("asset", first)
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        queue = self.run_ok(
            {fakes.draft_path(8): fakes.filming_draft(8), fakes.edit_path(8): fakes.edit_record(8, DAY_1)}
        )
        self.assertRegex(self.brief().split("## Filming")[1], r"\| 8 \|[^\n]*\| ready \|")
        second = next(entry for entry in queue["open"] if entry.get("day") == 8)
        self.assertIn("the same source ranges as day 1's leg after the re-cut opening", self.item(second))
        ours, theirs = self.asset(first), self.asset(second)
        self.assertEqual(theirs["inputs"], [str(self.footage / "window-1" / "d01-s1.mov")])
        self.assertEqual((ours["inputs"], ours["seeks"]), (theirs["inputs"], theirs["seeks"]))

    def test_a_re_cut_pair_with_its_shared_take_is_cut_and_a_lettered_take_stays_in_the_opening(self):
        self.one_shot_pair()
        self.clip("d02-s1a.mov", 20.0, 1080, 1920, 30, sound=True)
        self.clip("d02-s1b.mov", 6.0, 1080, 1920, 30, sound=True)
        self.clip("d02-s1.mov", 20.0, 1080, 1920, 30, sound=True)
        whole = fakes.edit_record(2, ("d02-s1", "d02-s1a.mov", 0, 20))
        queue = self.run_ok({fakes.draft_path(2): fakes.filming_draft(2), fakes.edit_path(2): whole})
        self.assertEqual([entry for entry in queue["open"] if entry["kind"] == "post"], [])
        self.assertFalse((self.ledger() / "assets" / "window-1").exists())
        self.assertIn(
            "pair-legs: `window-1/d02-s1a.mov` is leg A's own take, and after the opening the legs of AB-3 share"
            " their footage; use a take named without a leg letter there",
            self.report(),
        )
        day_2 = fakes.edit_record(2, ("d02-s1", "d02-s1a.mov", 0, 3), ("d02-s1", "d02-s1.mov", 3, 20))
        queue = self.run_ok({fakes.edit_path(2): day_2})
        first = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertIn("asset", first)
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        day_9 = fakes.edit_record(9, ("d02-s1", "d02-s1b.mov", 0, 3), ("d02-s1", "d02-s1.mov", 3, 20))
        queue = self.run_ok({fakes.draft_path(9): fakes.filming_draft(9), fakes.edit_path(9): day_9})
        second = next(entry for entry in queue["open"] if entry.get("day") == 9)
        self.assertIn("the same source ranges as day 2's leg after the re-cut opening", self.item(second))
        ours, theirs = self.asset(first), self.asset(second)
        self.assertEqual(ours["inputs"][1:], theirs["inputs"][1:])
        self.assertEqual(ours["seeks"][1:], theirs["seeks"][1:])
        self.assertNotEqual(ours["inputs"][0], theirs["inputs"][0])

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
            f"- Pair AB-3, days 2 and 9: the video in day 2's post `{first['id']}` and the video cut for day 9 do not"
            " show the same footage after each one's opening (day 9's shows `window-1/d02-s2.mov` 4-15s,"
            " `window-1/d02-s1-closing.mov` 5-11s, and day 2's shows `window-1/d02-s2.mov` 2-13s,"
            " `window-1/d02-s1-closing.mov` 5-11s). Nothing this run changed for either day is offered, and what stood"
            " before stays.",
            self.notice(),
        )
        # Day 9 is judged against the video day 2's post shows, by that video's own record: whatever has become of
        # the edit record it was cut from, that file is not read for it.
        day_9 = fakes.edit_record(9, ("d02-s1", "d02-s1b-take-1.mov", 0.5, 3.5), *tail)
        queue = self.run_ok({fakes.edit_path(9): day_9, fakes.edit_path(2): "not an edit record\n"})
        self.assertEqual(self.pairs_shown(), [[2, 9]])
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

    def test_an_edit_record_saved_again_in_other_bytes_is_still_the_record_its_video_was_cut_from(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        written = fakes.edit_record(1, DAY_1)
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): written})
        day_1 = next(entry for entry in queue["open"] if entry["kind"] == "post")
        # The same record is saved again: its keys in another order, other spacing, and 2.0 where it said 2.
        again = json.dumps(dict(reversed(list(json.loads(written).items()))), indent=4).replace(
            '"in": 2,', '"in": 2.0,'
        )
        self.assertIn('"in": 2.0,', again)
        queue = self.run_ok({fakes.edit_path(1): again})
        self.assertEqual((self.workspace() / fakes.edit_path(1)).read_text(encoding="utf-8"), again)
        self.assertEqual([entry["id"] for entry in queue["open"] if entry["kind"] == "post"], [day_1["id"]])
        report = self.report()
        self.assertIn(
            f"| 1 | P01 / AB-1 leg A | kept | `{day_1['id']}`; its Draft is unchanged and passes, and so is its"
            " video |",
            report,
        )
        self.assertIn(
            f"| 1 | d01-s1 | finished | `{day_1['asset']}`, 10.00s, 1080x1920, 30 fps, no sound, kept", report
        )
        filmed = json.loads((self.ledger() / f"evidence/filming/{queue['updated_by_run']}.json").read_text())
        self.assertEqual(filmed["days"][0]["edit_sha256"], day_1["edit_sha256"])
        # Day 8, a week on, is compared with day 1's video and cut.
        fakes.set_window(self.repo, fakes.window_from(date(2026, 10, 4)))
        queue = self.run_ok(
            {fakes.draft_path(8): fakes.filming_draft(8), fakes.edit_path(8): fakes.edit_record(8, DAY_1)}
        )
        day_8 = next(entry for entry in queue["open"] if entry.get("day") == 8)
        self.assertIn("; the same source ranges as day 1's leg from the first frame to the last.", self.item(day_8))
        self.assertEqual(self.pairs_shown(), [[1, 8]])

    def test_a_changed_edit_record_put_back_is_again_the_record_its_first_video_was_cut_from(self):
        self.approved_plan()
        self.clip("d01-s1.mov")
        written = fakes.edit_record(1, DAY_1)
        queue = self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): written})
        first = next(entry for entry in queue["open"] if entry["kind"] == "post")
        held = json.loads((self.ledger() / first["asset_record"]).read_text(encoding="utf-8"))["edit"]
        self.assertEqual(held["sha256"], first["edit_sha256"])
        queue = self.run_ok({fakes.edit_path(1): fakes.edit_record(1, ("d01-s1", "d01-s1.mov", 3, 13))})
        second = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual(second["supersedes"], first["id"])
        self.assertNotEqual((second["asset"], second["edit_sha256"]), (first["asset"], first["edit_sha256"]))
        # The record is put back to what the first video's own record holds of it, in bytes the agent never wrote:
        # it is the record that video was cut from, so the video is kept, not rendered again, and offered as that.
        back = json.dumps(held["record"], sort_keys=True)
        self.assertNotEqual(back, written)
        queue = self.run_ok({fakes.edit_path(1): back})
        third = next(entry for entry in queue["open"] if entry["kind"] == "post")
        self.assertEqual(third["supersedes"], second["id"])
        for key in ("asset", "asset_sha256", "asset_record", "edit_sha256"):
            self.assertEqual(third[key], first[key], key)
        self.assertIn(
            f"| 1 | d01-s1 | finished | `{first['asset']}`, 10.00s, 1080x1920, 30 fps, no sound, kept", self.report()
        )
        again = json.loads((self.ledger() / third["asset_record"]).read_text(encoding="utf-8"))["edit"]
        self.assertEqual(again, held)


class PairWalkTest(FilmingRunCase):
    """The one rule of an A/B pair's videos, through whatever happens to a pair from one run to the next: every run
    of every sequence ends with the two posts of the pair showing no two videos that differ (run_ok asserts it)."""

    LEGS = (1, 4)
    DRAFTS = {1: 1, 4: 8}  # each leg's Draft in the example set
    # What can happen to a pair between two runs, as (what, leg).
    EVENTS = (
        ("a new edit record", 1),
        ("a new edit record", 4),
        ("a Draft changed", 1),
        ("a Draft blocked", 1),
        ("a Draft unreadable", 4),
        ("a cut that fails", 1),
        ("a cut that fails", 4),
        ("an approval", 4),
        ("a rejection", 1),
        ("a record saved again", 4),
        ("a file replaced under its name", None),
        ("a file renamed", None),
    )
    # The events a third run is walked for, after any two of them.
    CORE = (("a new edit record", 1), ("a new edit record", 4), ("a cut that fails", 4))

    def setUp(self):
        super().setUp()
        held = tempfile.TemporaryDirectory()
        self.addCleanup(held.cleanup)
        self.held = Path(held.name)
        self.saves = 0
        self.seen = collections.Counter()

    def snapshot(self):
        """Everything a run reads and writes, as it is now, to walk more than one way on from here."""
        self.saves += 1
        kept = self.held / str(self.saves)
        shutil.copytree(str(self.root), str(kept), symlinks=True)
        return kept, self.runs

    def restore(self, snapshot):
        kept, self.runs = snapshot
        for entry in self.root.iterdir():
            shutil.rmtree(str(entry)) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
        shutil.copytree(str(kept), str(self.root), symlinks=True, dirs_exist_ok=True)

    def draft(self, leg):
        return fakes.filming_draft(self.DRAFTS[leg]).replace(f"day: {self.DRAFTS[leg]}", f"day: {leg}")

    def clip_now(self):
        """The pair's one footage file, under whatever name it has now."""
        return next((self.footage / "window-1").iterdir())

    def record(self, leg, later=0):
        """The leg's edit record as it is, naming the footage file as it is named now, with its one source range
        that many seconds later, or back at the start once it reaches the end of the file, so that the two legs'
        records come to differ and to agree again."""
        start = json.loads((self.workspace() / fakes.edit_path(leg)).read_text(encoding="utf-8"))["segments"][0]["in"]
        start = 2 + (start - 2 + later) % 3
        return {fakes.edit_path(leg): fakes.edit_record(leg, ("d01-s1", self.clip_now().name, start, start + 10))}

    def as_it_began(self):
        """Whether the run just made left the pair as the walk began it: no post of the pair decided, and each
        leg's post open and showing the video its Draft, its edit record, and the footage in place are cut into.
        What can follow such a run is what the walk's first runs already tried."""
        decided = [entry for entry in self.entries() if entry["status"] in ("approved", "rejected")]
        drafted = self.report().split("## Post Drafts")[1].split("## Filming")[0].splitlines()
        rows = [row for row in drafted if row.startswith(tuple(f"| {leg} |" for leg in self.LEGS))]
        shown = ("; with its finished video |", ", with its finished video |", ", and so is its video |")
        return not decided and len(rows) == len(self.LEGS) and all(row.endswith(shown) for row in rows)

    def happen(self, what, leg):
        """One event, then the run that meets it."""
        self.saves += 1
        failing = self.tools / "ffmpeg.json"
        failing.unlink(missing_ok=True)
        post = self.posts_open().get(leg)
        writes = {}
        if what == "a new edit record":
            writes = self.record(leg, later=1)
        elif what == "a Draft changed":
            writes = {fakes.draft_path(leg): self.draft(leg) + "\n" * self.saves}
        elif what == "a Draft blocked":
            hook = "Open it and the session is already waiting."
            writes = {
                fakes.draft_path(leg): self.draft(leg).replace(f"## Hook\n\n{hook}", "## Hook\n\nNo Hook of the kit.")
            }
            self.assertNotEqual(writes[fakes.draft_path(leg)], self.draft(leg))
        elif what == "a Draft unreadable":
            writes = {fakes.draft_path(leg): "not a Draft\n"}
        elif what == "a cut that fails":
            writes = self.record(leg, later=1)
            failing.write_text(json.dumps({"fail": "Error opening output files", "only": f"day-{leg:02d}"}))
        elif what in ("an approval", "a rejection") and post is not None:
            approve = what == "an approval"
            self.decide(post["id"], "approve" if approve else "reject", None if approve else "Not this one.")
        elif what == "a record saved again":
            path = self.workspace() / fakes.edit_path(leg)
            writes = {fakes.edit_path(leg): json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=self.saves)}
        elif what == "a file replaced under its name":
            fakes.fake_clip(self.clip_now(), 14.0, take=self.saves)
        elif what == "a file renamed":
            clip = self.clip_now()
            clip.rename(clip.with_name(f"d01-s1-take-{self.saves}.mov"))
            writes = {path: record for each in self.LEGS for path, record in self.record(each).items()}
        self.run_ok(writes)
        report = self.report()
        drafted = report.split("## Post Drafts")[1].split("## Filming")[0]
        self.seen["both posts show a video"] += len(self.matched)
        self.seen["a video not offered"] += "A/B pairs whose two videos differ:" in report
        self.seen["a post replaced"] += "| queued | " in drafted and "replaces `" in drafted
        self.seen["a post withdrawn"] += " was withdrawn" in drafted
        self.seen["a cut that failed"] += FAILURE in report
        self.seen["a leg settled"] += "the Founder approved it, so it is not asked again" in drafted
        self.seen["a Draft not asked again"] += "| not queued again | " in drafted
        self.seen["a file that is no longer the one a video was cut from"] += " is no longer the file day " in report
        self.seen["a compared leg"] += f"the same source ranges as day {self.LEGS[0]}'s leg" in json.dumps(
            self.checks_of(self.LEGS[1])
        )

    def test_no_sequence_of_pair_events_leaves_two_posts_showing_videos_that_differ(self):
        drafts = self.one_week_pair()
        self.run_ok(dict(drafts, **self.both(DAY_1)))
        self.assertEqual(self.pairs_shown(), [[1, 4]])
        self.assertTrue(self.as_it_began())
        start = self.snapshot()
        walked = collections.Counter()
        for first in self.EVENTS:
            self.restore(start)
            with self.subTest(events=(first,)):
                self.happen(*first)
                walked[1] += 1
                if self.as_it_began():
                    continue
                after_one = self.snapshot()
                for second in self.EVENTS:
                    self.restore(after_one)
                    with self.subTest(events=(first, second)):
                        self.happen(*second)
                        walked[2] += 1
                        if first not in self.CORE or second not in self.CORE or self.as_it_began():
                            continue
                        after_two = self.snapshot()
                        for third in self.CORE:
                            self.restore(after_two)
                            with self.subTest(events=(first, second, third)):
                                self.happen(*third)
                                walked[3] += 1
        # Every event was tried first, most of them leave the pair other than it began and were walked on from with
        # every event, and some of those twice.
        self.assertEqual(walked[1], len(self.EVENTS))
        self.assertEqual(walked[2] % len(self.EVENTS), 0)
        self.assertGreater(walked[2], len(self.EVENTS) ** 2 // 2)
        self.assertGreater(walked[3], len(self.CORE) ** 2)
        # The walk met every way a pair's posts can come out of a run, so the rule was tried against each.
        for outcome in (
            "both posts show a video",
            "a video not offered",
            "a post replaced",
            "a post withdrawn",
            "a cut that failed",
            "a leg settled",
            "a Draft not asked again",
            "a file that is no longer the one a video was cut from",
            "a compared leg",
        ):
            self.assertGreater(self.seen[outcome], 0, outcome)


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

    def test_a_real_finished_file_deleted_while_its_footage_is_away_gives_way_and_is_cut_again_the_same(self):
        tooling, _, why = fakes.real_video_tools()
        if why:
            self.skipTest(why)
        shutil.copy(str(fakes.REPO / "config" / "platforms.json"), str(self.repo / "config" / "platforms.json"))
        for name in ("GR0WTHLAB_FFMPEG_BIN", "GR0WTHLAB_FFPROBE_BIN"):
            del self.env[name]
        self.env["PATH"] = os.environ["PATH"]
        self.approved_plan()
        clip = self.footage / "window-1" / "d01-s1.mov"
        fakes.make_test_clip(tooling, clip, 14, 886, 1920, 60)
        self.run_ok({fakes.draft_path(1): fakes.filming_draft(1), fakes.edit_path(1): fakes.edit_record(1, DAY_1)})
        post = self.posts_open()[1]
        asset = self.ledger() / post["asset"]
        away = self.root / "put-away.mov"
        clip.rename(away)
        asset.unlink()
        self.run_ok()
        bare = self.posts_open()[1]
        self.assertEqual((bare["supersedes"], "asset" in bare), (post["id"], False))
        why = (
            f"no footage yet for shot d01-s1, and the finished file `{post['asset']}` of the video `{post['id']}`"
            " named is gone"
        )
        self.assertIn(f"**Video file**: none yet ({why}).", self.item(bare))
        gone = (
            f"- Day 1's post `{post['id']}` gave way to `{bare['id']}`, which shows no video: {why}. Approving it"
            " approves the copy alone, and the video comes back for approval once it is cut again."
        )
        self.assertIn(gone, self.report())
        self.assertIn(gone, self.notice())
        self.assertNotIn("keeps the video it shows", self.report() + self.notice() + self.brief())
        self.assertFalse(asset.exists())
        away.rename(clip)
        self.run_ok()
        shown = self.posts_open()[1]
        self.assertEqual((shown["supersedes"], shown["asset_sha256"]), (bare["id"], post["asset_sha256"]))
        self.assertEqual(footage.fingerprint(asset)[0], post["asset_sha256"])
        self.assertNotIn("finished file", self.report())


if __name__ == "__main__":
    unittest.main()
