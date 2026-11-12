"""ffmpeg command lines for concatenating clips.

Two strategies, both using the concat demuxer:

* stream copy (`-c copy`) — instant, no quality loss, but requires every clip
  to share codec and parameters. The recorder encodes every clip with one
  set of settings, so this is the default and normally works.
* re-encode — the fallback when clips do not match (mixed sources, a settings
  change mid-session). Slower and lossy but robust.

Pure builders: they assemble argument lists and run nothing, so the exact
command is testable without ffmpeg installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Sensible re-encode defaults: H.264 video, AAC audio, broadly playable.
DEFAULT_VIDEO_CODEC = "libx264"
DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_CRF = 18  # visually near-lossless for gameplay footage


@dataclass(frozen=True)
class ConcatCommand:
    """A built ffmpeg invocation and the output it will write."""

    args: list[str]
    output_path: Path
    re_encoded: bool


def _base_args(ffmpeg: str, concat_list: Path) -> list[str]:
    return [
        ffmpeg,
        "-y",  # overwrite the output without prompting
        "-f",
        "concat",
        "-safe",
        "0",  # allow absolute paths in the list file
        "-i",
        str(concat_list),
    ]


def build_stream_copy(
    ffmpeg: str, concat_list: Path, output_path: Path
) -> ConcatCommand:
    """Concatenate by copying streams — fast, lossless, needs matching clips."""
    args = _base_args(ffmpeg, concat_list) + ["-c", "copy", str(output_path)]
    return ConcatCommand(args=args, output_path=output_path, re_encoded=False)


def build_reencode(
    ffmpeg: str,
    concat_list: Path,
    output_path: Path,
    video_codec: str = DEFAULT_VIDEO_CODEC,
    audio_codec: str = DEFAULT_AUDIO_CODEC,
    crf: int = DEFAULT_CRF,
) -> ConcatCommand:
    """Concatenate by re-encoding — robust when clips do not match."""
    args = _base_args(ffmpeg, concat_list) + [
        "-c:v",
        video_codec,
        "-crf",
        str(crf),
        "-c:a",
        audio_codec,
        str(output_path),
    ]
    return ConcatCommand(args=args, output_path=output_path, re_encoded=True)
