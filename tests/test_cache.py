"""Tests for the parsed-demo cache."""

import os

import polars as pl

from highlights.engine.cache import HEADER_FILE, DemoCache


def make_demo(tmp_path, name="match.dem", content=b"demo-bytes"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def frames():
    return {
        "kills": pl.DataFrame({"tick": [1, 2], "weapon": ["ak47", "awp"]}),
        "rounds": pl.DataFrame({"round_num": [1]}),
        "player_blind": None,  # an event the demo did not contain
    }


def test_round_trip_returns_the_same_tables(tmp_path):
    demo = make_demo(tmp_path)
    cache = DemoCache(tmp_path / "cache")
    cache.store(demo, {"map_name": "de_nuke"}, frames())

    cached = cache.load(demo)
    assert cached.header == {"map_name": "de_nuke"}
    assert cached.frames["kills"].equals(frames()["kills"])
    assert "player_blind" not in cached.frames


def test_miss_on_an_uncached_demo(tmp_path):
    assert DemoCache(tmp_path / "cache").load(make_demo(tmp_path)) is None


def test_changed_file_is_not_served_stale(tmp_path):
    demo = make_demo(tmp_path)
    cache = DemoCache(tmp_path / "cache")
    cache.store(demo, {"map_name": "old"}, frames())

    demo.write_bytes(b"a different, longer demo file")
    os.utime(demo, ns=(1, 1))
    assert cache.load(demo) is None


def test_entry_without_header_counts_as_incomplete(tmp_path):
    demo = make_demo(tmp_path)
    cache = DemoCache(tmp_path / "cache")
    entry = cache.store(demo, {"map_name": "de_nuke"}, frames())
    (entry / HEADER_FILE).unlink()  # simulate a crash before the header landed
    assert cache.load(demo) is None


def test_restoring_replaces_the_old_entry(tmp_path):
    demo = make_demo(tmp_path)
    cache = DemoCache(tmp_path / "cache")
    cache.store(demo, {"v": 1}, frames())
    cache.store(demo, {"v": 2}, {"kills": pl.DataFrame({"tick": [9]})})

    cached = cache.load(demo)
    assert cached.header == {"v": 2}
    assert set(cached.frames) == {"kills"}
    assert not list((tmp_path / "cache").glob("*.tmp-*"))
