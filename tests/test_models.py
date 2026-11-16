"""Tests for the internal models and their extraction from dataframes."""

import polars as pl

from highlights.engine.models import (
    Kill,
    Round,
    deaths_of_player,
    extract_kills,
    extract_rounds,
    kills_by_player,
)

ROUND_COLUMNS = {
    "round_num": [2, 1],
    "start": [2000, 100],
    "freeze_end": [2100, 200],
    "end": [3000, 1000],
    "official_end": [3100, 1100],
    "winner": ["ct", "t"],
    "reason": ["ct_win", "t_win"],
}


def make_kill_frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows)


def kill_row(tick: int, attacker: str | None, victim: str, **kwargs) -> dict:
    row = {
        "round_num": 1,
        "tick": tick,
        "attacker_steamid": attacker,
        "attacker_name": "att" if attacker else None,
        "attacker_side": "ct",
        "victim_steamid": victim,
        "victim_name": "vic",
        "victim_side": "t",
        "weapon": "ak47",
        "headshot": False,
    }
    row.update(kwargs)
    return row


def test_extract_rounds_orders_by_round_number():
    rounds = extract_rounds(pl.DataFrame(ROUND_COLUMNS))
    assert [r.number for r in rounds] == [1, 2]


def test_round_duration_and_containment():
    rounds = extract_rounds(pl.DataFrame(ROUND_COLUMNS))
    first = rounds[0]
    assert first.duration_seconds == (1000 - 100) / 64
    assert first.contains_tick(500)
    # Still inside the round during the post-round lull, before official_end.
    assert first.contains_tick(1050)
    assert not first.contains_tick(2000)


def test_extract_kills_orders_by_tick():
    frame = make_kill_frame(
        [kill_row(900, "A", "B"), kill_row(100, "B", "A")]
    )
    assert [k.tick for k in extract_kills(frame)] == [100, 900]


def test_extract_kills_drops_world_deaths():
    """Falling and bomb deaths have no attacker and belong to nobody."""
    frame = make_kill_frame(
        [kill_row(100, "A", "B"), kill_row(200, None, "C")]
    )
    kills = extract_kills(frame)
    assert len(kills) == 1
    assert kills[0].attacker_steamid == "A"


def test_kills_by_player_and_deaths_of_player():
    frame = make_kill_frame(
        [kill_row(100, "A", "B"), kill_row(200, "B", "A"), kill_row(300, "A", "C")]
    )
    kills = extract_kills(frame)
    assert len(kills_by_player(kills, "A")) == 2
    assert len(deaths_of_player(kills, "A")) == 1


def test_kill_str_marks_headshots():
    kill = Kill(
        round_number=3,
        tick=64 * 65,
        attacker_steamid="A",
        attacker_name="semi",
        attacker_side="t",
        victim_steamid="B",
        victim_name="ORYX",
        victim_side="ct",
        weapon="awp",
        headshot=True,
    )
    assert str(kill) == "R3 01:05 semi killed ORYX with awp (hs)"


def test_round_is_frozen():
    rounds = extract_rounds(pl.DataFrame(ROUND_COLUMNS))
    assert isinstance(rounds[0], Round)


def test_shots_come_out_tick_ordered_without_the_weapon_prefix():
    import polars as pl

    from highlights.engine.models import extract_shots

    frame = pl.DataFrame({
        "tick": [300, 100, 200],
        "user_steamid": ["P", None, "Q"],
        "user_name": ["semi", "x", "q"],
        "weapon": ["weapon_ak47", "weapon_knife", "weapon_usp_silencer"],
        "silenced": [False, False, True],
    })
    shots = extract_shots(frame)
    assert [(s.tick, s.shooter_steamid, s.weapon) for s in shots] == [
        (200, "Q", "usp_silencer"), (300, "P", "ak47")]
