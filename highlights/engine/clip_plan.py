"""The clip-plan builder — the engine's public entry point.

Given a parsed match, a chosen player, and the highlight types they want, it
runs the matching detectors and returns an ordered ClipPlan. This is what the
recorder consumes: a chronological list of padded moments to capture.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from highlights.engine.detection import DetectionContext, Detector
from highlights.engine.detectors.clutch import ClutchDetector
from highlights.engine.detectors.deaths import DeathDetector
from highlights.engine.detectors.kills import SingleKillDetector
from highlights.engine.detectors.multikills import AceDetector, MultiKillDetector
from highlights.engine.detectors.utility_damage import UtilityDamageDetector
from highlights.engine.detectors.utility_flash import FlashUtilityDetector
from highlights.engine.detectors.utility_smoke import SmokeUtilityDetector
from highlights.engine.moments import HighlightType, Moment
from highlights.engine.scoring import score_moments

# One HighlightType can map to several detectors — utility covers both flashes
# and grenade damage.
DETECTOR_REGISTRY: dict[HighlightType, list[Detector]] = {
    HighlightType.KILL: [SingleKillDetector()],
    HighlightType.MULTI_KILL: [MultiKillDetector()],
    HighlightType.ACE: [AceDetector()],
    HighlightType.CLUTCH: [ClutchDetector()],
    HighlightType.DEATH: [DeathDetector()],
    HighlightType.UTILITY: [
        FlashUtilityDetector(),
        UtilityDamageDetector(),
        SmokeUtilityDetector(),
    ],
}


# Cluster moments already contain the individual frags, so a single KILL that
# overlaps one of these would just re-record the same footage.
_ABSORBING_TYPES = frozenset(
    {HighlightType.MULTI_KILL, HighlightType.ACE, HighlightType.CLUTCH}
)


def merge_overlaps(moments: list[Moment]) -> list[Moment]:
    """Drop single-kill moments already covered by a richer overlapping moment.

    Only KILL moments are absorbed, and only by multi-kill, ace, or clutch
    moments — every other pairing (a death overlapping a kill, two utility
    moments) is a distinct highlight and kept.
    """
    absorbers = [m for m in moments if m.highlight_type in _ABSORBING_TYPES]
    kept: list[Moment] = []
    for moment in moments:
        if moment.highlight_type is HighlightType.KILL and any(
            moment.overlaps(a) for a in absorbers
        ):
            continue
        kept.append(moment)
    return _join_close_kills(kept)


def _join_close_kills(moments: list[Moment]) -> list[Moment]:
    """Fold single kills whose windows overlap into one moment.

    Two kills a second apart would otherwise be two clips of the same few
    seconds of footage, and the reel would show the double kill twice.
    """
    kills = sorted(
        (m for m in moments if m.highlight_type is HighlightType.KILL),
        key=lambda m: m.start_tick,
    )
    joined: list[Moment] = []
    for kill in kills:
        previous = joined[-1] if joined else None
        if (
            previous is not None
            and previous.round_number == kill.round_number
            and previous.overlaps(kill)
        ):
            joined[-1] = replace(
                previous,
                core_tick=max(previous.core_tick, kill.core_tick),
                start_tick=min(previous.start_tick, kill.start_tick),
                end_tick=max(previous.end_tick, kill.end_tick),
                description=f"{previous.description} + {kill.description}",
            )
        else:
            joined.append(kill)
    others = [m for m in moments if m.highlight_type is not HighlightType.KILL]
    return sorted(others + joined, key=lambda m: (m.core_tick, m.highlight_type))


@dataclass(frozen=True)
class ClipPlan:
    """An ordered set of moments to record for one player."""

    player_steamid: str
    selected_types: tuple[HighlightType, ...]
    moments: list[Moment]

    def __len__(self) -> int:
        return len(self.moments)

    @property
    def total_seconds(self) -> float:
        return sum(m.duration_seconds for m in self.moments)

    def counts_by_type(self) -> dict[HighlightType, int]:
        """How many moments of each type are in the plan.

        Only types that actually occur are included, ordered by first
        appearance in the (already chronological) moment list.
        """
        counts: dict[HighlightType, int] = {}
        for moment in self.moments:
            counts[moment.highlight_type] = counts.get(moment.highlight_type, 0) + 1
        return counts


def build_clip_plan(
    ctx: DetectionContext,
    player_steamid: str,
    selected_types: Iterable[HighlightType],
    *,
    merge: bool = True,
    score: bool = True,
) -> ClipPlan:
    """Run the detectors for the selected types and order the result by time.

    With merge on (the default), single kills already shown inside a
    multi-kill, ace, or clutch are dropped so the same footage is not
    recorded twice. With score on, every moment is rated so plans from
    different matches can be ranked against each other.
    """
    types = tuple(dict.fromkeys(selected_types))  # de-dupe, preserve order
    moments: list[Moment] = []
    for highlight_type in types:
        for detector in DETECTOR_REGISTRY.get(highlight_type, []):
            moments.extend(detector.detect(ctx, player_steamid))

    if ctx.demo_path is not None:
        moments = [replace(m, source_demo=ctx.demo_path) for m in moments]
    moments.sort(key=lambda m: (m.core_tick, m.highlight_type))
    if merge:
        moments = merge_overlaps(moments)
    if score:
        moments = score_moments(moments, ctx)
    return ClipPlan(
        player_steamid=player_steamid,
        selected_types=types,
        moments=moments,
    )
