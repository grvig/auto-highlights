"""Builders for hand-made engine data in tests.

Detectors are pure functions of a DetectionContext, so tests construct small
synthetic matches rather than parsing a demo. These keep that construction terse.
"""

from __future__ import annotations

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Blind, Damage, Kill, Round


def make_damage(
    tick: int,
    attacker: str,
    victim: str,
    *,
    round_number: int = 1,
    attacker_side: str = "ct",
    victim_side: str = "t",
    weapon: str = "hegrenade",
    damage: int = 40,
) -> Damage:
    return Damage(
        round_number=round_number,
        tick=tick,
        attacker_steamid=attacker,
        attacker_name=f"att-{attacker}",
        attacker_side=attacker_side,
        victim_steamid=victim,
        victim_side=victim_side,
        weapon=weapon,
        damage=damage,
    )


def make_blind(
    tick: int,
    flasher: str,
    victim: str,
    *,
    duration: float = 2.0,
) -> Blind:
    return Blind(
        tick=tick,
        flasher_steamid=flasher,
        flasher_name=f"f-{flasher}",
        victim_steamid=victim,
        victim_name=f"v-{victim}",
        duration_seconds=duration,
    )


def make_round(number: int, start: int = 0, end: int = 5000, winner: str = "ct") -> Round:
    return Round(
        number=number,
        start_tick=start,
        freeze_end_tick=start + 100,
        end_tick=end,
        official_end_tick=end + 100,
        winner=winner,
        reason="elimination",
    )


def make_kill(
    tick: int,
    attacker: str,
    victim: str,
    *,
    round_number: int = 1,
    attacker_side: str = "ct",
    victim_side: str = "t",
    weapon: str = "ak47",
    headshot: bool = False,
) -> Kill:
    return Kill(
        round_number=round_number,
        tick=tick,
        attacker_steamid=attacker,
        attacker_name=f"att-{attacker}",
        attacker_side=attacker_side,
        victim_steamid=victim,
        victim_name=f"vic-{victim}",
        victim_side=victim_side,
        weapon=weapon,
        headshot=headshot,
    )


def make_context(
    kills: list[Kill],
    rounds: list[Round] | None = None,
    *,
    round_rosters: dict[int, dict[str, str]] | None = None,
    blinds: list[Blind] | None = None,
    damages: list[Damage] | None = None,
    pre_roll: float = 3.0,
    post_roll: float = 2.0,
    first_tick: int = 0,
    last_tick: int = 1_000_000,
) -> DetectionContext:
    return DetectionContext(
        rounds=rounds or [make_round(1)],
        kills=kills,
        first_tick=first_tick,
        last_tick=last_tick,
        pre_roll_seconds=pre_roll,
        post_roll_seconds=post_roll,
        tickrate=64,
        round_rosters=round_rosters or {},
        blinds=blinds or [],
        damages=damages or [],
    )
