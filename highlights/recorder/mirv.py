"""HLAE's mirv_streams commands, and turning a take into a finished clip.

A take is recorded with host_framerate pinned, so the game renders every frame
at exactly the target rate however long each frame takes; ffmpeg receives the
frames through HLAE's pipe and the game's audio lands in a wav beside them.
Frame N of the video is therefore tick start + N * tickrate / fps, which is
what makes trimming by time exact instead of guessed.
"""

from __future__ import annotations

from pathlib import Path

VIDEO_NAME = "video.mp4"
AUDIO_RELATIVE = Path("take0000") / "audio.wav"
PRESET = "hlpreset"


def _console_path(path: Path) -> str:
    # HLAE unescapes backslashes in settings strings, so each one is doubled.
    return str(Path(path)).replace("\\", "\\\\")


def start_commands(take_dir: Path, framerate: int = 60, crf: int = 16) -> list[str]:
    """Commands that arm and start a take writing into take_dir."""
    video = _console_path(Path(take_dir) / VIDEO_NAME)
    encoder = f"-c:v libx264 -preset veryfast -pix_fmt yuv420p -crf {int(crf)}"
    return [
        f"host_framerate {int(framerate)}",
        f'mirv_streams record name "{Path(take_dir).as_posix()}"',
        f'mirv_streams settings add ffmpeg {PRESET} "{encoder} {{QUOTE}}{video}{{QUOTE}}"',
        "mirv_streams record screen enabled 1",
        f"mirv_streams record screen settings {PRESET}",
        "mirv_streams record startMovieWav 1",
        "mirv_streams record start",
    ]


def stop_commands() -> list[str]:
    """Commands that end a take and hand the frame rate back to the game."""
    return [
        "mirv_streams record end",
        f"mirv_streams settings remove {PRESET}",
        "host_framerate 0",
    ]


def finish_command(
    take_dir: Path,
    output: Path,
    skip_seconds: float,
    duration_seconds: float,
    speed: float = 1.0,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """ffmpeg arguments that trim a take, add its audio and apply slow motion.

    skip_seconds drops the lead-in recorded before the window starts. Speeds
    below 1 stretch both picture and sound, so a slowed shot stays in sync.
    """
    if speed <= 0:
        raise ValueError(f"Speed must be positive: {speed}")
    take_dir = Path(take_dir)
    video_filter = "setpts=PTS-STARTPTS"
    audio_filter = "asetpts=PTS-STARTPTS"
    if speed != 1.0:
        video_filter += f",setpts=PTS/{speed:g}"
        audio_filter += "," + _atempo_chain(speed)
    return [
        ffmpeg, "-y", "-loglevel", "error",
        "-ss", f"{skip_seconds:.3f}", "-t", f"{duration_seconds:.3f}",
        "-i", str(take_dir / VIDEO_NAME),
        "-ss", f"{skip_seconds:.3f}", "-t", f"{duration_seconds:.3f}",
        "-i", str(take_dir / AUDIO_RELATIVE),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", video_filter, "-af", audio_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]


def _atempo_chain(speed: float) -> str:
    """atempo only accepts 0.5-2.0 per stage, so slower speeds chain stages."""
    stages: list[str] = []
    remaining = speed
    while remaining < 0.5:
        stages.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        stages.append("atempo=2.0")
        remaining /= 2.0
    stages.append(f"atempo={remaining:g}")
    return ",".join(stages)
