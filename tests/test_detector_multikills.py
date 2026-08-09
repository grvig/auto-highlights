"""Tests for the multi-kill and ace detectors."""

from highlights.engine.detectors.multikills import (
    AceDetector,
    MultiKillDetector,
    kills_by_round,
)
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill, make_round


def round_with_kills(player: str, ticks: list[int], round_number: int = 1):
    return [make_kill(t, player, f"v{i}", round_number=round_number) for i, t in enumerate(ticks)]


def test_kills_by_round_groups_and_orders():
    kills = round_with_kills("A", [3000, 1000, 2000])
    grouped = kills_by_round(kills, "A")
    assert [k.tick for k in grouped[1]] == [1000, 2000, 3000]


def test_three_kills_is_a_multikill():
    kills = round_with_kills("A", [1000, 1200, 1400])
    moments = MultiKillDetector().detect(make_context(kills), "A")
    assert len(moments) == 1
    assert moments[0].highlight_type is HighlightType.MULTI_KILL
    assert "Triple" in moments[0].description


def test_two_kills_is_not_a_multikill():
    kills = round_with_kills("A", [1000, 1200])
    assert MultiKillDetector().detect(make_context(kills), "A") == []


def test_five_kills_is_an_ace_not_a_multikill():
    kills = round_with_kills("A", [1000, 1200, 1400, 1600, 1800])
    ctx = make_context(kills)
    assert MultiKillDetector().detect(ctx, "A") == []
    aces = AceDetector().detect(ctx, "A")
    assert len(aces) == 1
    assert aces[0].highlight_type is HighlightType.ACE
    assert "ACE" in aces[0].description


def test_multikill_spans_first_to_last_kill():
    # A short span (under the 25s cap) is kept whole.
    kills = round_with_kills("A", [5000, 5500, 6000])
    moment = MultiKillDetector().detect(make_context(kills), "A")[0]
    assert moment.start_tick == 5000 - 3 * 64
    assert moment.end_tick == 6000 + 2 * 64
    assert moment.core_tick == 6000


def test_long_multikill_span_is_capped():
    # Three kills strung across 40s; the span must trim to 25s before the last.
    last_tick = 10_000 + 40 * 64
    kills = round_with_kills("A", [10_000, 11_000, last_tick])
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    moment = MultiKillDetector().detect(ctx, "A")[0]
    assert moment.core_tick == last_tick
    assert moment.start_tick == (last_tick - 25 * 64) - 3 * 64
    assert moment.end_tick == last_tick + 2 * 64


def test_multikills_across_two_rounds():
    kills = round_with_kills("A", [1000, 1100, 1200], round_number=1) + round_with_kills(
        "A", [2000, 2100, 2200, 2300], round_number=2
    )
    rounds = [make_round(1), make_round(2)]
    moments = MultiKillDetector().detect(make_context(kills, rounds), "A")
    assert len(moments) == 2
    assert {m.round_number for m in moments} == {1, 2}
    assert "Quad" in [m.description for m in moments if m.round_number == 2][0]
