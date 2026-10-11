"""Local video tooling (US-ME09): ffmpeg and ffprobe, which the package's launch-video build already uses.

Three jobs, all run by the launcher outside the sandbox: measure a file (probe), turn source ranges of the Founder's
footage into one 9:16 asset with on-screen text and captions drawn over it (render), and check a finished asset by
measurement (verify). Rendering is deterministic: the same footage, cuts, text, and tooling give the same file.

There is no generative step. Every input of a render is a footage file the caller resolved inside the footage place,
and the filter graph only trims, retimes, scales, pads or crops, joins, and draws text; the one thing it makes from
nothing is silence, for a cut whose source has no sound. Every output goes to the path the caller gives, never beside
an input. Tooling that is missing, or lacks what a render needs, is a finding the run reports, never an error.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

FFMPEG_ENV = "GR0WTHLAB_FFMPEG_BIN"
FFPROBE_ENV = "GR0WTHLAB_FFPROBE_BIN"
# Where Homebrew installs them; launchd's PATH names neither.
SEARCH = ("/opt/homebrew/bin", "/usr/local/bin")
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
FILTERS = ("scale", "pad", "crop", "fps", "trim", "setpts", "setsar", "format", "concat", "subtitles")
SOUND_FILTERS = ("aresample", "aformat", "apad", "atrim", "asetpts", "anullsrc")
HDR_FILTERS = ("zscale", "tonemap")
ENCODERS = ("libx264", "aac")
HDR_TRANSFERS = ("smpte2084", "arib-std-b67")
# The launch-video build's encoder settings, so a post reads like the package's own video.
VIDEO_CODEC = ("-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p")
SOUND_CODEC = ("-c:a", "aac", "-b:a", "192k", "-ar", "44100")
SOUND_RATE = 44100
# Nothing that varies from one run to the next goes into the file.
REPEATABLE = ("-map_metadata", "-1", "-map_chapters", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact")
TO_SDR = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
)
CONTAIN = "contain"
COVER = "cover"
FITS = (CONTAIN, COVER)
PROBE_TIMEOUT = 60
RENDER_TIMEOUT = 1800
# How far a measured length may sit from the length asked for: under two frames of a 30 fps asset.
DURATION_TOLERANCE = 0.06


class VideoError(Exception):
    """A file that could not be measured, or a render that did not finish."""


@dataclass(frozen=True)
class Tooling:
    """The ffmpeg and ffprobe a run found, and why it cannot use them when it cannot."""

    ffmpeg: Path | None
    ffprobe: Path | None
    version: str = ""
    problem: str = ""
    converts_hdr: bool = False

    @property
    def ok(self) -> bool:
        return not self.problem

    def describe(self) -> str:
        return f"{self.version} at `{self.ffmpeg}`" if self.ok else self.problem

    def as_json(self) -> dict[str, object]:
        return {
            "ffmpeg": str(self.ffmpeg) if self.ffmpeg else None,
            "ffprobe": str(self.ffprobe) if self.ffprobe else None,
            "version": self.version,
            "problem": self.problem,
            "converts_hdr": self.converts_hdr,
        }


@dataclass(frozen=True)
class Canvas:
    """The finished asset's shape and the look of its text: platform facts from config/platforms.json."""

    width: int
    height: int
    fps: int
    top: int
    bottom: int
    left: int
    right: int
    font: Path
    font_name: str
    text_size: int
    caption_size: int
    outline: int
    max_chars: int

    @property
    def ratio(self) -> Fraction:
        return Fraction(self.width, self.height)

    @property
    def shape(self) -> str:
        return f"{self.width}x{self.height} ({self.ratio.numerator}:{self.ratio.denominator})"

    def as_json(self) -> dict[str, object]:
        return dict(self.__dict__, font=str(self.font))


