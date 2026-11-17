"""Tests for planning a reel from loaded matches."""

from dataclasses import replace
from pathlib import Path

from highlights.engine.moments import HighlightType
from highlights.engine.multi import Match
from highlights.engine.demo_source import Player
from highlights.pipeline.planning import Matches, PlanOptions, kills_in_plan, plan_reel

from tests.factories import make_context, make_kill, make_round


def loaded_with(kills, demo="nuke.dem", roster=("P",)):
    ctx = replace(make_context(kills, rounds=[make_round(1, 0, 100_000)]), demo_path=Path(demo))
    match = Match(label="nuke", players=[Player(sid, sid, "ct") for sid in roster], context=ctx)
    return Matches(sources=[], matches=[match])


def test_every_play_is_kept_without_a_length():
    kills = [make_kill(1000, "P", "a"), make_kill(20_000, "P", "b")]
    reel = plan_reel(loaded_with(kills), "P", PlanOptions(types=(HighlightType.KILL,), min_score=0))
    assert len(reel.plan.moments) == 2


def test_a_length_keeps_only_the_best_plays():
    kills = [make_kill(1000, "P", "a", headshot=True), make_kill(20_000, "P", "b")]
    options = PlanOptions(types=(HighlightType.KILL,), best_seconds=1, min_score=0)
    assert len(plan_reel(loaded_with(kills), "P", options).plan.moments) == 1


def test_kills_are_counted_across_the_plan():
    kills = [make_kill(1000, "P", "a"), make_kill(1100, "P", "b"), make_kill(20_000, "P", "c")]
    loaded = loaded_with(kills)
    plan = plan_reel(loaded, "P", PlanOptions(types=(HighlightType.KILL,))).plan
    assert kills_in_plan(plan, loaded) == 3


def test_players_missing_from_a_demo_are_reported():
    reel = plan_reel(loaded_with([make_kill(1000, "Q", "a")], roster=("Q",)), "P")
    assert reel.missing_from == ["nuke"]
