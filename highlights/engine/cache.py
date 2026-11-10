"""On-disk cache of parsed demos.

Parsing a demo takes several seconds; reading its tables back from Parquet takes
a fraction of that. Each demo gets a folder keyed by its name, size and
modification time, so an edited or replaced file is never served stale.

Entries are written to a temporary folder and renamed into place, with the
header written last, so a crash mid-write leaves nothing that looks complete.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

# Bump when parsing changes shape, so old entries are ignored rather than misread.
CACHE_VERSION = 1

HEADER_FILE = "header.json"


@dataclass(frozen=True)
class CachedDemo:
    header: dict
    frames: dict[str, pl.DataFrame]


class DemoCache:
    """Parsed demo tables stored as Parquet under one root folder."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def key_for(self, demo_path: Path) -> str:
        stat = demo_path.stat()
        identity = f"{CACHE_VERSION}|{demo_path.name}|{stat.st_size}|{stat.st_mtime_ns}"
        return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:20]

    def entry_dir(self, demo_path: Path) -> Path:
        return self.root / self.key_for(demo_path)

    def load(self, demo_path: Path) -> CachedDemo | None:
        """The cached tables for a demo, or None on a miss or damaged entry."""
        entry = self.entry_dir(demo_path)
        header_file = entry / HEADER_FILE
        if not header_file.is_file():
            return None
        try:
            header = json.loads(header_file.read_text(encoding="utf-8"))
            frames = {
                path.stem: pl.read_parquet(path) for path in entry.glob("*.parquet")
            }
        except (OSError, ValueError, pl.exceptions.PolarsError) as error:
            logger.warning("Ignoring damaged cache entry %s: %s", entry, error)
            return None
        logger.info("Loaded %s from cache", demo_path.name)
        return CachedDemo(header=header, frames=frames)

    def store(
        self, demo_path: Path, header: dict, frames: dict[str, pl.DataFrame | None]
    ) -> Path:
        """Write a demo's tables, replacing any older entry atomically."""
        entry = self.entry_dir(demo_path)
        staging = entry.with_name(f"{entry.name}.tmp-{os.getpid()}")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)

        for name, frame in frames.items():
            if frame is not None:
                frame.write_parquet(staging / f"{name}.parquet")
        # The header goes last: its presence marks the entry as complete.
        (staging / HEADER_FILE).write_text(json.dumps(header), encoding="utf-8")

        shutil.rmtree(entry, ignore_errors=True)
        staging.rename(entry)
        logger.info("Cached %s in %s", demo_path.name, entry)
        return entry
