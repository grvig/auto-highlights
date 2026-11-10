"""Clutch detector.

Turns won clutch situations into Moments. The brief defines a clutch as the
player being last alive on their team and winning the round, so lost attempts
are filtered out by default. The moment spans from when the clutch began to the
end of the round, so the clip shows the whole 1vN.
"""

from __future__ import annotations

from highlights.engine.clutch_analysis import ClutchSituation, analyse_clutch
from highlights.engine.detection import DetectionContext
from highlights.engine.models import Kill
from highlights.engine.moments import HighlightType, Moment


def _round_kills(kills: list[Kill], round_number: int) -> list[Kill]:
    return [k for k in kills if k.round_number == round_number]


def _teams(
    roster: dict[str, str], player_steamid: str, player_side: str
) -> tuple[set[str], set[str]]:
    teammates = {
        sid
        for sid, side in roster.items()
        if side == player_side and sid != player_steamid
    }
    enemies = {sid for sid, side in roster.items() if side != player_side}
    return teammates, enemies


class ClutchDetector:
    """Rounds the player won as the last one standing on their team."""

    highlight_type = HighlightType.CLUTCH

    def __init__(self, won_only: bool = True) -> None:
        self.won_only = won_only

    def _situation(
        self, ctx: DetectionContext, player_steamid: str, round_number: int
    ) -> ClutchSituation | None:
        rnd = ctx.round_by_number(round_number)
        player_side = ctx.side_of(player_steamid, round_number)
        if rnd is None or player_side is None:
            return None
        roster = ctx.round_rosters.get(round_number, {})
        teammates, enemies = _teams(roster, player_steamid, player_side)
        if not enemies:
            return None
        return analyse_clutch(
            round_number=round_number,
            round_winner=rnd.winner,
            player_steamid=player_steamid,
            player_side=player_side,
            teammates=teammates,
            enemies=enemies,
            round_kills=_round_kills(ctx.kills, round_number),
        )

    def detect(self, ctx: DetectionContext, player_steamid: str) -> list[Moment]:
        moments: list[Moment] = []
        for rnd in ctx.rounds:
            sit = self._situation(ctx, player_steamid, rnd.number)
            if sit is None or (self.won_only and not sit.won):
                continue
            segments = ctx.segments(self._beats(ctx, player_steamid, rnd, sit))
            moments.append(
                Moment(
                    round_number=rnd.number,
                    highlight_type=self.highlight_type,
                    player_steamid=player_steamid,
                    core_tick=sit.start_tick,
                    start_tick=segments[0].start_tick,
                    end_tick=segments[-1].end_tick,
                    description=sit.label,
                    segments=segments,
                    opponents=sit.enemies_at_start,
                )
            )
        return sorted(moments, key=lambda m: m.core_tick)

    @staticmethod
    def _beats(
        ctx: DetectionContext, player_steamid: str, rnd, sit: ClutchSituation
    ) -> list[int]:
        """The instants a clutch clip must show.

        When the player is left alone, each frag they make from there, and the
        finish. The standoffs in between are cut, so a slow 1v3 stays tense
        rather than turning into a minute of crouch-walking.
        """
        clutch_kills = [
            kill.tick
            for kill in _round_kills(ctx.kills, rnd.number)
            if kill.attacker_steamid == player_steamid and kill.tick >= sit.start_tick
        ]
        finish = max(rnd.end_tick, sit.start_tick)
        return [sit.start_tick, *clutch_kills, finish]
