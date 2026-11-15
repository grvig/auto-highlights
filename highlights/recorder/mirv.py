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
OUTPUT_FPS = 60
AUDIO_RELATIVE = Path("take0000") / "audio.wav"

# HLAE refuses to delete a preset a stream has used ("has further
# references") and to add one whose name exists, so a reused name silently
# keeps the first take's output path. Every take gets a preset of its own.
PRESET_PREFIX = "ahtake"


def preset_name(take_number: int) -> str:
    return f"{PRESET_PREFIX}{int(take_number)}"


def _console_path(path: Path) -> str:
    # HLAE unescapes backslashes in settings strings, so each one is doubled.
    return str(Path(path)).replace("\\", "\\\\")


def start_commands(
    take_dir: Path, take_number: int = 1, framerate: int = 60, crf: int = 16
) -> list[str]:
    """Commands that arm and start a take writing into take_dir.

    take_number must be unique within one game session (see PRESET_PREFIX).
    """
    video = _console_path(Path(take_dir) / VIDEO_NAME)
    encoder = f"-c:v libx264 -preset veryfast -pix_fmt yuv420p -crf {int(crf)}"
    preset = preset_name(take_number)
    return [
        f"host_framerate {int(framerate)}",
        f'mirv_streams record name "{Path(take_dir).as_posix()}"',
        f'mirv_streams settings add ffmpeg {preset} "{encoder} {{QUOTE}}{video}{{QUOTE}}"',
        "mirv_streams record screen enabled 1",
        f"mirv_streams record screen settings {preset}",
        "mirv_streams record startMovieWav 1",
        "mirv_streams record start",
    ]


def stop_commands() -> list[str]:
    """Commands that end a take and hand the frame rate back to the game."""
    return [
        "mirv_streams record end",
        "host_framerate 0",
    ]


def finish_command(
    take_dir: Path,
    output: Path,
    skip_seconds: float,
    duration_seconds: float,
    speed: float = 1.0,
    ffmpeg: str = "ffmpeg",
    ramps: tuple[tuple[float, float], ...] = (),
    ramp_speed: float = 1.0,
) -> list[str]:
    """ffmpeg arguments that trim a take, add its audio and apply slow motion.

    ramps are (start, end) seconds into the clip played at speed * ramp_speed,
    for a dip into slow motion on a kill within one continuous shot.

    skip_seconds drops the lead-in recorded before the window starts. Speeds
    below 1 stretch both picture and sound, so a slowed shot stays in sync.
    """
    if speed <= 0:
        raise ValueError(f"Speed must be positive: {speed}")
    take_dir = Path(take_dir)
    graph = ramp_filter(speed_pieces(duration_seconds, ramps, speed, ramp_speed))
    return [
        ffmpeg, "-y", "-loglevel", "error",
        "-ss", f"{skip_seconds:.3f}", "-t", f"{duration_seconds:.3f}",
        "-i", str(take_dir / VIDEO_NAME),
        "-ss", f"{skip_seconds:.3f}", "-t", f"{duration_seconds:.3f}",
        "-i", str(take_dir / AUDIO_RELATIVE),
        "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]


def speed_pieces(
    duration: float,
    ramps: tuple[tuple[float, float], ...] = (),
    speed: float = 1.0,
    ramp_speed: float = 1.0,
) -> list[tuple[float, float, float]]:
    """(start, end, speed) stretches covering the clip; ramps in seconds."""
    pieces: list[tuple[float, float, float]] = []
    cursor = 0.0
    for start, end in ramps:
        start, end = max(start, cursor), min(end, duration)
        if end <= start:
            continue
        if start > cursor:
            pieces.append((cursor, start, speed))
        pieces.append((start, end, speed * ramp_speed))
        cursor = end
    if cursor < duration or not pieces:
        pieces.append((cursor, duration, speed))
    return pieces


def ramp_filter(
    pieces: list[tuple[float, float, float]],
    video_in: str = "0:v",
    audio_in: str | None = "1:a",
) -> str:
    """A filter graph playing each stretch at its speed, joined seamlessly.

    Video comes from video_in and sound from audio_in (None for a silent
    capture); the result is labelled [v] and, with sound, [a].
    """
    count = len(pieces)
    has_audio = audio_in is not None
    if count == 1:
        speed = pieces[0][2]
        video, audio = "setpts=PTS-STARTPTS", "asetpts=PTS-STARTPTS"
        if speed != 1.0:
            video += f",setpts=PTS/{speed:g},fps={OUTPUT_FPS}"
            audio += "," + atempo_chain(speed)
        graph = f"[{video_in}]{video}[v]"
        return graph + (f";[{audio_in}]{audio}[a]" if has_audio else "")
    parts = [f"[{video_in}]split={count}" + "".join(f"[sv{i}]" for i in range(count))]
    if has_audio:
        parts.append(f"[{audio_in}]asplit={count}" + "".join(f"[sa{i}]" for i in range(count)))
    joins = []
    for i, (start, end, speed) in enumerate(pieces):
        parts.append(f"[sv{i}]trim=start={start:g}:end={end:g},setpts=(PTS-STARTPTS)/{speed:g}[v{i}]")
        joins.append(f"[v{i}]")
        if has_audio:
            audio = f"atrim=start={start:g}:end={end:g},asetpts=PTS-STARTPTS"
            if speed != 1.0:
                audio += "," + atempo_chain(speed)
            parts.append(f"[sa{i}]{audio}[a{i}]")
            joins[-1] += f"[a{i}]"
    outputs = "[vc][a]" if has_audio else "[vc]"
    parts.append("".join(joins) + f"concat=n={count}:v=1:a={int(has_audio)}{outputs}")
    # Slowed stretches have fewer frames per second; even the output out.
    parts.append(f"[vc]fps={OUTPUT_FPS}[v]")
    return ";".join(parts)


def atempo_chain(speed: float) -> str:
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
