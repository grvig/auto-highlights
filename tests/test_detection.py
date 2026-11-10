"""Tests for the detection context and protocol."""

from highlights.engine.detection import DetectionContext, Detector
from highlights.engine.models import Kill, Round
from highlights.engine.moments import HighlightType, Moment


def make_round(number: int, start: int, end: int) -> Round:
    return Round(
        number=number,
        start_tick=start,
        freeze_end_tick=start + 100,
        end_tick=end,
        official_end_tick=end + 100,
        winner="ct",
        reason="elimination",
    )


def make_context(**kwargs) -> DetectionContext:
    base = dict(
        rounds=[make_round(1, 0, 5000)],
        kills=[],
        first_tick=0,
        last_tick=100_000,
        pre_roll_seconds=3.0,
        post_roll_seconds=2.0,
        tickrate=64,
        round_rosters={1: {"A": "ct", "B": "t"}},
    )
    base.update(kwargs)
    return DetectionContext(**base)


def test_round_by_number():
    ctx = make_context()
    assert ctx.round_by_number(1).number == 1
    assert ctx.round_by_number(99) is None


def test_side_of_reads_round_roster():
    ctx = make_context()
    assert ctx.side_of("A", 1) == "ct"
    assert ctx.side_of("B", 1) == "t"
    assert ctx.side_of("A", 2) is None
    assert ctx.side_of("unknown", 1) is None


def test_pad_uses_context_settings():
    ctx = make_context()
    start, end = ctx.pad(10_000)
    assert start == 10_000 - 3 * 64
    assert end == 10_000 + 2 * 64


def test_pad_clamps_to_bounds():
    ctx = make_context(first_tick=9_900, last_tick=10_050)
    start, end = ctx.pad(10_000)
    assert start == 9_900
    assert end == 10_050


class _StubDetector:
    highlight_type = HighlightType.KILL

    def detect(self, ctx, player_steamid):
        return []


def test_detector_protocol_is_satisfied_structurally():
    assert isinstance(_StubDetector(), Detector)


def test_context_segments_use_its_padding_and_bounds():
    from highlights.engine.moments import Segment

    ctx = make_context(first_tick=0, last_tick=100_000)
    assert ctx.segments([10_000]) == (Segment(10_000 - 192, 10_000 + 128),)
