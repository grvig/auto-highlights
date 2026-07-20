"""Flash utility detector.

Emits a UTILITY moment when the chosen player throws one flashbang that blinds
multiple enemies meaningfully — a pop-flash with real impact — rather than every
incidental blink. Self-flashes and team-flashes are excluded by comparing sides
within the round.
"""

from __future__ import annotations

from collections import defaultdict

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Blind
from highlights.engine.moments import HighlightType, Moment

# A blink shorter than this is a graze, not impact.
FLASH_MIN_SECONDS = 0.7
# How many enemies one flash must blind to count as a highlight.
MIN_ENEMIES_FLASHED = 2


def _enemy_flashes(
    ctx: DetectionContext, player_steamid: str
) -> list[Blind]:
    """The player's flashes that blinded an enemy for a meaningful duration."""
    result: list[Blind] = []
    for blind in ctx.blinds:
        if blind.flasher_steamid != player_steamid:
            continue
        if blind.victim_steamid == player_steamid:
            continue
        if blind.duration_seconds < FLASH_MIN_SECONDS:
            continue
        rnd = ctx.round_of_tick(blind.tick)
        if rnd is None:
            continue
        flasher_side = ctx.side_of(player_steamid, rnd.number)
        victim_side = ctx.side_of(blind.victim_steamid, rnd.number)
        if flasher_side is None or victim_side is None:
            continue
        if flasher_side != victim_side:
            result.append(blind)
    return result


class FlashUtilityDetector:
    """Single flashes that blind two or more enemies."""

    highlight_type = HighlightType.UTILITY

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        # Group by the throw: same flasher, same detonation tick.
        by_tick: dict[int, list[Blind]] = defaultdict(list)
        for blind in _enemy_flashes(ctx, player_steamid):
            by_tick[blind.tick].append(blind)

        moments: list[Moment] = []
        for tick, blinds in by_tick.items():
            if len(blinds) < MIN_ENEMIES_FLASHED:
                continue
            rnd = ctx.round_of_tick(tick)
            longest = max(b.duration_seconds for b in blinds)
            start, end = ctx.pad(tick)
            moments.append(
                Moment(
                    round_number=rnd.number,
                    highlight_type=self.highlight_type,
                    player_steamid=player_steamid,
                    core_tick=tick,
                    start_tick=start,
                    end_tick=end,
                    description=f"Flashed {len(blinds)} enemies ({longest:.1f}s)",
                )
            )
        return sorted(moments, key=lambda m: m.core_tick)
