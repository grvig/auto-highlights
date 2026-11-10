"""Tests for broadcast-style victim-cam replays."""

from highlights.engine.clip_plan import build_clip_plan
from highlights.engine.moments import HighlightType, Moment
from highlights.engine.replays import VICTIM_CAM_TAG, victim_replays

from tests.factories import make_context, make_kill, make_round


def multi(start, end, htype=HighlightType.MULTI_KILL):
    return Moment(
        round_number=1,
        highlight_type=htype,
        player_steamid="P",
        core_tick=end,
        start_tick=start,
        end_tick=end,
        description="x",
    )


def test_fast_triple_gets_one_replay_per_victim():
    kills = [make_kill(t, "P", v) for t, v in ((10_000, "A"), (10_064, "B"), (10_128, "C"))]
    replays = victim_replays(multi(9_000, 11_000), kills)
    assert [r.pov_steamid for r in replays] == ["A", "B", "C"]
    first = replays[0]
    assert (first.start_tick, first.end_tick) == (10_000 - 160, 10_000 + 26)


def test_spread_out_kills_get_no_replays():
    kills = [make_kill(t, "P", v) for t, v in ((10_000, "A"), (10_000 + 30 * 64, "B"))]
    assert victim_replays(multi(9_000, 13_000), kills) == ()


def test_a_single_kill_gets_no_replay():
    assert victim_replays(multi(9_000, 11_000), [make_kill(10_000, "P", "A")]) == ()


def test_deaths_never_get_victim_cams():
    kills = [make_kill(10_000, "P", "A"), make_kill(10_064, "P", "B")]
    assert victim_replays(multi(9_000, 11_000, HighlightType.DEATH), kills) == ()


def test_replays_are_clamped_to_the_moment_window():
    kills = [make_kill(10_000, "P", "A"), make_kill(10_064, "P", "B")]
    replays = victim_replays(multi(9_950, 10_070), kills)
    assert all(9_950 <= r.start_tick and r.end_tick <= 10_070 for r in replays)


def test_built_plan_adds_victim_cams_to_a_quick_multikill():
    kills = [make_kill(10_000 + i * 64, "P", f"E{i}") for i in range(3)]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.MULTI_KILL])
    triple = plan.moments[0]
    assert len(triple.replays) == 3
    assert VICTIM_CAM_TAG in triple.tags
    assert triple.duration_seconds > sum(w.duration_seconds for w in triple.windows)


def test_victim_cams_can_be_turned_off():
    kills = [make_kill(10_000 + i * 64, "P", f"E{i}") for i in range(3)]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.MULTI_KILL], replays=False)
    assert plan.moments[0].replays == ()
