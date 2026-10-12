"""The video tooling: finding it, measuring a file, composing a render, and checking a finished asset."""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
import unittest.mock
from dataclasses import replace
from pathlib import Path

from gr0wthlab import video
from tests import fakes

PLATFORMS = json.loads((fakes.REPO / "config" / "platforms.json").read_text(encoding="utf-8"))
CANVAS = video.load_canvas(PLATFORMS)
SCREEN = video.Facts(14.0, 886, 1920, 60.0, "h264", "yuv420p", False)
CAMERA = video.Facts(8.0, 1080, 1920, 30.0, "h264", "yuv420p", True)
FINISHED = video.Facts(10.0, 1080, 1920, 30.0, "h264", "yuv420p", False)
TOOLS = video.Tooling(Path("/opt/tools/ffmpeg"), Path("/opt/tools/ffprobe"), "ffmpeg version 7.1.1", converts_hdr=True)
# Every filter a render may use, named here and not read from the renderer: each only trims, retimes, resizes, pads,
# joins, converts colour or sound format, or draws text, and anullsrc, the one that makes something, makes silence.
PICTURE = {"setpts", "fps", "trim", "scale", "pad", "setsar", "format", "concat", "subtitles", "null"}
SOUND = {"aresample", "aformat", "apad", "atrim", "asetpts", "anullsrc"}
TO_SDR = {"zscale", "tonemap"}
ALLOWED = PICTURE | SOUND | TO_SDR


def filters(graph):
    """The name of every filter in a filter graph: what each step of each chain starts with, once its labels are
    taken off."""
    steps = [step for chain in graph.split(";") for step in re.sub(r"\[[^\]]*\]", "", chain).split(",")]
    return {step.split("=", 1)[0].strip() for step in steps}


class CanvasTest(unittest.TestCase):
    def test_the_configured_canvas_is_9_16_at_1080_by_1920_with_the_safe_zone(self):
        self.assertEqual((CANVAS.width, CANVAS.height, CANVAS.fps), (1080, 1920, 30))
        self.assertEqual((CANVAS.ratio.numerator, CANVAS.ratio.denominator), (9, 16))
        self.assertEqual(CANVAS.shape, "1080x1920 (9:16)")
        self.assertEqual((CANVAS.top, CANVAS.bottom, CANVAS.left, CANVAS.right), (220, 500, 180, 180))
        self.assertTrue(CANVAS.font.is_absolute())
        self.assertEqual(video.Canvas(**dict(CANVAS.as_json(), font=Path(CANVAS.as_json()["font"]))), CANVAS)

    def test_a_canvas_that_could_not_hold_text_or_be_encoded_is_refused(self):
        block = PLATFORMS["video"]
        for change, said in (
            ({"width": 1081}, "width and height must be even"),
            ({"fps": 0}, "fps must be a whole number from 1"),
            ({"safe_zone": dict(block["safe_zone"], left=600, right=600)}, "safe_zone leaves no room for text"),
            ({"text": dict(block["text"], font_file="Arial Bold.ttf")}, "font_file, an absolute path"),
            ({"safe_zone": None}, "needs safe_zone and text"),
        ):
            with self.subTest(said=said), self.assertRaisesRegex(ValueError, said):
                video.load_canvas({"video": dict(block, **change)})
        with self.assertRaisesRegex(ValueError, "no video block"):
            video.load_canvas({})


