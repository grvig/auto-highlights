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


def test_directory_path_reports_a_folder(tmp_path):
    with pytest.raises(DemoError, match="is a folder"):
        DemoSource(tmp_path)


def test_non_dem_file_is_rejected(tmp_path):
    wrong = tmp_path / "clip.mp4"
    wrong.write_text("not a demo")
    with pytest.raises(DemoError, match="not a .dem file"):
        DemoSource(wrong)


def test_player_str_shows_name_and_side():
    player = Player(steamid="76561198000000000", name="semi", starting_side="t")
    assert str(player) == "semi (t)"


def test_cache_hit_skips_parsing(tmp_path, monkeypatch):
    import polars as pl

    from highlights.engine.cache import DemoCache

    demo = tmp_path / "match.dem"
    demo.write_bytes(b"not really a demo")
    cache = DemoCache(tmp_path / "cache")
    cache.store(
        demo,
        {"map_name": "de_nuke", "client_name": GOTV_CLIENT_NAME},
        {
            "rounds": pl.DataFrame({"round_num": [1]}),
            "kills": pl.DataFrame({"tick": [100]}),
            "damages": pl.DataFrame({"tick": [90]}),
            "ticks": pl.DataFrame({"tick": [1, 2]}),
        },
    )

    def no_parsing(*args, **kwargs):
        raise AssertionError("a cache hit must not parse the demo")

    monkeypatch.setattr("highlights.engine.demo_source.Demo", no_parsing)
    source = DemoSource(demo, cache=cache)
    assert source.info.map_name == "de_nuke"
    assert source.info.is_gotv
    assert source.kills.height == 1
    assert source.extra_event("player_blind") is None
