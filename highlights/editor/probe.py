"""Reading a media file's length, size and streams with ffprobe."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

ProbeRunner = Callable[[Sequence[str]], str]


class ProbeError(Exception):
    """Raised when a file cannot be read as media."""


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    has_audio: bool = False


def _run(args: Sequence[str]) -> str:
    result = subprocess.run(list(args), capture_output=True, text=True)
    if result.returncode != 0:
        raise ProbeError(result.stderr.strip().splitlines()[-1] if result.stderr else "ffprobe failed")
    return result.stdout


def ffprobe_for(ffmpeg: str) -> str:
    """ffprobe sits next to ffmpeg; a bare "ffmpeg" means a bare "ffprobe"."""
    path = Path(ffmpeg)
    if path.parent == Path("."):
        return "ffprobe"
    return str(path.with_name(path.name.replace("ffmpeg", "ffprobe")))


def probe(path: Path, ffmpeg: str = "ffmpeg", runner: ProbeRunner = _run) -> MediaInfo:
    """Duration, picture size, frame rate and whether there is sound."""
    output = runner([
        ffprobe_for(ffmpeg), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    try:
        data = json.loads(output)
        duration = float(data["format"]["duration"])
    except (ValueError, KeyError, TypeError) as error:
        raise ProbeError(f"Could not read {path}: {error}") from error
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    fps = None
    if video and video.get("avg_frame_rate", "0/0") not in ("0/0", ""):
        fps = float(Fraction(video["avg_frame_rate"]))
    return MediaInfo(
        duration=duration,
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        fps=fps,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
    )
