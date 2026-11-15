"""Speed ramps: slowing the instant of each kill inside the player's own view.

Frag movies dip into slow motion as the shot lands and snap back to real time
straight after. Here each of the player's kills in a moment gets a short span
around its tick marked on the segment that contains it; the recorder plays
the footage once and the finishing step stretches just those spans.
"""

from __future__ import annotations

from dataclasses import replace

from highlights.engine.detection import DetectionContext
from highlights.engine.moments import Moment, Segment
from highlights.engine.scoring import KILL_TYPES, moment_kills
from highlights.engine.timing import seconds_to_ticks

# Slow from just before the shot until the body drops.
BEFORE_KILL_SECONDS = 0.15
AFTER_KILL_SECONDS = 0.35
RAMP_SPEED = 0.4

SLOWMO_TAG = "slow-mo"


def kill_ramps(
    segment: Segment, kill_ticks: list[int], tickrate: int = 64
) -> tuple[tuple[int, int], ...]:
    """Ramp spans for the kills inside this segment, merged where they touch."""
    before = seconds_to_ticks(BEFORE_KILL_SECONDS, tickrate)
    after = seconds_to_ticks(AFTER_KILL_SECONDS, tickrate)
    spans: list[list[int]] = []
    for tick in sorted(t for t in kill_ticks if segment.start_tick <= t <= segment.end_tick):
        start = max(segment.start_tick, tick - before)
        end = min(segment.end_tick, tick + after)
        if end <= start:
            continue
        if spans and start <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    return tuple((start, end) for start, end in spans)


def mark_kills(moments: list[Moment], ctx: DetectionContext) -> list[Moment]:
    """Note the player's kills (and headshots) on each of their own windows."""
    result: list[Moment] = []
    for moment in moments:
        kills = moment_kills(moment, ctx.kills) if moment.highlight_type in KILL_TYPES else []
        if not kills:
            result.append(moment)
            continue
        windows = []
        for w in moment.windows:
            inside = [k for k in kills if w.start_tick <= k.tick <= w.end_tick]
            windows.append(replace(
                w,
                kill_ticks=tuple(k.tick for k in inside),
                headshot_ticks=tuple(k.tick for k in inside if k.headshot),
            ) if w.pov_steamid is None else w)
        result.append(replace(moment, segments=tuple(windows)))
    return result


def add_kill_ramps(
    moments: list[Moment], ctx: DetectionContext, ramp_speed: float = RAMP_SPEED
) -> list[Moment]:
    """Ramp every kill in the player's own footage. Replays are left as they are."""
    result: list[Moment] = []
    for moment in moments:
        if moment.highlight_type not in KILL_TYPES:
            result.append(moment)
            continue
        ticks = [kill.tick for kill in moment_kills(moment, ctx.kills)]
        windows = tuple(
            replace(w, ramps=kill_ramps(w, ticks, ctx.tickrate), ramp_speed=ramp_speed)
            if w.speed == 1.0 and w.pov_steamid is None else w
            for w in moment.windows
        )
        if any(w.ramps for w in windows):
            moment = replace(moment, segments=windows, tags=(*moment.tags, SLOWMO_TAG))
        result.append(moment)
    return result
