"""Tests for choosing and ordering reel moments."""

from pathlib import Path

import pytest

from highlights.engine.moments import HighlightType, Moment
from highlights.engine.selection import arrange, select_best


def moment(score, seconds=5, htype=HighlightType.KILL, demo="a.dem", tick=0):
    return Moment(
        round_number=1,
        highlight_type=htype,
        player_steamid="P",
        core_tick=tick,
        start_tick=tick,
        end_tick=tick + int(seconds * 64),
        description=f"{htype}:{score}",
        source_demo=Path(demo),
        score=score,
    )


def test_picks_the_highest_scores_until_the_target_is_filled():
    moments = [moment(1), moment(9), moment(5), moment(7)]
    chosen = select_best(moments, target_seconds=10, variety=False)
    assert [m.score for m in chosen] == [9, 7]


def test_zero_score_moments_are_never_chosen():
    chosen = select_best([moment(0, htype=HighlightType.DEATH), moment(2)], 60)
    assert [m.score for m in chosen] == [2]


def test_too_long_moment_is_skipped_for_shorter_ones():
    moments = [moment(10, seconds=5), moment(9, seconds=30), moment(8, seconds=5)]
    chosen = select_best(moments, target_seconds=12, variety=False)
    assert [m.score for m in chosen] == [10, 8]


def test_first_pick_is_kept_even_if_longer_than_the_target():
    chosen = select_best([moment(10, seconds=30)], target_seconds=5)
    assert len(chosen) == 1


def test_variety_spreads_types_and_matches():
    moments = [
        moment(10, htype=HighlightType.KILL, demo="a.dem"),
        moment(9.5, htype=HighlightType.KILL, demo="a.dem"),
        moment(9, htype=HighlightType.CLUTCH, demo="b.dem"),
    ]
    chosen = select_best(moments, target_seconds=10)
    # second pick is the clutch from the other match, not another a.dem kill
    assert [m.highlight_type for m in chosen] == [HighlightType.KILL, HighlightType.CLUTCH]


def test_montage_opens_with_a_hook_and_ends_on_the_best():
    chosen = [moment(s) for s in (3, 9, 5, 7, 1)]
    ordered = arrange(chosen, chosen, "montage")
    assert [m.score for m in ordered] == [7, 1, 3, 5, 9]


def test_chronological_keeps_plan_order():
    plan = [moment(5, tick=100), moment(9, tick=200), moment(1, tick=300)]
    chosen = [plan[1], plan[0]]
    assert arrange(chosen, plan, "chronological") == [plan[0], plan[1]]


def test_unknown_order_is_rejected():
    with pytest.raises(ValueError, match="Unknown order"):
        arrange([], [], "random")
