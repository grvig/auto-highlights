"""Tests for the window-capture fallback helpers."""

from pathlib import Path

import pytest

from highlights.recorder import window_capture as wc

LEADING = """
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 0.0333
[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 1.9
[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 1.9333
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 7.4333
"""

TRAILING_ONLY = """
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 7.5
"""


def test_capture_grabs_the_cs2_window_without_the_cursor():
    args = wc.capture_command(Path("raw.mkv"))
    source = args[args.index("-i") + 1]
    assert "window_exe=cs2\\.exe" in source and "capture_cursor=0" in source
    assert "dshow" not in args
    assert args[-1] == "raw.mkv"


def test_capture_delays_loopback_audio():
    args = wc.capture_command(Path("raw.mkv"), audio_device="virtual-audio-capturer")
    assert args[args.index("-itsoffset") + 1] == "0.55"
    assert "audio=virtual-audio-capturer" in args
    assert args[args.index("-map", args.index("[v]") + 1) + 1] == "1:a"


def test_playback_starts_where_the_leading_freeze_ends():
    assert wc.motion_start(LEADING, played_seconds=5.5) == pytest.approx(1.9333)


def test_without_a_leading_freeze_the_end_anchors_the_start():
    assert wc.motion_start(TRAILING_ONLY, played_seconds=5.5) == pytest.approx(2.0)


def test_a_late_first_freeze_is_not_mistaken_for_the_pause():
    log = "freeze_start: 3.0\nfreeze_end: 3.5\nfreeze_start: 8.0\n"
    assert wc.motion_start(log, played_seconds=5.0) == pytest.approx(3.0)


def test_no_freezes_means_start_of_file():
    assert wc.motion_start("", played_seconds=5.0) == 0.0


def test_probe_and_trim_commands():
    probe = wc.freeze_probe_command(Path("raw.mkv"))
    assert "freezedetect=n=-45dB:d=0.3" in probe
    trim = wc.trim_command(Path("raw.mkv"), Path("out.mp4"), 1.9333, 5.0)
    assert trim[trim.index("-ss") + 1] == "1.933"
    assert trim[trim.index("-t") + 1] == "5.000"
    assert trim[-1] == "out.mp4"
