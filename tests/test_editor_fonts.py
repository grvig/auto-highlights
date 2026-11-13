"""Tests for caption font selection."""

from pathlib import Path

import pytest

from highlights.editor.fonts import FontError, filter_path, find_font, needs_wide_font


def install(folder: Path, *names: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"font")
    return folder


def test_latin_names_do_not_need_a_wide_font():
    assert not needs_wide_font("semi — ACE · Round 5")
    assert not needs_wide_font("Ibrahim Moizoos")


def test_cjk_and_cyrillic_names_do():
    assert needs_wide_font("臻咘踔")
    assert needs_wide_font("Саша")


def test_display_font_is_preferred_for_latin(tmp_path):
    folder = install(tmp_path, "arialbd.ttf", "bahnschrift.ttf", "segoeuib.ttf", "msyh.ttc")
    assert find_font("semi", (folder,)).name == "segoeuib.ttf"


def test_wide_font_is_used_for_cjk(tmp_path):
    folder = install(tmp_path, "bahnschrift.ttf", "msyh.ttc")
    assert find_font("唱支荭歌给灙听", (folder,)).name == "msyh.ttc"


def test_bundled_fonts_win(tmp_path):
    bundled = install(tmp_path / "bundled", "display.ttf")
    system = install(tmp_path / "system", "bahnschrift.ttf")
    assert find_font("semi", (bundled, system)).parent == bundled


def test_missing_fonts_raise(tmp_path):
    with pytest.raises(FontError):
        find_font("semi", (tmp_path,))


def test_filter_path_escapes_the_drive_colon():
    assert filter_path(Path("C:/Windows/Fonts/arialbd.ttf")) == "C\\:/Windows/Fonts/arialbd.ttf"
