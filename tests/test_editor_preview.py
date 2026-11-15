"""Tests for the dry-run edit preview."""

from dataclasses import replace
from pathlib import Path

from highlights.editor.preview import describe_edit
from highlights.editor.reel import EditOptions
from highlights.engine.moments import HighlightType, Moment, Segment
from highlights.recorder.base import ClipRequest

MOMENT = Moment(round_number=1, highlight_type=HighlightType.MULTI_KILL, player_steamid="P",
                core_tick=2651, start_tick=2400, end_tick=2700, description="Double kill (2 kills)")


def request(part, segment, camera=None):
    return ClipRequest(index=1, moment=MOMENT, demo_path=Path("cache.dem"), player_name="semi",
                       output_path=Path(f"001-{part:02d}.mp4"), segment=segment, part=part, parts=2,
                       camera_name=camera)


def test_preview_lists_cards_captions_and_replays():
    requests = [request(1, Segment(2400, 2700)),
                request(2, Segment(2604, 2677, pov_steamid="V", speed=0.6), camera="臻咘踔")]
    lines = describe_edit(requests, EditOptions("semi", maps={Path("cache.dem"): "de_cache"}))
    assert lines[0] == "[title]  semi  Cache"
    assert "DOUBLE KILL - semi  ·  Cache  ·  Round 1" in lines[1]
    assert "x0.6" in lines[2] and "REPLAY - 臻咘踔's view" in lines[2]
    assert lines[3] == "[outro]  GG"
    assert lines[4] == "No music; fade transitions"


def test_preview_reports_the_music_tempo():
    options = EditOptions("semi", cards=False, transition="cut", music=Path("song.mp3"))
    lines = describe_edit([request(1, Segment(2400, 2700))], options, tempo=lambda p: 128.0)
    assert lines[-1] == "Music: song.mp3, cuts on the beat (128 BPM); hard cuts"


def test_preview_without_captions_shows_bare_clips():
    options = replace(EditOptions("semi"), captions=False, cards=False)
    lines = describe_edit([request(1, Segment(2400, 2700))], options)
    assert lines[0].endswith("4.7s")


def test_outro_preview_counts_the_kills():
    options = EditOptions("semi", kills_shown=6)
    assert "[outro]  GG  6 kills" in describe_edit([request(1, Segment(2400, 2700))], options)


def test_preview_marks_slow_motion_ramps():
    ramped = Segment(2400, 2700, ramps=((2600, 2632), (2650, 2670)))
    line = describe_edit([request(1, ramped)], EditOptions("semi", cards=False))[0]
    assert "slow-mo x2" in line
