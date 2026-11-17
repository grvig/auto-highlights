"""Tests for first-run tool setup, with downloads faked."""

from pathlib import Path

import pytest

from highlights import setup
from highlights.config import ClipConfig, Config, RecordingConfig
from highlights.recorder.hlae_release import ReleaseError


def make_config(tmp_path, ffmpeg="ffmpeg", recorder="hlae", hlae=None):
    return Config(cs2_root=None, output_dir=tmp_path / "out", clips_dir=tmp_path / "clips",
                  clips=ClipConfig(), ffmpeg_path=ffmpeg,
                  recording=RecordingConfig(recorder=recorder, hlae_path=hlae))


@pytest.fixture
def fake_tools(monkeypatch):
    calls = {}

    def install_ffmpeg(folder):
        calls["ffmpeg"] = folder
        return Path(folder) / "bin" / "ffmpeg.exe"

    def ensure_current(folder):
        calls["hlae"] = folder
        return "2.193.0", True

    monkeypatch.setattr(setup, "install_ffmpeg", install_ffmpeg)
    monkeypatch.setattr(setup, "ensure_current", ensure_current)
    return calls


def test_an_ffmpeg_already_present_is_used(tmp_path, fake_tools):
    exe = tmp_path / "ffmpeg.exe"
    exe.write_bytes(b"exe")
    result = setup.ensure_tools(make_config(tmp_path, ffmpeg=str(exe)), tools=tmp_path / "tools")
    assert result["ffmpeg"] == str(exe) and "ffmpeg" not in fake_tools


def test_a_missing_ffmpeg_is_downloaded_into_the_tools_folder(tmp_path, fake_tools, monkeypatch):
    monkeypatch.setattr(setup, "ffmpeg_found", lambda ffmpeg: False)
    events = []
    result = setup.ensure_tools(make_config(tmp_path), events.append, tools=tmp_path / "tools")
    assert fake_tools["ffmpeg"] == tmp_path / "tools" / "ffmpeg"
    assert result["hlae_version"] == "2.193.0" and fake_tools["hlae"] == tmp_path / "tools" / "hlae"
    assert events[-1].message == "Ready"


def test_hlae_is_skipped_for_window_capture(tmp_path, fake_tools, monkeypatch):
    monkeypatch.setattr(setup, "ffmpeg_found", lambda ffmpeg: True)
    result = setup.ensure_tools(make_config(tmp_path, recorder="window"), tools=tmp_path / "tools")
    assert "hlae" not in result and "hlae" not in fake_tools


def test_offline_with_hlae_installed_is_fine_but_without_it_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "ffmpeg_found", lambda ffmpeg: True)

    def offline(folder):
        raise ReleaseError("Could not check for HLAE releases")

    monkeypatch.setattr(setup, "ensure_current", offline)
    with pytest.raises(setup.SetupError, match="HLAE could not be installed"):
        setup.ensure_tools(make_config(tmp_path), tools=tmp_path / "tools")
    hlae = tmp_path / "hlae"
    hlae.mkdir()
    (hlae / "HLAE.exe").write_bytes(b"exe")
    assert setup.ensure_tools(make_config(tmp_path, hlae=hlae))["hlae_version"] is None
