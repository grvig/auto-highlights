"""Tests for fetching ffmpeg, with the network faked."""

import hashlib
import io
import zipfile

import pytest

from highlights.recorder.ffmpeg_setup import FfmpegSetupError, ffmpeg_exe, install_ffmpeg


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


GOOD = zip_bytes({"ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe": b"exe",
                  "ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe": b"probe"})


def fakes(archive=GOOD, checksum=None, lacking=()):
    def download(url, target):
        target.write_bytes(archive)

    def fetch_text(url):
        return (checksum or hashlib.sha256(archive).hexdigest()) + " *ffmpeg-release-essentials.zip\n"

    return dict(download=download, fetch_text=fetch_text, check=lambda exe: list(lacking))


def test_a_verified_build_is_unpacked_into_place(tmp_path):
    exe = install_ffmpeg(tmp_path / "ffmpeg", **fakes())
    assert exe == ffmpeg_exe(tmp_path / "ffmpeg") and exe.read_bytes() == b"exe"
    assert (tmp_path / "ffmpeg" / "bin" / "ffprobe.exe").is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ffmpeg"]  # nothing left behind


def test_a_download_that_fails_its_checksum_is_refused(tmp_path):
    with pytest.raises(FfmpegSetupError, match="checksum"):
        install_ffmpeg(tmp_path / "ffmpeg", **fakes(checksum="0" * 64))
    assert not (tmp_path / "ffmpeg").exists()


def test_a_build_missing_needed_filters_is_refused(tmp_path):
    with pytest.raises(FfmpegSetupError, match="drawtext"):
        install_ffmpeg(tmp_path / "ffmpeg", **fakes(lacking=("drawtext",)))


def test_archive_paths_cannot_escape(tmp_path):
    evil = zip_bytes({"ffmpeg/bin/ffmpeg.exe": b"exe", "../escape.txt": b"x"})
    with pytest.raises(FfmpegSetupError, match="Unsafe"):
        install_ffmpeg(tmp_path / "ffmpeg", **fakes(archive=evil))
    assert not (tmp_path / "escape.txt").exists()


def test_an_archive_without_ffmpeg_is_refused(tmp_path):
    with pytest.raises(FfmpegSetupError, match="no bin/ffmpeg.exe"):
        install_ffmpeg(tmp_path / "ffmpeg", **fakes(archive=zip_bytes({"readme.txt": b"x"})))
