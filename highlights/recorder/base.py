"""The Recorder interface and its data types.

Layer 2 consumes what Layer 1 produced: a ClipPlan becomes a series of
ClipRequests, and each recorded clip comes back as a RecordedClip. Backends
(dry-run, OBS, or a future HLAE one) implement Recorder without the engine
knowing anything about them.

The dependency only ever points this way — recorder imports engine, never the
reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from highlights.engine.moments import Moment, Segment


class RecorderError(Exception):
    """Raised when a backend cannot record — game not running, OBS down, etc."""


@dataclass(frozen=True)
class ClipRequest:
    """One recorded window of a moment, resolved into recording parameters.

    A moment with several segments becomes several requests sharing an index,
    numbered by part, so each window is captured as its own sub-clip.
    """

    # Position in the plan, 1-based. Drives clip ordering and filenames.
    index: int
    moment: Moment
    demo_path: Path
    player_name: str
    output_path: Path
    # The window this request records; None means the moment's whole window.
    segment: Segment | None = None
    part: int = 1
    parts: int = 1

    @property
    def player_steamid(self) -> str:
        return self.moment.player_steamid

    @property
    def spectate_steamid(self) -> str:
        """Whose view to record: the segment's camera, else the player's."""
        return self.window.pov_steamid or self.moment.player_steamid

    @property
    def speed(self) -> float:
        return self.window.speed

    @property
    def window(self) -> Segment:
        return self.segment or Segment(self.moment.start_tick, self.moment.end_tick)

    @property
    def start_tick(self) -> int:
        return self.window.start_tick

    @property
    def end_tick(self) -> int:
        return self.window.end_tick

    @property
    def duration_seconds(self) -> float:
        return self.window.duration_seconds

    @property
    def label(self) -> str:
        """#007, or #007.2/3 for the second of three parts."""
        if self.parts > 1:
            return f"#{self.index:03d}.{self.part}/{self.parts}"
        return f"#{self.index:03d}"

    def __str__(self) -> str:
        camera = "" if self.spectate_steamid == self.player_steamid else f" pov={self.spectate_steamid}"
        speed = "" if self.speed == 1.0 else f" x{self.speed:g}"
        return (
            f"{self.label} {self.moment.highlight_type} "
            f"R{self.moment.round_number} ticks {self.start_tick}-{self.end_tick}"
            f"{camera}{speed} ({self.duration_seconds:.1f}s) -> {self.output_path.name}"
        )


@dataclass(frozen=True)
class RecordedClip:
    """The outcome of recording one request."""

    request: ClipRequest
    output_path: Path
    succeeded: bool
    error: str | None = None

    @property
    def index(self) -> int:
        return self.request.index

    def __str__(self) -> str:
        if self.succeeded:
            return f"#{self.request.index:03d} ok -> {self.output_path.name}"
        return f"#{self.request.index:03d} FAILED: {self.error}"


@runtime_checkable
class Recorder(Protocol):
    """A backend that turns ClipRequests into video files.

    Backends are used as context managers so connections and processes are
    torn down even when a clip fails partway through.
    """

    name: str

    def open(self) -> None:
        """Connect to or launch whatever the backend needs."""
        ...

    def close(self) -> None:
        """Release resources. Must be safe to call even if open() failed."""
        ...

    def record_clip(self, request: ClipRequest) -> RecordedClip:
        """Record one moment. Should not raise — return a failed clip instead."""
        ...
