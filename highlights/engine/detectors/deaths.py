"""Death detector.

One DEATH moment for each time the chosen player was killed. Useful for
lowlight reels and for reviewing how a player died. World deaths are already
excluded upstream, so every death here has a killer.
"""

from __future__ import annotations

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill, deaths_of_player
from highlights.engine.moments import HighlightType, Moment


def describe_death(kill: Kill) -> str:
    weapon = kill.weapon or "unknown"
    how = " headshot" if kill.headshot else ""
    return f"Died to {kill.attacker_name} ({weapon}{how})"


class DeathDetector:
    """Emits a DEATH moment for every death the player suffered."""

    highlight_type = HighlightType.DEATH

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        moments: list[Moment] = []
        for kill in deaths_of_player(ctx.kills, player_steamid):
            start, end = ctx.pad(kill.tick)
            moments.append(
                Moment(
                    round_number=kill.round_number,
                    highlight_type=self.highlight_type,
                    player_steamid=player_steamid,
                    core_tick=kill.tick,
                    start_tick=start,
                    end_tick=end,
                    description=describe_death(kill),
                )
            )
        return sorted(moments, key=lambda m: m.core_tick)
