"""Broadcast-style replays.

After a quick multi-kill, tournament broadcasts replay it from each victim's
eyes: every enemy walking into the angle and getting taken down. This builds
those replay segments: one per victim, watched from their camera, ending just
after the shot lands.
"""

from __future__ import annotations

from dataclasses import replace

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill
from highlights.engine.moments import Moment, Segment
from highlights.engine.scoring import KILL_TYPES, moment_kills
from highlights.engine.timing import seconds_to_ticks

# How much of each victim's approach to show before the shot.
VICTIM_LEAD_SECONDS = 2.5
# A beat after the shot so the death lands on screen.
VICTIM_TAIL_SECONDS = 0.4
# A later victim's replay starts this long after the previous victim died.
AFTER_PREVIOUS_KILL_SECONDS = 0.15
# Only sequences whose kills average this close together get victim cams;
# kills spread across a round have no rapid sequence worth reliving.
REPLAY_MAX_GAP_SECONDS = 4.0
# Playback speed of victim cams (1.0 real time, lower for slow motion).
REPLAY_SPEED = 1.0

VICTIM_CAM_TAG = "victim cam"

# A victim cam shorter than this on screen is slowed down to fill it, so a
# kill that came fractions of a second after the last one still reads.
MIN_REPLAY_SCREEN_SECONDS = 1.2
# Never slower than this; below it the game's animation looks choppy.
SLOWEST_REPLAY_SPEED = 0.4


def replay_speed(footage_seconds: float) -> float:
    """Playback speed for a victim cam with this much footage."""
    if footage_seconds <= 0:
        return SLOWEST_REPLAY_SPEED
    if footage_seconds / REPLAY_SPEED >= MIN_REPLAY_SCREEN_SECONDS:
        return REPLAY_SPEED
    return round(max(SLOWEST_REPLAY_SPEED, footage_seconds / MIN_REPLAY_SCREEN_SECONDS), 2)


def victim_replays(
    moment: Moment, kills: list[Kill], tickrate: int = 64
) -> tuple[Segment, ...]:
    """One replay per victim of a quick multi-kill, or none."""
    if moment.highlight_type not in KILL_TYPES or len(kills) < 2:
        return ()
    average_gap = (kills[-1].tick - kills[0].tick) / tickrate / (len(kills) - 1)
    if average_gap > REPLAY_MAX_GAP_SECONDS:
        return ()

    lead = seconds_to_ticks(VICTIM_LEAD_SECONDS, tickrate)
    tail = seconds_to_ticks(VICTIM_TAIL_SECONDS, tickrate)
    settle = seconds_to_ticks(AFTER_PREVIOUS_KILL_SECONDS, tickrate)
    replays: list[Segment] = []
    previous: Kill | None = None
    for kill in kills:
        start = max(kill.tick - lead, moment.start_tick)
        if previous is not None:
            # Never reach back past the previous victim's death: that kill has
            # had its own replay, and from here it would look like a teammate
            # watching someone else die.
            start = max(start, previous.tick + settle)
        start = min(start, kill.tick)
        end = min(kill.tick + tail, moment.end_tick)
        replays.append(Segment(
            start,
            end,
            pov_steamid=kill.victim_steamid,
            speed=replay_speed((end - start) / tickrate),
        ))
        previous = kill
    return tuple(replays)


def add_victim_replays(moments: list[Moment], ctx: DetectionContext) -> list[Moment]:
    """Attach victim cams to every quick multi-kill in a list of moments."""
    result: list[Moment] = []
    for moment in moments:
        replays = victim_replays(moment, moment_kills(moment, ctx.kills), ctx.tickrate)
        if replays:
            moment = replace(moment, replays=replays, tags=(*moment.tags, VICTIM_CAM_TAG))
        result.append(moment)
    return result
