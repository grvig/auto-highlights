"""Tests for readable demo names (map, score, result)."""

from pathlib import Path

import pytest

from highlights.engine.describe import Descriptions, pretty_map, read_description


def test_map_names_read_like_people_say_them():
    assert pretty_map("de_cache") == "Cache"
    assert pretty_map("de_dust2") == "Dust2"
    assert pretty_map("cs_office") == "Office"
    assert pretty_map("workshop/123/de_cbble_classic") == "Cbble Classic"


def test_descriptions_are_read_once_and_kept(tmp_path):
    demo = tmp_path / "match.dem"
    demo.write_bytes(b"demo")
    reads = []

    def reader(path, steamid):
        reads.append(path)
        return {"map": "Cache", "score": [13, 11], "result": "W"}

    store = Descriptions(tmp_path / "cache" / "descriptions.json", reader)
    assert store.describe(demo, "7656") == {"map": "Cache", "score": [13, 11], "result": "W"}
    again = Descriptions(tmp_path / "cache" / "descriptions.json", reader)  # a later run
    assert again.describe(demo, "7656")["score"] == [13, 11]
    assert reads == [demo]


def test_a_changed_file_or_another_player_is_read_again(tmp_path):
    demo = tmp_path / "match.dem"
    demo.write_bytes(b"demo")
    reads = []
    store = Descriptions(tmp_path / "d.json", lambda p, s: reads.append(s) or {"map": "Nuke"})
    store.describe(demo, "1")
    store.describe(demo, "2")
    demo.write_bytes(b"a longer demo")
    store.describe(demo, "1")
    assert reads == ["1", "2", "1"]


def test_a_compressed_download_is_read_from_its_unpacked_copy(tmp_path):
    archive, unpacked = tmp_path / "f.dem.zst", tmp_path / "f.dem"
    archive.write_bytes(b"z")
    seen = []
    Descriptions(tmp_path / "d.json", lambda p, s: seen.append(p) or {}).describe(archive, None, unpacked)
    assert seen == [unpacked]


DEMO = Path(r"D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays"
            r"\match730_003828772214044361202_0866075277_383.dem")


@pytest.mark.skipif(not DEMO.is_file(), reason="needs the real Cache demo from 2026-07")
def test_a_real_demo_reads_as_cache_won_13_11():
    assert read_description(DEMO, "76561199266315708") == {"map": "Cache", "score": [13, 11], "result": "W"}
