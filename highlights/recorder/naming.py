"""Clip filenames and output paths.

Player names come straight from a match and are wildly unsafe as filenames —
real examples from sample demos include "@!<$#" and "( ͡ʘ ͜ʖ ͡ʘ)". Everything
that reaches the filesystem goes through here.
"""

from __future__ import annotations

from pathlib import Path

from highlights.engine.clip_plan import ClipPlan
from highlights.recorder.base import ClipRequest

DEFAULT_EXTENSION = "mkv"

# Longest a single sanitised name fragment may be, to keep total paths short.
MAX_PART_LENGTH = 24

# Windows refuses these as filenames regardless of extension.
_RESERVED_STEMS = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def sanitise_part(text: str, fallback: str = "player") -> str:
    """Reduce arbitrary text to a safe filename fragment.

    Keeps letters, digits, hyphens and underscores — including non-Latin
    letters, which NTFS handles fine — and drops everything else rather than
    trying to guess a transliteration. Falls back when nothing usable is left.
    """
    kept = [
        char if (char.isalnum() or char in "-_") else " " for char in text.strip()
    ]
    collapsed = "_".join("".join(kept).split())
    collapsed = collapsed.strip("._-")[:MAX_PART_LENGTH].strip("._-")

    if not collapsed or collapsed.lower() in _RESERVED_STEMS:
        return fallback
    return collapsed


def clip_filename(
    index: int,
    round_number: int,
    highlight_type: str,
    player_name: str,
    extension: str = DEFAULT_EXTENSION,
    part: int | None = None,
) -> str:
    """Build one clip's filename.

    Index-first so clips sort in plan order on disk, which is exactly the order
    the stitcher needs. Parts of a segmented moment carry a -NN suffix on the
    index (001-01, 001-02), which still sorts before 002.
    """
    player = sanitise_part(player_name)
    kind = sanitise_part(str(highlight_type), fallback="clip")
    number = f"{index:03d}" if part is None else f"{index:03d}-{part:02d}"
    return f"{number}_r{round_number:02d}_{kind}_{player}.{extension}"


def build_clip_requests(
    plan: ClipPlan,
    demo_path: Path,
    player_name: str,
    output_dir: Path,
    extension: str = DEFAULT_EXTENSION,
) -> list[ClipRequest]:
    """Turn a ClipPlan into numbered, named requests, one per recorded window."""
    requests: list[ClipRequest] = []
    for index, moment in enumerate(plan.moments, start=1):
        windows = moment.windows
        for part, window in enumerate(windows, start=1):
            filename = clip_filename(
                index=index,
                round_number=moment.round_number,
                highlight_type=str(moment.highlight_type),
                player_name=player_name,
                extension=extension,
                part=part if len(windows) > 1 else None,
            )
            requests.append(
                ClipRequest(
                    index=index,
                    moment=moment,
                    # A moment from a multi-demo plan names its own demo.
                    demo_path=Path(moment.source_demo or demo_path),
                    player_name=player_name,
                    output_path=Path(output_dir) / filename,
                    segment=window,
                    part=part,
                    parts=len(windows),
                )
            )
    return requests
