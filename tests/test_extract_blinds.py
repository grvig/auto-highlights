"""Tests for Blind extraction from the player_blind event frame."""

import polars as pl

from highlights.engine.models import extract_blinds


def blind_frame(rows):
    return pl.DataFrame(
        rows,
        schema={
            "attacker_name": pl.Utf8,
            "attacker_steamid": pl.Utf8,
            "blind_duration": pl.Float32,
            "tick": pl.Int32,
            "user_name": pl.Utf8,
            "user_steamid": pl.Utf8,
        },
    )


def test_extract_maps_user_to_victim_and_orders_by_tick():
    frame = blind_frame(
        [
            {
                "attacker_name": "F",
                "attacker_steamid": "flasher",
                "blind_duration": 2.5,
                "tick": 2000,
                "user_name": "V",
                "user_steamid": "victim",
            },
            {
                "attacker_name": "F",
                "attacker_steamid": "flasher",
                "blind_duration": 1.0,
                "tick": 1000,
                "user_name": "V2",
                "user_steamid": "victim2",
            },
        ]
    )
    blinds = extract_blinds(frame)
    assert [b.tick for b in blinds] == [1000, 2000]
    assert blinds[1].flasher_steamid == "flasher"
    assert blinds[1].victim_steamid == "victim"
    assert blinds[1].duration_seconds == 2.5


def test_extract_drops_rows_without_flasher():
    frame = blind_frame(
        [
            {
                "attacker_name": None,
                "attacker_steamid": None,
                "blind_duration": 2.0,
                "tick": 500,
                "user_name": "V",
                "user_steamid": "victim",
            }
        ]
    )
    assert extract_blinds(frame) == []
