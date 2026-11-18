"""Explaining failures that a recent CS2 update is the likely cause of.

CS2 updates regularly break HLAE's hook until HLAE ships a fix, and can stop
the game playing demos recorded on older builds. When either symptom shows
up shortly after an update, the error says so and suggests what to do,
instead of a bare timeout. The update time comes from Steam's own manifest
for the game, so nothing goes over the network.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

CS2_APP_ID = 730
# An update this recent is worth mentioning when something breaks.
RECENT = timedelta(days=14)


def manifest_path(cs2_root: Path) -> Path:
    """steamapps/appmanifest_730.acf, two folders above the game's root."""
    return Path(cs2_root).parent.parent / f"appmanifest_{CS2_APP_ID}.acf"


def cs2_updated_at(cs2_root: Path | None) -> datetime | None:
    """When Steam last updated CS2, or None if it cannot be told."""
    if cs2_root is None:
        return None
    try:
        text = manifest_path(cs2_root).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r'"LastUpdated"\s+"(\d+)"', text)
    return datetime.fromtimestamp(int(match.group(1))) if match else None


def recent_update(cs2_root: Path | None, now: datetime | None = None) -> datetime | None:
    """The last update time, but only when it was recent enough to blame."""
    updated = cs2_updated_at(cs2_root)
    if updated is None:
        return None
    return updated if (now or datetime.now()) - updated <= RECENT else None


def hlae_older_than_game(hlae_published: datetime | None, cs2_root: Path | None,
                         now: datetime | None = None) -> bool:
    """Whether the installed HLAE came out before CS2's latest (recent) update."""
    updated = recent_update(cs2_root, now)
    return bool(updated and hlae_published and hlae_published < updated)


def hook_failure_hint(cs2_root: Path | None, now: datetime | None = None) -> str:
    updated = recent_update(cs2_root, now)
    if updated is None:
        return ""
    return (f" CS2 was updated on {updated:%d %b %Y}; HLAE may not support this build yet. "
            "It updates itself once a fix is out, or set recorder = \"window\" meanwhile.")


def old_demo_hint(cs2_root: Path | None, now: datetime | None = None) -> str:
    updated = recent_update(cs2_root, now)
    if updated is None:
        return ""
    return (f" CS2 was updated on {updated:%d %b %Y}; it may refuse demos recorded "
            "before that update.")
