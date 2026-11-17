"""Turning demos into a plan of which plays to show.

Loads the demos (through the parse cache), builds every highlight for one
player across them, and trims that down to the reel: the best plays, in reel
order. Front ends decide how to present each step.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

from highlights.config import ClipConfig, Config, ConfigError, load_config
from highlights.engine.cache import DemoCache
from highlights.engine.clip_plan import ClipPlan
from highlights.engine.demo_source import DemoSource
from highlights.engine.moments import HighlightType
from highlights.engine.multi import Match, build_multi_plan, match_from_source
from highlights.engine.scoring import moment_kills
from highlights.engine.selection import DEFAULT_MIN_SCORE, arrange, select_best
from highlights.pipeline.types import FRAG_TYPES


@dataclass(frozen=True)
class PlanOptions:
    types: tuple[HighlightType, ...] = FRAG_TYPES
    # Seconds of the best plays to keep; None keeps every play.
    best_seconds: float | None = None
    min_score: float = DEFAULT_MIN_SCORE
    order: str = "montage"
    slowmo: bool = False
    victim_cams: bool = False


@dataclass(frozen=True)
class Matches:
    """Demos loaded and ready to plan from, side by side."""

    sources: list[DemoSource]
    matches: list[Match]

    def player_names(self) -> dict[str, str]:
        """SteamID to in-game name across every demo."""
        return {p.steamid: p.name for s in self.sources for p in s.players()}

    def map_names(self) -> dict[Path, str]:
        return {s.path: s.info.map_name for s in self.sources}

    def pov_demos(self) -> list[str]:
        """Names of demos recorded from one player's view (not GOTV)."""
        return [s.path.name for s in self.sources if not s.info.is_gotv]


@dataclass(frozen=True)
class ReelPlan:
    plan: ClipPlan
    # Labels of loaded matches the player does not appear in.
    missing_from: list[str] = field(default_factory=list)


def open_cache(config: Config | None = None) -> DemoCache | None:
    """The parse cache from config, or None when there is no usable config."""
    try:
        return DemoCache((config or load_config()).resolved_cache_dir)
    except ConfigError:
        return None


def clip_timing(config: Config | None = None) -> ClipConfig:
    """How much of each engagement to keep, from config (defaults if none)."""
    try:
        return (config or load_config()).clips
    except ConfigError:
        return ClipConfig()


def load_matches(
    paths: Iterable[Path | str], cache: DemoCache | None, timing: ClipConfig | None = None
) -> Matches:
    """Parse (or load from cache) every demo. Raises DemoError on a bad one."""
    sources = [DemoSource(path, cache=cache) for path in paths]
    timing = timing or ClipConfig()
    return Matches(sources, [match_from_source(source, timing) for source in sources])


def plan_reel(loaded: Matches, steamid: str, options: PlanOptions = PlanOptions()) -> ReelPlan:
    """Every play of one player across the demos, trimmed to the best ones."""
    multi = build_multi_plan(
        loaded.matches, steamid, options.types,
        slowmo=options.slowmo, replays=options.victim_cams,
    )
    plan = multi.plan
    if options.best_seconds:
        chosen = select_best(plan.moments, options.best_seconds, min_score=options.min_score)
        plan = replace(plan, moments=arrange(chosen, plan.moments, options.order))
    return ReelPlan(plan, list(multi.missing_from))


def kills_in_plan(plan: ClipPlan, loaded: Matches) -> int:
    """How many of the player's kills the planned moments contain."""
    by_demo = {source.path: match.context for source, match in zip(loaded.sources, loaded.matches)}
    total = 0
    for moment in plan.moments:
        context = by_demo.get(Path(moment.source_demo)) if moment.source_demo else None
        context = context or loaded.matches[0].context
        total += len(moment_kills(moment, context.kills))
    return total
