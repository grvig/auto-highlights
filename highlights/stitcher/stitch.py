"""Stitching a set of recorded clips into one reel.

The Layer 3 public entry point, the counterpart to the engine's clip-plan
builder. Given the clips a recorder produced, it writes the concat list, tries
the fast stream copy, and falls back to a re-encode if the clips do not concat
cleanly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from highlights.recorder.base import RecordedClip
from highlights.stitcher.concat_list import write_concat_list
from highlights.stitcher.ffmpeg_command import build_reencode, build_stream_copy
from highlights.stitcher.runner import Runner, StitchError, run_concat

logger = logging.getLogger(__name__)


def usable_clip_paths(clips: list[RecordedClip]) -> list[Path]:
    """The output paths of clips that succeeded and exist on disk, in order.

    A recorder returns a result per request; failed ones and any whose file
    never materialised are skipped so a gap does not abort the whole reel.
    """
    paths: list[Path] = []
    for clip in clips:
        if not clip.succeeded:
            logger.warning("Skipping failed clip #%03d", clip.index)
            continue
        if not clip.output_path.exists():
            logger.warning(
                "Skipping clip #%03d, file missing: %s", clip.index, clip.output_path
            )
            continue
        paths.append(clip.output_path)
    return paths


def stitch_paths(
    clip_paths: list[Path],
    output_path: Path,
    ffmpeg: str = "ffmpeg",
    *,
    work_dir: Path | None = None,
    allow_reencode: bool = True,
    runner: Runner | None = None,
) -> Path:
    """Concatenate clip files into output_path, returning the reel path."""
    if not clip_paths:
        raise StitchError("No clips to stitch")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_dir = work_dir or output_path.parent
    concat_list = write_concat_list(clip_paths, list_dir / "concat_list.txt")

    copy_cmd = build_stream_copy(ffmpeg, concat_list, output_path)
    try:
        return run_concat(copy_cmd, ffmpeg, runner=runner)
    except StitchError as error:
        if not allow_reencode:
            raise
        logger.warning(
            "Stream copy failed (%s); retrying with a re-encode", error
        )

    reencode_cmd = build_reencode(ffmpeg, concat_list, output_path)
    return run_concat(reencode_cmd, ffmpeg, runner=runner)


def stitch_clips(
    clips: list[RecordedClip],
    output_path: Path,
    ffmpeg: str = "ffmpeg",
    *,
    work_dir: Path | None = None,
    allow_reencode: bool = True,
    runner: Runner | None = None,
) -> Path:
    """Stitch a recorder's clips into a final reel.

    Only successful, on-disk clips are included. Raises StitchError if none
    remain.
    """
    paths = usable_clip_paths(clips)
    if not paths:
        raise StitchError("No usable clips to stitch — every clip failed or is missing")
    logger.info("Stitching %d clip(s) into %s", len(paths), output_path.name)
    return stitch_paths(
        paths,
        output_path,
        ffmpeg,
        work_dir=work_dir,
        allow_reencode=allow_reencode,
        runner=runner,
    )