@dataclass(frozen=True)
class Facts:
    """What ffprobe measured of one file; width and height are as displayed, after any rotation."""

    duration: float
    width: int
    height: int
    fps: float
    codec: str
    pix_fmt: str
    sound: bool
    transfer: str = ""
    square_pixels: bool = True

    @property
    def hdr(self) -> bool:
        return self.transfer in HDR_TRANSFERS

    def shape(self) -> str:
        ratio = Fraction(self.width, self.height)
        return f"{self.width}x{self.height} ({ratio.numerator}:{ratio.denominator})"

    def describe(self) -> str:
        sound = "with sound" if self.sound else "no sound"
        return f"{self.duration:.2f}s, {self.width}x{self.height}, {self.fps:g} fps, {sound}" + (
            ", HDR" if self.hdr else ""
        )

    def as_json(self) -> dict[str, object]:
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, data: Mapping) -> Facts:
        return cls(
            float(data["duration"]),
            int(data["width"]),
            int(data["height"]),
            float(data["fps"]),
            str(data["codec"]),
            str(data["pix_fmt"]),
            data["sound"] is True,
            str(data.get("transfer") or ""),
            data.get("square_pixels", True) is True,
        )


@dataclass(frozen=True)
class Cut:
    """One piece of an asset's timeline: a source range of one footage file, already resolved inside the footage
    place by the caller."""

    path: Path
    start: float
    end: float
    speed: float
    fit: str
    mute: bool
    facts: Facts

    @property
    def length(self) -> float:
        return (self.end - self.start) / self.speed

    @property
    def sound(self) -> bool:
        """A cut carries its source's sound only at the speed it was recorded at."""
        return self.facts.sound and not self.mute and self.speed == 1


@dataclass(frozen=True)
class Overlay:
    """Text drawn over the asset for a stretch of its timeline: on-screen text, or a caption of a spoken line."""

    start: float
    end: float
    text: str
    caption: bool = False


def load_canvas(data: Mapping) -> Canvas:
    """config/platforms.json's video block; anything missing or out of range raises ValueError."""
    block = data.get("video")
    if not isinstance(block, dict):
        raise ValueError("config/platforms.json has no video block")
    safe, text = block.get("safe_zone"), block.get("text")
    if not isinstance(safe, dict) or not isinstance(text, dict):
        raise ValueError("config/platforms.json's video block needs safe_zone and text")

    def whole(source: Mapping, key: str, least: int = 1) -> int:
        value = source.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < least:
            raise ValueError(f"config/platforms.json video {key} must be a whole number from {least}")
        return value

    font = text.get("font_file")
    if not isinstance(font, str) or not os.path.isabs(font) or not isinstance(text.get("font_name"), str):
        raise ValueError("config/platforms.json video text needs font_file, an absolute path, and font_name")
    canvas = Canvas(
        whole(block, "width"),
        whole(block, "height"),
        whole(block, "fps"),
        whole(safe, "top", 0),
        whole(safe, "bottom", 0),
        whole(safe, "left", 0),
        whole(safe, "right", 0),
        Path(font),
        text["font_name"],
        whole(text, "size"),
        whole(text, "caption_size"),
        whole(text, "outline", 0),
        whole(text, "max_chars"),
    )
    if canvas.width % 2 or canvas.height % 2:
        raise ValueError("config/platforms.json video width and height must be even")
    if canvas.left + canvas.right >= canvas.width or canvas.top + canvas.bottom >= canvas.height:
        raise ValueError("config/platforms.json video safe_zone leaves no room for text")
    return canvas


# Finding the tooling.


def environment(env: Mapping[str, str]) -> dict[str, str]:
    """What ffmpeg runs with: the system's own path and nothing of the caller's but its home."""
    return {"PATH": SYSTEM_PATH, "HOME": env.get("HOME", "/"), "LANG": "en_US.UTF-8"}


