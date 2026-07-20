"""The clip-plan builder — the engine's public entry point.

Given a parsed match, a chosen player, and the highlight types they want, it
runs the matching detectors and returns an ordered ClipPlan. This is what the
recorder consumes: a chronological list of padded moments to capture.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from highlights.engine.detection import DetectionContext, Detector
from highlights.engine.detectors.clutch import ClutchDetector
from highlights.engine.detectors.deaths import DeathDetector
from highlights.engine.detectors.kills import SingleKillDetector
from highlights.engine.detectors.multikills import AceDetector, MultiKillDetector
from highlights.engine.detectors.utility_damage import UtilityDamageDetector
from highlights.engine.detectors.utility_flash import FlashUtilityDetector
from highlights.engine.moments import HighlightType, Moment

# One HighlightType can map to several detectors — utility covers both flashes
# and grenade damage.
DETECTOR_REGISTRY: dict[HighlightType, list[Detector]] = {
    HighlightType.KILL: [SingleKillDetector()],
    HighlightType.MULTI_KILL: [MultiKillDetector()],
    HighlightType.ACE: [AceDetector()],
    HighlightType.CLUTCH: [ClutchDetector()],
    HighlightType.DEATH: [DeathDetector()],
    HighlightType.UTILITY: [FlashUtilityDetector(), UtilityDamageDetector()],
}


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


def build_clip_plan(
    ctx: DetectionContext,
    player_steamid: str,
    selected_types: Iterable[HighlightType],
) -> ClipPlan:
    """Run the detectors for the selected types and order the result by time."""
    types = tuple(dict.fromkeys(selected_types))  # de-dupe, preserve order
    moments: list[Moment] = []
    for highlight_type in types:
        for detector in DETECTOR_REGISTRY.get(highlight_type, []):
            moments.extend(detector.detect(ctx, player_steamid))

    moments.sort(key=lambda m: (m.core_tick, m.highlight_type))
    return ClipPlan(
        player_steamid=player_steamid,
        selected_types=types,
        moments=moments,
    )
