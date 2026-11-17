"""Tests for the app API, with demos faked so nothing is parsed or launched."""

from dataclasses import replace
from pathlib import Path

import pytest

from highlights.app import api as api_module
from highlights.app.api import AppApi
from highlights.config import ClipConfig, Config, ConfigError
from highlights.engine.demo_source import DemoError, Player
from highlights.engine.multi import Match
from highlights.pipeline.planning import Matches

from tests.factories import make_context, make_kill, make_round


def fake_matches(paths, cache, timing):
    kills = [make_kill(1000, "P", "Q", headshot=True), make_kill(1060, "P", "R", headshot=True),
             make_kill(30_000, "P", "Q")]
    ctx = replace(make_context(kills, rounds=[make_round(1, 0, 100_000)]), demo_path=Path(paths[0]))
    players = [Player("P", "semi", "ct"), Player("Q", "ORYX", "t"), Player("R", "HUNTER", "t")]
    return Matches(sources=[], matches=[Match("nuke", players, ctx)])


@pytest.fixture
def app(tmp_path, monkeypatch):
    calls = []

    def loader(paths, cache, timing):
        calls.append(paths)
        return fake_matches(paths, cache, timing)

    monkeypatch.setattr(api_module, "load_matches", loader)
    monkeypatch.setattr(api_module, "match_summary", lambda loaded: [{"map": "de_nuke"}])
    config = Config(cs2_root=None, output_dir=tmp_path / "out", clips_dir=tmp_path / "clips",
                    clips=ClipConfig())
    instance = AppApi(config_loader=lambda: config, you=lambda: "P")
    instance.parse_calls = calls
    return instance


def test_analyze_lists_players_with_you_first(app):
    result = app.analyze(["D:/demos/nuke.dem"])
    assert result["matches"] == [{"map": "de_nuke"}]
    assert result["players"][0]["name"] == "semi" and result["players"][0]["you"]


def test_planning_reuses_the_parsed_demos(app):
    app.analyze(["D:/demos/nuke.dem"])
    plan = app.plan(["D:/demos/nuke.dem"], "P", {"all": True})
    assert plan["count"] >= 1 and plan["missing_from"] == []
    assert len(app.parse_calls) == 1


def test_bad_input_comes_back_as_an_error_not_an_exception(app, monkeypatch):
    assert app.analyze([]) == {"error": "Pick at least one demo."}
    assert "error" in app.plan(["D:/demos/nuke.dem"], "P", {"types": "headshots"})

    def broken(paths, cache, timing):
        raise DemoError("x.txt is not a .dem file")

    monkeypatch.setattr(api_module, "load_matches", broken)
    assert app.analyze(["x.txt"]) == {"error": "x.txt is not a .dem file"}


def test_works_without_any_config_file(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "load_matches", fake_matches)

    def no_config():
        raise ConfigError("No config")

    app = AppApi(config_loader=no_config, you=lambda: None)
    assert app.plan(["D:/demos/nuke.dem"], "P")["count"] >= 1
