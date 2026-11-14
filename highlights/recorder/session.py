"""Running a whole plan through a recorder.

A deliberately plain loop: open the backend, record each request in order,
always close. Per-clip timing and sync refinements belong in the orchestration
milestone; this is the minimum needed to run a plan end to end.
"""

from __future__ import annotations

import logging

from highlights.recorder.base import ClipRequest, RecordedClip, Recorder

logger = logging.getLogger(__name__)


def already_recorded(request: ClipRequest) -> bool:
    """Whether this clip's file exists from an earlier run."""
    path = request.output_path
    return path.is_file() and path.stat().st_size > 0


def record_requests(
    recorder: Recorder, requests: list[ClipRequest], skip_existing: bool = False
) -> list[RecordedClip]:
    """Record every request, returning one result per request, in order.

    The backend is always closed, and a failed clip never stops the run — the
    caller decides what to do with partial results. With skip_existing, clips
    already on disk from an interrupted run are kept, and the game is not even
    launched when nothing is left to record.
    """
    kept = {id(r) for r in requests if skip_existing and already_recorded(r)}
    todo = [r for r in requests if id(r) not in kept]
    logger.info(
        "[%s] starting run of %d clip(s), %d already recorded",
        getattr(recorder, "name", "?"), len(todo), len(kept),
    )
    recorded: dict[int, RecordedClip] = {}
    if todo:
        recorder.open()
        try:
            for request in todo:
                recorded[id(request)] = recorder.record_clip(request)
        finally:
            recorder.close()
    results = [
        recorded.get(id(r)) or RecordedClip(r, r.output_path, succeeded=True) for r in requests
    ]

    failed = [clip for clip in results if not clip.succeeded]
    if failed:
        logger.warning("%d of %d clip(s) failed", len(failed), len(results))
    else:
        logger.info("All %d clip(s) recorded", len(results))
    return results
