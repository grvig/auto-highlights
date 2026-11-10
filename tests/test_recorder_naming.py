"""Tests for clip naming, using real player names from the sample demos."""

from pathlib import Path

from highlights.engine.clip_plan import ClipPlan
from highlights.engine.moments import HighlightType, Moment
from highlights.recorder.naming import (
    build_clip_requests,
    clip_filename,
    sanitise_part,
)


def test_ordinary_name_is_kept():
    assert sanitise_part("semi") == "semi"
    assert sanitise_part("Ibrahim Moizoos") == "Ibrahim_Moizoos"


def test_symbol_only_name_falls_back():
    # A real name from the de_cache demo.
    assert sanitise_part("@!<$#") == "player"


def test_windows_illegal_characters_are_removed():
    result = sanitise_part('bad<>:"/\\|?*name')
    for char in '<>:"/\\|?*':
        assert char not in result


def test_non_latin_names_survive():
    # NTFS handles these; only unsafe punctuation should go.
    assert sanitise_part("最強雄性") == "最強雄性"


def test_reserved_windows_stems_fall_back():
    assert sanitise_part("CON") == "player"
    assert sanitise_part("com1") == "player"


def test_long_names_are_truncated():
    assert len(sanitise_part("x" * 100)) <= 24


def test_filename_sorts_in_plan_order():
    first = clip_filename(1, 5, "ace", "semi")
    tenth = clip_filename(10, 12, "clutch", "semi")
    assert first.startswith("001_")
    assert sorted([tenth, first]) == [first, tenth]


def test_filename_shape():
    assert clip_filename(3, 7, "multi_kill", "semi") == "003_r07_multi_kill_semi.mkv"


def make_moment(index: int) -> Moment:
    return Moment(
        round_number=index,
        highlight_type=HighlightType.KILL,
        player_steamid="P",
        core_tick=1000 * index,
        start_tick=1000 * index - 100,
        end_tick=1000 * index + 100,
        description="k",
    )


def test_segmented_moment_becomes_numbered_parts():
    from highlights.engine.moments import Segment

    moment = Moment(
        round_number=5,
        highlight_type=HighlightType.ACE,
        player_steamid="P",
        core_tick=9000,
        start_tick=1000,
        end_tick=9500,
        description="ace",
        segments=(Segment(1000, 1300), Segment(5000, 5300), Segment(9000, 9500)),
    )
    plan = ClipPlan(player_steamid="P", selected_types=(HighlightType.ACE,), moments=[moment])
    requests = build_clip_requests(plan, Path("m.dem"), "semi", Path("out"))

    assert [r.output_path.name for r in requests] == [
        "001-01_r05_ace_semi.mkv",
        "001-02_r05_ace_semi.mkv",
        "001-03_r05_ace_semi.mkv",
    ]
    assert [(r.start_tick, r.end_tick) for r in requests] == [
        (1000, 1300), (5000, 5300), (9000, 9500),
    ]
    assert requests[1].label == "#001.2/3"


def test_parts_sort_before_the_next_moment():
    names = [
        clip_filename(2, 6, "kill", "semi"),
        clip_filename(1, 5, "ace", "semi", part=2),
        clip_filename(1, 5, "ace", "semi", part=1),
    ]
    assert sorted(names) == [names[2], names[1], names[0]]


def test_build_requests_numbers_and_places_clips():
    plan = ClipPlan(
        player_steamid="P",
        selected_types=(HighlightType.KILL,),
        moments=[make_moment(1), make_moment(2)],
    )
    requests = build_clip_requests(plan, Path("m.dem"), "semi", Path("out"))
    assert [r.index for r in requests] == [1, 2]
    assert requests[0].output_path == Path("out/001_r01_kill_semi.mkv")
    assert requests[1].output_path.parent == Path("out")
