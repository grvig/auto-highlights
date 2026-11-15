"""Tests for HLAE stream commands and take finishing."""

from pathlib import Path

import pytest

from highlights.recorder import mirv


def test_start_pins_the_framerate_and_pipes_to_ffmpeg():
    commands = mirv.start_commands(Path("D:/clips/take_001"), 1, framerate=60)
    assert commands[0] == "host_framerate 60"
    assert commands[-1] == "mirv_streams record start"
    preset = next(c for c in commands if c.startswith("mirv_streams settings add ffmpeg"))
    assert "-c:v libx264" in preset
    assert "{QUOTE}" in preset and "video.mp4{QUOTE}" in preset
    assert "mirv_streams record startMovieWav 1" in commands


def test_backslashes_are_doubled_for_hlae():
    commands = mirv.start_commands(Path("D:\\clips\\take"))
    preset = next(c for c in commands if "settings add" in c)
    if "\\" in str(Path("D:\\clips\\take")):  # only meaningful on Windows paths
        assert "clips\\\\take" in preset


def test_stop_hands_the_framerate_back():
    commands = mirv.stop_commands()
    assert commands[0] == "mirv_streams record end"
    assert commands[-1] == "host_framerate 0"


def test_finish_trims_both_streams_identically():
    args = mirv.finish_command(Path("take"), Path("out.mp4"), 0.5, 5.0)
    assert args.count("-ss") == 2 and args.count("-t") == 2
    assert args[args.index("-ss") + 1] == "0.500"
    assert args[-1] == "out.mp4"
    assert "atempo" not in " ".join(args) and "concat" not in " ".join(args)


def test_finish_slows_picture_and_sound_together():
    args = mirv.finish_command(Path("take"), Path("out.mp4"), 0.5, 5.0, speed=0.5)
    graph = args[args.index("-filter_complex") + 1]
    assert "setpts=PTS/0.5" in graph and "atempo=0.5" in graph


def test_very_slow_motion_chains_atempo_stages():
    assert mirv.atempo_chain(0.25) == "atempo=0.5,atempo=0.5"
    assert mirv.atempo_chain(0.3) == "atempo=0.5,atempo=0.6"


def test_finish_rejects_zero_speed():
    with pytest.raises(ValueError):
        mirv.finish_command(Path("t"), Path("o.mp4"), 0, 1, speed=0)


def test_every_take_gets_its_own_preset():
    first = mirv.start_commands(Path("t1"), take_number=1)
    second = mirv.start_commands(Path("t2"), take_number=2)
    assert "mirv_streams record screen settings ahtake1" in first
    assert "mirv_streams record screen settings ahtake2" in second
    assert not any("settings remove" in c for c in mirv.stop_commands())


def test_pieces_cover_the_clip_with_ramps_in_between():
    assert mirv.speed_pieces(5.0, ((2.0, 2.5),), 1.0, 0.4) == [
        (0.0, 2.0, 1.0), (2.0, 2.5, 0.4), (2.5, 5.0, 1.0)]
    assert mirv.speed_pieces(5.0) == [(0.0, 5.0, 1.0)]
    assert mirv.speed_pieces(5.0, ((0.0, 0.5),), 1.0, 0.5) == [(0.0, 0.5, 0.5), (0.5, 5.0, 1.0)]


def test_ramped_finish_joins_the_stretches_in_one_shot():
    args = mirv.finish_command(Path("take"), Path("out.mp4"), 0.5, 5.0,
                               ramps=((2.0, 2.5),), ramp_speed=0.4)
    graph = args[args.index("-filter_complex") + 1]
    assert "split=3" in graph and "asplit=3" in graph
    assert "trim=start=2:end=2.5,setpts=(PTS-STARTPTS)/0.4" in graph
    assert "atempo=0.5,atempo=0.8" in graph
    assert "concat=n=3:v=1:a=1[vc][a]" in graph and graph.endswith("[vc]fps=60[v]")
