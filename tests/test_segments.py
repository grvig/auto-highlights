"""Tests for slow-motion ramps inside a segment."""


def test_ramps_lengthen_the_footage():
    from highlights.engine.moments import Segment

    plain = Segment(0, 640)
    ramped = Segment(0, 640, ramps=((300, 332),), ramp_speed=0.5)
    assert plain.duration_seconds == 10.0
    assert ramped.duration_seconds == 10.5  # 0.5s slowed to 1.0s


def test_ramps_must_sit_inside_the_segment_in_order():
    import pytest

    from highlights.engine.moments import Segment

    with pytest.raises(ValueError, match="Ramp"):
        Segment(0, 640, ramps=((600, 700),))
    with pytest.raises(ValueError, match="Ramp"):
        Segment(0, 640, ramps=((300, 350), (320, 360)))
    with pytest.raises(ValueError, match="Ramp speed"):
        Segment(0, 640, ramp_speed=0)


def test_screen_time_of_a_tick_counts_slow_motion():
    from highlights.engine.moments import Segment

    plain = Segment(0, 640)
    assert plain.screen_seconds(320) == 5.0
    ramped = Segment(0, 640, ramps=((256, 288),), ramp_speed=0.5)
    assert ramped.screen_seconds(256) == 4.0   # before the ramp: real time
    assert ramped.screen_seconds(272) == 4.5   # halfway through: stretched
    assert ramped.screen_seconds(320) == 5.5   # after it: shifted by the stretch
    assert ramped.screen_seconds(640) == ramped.duration_seconds


def test_screen_time_follows_the_whole_segment_speed():
    from highlights.engine.moments import Segment

    assert Segment(0, 640, speed=0.5).screen_seconds(320) == 10.0
    assert Segment(100, 740).screen_seconds(50) == 0.0  # clamped to the start
