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
