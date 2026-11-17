"""Recording planned plays and producing the finished reel.

Front ends call these and present the results: which clips recorded, where
the reel and its extras landed. Failures come back as ProductionError with a
message fit to show a person.
"""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from highlights.config import Config
from highlights.engine.clip_plan import ClipPlan
from highlights.editor.fonts import FontError
from highlights.editor.probe import ProbeError
from highlights.editor.reel import EditOptions, ReelBuilder
from highlights.editor.thumbnail import best_frame, thumbnail_command
from highlights.recorder.base import ClipRequest, RecordedClip
from highlights.recorder.cs2_controller import Cs2Error
from highlights.recorder.dry_run import DryRunRecorder
from highlights.recorder.factory import build_live_recorder, settings_guard
from highlights.recorder.hlae import HlaeError
from highlights.recorder.naming import build_clip_requests, reel_filename
from highlights.recorder.session import already_recorded, record_requests
from highlights.stitcher.aspect import PROFILES, convert
from highlights.stitcher.runner import StitchError
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
) -> list[RecordedClip]:
    """Film every request (or log them, when not live), guarding CS2 settings.

    One failed clip never stops the run; a game that cannot be started or
    reached raises ProductionError.
    """
    if spectator_hud:
        config = replace(config, recording=replace(config.recording, hud="full"))
    try:
        recorder = build_live_recorder(config) if live else DryRunRecorder()
        with settings_guard(config) if live else contextlib.nullcontext():
            return record_requests(recorder, requests, skip_existing=resume and live)
    except (HlaeError, Cs2Error) as error:
        raise ProductionError(str(error)) from error


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
            output = builder.build(clips, joined)
        else:
            output = stitch_clips(clips, joined, config.ffmpeg_path, work_dir=config.clips_dir)
        final = convert(output, config.output_dir / reel_name, profile, config.ffmpeg_path)
        chapters = thumbnail = None
        if builder and builder.chapters:
            chapters = final.with_suffix(".chapters.txt")
            chapters.write_text("\n".join(builder.chapters) + "\n", encoding="utf-8")
            thumbnail = _thumbnail(clips, player_name, final, config)
    except (StitchError, RuntimeError, ValueError, OSError,
            subprocess.CalledProcessError, FontError, ProbeError) as error:
        raise ProductionError(str(error)) from error
    finally:
        with contextlib.suppress(OSError):
            joined.unlink(missing_ok=True)
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
