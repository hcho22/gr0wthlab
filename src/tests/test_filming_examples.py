"""The filming example set (F5): every deterministic assertion in src/examples/filming/evals.json holds."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import drafts, edits, exchange, filming, footage, shots, video
from tests import fakes

EVALS = fakes.FILMING / "evals.json"
PLAN_CHECKS = ("plan_is_one_item", "plan_films", "plan_reuses", "plan_on_camera", "plan_unplanned", "plan_sittings")
TOOLING, CANVAS, WHY_NOT = fakes.real_video_tools()
# The five cases every filming example set must cover: these by the rule that blocks each, a rendered asset that is
# not 9:16 by the words of its finding, and a leg whose video differs from its other leg's by the check of the two.
MUST_BLOCK = ("no-cut", "missing-shot", "footage-place")


class FilmingExampleSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(os.path.realpath(cls.tmp.name))
        cls.data = json.loads(EVALS.read_text(encoding="utf-8"))
        cls.kit, cls.roles = fakes.filming_kit(cls.root / "Mandu")
        cls.found = shots.requirements(cls.kit, cls.roles["calendar"])
        held = json.loads((fakes.FILMING / cls.data["footage"]).read_text(encoding="utf-8"))
        cls.clips = {clip["name"]: edits.Clip.from_json(clip) for clip in held["clips"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def plan(self):
        made = filming.Filming(
            "RepToday",
            1,
            "run",
            filming.Place("RepToday", None, ""),
            CANVAS,
            video.Tooling(None, None),
            filming.Standing(filming.NOT_FILED),
            footage.Inventory(None, "window-1", footage.NOT_SET),
            Path("drafts/posts/window-1"),
            Path("drafts/edits/window-1"),
            requirements=self.found,
            paths=self.roles,
            calendar_lines=[day.line for day in self.kit.days.values()],
            screen_rule=shots.screen_rule(self.kit.asset_checks),
        )
        return filming.plan_item(made)

    def read(self, example):
        """An edit example's record and Draft, then its reference leg's, parsed as a run parses them."""
        parsed = []
        for name in example["files"]:
            text = (fakes.FILMING / name).read_text(encoding="utf-8")
            parsed.append(edits.parse(text, name) if name.endswith(".json") else drafts.parse(text, name))
        return parsed

    def spec(self, draft):
        return filming.day_spec("RepToday", 1, draft.day, self.kit.days[draft.day].leg, self.found.job_for(draft.day))

    def findings(self, example):
        edit, draft, *_ = self.read(example)
        return edits.check(edit, self.spec(draft), self.clips, draft, CANVAS)

    def legs_differ(self, example):
        """How the video cut from an example's record and the video of its other leg differ, as the pair check reads
        the two from their own records; "" when they show the same footage outside each one's opening."""
        edit, draft, theirs, their_draft = self.read(example)
        shown = [
            {
                "day": text.day,
                "opening": [list(window) for window in edits.opening_windows(text, self.spec(text).hooks)],
                "cuts": [
                    dict(segment.as_json(), sha256=self.clips[segment.source].sha256) for segment in record.segments
                ],
            }
            for record, text in ((edit, draft), (theirs, their_draft))
        ]
        return edits.unlike(*shown)

    def test_the_set_has_the_evals_json_shape_and_covers_every_case_it_must(self):
        self.assertEqual(self.data["skill_name"], "filming")
        ids = [example["id"] for example in self.data["evals"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertGreaterEqual(len(ids), 10)
        for example in self.data["evals"]:
            self.assertEqual(sorted(example), ["assertions", "expected_output", "files", "id", "prompt"])
            self.assertTrue(all((fakes.FILMING / name).is_file() for name in example["files"]), example["id"])
            kinds = {assertion["kind"] for assertion in example["assertions"]}
            self.assertLessEqual(kinds, {"deterministic", "judged"})
            self.assertIn("deterministic", kinds)
        checks = [assertion for example in self.data["evals"] for assertion in example["assertions"]]
        blocked = {assertion["rule"] for assertion in checks if assertion.get("check") == "blocked_by"}
        for rule in MUST_BLOCK:
            self.assertIn(rule, blocked)
        self.assertTrue(any("not 9:16" in assertion.get("says", "") for assertion in checks))
        self.assertTrue(any(assertion.get("check") == "legs_not_offered" for assertion in checks))
        self.assertTrue(any(assertion.get("check") == "legs_differ_only_in_the_opening" for assertion in checks))

    def test_no_media_file_is_in_the_repository(self):
        tracked = fakes.git(fakes.REPO, "ls-files").splitlines()
        media = [name for name in tracked if name.lower().endswith((".mov", ".mp4", ".m4v"))]
        self.assertEqual(media, [])

    def test_every_deterministic_assertion_that_needs_no_tooling_holds(self):
        for example in self.data["evals"]:
            for assertion in example["assertions"]:
                if assertion["kind"] != "deterministic" or assertion.get("needs"):
                    continue
                with self.subTest(example=example["id"], check=assertion["check"], rule=assertion.get("rule")):
                    self.assertTrue(*self.holds(assertion, example))

    def holds(self, assertion, example):
        check = assertion["check"]
        if check in PLAN_CHECKS or check == "plan_quotes_formats":
            return self.plan_holds(assertion)
        if check in ("asset_blocked", "asset_kept"):
            measured = json.loads((fakes.FILMING / example["files"][0]).read_text(encoding="utf-8"))
            problems = video.verify(video.Facts.from_json(measured), CANVAS, measured["duration"])
            if check == "asset_kept":
                return problems == [], problems
            return any(assertion["says"] in problem for problem in problems), problems
        found = self.findings(example)
        lines = [finding.line() for finding in found]
        if check == "legs_not_offered":
            differ = self.legs_differ(example)
            return found == [] and assertion["says"] in differ, lines + [differ]
        if check == "edit_passes":
            differ = self.legs_differ(example) if len(example["files"]) > 2 else ""
            return found == [] and not differ, lines + [differ]
        if check == "blocked_by":
            # An example claims every rule its record is blocked by, so no case trips a rule it is not about.
            named = {other["rule"] for other in example["assertions"] if other.get("check") == "blocked_by"}
            rules = {finding.rule for finding in found}
            return assertion["rule"] in rules and rules <= named, lines
        raise AssertionError(f"unknown check {check}")

    def plan_holds(self, assertion):
        check, found = assertion["check"], self.found
        if check == "plan_is_one_item":
            item = self.plan()
            text = exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence)
            problems = exchange.check_item(text, ["RepToday"]).problems
            return item.kind == "filming-plan" and not problems, problems
        if check == "plan_films":
            return [job.films for job in found.jobs] == assertion["days"], [job.films for job in found.jobs]
        if check == "plan_reuses":
            return found.reuse_days() == assertion["days"], found.reuse_days()
        if check == "plan_on_camera":
            return found.on_camera_days() == assertion["days"], found.on_camera_days()
        if check == "plan_unplanned":
            return [day for day, _ in found.unplanned] == assertion["days"], found.unplanned
        if check == "plan_sittings":
            return len(shots.sittings(found)) == assertion["count"], shots.sittings(found)
        body = self.plan().body
        missing = [shot.what for _, shot in found.shots() if f"| {shot.what} |" not in body]
        cited = all(f"Format in `angles.md` line {job.line}." in body for job in found.jobs)
        return not missing and cited, missing

    @unittest.skipIf(WHY_NOT, WHY_NOT)
    def test_the_examples_that_render_make_9_16_assets_whose_legs_differ_only_in_the_opening(self):
        """Test clips with the measured facts of files/footage.json, made from ffmpeg's own test pattern, are cut by
        the day 1 and day 8 example records: both assets measure as the canvas asks, and frame for frame they are the
        same picture after the hook beat and differ before it."""
        place = self.root / "footage"
        held = self.clips["window-1/d01-s1.mov"]
        facts = held.facts
        fakes.make_test_clip(TOOLING, place / held.name, facts.duration, facts.width, facts.height, int(facts.fps))
        before = fakes.tree_digest(place)
        env = dict(os.environ)
        found = footage.read(place, 1, {"d01-s1"}, TOOLING, env)
        measured = found.clips[held.name].facts
        self.assertEqual((measured.width, measured.height, measured.fps), (facts.width, facts.height, facts.fps))
        examples = {example["id"]: example for example in self.data["evals"]}
        needing = [
            example
            for example in self.data["evals"]
            if any(assertion.get("needs") for assertion in example["assertions"])
        ]
        self.assertEqual([example["id"] for example in needing], [2, 3])
        assets = {}
        for example in needing:
            edit, draft, *_ = self.read(example)
            day = self.kit.days[draft.day]
            spec = filming.day_spec("RepToday", 1, draft.day, day.leg, self.found.job_for(draft.day))
            self.assertEqual(edits.check(edit, spec, found.clips, draft, CANVAS), [])
            cuts = [
                video.Cut(found.path(found.clips[cut.source]), cut.start, cut.end, cut.speed, measured)
                for cut in edit.segments
            ]
            assets[draft.day] = self.root / "assets" / f"day-{draft.day:02d}.mp4"
            video.render(TOOLING, CANVAS, cuts, edits.overlays(draft), assets[draft.day], env)
            rendered = video.probe(TOOLING, assets[draft.day], env)
            self.assertEqual(video.verify(rendered, CANVAS, edit.length), [], example["id"])
        self.assertEqual(examples[3]["assertions"][1]["check"], "legs_differ_only_in_the_opening")

        def likeness(start, length):
            command = [str(TOOLING.ffmpeg), "-nostdin", "-hide_banner", "-ss", str(start), "-t", str(length)]
            command += ["-i", str(assets[1]), "-ss", str(start), "-t", str(length), "-i", str(assets[8])]
            said = subprocess.run(
                command + ["-lavfi", "ssim", "-f", "null", "-"], capture_output=True, text=True
            ).stderr
            return float(said.rsplit("All:", 1)[1].split()[0])

        self.assertGreater(likeness(3.2, 6.5), 0.995)
        self.assertLess(likeness(0, 2.8), 0.99)
        self.assertEqual(fakes.tree_digest(place), before)


if __name__ == "__main__":
    unittest.main()
