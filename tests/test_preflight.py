"""Tests for the environment readiness checks."""

from pathlib import Path

from highlights.config import ClipConfig, Config, ObsConfig, RecordingConfig
from highlights.preflight import Check, all_passed, run_preflight


def make_config(tmp_path, *, ffmpeg="ffmpeg", make_exe=True, port=4455, hlae=True):
    hlae_dir = tmp_path / "hlae"
    if hlae:
        hlae_dir.mkdir()
        (hlae_dir / "HLAE.exe").write_text("")
    cs2_root = tmp_path / "cs2"
    exe = cs2_root / "game" / "bin" / "win64" / "cs2.exe"
    if make_exe:
        exe.parent.mkdir(parents=True)
        exe.write_text("")
    return Config(
        cs2_root=cs2_root,
        output_dir=tmp_path / "output",
        clips_dir=tmp_path / "clips",
        obs=ObsConfig(host="localhost", port=port, password="pw"),
        clips=ClipConfig(pre_roll_seconds=3.0, post_roll_seconds=2.0),
        ffmpeg_path=ffmpeg,
        recording=RecordingConfig(hlae_path=hlae_dir),
    )


def find(checks, name):
    return next(c for c in checks if c.name == name)


def test_all_pass_when_everything_is_present(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    checks = run_preflight(make_config(tmp_path))
    assert all_passed(checks)
    assert find(checks, "CS2 install").ok
    assert find(checks, "clips dir writable").ok


def test_missing_cs2_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    checks = run_preflight(make_config(tmp_path, make_exe=False))
    assert not find(checks, "CS2 install").ok
    assert not all_passed(checks)


def test_missing_ffmpeg_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: False)
    checks = run_preflight(make_config(tmp_path))
    assert not find(checks, "ffmpeg").ok


def test_invalid_config_value_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    checks = run_preflight(make_config(tmp_path, port=70000))
    assert not find(checks, "config values").ok


def test_creates_and_reports_writable_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    config = make_config(tmp_path)
    run_preflight(config)
    assert config.clips_dir.exists()
    assert config.output_dir.exists()


def test_all_passed_helper():
    assert all_passed([Check("a", True, ""), Check("b", True, "")])
    assert not all_passed([Check("a", True, ""), Check("b", False, "")])


def test_missing_hlae_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    monkeypatch.setattr("highlights.recorder.hlae.BUNDLED_DIR", tmp_path / "none")
    checks = run_preflight(make_config(tmp_path, hlae=False))
    assert not find(checks, "HLAE").ok
