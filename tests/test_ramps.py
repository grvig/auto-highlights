"""Tests for slow-motion ramps around kills."""

from highlights.engine.clip_plan import build_clip_plan
from highlights.engine.moments import HighlightType, Segment
from highlights.engine.ramps import SLOWMO_TAG, kill_ramps

from tests.factories import make_context, make_kill, make_round


def test_each_kill_gets_a_short_span():
    spans = kill_ramps(Segment(0, 2000), [1000])
    assert spans == ((1000 - 10, 1000 + 22),)


def test_kills_close_together_share_one_ramp():
    assert kill_ramps(Segment(0, 2000), [1000, 1020]) == ((990, 1042),)


def test_ramps_stay_inside_the_segment():
    assert kill_ramps(Segment(995, 1010), [1000]) == ((995, 1010),)
    assert kill_ramps(Segment(0, 500), [1000]) == ()


def test_plan_ramps_the_players_kills_when_asked():
    kills = [make_kill(1000, "P", "a"), make_kill(1200, "P", "b"), make_kill(1400, "P", "c")]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.MULTI_KILL], replays=False, slowmo=True)
    moment = plan.moments[0]
    assert SLOWMO_TAG in moment.tags
    ramped = [span for window in moment.windows for span in window.ramps]
    assert len(ramped) == 3


def test_plans_have_no_ramps_by_default():
    kills = [make_kill(1000, "P", "a"), make_kill(1200, "P", "b")]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.MULTI_KILL])
    assert all(not w.ramps for m in plan.moments for w in m.playlist)


def test_victim_cams_are_never_ramped():
    kills = [make_kill(1000, "P", "a"), make_kill(1060, "P", "b")]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.KILL], slowmo=True)
    assert all(not r.ramps for m in plan.moments for r in m.replays)


def test_windows_know_where_the_kills_and_headshots_are():
    kills = [make_kill(1000, "P", "a", headshot=True), make_kill(1200, "P", "b"),
             make_kill(1400, "P", "c")]
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)])
    plan = build_clip_plan(ctx, "P", [HighlightType.MULTI_KILL], replays=False)
    windows = plan.moments[0].windows
    assert sorted(t for w in windows for t in w.kill_ticks) == [1000, 1200, 1400]
    assert [t for w in windows for t in w.headshot_ticks] == [1000]
