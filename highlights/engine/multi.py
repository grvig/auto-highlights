"""Plans that span several demos.

A frag movie often draws on many matches. Each match is planned on its own for
the same player, matched by SteamID so a name change between matches does not
lose them, and the results are pooled into one plan. Matches the player was not
in are reported rather than silently skipped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from highlights.config import ClipConfig
from highlights.engine.clip_plan import ClipPlan, build_clip_plan
from highlights.engine.demo_source import DemoSource, Player
from highlights.engine.detection import DetectionContext
from highlights.engine.moments import HighlightType


@dataclass(frozen=True)
class Match:
    """One demo, ready to plan from."""

    label: str
    players: list[Player]
    context: DetectionContext

    def find(self, steamid: str) -> Player | None:
        return next((p for p in self.players if p.steamid == steamid), None)


@dataclass(frozen=True)
class MultiPlan:
    """The pooled plan plus what happened in each match."""

    plan: ClipPlan
    moments_per_match: dict[str, int] = field(default_factory=dict)
    missing_from: list[str] = field(default_factory=list)


def match_from_source(source: DemoSource, timing: ClipConfig | None = None) -> Match:
    """A demo ready to plan from, padded with the configured clip timing."""
    label = f"{source.info.map_name} ({source.path.name})"
    timing = timing or ClipConfig()
    return Match(
        label=label,
        players=source.players(),
        context=DetectionContext.from_source(
            source, timing.pre_roll_seconds, timing.post_roll_seconds, timing.merge_gap_seconds
        ),
    )


def players_across(matches: Iterable[Match]) -> list[tuple[Player, int]]:
    """Every player seen, with how many of the matches they appear in.

    Keyed by SteamID; the name shown is the most recent one used.
    """
    seen: dict[str, tuple[Player, int]] = {}
    for match in matches:
        for player in match.players:
            _, count = seen.get(player.steamid, (player, 0))
            seen[player.steamid] = (player, count + 1)
    return sorted(seen.values(), key=lambda item: (-item[1], item[0].name.lower()))


def build_multi_plan(
    matches: list[Match],
    steamid: str,
    selected_types: Iterable[HighlightType],
    slowmo: bool = False,
    replays: bool = True,
) -> MultiPlan:
    """Plan each match for one player and pool the moments, match by match."""
    types = tuple(dict.fromkeys(selected_types))
    moments = []
    per_match: dict[str, int] = {}
    missing: list[str] = []
    for match in matches:
        if match.find(steamid) is None:
            missing.append(match.label)
            continue
        plan = build_clip_plan(match.context, steamid, types, slowmo=slowmo, replays=replays)
        per_match[match.label] = len(plan)
        moments.extend(plan.moments)

    pooled = ClipPlan(player_steamid=steamid, selected_types=types, moments=moments)
    return MultiPlan(plan=pooled, moments_per_match=per_match, missing_from=missing)
