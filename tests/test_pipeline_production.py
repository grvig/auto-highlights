"""Tests for producing the finished reel, with ffmpeg faked out."""

from pathlib import Path

import pytest

from highlights.config import ClipConfig, Config
from highlights.pipeline import production
from highlights.pipeline.production import ProductionError, produce_reel


def make_config(tmp_path):
    return Config(cs2_root=None, output_dir=tmp_path / "out", clips_dir=tmp_path / "clips",
                  clips=ClipConfig())


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    calls = {}

    def stitch(clips, joined, ffmpeg, work_dir=None):
        joined.parent.mkdir(parents=True, exist_ok=True)
        joined.write_bytes(b"joined")
        calls["stitch"] = joined
        return joined

    def convert(source, output, profile, ffmpeg):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(source.read_bytes())
        calls["convert"] = (output, profile.name)
        return output

    monkeypatch.setattr(production, "stitch_clips", stitch)
    monkeypatch.setattr(production, "convert", convert)
    return calls


def test_a_plain_reel_is_joined_exported_and_cleaned_up(tmp_path, fake_ffmpeg):
    result = produce_reel([], "semi", make_config(tmp_path))
    assert result.video.parent == tmp_path / "out"
    assert result.video.name.startswith("semi_highlights_")
    assert result.shape == "stretched"
    assert (result.chapters, result.thumbnail) == (None, None)
    assert not fake_ffmpeg["stitch"].exists()  # the in-between file is gone


def test_the_shape_can_be_chosen(tmp_path, fake_ffmpeg):
    assert produce_reel([], "semi", make_config(tmp_path), aspect="4:3").shape == "4:3"


def test_failures_come_back_as_one_readable_error(tmp_path, monkeypatch):
    from highlights.stitcher.runner import StitchError

    def broken(*args, **kwargs):
        raise StitchError("No usable clips to stitch")

    monkeypatch.setattr(production, "stitch_clips", broken)
    with pytest.raises(ProductionError, match="No usable clips"):
        produce_reel([], "semi", make_config(tmp_path))


def test_an_edited_reel_gets_chapters_beside_it(tmp_path, fake_ffmpeg, monkeypatch):
    from highlights.editor.reel import EditOptions

    class FakeBuilder:
        def __init__(self, options, work_dir, ffmpeg):
            self.chapters = ["00:00 Intro", "00:03 ACE (Round 5)"]

        def build(self, clips, output):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"edited")
            return output

    monkeypatch.setattr(production, "ReelBuilder", FakeBuilder)
    monkeypatch.setattr(production, "best_frame", lambda clips: None)
    result = produce_reel([], "semi", make_config(tmp_path), edit=EditOptions("semi"))
    assert result.chapters.read_text(encoding="utf-8").splitlines()[1] == "00:03 ACE (Round 5)"
    assert result.thumbnail is None
    assert Path(result.video).read_bytes() == b"edited"
