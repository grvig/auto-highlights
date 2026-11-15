"""A text preview of the edit, for dry runs: what the reel will show, in order."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from highlights.editor.captions import caption_for, replay_caption
from highlights.editor.cards import pretty_map
from highlights.editor.reel import EditOptions
from highlights.recorder.base import ClipRequest


def describe_edit(
    requests: list[ClipRequest],
    options: EditOptions,
    tempo: Callable[[Path], float | None] | None = None,
) -> list[str]:
    """One line per piece of the reel, title to outro."""
    lines: list[str] = []
    if options.cards:
        maps = sorted({pretty_map(m) for m in options.maps.values() if m})
        lines.append(f"[title]  {options.player_name}  {' / '.join(maps)}")
    for request in requests:
        caption = ""
        if options.captions and request.camera_name and request.window.pov_steamid:
            cap = replay_caption(request.camera_name)
            caption = f"{cap.headline} - {cap.detail}"
        elif options.captions and request.part == 1:
            cap = caption_for(request.moment, options.player_name,
                              options.maps.get(Path(request.demo_path)))
            caption = f"{cap.headline} - {cap.detail}"
        speed = "" if request.speed == 1.0 else f" x{request.speed:g}"
        if request.window.ramps:
            speed += f" slow-mo x{len(request.window.ramps)}"
        lines.append(f"{request.label:<10} {request.duration_seconds:5.1f}s{speed}  {caption}".rstrip())
    if options.cards:
        kills = f"  {options.kills_shown} kills" if options.kills_shown else ""
        lines.append(f"[outro]  GG{kills}")
    join = "hard cuts" if options.transition == "cut" else f"{options.transition} transitions"
    if options.music:
        bpm = tempo(options.music) if tempo else None
        beat = f", cuts on the beat ({bpm:.0f} BPM)" if bpm else ", cuts on the beat"
        lines.append(f"Music: {options.music.name}{beat}; {join}")
    else:
        lines.append(f"No music; {join}")
    return lines
