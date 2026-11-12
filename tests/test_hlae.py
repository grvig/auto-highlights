"""Tests for the HLAE launcher helpers."""

import sys
from pathlib import Path

import pytest

from highlights.recorder import hlae


def fake_hlae(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "HLAE.exe").write_text("")
    return folder


def test_configured_hlae_is_used(tmp_path):
    folder = fake_hlae(tmp_path / "hlae")
    assert hlae.find_hlae(folder) == folder


def test_missing_hlae_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(hlae, "BUNDLED_DIR", tmp_path / "nowhere")
    assert hlae.find_hlae(tmp_path / "empty") is None


def test_bundled_copy_is_the_fallback(tmp_path, monkeypatch):
    bundled = fake_hlae(tmp_path / "bundled")
    monkeypatch.setattr(hlae, "BUNDLED_DIR", bundled)
    assert hlae.find_hlae(None) == bundled


def test_launch_args_hook_cs2_at_the_render_size():
    args = hlae.launch_args(Path("D:/hlae"), Path("D:/cs2/cs2.exe"), 1440, 1080, 29000)
    assert args[0].endswith("HLAE.exe")
    assert args[args.index("-hookDllPath") + 1].endswith("AfxHookSource2.dll")
    assert args[args.index("-programPath") + 1].endswith("cs2.exe")
    game = args[args.index("-cmdLine") + 1]
    assert "-insecure" in game
    assert "-width 1440 -height 1080" in game
    assert "-netconport 29000" in game


def test_ffmpeg_ini_names_the_executable(tmp_path):
    ini = hlae.write_ffmpeg_ini(tmp_path, Path("C:/ffmpeg/bin/ffmpeg.exe"))
    text = ini.read_text(encoding="utf-8")
    assert text.startswith("[Ffmpeg]\n")
    assert "Path=" in text and "ffmpeg.exe" in text


def test_resolve_ffmpeg_finds_an_absolute_path():
    found = hlae.resolve_ffmpeg(sys.executable)
    assert found.is_absolute()


def test_resolve_ffmpeg_rejects_a_missing_command():
    with pytest.raises(hlae.HlaeError):
        hlae.resolve_ffmpeg("definitely-not-ffmpeg-xyz")
