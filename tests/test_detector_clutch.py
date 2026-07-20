"""Tests for the clutch detector."""

from highlights.engine.detectors.clutch import ClutchDetector
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill, make_round

ROSTER = {
    "P": "ct",
    "T1": "ct",
    "T2": "ct",
    "T3": "ct",
    "T4": "ct",
    "E1": "t",
    "E2": "t",
    "E3": "t",
    "E4": "t",
    "E5": "t",
}


def won_1v2_kills():
    return [
        make_kill(1000, "P", "E1", round_number=1),
        make_kill(1100, "E2", "T1", round_number=1),
        make_kill(1200, "P", "E2", round_number=1),
        make_kill(1300, "E3", "T2", round_number=1),
        make_kill(1400, "P", "E3", round_number=1),
        make_kill(1500, "E4", "T3", round_number=1),
        make_kill(1600, "E5", "T4", round_number=1),  # 1v2 begins
        make_kill(1700, "P", "E4", round_number=1),
        make_kill(1800, "P", "E5", round_number=1),
    ]


def context(winner="ct"):
    return make_context(
        won_1v2_kills(),
        rounds=[make_round(1, start=500, end=2000, winner=winner)],
        round_rosters={1: ROSTER},
    )


def test_won_clutch_produces_a_moment():
    moments = ClutchDetector().detect(context(winner="ct"), "P")
    assert len(moments) == 1
    m = moments[0]
    assert m.highlight_type is HighlightType.CLUTCH
    assert "1v2" in m.description and "won" in m.description
    assert m.core_tick == 1600


def test_lost_clutch_excluded_by_default():
    assert ClutchDetector().detect(context(winner="t"), "P") == []


def test_lost_clutch_included_when_won_only_false():
    moments = ClutchDetector(won_only=False).detect(context(winner="t"), "P")
    assert len(moments) == 1
    assert "lost" in moments[0].description


def test_no_clutch_for_player_not_in_situation():
    # T1 died early and was never last alive.
    assert ClutchDetector().detect(context(), "T1") == []


def test_clutch_moment_spans_to_round_end():
    moment = ClutchDetector().detect(context(), "P")[0]
    # padded from the clutch start; end clamped near round end + post-roll
    assert moment.start_tick == 1600 - 3 * 64
    assert moment.end_tick == 2000 + 2 * 64
