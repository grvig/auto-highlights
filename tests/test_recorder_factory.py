"""Tests for picking the live recorder and guarding CS2 settings."""

from contextlib import nullcontext

import pytest

from highlights.config import ClipConfig, Config, RecordingConfig
from highlights.recorder import factory
from highlights.recorder.cfg_guard import CfgGuard
from highlights.recorder.hlae_backend import HlaeRecorder
from highlights.recorder.hlae_release import VERSION_FILE
from highlights.recorder.window_backend import WindowRecorder


def make_config(tmp_path, recorder="hlae", hlae=True):
    cs2 = tmp_path / "cs2"
    exe = cs2 / "game" / "bin" / "win64" / "cs2.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    hlae_dir = tmp_path / "hlae"
    if hlae:
        hlae_dir.mkdir()
        (hlae_dir / "HLAE.exe").write_text("")
    return Config(
        cs2_root=cs2,
        output_dir=tmp_path / "out",
        clips_dir=tmp_path / "media" / "clips",
        clips=ClipConfig(3.0, 2.0),
        recording=RecordingConfig(recorder=recorder, hlae_path=hlae_dir),
    )


@pytest.fixture(autouse=True)
def fake_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(factory, "resolve_ffmpeg", lambda name: tmp_path / "ffmpeg.exe")
    monkeypatch.setattr("highlights.recorder.hlae.BUNDLED_DIR", tmp_path / "no-bundle")
    monkeypatch.setattr(factory, "ensure_current", lambda d: ("2.193.0", False))
    monkeypatch.setattr(factory, "find_steam_root", lambda: None)  # never the real PC


def test_hlae_is_used_when_installed(tmp_path):
    recorder = factory.build_live_recorder(make_config(tmp_path))
    assert type(recorder) is HlaeRecorder
    assert recorder.launch_args[0].endswith("HLAE.exe")
    assert "-width 1440 -height 1080" in recorder.launch_args[-1]
    assert (tmp_path / "hlae" / "ffmpeg" / "ffmpeg.ini").is_file()


def test_missing_hlae_falls_back_to_window_capture(tmp_path):
    recorder = factory.build_live_recorder(make_config(tmp_path, hlae=False))
    assert isinstance(recorder, WindowRecorder)
    assert recorder.launch_args is None


def test_window_capture_can_be_chosen(tmp_path):
    assert isinstance(factory.build_live_recorder(make_config(tmp_path, "window")), WindowRecorder)


def test_settings_guard_targets_the_signed_in_account(tmp_path):
    steam = tmp_path / "steam"
    (steam / "config").mkdir(parents=True)
    (steam / "config" / "loginusers.vdf").write_text(
        '"users" { "76561199266315708" { "PersonaName" "semi" "MostRecent" "1" } }'
    )
    guard = factory.settings_guard(make_config(tmp_path), steam_root=steam)
    assert isinstance(guard, CfgGuard)
    assert guard.cfg_dir.as_posix().endswith("userdata/1306049980/730/local/cfg")
    assert guard.backup_root == tmp_path / "media" / "backup"


def test_settings_guard_is_a_no_op_without_steam(tmp_path):
    guard = factory.settings_guard(make_config(tmp_path), steam_root=tmp_path / "nope")
    assert isinstance(guard, type(nullcontext()))


def test_recording_updates_hlae_first(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(factory, "ensure_current", lambda d: seen.append(d) or ("2.193.0", False))
    factory.build_live_recorder(make_config(tmp_path))
    assert seen == [tmp_path / "hlae"]


def test_an_offline_update_check_does_not_block_recording(tmp_path, monkeypatch):
    from highlights.recorder.hlae_release import ReleaseError

    def offline(d):
        raise ReleaseError("Could not check")
    monkeypatch.setattr(factory, "ensure_current", offline)
    assert factory.update_hlae(tmp_path) is None
    assert factory.build_live_recorder(make_config(tmp_path)) is not None


def test_recorder_restores_the_signed_in_players_settings(tmp_path):
    steam = tmp_path / "steam"
    (steam / "config").mkdir(parents=True)
    (steam / "config" / "loginusers.vdf").write_text(
        '"users" { "76561199266315708" { "PersonaName" "semi" "MostRecent" "1" } }'
    )
    cfg = steam / "userdata" / "1306049980" / "730" / "local" / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "cs2_user_convars_0_slot0.vcfg").write_text('\t\t"hud_showtargetid"\t\t"true"\n')
    recorder = factory.build_live_recorder(make_config(tmp_path), steam_root=steam)
    assert "hud_showtargetid 1" in recorder.restore_commands


