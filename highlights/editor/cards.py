"""Title and outro cards: short full-screen text slates.

Cards are rendered at the clips' own size, frame rate and audio layout (with
silence), so they join the reel without forcing a re-encode mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from highlights.editor.encoding import INTERMEDIATE_VIDEO
from highlights.editor.fonts import filter_path, find_font

BACKGROUND = "0x0b0d12"
ACCENT = "0xf2a93b"
FADE_SECONDS = 0.4


@dataclass(frozen=True)
class CardLine:
    text: str
    # Height of the text as a fraction of the frame height.
    scale: float
    color: str = "white"


def pretty_map(name: str) -> str:
    """ "de_nuke" -> "Nuke", "cs_office" -> "Office"; other names unchanged."""
    for prefix in ("de_", "cs_", "ar_", "dz_"):
        if name.lower().startswith(prefix):
            return name[len(prefix):].replace("_", " ").title()
    return name


def title_lines(player_name: str, maps: list[str], moments: int) -> list[CardLine]:
    detail = "  ·  ".join(pretty_map(m) for m in maps) if maps else "HIGHLIGHTS"
    return [
        CardLine(player_name, 0.11),
        CardLine(detail.upper(), 0.035, ACCENT),
        CardLine(f"{moments} HIGHLIGHT{'S' if moments != 1 else ''}", 0.028),
    ]


def outro_lines(player_name: str, kills: int | None = None) -> list[CardLine]:
    lines = [CardLine("GG", 0.12, ACCENT), CardLine(player_name, 0.045)]
    if kills:
        lines.append(CardLine(f"{kills} KILLS SHOWN", 0.028))
    return lines


def card_command(
    lines: list[CardLine],
    output: Path,
    work_dir: Path,
    duration: float = 2.5,
    width: int = 1440,
    height: int = 1080,
    fps: int = 60,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """ffmpeg arguments that render a card with silent stereo audio."""
    work_dir.mkdir(parents=True, exist_ok=True)
    sizes = [round(height * line.scale) for line in lines]
    gap = round(height * 0.025)
    block = sum(sizes) + gap * (len(lines) - 1)
    y = (height - block) // 2
    draws = []
    for number, (line, size) in enumerate(zip(lines, sizes)):
        text_file = work_dir / f"card_{output.stem}_{number}.txt"
        text_file.write_text(line.text, encoding="utf-8")
        draws.append(
            f"drawtext=fontfile='{filter_path(find_font(line.text))}':"
            f"textfile='{filter_path(text_file)}':fontsize={size}:fontcolor={line.color}:"
            f"x=(w-tw)/2:y={y}"
        )
        y += size + gap
    fade_out = max(duration - FADE_SECONDS, 0)
    video = ",".join(draws + [
        f"fade=t=in:st=0:d={FADE_SECONDS}", f"fade=t=out:st={fade_out:g}:d={FADE_SECONDS}",
        "format=yuv420p",
    ])
    return [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c={BACKGROUND}:s={width}x{height}:r={fps}:d={duration:g}",
        "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration:g}",
        "-vf", video, *INTERMEDIATE_VIDEO,
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(output),
    ]
