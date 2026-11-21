"""Tests for the window's views of matches, players and plans."""

import json
from dataclasses import replace
from pathlib import Path

from highlights.app.serialize import plan_view, player_table
from highlights.engine.demo_source import Player
from highlights.engine.moments import HighlightType
from highlights.engine.multi import Match
from highlights.pipeline.planning import Matches, PlanOptions, plan_reel

from tests.factories import make_context, make_kill, make_round


def loaded():
    kills = [make_kill(1000, "P", "Q", headshot=True), make_kill(3000, "Q", "P"),
             make_kill(20_000, "P", "R")]
    ctx = replace(make_context(kills, rounds=[make_round(1, 0, 100_000)]), demo_path=Path("nuke.dem"))
    players = [Player("P", "semi", "ct"), Player("Q", "ORYX", "t"), Player("R", "HUNTER", "t")]
    return Matches(sources=[], matches=[Match("nuke", players, ctx)])


def test_players_are_counted_and_you_come_first():
    table = player_table(loaded(), you="Q")
    assert [r["name"] for r in table] == ["ORYX", "semi", "HUNTER"]
    semi = table[1]
    assert (semi["kills"], semi["deaths"], semi["matches"], semi["you"]) == (2, 1, 1, False)


def test_a_plan_view_is_plain_json():
    plan = plan_reel(loaded(), "P", PlanOptions(types=(HighlightType.KILL,), min_score=0)).plan
    view = plan_view(plan)
    assert view["count"] == 2 and view["moments"][0]["number"] == 1
    assert view["moments"][0]["demo"] == "nuke.dem"
    json.dumps(view)  # must not raise


def test_plays_name_their_match_by_map_and_day(tmp_path):
    import os
    from datetime import datetime
    from types import SimpleNamespace

    from highlights.app.serialize import match_label

    demo = tmp_path / "match730_1.dem"
    demo.write_bytes(b"d")
    stamp = datetime(2026, 7, 1, 18, 35).timestamp()
    os.utime(demo, (stamp, stamp))
    source = SimpleNamespace(path=demo, info=SimpleNamespace(map_name="de_cache"))
    assert match_label(source) == "Cache 1 Jul"
