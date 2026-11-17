"""The reels the app has made, for a "your reels" list."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# player_highlights_2026-11-16_0839.mp4 (with an optional _2, _3 ... suffix)
REEL_NAME = re.compile(r"^(?P<player>.+)_highlights_(?P<stamp>\d{4}-\d{2}-\d{2}_\d{4})(?:_\d+)?\.mp4$")


def list_reels(output_dir: Path) -> list[dict]:
    """Every reel in output_dir, newest first, with its extras when present."""
    reels = []
    for video in Path(output_dir).glob("*_highlights_*.mp4"):
        match = REEL_NAME.match(video.name)
        if not match:
            continue
        try:
            stat = video.stat()
        except OSError:
            continue
        made = datetime.strptime(match["stamp"], "%Y-%m-%d_%H%M")
        thumbnail = video.with_suffix(".thumbnail.png")
        chapters = video.with_suffix(".chapters.txt")
        reels.append({
            "path": str(video),
            "player": match["player"],
            "made": made.isoformat(timespec="minutes"),
            "megabytes": round(stat.st_size / 1_000_000, 1),
            "thumbnail": str(thumbnail) if thumbnail.is_file() else None,
            "chapters": chapters.read_text(encoding="utf-8") if chapters.is_file() else None,
            "_sort": (made, stat.st_mtime),
        })
    reels.sort(key=lambda r: r["_sort"], reverse=True)
    for reel in reels:
        del reel["_sort"]
    return reels