class FactsTest(unittest.TestCase):
    def probed(self, **stream):
        picture = dict(
            codec_type="video",
            codec_name="hevc",
            pix_fmt="yuv420p10le",
            width=1920,
            height=1080,
            avg_frame_rate="30000/1001",
            duration="12.5",
            sample_aspect_ratio="1:1",
        )
        return {"streams": [dict(picture, **stream), {"codec_type": "audio"}], "format": {"duration": "12.6"}}

    def test_what_ffprobe_measured_is_read_as_displayed(self):
        facts = video.facts_of(self.probed())
        self.assertEqual((facts.duration, facts.width, facts.height, facts.fps), (12.5, 1920, 1080, 29.97))
        self.assertEqual((facts.codec, facts.pix_fmt, facts.sound, facts.hdr), ("hevc", "yuv420p10le", True, False))
        self.assertEqual(facts.describe(), "12.50s, 1920x1080, 29.97 fps, with sound")
        self.assertEqual(video.Facts.from_json(facts.as_json()), facts)

    def test_a_phone_s_upright_recording_is_measured_upright(self):
        turned = video.facts_of(self.probed(side_data_list=[{"side_data_type": "Display Matrix", "rotation": -90}]))
        self.assertEqual((turned.width, turned.height, turned.shape()), (1080, 1920, "1080x1920 (9:16)"))
        flipped = video.facts_of(self.probed(side_data_list=[{"rotation": 180}]))
        self.assertEqual((flipped.width, flipped.height), (1920, 1080))

    def test_hdr_footage_is_told_by_its_transfer(self):
        for transfer in ("arib-std-b67", "smpte2084"):
            self.assertTrue(video.facts_of(self.probed(color_transfer=transfer)).hdr)
        self.assertFalse(video.facts_of(self.probed(color_transfer="bt709")).hdr)

    def test_a_file_with_no_video_or_no_size_is_not_measured(self):
        with self.assertRaisesRegex(video.VideoError, "it holds no video"):
            video.facts_of({"streams": [{"codec_type": "audio"}], "format": {"duration": "3"}})
        with self.assertRaisesRegex(video.VideoError, "its size or length could not be measured"):
            video.facts_of({"streams": [{"codec_type": "video", "width": 1080}], "format": {}})


class VerifyTest(unittest.TestCase):
    def test_an_asset_that_measures_as_the_canvas_asks_is_kept(self):
        self.assertEqual(video.verify(FINISHED, CANVAS, 10.0), [])
        self.assertEqual(video.verify(replace(FINISHED, duration=10.03), CANVAS, 10.0), [])

    def test_an_asset_that_is_not_9_16_is_named_by_its_measured_shape(self):
        problems = video.verify(replace(FINISHED, width=1920, height=1080), CANVAS, 10.0)
        self.assertEqual(problems, ["it measures 1920x1080 (16:9), which is not 9:16"])
        squashed = video.verify(replace(FINISHED, square_pixels=False), CANVAS, 10.0)
        self.assertEqual(squashed, ["it measures 1080x1920 (9:16), with pixels that are not square, which is not 9:16"])

    def test_a_9_16_asset_of_another_resolution_is_named_too(self):
        problems = video.verify(replace(FINISHED, width=720, height=1280), CANVAS, 10.0)
        self.assertEqual(problems, ["it measures 720x1280, not the expected 1080x1920"])

    def test_the_frame_rate_the_length_the_encoding_and_hdr_are_measured(self):
        self.assertEqual(
            video.verify(replace(FINISHED, fps=60.0), CANVAS, 10.0), ["it measures 60 frames a second, not 30"]
        )
        self.assertEqual(
            video.verify(replace(FINISHED, duration=9.5), CANVAS, 10.0),
            ["it measures 9.50s, not the 10.00s its edit record adds up to"],
        )
        self.assertEqual(
            video.verify(replace(FINISHED, codec="hevc", pix_fmt="yuv420p10le"), CANVAS, 10.0),
            ["it is hevc yuv420p10le, not h264 yuv420p"],
        )
        self.assertIn("it is HDR", video.verify(replace(FINISHED, transfer="arib-std-b67"), CANVAS, 10.0)[0])


