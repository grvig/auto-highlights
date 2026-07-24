"""Tests for the high-level stitch orchestration."""

from pathlib import Path

import pytest

from highlights.engine.moments import HighlightType, Moment
from highlights.recorder.base import ClipRequest, RecordedClip
from highlights.stitcher.runner import RunResult, StitchError
from highlights.stitcher.stitch import stitch_clips, stitch_paths, usable_clip_paths


def make_clip(index, output_path, succeeded=True):
    moment = Moment(
        round_number=index,
        highlight_type=HighlightType.KILL,
        player_steamid="P",
        core_tick=1000 * index,
        start_tick=1000 * index - 64,
        end_tick=1000 * index + 64,
        description="k",
    )
    request = ClipRequest(
        index=index,
        moment=moment,
        demo_path=Path("m.dem"),
        player_name="semi",
        output_path=output_path,
    )
    return RecordedClip(
        request=request,
        output_path=output_path,
        succeeded=succeeded,
        error=None if succeeded else "boom",
    )


class FakeRunner:
    """Fakes ffmpeg: writes the output, optionally failing the first (copy) call."""

    def __init__(self, fail_stream_copy=False):
        self.fail_stream_copy = fail_stream_copy
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(args)
        is_copy = "copy" in args
        if is_copy and self.fail_stream_copy:
            return RunResult(returncode=1, stdout="", stderr="codec mismatch")
        Path(args[-1]).write_text("reel")
        return RunResult(returncode=0, stdout="", stderr="")


@pytest.fixture(autouse=True)
def _ffmpeg_on_path(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "ffmpeg")


def existing_clip(tmp_path, index):
    path = tmp_path / f"{index:03d}.mkv"
    path.write_text("clip")
    return make_clip(index, path)


def test_usable_paths_skips_failed_and_missing(tmp_path):
    good = existing_clip(tmp_path, 1)
    failed = make_clip(2, tmp_path / "002.mkv", succeeded=False)
    missing = make_clip(3, tmp_path / "gone.mkv")  # file never written
    paths = usable_clip_paths([good, failed, missing])
    assert paths == [good.output_path]


def test_stitch_clips_stream_copy_happy_path(tmp_path):
    clips = [existing_clip(tmp_path, 1), existing_clip(tmp_path, 2)]
    runner = FakeRunner()
    out = stitch_clips(clips, tmp_path / "reel.mkv", runner=runner)
    assert out.exists()
    assert len(runner.calls) == 1  # no re-encode needed


def test_stitch_falls_back_to_reencode(tmp_path):
    clips = [existing_clip(tmp_path, 1)]
    runner = FakeRunner(fail_stream_copy=True)
    out = stitch_clips(clips, tmp_path / "reel.mkv", runner=runner)
    assert out.exists()
    assert len(runner.calls) == 2
    assert "copy" in runner.calls[0]
    assert "-c:v" in runner.calls[1]


def test_stitch_reencode_can_be_disabled(tmp_path):
    clips = [existing_clip(tmp_path, 1)]
    runner = FakeRunner(fail_stream_copy=True)
    with pytest.raises(StitchError):
        stitch_clips(
            clips, tmp_path / "reel.mkv", runner=runner, allow_reencode=False
        )
    assert len(runner.calls) == 1


def test_stitch_with_no_usable_clips_raises(tmp_path):
    failed = make_clip(1, tmp_path / "001.mkv", succeeded=False)
    with pytest.raises(StitchError, match="No usable clips"):
        stitch_clips([failed], tmp_path / "reel.mkv", runner=FakeRunner())


def test_stitch_paths_writes_concat_list(tmp_path):
    clips = [existing_clip(tmp_path, 1).output_path]
    stitch_paths(clips, tmp_path / "reel.mkv", runner=FakeRunner())
    assert (tmp_path / "concat_list.txt").exists()


def test_stitch_paths_empty_raises(tmp_path):
    with pytest.raises(StitchError, match="No clips"):
        stitch_paths([], tmp_path / "reel.mkv", runner=FakeRunner())
