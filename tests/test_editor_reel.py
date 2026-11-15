"""Tests for assembling the edited reel, with ffmpeg and ffprobe faked."""

from pathlib import Path

import pytest

from highlights.editor import captions, cards
from highlights.editor.probe import MediaInfo
from highlights.editor.reel import EditOptions, ReelBuilder
from highlights.engine.moments import HighlightType, Moment, Segment
from highlights.recorder.base import ClipRequest, RecordedClip


@pytest.fixture(autouse=True)
def fake_font(monkeypatch, tmp_path):
    font = tmp_path / "font.ttf"
    font.write_bytes(b"f")
    monkeypatch.setattr(captions, "find_font", lambda text: font)
    monkeypatch.setattr(cards, "find_font", lambda text: font)


def recorded(tmp_path, index, part=1, ok=True):
    moment = Moment(round_number=index, highlight_type=HighlightType.ACE, player_steamid="P",
                    core_tick=100, start_tick=0, end_tick=640, description="ACE (5 kills)")
    path = tmp_path / f"{index:03d}-{part:02d}.mp4"
    path.write_bytes(b"video")
    request = ClipRequest(index=index, moment=moment, demo_path=Path("nuke.dem"), player_name="semi",
                          output_path=path, segment=Segment(0, 320), part=part, parts=2)
    return RecordedClip(request, path, succeeded=ok, error=None if ok else "x")


def builder(tmp_path, runs, **options):
    opts = EditOptions(player_name="semi", maps={Path("nuke.dem"): "de_nuke"}, **options)
    return ReelBuilder(opts, tmp_path / "work", runner=runs.append,
                       prober=lambda p: MediaInfo(5.3, 1440, 1080, 60.0, True),
                       beat_finder=lambda p: [i * 0.5 for i in range(200)])


def test_full_edit_renders_parts_cards_and_join(tmp_path):
    runs = []
    clips = [recorded(tmp_path, 1, 1), recorded(tmp_path, 1, 2), recorded(tmp_path, 2, 1)]
    builder(tmp_path, runs).build(clips, tmp_path / "reel.mp4")
    outputs = [Path(r[-1]).name for r in runs]
    assert outputs == ["part_001.mp4", "part_002.mp4", "part_003.mp4", "title.mp4", "outro.mp4", "reel.mp4"]
    join = runs[-1]
    assert join.count("-i") == 5
    assert Path(join[join.index("-i") + 1]).name == "title.mp4"


def test_only_the_first_window_of_a_moment_is_captioned(tmp_path):
    runs = []
    clips = [recorded(tmp_path, 1, 1), recorded(tmp_path, 1, 2)]
    builder(tmp_path, runs, cards=False).build(clips, tmp_path / "reel.mp4")
    assert "-vf" in runs[0] and "drawtext" in runs[0][runs[0].index("-vf") + 1]
    assert "-vf" not in runs[1]


def test_failed_clips_are_left_out(tmp_path):
    runs = []
    clips = [recorded(tmp_path, 1), recorded(tmp_path, 2, ok=False)]
    builder(tmp_path, runs, cards=False).build(clips, tmp_path / "reel.mp4")
    assert [Path(r[-1]).name for r in runs] == ["part_001.mp4", "reel.mp4"]


def test_music_trims_cuts_onto_beats_and_mixes_last(tmp_path):
    song = tmp_path / "song.mp3"
    song.write_bytes(b"id3")
    runs = []
    clips = [recorded(tmp_path, 1), recorded(tmp_path, 2)]
    builder(tmp_path, runs, music=song).build(clips, tmp_path / "reel.mp4")
    first_part = runs[0]
    assert float(first_part[first_part.index("-t") + 1]) < 5.3
    assert "-stream_loop" in runs[-1]
    assert Path(runs[-2][-1]).name == "joined.mp4"


def test_nothing_to_edit_raises(tmp_path):
    with pytest.raises(ValueError, match="No recorded clips"):
        builder(tmp_path, []).build([recorded(tmp_path, 1, ok=False)], tmp_path / "reel.mp4")


def test_victim_cams_are_captioned_as_replays(tmp_path):
    from dataclasses import replace

    runs = []
    clip = recorded(tmp_path, 1, 2)
    victim = replace(clip.request, segment=Segment(0, 320, pov_steamid="V"), camera_name="臻咘踔")
    builder(tmp_path, runs, cards=False).build([replace(clip, request=victim)], tmp_path / "reel.mp4")
    detail = (tmp_path / "work" / "captions_001" / "caption_detail.txt").read_text(encoding="utf-8")
    assert detail == "臻咘踔's view"


def test_hard_cuts_join_without_crossfades(tmp_path):
    runs = []
    clips = [recorded(tmp_path, 1), recorded(tmp_path, 2)]
    builder(tmp_path, runs, transition="cut").build(clips, tmp_path / "reel.mp4")
    graph = runs[-1][runs[-1].index("-filter_complex") + 1]
    assert "xfade" not in graph and "concat=n=2" in graph


def test_outro_card_carries_the_kill_count(tmp_path):
    runs = []
    builder(tmp_path, runs, kills_shown=6).build([recorded(tmp_path, 1)], tmp_path / "reel.mp4")
    texts = sorted(p.read_text(encoding="utf-8") for p in (tmp_path / "work").glob("card_outro_*.txt"))
    assert "6 KILLS SHOWN" in texts


def test_headshots_punch_in_and_kills_flash_at_their_screen_time(tmp_path):
    from dataclasses import replace

    runs = []
    clip = recorded(tmp_path, 1, 2)
    marked = replace(clip.request.segment, kill_ticks=(64, 192), headshot_ticks=(192,))
    clip = replace(clip, request=replace(clip.request, segment=marked))
    builder(tmp_path, runs, cards=False, punch_ins=True, flashes=True).build([clip], tmp_path / "r.mp4")
    vf = runs[0][runs[0].index("-vf") + 1]
    assert "zoompan" in vf and "(it-3.000)" in vf  # headshot at tick 192 = 3s
    assert "eq=brightness" in vf and "(t-1.000)" in vf and "(t-3.000)" in vf


def test_effects_are_off_unless_asked(tmp_path):
    from dataclasses import replace

    runs = []
    clip = recorded(tmp_path, 1, 2)
    marked = replace(clip.request.segment, kill_ticks=(64,), headshot_ticks=(64,))
    clip = replace(clip, request=replace(clip.request, segment=marked))
    builder(tmp_path, runs, cards=False).build([clip], tmp_path / "r.mp4")
    assert "-vf" not in runs[0]
