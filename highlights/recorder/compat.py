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
# Written into HLAE's folder once it has recorded on a CS2 build, so an HLAE
# that turned out to work on the new build stops being warned about.
WORKED_FILE = "auto-highlights-cs2-build.txt"
# An update this recent is worth mentioning when something breaks.
RECENT = timedelta(days=14)


def manifest_path(cs2_root: Path) -> Path:
    """steamapps/appmanifest_730.acf, two folders above the game's root."""
    return Path(cs2_root).parent.parent / f"appmanifest_{CS2_APP_ID}.acf"


def _manifest_value(cs2_root: Path | None, key: str) -> str | None:
    if cs2_root is None:
        return None
    try:
        text = manifest_path(cs2_root).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(rf'"{key}"\s+"(\d+)"', text)
    return match.group(1) if match else None


def cs2_updated_at(cs2_root: Path | None) -> datetime | None:
    """When Steam last updated CS2, or None if it cannot be told."""
    stamp = _manifest_value(cs2_root, "LastUpdated")
    return datetime.fromtimestamp(int(stamp)) if stamp else None


def cs2_build(cs2_root: Path | None) -> str | None:
    """Steam's build id for the installed CS2."""
    return _manifest_value(cs2_root, "buildid")


def mark_hlae_working(hlae_dir: Path, cs2_root: Path | None) -> None:
    """Note that this HLAE has recorded on the installed CS2 build."""
    build = cs2_build(cs2_root)
    if build:
        (Path(hlae_dir) / WORKED_FILE).write_text(build + "\n", encoding="utf-8")


def hlae_worked_on(hlae_dir: Path | None) -> str | None:
    """The CS2 build this HLAE last recorded on, if any."""
    if hlae_dir is None:
        return None
    try:
        return (Path(hlae_dir) / WORKED_FILE).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def recent_update(cs2_root: Path | None, now: datetime | None = None) -> datetime | None:
    """The last update time, but only when it was recent enough to blame."""
    updated = cs2_updated_at(cs2_root)
    if updated is None:
        return None
    return updated if (now or datetime.now()) - updated <= RECENT else None


def hlae_older_than_game(hlae_published: datetime | None, cs2_root: Path | None,
                         now: datetime | None = None, worked_on: str | None = None) -> bool:
    """Whether the installed HLAE came out before CS2's latest (recent) update
    and has not yet been seen recording on that build."""
    if worked_on and worked_on == cs2_build(cs2_root):
        return False
    updated = recent_update(cs2_root, now)
    return bool(updated and hlae_published and hlae_published < updated)


# HLAE's hook prints this when a CS2 update moved the code it patches; from
# then on demos never load, so waiting for one is pointless.
HOOK_BROKEN = r"Could not find address for pattern"


def hook_unsupported_message(cs2_root: Path | None) -> str:
    build = cs2_build(cs2_root)
    which = f"CS2 build {build}" if build else "this CS2 build"
    return (f"HLAE cannot hook {which} yet: it needs an HLAE update for the latest CS2 patch. "
            "Window capture still records; set recorder = \"window\" until HLAE is updated.")


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
