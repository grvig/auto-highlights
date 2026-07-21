"""Tests for the OBS recorder backend, with both CS2 and OBS faked."""

from pathlib import Path

import pytest

from highlights.engine.moments import HighlightType, Moment
from highlights.recorder.base import ClipRequest, Recorder
from highlights.recorder.cs2_controller import Cs2Error
from highlights.recorder.obs_backend import ObsRecorder
from highlights.recorder.obs_client import ObsError


class FakeCs2:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_on_play = False

    def launch(self):
        self.calls.append("launch")

    def attach(self):
        self.calls.append("attach")

    def load_demo(self, path):
        self.calls.append(f"load:{Path(path).name}")

    def spectate(self, steamid):
        self.calls.append(f"spec:{steamid}")

    def seek_to(self, tick):
        self.calls.append(f"seek:{tick}")

    def play_window(self, start, end):
        self.calls.append(f"play:{start}-{end}")
        if self.fail_on_play:
            raise Cs2Error("playback died")
        return 5.0

    def quit(self):
        self.calls.append("quit")


class FakeObs:
    def __init__(self, written: Path | None = None) -> None:
        self.calls: list[str] = []
        self.written = written
        self.fail_on_start = False

    def connect(self):
        self.calls.append("connect")

    def set_record_directory(self, directory):
        self.calls.append("setdir")

    def start_recording(self):
        self.calls.append("start")
        if self.fail_on_start:
            raise ObsError("obs down")

    def stop_recording(self):
        self.calls.append("stop")
        return self.written

    def close(self):
        self.calls.append("close")


def make_request(tmp_path, index=1) -> ClipRequest:
    moment = Moment(
        round_number=5,
        highlight_type=HighlightType.ACE,
        player_steamid="76561199266315708",
        core_tick=10_000,
        start_tick=9_808,
        end_tick=10_128,
        description="ACE",
    )
    return ClipRequest(
        index=index,
        moment=moment,
        demo_path=Path("match.dem"),
        player_name="semi",
        output_path=tmp_path / "clips" / f"{index:03d}_ace.mkv",
    )


def test_satisfies_recorder_protocol(tmp_path):
    assert isinstance(ObsRecorder(FakeCs2(), FakeObs(), tmp_path), Recorder)


def test_open_connects_both_sides(tmp_path):
    cs2, obs = FakeCs2(), FakeObs()
    ObsRecorder(cs2, obs, tmp_path).open()
    assert cs2.calls == ["attach"]
    assert obs.calls == ["connect", "setdir"]
    assert tmp_path.exists()


def test_open_can_launch_cs2(tmp_path):
    cs2 = FakeCs2()
    ObsRecorder(cs2, FakeObs(), tmp_path, launch_cs2=True).open()
    assert cs2.calls[0] == "launch"


def test_record_clip_runs_the_expected_sequence(tmp_path):
    source = tmp_path / "obs_out.mkv"
    source.write_text("video")
    cs2, obs = FakeCs2(), FakeObs(written=source)
    recorder = ObsRecorder(cs2, obs, tmp_path)
    request = make_request(tmp_path)

    clip = recorder.record_clip(request)

    assert cs2.calls == [
        "load:match.dem",
        "spec:76561199266315708",
        "seek:9808",
        "play:9808-10128",
    ]
    assert obs.calls == ["start", "stop"]
    assert clip.succeeded
    assert clip.output_path.exists()
    assert not source.exists()  # moved, not copied


def test_demo_and_spectator_are_not_reset_between_clips(tmp_path):
    written = tmp_path / "o.mkv"
    cs2, obs = FakeCs2(), FakeObs(written=written)
    recorder = ObsRecorder(cs2, obs, tmp_path)
    for index in (1, 2):
        written.write_text("v")
        recorder.record_clip(make_request(tmp_path, index))
    # load and spectate happen once, seek/play happen per clip
    assert cs2.calls.count("load:match.dem") == 1
    assert cs2.calls.count("spec:76561199266315708") == 1
    assert cs2.calls.count("seek:9808") == 2


def test_playback_failure_still_stops_recording(tmp_path):
    cs2, obs = FakeCs2(), FakeObs()
    cs2.fail_on_play = True
    recorder = ObsRecorder(cs2, obs, tmp_path)

    clip = recorder.record_clip(make_request(tmp_path))

    assert "stop" in obs.calls  # OBS not left rolling
    assert not clip.succeeded
    assert "playback died" in clip.error


def test_obs_failure_returns_failed_clip_not_raises(tmp_path):
    obs = FakeObs()
    obs.fail_on_start = True
    recorder = ObsRecorder(FakeCs2(), obs, tmp_path)

    clip = recorder.record_clip(make_request(tmp_path))

    assert not clip.succeeded
    assert "obs down" in clip.error


def test_missing_obs_output_is_reported_but_not_fatal(tmp_path):
    recorder = ObsRecorder(FakeCs2(), FakeObs(written=None), tmp_path)
    clip = recorder.record_clip(make_request(tmp_path))
    assert clip.succeeded  # the run happened; the file just is not there
    assert not clip.output_path.exists()


def test_close_tolerates_both_sides_failing(tmp_path):
    class Exploding:
        def close(self):
            raise RuntimeError("nope")

        def quit(self):
            raise RuntimeError("nope")

    recorder = ObsRecorder(Exploding(), Exploding(), tmp_path)
    recorder.close()  # must not raise
