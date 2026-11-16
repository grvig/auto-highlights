"""Export shapes: 4:3, stretched 4:3, pillarboxed, widescreen and vertical.

Many players run 4:3 stretched (e.g. 1280x960 filling a 16:9 monitor), and a
reel of their play should be able to keep that look rather than being forced
into native 16:9. Each profile is one ffmpeg video filter chain; capture at the
4:3 render resolution and let the filter decide the final shape.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AspectMode(str, Enum):
    NATIVE = "native"  # keep the source shape, scaled to the target height
    STRETCHED = "stretched"  # fill the frame, distorting 4:3 into 16:9
    PILLARBOX = "pillarbox"  # source shape centred with black bars
    FILL = "fill"  # fill the frame by cropping the excess
    VERTICAL = "vertical"  # 9:16, cropped around the centre crosshair


@dataclass(frozen=True)
class ExportProfile:
    name: str
    mode: AspectMode
    width: int
    height: int


PROFILES = {
    "4:3": ExportProfile("4:3", AspectMode.NATIVE, 1440, 1080),
    "stretched": ExportProfile("stretched", AspectMode.STRETCHED, 1920, 1080),
    "pillarbox": ExportProfile("pillarbox", AspectMode.PILLARBOX, 1920, 1080),
    "16:9": ExportProfile("16:9", AspectMode.FILL, 1920, 1080),
    "vertical": ExportProfile("vertical", AspectMode.VERTICAL, 1080, 1920),
}


def video_filter(profile: ExportProfile) -> str:
    """The ffmpeg -vf chain that turns any source into this profile's shape.

    setsar=1 marks the pixels square, so players show the stretch as encoded
    instead of quietly undoing it.
    """
    w, h = profile.width, profile.height
    chains = {
        AspectMode.NATIVE: f"scale=-2:{h}",
        AspectMode.STRETCHED: f"scale={w}:{h}",
        AspectMode.PILLARBOX: f"scale=-2:{h},pad={w}:{h}:(ow-iw)/2:0",
        AspectMode.FILL: f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        AspectMode.VERTICAL: f"scale=-2:{h},crop={w}:{h}",
    }
    return f"{chains[profile.mode]},setsar=1"


# Loudness target for the finished reel: what YouTube and most platforms
# normalise to, so the reel is neither quieter nor squashed after upload.
# Game audio is all transients: at -14 LUFS gunshots overshoot full scale, so
# the reel is levelled a little lower and a limiter catches what is left.
LOUDNESS = "loudnorm=I=-16:TP=-2:LRA=11"
# Limited at 4x the sample rate so peaks between samples are caught too;
# measured on a real reel: true peak -1.2 dBFS after AAC encoding.
PEAK_LIMIT = "aresample=192000,alimiter=limit=0.708:level=false,aresample=48000"  # -3 dBFS


def measure_args(source: Path, ffmpeg: str = "ffmpeg") -> list[str]:
    """ffmpeg arguments for loudnorm's measuring pass (stats go to stderr)."""
    return [ffmpeg, "-hide_banner", "-i", str(source), "-vn",
            "-af", f"{LOUDNESS}:print_format=json", "-f", "null", "-"]


def parse_measurement(stderr: str) -> dict[str, str] | None:
    """The measured_* values loudnorm printed, or None if it printed none."""
    start, end = stderr.rfind("{"), stderr.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        data = json.loads(stderr[start:end + 1])
        return {key: str(data[key]) for key in
                ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (ValueError, KeyError):
        return None


def linear_loudness(measured: dict[str, str] | None) -> str:
    """One steady gain to the target (linear mode), so gunshots keep their
    punch; without a measurement, the single-pass filter is the fallback."""
    if not measured:
        return LOUDNESS
    return (
        f"{LOUDNESS}:linear=true:measured_I={measured['input_i']}:"
        f"measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}"
    )


def convert_args(
    source: Path, output: Path, profile: ExportProfile, ffmpeg: str = "ffmpeg",
    normalise: bool = True, loudness: str = LOUDNESS,
) -> list[str]:
    """ffmpeg arguments that reshape a video and, by default, level its loudness."""
    audio = (["-af", f"{loudness},{PEAK_LIMIT}", "-ar", "48000", "-c:a", "aac", "-b:a", "192k"]
             if normalise else ["-c:a", "copy"])
    return [
        ffmpeg, "-y", "-i", str(source),
        "-vf", video_filter(profile),
        "-c:v", "libx264", "-crf", "18", *audio,
        str(output),
    ]


def convert(
    source: Path, output: Path, profile: ExportProfile, ffmpeg: str = "ffmpeg",
    normalise: bool = True,
) -> Path:
    """Re-encode a video into the profile's shape, levelling its loudness."""
    output.parent.mkdir(parents=True, exist_ok=True)
    loudness = LOUDNESS
    if normalise:
        measured = subprocess.run(measure_args(source, ffmpeg), capture_output=True, text=True)
        loudness = linear_loudness(parse_measurement(measured.stderr))
    args = convert_args(source, output, profile, ffmpeg, normalise, loudness)
    logger.info("Exporting %s as %s", source.name, profile.name)
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not output.exists():
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f"ffmpeg could not export {profile.name}:\n{tail}")
    return output
