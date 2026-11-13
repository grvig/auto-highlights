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


def test_later_victim_cams_do_not_replay_the_earlier_kill():
    # Cache R1: two kills 57 ticks (0.9s) apart. The second victim's camera
    # used to start 2.5s back and show the first kill all over again.
    kills = [make_kill(2594, "P", "A"), make_kill(2651, "P", "B")]
    first, second = victim_replays(multi(1_000, 3_000), kills)
    assert first.start_tick == 2594 - 160
    assert second.start_tick > 2594
    assert second.start_tick <= 2651 < second.end_tick


def test_every_victim_cam_still_contains_its_own_death():
    ticks = (10_000, 10_004, 10_010)
    kills = [make_kill(t, "P", v) for t, v in zip(ticks, "ABC")]
    replays = victim_replays(multi(9_000, 11_000), kills)
    assert all(r.start_tick <= t < r.end_tick for r, t in zip(replays, ticks))


def test_short_victim_cams_play_in_slow_motion():
    from highlights.engine.replays import replay_speed

    assert replay_speed(2.9) == 1.0
    assert replay_speed(0.6) == 0.5
    assert replay_speed(0.1) == 0.4  # capped, not a slideshow


def test_cache_double_kill_second_cam_is_slowed_to_read():
    kills = [make_kill(2594, "P", "A"), make_kill(2651, "P", "B")]
    first, second = victim_replays(multi(1_000, 3_000), kills)
    assert first.speed == 1.0
    assert second.speed < 1.0
    assert second.duration_seconds >= 1.1
