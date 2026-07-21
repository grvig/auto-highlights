"""Tests for the dry-run recorder backend."""

import logging
from pathlib import Path

from highlights.engine.moments import HighlightType, Moment
from highlights.recorder.base import ClipRequest, Recorder
from highlights.recorder.dry_run import DryRunRecorder


def make_request(index: int = 1, tick: int = 10_000) -> ClipRequest:
    moment = Moment(
        round_number=5,
        highlight_type=HighlightType.ACE,
        player_steamid="P",
        core_tick=tick,
        start_tick=tick - 192,
        end_tick=tick + 128,
        description="ACE (5 kills)",
    )
    return ClipRequest(
        index=index,
        moment=moment,
        demo_path=Path("match.dem"),
        player_name="semi",
        output_path=Path(f"clips/{index:03d}_ace.mkv"),
    )


def test_satisfies_recorder_protocol():
    assert isinstance(DryRunRecorder(), Recorder)


def test_records_are_reported_as_succeeded():
    recorder = DryRunRecorder()
    clip = recorder.record_clip(make_request())
    assert clip.succeeded
    assert clip.error is None


def test_writes_no_files(tmp_path):
    recorder = DryRunRecorder()
    request = ClipRequest(
        index=1,
        moment=make_request().moment,
        demo_path=Path("m.dem"),
        player_name="semi",
        output_path=tmp_path / "001.mkv",
    )
    recorder.record_clip(request)
    assert not (tmp_path / "001.mkv").exists()
    assert list(tmp_path.iterdir()) == []


def test_tracks_everything_it_was_asked_to_record():
    recorder = DryRunRecorder()
    recorder.record_clip(make_request(1))
    recorder.record_clip(make_request(2))
    assert [c.index for c in recorder.recorded] == [1, 2]


def test_logs_each_clip_details(caplog):
    recorder = DryRunRecorder()
    with caplog.at_level(logging.INFO):
        recorder.open()
        recorder.record_clip(make_request(3))
        recorder.close()
    text = caplog.text
    assert "would record #003" in text
    assert "9808-10128" in text  # the tick window
    assert "ACE (5 kills)" in text
    assert "1 clip(s)" in text


def test_open_and_close_are_safe_without_clips(caplog):
    recorder = DryRunRecorder()
    with caplog.at_level(logging.INFO):
        recorder.open()
        recorder.close()
    assert "0 clip(s)" in caplog.text
