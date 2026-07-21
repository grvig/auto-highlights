"""Tests for the Recorder interface and its data types."""

from pathlib import Path

from highlights.engine.moments import HighlightType, Moment
from highlights.recorder.base import ClipRequest, Recorder, RecordedClip


def make_moment(**kwargs) -> Moment:
    base = dict(
        round_number=5,
        highlight_type=HighlightType.ACE,
        player_steamid="76561199266315708",
        core_tick=10_000,
        start_tick=9_808,
        end_tick=10_128,
        description="ACE (5 kills)",
    )
    base.update(kwargs)
    return Moment(**base)


def make_request(index: int = 1) -> ClipRequest:
    return ClipRequest(
        index=index,
        moment=make_moment(),
        demo_path=Path("match.dem"),
        player_name="semi",
        output_path=Path("clips/001_ace.mp4"),
    )


def test_request_exposes_moment_fields():
    request = make_request()
    assert request.player_steamid == "76561199266315708"
    assert request.start_tick == 9_808
    assert request.end_tick == 10_128
    assert request.duration_seconds == (10_128 - 9_808) / 64


def test_request_str_is_loggable():
    text = str(make_request(7))
    assert "#007" in text
    assert "ace" in text
    assert "9808-10128" in text


def test_recorded_clip_success_and_failure_strings():
    request = make_request(2)
    ok = RecordedClip(request=request, output_path=request.output_path, succeeded=True)
    bad = RecordedClip(
        request=request,
        output_path=request.output_path,
        succeeded=False,
        error="OBS not connected",
    )
    assert "ok" in str(ok)
    assert ok.index == 2
    assert "FAILED" in str(bad)
    assert "OBS not connected" in str(bad)


class _StubRecorder:
    name = "stub"

    def open(self) -> None: ...

    def close(self) -> None: ...

    def record_clip(self, request):
        return RecordedClip(
            request=request, output_path=request.output_path, succeeded=True
        )


def test_backend_satisfies_recorder_protocol_structurally():
    assert isinstance(_StubRecorder(), Recorder)
