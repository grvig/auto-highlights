"""Frag-movie effects timed to the shot: a punch-in zoom and a kill flash.

Both are smooth bumps centred on the moment a kill lands, built as ffmpeg
expressions over the clip's own time. A punch-in briefly zooms toward the
crosshair on a headshot; a flash lifts the brightness for a few frames on
every kill.
"""

from __future__ import annotations

PUNCH_AMOUNT = 0.09  # peak zoom: 9% closer
PUNCH_WIDTH = 0.16  # seconds either side of the peak
FLASH_AMOUNT = 0.22  # peak brightness lift (eq scale, -1..1)
FLASH_WIDTH = 0.05


def _bumps(times: list[float], amount: float, width: float, var: str) -> str:
    """A sum of gaussian bumps peaking at each time; 0 everywhere else."""
    return "+".join(f"{amount:g}*exp(-pow(({var}-{t:.3f})/{width:g},2))" for t in times)


def punch_in_filter(times: list[float], width: int, height: int, fps: int = 60) -> str:
    """Zoom toward the centre (the crosshair) and back at each time."""
    zoom = f"1+{_bumps(times, PUNCH_AMOUNT, PUNCH_WIDTH, 'it')}"
    return (
        f"zoompan=z='{zoom}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:fps={fps}"
    )


def flash_filter(times: list[float]) -> str:
    """Brighten for a few frames at each time."""
    return f"eq=brightness='{_bumps(times, FLASH_AMOUNT, FLASH_WIDTH, 't')}':eval=frame"


def effect_filters(
    punches: list[float], flashes: list[float], width: int, height: int, fps: int = 60
) -> list[str]:
    """The effect filters a clip needs, in the order they should run."""
    filters = []
    if punches:
        filters.append(punch_in_filter(punches, width, height, fps))
    if flashes:
        filters.append(flash_filter(flashes))
    return filters
