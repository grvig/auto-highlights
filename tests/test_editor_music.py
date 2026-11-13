"""Tests for the music bed."""

from pathlib import Path

import pytest

from highlights.editor.music import MusicError, check_music, music_command, music_filter


def test_music_must_exist_and_be_audio(tmp_path):
    song = tmp_path / "song.mp3"
    song.write_bytes(b"id3")
    assert check_music(song) == song
    with pytest.raises(MusicError, match="not found"):
        check_music(tmp_path / "missing.mp3")
    text = tmp_path / "notes.txt"
    text.write_text("x")
    with pytest.raises(MusicError, match="Unsupported"):
        check_music(text)


def test_music_fades_and_ducks_under_the_game():
    graph = music_filter(60.0)
    assert "afade=t=in:d=1" in graph
    assert "afade=t=out:st=57.5:d=2.5" in graph
    assert "[music][key]sidechaincompress" in graph
    assert "amix=inputs=2:duration=first" in graph


def test_music_can_start_partway_into_the_track():
    assert "atrim=start=12.5" in music_filter(30.0, start=12.5)


def test_command_loops_the_track_and_keeps_the_picture():
    args = music_command(Path("reel.mp4"), Path("song.mp3"), Path("out.mp4"), 42.0)
    assert args[args.index("-stream_loop") + 1] == "-1"
    assert "copy" == args[args.index("-c:v") + 1]
    assert args[args.index("-t") + 1] == "42.000"
