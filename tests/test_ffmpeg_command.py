"""Tests for the ffmpeg concat command builders."""

from pathlib import Path

from highlights.stitcher.ffmpeg_command import (
    build_reencode,
    build_stream_copy,
)

LIST = Path("clips/list.txt")
OUT = Path("output/reel.mkv")


def test_stream_copy_uses_concat_demuxer_and_copy():
    cmd = build_stream_copy("ffmpeg", LIST, OUT)
    assert cmd.args[0] == "ffmpeg"
    assert "-f" in cmd.args and "concat" in cmd.args
    assert cmd.args[cmd.args.index("-c") + 1] == "copy"
    assert cmd.args[-1] == str(OUT)
    assert not cmd.re_encoded


def test_stream_copy_allows_absolute_paths_and_overwrites():
    cmd = build_stream_copy("ffmpeg", LIST, OUT)
    assert "-safe" in cmd.args
    assert cmd.args[cmd.args.index("-safe") + 1] == "0"
    assert "-y" in cmd.args


def test_input_is_the_concat_list():
    cmd = build_stream_copy("ffmpeg", LIST, OUT)
    assert cmd.args[cmd.args.index("-i") + 1] == str(LIST)


def test_reencode_sets_codecs_and_crf():
    cmd = build_reencode("ffmpeg", LIST, OUT, crf=20)
    assert cmd.re_encoded
    assert cmd.args[cmd.args.index("-c:v") + 1] == "libx264"
    assert cmd.args[cmd.args.index("-c:a") + 1] == "aac"
    assert cmd.args[cmd.args.index("-crf") + 1] == "20"


def test_custom_ffmpeg_path_is_used():
    cmd = build_stream_copy("C:/tools/ffmpeg.exe", LIST, OUT)
    assert cmd.args[0] == "C:/tools/ffmpeg.exe"


def test_output_path_is_carried_on_the_command():
    cmd = build_reencode("ffmpeg", LIST, OUT)
    assert cmd.output_path == OUT
