"""Export shapes: 4:3, stretched 4:3, pillarboxed, widescreen and vertical.

Many players run 4:3 stretched (e.g. 1280x960 filling a 16:9 monitor), and a
reel of their play should be able to keep that look rather than being forced
into native 16:9. Each profile is one ffmpeg video filter chain; capture at the
4:3 render resolution and let the filter decide the final shape.
"""

from __future__ import annotations

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


def convert(source: Path, output: Path, profile: ExportProfile, ffmpeg: str = "ffmpeg") -> Path:
    """Re-encode a video into the profile's shape, keeping its audio as is."""
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [
        ffmpeg, "-y", "-i", str(source),
        "-vf", video_filter(profile),
        "-c:v", "libx264", "-crf", "18", "-c:a", "copy",
        str(output),
    ]
    logger.info("Exporting %s as %s", source.name, profile.name)
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not output.exists():
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f"ffmpeg could not export {profile.name}:\n{tail}")
    return output
