"""Tests for highlight captions."""

import pytest

from highlights.editor import captions
from highlights.editor.captions import Caption, caption_filter, caption_for, headline_for
from highlights.engine.moments import HighlightType, Moment


def moment(description, round_number=5):
    return Moment(
        round_number=round_number, highlight_type=HighlightType.ACE, player_steamid="P",
        core_tick=100, start_tick=0, end_tick=200, description=description,
    )


@pytest.fixture(autouse=True)
def fake_font(monkeypatch, tmp_path):
    font = tmp_path / "font.ttf"
    font.write_bytes(b"f")
    monkeypatch.setattr(captions, "find_font", lambda text: font)


def test_headline_drops_the_detail_in_brackets():
    assert headline_for(moment("ACE (5 kills) + 1v3 clutch (won)")) == "ACE + 1V3 CLUTCH"
    assert headline_for(moment("Triple kill (3 kills)")) == "TRIPLE KILL"


def test_caption_names_player_map_and_round():
    cap = caption_for(moment("ACE (5 kills)"), "semi", "de_nuke")
    assert cap.detail == "semi  ·  de_nuke  ·  Round 5"


def test_caption_without_a_map():
    assert caption_for(moment("x", 12), "semi").detail == "semi  ·  Round 12"


def test_filter_reads_text_from_files_so_names_need_no_escaping(tmp_path):
    cap = Caption("ACE", "唱支荭歌给灙听: 'quoted'")
    chain = caption_filter(cap, tmp_path / "work")
    assert chain.count("drawtext=") == 2
    assert "唱支" not in chain  # the name lives in a file, not the filter
    detail = (tmp_path / "work" / "caption_detail.txt").read_text(encoding="utf-8")
    assert detail == "唱支荭歌给灙听: 'quoted'"


def test_caption_fades_in_and_out():
    alpha = captions._alpha(0.3, 2.9)
    assert alpha.startswith("if(lt(t,0.3),0")
    assert "(2.9-t)/0.25" in alpha
