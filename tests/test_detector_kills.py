"""Tests for the single-kill detector."""

from highlights.engine.detectors.kills import SingleKillDetector, describe_kill
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill


def test_one_moment_per_player_kill():
    kills = [
        make_kill(1000, "A", "x"),
        make_kill(2000, "A", "y"),
        make_kill(1500, "B", "z"),  # someone else's kill
    ]
    moments = SingleKillDetector().detect(make_context(kills), "A")
    assert len(moments) == 2
    assert all(m.highlight_type is HighlightType.KILL for m in moments)
    assert all(m.player_steamid == "A" for m in moments)


def test_moments_are_tick_ordered():
    kills = [make_kill(3000, "A", "x"), make_kill(1000, "A", "y")]
    moments = SingleKillDetector().detect(make_context(kills), "A")
    assert [m.core_tick for m in moments] == [1000, 3000]


def test_no_kills_yields_no_moments():
    assert SingleKillDetector().detect(make_context([]), "A") == []


def test_moment_window_is_padded():
    kills = [make_kill(10_000, "A", "x")]
    moment = SingleKillDetector().detect(make_context(kills), "A")[0]
    assert moment.start_tick == 10_000 - 3 * 64
    assert moment.end_tick == 10_000 + 2 * 64


def test_describe_kill_marks_headshot():
    hs = make_kill(1, "A", "x", weapon="awp", headshot=True)
    normal = make_kill(1, "A", "y", weapon="ak47")
    assert "headshot" in describe_kill(hs)
    assert "awp" in describe_kill(hs)
    assert "headshot" not in describe_kill(normal)
