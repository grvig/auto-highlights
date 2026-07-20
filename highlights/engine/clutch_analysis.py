"""Clutch situation analysis.

Pure reasoning over a round's kills and roster: was the chosen player the last
one standing on their team, against how many enemies, and did they pull it off?
No Moment building here — the detector layer turns a ClutchSituation into a
Moment. Kept separate so the tricky alive-tracking is testable on its own.

Note: analysis works off recorded kills, which exclude attacker-less world
deaths (fall, bomb). A teammate dying that way is not counted, so the effect is
at worst a missed clutch, never a false one.
"""

from __future__ import annotations

from dataclasses import dataclass

from highlights.engine.models import Kill


@dataclass(frozen=True)
class ClutchSituation:
    """A 1-vs-N the player found themselves in during a round."""

    round_number: int
    # Tick the clutch began — when the player's last teammate died.
    start_tick: int
    # Enemies still alive at that moment (the N in 1vN).
    enemies_at_start: int
    won: bool

    @property
    def label(self) -> str:
        outcome = "won" if self.won else "lost"
        return f"1v{self.enemies_at_start} clutch ({outcome})"


def analyse_clutch(
    round_number: int,
    round_winner: str,
    player_steamid: str,
    player_side: str,
    teammates: set[str],
    enemies: set[str],
    round_kills: list[Kill],
) -> ClutchSituation | None:
    """Return the ClutchSituation for a player in a round, or None.

    A clutch requires every teammate to die while the player is still alive and
    at least one enemy remains. Whether it was won is decided by the round
    winner, so time-outs and defuses count, not just eliminations.
    """
    alive_teammates = set(teammates)
    alive_enemies = set(enemies)
    player_dead = False
    clutch_start_tick: int | None = None

    for kill in sorted(round_kills, key=lambda k: k.tick):
        victim = kill.victim_steamid
        if victim == player_steamid:
            player_dead = True
        alive_teammates.discard(victim)
        alive_enemies.discard(victim)

        # The instant the last teammate falls and the player is still up with
        # enemies remaining, the clutch begins.
        if (
            clutch_start_tick is None
            and not player_dead
            and not alive_teammates
            and alive_enemies
        ):
            clutch_start_tick = kill.tick
            enemies_at_start = len(alive_enemies)

    if clutch_start_tick is None:
        return None

    won = round_winner == player_side and not player_dead
    return ClutchSituation(
        round_number=round_number,
        start_tick=clutch_start_tick,
        enemies_at_start=enemies_at_start,
        won=won,
    )
