"""Tests for the window-capture backend, with game, capture and ffmpeg faked."""

import pytest

from highlights.recorder.window_backend import WindowRecorder
from tests.test_hlae_backend import FakeCs2, make_request


class FakeCapture:
    def __init__(self, log):
        self.log = log

    def communicate(self, data, timeout):
        self.log.append(("stop", data))


def make_recorder(tmp_path, cs2, runs, freeze_log):
    events = []

    def popen(args, stdin):
        events.append(("capture", args[-1]))
        return FakeCapture(events)

    rec = WindowRecorder(
        cs2, tmp_path, runner=runs.append, sleeper=lambda s: None,
        popen=popen, probe=lambda args: freeze_log,
    )
    return rec, events


def test_captures_while_stepping_then_cuts_after_the_pause(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    rec, events = make_recorder(tmp_path, cs2, runs, "freeze_start: 0.03\nfreeze_end: 1.9\n")
    assert rec.record_clip(make_request(tmp_path)).succeeded
    assert events[0][0] == "capture" and events[0][1].endswith("raw.mkv")
    assert events[-1] == ("stop", b"q")
    trim = runs[0]
    # playback began at 1.9s; the 32-tick lead-in adds 0.5s more
    assert float(trim[trim.index("-ss") + 1]) == pytest.approx(2.4)
    assert trim[trim.index("-t") + 1] == "5.000"


def test_capture_is_stopped_even_if_playback_fails(tmp_path):
    cs2, runs = FakeCs2(), []

    def broken(ticks):
        raise RuntimeError("console died")

    cs2.play_ticks = broken
    rec, events = make_recorder(tmp_path, cs2, runs, "")
    with pytest.raises(RuntimeError):
        rec.record_clip(make_request(tmp_path))
    assert events[-1] == ("stop", b"q")


def test_spectates_before_capturing(tmp_path):
    cs2, runs = FakeCs2(landings=[26527]), []
    rec, _ = make_recorder(tmp_path, cs2, runs, "")
    rec.record_clip(make_request(tmp_path, pov="V", camera="victim"))
    assert ("spectate", "victim") in cs2.log


def test_slowed_victim_cams_stay_slow_in_window_capture(tmp_path):
    from dataclasses import replace

    from highlights.engine.moments import Segment

    cs2, runs = FakeCs2(landings=[26527]), []
    rec, _ = make_recorder(tmp_path, cs2, runs, "")
    request = make_request(tmp_path, pov="V", camera="victim")
    request = replace(request, segment=Segment(26207, 26527, pov_steamid="V", speed=0.5))
    rec.record_clip(request)
    assert "setpts=PTS/0.5" in runs[0][runs[0].index("-filter_complex") + 1]