def test_recordings_use_the_clean_hud_unless_config_asks_for_full(tmp_path):
    from dataclasses import replace

    config = make_config(tmp_path)
    assert not factory.build_live_recorder(config).cs2.full_hud
    full = replace(config, recording=replace(config.recording, hud="full"))
    assert factory.build_live_recorder(full).cs2.full_hud


def test_window_capture_records_from_the_configured_sound_device(tmp_path):
    from dataclasses import replace

    config = make_config(tmp_path, "window")
    with_sound = replace(config, recording=replace(config.recording, audio_device="virtual-audio-capturer"))
    assert factory.build_live_recorder(with_sound).audio_device == "virtual-audio-capturer"
    assert factory.build_live_recorder(config).audio_device is None


def test_window_mode_starts_cs2_through_steam_when_it_is_not_running(tmp_path, monkeypatch):
    steam = tmp_path / "steam"
    steam.mkdir()
    (steam / "steam.exe").write_bytes(b"exe")
    monkeypatch.setattr(factory.Cs2Controller, "game_running", lambda self: False)
    recorder = factory.build_live_recorder(make_config(tmp_path, "window"), steam_root=steam)
    assert recorder.launch_args[:3] == [str(steam / "steam.exe"), "-applaunch", "730"]
    assert "-netconport" in recorder.launch_args and "1440" in recorder.launch_args
    assert recorder.cs2.terminate_launcher is False  # never kill the Steam client


def test_window_mode_films_a_cs2_that_is_already_running(tmp_path, monkeypatch):
    steam = tmp_path / "steam"
    steam.mkdir()
    (steam / "steam.exe").write_bytes(b"exe")
    monkeypatch.setattr(factory.Cs2Controller, "game_running", lambda self: True)
    assert factory.build_live_recorder(make_config(tmp_path, "window"), steam_root=steam).launch_args is None


def test_an_hlae_older_than_the_latest_cs2_update_is_warned_about(tmp_path, monkeypatch, caplog):
    config = make_config(tmp_path)
    (tmp_path / "hlae" / VERSION_FILE).write_text("2.193.0\n2026-11-07T19:44:48\n", encoding="utf-8")
    monkeypatch.setattr(factory, "hlae_older_than_game", lambda published, root, **_: published is not None)
    with caplog.at_level("WARNING"):
        recorder = factory.build_live_recorder(config)
    assert type(recorder) is HlaeRecorder  # still records, only warns
    assert "HLAE 2.193.0 was released before this CS2 update" in caplog.text


def test_no_warning_when_hlae_is_newer_than_the_game(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(factory, "hlae_older_than_game", lambda published, root, **_: False)
    with caplog.at_level("WARNING"):
        factory.build_live_recorder(make_config(tmp_path))
    assert "CS2 update" not in caplog.text


def test_a_build_hlae_failed_on_goes_straight_to_window_capture(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(factory, "hlae_broken_here", lambda hlae_dir, root: True)
    monkeypatch.setattr(factory, "cs2_build", lambda root: "26798866")
    with caplog.at_level("WARNING"):
        recorder = factory.build_live_recorder(make_config(tmp_path))
    assert isinstance(recorder, WindowRecorder)
    assert "cannot hook CS2 build 26798866" in caplog.text


def test_the_hlae_recorder_remembers_a_build_it_cannot_hook(tmp_path, monkeypatch):
    noted = []
    monkeypatch.setattr(factory, "mark_hlae_broken", lambda hlae_dir, root: noted.append(hlae_dir))
    recorder = factory.build_live_recorder(make_config(tmp_path))
    recorder._on_unusable()
    assert noted == [tmp_path / "hlae"]
