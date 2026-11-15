"""A YouTube thumbnail for the reel.

The frame comes from the highest-scoring highlight, at its first kill, so the
thumbnail shows the play itself. It is stretched to 16:9 like the reel, with
the headline in large type across the bottom.
"""

from __future__ import annotations

from pathlib import Path

from highlights.editor.cards import ACCENT
from highlights.editor.captions import headline_for
from highlights.editor.fonts import filter_path, find_font
from highlights.recorder.base import RecordedClip

WIDTH, HEIGHT = 1280, 720


def best_frame(clips: list[RecordedClip]) -> tuple[RecordedClip, float] | None:
    """The clip and second to grab: top score, first kill (else its middle)."""
    candidates = [c for c in clips if c.succeeded and c.output_path.is_file()]
    if not candidates:
        return None
    best = max(candidates, key=lambda c: (c.request.moment.score, c.request.part == 1))
    window = best.request.window
    if window.kill_ticks:
        return best, window.screen_seconds(window.kill_ticks[0])
    return best, window.duration_seconds / 2


def thumbnail_command(
    clip: RecordedClip,
    at_seconds: float,
    player_name: str,
    output: Path,
    work_dir: Path,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """ffmpeg arguments that grab one frame and letter it as a thumbnail."""
    work_dir.mkdir(parents=True, exist_ok=True)
    headline = headline_for(clip.request.moment)
    texts = []
    for name, text, size, color, y in (
        ("headline", headline, 96, "white", "h-th-110"),
        ("player", player_name, 54, ACCENT, "h-th-40"),
    ):
        text_file = work_dir / f"thumb_{name}.txt"
        text_file.write_text(text, encoding="utf-8")
        texts.append(
            f"drawtext=fontfile='{filter_path(find_font(text))}':textfile='{filter_path(text_file)}':"
            f"fontsize={size}:fontcolor={color}:x=48:y={y}:"
            f"borderw=5:bordercolor=black@0.85"
        )
    video = ",".join([
        f"scale={WIDTH}:{HEIGHT}", "setsar=1",
        # darken the bottom third so the lettering pops
        f"drawbox=x=0:y={HEIGHT * 2 // 3}:w={WIDTH}:h={HEIGHT // 3}:color=black@0.35:t=fill",
        *texts,
    ])
    return [
        ffmpeg, "-y", "-loglevel", "error",
        "-ss", f"{max(at_seconds, 0):.3f}", "-i", str(clip.output_path),
        "-frames:v", "1", "-vf", video, str(output),
    ]
