"""Tests for the flash utility detector."""

from highlights.engine.detectors.utility_flash import FlashUtilityDetector
from highlights.engine.moments import HighlightType

from tests.factories import make_blind, make_context, make_round

# P is ct; E* are t (enemies); M* are ct (teammates).
ROSTER = {1: {"P": "ct", "M1": "ct", "E1": "t", "E2": "t", "E3": "t"}}


def context(blinds):
    return make_context(
        kills=[],
        rounds=[make_round(1, start=0, end=100_000)],
        round_rosters=ROSTER,
        blinds=blinds,
    )


def test_flash_blinding_two_enemies_is_a_moment():
    blinds = [make_blind(5000, "P", "E1"), make_blind(5000, "P", "E2")]
    moments = FlashUtilityDetector().detect(context(blinds), "P")
    assert len(moments) == 1
    assert moments[0].highlight_type is HighlightType.UTILITY
    assert "2 enemies" in moments[0].description


def test_single_enemy_flash_is_not_enough():
    blinds = [make_blind(5000, "P", "E1")]
    assert FlashUtilityDetector().detect(context(blinds), "P") == []


def test_team_and_self_flashes_are_ignored():
    blinds = [
        make_blind(5000, "P", "M1"),  # teammate
        make_blind(5000, "P", "P"),  # self
        make_blind(5000, "P", "E1"),  # only one real enemy
    ]
    assert FlashUtilityDetector().detect(context(blinds), "P") == []


def test_short_blinks_are_filtered_out():
    blinds = [
        make_blind(5000, "P", "E1", duration=0.3),
        make_blind(5000, "P", "E2", duration=0.4),
    ]
    assert FlashUtilityDetector().detect(context(blinds), "P") == []


def test_two_separate_flashes_make_two_moments():
    blinds = [
        make_blind(5000, "P", "E1"),
        make_blind(5000, "P", "E2"),
        make_blind(9000, "P", "E1"),
        make_blind(9000, "P", "E3"),
    ]
    moments = FlashUtilityDetector().detect(context(blinds), "P")
    assert [m.core_tick for m in moments] == [5000, 9000]
