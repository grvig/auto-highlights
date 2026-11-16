"""Starting each clip where the fight starts.

A fixed lead-in before the first kill can open mid-spray or after the player
has already been hit. Here the player's own fighting just before a window
(their gunfire, and damage dealt or taken) is followed back while it keeps
going, and the window starts a beat before it, so a clip shows the whole
exchange. The reach-back is capped and never crosses into the previous
window or round.
"""

from __future__ import annotations

from dataclasses import replace

from highlights.engine.detection import DetectionContext
from highlights.engine.moments import Moment
from highlights.engine.scoring import is_gunfire
from highlights.engine.timing import seconds_to_ticks

# Fighting events further apart than this are separate exchanges.
EXCHANGE_GAP_SECONDS = 2.5
# Never reach back more than this beyond the planned start.
MAX_EXTRA_SECONDS = 8.0
# Seconds kept before the first shot or hit of the fight.
BEFORE_FIGHT_SECONDS = 1.5


def fight_ticks(ctx: DetectionContext, player: str) -> list[int]:
    """Every tick the player fired a gun, hit someone, or was hit."""
    ticks = [s.tick for s in ctx.shots if s.shooter_steamid == player and is_gunfire(s)]
    ticks += [d.tick for d in ctx.damages if player in (d.attacker_steamid, d.victim_steamid)]
    return sorted(ticks)


def fight_start(start_tick: int, ticks: list[int], floor: int, tickrate: int = 64) -> int:
    """The planned start, pulled back to cover an exchange already under way."""
    gap = seconds_to_ticks(EXCHANGE_GAP_SECONDS, tickrate)
    limit = max(floor, start_tick - seconds_to_ticks(MAX_EXTRA_SECONDS, tickrate))
    earliest = None
    cursor = start_tick
    for tick in reversed([t for t in ticks if limit <= t < start_tick]):
        if cursor - tick > gap:
            break
        earliest = cursor = tick
    if earliest is None:
        return start_tick
    return max(limit, earliest - seconds_to_ticks(BEFORE_FIGHT_SECONDS, tickrate))


def extend_to_fights(moments: list[Moment], ctx: DetectionContext) -> list[Moment]:
    """Open each of the player's windows at the start of its fight."""
    result: list[Moment] = []
    for moment in moments:
        ticks = fight_ticks(ctx, moment.player_steamid)
        rnd = ctx.round_by_number(moment.round_number)
        floor = max(ctx.first_tick, rnd.start_tick if rnd else ctx.first_tick)
        windows, previous_end = [], floor
        for window in moment.windows:
            start = window.start_tick
            if window.pov_steamid is None:
                start = fight_start(window.start_tick, ticks, previous_end, ctx.tickrate)
            windows.append(replace(window, start_tick=start))
            previous_end = window.end_tick + 1
        new_start = min(moment.start_tick, windows[0].start_tick)
        result.append(replace(moment, start_tick=new_start, segments=tuple(windows)))
    return result
