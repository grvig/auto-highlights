"""Tests for clutch situation analysis."""

from highlights.engine.clutch_analysis import analyse_clutch

from tests.factories import make_kill

# Player P (ct) with teammates T1..T4; enemies E1..E5.
TEAMMATES = {"T1", "T2", "T3", "T4"}
ENEMIES = {"E1", "E2", "E3", "E4", "E5"}


def analyse(round_kills, winner="ct", player_dead_side="ct"):
    return analyse_clutch(
        round_number=1,
        round_winner=winner,
        player_steamid="P",
        player_side="ct",
        teammates=TEAMMATES,
        enemies=ENEMIES,
        round_kills=round_kills,
    )


def test_no_clutch_when_teammates_survive():
    # Only one teammate dies; player never becomes last alive.
    kills = [make_kill(1000, "E1", "T1")]
    assert analyse(kills) is None


def test_one_v_two_clutch_won():
    # P kills 3 enemies while teammates trade down; last teammate dies with
    # E4,E5 still alive -> 1v2, which P then wins.
    kills = [
        make_kill(1000, "P", "E1"),
        make_kill(1100, "E2", "T1"),
        make_kill(1200, "P", "E2"),
        make_kill(1300, "E3", "T2"),
        make_kill(1400, "P", "E3"),
        make_kill(1500, "E4", "T3"),
        make_kill(1600, "E5", "T4"),  # clutch starts here: E4,E5 alive -> 1v2
        make_kill(1700, "P", "E4"),
        make_kill(1800, "P", "E5"),
    ]
    sit = analyse(kills)
    assert sit is not None
    assert sit.enemies_at_start == 2
    assert sit.won
    assert sit.start_tick == 1600
    assert "1v2" in sit.label


def test_clutch_lost_when_other_side_wins():
    kills = [
        make_kill(1000, "E1", "T1"),
        make_kill(1100, "E1", "T2"),
        make_kill(1200, "E1", "T3"),
        make_kill(1300, "E1", "T4"),  # 1v5 begins
    ]
    sit = analyse(kills, winner="t")
    assert sit is not None
    assert sit.enemies_at_start == 5
    assert not sit.won


def test_clutch_lost_when_player_dies():
    kills = [
        make_kill(1000, "E1", "T1"),
        make_kill(1100, "E1", "T2"),
        make_kill(1200, "E1", "T3"),
        make_kill(1300, "E1", "T4"),  # 1v5
        make_kill(1400, "E1", "P"),  # player dies
    ]
    sit = analyse(kills, winner="ct")
    assert sit is not None
    assert not sit.won


def test_no_clutch_if_all_enemies_already_dead():
    # Teammates die only after every enemy is gone: not a clutch.
    kills = [
        make_kill(1000, "P", "E1"),
        make_kill(1100, "T1", "E2"),
        make_kill(1200, "T1", "E3"),
        make_kill(1300, "T1", "E4"),
        make_kill(1400, "T1", "E5"),
        make_kill(1500, "T5unknown", "T1"),  # teammates die post-round, no enemies
        make_kill(1600, "x", "T2"),
        make_kill(1700, "x", "T3"),
        make_kill(1800, "x", "T4"),
    ]
    assert analyse(kills) is None
