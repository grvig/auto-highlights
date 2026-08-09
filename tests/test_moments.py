"""Tests for the Moment model and padding."""

import pytest

from highlights.engine.moments import HighlightType, Moment, pad_window


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


def test_pad_window_caps_a_long_span():
    # A span from tick 0 to 64000 is 1000s; cap to 25s before the end.
    start, end = pad_window(
        core_tick=64_000,
        pre_roll_seconds=0.0,
        post_roll_seconds=0.0,
        first_tick=0,
        last_tick=1_000_000,
        span_start_tick=0,
        span_end_tick=64_000,
        max_span_seconds=25.0,
    )
    assert start == 64_000 - 25 * 64
    assert end == 64_000


def test_pad_window_cap_does_not_extend_a_short_span():
    # A span already under the cap is left alone.
    start, end = pad_window(
        core_tick=10_000,
        pre_roll_seconds=0.0,
        post_roll_seconds=0.0,
        first_tick=0,
        last_tick=1_000_000,
        span_start_tick=9_680,  # 5s span
        span_end_tick=10_000,
        max_span_seconds=25.0,
    )
    assert start == 9_680
