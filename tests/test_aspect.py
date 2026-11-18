"""Tests for export shapes, including a real ffmpeg run when ffmpeg is present."""

import json
import shutil
import subprocess

import pytest

from highlights.stitcher.aspect import PROFILES, AspectMode, convert, video_filter

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_stretched_scales_to_the_full_frame_without_bars():
    chain = video_filter(PROFILES["stretched"])
    assert chain.startswith("scale=1920:1080")
    assert "pad" not in chain and "crop" not in chain
    assert chain.endswith("setsar=1")


def test_pillarbox_pads_and_vertical_crops():
    assert "pad=1920:1080" in video_filter(PROFILES["pillarbox"])
    assert "crop=1080:1920" in video_filter(PROFILES["vertical"])


def test_every_mode_has_a_profile():
    assert {p.mode for p in PROFILES.values()} == set(AspectMode)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,sample_aspect_ratio", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return stream["width"], stream["height"], stream.get("sample_aspect_ratio", "1:1")


@pytest.fixture(scope="module")
def source_4x3(tmp_path_factory):
    """One second of 1280x960 test pattern: the stretched-res capture shape."""
    path = tmp_path_factory.mktemp("aspect") / "source_4x3.mkv"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x960:rate=30:duration=1",
         "-c:v", "libx264", "-preset", "ultrafast", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
@pytest.mark.parametrize(
    "name, expected",
    [
        ("4:3", (1440, 1080)),
        ("stretched", (1920, 1080)),
        ("pillarbox", (1920, 1080)),
        ("16:9", (1920, 1080)),
        ("vertical", (1080, 1920)),
    ],
)
def test_real_ffmpeg_export_produces_the_right_shape(source_4x3, tmp_path, name, expected):
    out = convert(source_4x3, tmp_path / f"{name.replace(':', 'x')}.mkv", PROFILES[name])
    width, height, sar = probe(out)
    assert (width, height) == expected
    assert sar in ("1:1", "N/A")  # square pixels: the stretch is baked in


def test_export_levels_loudness_for_upload():
    from pathlib import Path

    from highlights.stitcher.aspect import PROFILES, convert_args

    args = convert_args(Path("in.mp4"), Path("out.mp4"), PROFILES["stretched"])
    assert args[args.index("-af") + 1].startswith("loudnorm=I=-16")
    assert args[args.index("-af") + 1].endswith("alimiter=limit=0.708:level=false,aresample=48000")
    plain = convert_args(Path("in.mp4"), Path("out.mp4"), PROFILES["stretched"], normalise=False)
    assert "-af" not in plain and plain[plain.index("-c:a") + 1] == "copy"


SAMPLE_MEASUREMENT = """[Parsed_loudnorm_0 @ 0x1]
{
	"input_i" : "-33.52",
	"input_tp" : "-17.60",
	"input_lra" : "9.10",
	"input_thresh" : "-44.01",
	"output_i" : "-14.20",
	"target_offset" : "0.20"
}"""


def test_measured_loudness_becomes_one_steady_gain():
    from highlights.stitcher.aspect import linear_loudness, parse_measurement

    measured = parse_measurement(SAMPLE_MEASUREMENT)
    assert measured["input_i"] == "-33.52"
    chain = linear_loudness(measured)
    assert ":linear=true:" in chain and "measured_I=-33.52" in chain and "offset=0.20" in chain


def test_without_a_measurement_the_single_pass_filter_is_used():
    from highlights.stitcher.aspect import LOUDNESS, linear_loudness, parse_measurement

    assert parse_measurement("no json here") is None
    assert linear_loudness(None) == LOUDNESS


EBUR128_SUMMARY = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -16.2 LUFS
    Threshold: -26.4 LUFS

  True peak:
    Peak:       -0.7 dBFS"""


def test_the_true_peak_is_read_from_the_summary():
    from highlights.stitcher.aspect import parse_true_peak

    assert parse_true_peak(EBUR128_SUMMARY) == -0.7
    assert parse_true_peak("    Peak:       -inf dBFS") == float("-inf")
    assert parse_true_peak("no summary") is None


def test_trimming_copies_the_video_and_turns_only_the_audio_down():
    from pathlib import Path

    from highlights.stitcher.aspect import trim_args

    args = trim_args(Path("reel.mp4"), Path("reel.trim.mp4"), -0.8)
    assert args[args.index("-c:v") + 1] == "copy"
    assert args[args.index("-af") + 1] == "volume=-0.80dB"


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_a_reel_whose_peak_is_too_hot_is_turned_down(tmp_path):
    from highlights.stitcher.aspect import (
        MAX_TRUE_PEAK, keep_peaks_down, parse_true_peak, true_peak_args)

    hot = tmp_path / "hot.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
         "-f", "lavfi", "-i", "aevalsrc=0.97*sin(1000*2*PI*t):s=48000:d=2",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k", str(hot)],
        capture_output=True, check=True,
    )
    def peak(path):
        return parse_true_peak(subprocess.run(true_peak_args(path), capture_output=True, text=True).stderr)

    assert peak(hot) > MAX_TRUE_PEAK
    assert keep_peaks_down(hot) is not None
    assert peak(hot) <= MAX_TRUE_PEAK
    assert probe(hot)[:2] == (320, 240) and not list(tmp_path.glob("*.trim.*"))
    assert keep_peaks_down(hot) is None  # already fine: left alone
