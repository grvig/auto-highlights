"""Tests for title and outro cards."""

from pathlib import Path

import pytest

from highlights.editor import cards
from highlights.editor.cards import card_command, outro_lines, title_lines


@pytest.fixture(autouse=True)
def fake_font(monkeypatch, tmp_path):
    font = tmp_path / "font.ttf"
    font.write_bytes(b"f")
    monkeypatch.setattr(cards, "find_font", lambda text: font)


def test_title_names_the_player_and_maps():
    lines = title_lines("semi", ["de_nuke", "de_cache"], 7)
    assert [line.text for line in lines] == ["semi", "NUKE  ·  CACHE", "7 HIGHLIGHTS"]


def test_map_names_lose_their_prefix():
    assert cards.pretty_map("de_dust2") == "Dust2"
    assert cards.pretty_map("cs_office") == "Office"
    assert cards.pretty_map("workshop_map") == "workshop_map"


def test_single_highlight_is_not_plural():
    assert title_lines("semi", [], 1)[-1].text == "1 HIGHLIGHT"


def test_outro_mentions_kills_when_known():
    assert [line.text for line in outro_lines("semi", 12)] == ["GG", "semi", "12 KILLS SHOWN"]
    assert len(outro_lines("semi")) == 2


def test_card_matches_the_clip_format(tmp_path):
    args = card_command(title_lines("semi", ["de_nuke"], 3), tmp_path / "title.mp4",
                        tmp_path / "work", duration=2.5, width=1440, height=1080, fps=60)
    color = args[args.index("-i") + 1]
    assert "s=1440x1080" in color and "r=60" in color and "d=2.5" in color
    assert any(a.startswith("anullsrc=") for a in args)
    vf = args[args.index("-vf") + 1]
    assert vf.count("drawtext=") == 3
    assert "fade=t=out:st=2.1" in vf
    assert args[-1].endswith("title.mp4")


def test_card_text_is_read_from_files(tmp_path):
    card_command([cards.CardLine("唱支荭歌给灙听", 0.1)], tmp_path / "t.mp4", tmp_path / "w")
    assert (tmp_path / "w" / "card_t_0.txt").read_text(encoding="utf-8") == "唱支荭歌给灙听"
