"""Knowing which HLAE release is newest, and which one is installed.

CS2 updates regularly break HLAE's hook until a new HLAE ships, so the app
checks the official GitHub releases and keeps its copy current. This half is
pure: parsing the release listing and comparing versions. Fetching and
unpacking live in hlae_update.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

RELEASES_API = "https://api.github.com/repos/advancedfx/advancedfx/releases/latest"
# Written into the HLAE folder after an install, since HLAE.exe carries no
# version that is easy to read without running it.
VERSION_FILE = "auto-highlights-version.txt"

_ZIP_NAME = re.compile(r"^hlae_(\d+)_(\d+)_(\d+)\.zip$", re.IGNORECASE)


class ReleaseError(Exception):
    """Raised when the release listing has no usable HLAE download."""


@dataclass(frozen=True)
class HlaeRelease:
    version: tuple[int, int, int]
    zip_url: str
    size: int
    # When GitHub published it: an HLAE older than the newest CS2 update may
    # not hook that build yet.
    published: datetime | None = None

    @property
    def label(self) -> str:
        return ".".join(map(str, self.version))


def parse_version(text: str) -> tuple[int, int, int] | None:
    """ "v2.193.0" or "2.193.0" -> (2, 193, 0)."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def release_from_listing(listing: dict) -> HlaeRelease:
    """The portable zip of a release from GitHub's JSON (not the installer)."""
    for asset in listing.get("assets", []):
        match = _ZIP_NAME.match(str(asset.get("name", "")))
        if match:
            return HlaeRelease(
                version=tuple(int(part) for part in match.groups()),  # type: ignore[arg-type]
                zip_url=str(asset["browser_download_url"]),
                size=int(asset.get("size", 0)),
                published=parse_time(listing.get("published_at")),
            )
    raise ReleaseError(f"No HLAE zip in release {listing.get('tag_name', '?')}")


def parse_time(text: object) -> datetime | None:
    """GitHub's "2026-11-07T14:14:48Z" as a local, naive datetime."""
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.astimezone().replace(tzinfo=None) if moment.tzinfo else moment


def marker_text(release: HlaeRelease) -> str:
    """The installed-version marker: version, then when it was published."""
    published = release.published.isoformat(timespec="seconds") if release.published else ""
    return f"{release.label}\n{published}\n"


def installed_published(hlae_dir: Path) -> datetime | None:
    try:
        lines = (Path(hlae_dir) / VERSION_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    return parse_time(lines[1]) if len(lines) > 1 and lines[1].strip() else None


def installed_version(hlae_dir: Path) -> tuple[int, int, int] | None:
    marker = Path(hlae_dir) / VERSION_FILE
    try:
        return parse_version(marker.read_text(encoding="utf-8"))
    except OSError:
        return None


def needs_update(installed: tuple[int, int, int] | None, latest: HlaeRelease) -> bool:
    return installed is None or installed < latest.version
