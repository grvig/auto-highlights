"""Tick/second conversion.

CS2 runs at 64 ticks per second. Every conversion in the project goes through
this module — no bare `/ 64` anywhere else, so a tickrate assumption can never
drift between the engine and the recorder.
"""

from __future__ import annotations

CS2_TICKRATE = 64


def ticks_to_seconds(ticks: int, tickrate: int = CS2_TICKRATE) -> float:
    """Convert a tick count to seconds."""
    return ticks / tickrate


def seconds_to_ticks(seconds: float, tickrate: int = CS2_TICKRATE) -> int:
    """Convert seconds to a whole number of ticks, rounded to nearest."""
    return round(seconds * tickrate)


def tick_span_seconds(
    start_tick: int, end_tick: int, tickrate: int = CS2_TICKRATE
) -> float:
    """Duration in seconds between two ticks."""
    return ticks_to_seconds(end_tick - start_tick, tickrate)


def format_timestamp(ticks: int, tickrate: int = CS2_TICKRATE) -> str:
    """Format a tick as mm:ss from the start of the demo, for logs and the CLI."""
    total_seconds = int(ticks_to_seconds(ticks, tickrate))
    minutes, seconds = divmod(max(total_seconds, 0), 60)
    return f"{minutes:02d}:{seconds:02d}"
