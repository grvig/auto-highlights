"""Tests for the clip-plan builder."""

from highlights.engine.clip_plan import DETECTOR_REGISTRY, build_clip_plan
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill, make_round


def test_every_highlight_type_has_a_detector():
    for highlight_type in HighlightType:
        assert DETECTOR_REGISTRY.get(highlight_type), highlight_type


def test_builds_kills_only_when_selected():
    kills = [make_kill(1000, "P", "E1"), make_kill(2000, "P", "E2")]
    plan = build_clip_plan(make_context(kills), "P", [HighlightType.KILL])
    assert len(plan) == 2
    assert all(m.highlight_type is HighlightType.KILL for m in plan.moments)


def test_moments_are_chronological_across_types():
    # A death at 1500 between two kills should sort in the middle.
    kills = [
        make_kill(1000, "P", "E1"),
        make_kill(1500, "E2", "P"),  # P's death
        make_kill(2000, "P", "E3"),
    ]
    plan = build_clip_plan(
        make_context(kills), "P", [HighlightType.KILL, HighlightType.DEATH]
    )
    assert [m.core_tick for m in plan.moments] == [1000, 1500, 2000]


def test_unselected_types_are_excluded():
    kills = [make_kill(1500, "E2", "P")]  # only a death exists
    plan = build_clip_plan(make_context(kills), "P", [HighlightType.KILL])
    assert len(plan) == 0


def test_selected_types_are_deduped_preserving_order():
    plan = build_clip_plan(
        make_context([]), "P", [HighlightType.KILL, HighlightType.KILL]
    )
    assert plan.selected_types == (HighlightType.KILL,)


def test_total_seconds_sums_moment_durations():
    kills = [make_kill(10_000, "P", "E1")]
    plan = build_clip_plan(make_context(kills), "P", [HighlightType.KILL])
    # one padded kill: 3s pre + 2s post = 5s
    assert plan.total_seconds == 5.0


def test_counts_by_type_tallies_each_type():
    kills = [
        make_kill(1000, "P", "E1"),
        make_kill(2000, "P", "E2"),
        make_kill(3000, "E3", "P"),  # a death
    ]
    plan = build_clip_plan(
        make_context(kills), "P", [HighlightType.KILL, HighlightType.DEATH]
    )
    counts = plan.counts_by_type()
    assert counts[HighlightType.KILL] == 2
    assert counts[HighlightType.DEATH] == 1


def test_counts_by_type_omits_absent_types():
    kills = [make_kill(1000, "P", "E1")]
    plan = build_clip_plan(make_context(kills), "P", [HighlightType.KILL])
    assert plan.counts_by_type() == {HighlightType.KILL: 1}


def test_counts_by_type_empty_plan():
    plan = build_clip_plan(make_context([]), "P", [HighlightType.KILL])
    assert plan.counts_by_type() == {}
