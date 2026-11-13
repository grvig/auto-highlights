"""Laying the player's own music under the reel.

The track loops if it is shorter than the reel, fades in and out, and ducks
whenever the game is loud, so shots and footsteps cut through the music the
way they do in frag movies. Only local files the user picks are used.
"""

from __future__ import annotations

from pathlib import Path

MUSIC_EXTENSIONS = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
# Music level under the game before ducking (1.0 = as recorded).
MUSIC_GAIN = 0.55
FADE_IN_SECONDS = 1.0
FADE_OUT_SECONDS = 2.5


class MusicError(ValueError):
    """Raised for a music file that cannot be used."""


def check_music(path: Path) -> Path:
    path = Path(path)
    if not path.is_file():
        raise MusicError(f"Music file not found: {path}")
    if path.suffix.lower() not in MUSIC_EXTENSIONS:
        raise MusicError(f"Unsupported music format {path.suffix}; use {', '.join(MUSIC_EXTENSIONS)}")
    return path


def music_filter(duration: float, gain: float = MUSIC_GAIN, start: float = 0.0) -> str:
    """Input 0 is the reel, input 1 the looping track. Output label [mix]."""
    fade_out = max(duration - FADE_OUT_SECONDS, 0)
    return ";".join([
        f"[1:a]atrim=start={start:g},asetpts=PTS-STARTPTS,aresample=48000,"
        f"aformat=channel_layouts=stereo,volume={gain:g},"
        f"afade=t=in:d={FADE_IN_SECONDS:g},afade=t=out:st={fade_out:g}:d={FADE_OUT_SECONDS:g},"
        f"atrim=0:{duration:g}[music]",
        "[0:a]asplit=2[game][key]",
        "[music][key]sidechaincompress=threshold=0.04:ratio=6:attack=15:release=350[ducked]",
        "[game][ducked]amix=inputs=2:duration=first:normalize=0[mix]",
    ])


def music_command(
    reel: Path,
    music: Path,
    output: Path,
    duration: float,
    gain: float = MUSIC_GAIN,
    start: float = 0.0,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """ffmpeg arguments that mix music under a finished reel, keeping its picture."""
    return [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(reel), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", music_filter(duration, gain, start),
        "-map", "0:v", "-map", "[mix]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}", str(output),
    ]
