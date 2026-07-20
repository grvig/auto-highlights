"""Single-kill detector.

One Moment per kill the chosen player got. Multi-kill and ace clustering live
in their own detectors; this one is deliberately the simplest — every frag is a
candidate highlight, and dedup against richer moments happens in the builder.
"""

from __future__ import annotations

from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill, kills_by_player
from highlights.engine.moments import HighlightType, Moment


def describe_kill(kill: Kill) -> str:
    weapon = kill.weapon or "unknown"
    how = " headshot" if kill.headshot else ""
    return f"Killed {kill.victim_name} ({weapon}{how})"


class SingleKillDetector:
    """Emits a KILL moment for every kill credited to the player."""

    highlight_type = HighlightType.KILL

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        moments: list[Moment] = []
        for kill in kills_by_player(ctx.kills, player_steamid):
            start, end = ctx.pad(kill.tick)
            moments.append(
                Moment(
                    round_number=kill.round_number,
                    highlight_type=self.highlight_type,
                    player_steamid=player_steamid,
                    core_tick=kill.tick,
                    start_tick=start,
                    end_tick=end,
                    description=describe_kill(kill),
                )
            )
        return sorted(moments, key=lambda m: m.core_tick)
