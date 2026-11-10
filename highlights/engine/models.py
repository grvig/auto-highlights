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


# A kill from at least this far (in metres) counts as long range.
LONG_RANGE_METRES = 30.0


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
    # Where the victim died, in map units. Defaulted so hand-built Kills in
    # tests need not supply them; used to correlate kills with nearby utility.
    victim_x: float = 0.0
    victim_y: float = 0.0
    # How the kill happened — the details that make a frag worth showing.
    wallbang: bool = False
    through_smoke: bool = False
    noscope: bool = False
    attacker_blind: bool = False
    attacker_airborne: bool = False
    # Distance to the victim in metres, as the game reports it.
    distance: float = 0.0

    @property
    def timestamp(self) -> str:
        return format_timestamp(self.tick)

    @property
    def style_tags(self) -> tuple[str, ...]:
        """Short labels for what made this kill special, most striking first."""
        flags = (
            (self.noscope, "noscope"),
            (self.wallbang, "wallbang"),
            (self.through_smoke, "through smoke"),
            (self.attacker_airborne, "airborne"),
            (self.attacker_blind, "while flashed"),
            (self.distance >= LONG_RANGE_METRES, "long range"),
            (self.headshot, "headshot"),
        )
        return tuple(label for active, label in flags if active)

    def __str__(self) -> str:
        how = " (hs)" if self.headshot else ""
        return (
            f"R{self.round_number} {self.timestamp} "
            f"{self.attacker_name} killed {self.victim_name} "
            f"with {self.weapon}{how}"
        )


@dataclass(frozen=True)
class Smoke:
    """A smoke grenade detonating (a smokegrenade_detonate event)."""

    tick: int
    thrower_steamid: str
    thrower_name: str
    x: float
    y: float


@dataclass(frozen=True)
class Blind:
    """One player being flashed by another (a player_blind event)."""

    tick: int
    flasher_steamid: str
    flasher_name: str
    victim_steamid: str
    victim_name: str
    duration_seconds: float


@dataclass(frozen=True)
class Damage:
    """One damage event (a player_hurt)."""

    round_number: int
    tick: int
    attacker_steamid: str
    attacker_name: str
    attacker_side: str
    victim_steamid: str
    victim_side: str
    weapon: str
    # Health actually removed, capped at the victim's remaining health.
    damage: int


def _as_int(value: object, default: int = 0) -> int:
    return default if value is None else int(value)


def _as_str(value: object, default: str = "") -> str:
    return default if value is None else str(value)


def _as_float(value: object, default: float = 0.0) -> float:
    return default if value is None else float(value)


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
            victim_x=_as_float(row.get("victim_X")),
            victim_y=_as_float(row.get("victim_Y")),
            # penetrated counts the surfaces the bullet went through.
            wallbang=_as_int(row.get("penetrated")) > 0,
            through_smoke=bool(row.get("thrusmoke")),
            noscope=bool(row.get("noscope")),
            attacker_blind=bool(row.get("attackerblind")),
            attacker_airborne=bool(row.get("attackerinair")),
            distance=_as_float(row.get("distance")),
        )
        for row in kills.iter_rows(named=True)
        if row["attacker_steamid"] is not None
    ]
    return sorted(result, key=lambda k: k.tick)


def extract_smokes(smokes: pl.DataFrame) -> list[Smoke]:
    """Convert awpy's smokegrenade_detonate frame into Smoke models, tick-ordered.

    The event's user_* fields are the thrower; x/y are the detonation point.
    Rows with no thrower are dropped.
    """
    result = [
        Smoke(
            tick=_as_int(row["tick"]),
            thrower_steamid=_as_str(row["user_steamid"]),
            thrower_name=_as_str(row["user_name"]),
            x=_as_float(row.get("x")),
            y=_as_float(row.get("y")),
        )
        for row in smokes.iter_rows(named=True)
        if row["user_steamid"] is not None
    ]
    return sorted(result, key=lambda s: s.tick)


def extract_blinds(blinds: pl.DataFrame) -> list[Blind]:
    """Convert awpy's player_blind event frame into Blind models, tick-ordered.

    The event's user_* fields are the blinded victim and attacker_* the flasher.
    Rows with no flasher steamid are dropped.
    """
    result = [
        Blind(
            tick=_as_int(row["tick"]),
            flasher_steamid=_as_str(row["attacker_steamid"]),
            flasher_name=_as_str(row["attacker_name"]),
            victim_steamid=_as_str(row["user_steamid"]),
            victim_name=_as_str(row["user_name"]),
            duration_seconds=float(row["blind_duration"] or 0.0),
        )
        for row in blinds.iter_rows(named=True)
        if row["attacker_steamid"] is not None
    ]
    return sorted(result, key=lambda b: b.tick)


def extract_damages(damages: pl.DataFrame) -> list[Damage]:
    """Convert awpy's damages frame into Damage models, tick-ordered.

    Uses dmg_health_real (health actually removed) rather than raw damage, so
    over-damage on a nearly-dead victim is not counted. Rows with no attacker
    (world damage) are dropped.
    """
    real = "dmg_health_real" if "dmg_health_real" in damages.columns else "dmg_health"
    result = [
        Damage(
            round_number=_as_int(row["round_num"]),
            tick=_as_int(row["tick"]),
            attacker_steamid=_as_str(row["attacker_steamid"]),
            attacker_name=_as_str(row["attacker_name"]),
            attacker_side=_as_str(row["attacker_side"]),
            victim_steamid=_as_str(row["victim_steamid"]),
            victim_side=_as_str(row["victim_side"]),
            weapon=_as_str(row["weapon"], "unknown"),
            damage=_as_int(row[real]),
        )
        for row in damages.iter_rows(named=True)
        if row["attacker_steamid"] is not None
    ]
    return sorted(result, key=lambda d: d.tick)


def kills_by_player(kills: list[Kill], steamid: str) -> list[Kill]:
    """Kills credited to one player."""
    return [k for k in kills if k.attacker_steamid == steamid]


def deaths_of_player(kills: list[Kill], steamid: str) -> list[Kill]:
    """Kill events where this player was the victim."""
    return [k for k in kills if k.victim_steamid == steamid]
