"""Tests for the smoke utility detector."""

from highlights.engine.detectors.utility_smoke import SmokeUtilityDetector
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill, make_round, make_smoke

# P is ct; enemies are t.
ROSTER = {1: {"P": "ct", "E1": "t", "E2": "t"}}


def context(smokes, kills):
    return make_context(
        kills=kills,
        rounds=[make_round(1, start=0, end=100_000)],
        round_rosters=ROSTER,
        smokes=smokes,
    )


def test_smoke_with_nearby_enemy_kill_is_a_moment():
    smokes = [make_smoke(5000, "P", x=100.0, y=100.0)]
    kills = [
        make_kill(5300, "P", "E1", victim_side="t", victim_x=200.0, victim_y=150.0)
    ]
    moments = SmokeUtilityDetector().detect(context(smokes, kills), "P")
    assert len(moments) == 1
    assert moments[0].highlight_type is HighlightType.UTILITY
    assert "set up 1 kill" in moments[0].description


def test_kill_too_far_from_smoke_does_not_count():
    smokes = [make_smoke(5000, "P", x=0.0, y=0.0)]
    kills = [make_kill(5300, "P", "E1", victim_side="t", victim_x=5000.0, victim_y=5000.0)]
    assert SmokeUtilityDetector().detect(context(smokes, kills), "P") == []


def test_kill_too_late_does_not_count():
    smokes = [make_smoke(5000, "P", x=100.0, y=100.0)]
    # 20s later, past the 12s window.
    kills = [make_kill(5000 + 20 * 64, "P", "E1", victim_side="t", victim_x=120.0, victim_y=120.0)]
    assert SmokeUtilityDetector().detect(context(smokes, kills), "P") == []


def test_teammate_death_near_smoke_is_not_impact():
    smokes = [make_smoke(5000, "P", x=100.0, y=100.0)]
    # A ct (teammate of P) dies near the smoke — not the smoke helping.
    kills = [make_kill(5300, "E1", "P2", victim_side="ct", victim_x=120.0, victim_y=120.0)]
    assert SmokeUtilityDetector().detect(context(smokes, kills), "P") == []


def test_other_players_smokes_are_ignored():
    smokes = [make_smoke(5000, "OTHER", x=100.0, y=100.0)]
    kills = [make_kill(5300, "OTHER", "E1", victim_side="t", victim_x=120.0, victim_y=120.0)]
    assert SmokeUtilityDetector().detect(context(smokes, kills), "P") == []


def test_multiple_enemy_kills_near_one_smoke_report_the_count():
    smokes = [make_smoke(5000, "P", x=100.0, y=100.0)]
    kills = [
        make_kill(5200, "P", "E1", victim_side="t", victim_x=150.0, victim_y=150.0),
        make_kill(5400, "P", "E2", victim_side="t", victim_x=120.0, victim_y=80.0),
    ]
    moment = SmokeUtilityDetector().detect(context(smokes, kills), "P")[0]
    assert "set up 2 kills" in moment.description
