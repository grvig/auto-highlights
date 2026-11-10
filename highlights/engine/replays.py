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
# Only sequences whose kills average this close together get victim cams;
# kills spread across a round have no rapid sequence worth reliving.
REPLAY_MAX_GAP_SECONDS = 4.0
# Playback speed of victim cams (1.0 real time, lower for slow motion).
REPLAY_SPEED = 1.0

VICTIM_CAM_TAG = "victim cam"


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
    return tuple(
        Segment(
            max(kill.tick - lead, moment.start_tick),
            min(kill.tick + tail, moment.end_tick),
            pov_steamid=kill.victim_steamid,
            speed=REPLAY_SPEED,
        )
        for kill in kills
    )


def add_victim_replays(moments: list[Moment], ctx: DetectionContext) -> list[Moment]:
    """Attach victim cams to every quick multi-kill in a list of moments."""
    result: list[Moment] = []
    for moment in moments:
        replays = victim_replays(moment, moment_kills(moment, ctx.kills), ctx.tickrate)
        if replays:
            moment = replace(moment, replays=replays, tags=(*moment.tags, VICTIM_CAM_TAG))
        result.append(moment)
    return result
