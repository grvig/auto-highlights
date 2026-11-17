"""Running a whole plan through a recorder.

A deliberately plain loop: open the backend, record each request in order,
always close. Per-clip timing and sync refinements belong in the orchestration
milestone; this is the minimum needed to run a plan end to end.
"""

from __future__ import annotations

import logging

from highlights.progress import CancelToken, Progress, ProgressFn, ignore
from highlights.recorder.base import ClipRequest, RecordedClip, Recorder

logger = logging.getLogger(__name__)


def already_recorded(request: ClipRequest) -> bool:
    """Whether this clip's file exists from an earlier run."""
    path = request.output_path
    return path.is_file() and path.stat().st_size > 0


def recording_order(requests: list[ClipRequest]) -> list[ClipRequest]:
    """The order to film in: grouped by demo, then by tick.

    A reel arranged as a montage hops between matches, and loading a demo
    costs far more than a clip, so filming goes demo by demo. Results still
    come back in reel order.
    """
    first_seen: dict[str, int] = {}
    for request in requests:
        first_seen.setdefault(str(request.demo_path), len(first_seen))
    return sorted(requests, key=lambda r: (first_seen[str(r.demo_path)], r.start_tick))


def record_requests(
    recorder: Recorder,
    requests: list[ClipRequest],
    skip_existing: bool = False,
    progress: ProgressFn = ignore,
    cancel: CancelToken | None = None,
) -> list[RecordedClip]:
    """Record every request, returning one result per request, in order.

    The backend is always closed, and a failed clip never stops the run — the
    caller decides what to do with partial results. With skip_existing, clips
    already on disk from an interrupted run are kept, and the game is not even
    launched when nothing is left to record. A cancelled run stops between
    clips; the clips it never reached come back failed as "cancelled".
    """
    kept = {id(r) for r in requests if skip_existing and already_recorded(r)}
    todo = [r for r in requests if id(r) not in kept]
    logger.info(
        "[%s] starting run of %d clip(s), %d already recorded",
        getattr(recorder, "name", "?"), len(todo), len(kept),
    )
    recorded: dict[int, RecordedClip] = {}
    if todo:
        progress(Progress("record", 0, len(todo), "Starting the game"))
        recorder.open()
        try:
            for number, request in enumerate(recording_order(todo), start=1):
                if cancel is not None and cancel.cancelled:
                    logger.info("Recording cancelled before %s", request.label)
                    break
                progress(Progress("record", number - 1, len(todo), f"Recording {request.label}"))
                recorded[id(request)] = recorder.record_clip(request)
            progress(Progress("record", len(recorded), len(todo), "Closing the game"))
        finally:
            recorder.close()
    results = []
    for request in requests:
        if id(request) in kept:
            results.append(RecordedClip(request, request.output_path, succeeded=True))
        else:
            results.append(recorded.get(id(request)) or RecordedClip(
                request, request.output_path, succeeded=False, error="cancelled"))

    failed = [clip for clip in results if not clip.succeeded]
    if failed:
        logger.warning("%d of %d clip(s) failed", len(failed), len(results))
    else:
        logger.info("All %d clip(s) recorded", len(results))
    return results
