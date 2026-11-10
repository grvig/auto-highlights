"""Scoring how good a moment is.

Detection decides what happened; scoring decides how much it is worth showing.
Each signal is a small pure function returning points and the tags that
explain them, so the final ranking is easy to inspect and tune.
"""

from __future__ import annotations

from highlights.engine.models import Kill
from highlights.engine.moments import Moment

# Points per style detail on a kill. Rare, hard plays are worth the most.
STYLE_POINTS = {
    "noscope": 3.0,
    "wallbang": 2.5,
    "through smoke": 2.0,
    "airborne": 2.0,
    "while flashed": 2.0,
    "long range": 1.0,
    "headshot": 0.5,
}


def moment_kills(moment: Moment, kills: list[Kill]) -> list[Kill]:
    """The player's own kills inside a moment, in tick order.

    A death moment has none (the player is the victim); a multi-kill or clutch
    has every frag the player made within its window.
    """
    return sorted(
        (
            kill
            for kill in kills
            if kill.attacker_steamid == moment.player_steamid
            and kill.round_number == moment.round_number
            and moment.start_tick <= kill.tick <= moment.end_tick
        ),
        key=lambda kill: kill.tick,
    )


def style_points(kill: Kill) -> float:
    return sum(STYLE_POINTS.get(tag, 0.0) for tag in kill.style_tags)


def style_score(moment_kills: list[Kill]) -> tuple[float, tuple[str, ...]]:
    """Style points across a moment's kills, plus the distinct tags earned.

    Headshots are common enough that they add points but are not called out
    as a tag on their own.
    """
    points = sum(style_points(kill) for kill in moment_kills)
    tags: list[str] = []
    for kill in moment_kills:
        for tag in kill.style_tags:
            if tag != "headshot" and tag not in tags:
                tags.append(tag)
    return points, tuple(tags)


# A multi-kill whose kills average this far apart (seconds) earns no tempo
# points; faster sequences earn up to TEMPO_POINTS per extra kill.
TEMPO_WINDOW_SECONDS = 10.0
TEMPO_POINTS = 2.0
# Average gap at or under which a multi-kill is called out as fast.
FAST_GAP_SECONDS = 4.0

# Points for winning a clutch against N enemies alone.
CLUTCH_POINTS = {1: 2.0, 2: 4.0, 3: 6.5, 4: 9.0, 5: 12.0}


def tempo_score(
    moment_kills: list[Kill], tickrate: int = 64
) -> tuple[float, tuple[str, ...]]:
    """Points for kills strung together quickly, tagged like "3 kills in 3.7s"."""
    if len(moment_kills) < 2:
        return 0.0, ()
    span = (moment_kills[-1].tick - moment_kills[0].tick) / tickrate
    average_gap = span / (len(moment_kills) - 1)
    speed = max(0.0, 1.0 - average_gap / TEMPO_WINDOW_SECONDS)
    points = TEMPO_POINTS * (len(moment_kills) - 1) * speed
    tags = (f"{len(moment_kills)} kills in {span:.1f}s",) if average_gap <= FAST_GAP_SECONDS else ()
    return points, tags


def clutch_score(moment: Moment) -> tuple[float, tuple[str, ...]]:
    """Points for the size of a won clutch, tagged like "1v3"."""
    if moment.opponents <= 0:
        return 0.0, ()
    points = CLUTCH_POINTS.get(moment.opponents, CLUTCH_POINTS[5])
    return points, (f"1v{moment.opponents}",)
