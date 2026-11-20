"""Recording planned plays and producing the finished reel.

Front ends call these and present the results: which clips recorded, where
the reel and its extras landed. Failures come back as ProductionError with a
message fit to show a person.
"""

from __future__ import annotations

import contextlib
import logging
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from highlights.config import Config
from highlights.engine.clip_plan import ClipPlan
from highlights.editor.fonts import FontError
from highlights.editor.probe import ProbeError
from highlights.editor.reel import EditOptions, ReelBuilder
from highlights.editor.thumbnail import best_frame, thumbnail_command
from highlights.progress import CancelToken, Cancelled, Progress, ProgressFn, ignore
from highlights.recorder.base import ClipRequest, RecordedClip
from highlights.recorder.cs2_controller import Cs2Error
from highlights.recorder.dry_run import DryRunRecorder
from highlights.recorder.factory import build_live_recorder, settings_guard
from highlights.recorder.hlae import HlaeError
from highlights.recorder.naming import build_clip_requests, reel_filename
from highlights.recorder.session import already_recorded, record_requests
from highlights.stitcher.aspect import PROFILES, convert
from highlights.stitcher.runner import StitchError

logger = logging.getLogger(__name__)
from highlights.stitcher.stitch import stitch_clips


class ProductionError(Exception):
    """Raised when a reel cannot be made; the message explains why."""


def clip_requests(
    plan: ClipPlan,
    player_name: str,
    config: Config,
    fallback_demo: Path,
    names: dict[str, str] | None = None,
) -> list[ClipRequest]:
    """One numbered clip to film per window of the plan."""
    return build_clip_requests(
        plan=plan, demo_path=fallback_demo, player_name=player_name,
        output_dir=config.clips_dir, extension="mp4", names=names,
    )


def clips_on_disk(requests: list[ClipRequest]) -> list[RecordedClip]:
    """The clips an earlier run already recorded, for editing again."""
    return [
        RecordedClip(r, r.output_path, succeeded=already_recorded(r),
                     error=None if already_recorded(r) else "not recorded yet")
        for r in requests
    ]


def record_clips(
    requests: list[ClipRequest],
    config: Config,
    *,
    live: bool,
    resume: bool = False,
    spectator_hud: bool = False,
    progress: ProgressFn = ignore,
    cancel: CancelToken | None = None,
) -> list[RecordedClip]:
    """Film every request (or log them, when not live), guarding CS2 settings.

    One failed clip never stops the run; a game that cannot be started or
    reached raises ProductionError. When HLAE turns out unable to hook the
    installed CS2 build, the clips are recorded again with window capture in
    the same run, so a CS2 update does not leave the player with nothing.
    """
    if spectator_hud:
        config = replace(config, recording=replace(config.recording, hud="full"))
    try:
        recorder = build_live_recorder(config) if live else DryRunRecorder()
        with settings_guard(config) if live else contextlib.nullcontext():
            clips = record_requests(recorder, requests, skip_existing=resume and live,
                                    progress=progress, cancel=cancel)
            reason = getattr(recorder, "unusable", None)
            if live and reason and not (cancel is not None and cancel.cancelled):
                clips = _record_again_without_hlae(clips, config, reason, progress, cancel)
            return clips
    except (HlaeError, Cs2Error) as error:
        raise ProductionError(str(error)) from error


def _record_again_without_hlae(
    clips: list[RecordedClip], config: Config, reason: str,
    progress: ProgressFn, cancel: CancelToken | None,
) -> list[RecordedClip]:
    """Retry the failed clips with the window-capture backend."""
    fallback = build_live_recorder(config)  # HLAE has noted this build as broken
    if getattr(fallback, "name", "") == "hlae":
        return clips  # the build could not be noted, so there is nothing else to try
    logger.warning("%s Recording with window capture instead.", reason)
    failed = [clip.request for clip in clips if not clip.succeeded]
    progress(Progress("record", 0, len(failed), "HLAE cannot hook this CS2 build: switching to window capture"))
    again = {id(clip.request): clip for clip in
             record_requests(fallback, failed, progress=progress, cancel=cancel)}
    return [again.get(id(clip.request), clip) for clip in clips]


@dataclass(frozen=True)
class ReelResult:
    video: Path
    shape: str
    chapters: Path | None = None
    thumbnail: Path | None = None


def produce_reel(
    clips: list[RecordedClip],
    player_name: str,
    config: Config,
    aspect: str | None = None,
    edit: EditOptions | None = None,
    progress: ProgressFn = ignore,
    cancel: CancelToken | None = None,
) -> ReelResult:
    """Edit (or just join) recorded clips into a reel in the chosen shape.

    The reel gets a name of its own in output_dir, so nothing is overwritten.
    An edited reel also gets YouTube chapters and a thumbnail beside it.
    """
    profile = PROFILES.get(aspect or config.recording.aspect, PROFILES["stretched"])
    reel_name = reel_filename(player_name, config.output_dir)
    joined = config.clips_dir / f"_joined_{reel_name}"
    try:
        builder = None
        if edit:
            builder = ReelBuilder(edit, config.clips_dir / "edit", config.ffmpeg_path)
            output = builder.build(clips, joined, progress=progress, cancel=cancel)
        else:
            progress(Progress("edit", 0, 1, "Joining the clips"))
            output = stitch_clips(clips, joined, config.ffmpeg_path, work_dir=config.clips_dir)
        if cancel is not None:
            cancel.check()
        progress(Progress("export", 0, 1, f"Exporting as {profile.name}"))
        final = convert(output, config.output_dir / reel_name, profile, config.ffmpeg_path)
        chapters = thumbnail = None
        if builder and builder.chapters:
            chapters = final.with_suffix(".chapters.txt")
            chapters.write_text("\n".join(builder.chapters) + "\n", encoding="utf-8")
            thumbnail = _thumbnail(clips, player_name, final, config)
    except Cancelled:
        raise
    except (StitchError, RuntimeError, ValueError, OSError,
            subprocess.CalledProcessError, FontError, ProbeError) as error:
        raise ProductionError(str(error)) from error
    finally:
        with contextlib.suppress(OSError):
            joined.unlink(missing_ok=True)
    progress(Progress("export", 1, 1, "Done"))
    return ReelResult(final, profile.name, chapters, thumbnail)


def _thumbnail(clips: list[RecordedClip], player_name: str, final: Path, config: Config) -> Path | None:
    frame = best_frame(clips)
    if not frame:
        return None
    thumb = final.with_suffix(".thumbnail.png")
    subprocess.run(
        thumbnail_command(frame[0], frame[1], player_name, thumb,
                          config.clips_dir / "edit", config.ffmpeg_path),
        check=True, capture_output=True,
    )
    return thumb
