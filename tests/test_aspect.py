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
    assert args[args.index("-af") + 1].startswith("loudnorm=I=-14")
    plain = convert_args(Path("in.mp4"), Path("out.mp4"), PROFILES["stretched"], normalise=False)
    assert "-af" not in plain and plain[plain.index("-c:a") + 1] == "copy"