def locate(name: str, override: str | None, env: Mapping[str, str]) -> tuple[Path | None, str]:
    if override:
        if os.path.isabs(override) and os.access(override, os.X_OK):
            return Path(override), ""
        return None, f"{name} is not an executable at `{override}`"
    path = os.pathsep.join([env.get("PATH", ""), *SEARCH])
    found = shutil.which(name, path=path)
    return (Path(found), "") if found else (None, f"{name} was not found on the PATH or in {' or '.join(SEARCH)}")


def listed(binary: Path, flag: str, env: Mapping[str, str]) -> set[str]:
    """The names an ffmpeg listing (-filters, -encoders) holds: the second word of each line that has one."""
    completed = subprocess.run(
        [str(binary), "-hide_banner", flag], capture_output=True, text=True, env=environment(env), timeout=PROBE_TIMEOUT
    )
    return {words[1] for words in (line.split() for line in completed.stdout.splitlines()) if len(words) > 2}


def find(env: Mapping[str, str], canvas: Canvas | None = None) -> Tooling:
    """The video tooling on this Mac, checked for everything an edit needs; never raises."""
    ffmpeg, problem = locate("ffmpeg", env.get(FFMPEG_ENV), env)
    ffprobe, probe_problem = locate("ffprobe", env.get(FFPROBE_ENV), env)
    if problem or probe_problem:
        return Tooling(ffmpeg, ffprobe, problem=problem or probe_problem)
    try:
        banner = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-version"],
            capture_output=True,
            text=True,
            env=environment(env),
            timeout=PROBE_TIMEOUT,
        )
        version = " ".join((banner.stdout.splitlines() or [""])[0].split()[:3])
        filters, encoders = listed(ffmpeg, "-filters", env), listed(ffmpeg, "-encoders", env)
    except (OSError, subprocess.SubprocessError) as error:
        return Tooling(ffmpeg, ffprobe, problem=f"ffmpeg could not be run ({error})")
    if banner.returncode != 0 or not version:
        return Tooling(ffmpeg, ffprobe, problem="ffmpeg did not report its version")
    missing = [f"the {name} filter" for name in FILTERS + SOUND_FILTERS if name not in filters]
    missing += [f"the {name} encoder" for name in ENCODERS if name not in encoders]
    if canvas is not None and not canvas.font.is_file():
        missing.append(f"the font `{canvas.font}`")
    if missing:
        return Tooling(ffmpeg, ffprobe, version, f"{version} lacks {', '.join(missing)}")
    return Tooling(ffmpeg, ffprobe, version, converts_hdr=all(name in filters for name in HDR_FILTERS))


# Measuring.


def rate(text: object) -> float:
    try:
        value = Fraction(str(text))
    except (ValueError, ZeroDivisionError):
        return 0.0
    return float(value)


