"""Tests for opening clips at the start of the fight."""

from highlights.engine.clip_plan import build_clip_plan
from highlights.engine.fights import fight_start
from highlights.engine.models import Shot
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill, make_round


def test_an_exchange_already_under_way_is_included():
    # shots every second from tick 600 up to the planned start at 1000
    ticks = [600, 664, 728, 792, 856, 920, 984]
    assert fight_start(1000, ticks, floor=0) == 600 - 96  # 1.5s before the first shot


def test_a_quiet_lead_in_is_left_alone():
    assert fight_start(1000, [100, 200], floor=0) == 1000


def test_the_reach_back_is_capped_and_respects_the_floor():
    ticks = list(range(0, 1000, 64))  # shooting the whole time
    assert fight_start(1000, ticks, floor=0) == 1000 - 512  # at most 8s
    assert fight_start(1000, ticks, floor=900) == 900


def test_plans_open_at_the_fight_not_the_fixed_lead():
    kills = [make_kill(5000, "P", "a")]
    shots = [Shot(t, "P", "ak47") for t in (4500, 4600, 4700, 4790, 4990)]  # one exchange
    ctx = make_context(kills, rounds=[make_round(1, 0, 100_000)], shots=shots)
    moment = build_clip_plan(ctx, "P", [HighlightType.KILL]).moments[0]
    planned_start = 5000 - ctx.pre_roll_seconds * 64
    assert moment.windows[0].start_tick < planned_start
    assert moment.windows[0].start_tick == 4500 - 96


def test_a_fight_that_carries_on_after_the_last_kill_is_followed():
    from highlights.engine.fights import fight_end

    ticks = [1050, 1100, 1180]  # still shooting after the planned end at 1000
    assert fight_end(1000, ticks, ceiling=100_000) == 1180 + 64


def test_the_tail_is_capped_and_stops_at_the_ceiling():
    from highlights.engine.fights import fight_end

    ticks = list(range(1010, 2000, 64))
    assert fight_end(1000, ticks, ceiling=100_000) == 1000 + 256
    assert fight_end(1000, ticks, ceiling=1100) == 1100
    assert fight_end(1000, [1500], ceiling=100_000) == 1000  # a later, separate fight
