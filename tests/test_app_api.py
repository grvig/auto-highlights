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


def test_render_runs_in_the_background_and_reports_the_reel(app, monkeypatch):
    from highlights.pipeline.production import ReelResult
    from highlights.progress import Progress

    def record(requests, config, live, resume, progress, cancel):
        progress(Progress("record", 1, 2, "Recording #001"))
        return [type("Clip", (), {"succeeded": True})() for _ in requests]

    def produce(clips, player, config, aspect, edit, progress, cancel):
        progress(Progress("export", 0, 1, "Exporting"))
        return ReelResult(Path("D:/out/semi_highlights.mp4"), "stretched")

    monkeypatch.setattr(api_module, "record_clips", record)
    monkeypatch.setattr(api_module, "produce_reel", produce)
    app.plan(["D:/demos/nuke.dem"], "P", {"all": True})
    job = app.render(["D:/demos/nuke.dem"], "P")["job"]
    status = app.jobs.wait(job, timeout=10)
    assert status["state"] == "done", status
    assert status["result"]["video"].endswith("semi_highlights.mp4")
    assert status["result"]["failed"] == 0


def test_overall_progress_spans_the_stages():
    from highlights.app.api import overall
    from highlights.progress import Progress

    seen = []
    forward = overall(seen.append)
    forward(Progress("record", 1, 2))
    forward(Progress("edit", 1, 1))
    forward(Progress("export", 1, 1))
    assert [round(e.fraction, 2) for e in seen] == [0.4, 0.95, 1.0]


def test_render_needs_plays_to_record(app, monkeypatch):
    monkeypatch.setattr(api_module, "load_matches", lambda p, c, t: fake_matches(p, c, t))
    assert "error" in app.render(["D:/demos/nuke.dem"], "NOBODY")


def test_plain_is_the_default_edit():
    from highlights.app.api import _edit_options

    loaded = fake_matches(["D:/demos/nuke.dem"], None, None)
    edit = _edit_options({}, "semi", loaded)
    assert (edit.captions, edit.cards, edit.transition, edit.music) == (False, False, "cut", None)
    assert _edit_options({"plain": True}, "semi", loaded) is None


def test_settings_are_shown_and_saved_through_the_config_file(tmp_path):
    from highlights.config import load_config

    path = tmp_path / "config.toml"
    path.write_text('[paths]\noutput_dir = "D:/out"\n', encoding="utf-8")
    app = AppApi(config_loader=lambda: load_config(path, locate_cs2=lambda: None),
                 you=lambda: None, config_path=path)
    assert app.settings()["transition"] == "cut"
    saved = app.save_settings({"editing.transition": "fade", "editing.target_seconds": 90})
    assert (saved["transition"], saved["target_seconds"]) == ("fade", 90.0)
    assert "error" in app.save_settings({"recording.hud": "minimal"})  # fails validation
    assert "minimal" not in path.read_text(encoding="utf-8")  # and is rolled back
    assert app.settings()["transition"] == "fade"
    assert "error" in app.save_settings({"paths.cs2_root": "C:/"})  # not editable here


def test_settings_say_when_nothing_is_set_up_yet(tmp_path):
    def no_config():
        raise ConfigError("No config")

    assert AppApi(config_loader=no_config, you=lambda: None).settings() == {"configured": False}


def test_show_in_folder_only_opens_reels_in_the_output_folder(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    reel = out / "semi_highlights_2026-11-17_1015.mp4"
    reel.write_bytes(b"x")
    elsewhere = tmp_path / "secret.txt"
    elsewhere.write_text("x")
    opened = []
    config = Config(cs2_root=None, output_dir=out, clips_dir=tmp_path / "clips", clips=ClipConfig())
    app = AppApi(config_loader=lambda: config, you=lambda: None, opener=opened.append)
    assert app.show_in_folder(str(reel))["shown"] == str(reel.resolve())
    assert opened == [["explorer", f"/select,{reel.resolve()}"]]
    assert "error" in app.show_in_folder(str(elsewhere))
    assert "error" in app.show_in_folder(str(out / ".." / "secret.txt"))
    assert len(opened) == 1


def test_play_opens_only_reels_in_the_default_player(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    reel = out / "semi_highlights_2026-11-17_1015.mp4"
    reel.write_bytes(b"x")
    (out / "run.bat").write_text("x")
    opened = []
    config = Config(cs2_root=None, output_dir=out, clips_dir=tmp_path / "clips", clips=ClipConfig())
    app = AppApi(config_loader=lambda: config, you=lambda: None, opener=opened.append)
    assert app.play(str(reel)) == {"playing": str(reel.resolve())}
    assert opened == [["explorer", str(reel.resolve())]]
    assert "error" in app.play(str(out / "run.bat"))  # never anything that could run
    assert len(opened) == 1


def test_thumbnails_come_back_as_data_urls_for_reels_only(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "semi_highlights_2026-11-17_1015.thumbnail.png").write_bytes(b"PNG")
    (out / "notes.txt").write_text("x")
    (tmp_path / "other.png").write_bytes(b"PNG")
    config = Config(cs2_root=None, output_dir=out, clips_dir=tmp_path / "clips", clips=ClipConfig())
    app = AppApi(config_loader=lambda: config, you=lambda: None)
    answer = app.thumbnail(str(out / "semi_highlights_2026-11-17_1015.thumbnail.png"))
    assert answer == {"url": "data:image/png;base64,UE5H"}
    assert "error" in app.thumbnail(str(out / "notes.txt"))
    assert "error" in app.thumbnail(str(tmp_path / "other.png"))


def test_readiness_comes_back_as_data(tmp_path, monkeypatch):
    from highlights.preflight import Check

    monkeypatch.setattr(api_module, "run_preflight", lambda config: [
        Check("ffmpeg", True, "ffmpeg"), Check("HLAE", True, "v2.193.0 - older", warning=True)])
    config = Config(cs2_root=None, output_dir=tmp_path / "out", clips_dir=tmp_path / "clips", clips=ClipConfig())
    status = AppApi(config_loader=lambda: config, you=lambda: None).check()
    assert status["ready"] and status["warnings"] == 1
    assert status["checks"][1] == {"name": "HLAE", "state": "WARN", "detail": "v2.193.0 - older"}
