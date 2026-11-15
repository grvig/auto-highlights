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
    """One continuous tick window to record, from one camera, at one speed."""

    start_tick: int
    end_tick: int
    # Whose eyes to watch through; None means the moment's own player.
    pov_steamid: str | None = None
    # Playback speed: 1.0 is real time, 0.5 is half-speed slow motion.
    speed: float = 1.0
    # Tick spans inside the segment played slower still (speed * ramp_speed):
    # the instant of a kill, ramped down and back up in one continuous shot.
    ramps: tuple[tuple[int, int], ...] = ()
    ramp_speed: float = 0.4

    def __post_init__(self) -> None:
        if self.start_tick > self.end_tick:
            raise ValueError(
                f"Segment start_tick {self.start_tick} is after "
                f"end_tick {self.end_tick}"
            )
        if self.speed <= 0:
            raise ValueError(f"Segment speed must be positive, got {self.speed}")
        if not 0 < self.ramp_speed <= 1:
            raise ValueError(f"Ramp speed must be in (0, 1], got {self.ramp_speed}")
        previous_end = self.start_tick
        for start, end in self.ramps:
            if not previous_end <= start < end <= self.end_tick:
                raise ValueError(f"Ramp {start}-{end} must be ordered and inside the segment")
            previous_end = end

    @property
    def ramped_ticks(self) -> int:
        return sum(end - start for start, end in self.ramps)

    @property
    def duration_seconds(self) -> float:
        """Length of the footage once played back, so slow motion runs longer."""
        span = tick_span_seconds(self.start_tick, self.end_tick)
        slowed = tick_span_seconds(0, self.ramped_ticks)
        return (span - slowed + slowed / self.ramp_speed) / self.speed


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
    # How good the moment is (filled in by scoring) and what made it so.
    score: float = 0.0
    tags: tuple[str, ...] = ()
    # For a clutch: how many enemies the player faced alone (the N in 1vN).
    opponents: int = 0
    # Shown after the main footage: e.g. each victim's view of being killed.
    # Unlike segments these may revisit the same ticks from another camera.
    replays: tuple[Segment, ...] = ()

    def __post_init__(self) -> None:
        if self.start_tick > self.end_tick:
            raise ValueError(
                f"Moment start_tick {self.start_tick} is after "
                f"end_tick {self.end_tick}"
            )
        previous_end: int | None = None
        for segment in self.segments:
            if not self._inside(segment):
                raise ValueError("Segment lies outside the moment's outer window")
            if previous_end is not None and segment.start_tick <= previous_end:
                raise ValueError("Segments must be ordered and must not overlap")
            previous_end = segment.end_tick
        if not all(self._inside(replay) for replay in self.replays):
            raise ValueError("Replay lies outside the moment's outer window")

    def _inside(self, segment: Segment) -> bool:
        return self.start_tick <= segment.start_tick and segment.end_tick <= self.end_tick

    @property
    def windows(self) -> tuple[Segment, ...]:
        """The main windows: the segments, or the whole outer window."""
        return self.segments or (Segment(self.start_tick, self.end_tick),)

    @property
    def playlist(self) -> tuple[Segment, ...]:
        """Everything to record, in playback order: main footage then replays."""
        return self.windows + self.replays

    @property
    def duration_seconds(self) -> float:
        """Footage length, which excludes any dead time cut between segments."""
        return sum(window.duration_seconds for window in self.playlist)

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
