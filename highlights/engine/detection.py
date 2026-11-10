"""Detection scaffolding: the shared context and the Detector protocol.

Every detector reads from one DetectionContext — the parsed match plus padding
settings and demo bounds — and returns Moments for a chosen player. Keeping the
inputs in one object means detectors stay pure functions of (context, player)
and are trivial to test with hand-built data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from highlights.engine.demo_source import DemoSource
from highlights.engine.models import Blind, Damage, Kill, Round, Smoke
from highlights.engine.moments import (
    HighlightType,
    Moment,
    Segment,
    build_segments,
    pad_window,
)


@dataclass(frozen=True)
class DetectionContext:
    """Everything a detector needs, computed once per demo."""

    rounds: list[Round]
    kills: list[Kill]
    first_tick: int
    last_tick: int
    pre_roll_seconds: float
    post_roll_seconds: float
    tickrate: int
    # steamid -> side, per round number. Handles the halftime side swap.
    round_rosters: dict[int, dict[str, str]] = field(default_factory=dict)
    blinds: list[Blind] = field(default_factory=list)
    damages: list[Damage] = field(default_factory=list)
    smokes: list[Smoke] = field(default_factory=list)
    # The demo these tables came from; moments built from it carry it along.
    demo_path: Path | None = None

    @classmethod
    def from_source(
        cls,
        source: DemoSource,
        pre_roll_seconds: float = 3.0,
        post_roll_seconds: float = 2.0,
    ) -> DetectionContext:
        rounds = source.round_list()
        kills = source.kill_list()
        first_tick, last_tick = source.tick_bounds()
        return cls(
            rounds=rounds,
            kills=kills,
            first_tick=first_tick,
            last_tick=last_tick,
            pre_roll_seconds=pre_roll_seconds,
            post_roll_seconds=post_roll_seconds,
            tickrate=source.tickrate,
            round_rosters=source.round_rosters(),
            blinds=source.blind_list(),
            damages=source.damage_list(),
            smokes=source.smoke_list(),
            demo_path=source.path,
        )

    def round_by_number(self, number: int) -> Round | None:
        for rnd in self.rounds:
            if rnd.number == number:
                return rnd
        return None

    def round_of_tick(self, tick: int) -> Round | None:
        """The round containing a tick, or None if it falls between rounds."""
        for rnd in self.rounds:
            if rnd.contains_tick(tick):
                return rnd
        return None

    def side_of(self, steamid: str, round_number: int) -> str | None:
        """Which side a player was on in a given round, or None if unknown."""
        return self.round_rosters.get(round_number, {}).get(steamid)

    def pad(
        self,
        core_tick: int,
        *,
        span_start_tick: int | None = None,
        span_end_tick: int | None = None,
    ) -> tuple[int, int]:
        """Pad a moment window using this context's roll settings and bounds."""
        return pad_window(
            core_tick,
            self.pre_roll_seconds,
            self.post_roll_seconds,
            first_tick=self.first_tick,
            last_tick=self.last_tick,
            span_start_tick=span_start_tick,
            span_end_tick=span_end_tick,
            tickrate=self.tickrate,
        )

    def segments(self, event_ticks: list[int]) -> tuple[Segment, ...]:
        """Kill-by-kill windows around events, with this context's padding."""
        return build_segments(
            event_ticks,
            self.pre_roll_seconds,
            self.post_roll_seconds,
            first_tick=self.first_tick,
            last_tick=self.last_tick,
            tickrate=self.tickrate,
        )


@runtime_checkable
class Detector(Protocol):
    """A highlight detector for one HighlightType."""

    highlight_type: HighlightType

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        """Return this player's moments of this detector's type, in tick order."""
        ...
