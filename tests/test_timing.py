from highlights.engine.timing import (
    CS2_TICKRATE,
    format_timestamp,
    seconds_to_ticks,
    tick_span_seconds,
    ticks_to_seconds,
)


def test_cs2_runs_at_64_ticks_per_second():
    assert CS2_TICKRATE == 64


def test_ticks_to_seconds():
    assert ticks_to_seconds(64) == 1.0
    assert ticks_to_seconds(32) == 0.5
    assert ticks_to_seconds(0) == 0.0


def test_seconds_to_ticks():
    assert seconds_to_ticks(1.0) == 64
    assert seconds_to_ticks(2.5) == 160


def test_seconds_to_ticks_rounds_to_nearest():
    assert seconds_to_ticks(0.001) == 0
    assert seconds_to_ticks(0.01) == 1


def test_conversion_round_trips():
    for seconds in (0.5, 1.0, 3.0, 12.25):
        assert ticks_to_seconds(seconds_to_ticks(seconds)) == seconds


def test_tick_span_seconds():
    assert tick_span_seconds(1000, 1064) == 1.0


def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(64) == "00:01"
    assert format_timestamp(64 * 75) == "01:15"


def test_format_timestamp_clamps_negative():
    assert format_timestamp(-64) == "00:00"
