"""Tests for picking the live recorder and guarding CS2 settings."""

from contextlib import nullcontext

import pytest

from highlights.config import ClipConfig, Config, RecordingConfig
from highlights.recorder import factory
from highlights.recorder.cfg_guard import CfgGuard
from highlights.recorder.hlae_backend import HlaeRecorder
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
