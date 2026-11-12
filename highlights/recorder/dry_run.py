"""Dry-run recorder backend.

Logs exactly what would be recorded and touches nothing else — no CS2, no
files. This is the backend to reach for when checking that a plan looks
sane, and the one that keeps the whole pipeline testable on a machine with
neither the game nor HLAE installed.
"""

from __future__ import annotations

import logging

from highlights.engine.timing import format_timestamp
from highlights.recorder.base import ClipRequest, RecordedClip

logger = logging.getLogger(__name__)


class DryRunRecorder:
    """A Recorder that reports what it would do and produces no video.

    Clips come back as succeeded so the pipeline runs end to end, but no file
    is written — anything downstream that needs real footage will not find any.
    """

    name = "dry-run"

    def __init__(self) -> None:
        self._recorded: list[RecordedClip] = []

    @property
    def recorded(self) -> list[RecordedClip]:
        """Everything this backend was asked to record, in order."""
        return list(self._recorded)

    def open(self) -> None:
        logger.info("[%s] opened — nothing will be launched", self.name)

    def close(self) -> None:
        total = sum(c.request.duration_seconds for c in self._recorded)
        logger.info(
            "[%s] closed — %d clip(s), %.1fs of footage would have been recorded",
            self.name,
            len(self._recorded),
            total,
        )

    def record_clip(self, request: ClipRequest) -> RecordedClip:
        moment = request.moment
        logger.info(
            "[%s] would record %s | R%02d %s | ticks %d-%d pov=%s x%g (%.1fs) | %s | -> %s",
            self.name,
            request.label,
            moment.round_number,
            moment.highlight_type,
            request.start_tick,
            request.end_tick,
            request.spectate_steamid,
            request.speed,
            request.duration_seconds,
            moment.description,
            request.output_path,
        )
        logger.debug(
            "[%s]   demo=%s player=%s (%s) core=%s",
            self.name,
            request.demo_path,
            request.player_name,
            request.player_steamid,
            format_timestamp(moment.core_tick),
        )
        clip = RecordedClip(
            request=request, output_path=request.output_path, succeeded=True
        )
        self._recorded.append(clip)
        return clip
