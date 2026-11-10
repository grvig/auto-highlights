"""Tests for plans that span several demos."""

from dataclasses import replace
from pathlib import Path

from highlights.engine.demo_source import Player
from highlights.engine.moments import HighlightType
from highlights.engine.multi import Match, build_multi_plan, players_across

from tests.factories import make_context, make_kill


def player(steamid, name):
    return Player(steamid=steamid, name=name, starting_side="ct")


def match(label, players, kills, demo):
    ctx = replace(make_context(kills), demo_path=Path(demo))
    return Match(label=label, players=players, context=ctx)


def test_moments_are_pooled_across_matches():
    nuke = match("nuke", [player("ME", "semi")], [make_kill(1000, "ME", "x")], "nuke.dem")
    cache = match("cache", [player("ME", "semi")], [make_kill(2000, "ME", "y"), make_kill(9000, "ME", "z")], "cache.dem")

    result = build_multi_plan([nuke, cache], "ME", [HighlightType.KILL])

    assert len(result.plan) == 3
    assert [m.source_demo for m in result.plan.moments] == [
        Path("nuke.dem"), Path("cache.dem"), Path("cache.dem"),
    ]
    assert result.moments_per_match == {"nuke": 1, "cache": 2}


def test_player_found_by_steamid_despite_a_name_change():
    old = match("old", [player("ME", "semi")], [make_kill(1000, "ME", "x")], "a.dem")
    new = match("new", [player("ME", "renamed")], [make_kill(1000, "ME", "y")], "b.dem")
    assert len(build_multi_plan([old, new], "ME", [HighlightType.KILL]).plan) == 2


def test_matches_without_the_player_are_reported():
    mine = match("mine", [player("ME", "semi")], [make_kill(1000, "ME", "x")], "a.dem")
    other = match("other", [player("SOMEONE", "x")], [], "b.dem")
    result = build_multi_plan([mine, other], "ME", [HighlightType.KILL])
    assert result.missing_from == ["other"]
    assert len(result.plan) == 1


def test_players_across_counts_appearances_by_steamid():
    a = match("a", [player("ME", "semi"), player("B", "bob")], [], "a.dem")
    b = match("b", [player("ME", "semi2")], [], "b.dem")
    roster = players_across([a, b])
    assert roster[0][0].steamid == "ME" and roster[0][1] == 2
    assert roster[0][0].name == "semi2"  # the most recent name is shown
    assert ("B", 1) in [(p.steamid, n) for p, n in roster]
