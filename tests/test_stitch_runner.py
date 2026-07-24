"""Tests for the ffmpeg runner, with the subprocess faked."""

from pathlib import Path

import pytest

from highlights.stitcher.ffmpeg_command import build_stream_copy
from highlights.stitcher.runner import (
    RunResult,
    StitchError,
    ffmpeg_available,
    run_concat,
)


def make_command(output_path):
    return build_stream_copy("ffmpeg", Path("list.txt"), output_path)


class FakeRunner:
    def __init__(self, returncode=0, stderr="", writes=True):
        self.returncode = returncode
        self.stderr = stderr
        self.writes = writes
        self.called_with = None

    def __call__(self, args):
        self.called_with = args
        if self.writes and self.returncode == 0:
            # ffmpeg's output is the last argument.
            Path(args[-1]).write_text("video")
        return RunResult(returncode=self.returncode, stdout="", stderr=self.stderr)


def test_ffmpeg_available_finds_bare_command_on_path(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")
    assert ffmpeg_available("ffmpeg")
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert not ffmpeg_available("ffmpeg")


def test_ffmpeg_available_checks_explicit_path(tmp_path):
    exe = tmp_path / "ffmpeg.exe"
    assert not ffmpeg_available(str(exe))
    exe.write_text("")
    assert ffmpeg_available(str(exe))


def test_run_concat_success_returns_output(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "ffmpeg")
    out = tmp_path / "reel.mkv"
    runner = FakeRunner()
    result = run_concat(make_command(out), "ffmpeg", runner=runner)
    assert result == out
    assert out.exists()
    assert runner.called_with[-1] == str(out)


def test_missing_ffmpeg_raises_with_guidance(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(StitchError, match="ffmpeg not found"):
        run_concat(make_command(tmp_path / "reel.mkv"), "ffmpeg", runner=FakeRunner())


def test_nonzero_exit_surfaces_stderr_tail(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "ffmpeg")
    runner = FakeRunner(returncode=1, stderr="line1\nline2\nreal error here", writes=False)
    with pytest.raises(StitchError, match="real error here"):
        run_concat(make_command(tmp_path / "reel.mkv"), "ffmpeg", runner=runner)


def test_success_but_no_output_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "ffmpeg")
    runner = FakeRunner(returncode=0, writes=False)
    with pytest.raises(StitchError, match="was not written"):
        run_concat(make_command(tmp_path / "reel.mkv"), "ffmpeg", runner=runner)
