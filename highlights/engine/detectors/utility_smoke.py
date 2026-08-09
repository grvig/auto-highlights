"""Smoke utility detector.

Judging whether a smoke *mattered* has no clean signal in the demo, so this
uses a deliberate proxy: a smoke is a highlight when an enemy dies near where it
lands, soon after it lands. That catches smokes that shaped a winning duel and
skips the routine map-control throws into empty space.

It is a heuristic, not ground truth — a lurk kill that happens to be near an
unrelated smoke will occasionally qualify. The thresholds are tuned to keep
those rare rather than trying to eliminate them.
"""

from __future__ import annotations

import math

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill, Smoke
from highlights.engine.moments import HighlightType, Moment
from highlights.engine.timing import seconds_to_ticks

# How soon after detonation a kill still counts as shaped by the smoke.
SMOKE_IMPACT_SECONDS = 12.0
# How close to the detonation point the kill must be, in map units.
SMOKE_IMPACT_RADIUS = 600.0


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def _enemy_kills_near_smoke(
    ctx: DetectionContext, smoke: Smoke, thrower_side: str
) -> list[Kill]:
    """Enemy deaths within the smoke's window and radius."""
    window = seconds_to_ticks(SMOKE_IMPACT_SECONDS, ctx.tickrate)
    hits: list[Kill] = []
    for kill in ctx.kills:
        if not (smoke.tick <= kill.tick <= smoke.tick + window):
            continue
        if kill.victim_side == thrower_side:
            continue  # a teammate dying near the smoke is not the smoke helping
        if _distance(smoke.x, smoke.y, kill.victim_x, kill.victim_y) <= SMOKE_IMPACT_RADIUS:
            hits.append(kill)
    return hits


class SmokeUtilityDetector:
    """Smokes by the player that set up a nearby enemy kill."""

    highlight_type = HighlightType.UTILITY

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        moments: list[Moment] = []
        for smoke in ctx.smokes:
            if smoke.thrower_steamid != player_steamid:
                continue
            rnd = ctx.round_of_tick(smoke.tick)
            if rnd is None:
                continue
            thrower_side = ctx.side_of(player_steamid, rnd.number)
            if thrower_side is None:
                continue
            hits = _enemy_kills_near_smoke(ctx, smoke, thrower_side)
            if not hits:
                continue
            start, end = ctx.pad(smoke.tick)
            count = len(hits)
            noun = "kill" if count == 1 else "kills"
            moments.append(
                Moment(
                    round_number=rnd.number,
                    highlight_type=self.highlight_type,
                    player_steamid=player_steamid,
                    core_tick=smoke.tick,
                    start_tick=start,
                    end_tick=end,
                    description=f"Smoke set up {count} {noun}",
                )
            )
        return sorted(moments, key=lambda m: m.core_tick)
