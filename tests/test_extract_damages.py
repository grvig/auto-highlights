"""Tests for Damage extraction."""

import polars as pl

from highlights.engine.models import extract_damages


def damage_frame(rows):
    return pl.DataFrame(rows)


def row(tick, attacker, victim, weapon="hegrenade", real=40, raw=55):
    return {
        "round_num": 1,
        "tick": tick,
        "attacker_steamid": attacker,
        "attacker_name": "att" if attacker else None,
        "attacker_side": "ct",
        "victim_steamid": victim,
        "victim_side": "t",
        "weapon": weapon,
        "dmg_health": raw,
        "dmg_health_real": real,
    }


def test_extract_prefers_real_health_removed():
    dmg = extract_damages(damage_frame([row(1000, "A", "B", real=30, raw=90)]))
    assert dmg[0].damage == 30


def test_extract_orders_by_tick_and_drops_world_damage():
    frame = damage_frame(
        [row(2000, "A", "B"), row(1000, None, "C"), row(1500, "A", "D")]
    )
    dmg = extract_damages(frame)
    assert [d.tick for d in dmg] == [1500, 2000]


def test_falls_back_to_dmg_health_when_no_real_column():
    frame = pl.DataFrame(
        [
            {
                "round_num": 1,
                "tick": 1000,
                "attacker_steamid": "A",
                "attacker_name": "att",
                "attacker_side": "ct",
                "victim_steamid": "B",
                "victim_side": "t",
                "weapon": "inferno",
                "dmg_health": 25,
            }
        ]
    )
    assert extract_damages(frame)[0].damage == 25
