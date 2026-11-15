"""Tests for YouTube chapter timestamps."""

from highlights.editor.chapters import chapter_lines, starts, timestamp


def test_timestamps_switch_to_hours_only_when_needed():
    assert timestamp(0) == "00:00"
    assert timestamp(75.9) == "01:15"
    assert timestamp(3725) == "1:02:05"


def test_crossfades_pull_each_start_earlier():
    assert starts([2.5, 5.0, 5.0], 0.35) == [0.0, 2.15, 6.8]


def test_first_chapter_always_starts_at_zero():
    lines = chapter_lines([(0.4, "Intro"), (2.15, "ACE (Round 5)")])
    assert lines == ["00:00 Intro", "00:02 ACE (Round 5)"]
