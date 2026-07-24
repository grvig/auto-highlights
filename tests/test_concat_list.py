"""Tests for the ffmpeg concat list file."""

from pathlib import Path

import pytest

from highlights.stitcher.concat_list import (
    build_concat_list,
    escape_path,
    write_concat_list,
)


def test_each_clip_becomes_a_file_line():
    text = build_concat_list([Path("a.mkv"), Path("b.mkv")])
    assert text == "file 'a.mkv'\nfile 'b.mkv'\n"


def test_order_is_preserved():
    paths = [Path(f"{i:03d}.mkv") for i in (1, 2, 10)]
    lines = build_concat_list(paths).splitlines()
    assert lines == ["file '001.mkv'", "file '002.mkv'", "file '010.mkv'"]


def test_single_quote_in_path_is_escaped():
    # A name with an apostrophe would otherwise break out of the quoting.
    escaped = escape_path("clips/o'brien.mkv")
    assert escaped == "clips/o'\\''brien.mkv"
    text = build_concat_list([Path("o'brien.mkv")])
    assert "file 'o'\\''brien.mkv'\n" == text


def test_windows_backslash_paths_are_left_intact():
    text = build_concat_list([Path(r"C:\clips\001.mkv")])
    assert "C:\\clips\\001.mkv" in text


def test_empty_list_is_rejected():
    with pytest.raises(ValueError, match="zero clips"):
        build_concat_list([])


def test_write_creates_file_and_parent(tmp_path):
    dest = tmp_path / "sub" / "list.txt"
    written = write_concat_list([Path("a.mkv"), Path("b.mkv")], dest)
    assert written == dest
    assert dest.read_text(encoding="utf-8") == "file 'a.mkv'\nfile 'b.mkv'\n"
