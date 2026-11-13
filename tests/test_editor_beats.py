"""Tests for beat detection, on synthetic click tracks."""

from pathlib import Path

import numpy as np
import pytest

from highlights.editor.beats import SAMPLE_RATE, beat_times, load_samples, tempo_of


def click_track(bpm: float, seconds: float = 12.0, offset: float = 0.25) -> np.ndarray:
    samples = np.random.default_rng(1).normal(0, 0.002, int(SAMPLE_RATE * seconds)).astype(np.float32)
    period = 60.0 / bpm
    t = offset
    while t < seconds - 0.05:
        start = int(t * SAMPLE_RATE)
        burst = np.exp(-np.arange(400) / 60.0) * 0.8
        samples[start:start + 400] += burst.astype(np.float32)
        t += period
    return samples


@pytest.mark.parametrize("bpm", [90, 120, 150])
def test_tempo_of_a_click_track(bpm):
    assert tempo_of(beat_times(click_track(bpm))) == pytest.approx(bpm, abs=1)


def test_beats_land_on_the_clicks():
    beats = beat_times(click_track(120, offset=0.25))
    assert len(beats) >= 20
    # every detected beat sits within 40ms of a real click (0.25 + k*0.5)
    errors = [abs(((b - 0.25) + 0.25) % 0.5 - 0.25) for b in beats]
    assert max(errors) < 0.04


def test_silence_has_no_beats():
    assert beat_times(np.zeros(SAMPLE_RATE * 3, dtype=np.float32)) == []


def test_samples_are_decoded_as_mono_floats():
    captured = {}

    def decoder(args):
        captured["args"] = args
        return np.array([0.5, -0.5], dtype=np.float32).tobytes()

    samples = load_samples(Path("song.mp3"), decoder=decoder)
    assert list(samples) == [0.5, -0.5]
    assert "-ac" in captured["args"] and "f32le" in captured["args"]


def test_cuts_are_pulled_back_onto_beats():
    from highlights.editor.beats import snap_durations

    beats = [i * 0.5 for i in range(40)]  # 120 BPM from zero
    snapped = snap_durations([5.3, 4.2, 6.0], beats)
    assert snapped == [5.0, 4.0, 6.0]  # last clip untouched


def test_crossfade_midpoints_land_on_beats():
    from highlights.editor.beats import snap_durations

    beats = [i * 0.5 for i in range(40)]
    d = snap_durations([5.3, 4.2, 6.0], beats, transition=0.3)
    first_cut = d[0] - 0.15
    second_cut = d[0] - 0.3 + d[1] - 0.15
    assert first_cut % 0.5 == pytest.approx(0, abs=1e-6)
    assert second_cut % 0.5 == pytest.approx(0, abs=1e-6)


def test_clips_are_never_trimmed_past_their_limit():
    from highlights.editor.beats import snap_durations

    beats = [0.0, 4.0, 8.0]
    assert snap_durations([5.0, 3.0], beats, trimmable=[0.2, 0.2]) == [5.0, 3.0]
    assert snap_durations([5.0, 3.0], beats, trimmable=[1.0, 1.0]) == [4.0, 3.0]
