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
