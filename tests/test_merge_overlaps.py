"""Tests for overlap dedup in the clip-plan builder."""

from highlights.engine.clip_plan import build_clip_plan, merge_overlaps
from highlights.engine.moments import HighlightType, Moment

from tests.factories import make_context, make_kill, make_round


def moment(htype, core, start, end):
    return Moment(
        round_number=1,
        highlight_type=htype,
        player_steamid="P",
        core_tick=core,
        start_tick=start,
        end_tick=end,
        description="x",
    )


def test_kill_absorbed_by_overlapping_multikill():
    kill = moment(HighlightType.KILL, 1000, 900, 1100)
    multi = moment(HighlightType.MULTI_KILL, 1000, 800, 1400)
    kept = merge_overlaps([kill, multi])
    assert kept == [multi]


def test_kill_not_absorbed_when_no_overlap():
    kill = moment(HighlightType.KILL, 5000, 4900, 5100)
    multi = moment(HighlightType.MULTI_KILL, 1000, 800, 1400)
    kept = merge_overlaps([multi, kill])
    assert set(kept) == {multi, kill}


def test_death_overlapping_kill_is_kept():
    kill = moment(HighlightType.KILL, 1000, 900, 1100)
    death = moment(HighlightType.DEATH, 1050, 950, 1150)
    kept = merge_overlaps([kill, death])
    assert set(kept) == {kill, death}


def test_builder_dedupes_kills_inside_a_multikill():
    # Three kills in one round -> one multikill; selecting both types should
    # not double-record the frags.
    kills = [make_kill(1000, "P", "a"), make_kill(1200, "P", "b"), make_kill(1400, "P", "c")]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.KILL, HighlightType.MULTI_KILL])
    types = [m.highlight_type for m in plan.moments]
    assert types == [HighlightType.MULTI_KILL]


def test_merge_can_be_disabled():
    kills = [make_kill(1000, "P", "a"), make_kill(1200, "P", "b"), make_kill(1400, "P", "c")]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(
        ctx, "P", [HighlightType.KILL, HighlightType.MULTI_KILL], merge=False
    )
    assert len(plan) == 4  # 3 kills + 1 multikill


def test_overlapping_single_kills_become_one_moment():
    first = moment(HighlightType.KILL, 1000, 900, 1100)
    second = moment(HighlightType.KILL, 1060, 960, 1160)
    kept = merge_overlaps([first, second])
    assert len(kept) == 1
    assert (kept[0].start_tick, kept[0].end_tick, kept[0].core_tick) == (900, 1160, 1060)
    assert kept[0].description == "x + x"


def test_separate_single_kills_stay_apart():
    first = moment(HighlightType.KILL, 1000, 900, 1100)
    later = moment(HighlightType.KILL, 5000, 4900, 5100)
    assert len(merge_overlaps([first, later])) == 2


def test_kills_in_different_rounds_are_never_joined():
    from dataclasses import replace

    first = moment(HighlightType.KILL, 1000, 900, 1100)
    other_round = replace(moment(HighlightType.KILL, 1050, 950, 1150), round_number=2)
    assert len(merge_overlaps([first, other_round])) == 2


def test_double_kill_is_one_clip_in_a_built_plan():
    kills = [make_kill(1000, "P", "a"), make_kill(1058, "P", "b")]  # 0.9s apart
    plan = build_clip_plan(make_context(kills), "P", [HighlightType.KILL])
    assert len(plan) == 1
    assert "vic-a" in plan.moments[0].description and "vic-b" in plan.moments[0].description
