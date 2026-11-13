"""Joining clips with crossfades instead of hard cuts.

ffmpeg's xfade blends picture and acrossfade blends sound; both need every
input in one shared format, so each clip is normalised first. Each transition
overlaps two clips, so the reel is shorter than the sum of its clips by one
transition per join.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_TRANSITION = "fade"
DEFAULT_SECONDS = 0.35
# A transition never eats more than this share of the shortest clip.
MAX_SHARE_OF_CLIP = 0.3


def transition_seconds(durations: list[float], wanted: float = DEFAULT_SECONDS) -> float:
    """The crossfade length these clips can afford."""
    if len(durations) < 2:
        return 0.0
    return round(min(wanted, min(durations) * MAX_SHARE_OF_CLIP), 3)


def offsets(durations: list[float], seconds: float) -> list[float]:
    """When each crossfade starts on the joined timeline."""
    result, elapsed = [], 0.0
    for number, duration in enumerate(durations[:-1], start=1):
        elapsed += duration
        result.append(round(elapsed - number * seconds, 3))
    return result


def join_filter(
    durations: list[float],
    width: int,
    height: int,
    fps: int = 60,
    transition: str = DEFAULT_TRANSITION,
    seconds: float = DEFAULT_SECONDS,
) -> tuple[str, str, str]:
    """A filter_complex joining every input. Returns (graph, video, audio) labels."""
    parts = []
    for i in range(len(durations)):
        parts.append(
            f"[{i}:v]fps={fps},scale={width}:{height},setsar=1,format=yuv420p,"
            f"settb=AVTB,setpts=PTS-STARTPTS[v{i}]"
        )
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
    fade = transition_seconds(durations, seconds)
    video, audio = "v0", "a0"
    for i, start in enumerate(offsets(durations, fade), start=1):
        if fade > 0:
            parts.append(
                f"[{video}][v{i}]xfade=transition={transition}:duration={fade:g}:offset={start:g}[vx{i}]"
            )
            parts.append(f"[{audio}][a{i}]acrossfade=d={fade:g}[ax{i}]")
        else:
            parts.append(f"[{video}][v{i}]concat=n=2:v=1:a=0[vx{i}]")
            parts.append(f"[{audio}][a{i}]concat=n=2:v=0:a=1[ax{i}]")
        video, audio = f"vx{i}", f"ax{i}"
    return ";".join(parts), video, audio


def join_command(
    clips: list[Path],
    durations: list[float],
    output: Path,
    width: int,
    height: int,
    fps: int = 60,
    transition: str = DEFAULT_TRANSITION,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """ffmpeg arguments that join clips with crossfades into one file."""
    graph, video, audio = join_filter(durations, width, height, fps, transition)
    inputs = [arg for clip in clips for arg in ("-i", str(clip))]
    return [
        ffmpeg, "-y", "-loglevel", "error", *inputs,
        "-filter_complex", graph, "-map", f"[{video}]", "-map", f"[{audio}]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(output),
    ]
