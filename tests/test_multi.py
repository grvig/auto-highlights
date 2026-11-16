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


def test_victim_cams_can_be_left_out_of_a_multi_plan():
    kills = [make_kill(1000, "ME", "a"), make_kill(1050, "ME", "b")]
    nuke = match("nuke", [player("ME", "semi")], kills, "nuke.dem")
    with_cams = build_multi_plan([nuke], "ME", [HighlightType.KILL])
    without = build_multi_plan([nuke], "ME", [HighlightType.KILL], replays=False)
    assert any(m.replays for m in with_cams.plan.moments)
    assert not any(m.replays for m in without.plan.moments)


def test_clip_timing_from_config_reaches_the_planner():
    from highlights.config import ClipConfig
    from highlights.engine.multi import match_from_source

    class Source:
        path = Path("nuke.dem")
        tickrate = 64

        class info:
            map_name = "de_nuke"

        def players(self):
            return []

        def round_list(self):
            return []

        def kill_list(self):
            return []

        def tick_bounds(self):
            return 0, 100_000

        def round_rosters(self):
            return {}

        def blind_list(self):
            return []

        def damage_list(self):
            return []

        def smoke_list(self):
            return []

    ctx = match_from_source(Source(), ClipConfig(6.0, 2.5, merge_gap_seconds=8.0)).context
    assert (ctx.pre_roll_seconds, ctx.post_roll_seconds, ctx.merge_gap_seconds) == (6.0, 2.5, 8.0)


def test_a_wider_merge_gap_keeps_a_fight_in_one_clip():
    from highlights.engine.moments import build_segments

    kills = [1000, 1000 + 64 * 8]  # eight seconds apart: three dead seconds between windows
    tight = build_segments(kills, 3.0, 2.0, first_tick=0, last_tick=100_000)
    wide = build_segments(kills, 3.0, 2.0, first_tick=0, last_tick=100_000, merge_gap_seconds=8.0)
    assert len(tight) == 2
    assert len(wide) == 1 and (wide[0].start_tick, wide[0].end_tick) == (808, 1640)
