"""Finding the player's demos without making them browse for files.

CS2 saves downloaded match demos into its replays folder, and demos from
FACEIT or friends usually land in Downloads. Both are searched (not
recursively, so a huge Downloads folder stays quick), newest first.
FACEIT's compressed demos (.dem.zst, .dem.gz) are listed too; they are
unpacked when read.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from highlights.engine.unpack import COMPRESSED, unpacked_name
from highlights.recorder.cs2_controller import REPLAYS_RELATIVE

PATTERNS = ("*.dem", *(f"*{suffix}" for suffix in COMPRESSED))


def default_folders(cs2_root: Path | None) -> list[Path]:
    folders = []
    if cs2_root is not None:
        folders.append(Path(cs2_root) / REPLAYS_RELATIVE)
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    folders.append(Path(home) / "Downloads")
    return folders


def find_demos(folders: list[Path], limit: int = 200) -> list[dict]:
    """Demo files in these folders, newest first, one entry per distinct file."""
    found: dict[tuple[str, int], dict] = {}
    for folder in folders:
        try:
            entries = [path for pattern in PATTERNS for path in Path(folder).glob(pattern)]
        except OSError:
            continue
        for path in entries:
            try:
                stat = path.stat()
            except OSError:
                continue
            key = (path.stem.lower(), stat.st_size)  # the same demo copied twice
            if key in found:
                continue
            found[key] = {
                "path": str(path),
                "name": path.name,
                "folder": str(path.parent),
                "megabytes": round(stat.st_size / 1_000_000, 1),
                "compressed": path.suffix.lower() != ".dem",
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes"),
                "_mtime": stat.st_mtime,
            }
    # A packed demo that was also unpacked by hand is the same match twice.
    plain = {d["name"].lower() for d in found.values() if not d["compressed"]}
    unique = [d for d in found.values() if not (d["compressed"] and unpacked_name(d["name"]).lower() in plain)]
    newest = sorted(unique, key=lambda d: d["_mtime"], reverse=True)[:limit]
    for demo in newest:
        del demo["_mtime"]
    return newest
