"""The Moment model — one highlight worth recording.

A Moment is the engine's output unit: a padded tick window around something
interesting one player did, tagged with what kind of highlight it is. Detectors
produce Moments; the clip-plan builder orders them; the recorder turns each into
a clip.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from highlights.engine.timing import (
    CS2_TICKRATE,
    format_timestamp,
    seconds_to_ticks,
    tick_span_seconds,
)


class HighlightType(str, Enum):
    """The highlight categories a player can filter on.

    Values are the stable identifiers the GUI checkboxes and CLI flags use.
    """

    KILL = "kill"
    MULTI_KILL = "multi_kill"
    ACE = "ace"
    CLUTCH = "clutch"
    DEATH = "death"
    UTILITY = "utility"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Segment:
    """One continuous tick window to record."""

    start_tick: int
    end_tick: int

    def __post_init__(self) -> None:
        if self.start_tick > self.end_tick:
            raise ValueError(
                f"Segment start_tick {self.start_tick} is after "
                f"end_tick {self.end_tick}"
            )

    @property
    def duration_seconds(self) -> float:
        return tick_span_seconds(self.start_tick, self.end_tick)


@dataclass(frozen=True)
class Moment:
    """A single highlight to record for one player.

    start_tick/end_tick are the padded outer bounds of the moment. A moment is
    recorded as one or more segments: a single kill is one window, while a
    multi-kill spread across a round is several short windows with the dead
    time between them cut. When segments is empty the whole outer window is the
    one segment. core_tick marks the key instant for ordering and description.
    """

    round_number: int
    highlight_type: HighlightType
    player_steamid: str
    core_tick: int
    start_tick: int
    end_tick: int
    description: str
    segments: tuple[Segment, ...] = ()
    # The demo this moment comes from, so a reel can mix several matches.
    source_demo: Path | None = None

    def __post_init__(self) -> None:
        if self.start_tick > self.end_tick:
            raise ValueError(
                f"Moment start_tick {self.start_tick} is after "
                f"end_tick {self.end_tick}"
            )
        previous_end: int | None = None
        for segment in self.segments:
            if segment.start_tick < self.start_tick or segment.end_tick > self.end_tick:
                raise ValueError("Segment lies outside the moment's outer window")
            if previous_end is not None and segment.start_tick <= previous_end:
                raise ValueError("Segments must be ordered and must not overlap")
            previous_end = segment.end_tick

    @property
    def windows(self) -> tuple[Segment, ...]:
        """The windows to record: the segments, or the whole outer window."""
        return self.segments or (Segment(self.start_tick, self.end_tick),)

    @property
    def duration_seconds(self) -> float:
        """Footage length, which excludes any dead time cut between segments."""
        return sum(window.duration_seconds for window in self.windows)

    @property
    def timestamp(self) -> str:
        """mm:ss of the core instant from the demo start."""
        return format_timestamp(self.core_tick)

    def overlaps(self, other: Moment) -> bool:
        """Whether this moment's tick window intersects another's."""
        return self.start_tick <= other.end_tick and other.start_tick <= self.end_tick

    def __str__(self) -> str:
        return (
            f"R{self.round_number} {self.timestamp} "
            f"[{self.highlight_type}] {self.description}"
        )


def pad_window(
    core_tick: int,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    *,
    first_tick: int,
    last_tick: int,
    span_start_tick: int | None = None,
    span_end_tick: int | None = None,
    tickrate: int = CS2_TICKRATE,
) -> tuple[int, int]:
    """Build a padded (start_tick, end_tick) window around a moment.

    Pads pre-roll before the earliest relevant tick and post-roll after the
    latest, then clamps to the demo's playable bounds so we never seek past
    the start or end of the recording.

    span_start_tick/span_end_tick let a multi-event moment (a multi-kill
    spanning several frags) pad around the whole span rather than one instant;
    they default to core_tick for single-instant moments.

    """
    span_start = span_start_tick if span_start_tick is not None else core_tick
    span_end = span_end_tick if span_end_tick is not None else core_tick

    start = span_start - seconds_to_ticks(pre_roll_seconds, tickrate)
    end = span_end + seconds_to_ticks(post_roll_seconds, tickrate)

    start = max(start, first_tick)
    end = min(end, last_tick)
    return start, end


# Windows closer than this are joined into one continuous segment, so a quick
# multi-kill plays as a single uninterrupted shot rather than jump cuts.
DEFAULT_MERGE_GAP_SECONDS = 2.0


def build_segments(
    event_ticks: list[int],
    pre_roll_seconds: float,
    post_roll_seconds: float,
    *,
    first_tick: int,
    last_tick: int,
    merge_gap_seconds: float = DEFAULT_MERGE_GAP_SECONDS,
    tickrate: int = CS2_TICKRATE,
) -> tuple[Segment, ...]:
    """Pad a window around each event and merge windows that nearly touch.

    Kills seconds apart become one segment; kills a minute apart become
    separate segments with the dead time between them dropped.
    """
    if not event_ticks:
        raise ValueError("Cannot build segments from zero events")

    pre = seconds_to_ticks(pre_roll_seconds, tickrate)
    post = seconds_to_ticks(post_roll_seconds, tickrate)
    gap = seconds_to_ticks(merge_gap_seconds, tickrate)

    windows = sorted(
        (max(tick - pre, first_tick), min(tick + post, last_tick))
        for tick in event_ticks
    )
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(Segment(start, end) for start, end in merged)
