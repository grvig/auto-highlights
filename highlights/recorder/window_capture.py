"""Real-time capture of the CS2 window, the fallback when HLAE is unavailable.

ffmpeg's gfxcapture grabs the game window itself through Windows Graphics
Capture, so overlapping windows and a black GDI surface do not matter. The
capture starts while the demo is paused and stops after it pauses again, so
the moment playback started is found afterwards: paused frames are pixel
identical (within the anti-aliasing shimmer), which freezedetect can see.

Game audio, when wanted, comes either from the speakers themselves (WASAPI
loopback, passed in through a named pipe; see loopback.py) or from a dshow
loopback device. Both reach ffmpeg ahead of the matching frames, so each is
delayed by its own measured amount.
"""

from __future__ import annotations

import re
from pathlib import Path

from highlights.recorder.mirv import ramp_filter, speed_pieces

# Measured against weapon_fire ticks: loopback audio arrives this early.
AUDIO_DELAY_SECONDS = 0.55
# The speakers' sound through the pipe, measured against the dshow device.
LOOPBACK_DELAY_SECONDS = 0.55
# audio_device value meaning "the speakers, through WASAPI loopback".
LOOPBACK = "loopback"
# Paused CS2 frames still shimmer slightly; -45dB treats that as frozen.
FREEZE_NOISE = "-45dB"
FREEZE_MIN_SECONDS = 0.3
# A leading freeze may start a few frames in, before the paused image settles.
LEADING_FREEZE_GRACE = 0.6


def capture_command(
    output: Path,
    framerate: int = 60,
    audio_device: str | None = None,
    ffmpeg: str = "ffmpeg",
    audio_pipe: str | None = None,
) -> list[str]:
    """ffmpeg arguments that record the CS2 window until sent "q".

    With audio_pipe, the game sound is raw float stereo read from that pipe;
    otherwise audio_device names a dshow loopback device, if any.
    """
    source = f"gfxcapture=window_exe=cs2\\.exe:capture_cursor=0:max_framerate={int(framerate)}"
    args = [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", source]
    if audio_pipe:
        args += [
            "-itsoffset", f"{LOOPBACK_DELAY_SECONDS}", "-f", "f32le", "-ar", "48000", "-ac", "2",
            "-thread_queue_size", "1024", "-i", audio_pipe,
        ]
    elif audio_device:
        args += [
            "-itsoffset", f"{AUDIO_DELAY_SECONDS}", "-f", "dshow",
            "-audio_buffer_size", "20", "-i", f"audio={audio_device}",
        ]
    args += [
        "-filter_complex", "[0:v]hwdownload,format=bgra[v]", "-map", "[v]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-pix_fmt", "yuv420p",
    ]
    if audio_pipe or audio_device:
        args += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    return args + [str(output)]


def freeze_probe_command(raw: Path, ffmpeg: str = "ffmpeg") -> list[str]:
    """ffmpeg arguments that log every frozen stretch of a capture."""
    return [
        ffmpeg, "-hide_banner", "-i", str(raw),
        "-vf", f"freezedetect=n={FREEZE_NOISE}:d={FREEZE_MIN_SECONDS}",
        "-map", "0:v", "-f", "null", "-",
    ]


def motion_start(freeze_log: str, played_seconds: float | None = None) -> float:
    """Seconds into a capture where playback began, from freezedetect's log.

    The paused stretch at the start ends when playback begins. If that
    stretch was not detected, the end is used instead: playback stops on the
    exact target tick, so it began played_seconds before the final freeze.
    """
    starts = [float(v) for v in re.findall(r"freeze_start: ([\d.]+)", freeze_log)]
    ends = [float(v) for v in re.findall(r"freeze_end: ([\d.]+)", freeze_log)]
    if starts and starts[0] < LEADING_FREEZE_GRACE and ends:
        return ends[0]
    if played_seconds and starts:
        return max(0.0, starts[-1] - played_seconds)
    return 0.0


def trim_command(
    raw: Path,
    output: Path,
    begin_seconds: float,
    duration_seconds: float,
    framerate: int = 60,
    ffmpeg: str = "ffmpeg",
    speed: float = 1.0,
    has_audio: bool = False,
    ramps: tuple[tuple[float, float], ...] = (),
    ramp_speed: float = 1.0,
) -> list[str]:
    """ffmpeg arguments that cut the played window out of a raw capture.

    Speed and ramps slow picture (and sound, when captured) the same way the
    HLAE backend finishes its takes. The cut length is an input limit, so
    slowed footage keeps its full stretched length.
    """
    if speed <= 0:
        raise ValueError(f"Speed must be positive: {speed}")
    pieces = speed_pieces(duration_seconds, ramps, speed, ramp_speed)
    graph = ramp_filter(pieces, "0:v", "0:a" if has_audio else None)
    maps = ["-map", "[v]"] + (["-map", "[a]"] if has_audio else [])
    return [
        ffmpeg, "-y", "-loglevel", "error",
        "-ss", f"{begin_seconds:.3f}", "-t", f"{duration_seconds:.3f}", "-i", str(raw),
        "-filter_complex", graph, *maps,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", str(int(framerate)), "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
