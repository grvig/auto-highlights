"""Tests for crossfade joins."""

from pathlib import Path

from highlights.editor.transitions import join_command, join_filter, offsets, transition_seconds


def test_crossfades_start_one_overlap_earlier_per_join():
    assert offsets([5.0, 4.0, 6.0], 0.5) == [4.5, 8.0]


def test_transition_is_shortened_for_short_clips():
    assert transition_seconds([5.0, 0.6]) == 0.18
    assert transition_seconds([5.0, 5.0]) == 0.35
    assert transition_seconds([5.0]) == 0.0


def test_graph_normalises_every_input_and_chains_fades():
    graph, video, audio = join_filter([5.0, 4.0, 6.0], 1440, 1080)
    assert graph.count("fps=60,scale=1440:1080") == 3
    assert "xfade=transition=fade:duration=0.35:offset=4.65[vx1]" in graph
    assert "[vx1][v2]xfade" in graph
    assert graph.count("acrossfade=d=0.35") == 2
    assert (video, audio) == ("vx2", "ax2")


def test_single_clip_passes_straight_through():
    graph, video, audio = join_filter([5.0], 1440, 1080)
    assert "xfade" not in graph and (video, audio) == ("v0", "a0")


def test_command_maps_the_final_labels():
    args = join_command([Path("a.mp4"), Path("b.mp4")], [5.0, 5.0], Path("out.mp4"), 1440, 1080)
    assert args.count("-i") == 2
    assert args[args.index("-map") + 1] == "[vx1]"
    assert args[-1] == "out.mp4"
