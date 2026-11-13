"""Lower-third captions naming each highlight.

Each moment gets a two-line caption: a bold headline ("ACE + 1V3 CLUTCH")
and a quieter line with the player, map and round. Text is handed to ffmpeg
through files rather than inline, so names full of quotes, colons or CJK
characters need no escaping at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from highlights.editor.cards import pretty_map
from highlights.editor.fonts import filter_path, find_font
from highlights.engine.moments import Moment

# Seconds the caption takes to fade in and out, and how long it stays.
FADE_SECONDS = 0.25
SHOW_SECONDS = 2.6
START_SECONDS = 0.3
# Translucent backing so white text stays readable on bright maps like Nuke.
BOX_OPACITY = 0.45


@dataclass(frozen=True)
class Caption:
    headline: str
    detail: str


def headline_for(moment: Moment) -> str:
    """ "ACE (5 kills) + 1v3 clutch (won)" -> "ACE + 1V3 CLUTCH"."""
    parts = [re.sub(r"\s*\([^)]*\)", "", part).strip() for part in moment.description.split("+")]
    return " + ".join(part.upper() for part in parts if part)


def caption_for(moment: Moment, player_name: str, map_name: str | None = None) -> Caption:
    detail = [player_name]
    if map_name:
        detail.append(pretty_map(map_name))
    detail.append(f"Round {moment.round_number}")
    return Caption(headline_for(moment), "  ·  ".join(detail))


def replay_caption(camera_name: str) -> Caption:
    """Marks a victim cam, so it is not mistaken for the player's own view."""
    return Caption("REPLAY", f"{camera_name}'s view")


def _alpha(start: float, end: float) -> str:
    """Opacity expression: fade in at start, hold, fade out before end."""
    f = FADE_SECONDS
    return (
        f"if(lt(t,{start:g}),0,if(lt(t,{start + f:g}),(t-{start:g})/{f:g},"
        f"if(lt(t,{end - f:g}),1,if(lt(t,{end:g}),({end:g}-t)/{f:g},0))))"
    )


def caption_filter(caption: Caption, work_dir: Path, height: int = 1080) -> str:
    """A drawtext chain that shows the caption in the lower left."""
    work_dir.mkdir(parents=True, exist_ok=True)
    start, end = START_SECONDS, START_SECONDS + SHOW_SECONDS
    alpha = _alpha(start, end)
    margin = round(height * 0.06)
    big, small = round(height * 0.055), round(height * 0.03)
    filters = []
    for name, text, size, y in (
        ("headline", caption.headline, big, f"h-{margin}-{small}-{round(small * 0.6)}-th"),
        ("detail", caption.detail, small, f"h-{margin}-th"),
    ):
        text_file = work_dir / f"caption_{name}.txt"
        text_file.write_text(text, encoding="utf-8")
        filters.append(
            f"drawtext=fontfile='{filter_path(find_font(text))}':"
            f"textfile='{filter_path(text_file)}':fontsize={size}:fontcolor=white:"
            f"x={margin}:y={y}:shadowcolor=black@0.7:shadowx=2:shadowy=2:"
            f"box=1:boxcolor=black@{BOX_OPACITY}:boxborderw={round(size * 0.25)}:"
            f"alpha='{alpha}'"
        )
    return ",".join(filters)
