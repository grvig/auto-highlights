"""Telling the player when a newer auto-highlights is out.

The latest release is read from GitHub's public API (no account needed). A
failed check is not an error: the app just does not mention updates.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from collections.abc import Callable

from highlights import __version__

logger = logging.getLogger(__name__)

REPO = "grvig/auto-highlights"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
Fetch = Callable[[str], bytes]


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "auto-highlights",
                                                   "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read()


def version_tuple(text: str) -> tuple[int, ...] | None:
    match = re.match(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def check_for_update(current: str = __version__, fetch: Fetch = _fetch) -> dict:
    """{"available": bool, "version": "1.0.1", "url": release page}."""
    try:
        release = json.loads(fetch(LATEST).decode("utf-8"))
    except (OSError, ValueError) as error:
        logger.info("Could not check for updates: %s", error)
        return {"available": False}
    latest = version_tuple(str(release.get("tag_name", "")))
    mine = version_tuple(current)
    if latest is None or mine is None or latest <= mine:
        return {"available": False}
    url = str(release.get("html_url") or RELEASES_PAGE)
    if not url.startswith(RELEASES_PAGE):
        url = RELEASES_PAGE
    return {"available": True, "version": ".".join(map(str, latest)), "url": url}
