"""Finding the beat of the user's music, so cuts can land on it.

A small, dependency-light tracker: decode to mono, measure how sharply the
loudness rises in short frames (onsets), find the tempo whose period best
lines those onsets up, then the phase that puts beats on the strongest ones.
Good enough for the steady beat of the tracks people cut frag movies to.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

SAMPLE_RATE = 11_025
HOP = 128
MIN_BPM, MAX_BPM = 70.0, 180.0

Decoder = Callable[[Sequence[str]], bytes]


def _decode(args: Sequence[str]) -> bytes:
    return subprocess.run(list(args), capture_output=True, check=True).stdout


def load_samples(path: Path, ffmpeg: str = "ffmpeg", decoder: Decoder = _decode) -> np.ndarray:
    raw = decoder([
        ffmpeg, "-loglevel", "error", "-i", str(path),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ])
    return np.frombuffer(raw, dtype=np.float32)


def onset_envelope(samples: np.ndarray) -> np.ndarray:
    """Rise in log loudness per frame, half-wave rectified."""
    frames = len(samples) // HOP
    if frames < 2:
        return np.zeros(0)
    energy = np.square(samples[: frames * HOP].reshape(frames, HOP)).sum(axis=1)
    rise = np.diff(np.log1p(energy * 1000.0), prepend=0.0)
    return np.maximum(rise, 0.0)


def estimate_tempo(envelope: np.ndarray) -> float:
    """Beats per minute with the strongest periodicity in the onsets."""
    frame_rate = SAMPLE_RATE / HOP
    centred = envelope - envelope.mean()
    best_bpm, best_score = 120.0, -np.inf
    for bpm in np.arange(MIN_BPM, MAX_BPM + 0.01, 0.5):
        lag = frame_rate * 60.0 / bpm
        low = int(lag)
        frac = lag - low
        if low + 1 >= len(centred):
            continue
        # interpolate between neighbouring whole-frame lags
        a = float(np.dot(centred[:-low], centred[low:]))
        b = float(np.dot(centred[: -(low + 1)], centred[low + 1:]))
        score = (1 - frac) * a + frac * b
        if score > best_score:
            best_bpm, best_score = float(bpm), score
    return best_bpm


def _grid_score(envelope: np.ndarray, period: float, phase: float) -> float:
    """Onset strength summed under a beat grid, read between frames linearly."""
    positions = np.arange(phase, len(envelope) - 1, period)
    low = positions.astype(int)
    frac = positions - low
    hits = ((1 - frac) * envelope[low] + frac * envelope[low + 1]).sum()
    # Each grid point costs the average onset strength, so a grid twice as
    # dense as the music (beats on nothing) loses to the true one.
    return float(hits - len(positions) * envelope.mean())


def _best_grid(envelope: np.ndarray, bpm: float) -> tuple[float, float]:
    """Refine a rough tempo to the grid that hits the most onset strength.

    Autocorrelation only resolves whole frames; over a whole track a small
    tempo error drifts the grid off the beat, so the full grid is scored.
    """
    frame_rate = SAMPLE_RATE / HOP
    best = (0.0, 0.0, -np.inf)
    # Autocorrelation often lands on half or double the real tempo.
    centres = [c for c in (bpm / 2, bpm, bpm * 2) if MIN_BPM - 4 <= c <= MAX_BPM + 4]
    candidates = np.concatenate([np.arange(c - 4.0, c + 4.0, 0.1) for c in centres])
    for candidate in candidates:
        period = frame_rate * 60.0 / candidate
        for phase in np.arange(0, period, 0.25):
            score = _grid_score(envelope, period, phase)
            if score > best[2]:
                best = (period, float(phase), score)
    return best[0], best[1]


def beat_times(samples: np.ndarray) -> list[float]:
    """Seconds of every beat in the track."""
    envelope = onset_envelope(samples)
    if len(envelope) < 8 or not envelope.any():
        return []
    frame_rate = SAMPLE_RATE / HOP
    period, phase = _best_grid(envelope, estimate_tempo(envelope))
    beats = np.arange(phase, len(envelope) - 1, period)
    return [round(float(frame) / frame_rate, 3) for frame in beats]


def snap_durations(
    durations: list[float],
    beats: list[float],
    transition: float = 0.0,
    trimmable: list[float] | None = None,
    lead_in: float = 0.0,
) -> list[float]:
    """Shorten clip tails so every cut lands on a beat.

    A cut is the middle of the crossfade between two clips. Clips only ever
    get shorter, by at most their `trimmable` seconds (the post-roll after
    the action), so no kill is ever cut off. The last clip is left alone.
    lead_in is where the reel starts within the track.
    """
    limits = trimmable or [0.6] * len(durations)
    result: list[float] = []
    start = lead_in
    for number, duration in enumerate(durations):
        if number < len(durations) - 1:
            cut = start + duration - transition / 2
            earlier = [b for b in beats if cut - limits[number] <= b <= cut]
            if earlier:
                duration -= cut - earlier[-1]
        result.append(round(duration, 3))
        start += duration - transition
    return result


def tempo_of(beats: list[float]) -> float | None:
    """Beats per minute implied by detected beat times."""
    if len(beats) < 2:
        return None
    return round(60.0 * (len(beats) - 1) / (beats[-1] - beats[0]), 1)
