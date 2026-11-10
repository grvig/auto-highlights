"""Tests for the Moment model and padding."""

import pytest

from highlights.engine.moments import HighlightType, Moment, Segment, pad_window


def make_moment(start=1000, end=1500, core=1200, **kwargs) -> Moment:
    base = dict(
        round_number=1,
        highlight_type=HighlightType.KILL,
        player_steamid="A",
        core_tick=core,
        start_tick=start,
        end_tick=end,
        description="test",
    )
    base.update(kwargs)
    return Moment(**base)


def test_highlight_type_values_are_stable():
    assert HighlightType.ACE == "ace"
    assert str(HighlightType.CLUTCH) == "clutch"


def test_moment_rejects_inverted_window():
    with pytest.raises(ValueError, match="after"):
        make_moment(start=2000, end=1000)


def test_duration_seconds():
    assert make_moment(start=1000, end=1000 + 64 * 5).duration_seconds == 5.0


def test_overlaps_is_symmetric_and_correct():
    a = make_moment(start=1000, end=2000)
    b = make_moment(start=1900, end=3000)
    c = make_moment(start=2001, end=4000)
    assert a.overlaps(b) and b.overlaps(a)
    assert not a.overlaps(c)
    assert not c.overlaps(a)


def test_pad_window_pads_and_is_symmetric():
    start, end = pad_window(
        core_tick=10_000,
        pre_roll_seconds=3.0,
        post_roll_seconds=2.0,
        first_tick=0,
        last_tick=100_000,
    )
    assert start == 10_000 - 3 * 64
    assert end == 10_000 + 2 * 64


def test_pad_window_clamps_to_demo_bounds():
    start, end = pad_window(
        core_tick=50,
        pre_roll_seconds=3.0,
        post_roll_seconds=2.0,
        first_tick=10,
        last_tick=60,
    )
    assert start == 10
    assert end == 60


def test_pad_window_spans_multi_event_range():
    start, end = pad_window(
        core_tick=5000,
        pre_roll_seconds=1.0,
        post_roll_seconds=1.0,
        first_tick=0,
        last_tick=100_000,
        span_start_tick=5000,
        span_end_tick=8000,
    )
    assert start == 5000 - 64
    assert end == 8000 + 64


def test_moment_without_segments_is_one_window():
    moment = make_moment(start=1000, end=1640)
    assert moment.windows == (Segment(1000, 1640),)
    assert moment.duration_seconds == 10.0


def test_duration_excludes_dead_time_between_segments():
    moment = make_moment(
        start=0,
        end=10_000,
        segments=(Segment(0, 320), Segment(9_680, 10_000)),
    )
    # two 5s windows, the ~140s gap between them is cut
    assert moment.duration_seconds == 10.0


def test_segments_must_stay_inside_the_outer_window():
    with pytest.raises(ValueError, match="outside"):
        make_moment(start=1000, end=2000, segments=(Segment(900, 1500),))


def test_segments_must_be_ordered_and_disjoint():
    with pytest.raises(ValueError, match="overlap"):
        make_moment(
            start=0,
            end=5000,
            segments=(Segment(1000, 2000), Segment(1500, 3000)),
        )


def test_segment_rejects_inverted_window():
    with pytest.raises(ValueError, match="after"):
        Segment(500, 100)


def segs(ticks, **kwargs):
    from highlights.engine.moments import build_segments

    base = dict(
        pre_roll_seconds=3.0,
        post_roll_seconds=2.0,
        first_tick=0,
        last_tick=1_000_000,
    )
    base.update(kwargs)
    return build_segments(ticks, **base)


def test_close_kills_merge_into_one_segment():
    # 2s apart: padded windows overlap, so one continuous shot
    result = segs([10_000, 10_128])
    assert result == (Segment(10_000 - 192, 10_128 + 128),)


def test_distant_kills_stay_separate():
    result = segs([10_000, 10_000 + 60 * 64])
    assert len(result) == 2
    assert result[0] == Segment(10_000 - 192, 10_000 + 128)


def test_gap_threshold_controls_merging():
    # windows end/start 3s apart: merged at a 4s gap, separate at a 2s gap
    ticks = [10_000, 10_000 + 8 * 64]
    assert len(segs(ticks, merge_gap_seconds=4.0)) == 1
    assert len(segs(ticks, merge_gap_seconds=2.0)) == 2


def test_segments_clamp_to_demo_bounds():
    result = segs([50], first_tick=10, last_tick=100)
    assert result == (Segment(10, 100),)


def test_unsorted_events_are_handled():
    assert segs([20_000, 10_000]) == segs([10_000, 20_000])


def test_no_events_is_rejected():
    with pytest.raises(ValueError, match="zero events"):
        segs([])
