"""Tests for reading media info."""

import json
import shutil
from pathlib import Path

import pytest

from highlights.editor.probe import ProbeError, ffprobe_for, probe

SAMPLE = {
    "format": {"duration": "5.016000"},
    "streams": [
        {"codec_type": "video", "width": 1440, "height": 1080, "avg_frame_rate": "60/1"},
        {"codec_type": "audio"},
    ],
}


def test_reads_duration_size_rate_and_audio():
    info = probe(Path("clip.mp4"), runner=lambda args: json.dumps(SAMPLE))
    assert info.duration == pytest.approx(5.016)
    assert (info.width, info.height, info.fps, info.has_audio) == (1440, 1080, 60.0, True)


def test_silent_clip_has_no_audio():
    silent = {"format": {"duration": "2"}, "streams": [SAMPLE["streams"][0]]}
    assert not probe(Path("c.mp4"), runner=lambda a: json.dumps(silent)).has_audio


def test_garbage_output_raises():
    with pytest.raises(ProbeError):
        probe(Path("c.mp4"), runner=lambda a: "not json")


def test_ffprobe_is_found_next_to_ffmpeg():
    assert ffprobe_for("ffmpeg") == "ffprobe"
    assert ffprobe_for("C:/tools/bin/ffmpeg.exe").replace("\\", "/") == "C:/tools/bin/ffprobe.exe"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_probes_a_real_file(tmp_path):
    import subprocess

    clip = tmp_path / "tone.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
         "-f", "lavfi", "-i", "sine=d=1", "-shortest", str(clip)],
        check=True,
    )
    info = probe(clip)
    assert info.width == 320 and info.has_audio
    assert info.duration == pytest.approx(1.0, abs=0.1)
