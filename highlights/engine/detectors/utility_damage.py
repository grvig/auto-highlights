"""Utility-damage detector.

Emits a UTILITY moment when the chosen player's grenade damage in a round is
worth showing. HE and fire (molotov/incendiary) are grouped separately per
round, since they are different plays. Fire damage is summed across its burn.

Grouping is per round and category, so two molotovs in the same round merge
into one moment — acceptable given the generous clip padding around it.
"""

from __future__ import annotations

from collections import defaultdict

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Damage
from highlights.engine.moments import HighlightType, Moment

HE_WEAPONS = {"hegrenade"}
FIRE_WEAPONS = {"inferno", "molotov", "incgrenade"}

# Total health a grenade must remove in a round to be a highlight.
MIN_UTILITY_DAMAGE = 40

_CATEGORY_LABEL = {"he": "HE grenade", "fire": "Molotov"}


def _category(weapon: str) -> str | None:
    if weapon in HE_WEAPONS:
        return "he"
    if weapon in FIRE_WEAPONS:
        return "fire"
    return None


class UtilityDamageDetector:
    """Grenade damage by the player that clears a per-round threshold."""

    highlight_type = HighlightType.UTILITY

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        # (round, category) -> damage events by this player.
        groups: dict[tuple[int, str], list[Damage]] = defaultdict(list)
        for dmg in ctx.damages:
            if dmg.attacker_steamid != player_steamid:
                continue
            category = _category(dmg.weapon)
            if category is None:
                continue
            groups[(dmg.round_number, category)].append(dmg)

        moments: list[Moment] = []
        for (round_number, category), events in groups.items():
            total = sum(d.damage for d in events)
            if total < MIN_UTILITY_DAMAGE:
                continue
            ticks = [d.tick for d in events]
            first, last = min(ticks), max(ticks)
            start, end = ctx.pad(first, span_start_tick=first, span_end_tick=last)
            label = _CATEGORY_LABEL[category]
            moments.append(
                Moment(
                    round_number=round_number,
                    highlight_type=self.highlight_type,
                    player_steamid=player_steamid,
                    core_tick=first,
                    start_tick=start,
                    end_tick=end,
                    description=f"{label} dealt {total} damage",
                )
            )
        return sorted(moments, key=lambda m: m.core_tick)
