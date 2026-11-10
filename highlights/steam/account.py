"""The Steam account signed in on this machine.

Steam lists every account that has logged in locally in config/loginusers.vdf
and flags the most recent one. That is almost always the person making the
reel, so it lets the app preselect "you" in every demo.

Only the public SteamID64 and display name are read. The account's login name
sits in the same file and is deliberately never touched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from highlights.steam.vdf import VdfError, get_ci, loads

logger = logging.getLogger(__name__)

LOGIN_USERS = Path("config/loginusers.vdf")


@dataclass(frozen=True)
class SteamAccount:
    steamid: str
    persona_name: str


def _timestamp(entry: dict) -> int:
    raw = get_ci(entry, "Timestamp")
    return int(raw) if isinstance(raw, str) and raw.isdigit() else 0


def signed_in_account(steam_root: Path) -> SteamAccount | None:
    """The most recently signed-in account, or None if it cannot be read."""
    path = steam_root / LOGIN_USERS
    try:
        data = loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, VdfError) as error:
        logger.debug("Could not read %s: %s", path, error)
        return None

    users = get_ci(data, "users")
    if not isinstance(users, dict):
        return None
    accounts = [
        (steamid, entry)
        for steamid, entry in users.items()
        if steamid.isdigit() and isinstance(entry, dict)
    ]
    if not accounts:
        return None

    flagged = [a for a in accounts if get_ci(a[1], "MostRecent") == "1"]
    steamid, entry = flagged[0] if flagged else max(accounts, key=lambda a: _timestamp(a[1]))
    name = get_ci(entry, "PersonaName")
    return SteamAccount(steamid=steamid, persona_name=name if isinstance(name, str) else "")
