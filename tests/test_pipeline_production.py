"""Tests for producing the finished reel, with ffmpeg faked out."""

from dataclasses import replace
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

        def build(self, clips, output, progress=None, cancel=None):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"edited")
            return output

    monkeypatch.setattr(production, "ReelBuilder", FakeBuilder)
    monkeypatch.setattr(production, "best_frame", lambda clips: None)
    result = produce_reel([], "semi", make_config(tmp_path), edit=EditOptions("semi"))
    assert result.chapters.read_text(encoding="utf-8").splitlines()[1] == "00:03 ACE (Round 5)"
    assert result.thumbnail is None
    assert Path(result.video).read_bytes() == b"edited"


def test_clips_already_on_disk_are_reused_and_missing_ones_flagged(tmp_path):
    from tests.test_hlae_backend import make_request

    present = make_request(tmp_path)
    present.output_path.write_bytes(b"clip")
    missing = replace(present, output_path=tmp_path / "missing.mp4")
    clips = production.clips_on_disk([present, missing])
    assert [c.succeeded for c in clips] == [True, False]
    assert clips[1].error == "not recorded yet"


def test_a_game_that_cannot_start_is_one_readable_error(tmp_path, monkeypatch):
    from highlights.recorder.hlae import HlaeError

    def no_hlae(config):
        raise HlaeError("ffmpeg not found: ffmpeg")

    monkeypatch.setattr(production, "build_live_recorder", no_hlae)
    with pytest.raises(ProductionError, match="ffmpeg not found"):
        production.record_clips([], make_config(tmp_path), live=True)


def test_dry_runs_log_without_touching_the_game(tmp_path, monkeypatch):
    from tests.test_hlae_backend import make_request

    monkeypatch.setattr(production, "build_live_recorder", lambda c: pytest.fail("no game"))
    clips = production.record_clips([make_request(tmp_path)], make_config(tmp_path), live=False)
    assert len(clips) == 1 and clips[0].succeeded


def test_producing_reports_joining_and_export(tmp_path, fake_ffmpeg):
    events = []
    produce_reel([], "semi", make_config(tmp_path), progress=events.append)
    assert [(e.stage, e.message) for e in events] == [
        ("edit", "Joining the clips"), ("export", "Exporting as stretched"), ("export", "Done")]


def test_a_cancelled_reel_stops_before_export(tmp_path, fake_ffmpeg):
    from highlights.progress import CancelToken, Cancelled

    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        produce_reel([], "semi", make_config(tmp_path), cancel=token)
    assert "convert" not in fake_ffmpeg


class FakeBackend:
    def __init__(self, name, unusable=None):
        self.name, self.unusable, self.recorded = name, None, []
        self._fail_with = unusable

    def open(self):
        pass

    def close(self):
        pass

    def record_clip(self, request):
        from highlights.recorder.base import RecordedClip

        if self._fail_with:
            self.unusable = self._fail_with
            return RecordedClip(request, request.output_path, succeeded=False, error=self._fail_with)
        self.recorded.append(request.index)
        return RecordedClip(request, request.output_path, succeeded=True)


def test_clips_hlae_cannot_record_are_recorded_again_with_window_capture(tmp_path, monkeypatch):
    from tests.test_hlae_backend import make_request

    backends = [FakeBackend("hlae", unusable="HLAE cannot hook CS2 build 26798866 yet."), FakeBackend("window")]
    monkeypatch.setattr(production, "build_live_recorder", lambda config: backends.pop(0))
    monkeypatch.setattr(production, "settings_guard", lambda config: __import__("contextlib").nullcontext())
    requests = [make_request(tmp_path), replace(make_request(tmp_path), index=2)]
    events = []
    clips = production.record_clips(requests, make_config(tmp_path), live=True, progress=events.append)
    assert [c.succeeded for c in clips] == [True, True]
    assert not backends  # the window backend was used
    assert any("switching to window capture" in e.message for e in events)


def test_no_second_try_when_hlae_would_be_picked_again(tmp_path, monkeypatch):
    from tests.test_hlae_backend import make_request

    reason = "HLAE cannot hook this CS2 build yet."
    backends = [FakeBackend("hlae", unusable=reason), FakeBackend("hlae", unusable=reason)]
    monkeypatch.setattr(production, "build_live_recorder", lambda config: backends.pop(0))
    monkeypatch.setattr(production, "settings_guard", lambda config: __import__("contextlib").nullcontext())
    clips = production.record_clips([make_request(tmp_path)], make_config(tmp_path), live=True)
    assert [c.succeeded for c in clips] == [False]
    assert clips[0].error == reason
