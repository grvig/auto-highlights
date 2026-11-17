"""Recording planned plays and producing the finished reel.

Front ends call these and present the results: which clips recorded, where
the reel and its extras landed. Failures come back as ProductionError with a
message fit to show a person.
"""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from highlights.config import Config
from highlights.editor.fonts import FontError
from highlights.editor.probe import ProbeError
from highlights.editor.reel import EditOptions, ReelBuilder
from highlights.editor.thumbnail import best_frame, thumbnail_command
from highlights.recorder.base import RecordedClip
from highlights.recorder.naming import reel_filename
from highlights.stitcher.aspect import PROFILES, convert
from highlights.stitcher.runner import StitchError
from highlights.stitcher.stitch import stitch_clips


class ProductionError(Exception):
    """Raised when a reel cannot be made; the message explains why."""


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