class ComposeTest(unittest.TestCase):
    def cut(self, name, start, end, facts=SCREEN, speed=1.0):
        return video.Cut(Path("/footage/window-1") / name, start, end, speed, facts)

    def test_text_is_drawn_inside_the_safe_zone_white_on_a_black_outline(self):
        text = video.subtitles(
            CANVAS, [video.Overlay(0, 3, "Open  it\nnow"), video.Overlay(3, 8.5, "A spoken line.", caption=True)]
        )
        self.assertIn("PlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n", text)
        self.assertIn("Style: Text,Arial,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,", text)
        self.assertIn(",1,6,0,8,180,180,220,1\n", text)  # outlined, hung from the top of the safe zone
        self.assertIn("Style: Caption,Arial,52,", text)
        self.assertIn(",1,6,0,2,180,180,500,1\n", text)  # standing on the bottom of the safe zone
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:03.00,Text,,0,0,0,,Open it now\n", text)
        self.assertIn("Dialogue: 0,0:00:03.00,0:00:08.50,Caption,,0,0,0,,A spoken line.\n", text)
        self.assertEqual(video.stamp(3725.25), "1:02:05.25")

    def test_a_render_reads_only_its_cuts_footage_and_writes_only_its_output(self):
        cuts = [self.cut("d02-s1a.mov", 1, 4, CAMERA), self.cut("d02-s2.mov", 2, 13)]
        command = video.command(TOOLS, CANVAS, cuts, True, Path("/ledger/assets/out.mp4"))
        self.assertEqual(command[0], "/opt/tools/ffmpeg")
        inputs = [command[index + 1] for index, word in enumerate(command) if word == "-i"]
        self.assertEqual(inputs, ["/footage/window-1/d02-s1a.mov", "/footage/window-1/d02-s2.mov"])
        seeks = [(command[index + 1], command[index + 3]) for index, word in enumerate(command) if word == "-ss"]
        self.assertEqual(seeks, [("1.000000", "3.000000"), ("2.000000", "11.000000")])
        self.assertEqual(command[-1], "/ledger/assets/out.mp4")
        self.assertEqual(command[command.index("-t", command.index("-map")) + 1], "14.000000")
        # No input is a generator: nothing but footage files goes in.
        self.assertNotIn("lavfi", command)
        self.assertNotIn("-f", command[: command.index("-filter_complex")])
        for flag in ("-nostdin", "-y", "libx264", "yuv420p", "+faststart", "+bitexact"):
            self.assertIn(flag, command)

    def test_the_filter_graph_only_trims_retimes_resizes_joins_and_draws_text(self):
        cuts = [
            self.cut("a.mov", 1, 4, CAMERA),
            self.cut("b.mov", 2, 13),
            self.cut("c.mov", 0, 300, replace(CAMERA, duration=330.0, transfer="arib-std-b67"), speed=20.0),
        ]
        for text in (True, False):
            graph, sound = video.graph(CANVAS, cuts, text)
            self.assertTrue(sound)
            self.assertEqual(filters(graph) - ALLOWED, set())
        graph, _ = video.graph(CANVAS, cuts, True)
        self.assertEqual(filters(graph), ALLOWED - {"null"})
        made_up = "[0:v:0]testsrc2=size=1080x1920,geq=random(1)[v0];[v0]null[vout]"
        self.assertEqual(filters(made_up) - ALLOWED, {"testsrc2", "geq"})
        self.assertIn("[0:v:0]setpts=(PTS-STARTPTS)/1.000000,fps=30,trim=duration=3.000000", graph)
        self.assertIn(f"[2:v:0]{video.TO_SDR},setpts=(PTS-STARTPTS)/20.000000,fps=30,trim=duration=15.000000", graph)
        self.assertIn("concat=n=3:v=1:a=1[vc][ac]", graph)
        self.assertTrue(graph.endswith("[vc]subtitles=overlay.ass:fontsdir=fonts[vout]"))

    def test_every_cut_is_fitted_whole_into_the_frame_and_never_cropped(self):
        wide = replace(CAMERA, width=1920, height=1080)
        cuts = [self.cut("a.mov", 1, 4, CAMERA), self.cut("b.mov", 2, 13), self.cut("c.mov", 0, 4, wide)]
        graph, _ = video.graph(CANVAS, cuts, False)
        fit = (
            "scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p"
        )
        self.assertEqual(graph.count(fit), 3)
        self.assertEqual((graph.count("scale="), graph.count("pad=")), (3, 3))
        self.assertNotIn("crop", graph)
        self.assertNotIn("increase", graph)

    def test_the_only_thing_made_from_nothing_is_silence_for_a_cut_with_no_sound(self):
        spoken, shown, sped = (
            self.cut("a.mov", 1, 4, CAMERA),
            self.cut("b.mov", 2, 13),
            self.cut("c.mov", 0, 8, CAMERA, speed=2.0),
        )
        graph, sound = video.graph(CANVAS, [spoken, shown, sped], False)
        self.assertTrue(sound)
        self.assertIn(
            "[0:a:0]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration=3.0", graph
        )
        self.assertEqual(graph.count("anullsrc=r=44100:cl=stereo"), 2)  # the silent recording, and the sped-up cut
        self.assertNotIn("[1:a:0]", graph)
        self.assertNotIn("[2:a:0]", graph)
        self.assertTrue(graph.endswith("[vc]null[vout]"))
        silent, sound = video.graph(CANVAS, [shown], False)
        self.assertFalse(sound)
        self.assertNotIn("anullsrc", silent)
        self.assertIn("concat=n=1:v=1:a=0[vc]", silent)
        # Sound is decided by rule: a cut that plays at another speed never carries its recording's sound.
        self.assertEqual((spoken.sound, shown.sound, sped.sound), (True, False, False))
        lapse, sound = video.graph(CANVAS, [sped], False)
        self.assertFalse(sound)
        self.assertEqual(filters(lapse) & SOUND, set())
        for cuts in ([shown], [sped]):
            command = video.command(TOOLS, CANVAS, cuts, False, Path("/out.mp4"))
            self.assertNotIn("aac", command)
            self.assertNotIn("[ac]", command)


class ToolingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.env = dict(fakes.install_video_tools(self.root / "tools"), PATH="/usr/bin:/bin", HOME=str(self.root))
        self.canvas = replace(CANVAS, font=self.root / "font.ttf")
        self.canvas.font.write_text("a font")

    def tearDown(self):
        self.tmp.cleanup()

    def test_tooling_that_has_everything_an_edit_needs_is_usable(self):
        tooling = video.find(self.env, self.canvas)
        self.assertEqual((tooling.ok, tooling.version, tooling.converts_hdr), (True, fakes.FAKE_FFMPEG_VERSION, True))
        self.assertEqual(tooling.describe(), f"{fakes.FAKE_FFMPEG_VERSION} at `{self.root}/tools/ffmpeg`")

    def test_missing_tooling_is_a_finding_with_its_reason_never_an_error(self):
        nowhere = video.find(dict(self.env, GR0WTHLAB_FFMPEG_BIN=str(self.root / "none")), self.canvas)
        self.assertFalse(nowhere.ok)
        self.assertEqual(nowhere.problem, f"ffmpeg is not an executable at `{self.root}/none`")
        with unittest.mock.patch.object(video, "SEARCH", (str(self.root / "empty"),)):
            absent = video.find({"PATH": str(self.root / "also-empty")}, self.canvas)
        self.assertEqual(absent.problem, f"ffmpeg was not found on the PATH or in {self.root}/empty")
        unprobed = video.find(dict(self.env, GR0WTHLAB_FFPROBE_BIN="relative/ffprobe"), self.canvas)
        self.assertEqual(unprobed.problem, "ffprobe is not an executable at `relative/ffprobe`")

    def test_tooling_is_found_where_homebrew_installs_it_when_the_path_does_not_name_it(self):
        # launchd's PATH names neither Homebrew folder, so a scheduled run finds the tooling by looking there.
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.root)}
        with unittest.mock.patch.object(video, "SEARCH", (str(self.root / "empty"), str(self.root / "tools"))):
            tooling = video.find(env, self.canvas)
        self.assertTrue(tooling.ok, tooling.problem)
        self.assertEqual(tooling.ffmpeg, self.root / "tools" / "ffmpeg")
        self.assertEqual(tooling.ffprobe, self.root / "tools" / "ffprobe")
        self.assertEqual(video.environment(env)["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")

    def test_tooling_that_lacks_a_filter_or_the_font_names_what_it_lacks(self):
        (self.root / "tools" / "ffmpeg.json").write_text(json.dumps({"lacks": ["subtitles"]}))
        self.assertEqual(
            video.find(self.env, self.canvas).problem, f"{fakes.FAKE_FFMPEG_VERSION} lacks the subtitles filter"
        )
        (self.root / "tools" / "ffmpeg.json").write_text(json.dumps({"lacks": ["zscale"]}))
        without_hdr = video.find(self.env, self.canvas)
        self.assertEqual((without_hdr.ok, without_hdr.converts_hdr), (True, False))
        (self.root / "tools" / "ffmpeg.json").unlink()
        fontless = video.find(self.env, replace(self.canvas, font=self.root / "missing.ttf"))
        self.assertEqual(fontless.problem, f"{fakes.FAKE_FFMPEG_VERSION} lacks the font `{self.root}/missing.ttf`")

    def test_a_render_writes_its_output_whole_or_not_at_all(self):
        tooling = video.find(self.env, self.canvas)
        clip = fakes.fake_clip(self.root / "footage" / "window-1" / "d01-s1.mov", 14.0)
        before = fakes.tree_digest(self.root / "footage")
        cut = video.Cut(clip, 2.0, 12.0, 1.0, video.probe(tooling, clip, self.env))
        out = self.root / "ledger" / "assets" / "window-1" / "day-01.mp4"
        video.render(tooling, self.canvas, [cut], [video.Overlay(0, 3, "Open it.")], out, self.env)
        made = json.loads(out.read_text())
        self.assertEqual(made["inputs"], [str(clip)])
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:03.00,Text,,0,0,0,,Open it.", made["text"])
        self.assertEqual(video.verify(video.probe(tooling, out, self.env), self.canvas, 10.0), [])
        self.assertEqual(sorted(path.name for path in out.parent.iterdir()), ["day-01.mp4"])
        # A render that fails part way leaves the half-written file it was making nowhere, and what stood stands.
        (self.root / "tools" / "ffmpeg.json").write_text(json.dumps({"fail": "Conversion failed!"}))
        log = self.root / "tools" / "partial.log"
        failed = out.with_name("day-02.mp4")
        for target in (failed, out):
            with self.assertRaisesRegex(video.VideoError, r"ffmpeg did not finish the render \(Conversion failed!\)"):
                video.render(tooling, self.canvas, [cut], [], target, self.env)
            self.assertEqual(sorted(path.name for path in out.parent.iterdir()), ["day-01.mp4"])
        written = log.read_text().splitlines()
        self.assertEqual([Path(line).parent for line in written], [out.parent, out.parent])
        self.assertNotIn(str(out), written)
        self.assertEqual(json.loads(out.read_text()), made)
        self.assertEqual(fakes.tree_digest(self.root / "footage"), before)

    def test_hdr_footage_is_not_rendered_by_tooling_that_cannot_convert_it(self):
        (self.root / "tools" / "ffmpeg.json").write_text(json.dumps({"lacks": ["tonemap"]}))
        tooling = video.find(self.env, self.canvas)
        clip = fakes.fake_clip(self.root / "footage" / "d02-s1.mov", 8.0, 1080, 1920, 30, transfer="arib-std-b67")
        cut = video.Cut(clip, 0.0, 3.0, 1.0, video.probe(tooling, clip, self.env))
        with self.assertRaisesRegex(video.VideoError, "lacks the zscale and tonemap filters that convert HDR footage"):
            video.render(tooling, self.canvas, [cut], [], self.root / "out.mp4", self.env)
        self.assertFalse((self.root / "out.mp4").exists())

    def test_a_file_ffprobe_cannot_read_is_not_measured(self):
        tooling = video.find(self.env, self.canvas)
        (self.root / "notes.mov").write_text("not a video")
        with self.assertRaisesRegex(video.VideoError, "ffprobe could not read it .*Invalid data found"):
            video.probe(tooling, self.root / "notes.mov", self.env)


TOOLING, REAL_CANVAS, WHY_NOT = fakes.real_video_tools()


@unittest.skipIf(WHY_NOT, WHY_NOT)
class RealToolingTest(unittest.TestCase):
    """The same steps with the real ffmpeg and ffprobe, on test clips made from ffmpeg's own test pattern."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(os.path.realpath(cls.tmp.name))
        cls.env = dict(os.environ)
        cls.screen = fakes.make_test_clip(TOOLING, cls.root / "footage" / "d01-s1.mov", 6, 886, 1920, 60)
        cls.camera = fakes.make_test_clip(TOOLING, cls.root / "footage" / "d02-s1.mov", 4, 1920, 1080, 30, sound=True)
        cls.before = fakes.tree_digest(cls.root / "footage")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def cut(self, path, start, end, **more):
        facts = video.probe(TOOLING, path, self.env)
        return video.Cut(path, start, end, more.get("speed", 1.0), facts)

    def test_footage_is_measured(self):
        screen = video.probe(TOOLING, self.screen, self.env)
        self.assertEqual((screen.width, screen.height, screen.fps, screen.sound), (886, 1920, 60.0, False))
        self.assertAlmostEqual(screen.duration, 6.0, places=1)
        self.assertTrue(video.probe(TOOLING, self.camera, self.env).sound)

    def test_a_render_measures_9_16_at_the_canvas_s_resolution_and_is_repeatable(self):
        out = self.root / "assets" / "screen.mp4"
        cuts = [self.cut(self.screen, 1.0, 5.0)]
        text = [
            video.Overlay(0, 2, "Stand-in test footage, not a real recording."),
            video.Overlay(2, 4, "Still a test."),
        ]
        video.render(TOOLING, REAL_CANVAS, cuts, text, out, self.env)
        facts = video.probe(TOOLING, out, self.env)
        self.assertEqual(video.verify(facts, REAL_CANVAS, 4.0), [])
        self.assertEqual((facts.width, facts.height, facts.fps, facts.sound), (1080, 1920, 30.0, False))
        first = hashlib.sha256(out.read_bytes()).hexdigest()
        video.render(TOOLING, REAL_CANVAS, cuts, text, out, self.env)
        self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), first)
        plain = self.root / "assets" / "plain.mp4"
        video.render(TOOLING, REAL_CANVAS, cuts, [], plain, self.env)
        self.assertNotEqual(hashlib.sha256(plain.read_bytes()).hexdigest(), first)  # the text was drawn
        self.assertEqual(fakes.tree_digest(self.root / "footage"), self.before)

    def test_cuts_of_any_shape_with_and_without_sound_join_into_one_asset(self):
        out = self.root / "assets" / "joined.mp4"
        cuts = [self.cut(self.camera, 0.5, 2.5), self.cut(self.screen, 0.0, 6.0, speed=2.0)]
        video.render(TOOLING, REAL_CANVAS, cuts, [video.Overlay(0, 2, "A spoken line.", caption=True)], out, self.env)
        facts = video.probe(TOOLING, out, self.env)
        self.assertEqual(video.verify(facts, REAL_CANVAS, 5.0), [])
        self.assertTrue(facts.sound)
        self.assertEqual(fakes.tree_digest(self.root / "footage"), self.before)

    def test_hdr_footage_as_a_phone_records_it_is_converted_so_the_asset_is_not_hdr(self):
        if not TOOLING.converts_hdr:
            self.skipTest("this ffmpeg has no zscale and tonemap filters, so it cannot convert HDR footage")
        clip = self.root / "footage" / "d02-s1-hdr.mov"
        tagged = "log-level=error:colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc"
        command = [str(TOOLING.ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi"]
        command += ["-i", "testsrc2=size=1080x1920:rate=30:duration=3", "-c:v", "libx265", "-preset", "ultrafast"]
        command += ["-pix_fmt", "yuv420p10le", "-x265-params", tagged, "-tag:v", "hvc1", str(clip)]
        made = subprocess.run(command, capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("this ffmpeg cannot make an HDR test clip (no libx265 encoder)")
        try:
            source = video.probe(TOOLING, clip, self.env)
            self.assertTrue(source.hdr)
            self.assertIn("HDR", source.describe())
            out = self.root / "assets" / "from-hdr.mp4"
            cut = video.Cut(clip, 0.0, 2.0, 1.0, source)
            video.render(TOOLING, REAL_CANVAS, [cut], [video.Overlay(0, 2, "Stand-in test footage.")], out, self.env)
            facts = video.probe(TOOLING, out, self.env)
            self.assertFalse(facts.hdr)
            self.assertEqual(video.verify(facts, REAL_CANVAS, 2.0), [])
        finally:
            clip.unlink()

    def test_a_landscape_file_measured_as_an_asset_is_not_9_16(self):
        problems = video.verify(video.probe(TOOLING, self.camera, self.env), REAL_CANVAS, 4.0)
        self.assertIn("it measures 1920x1080 (16:9), which is not 9:16", problems)


if __name__ == "__main__":
    unittest.main()
