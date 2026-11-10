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
