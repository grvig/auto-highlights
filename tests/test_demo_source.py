"""Tests for the awpy wrapper that need no demo file on disk."""

import pytest

from highlights.engine.demo_source import (
    GOTV_CLIENT_NAME,
    DemoError,
    DemoInfo,
    DemoSource,
    Player,
)


def make_info(client_name: str) -> DemoInfo:
    return DemoInfo(
        map_name="de_nuke",
        server_name="test server",
        client_name=client_name,
        tickrate=64,
    )


def test_sourcetv_demo_is_recognised_as_gotv():
    assert make_info(GOTV_CLIENT_NAME).is_gotv


def test_pov_demo_is_not_gotv():
    # POV demos carry the recording player's name instead.
    assert not make_info("some_player").is_gotv


def test_missing_demo_file_raises_demo_error(tmp_path):
    with pytest.raises(DemoError, match="No demo file"):
        DemoSource(tmp_path / "nope.dem")


def test_player_str_shows_name_and_side():
    player = Player(steamid="76561198000000000", name="semi", starting_side="t")
    assert str(player) == "semi (t)"
