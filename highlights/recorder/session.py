"""Running a whole plan through a recorder.

A deliberately plain loop: open the backend, record each request in order,
always close. Per-clip timing and sync refinements belong in the orchestration
milestone; this is the minimum needed to run a plan end to end.
"""

from __future__ import annotations

import logging

from highlights.recorder.base import ClipRequest, RecordedClip, Recorder

logger = logging.getLogger(__name__)


def record_requests(
    recorder: Recorder, requests: list[ClipRequest]
) -> list[RecordedClip]:
    """Record every request, returning one result per request.

    The backend is always closed, and a failed clip never stops the run — the
    caller decides what to do with partial results.
    """
    logger.info(
        "[%s] starting run of %d clip(s)", getattr(recorder, "name", "?"), len(requests)
    )
    results: list[RecordedClip] = []
    recorder.open()
    try:
        for request in requests:
            results.append(recorder.record_clip(request))
    finally:
        recorder.close()

    failed = [clip for clip in results if not clip.succeeded]
    if failed:
        logger.warning("%d of %d clip(s) failed", len(failed), len(results))
    else:
        logger.info("All %d clip(s) recorded", len(results))
    return results
