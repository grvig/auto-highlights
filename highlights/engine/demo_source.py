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

from highlights.engine.timing import CS2_TICKRATE

logger = logging.getLogger(__name__)

# awpy defaults to 128; CS2 matchmaking demos are 64. Getting this wrong
# silently doubles or halves every timestamp we derive.
DEFAULT_TICKRATE = CS2_TICKRATE

# header["client_name"] on a GOTV/SourceTV recording. POV demos carry the
# recording player's name instead, and only have that one perspective.
GOTV_CLIENT_NAME = "SourceTV Demo"


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
    """A parsed demo, exposing awpy's dataframes under stable names."""

    def __init__(self, path: Path | str, tickrate: int = DEFAULT_TICKRATE) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise DemoError(f"No demo file at {self.path}")

        self.tickrate = tickrate
        logger.info("Parsing %s (tickrate=%d)", self.path.name, tickrate)
        self._demo = Demo(self.path, tickrate=tickrate)
        self._demo.parse()
        logger.info("Parsed %s", self.path.name)

    @property
    def info(self) -> DemoInfo:
        header = self._demo.header
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

    @property
    def rounds(self) -> pl.DataFrame:
        return self._demo.rounds

    @property
    def kills(self) -> pl.DataFrame:
        return self._demo.kills

    @property
    def damages(self) -> pl.DataFrame:
        return self._demo.damages

    @property
    def grenades(self) -> pl.DataFrame:
        return self._demo.grenades

    @property
    def ticks(self) -> pl.DataFrame:
        return self._demo.ticks
