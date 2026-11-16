"""Tests for running a whole plan through a recorder."""

import logging
from pathlib import Path

import pytest

from highlights.engine.moments import HighlightType, Moment
from highlights.recorder.base import ClipRequest, RecordedClip
from highlights.recorder.session import record_requests


def make_request(index: int) -> ClipRequest:
    moment = Moment(
        round_number=index,
        highlight_type=HighlightType.KILL,
        player_steamid="P",
        core_tick=1000 * index,
        start_tick=1000 * index - 64,
        end_tick=1000 * index + 64,
        description="kill",
    )
    return ClipRequest(
        index=index,
        moment=moment,
        demo_path=Path("m.dem"),
        player_name="semi",
        output_path=Path(f"clips/{index:03d}.mkv"),
    )


class ScriptedRecorder:
    name = "scripted"

    def __init__(self, fail_indices=()) -> None:
        self.fail_indices = set(fail_indices)
        self.events: list[str] = []

    def open(self):
        self.events.append("open")

    def close(self):
        self.events.append("close")

    def record_clip(self, request):
        self.events.append(f"record:{request.index}")
        succeeded = request.index not in self.fail_indices
        return RecordedClip(
            request=request,
            output_path=request.output_path,
            succeeded=succeeded,
            error=None if succeeded else "boom",
        )


def test_records_every_request_in_order():
    recorder = ScriptedRecorder()
    results = record_requests(recorder, [make_request(i) for i in (1, 2, 3)])
    assert [c.index for c in results] == [1, 2, 3]
    assert recorder.events == ["open", "record:1", "record:2", "record:3", "close"]


def test_a_failed_clip_does_not_stop_the_run(caplog):
    recorder = ScriptedRecorder(fail_indices={2})
    with caplog.at_level(logging.WARNING):
        results = record_requests(recorder, [make_request(i) for i in (1, 2, 3)])
    assert len(results) == 3
    assert [c.succeeded for c in results] == [True, False, True]
    assert "1 of 3 clip(s) failed" in caplog.text


def test_backend_is_closed_even_when_recording_explodes():
    class Exploding(ScriptedRecorder):
        def record_clip(self, request):
            raise RuntimeError("unexpected")

    recorder = Exploding()
    with pytest.raises(RuntimeError):
        record_requests(recorder, [make_request(1)])
    assert "close" in recorder.events


def test_empty_plan_launches_nothing():
    recorder = ScriptedRecorder()
    assert record_requests(recorder, []) == []
    assert recorder.events == []


def on_disk(tmp_path, index):
    from dataclasses import replace

    request = replace(make_request(index), output_path=tmp_path / f"{index:03d}.mp4")
    request.output_path.write_bytes(b"video")
    return request


def test_clips_from_an_earlier_run_are_kept(tmp_path):
    recorder = ScriptedRecorder()
    requests = [on_disk(tmp_path, 1), make_request(2), on_disk(tmp_path, 3)]
    results = record_requests(recorder, requests, skip_existing=True)
    assert recorder.events == ["open", "record:2", "close"]
    assert [c.index for c in results] == [1, 2, 3]
    assert all(c.succeeded for c in results)


def test_nothing_left_to_record_never_opens_the_game(tmp_path):
    recorder = ScriptedRecorder()
    results = record_requests(recorder, [on_disk(tmp_path, 1)], skip_existing=True)
    assert recorder.events == [] and results[0].succeeded


def test_existing_clips_are_rerecorded_unless_asked(tmp_path):
    recorder = ScriptedRecorder()
    record_requests(recorder, [on_disk(tmp_path, 1)])
    assert recorder.events == ["open", "record:1", "close"]


def test_clips_are_filmed_demo_by_demo_but_returned_in_reel_order():
    from dataclasses import replace

    nuke1 = make_request(3)
    cache = replace(make_request(1), demo_path=Path("cache.dem"))
    nuke2 = make_request(2)
    recorder = ScriptedRecorder()
    results = record_requests(recorder, [nuke1, cache, nuke2])
    assert recorder.events == ["open", "record:2", "record:3", "record:1", "close"]
    assert [c.index for c in results] == [3, 1, 2]
