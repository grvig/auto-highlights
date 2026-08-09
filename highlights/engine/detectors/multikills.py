"""Multi-kill and ace detectors.

Both group the chosen player's kills by round. Three or four kills in a round
is a multi-kill; five or more is an ace. The moment spans the first to the last
kill of the round so the clip shows the whole sequence, not just the finisher.
"""

from __future__ import annotations

from collections import defaultdict

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill, kills_by_player
from highlights.engine.moments import HighlightType, Moment

MULTI_KILL_MIN = 3
ACE_MIN = 5

_MULTI_KILL_NAMES = {2: "Double kill", 3: "Triple kill", 4: "Quad kill"}


def kills_by_round(kills: list[Kill], player_steamid: str) -> dict[int, list[Kill]]:
    """The player's kills, grouped by round and tick-ordered within each."""
    grouped: dict[int, list[Kill]] = defaultdict(list)
    for kill in kills_by_player(kills, player_steamid):
        grouped[kill.round_number].append(kill)
    for round_kills in grouped.values():
        round_kills.sort(key=lambda k: k.tick)
    return grouped


def _round_moment(
    ctx: DetectionContext,
    player_steamid: str,
    round_kills: list[Kill],
    highlight_type: HighlightType,
    description: str,
) -> Moment:
    first, last = round_kills[0], round_kills[-1]
    start, end = ctx.pad(
        last.tick,
        span_start_tick=first.tick,
        span_end_tick=last.tick,
        cap_span=True,
    )
    return Moment(
        round_number=first.round_number,
        highlight_type=highlight_type,
        player_steamid=player_steamid,
        core_tick=last.tick,
        start_tick=start,
        end_tick=end,
        description=description,
    )


class MultiKillDetector:
    """Rounds where the player got 3 or 4 kills."""

    highlight_type = HighlightType.MULTI_KILL

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        moments: list[Moment] = []
        for round_kills in kills_by_round(ctx.kills, player_steamid).values():
            count = len(round_kills)
            if MULTI_KILL_MIN <= count < ACE_MIN:
                name = _MULTI_KILL_NAMES.get(count, f"{count}K")
                moments.append(
                    _round_moment(
                        ctx,
                        player_steamid,
                        round_kills,
                        self.highlight_type,
                        f"{name} ({count} kills)",
                    )
                )
        return sorted(moments, key=lambda m: m.core_tick)


class AceDetector:
    """Rounds where the player got 5 or more kills."""

    highlight_type = HighlightType.ACE

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        moments: list[Moment] = []
        for round_kills in kills_by_round(ctx.kills, player_steamid).values():
            count = len(round_kills)
            if count >= ACE_MIN:
                moments.append(
                    _round_moment(
                        ctx,
                        player_steamid,
                        round_kills,
                        self.highlight_type,
                        f"ACE ({count} kills)",
                    )
                )
        return sorted(moments, key=lambda m: m.core_tick)