def facts_of(data: Mapping) -> Facts:
    """The facts in ffprobe's JSON account of one file."""
    streams = data.get("streams") or []
    picture = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if picture is None:
        raise VideoError("it holds no video")
    try:
        width, height = int(picture["width"]), int(picture["height"])
        duration = float(picture.get("duration") or (data.get("format") or {})["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise VideoError(f"its size or length could not be measured ({error})") from error
    turned = 0
    for side in picture.get("side_data_list") or ():
        if "rotation" in side:
            turned = int(float(side["rotation"]))
    if abs(turned) % 180 == 90:
        width, height = height, width
    return Facts(
        duration,
        width,
        height,
        round(rate(picture.get("avg_frame_rate")) or rate(picture.get("r_frame_rate")), 3),
        str(picture.get("codec_name", "")),
        str(picture.get("pix_fmt", "")),
        any(stream.get("codec_type") == "audio" for stream in streams),
        str(picture.get("color_transfer") or ""),
        str(picture.get("sample_aspect_ratio") or "1:1") in ("1:1", "0:1"),
    )


def probe(tooling: Tooling, path: Path, env: Mapping[str, str]) -> Facts:
    """Measure one file with ffprobe, which only ever reads it."""
    command = [
        str(tooling.ffprobe),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, env=environment(env), timeout=PROBE_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        raise VideoError(f"ffprobe could not be run ({error})") from error
    if completed.returncode != 0:
        said = " ".join(completed.stderr.split())[-200:] or "no reason given"
        raise VideoError(f"ffprobe could not read it ({said})")
    try:
        return facts_of(json.loads(completed.stdout))
    except ValueError as error:
        raise VideoError(f"ffprobe's account of it could not be read ({error})") from error


def verify(facts: Facts, canvas: Canvas, duration: float) -> list[str]:
    """Why a finished asset, as measured, is not the asset asked for; empty when it is."""
    problems = []
    ratio = Fraction(facts.width, facts.height) if facts.height else None
    if ratio != canvas.ratio or not facts.square_pixels:
        was = facts.shape() + ("" if facts.square_pixels else ", with pixels that are not square")
        problems.append(f"it measures {was}, which is not {canvas.ratio.numerator}:{canvas.ratio.denominator}")
    elif (facts.width, facts.height) != (canvas.width, canvas.height):
        problems.append(f"it measures {facts.width}x{facts.height}, not the expected {canvas.width}x{canvas.height}")
    if abs(facts.fps - canvas.fps) > 0.01:
        problems.append(f"it measures {facts.fps:g} frames a second, not {canvas.fps}")
    if abs(facts.duration - duration) > DURATION_TOLERANCE:
        problems.append(f"it measures {facts.duration:.2f}s, not the {duration:.2f}s its edit record adds up to")
    if (facts.codec, facts.pix_fmt) != ("h264", "yuv420p"):
        problems.append(f"it is {facts.codec} {facts.pix_fmt}, not h264 yuv420p")
    if facts.hdr:
        problems.append("it is HDR, which the test platforms would show washed out")
    return problems


# Rendering.


def stamp(seconds: float) -> str:
    """A time as a subtitle file writes it: h:mm:ss.cc."""
    hundredths = round(seconds * 100)
    return f"{hundredths // 360000}:{hundredths // 6000 % 60:02d}:{hundredths // 100 % 60:02d}.{hundredths % 100:02d}"


def subtitles(canvas: Canvas, overlays: Sequence[Overlay]) -> str:
    """The text drawn over an asset, as a subtitle file: white with a black outline and no box, static, and inside
    the safe zone; on-screen text hangs from its top and a caption stands on its bottom."""
    head = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic,"
        " Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL,"
        " MarginR, MarginV, Encoding"
    )

    def style(name: str, size: int, alignment: int, edge: int) -> str:
        look = f"{canvas.font_name},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1"
        return f"Style: {name},{look},{canvas.outline},0,{alignment},{canvas.left},{canvas.right},{edge},1"

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {canvas.width}",
        f"PlayResY: {canvas.height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        head,
        style("Text", canvas.text_size, 8, canvas.top),
        style("Caption", canvas.caption_size, 2, canvas.bottom),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for overlay in overlays:
        name = "Caption" if overlay.caption else "Text"
        text = " ".join(overlay.text.split())
        lines.append(f"Dialogue: 0,{stamp(overlay.start)},{stamp(overlay.end)},{name},,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def graph(canvas: Canvas, cuts: Sequence[Cut], text: bool) -> tuple[str, bool]:
    """The filter graph that joins the cuts into one canvas-sized picture, and whether the asset has sound: it does
    when any cut carries its source's sound, and the cuts that carry none are silent."""
    sound = any(cut.sound for cut in cuts)
    size = f"{canvas.width}:{canvas.height}"
    chains, joined = [], ""
    for index, cut in enumerate(cuts):
        steps = [TO_SDR] if cut.facts.hdr else []
        steps += [
            f"setpts=(PTS-STARTPTS)/{cut.speed:.6f}",
            f"fps={canvas.fps}",
            f"trim=duration={cut.length:.6f}",
            "setpts=PTS-STARTPTS",
        ]
        if cut.fit == COVER:
            steps += [f"scale={size}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={size}"]
        else:
            steps += [
                f"scale={size}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos",
                f"pad={size}:(ow-iw)/2:(oh-ih)/2:color=black",
            ]
        steps += ["setsar=1", "format=yuv420p"]
        chains.append(f"[{index}:v:0]{','.join(steps)}[v{index}]")
        joined += f"[v{index}]"
        if sound:
            length = f"atrim=duration={cut.length:.6f},asetpts=PTS-STARTPTS"
            layout = f"aresample={SOUND_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo"
            if cut.sound:
                chains.append(f"[{index}:a:0]{layout},apad,{length}[a{index}]")
            else:
                chains.append(f"anullsrc=r={SOUND_RATE}:cl=stereo,{length}[a{index}]")
            joined += f"[a{index}]"
    outputs = "[vc][ac]" if sound else "[vc]"
    chains.append(f"{joined}concat=n={len(cuts)}:v=1:a={1 if sound else 0}{outputs}")
    chains.append("[vc]subtitles=overlay.ass:fontsdir=fonts[vout]" if text else "[vc]null[vout]")
    return ";".join(chains), sound


def command(tooling: Tooling, canvas: Canvas, cuts: Sequence[Cut], text: bool, output: Path) -> list[str]:
    """The one ffmpeg call that renders an asset: its only inputs are the cuts' footage files, read from each cut's
    start for its length, and its only output is the path given."""
    args = [str(tooling.ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    for cut in cuts:
        args += ["-ss", f"{cut.start:.6f}", "-t", f"{cut.end - cut.start:.6f}", "-i", str(cut.path)]
    filters, sound = graph(canvas, cuts, text)
    args += ["-filter_complex", filters, "-map", "[vout]"]
    args += [*VIDEO_CODEC, "-r", str(canvas.fps)]
    if sound:
        args += ["-map", "[ac]", *SOUND_CODEC, "-flags:a", "+bitexact"]
    total = sum(cut.length for cut in cuts)
    return args + [*REPEATABLE, "-movflags", "+faststart", "-t", f"{total:.6f}", "-f", "mp4", str(output)]


def render(
    tooling: Tooling,
    canvas: Canvas,
    cuts: Sequence[Cut],
    overlays: Sequence[Overlay],
    output: Path,
    env: Mapping[str, str],
) -> None:
    """Render the asset to output, whole or not at all: ffmpeg writes a hidden file beside it, which is renamed into
    place only once the render finished."""
    if not tooling.ok:
        raise VideoError(tooling.problem)
    if any(cut.facts.hdr for cut in cuts) and not tooling.converts_hdr:
        raise VideoError(f"{tooling.version} lacks the {' and '.join(HDR_FILTERS)} filters that convert HDR footage")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(f".{output.name}.partial")
    with tempfile.TemporaryDirectory(prefix="gr0wthlab-render-") as scratch:
        if overlays:
            Path(scratch, "overlay.ass").write_text(subtitles(canvas, overlays), encoding="utf-8")
            Path(scratch, "fonts").mkdir()
            os.symlink(str(canvas.font), str(Path(scratch, "fonts", canvas.font.name)))
        try:
            completed = subprocess.run(
                command(tooling, canvas, cuts, bool(overlays), partial),
                capture_output=True,
                text=True,
                env=environment(env),
                cwd=scratch,
                timeout=RENDER_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as error:
            partial.unlink(missing_ok=True)
            raise VideoError(f"ffmpeg could not be run ({error})") from error
    if completed.returncode != 0 or not partial.is_file():
        partial.unlink(missing_ok=True)
        said = " ".join(completed.stderr.split())[-300:] or "no reason given"
        raise VideoError(f"ffmpeg did not finish the render ({said})")
    os.replace(str(partial), str(output))
