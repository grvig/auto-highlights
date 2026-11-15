"""Tests for the reel thumbnail."""

from dataclasses import replace
from pathlib import Path

import pytest

from highlights.editor import thumbnail
from highlights.editor.thumbnail import best_frame, thumbnail_command
from highlights.engine.moments import HighlightType, Moment, Segment
from highlights.recorder.base import ClipRequest, RecordedClip


def clip(tmp_path, index, score, kills=(), part=1):
    moment = Moment(round_number=index, highlight_type=HighlightType.ACE, player_steamid="P",
                    core_tick=100, start_tick=0, end_tick=640, description="ACE (5 kills)",
                    score=score)
    path = tmp_path / f"{index}-{part}.mp4"
    path.write_bytes(b"v")
    request = ClipRequest(index=index, moment=moment, demo_path=Path("d.dem"), player_name="semi",
                          output_path=path, segment=Segment(0, 320, kill_ticks=kills), part=part)
    return RecordedClip(request, path, True)


@pytest.fixture(autouse=True)
def fake_font(monkeypatch, tmp_path):
    font = tmp_path / "font.ttf"
    font.write_bytes(b"f")
    monkeypatch.setattr(thumbnail, "find_font", lambda text: font)


def test_frame_comes_from_the_best_highlight_at_its_first_kill(tmp_path):
    clips = [clip(tmp_path, 1, 5.0, (64,)), clip(tmp_path, 2, 26.8, (192, 256))]
    chosen, seconds = best_frame(clips)
    assert chosen.request.index == 2 and seconds == 3.0


def test_without_kills_the_middle_of_the_clip_is_used(tmp_path):
    chosen, seconds = best_frame([clip(tmp_path, 1, 5.0)])
    assert seconds == 2.5


def test_no_usable_clips_means_no_thumbnail(tmp_path):
    failed = replace(clip(tmp_path, 1, 5.0), succeeded=False)
    assert best_frame([failed]) is None


def test_thumbnail_is_one_stretched_lettered_frame(tmp_path):
    args = thumbnail_command(clip(tmp_path, 1, 5.0), 3.0, "semi", tmp_path / "t.png", tmp_path / "w")
    vf = args[args.index("-vf") + 1]
    assert vf.startswith("scale=1280:720") and vf.count("drawtext") == 2
    assert args[args.index("-frames:v") + 1] == "1"
    assert (tmp_path / "w" / "thumb_headline.txt").read_text(encoding="utf-8") == "ACE"
