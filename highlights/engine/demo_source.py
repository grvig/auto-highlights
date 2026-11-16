"""Thin wrapper over awpy's Demo.

Isolates every awpy-specific detail — construction, tickrate, dataframe names —
so the rest of the engine talks to our own vocabulary. If awpy's API shifts,
this is the only file that should need to change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from awpy import Demo

from highlights.engine.cache import DemoCache
from highlights.engine.models import (
    Blind,
    Damage,
    Kill,
    Round,
    Shot,
    Smoke,
    extract_blinds,
    extract_damages,
    extract_kills,
    extract_rounds,
    extract_shots,
    extract_smokes,
)
from highlights.engine.timing import CS2_TICKRATE

logger = logging.getLogger(__name__)

# awpy defaults to 128; CS2 matchmaking demos are 64. Getting this wrong
# silently doubles or halves every timestamp we derive.
DEFAULT_TICKRATE = CS2_TICKRATE

# header["client_name"] on a GOTV/SourceTV recording. POV demos carry the
# recording player's name instead, and only have that one perspective.
GOTV_CLIENT_NAME = "SourceTV Demo"

# Events outside awpy's default set that detectors need, parsed together.
EXTRA_EVENTS = ("player_blind", "smokegrenade_detonate", "weapon_fire")


class DemoError(Exception):
    """Raised when a demo cannot be read or does not look like we expect."""


@dataclass(frozen=True)
class Player:
    """One of the players in the match."""

    steamid: str
    name: str
    starting_side: str

    def __str__(self) -> str:
        return f"{self.name} ({self.starting_side})"


@dataclass(frozen=True)
class DemoInfo:
    """Match-level facts pulled from the demo header."""

    map_name: str
    server_name: str
    client_name: str
    tickrate: int

    @property
    def is_gotv(self) -> bool:
        """GOTV demos can spectate all 10 players; POV demos cannot."""
        return self.client_name == GOTV_CLIENT_NAME


class DemoSource:
    """A parsed demo, exposing its tables under stable names.

    Given a DemoCache, a demo parsed once is reopened from disk in a fraction of
    the parse time; a fresh parse is stored for next time.
    """

    def __init__(
        self,
        path: Path | str,
        tickrate: int = DEFAULT_TICKRATE,
        cache: DemoCache | None = None,
    ) -> None:
        self.path = Path(path)
        if self.path.is_dir():
            raise DemoError(
                f"{self.path} is a folder, not a demo file. Point at a .dem file "
                "inside it (demos live under <cs2>/game/csgo/replays)."
            )
        if not self.path.is_file():
            raise DemoError(f"No demo file at {self.path}")
        if self.path.suffix.lower() != ".dem":
            raise DemoError(
                f"{self.path.name} is not a .dem file (got '{self.path.suffix}'). "
                "This tool reads Counter-Strike 2 demo files."
            )

        self.tickrate = tickrate
        cached = cache.load(self.path) if cache else None
        if cached is not None:
            self._header, self._frames = cached.header, cached.frames
        else:
            self._header, self._frames = self._parse()
            if cache is not None:
                cache.store(self.path, self._header, self._frames)

    def _parse(self) -> tuple[dict, dict[str, pl.DataFrame | None]]:
        """Run awpy over the demo and collect every table the engine reads."""
        logger.info("Parsing %s (tickrate=%d)", self.path.name, self.tickrate)
        demo = Demo(self.path, tickrate=self.tickrate)
        demo.parse()
        # Events outside awpy's default set, read together in one extra pass.
        extras = demo.parse_events(list(EXTRA_EVENTS))
        logger.info("Parsed %s", self.path.name)
        frames: dict[str, pl.DataFrame | None] = {
            "rounds": demo.rounds,
            "kills": demo.kills,
            "damages": demo.damages,
            "ticks": demo.ticks,
        }
        frames.update({name: extras.get(name) for name in EXTRA_EVENTS})
        return dict(demo.header), frames

    @property
    def info(self) -> DemoInfo:
        header = self._header
        return DemoInfo(
            map_name=header.get("map_name", "unknown"),
            server_name=header.get("server_name", "unknown"),
            client_name=header.get("client_name", "unknown"),
            tickrate=self.tickrate,
        )

    def players(self) -> list[Player]:
        """The players in the match, ordered by starting side then name.

        Derived from the tick stream rather than the header, since the header
        carries no roster. Each player's side is taken from their first
        appearance, before the halftime swap.
        """
        first_seen = (
            self.ticks.select("steamid", "name", "side", "tick")
            .sort("tick")
            .unique(subset=["steamid"], keep="first")
            .sort(["side", "name"])
        )
        return [
            Player(
                steamid=str(row["steamid"]),
                name=str(row["name"]),
                starting_side=str(row["side"]),
            )
            for row in first_seen.iter_rows(named=True)
        ]

    def round_list(self) -> list[Round]:
        """The match's rounds as internal models."""
        return extract_rounds(self.rounds)

    def tick_bounds(self) -> tuple[int, int]:
        """The first and last playable ticks in the demo.

        Used to clamp padded moment windows so a seek never runs off either
        end of the recording.
        """
        ticks = self.ticks
        return int(ticks["tick"].min()), int(ticks["tick"].max())

    def round_rosters(self) -> dict[int, dict[str, str]]:
        """Per-round {steamid: side}, taken from the tick stream.

        Sides are read per round rather than once, so the halftime swap is
        reflected correctly. A player's side within a round is their most
        common side across that round's ticks, guarding against the odd
        transitional tick at a round boundary.
        """
        per_round = (
            self.ticks.group_by(["round_num", "steamid", "side"])
            .len()
            .sort("len", descending=True)
            .unique(subset=["round_num", "steamid"], keep="first")
        )
        rosters: dict[int, dict[str, str]] = {}
        for row in per_round.iter_rows(named=True):
            rosters.setdefault(int(row["round_num"]), {})[str(row["steamid"])] = str(
                row["side"]
            )
        return rosters

    def kill_list(self) -> list[Kill]:
        """The match's kills as internal models, world deaths excluded."""
        return extract_kills(self.kills)

    def extra_event(self, name: str) -> pl.DataFrame | None:
        """One of the events awpy does not parse by default, or None if absent."""
        frame = self._frames.get(name)
        if frame is None or frame.height == 0:
            return None
        return frame

    def blind_list(self) -> list[Blind]:
        """Flash events as Blind models, empty if the demo has none."""
        frame = self.extra_event("player_blind")
        return extract_blinds(frame) if frame is not None else []

    def damage_list(self) -> list[Damage]:
        """Damage events as Damage models, world damage excluded."""
        return extract_damages(self.damages)

    def shot_list(self) -> list[Shot]:
        """Every weapon fired, as Shot models, empty if the demo has none."""
        frame = self.extra_event("weapon_fire")
        return extract_shots(frame) if frame is not None else []

    def smoke_list(self) -> list[Smoke]:
        """Smoke detonations as Smoke models, empty if the demo has none."""
        frame = self.extra_event("smokegrenade_detonate")
        return extract_smokes(frame) if frame is not None else []

    @property
    def rounds(self) -> pl.DataFrame:
        return self._frames["rounds"]

    @property
    def kills(self) -> pl.DataFrame:
        return self._frames["kills"]

    @property
    def damages(self) -> pl.DataFrame:
        return self._frames["damages"]

    @property
    def ticks(self) -> pl.DataFrame:
        return self._frames["ticks"]
