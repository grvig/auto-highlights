"""Internal data models.

Plain frozen dataclasses converted out of awpy's dataframes, so detectors work
against our own vocabulary rather than raw column names. Nothing here knows
about awpy or polars beyond the extraction functions at the bottom.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from highlights.engine.timing import format_timestamp, ticks_to_seconds


@dataclass(frozen=True)
class Round:
    """One round of the match."""

    number: int
    start_tick: int
    freeze_end_tick: int
    end_tick: int
    official_end_tick: int
    winner: str
    reason: str

    @property
    def duration_seconds(self) -> float:
        return ticks_to_seconds(self.end_tick - self.start_tick)

    def contains_tick(self, tick: int) -> bool:
        """Whether a tick falls inside this round, counting the post-round lull."""
        return self.start_tick <= tick <= self.official_end_tick


@dataclass(frozen=True)
class Kill:
    """A single kill event."""

    round_number: int
    tick: int
    attacker_steamid: str
    attacker_name: str
    attacker_side: str
    victim_steamid: str
    victim_name: str
    victim_side: str
    weapon: str
    headshot: bool

    @property
    def timestamp(self) -> str:
        return format_timestamp(self.tick)

    def __str__(self) -> str:
        how = " (hs)" if self.headshot else ""
        return (
            f"R{self.round_number} {self.timestamp} "
            f"{self.attacker_name} killed {self.victim_name} "
            f"with {self.weapon}{how}"
        )


def _as_int(value: object, default: int = 0) -> int:
    return default if value is None else int(value)


def _as_str(value: object, default: str = "") -> str:
    return default if value is None else str(value)


def extract_rounds(rounds: pl.DataFrame) -> list[Round]:
    """Convert awpy's rounds dataframe into Round models, ordered by number."""
    result = [
        Round(
            number=_as_int(row["round_num"]),
            start_tick=_as_int(row["start"]),
            freeze_end_tick=_as_int(row["freeze_end"]),
            end_tick=_as_int(row["end"]),
            # Falls back to end when the demo cuts off before the official end.
            official_end_tick=_as_int(row["official_end"], _as_int(row["end"])),
            winner=_as_str(row["winner"], "unknown"),
            reason=_as_str(row["reason"], "unknown"),
        )
        for row in rounds.iter_rows(named=True)
    ]
    return sorted(result, key=lambda r: r.number)


def extract_kills(kills: pl.DataFrame) -> list[Kill]:
    """Convert awpy's kills dataframe into Kill models, ordered by tick.

    Kills with no attacker are dropped — those are world deaths (falling,
    bomb) which belong to nobody and would corrupt per-player stats.
    """
    result = [
        Kill(
            round_number=_as_int(row["round_num"]),
            tick=_as_int(row["tick"]),
            attacker_steamid=_as_str(row["attacker_steamid"]),
            attacker_name=_as_str(row["attacker_name"]),
            attacker_side=_as_str(row["attacker_side"]),
            victim_steamid=_as_str(row["victim_steamid"]),
            victim_name=_as_str(row["victim_name"]),
            victim_side=_as_str(row["victim_side"]),
            weapon=_as_str(row["weapon"], "unknown"),
            headshot=bool(row["headshot"]),
        )
        for row in kills.iter_rows(named=True)
        if row["attacker_steamid"] is not None
    ]
    return sorted(result, key=lambda k: k.tick)


def kills_by_player(kills: list[Kill], steamid: str) -> list[Kill]:
    """Kills credited to one player."""
    return [k for k in kills if k.attacker_steamid == steamid]


def deaths_of_player(kills: list[Kill], steamid: str) -> list[Kill]:
    """Kill events where this player was the victim."""
    return [k for k in kills if k.victim_steamid == steamid]
