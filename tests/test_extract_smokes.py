"""Tests for Smoke extraction and kill position enrichment."""

import polars as pl

from highlights.engine.models import extract_kills, extract_smokes


def smoke_frame(rows):
    return pl.DataFrame(
        rows,
        schema={
            "entityid": pl.Int32,
            "tick": pl.Int32,
            "user_name": pl.Utf8,
            "user_steamid": pl.Utf8,
            "x": pl.Float32,
            "y": pl.Float32,
            "z": pl.Float32,
        },
    )


def test_extract_smokes_maps_thrower_and_position_ordered():
    frame = smoke_frame(
        [
            {"entityid": 1, "tick": 2000, "user_name": "A", "user_steamid": "sa",
             "x": 100.0, "y": 200.0, "z": 0.0},
            {"entityid": 2, "tick": 1000, "user_name": "B", "user_steamid": "sb",
             "x": -50.0, "y": 75.0, "z": 0.0},
        ]
    )
    smokes = extract_smokes(frame)
    assert [s.tick for s in smokes] == [1000, 2000]
    assert smokes[0].thrower_steamid == "sb"
    assert smokes[1].x == 100.0 and smokes[1].y == 200.0


def test_extract_smokes_drops_rows_without_thrower():
    frame = smoke_frame(
        [{"entityid": 1, "tick": 500, "user_name": None, "user_steamid": None,
          "x": 0.0, "y": 0.0, "z": 0.0}]
    )
    assert extract_smokes(frame) == []


def test_extract_kills_reads_victim_position():
    frame = pl.DataFrame(
        [
            {
                "round_num": 1,
                "tick": 1000,
                "attacker_steamid": "A",
                "attacker_name": "att",
                "attacker_side": "ct",
                "victim_steamid": "B",
                "victim_name": "vic",
                "victim_side": "t",
                "weapon": "ak47",
                "headshot": False,
                "victim_X": 123.5,
                "victim_Y": -456.5,
            }
        ]
    )
    kill = extract_kills(frame)[0]
    assert kill.victim_x == 123.5
    assert kill.victim_y == -456.5


def test_extract_kills_without_position_columns_defaults_to_zero():
    frame = pl.DataFrame(
        [
            {
                "round_num": 1,
                "tick": 1000,
                "attacker_steamid": "A",
                "attacker_name": "att",
                "attacker_side": "ct",
                "victim_steamid": "B",
                "victim_name": "vic",
                "victim_side": "t",
                "weapon": "ak47",
                "headshot": False,
            }
        ]
    )
    kill = extract_kills(frame)[0]
    assert kill.victim_x == 0.0
    assert kill.victim_y == 0.0


def test_extract_kills_reads_style_details():
    frame = pl.DataFrame(
        [
            {
                "round_num": 1,
                "tick": 1000,
                "attacker_steamid": "A",
                "attacker_name": "att",
                "attacker_side": "ct",
                "victim_steamid": "B",
                "victim_name": "vic",
                "victim_side": "t",
                "weapon": "awp",
                "headshot": True,
                "penetrated": 1,
                "thrusmoke": True,
                "noscope": True,
                "attackerblind": False,
                "attackerinair": True,
                "distance": 42.5,
            }
        ]
    )
    kill = extract_kills(frame)[0]
    assert kill.wallbang and kill.through_smoke and kill.noscope and kill.attacker_airborne
    assert not kill.attacker_blind
    assert kill.distance == 42.5
    assert kill.style_tags == (
        "noscope", "wallbang", "through smoke", "airborne", "long range", "headshot",
    )


def test_plain_kill_has_no_style_tags():
    frame = pl.DataFrame(
        [
            {
                "round_num": 1, "tick": 1000, "attacker_steamid": "A",
                "attacker_name": "att", "attacker_side": "ct", "victim_steamid": "B",
                "victim_name": "vic", "victim_side": "t", "weapon": "ak47",
                "headshot": False, "penetrated": 0, "distance": 8.0,
            }
        ]
    )
    assert extract_kills(frame)[0].style_tags == ()
