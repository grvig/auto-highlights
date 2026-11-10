"""Scoring how good a moment is.

Detection decides what happened; scoring decides how much it is worth showing.
Each signal is a small pure function returning points and the tags that
explain them, so the final ranking is easy to inspect and tune.
"""

from __future__ import annotations

from dataclasses import replace

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill
from highlights.engine.moments import HighlightType, Moment

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


# Round win chance from alive counts: own^k / (own^k + enemy^k). With k = 2.2
# this lands near commonly reported CS man-advantage rates (1v1 50%, 1v2 ~18%,
# 1v3 ~8%, 2v1 ~82%). A heuristic, not a trained model; bomb state is not yet
# included.
WIN_PROBABILITY_EXPONENT = 2.2
# Points for swinging a round from certain loss to certain win.
IMPACT_POINTS = 10.0
# Total swing at or above which a moment is called out as round-deciding.
SWING_TAG_THRESHOLD = 0.4


def win_probability(own_alive: int, enemy_alive: int) -> float:
    """Chance a side wins the round given how many are alive on each side."""
    if own_alive <= 0:
        return 0.0
    if enemy_alive <= 0:
        return 1.0
    own = own_alive**WIN_PROBABILITY_EXPONENT
    enemy = enemy_alive**WIN_PROBABILITY_EXPONENT
    return own / (own + enemy)


def alive_before(
    kill: Kill, round_kills: list[Kill], roster: dict[str, str]
) -> tuple[int, int]:
    """Players alive on the killer's side and the enemy side just before a kill."""
    side = roster.get(kill.attacker_steamid, kill.attacker_side)
    own = {sid for sid, s in roster.items() if s == side}
    enemy = {sid for sid, s in roster.items() if s != side}
    for earlier in round_kills:
        if earlier.tick >= kill.tick:
            continue
        own.discard(earlier.victim_steamid)
        enemy.discard(earlier.victim_steamid)
    return len(own), len(enemy)


def impact_score(
    moment_kills: list[Kill], round_kills: list[Kill], roster: dict[str, str]
) -> tuple[float, tuple[str, ...]]:
    """Points for how much the player's kills moved their side's win chance."""
    swing = 0.0
    for kill in moment_kills:
        own, enemy = alive_before(kill, round_kills, roster)
        swing += win_probability(own, enemy - 1) - win_probability(own, enemy)
    tags = ("swung the round",) if swing >= SWING_TAG_THRESHOLD else ()
    return swing * IMPACT_POINTS, tags


# Moment types that are about the player's own frags. Only these earn
# kill-based points; a death or utility clip that happens to contain a
# kill must not re-score a frag that already has its own clip.
KILL_TYPES = frozenset(
    {HighlightType.KILL, HighlightType.MULTI_KILL, HighlightType.ACE, HighlightType.CLUTCH}
)

# Starting points by highlight type, before the signals above are added.
BASE_POINTS = {
    HighlightType.ACE: 8.0,
    HighlightType.CLUTCH: 3.0,
    HighlightType.MULTI_KILL: 3.0,
    HighlightType.UTILITY: 1.5,
    HighlightType.KILL: 1.0,
    HighlightType.DEATH: 0.0,
}


def score_moment(moment: Moment, ctx: DetectionContext) -> Moment:
    """The moment with its score and the tags that explain it filled in."""
    kills = moment_kills(moment, ctx.kills) if moment.highlight_type in KILL_TYPES else []
    round_kills = sorted(
        (k for k in ctx.kills if k.round_number == moment.round_number),
        key=lambda k: k.tick,
    )
    roster = ctx.round_rosters.get(moment.round_number, {})
    parts = (
        clutch_score(moment),
        tempo_score(kills, ctx.tickrate),
        style_score(kills),
        impact_score(kills, round_kills, roster),
    )
    score = BASE_POINTS.get(moment.highlight_type, 0.0) + sum(p for p, _ in parts)
    tags = tuple(dict.fromkeys(tag for _, part_tags in parts for tag in part_tags))
    return replace(moment, score=round(score, 2), tags=tags)


def score_moments(moments: list[Moment], ctx: DetectionContext) -> list[Moment]:
    return [score_moment(moment, ctx) for moment in moments]
