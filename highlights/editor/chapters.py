"""YouTube chapter timestamps for a finished reel.

Pasted into a video description, lines like "00:12 ACE (Round 5)" become
clickable chapters, so viewers can jump straight to each highlight.
"""

from __future__ import annotations


def timestamp(seconds: float) -> str:
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def starts(durations: list[float], transition: float) -> list[float]:
    """Where each part of a crossfaded timeline starts."""
    result, elapsed = [], 0.0
    for duration in durations:
        result.append(round(elapsed, 3))
        elapsed += duration - transition
    return result


def chapter_lines(entries: list[tuple[float, str]]) -> list[str]:
    """One "MM:SS label" line per chapter; the first always starts at 00:00."""
    lines = []
    for number, (seconds, label) in enumerate(entries):
        lines.append(f"{timestamp(0 if number == 0 else seconds)} {label}")
    return lines
