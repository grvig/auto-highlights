"""Tests for finding ffmpeg off PATH."""

from pathlib import Path

from highlights import ffmpeg_locate
from highlights.ffmpeg_locate import locate_ffmpeg


def no_path(monkeypatch):
    monkeypatch.setattr(ffmpeg_locate.shutil, "which", lambda name: None)


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"exe")
    return path


def test_an_explicit_path_is_kept(tmp_path):
    assert locate_ffmpeg("C:/tools/ffmpeg.exe", tmp_path / "b", tmp_path / "w") == "C:/tools/ffmpeg.exe"


def test_path_wins_when_present(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg_locate.shutil, "which", lambda name: "C:/x/ffmpeg.exe")
    assert locate_ffmpeg("ffmpeg", touch(tmp_path / "b.exe"), tmp_path) == "ffmpeg"


def test_bundled_copy_is_next(monkeypatch, tmp_path):
    no_path(monkeypatch)
    bundled = touch(tmp_path / "tools" / "ffmpeg.exe")
    assert locate_ffmpeg("ffmpeg", bundled, tmp_path / "winget") == str(bundled)


def test_winget_install_is_found(monkeypatch, tmp_path):
    no_path(monkeypatch)
    packages = tmp_path / "Packages"
    exe = touch(packages / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                / "ffmpeg-9.0.1-full_build" / "bin" / "ffmpeg.exe")
    assert locate_ffmpeg("ffmpeg", tmp_path / "none.exe", packages) == str(exe)


def test_nothing_found_returns_the_bare_name(monkeypatch, tmp_path):
    no_path(monkeypatch)
    assert locate_ffmpeg("ffmpeg", tmp_path / "none.exe", tmp_path / "none") == "ffmpeg"
