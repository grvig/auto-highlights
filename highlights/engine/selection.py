"""Choosing and ordering the moments that make the reel.

A plan can hold a whole match's worth of moments. This picks the best ones to
fill a target length, keeps the mix varied, and arranges them the way a
montage is cut: a strong opener, a build, and the best moment last.
"""

from __future__ import annotations

from collections import Counter

from highlights.engine.moments import Moment

# Each repeat of the same highlight type or source match is worth this much
# less, so the reel mixes clutches, multi-kills and styles across matches.
VARIETY_DECAY = 0.8

ORDERS = ("montage", "chronological")


def _adjusted(moment: Moment, types: Counter, demos: Counter, variety: bool) -> float:
    if not variety:
        return moment.score
    repeats = types[moment.highlight_type] + demos[moment.source_demo]
    return moment.score * VARIETY_DECAY**repeats


def select_best(
    moments: list[Moment], target_seconds: float, *, variety: bool = True
) -> list[Moment]:
    """Pick the strongest moments until their footage fills target_seconds.

    Moments scoring nothing (deaths, routine frags) are never chosen. A moment
    longer than the time left is skipped in favour of shorter ones, but the
    first pick is always taken so a short target still yields a reel.
    """
    pool = [m for m in moments if m.score > 0]
    chosen: list[Moment] = []
    types: Counter = Counter()
    demos: Counter = Counter()
    used = 0.0
    while pool:
        best = max(pool, key=lambda m: _adjusted(m, types, demos, variety))
        pool.remove(best)
        if chosen and used + best.duration_seconds > target_seconds:
            continue
        chosen.append(best)
        used += best.duration_seconds
        types[best.highlight_type] += 1
        demos[best.source_demo] += 1
        if used >= target_seconds:
            break
    return chosen


def arrange(chosen: list[Moment], plan_order: list[Moment], order: str) -> list[Moment]:
    """Put the chosen moments in reel order.

    montage: the second-best opens as a hook, the rest build in score order,
    and the best closes the reel. chronological: the order they happened.
    """
    if order not in ORDERS:
        raise ValueError(f"Unknown order {order!r}; choose from {', '.join(ORDERS)}")
    if order == "chronological":
        keep = {id(m) for m in chosen}
        return [m for m in plan_order if id(m) in keep]
    rising = sorted(chosen, key=lambda m: m.score)
    if len(rising) < 3:
        return rising
    return [rising[-2], *rising[:-2], rising[-1]]
