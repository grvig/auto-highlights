"""Tests for the environment readiness checks."""

from pathlib import Path

from highlights.config import ClipConfig, Config, RecordingConfig
from highlights.preflight import Check, all_passed, run_preflight


def make_config(tmp_path, *, ffmpeg="ffmpeg", make_exe=True, framerate=60, hlae=True):
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
        clips=ClipConfig(pre_roll_seconds=3.0, post_roll_seconds=2.0),
        ffmpeg_path=ffmpeg,
        recording=RecordingConfig(hlae_path=hlae_dir, framerate=framerate),
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
    checks = run_preflight(make_config(tmp_path, framerate=1000))
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


def test_hlae_version_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    config = make_config(tmp_path)
    (tmp_path / "hlae" / "auto-highlights-version.txt").write_text("2.193.0")
    assert find(run_preflight(config), "HLAE").detail.endswith("(v2.193.0)")


def test_missing_caption_font_is_reported(tmp_path, monkeypatch):
    from highlights.editor.fonts import FontError

    def no_font(text):
        raise FontError("No usable font found")
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    monkeypatch.setattr("highlights.preflight.find_font", no_font)
    assert not find(run_preflight(make_config(tmp_path)), "caption font").ok


def test_the_last_cs2_update_is_reported_when_steam_knows_it(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    config = make_config(tmp_path)
    (tmp_path / "appmanifest_730.acf").write_text('"AppState" { "LastUpdated" "1794976532" }')
    monkeypatch.setattr("highlights.preflight.cs2_updated_at",
                        lambda root: __import__("datetime").datetime(2026, 11, 18, 10, 5))
    check = find(run_preflight(config), "CS2 updated")
    assert check.ok and check.detail.startswith("18 Nov 2026 10:05")


def test_an_hlae_older_than_the_cs2_update_is_a_warning_not_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.preflight.ffmpeg_available", lambda p: True)
    monkeypatch.setattr("highlights.preflight.hlae_older_than_game", lambda published, root, **_: True)
    check = find(run_preflight(make_config(tmp_path)), "HLAE")
    assert check.ok and check.warning and check.mark == "WARN"
    assert "before the latest CS2 update" in check.detail
    assert Check("x", True, "").mark == "OK" and Check("x", False, "").mark == "FAIL"
