"""Downloading and installing HLAE releases from GitHub.

The new release is unpacked beside the current copy and only swapped in once
it is complete and holds HLAE.exe, so a failed download never leaves the
user without a working HLAE. The previous copy is kept one generation back.
"""

from __future__ import annotations

import json
import logging
import shutil
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from highlights.recorder.hlae import HLAE_EXE
from highlights.recorder.hlae_release import (
    RELEASES_API,
    VERSION_FILE,
    HlaeRelease,
    ReleaseError,
    installed_version,
    needs_update,
    release_from_listing,
)

logger = logging.getLogger(__name__)

USER_AGENT = "auto-highlights"
Fetcher = Callable[[str], bytes]


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def latest_release(fetch: Fetcher = _fetch) -> HlaeRelease:
    try:
        listing = json.loads(fetch(RELEASES_API).decode("utf-8"))
    except (OSError, ValueError) as error:
        raise ReleaseError(f"Could not check for HLAE releases: {error}") from error
    return release_from_listing(listing)


def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    """Extract, refusing any entry that would land outside the target."""
    root = target.resolve()
    for member in archive.namelist():
        destination = (target / member).resolve()
        if root != destination and root not in destination.parents:
            raise ReleaseError(f"Unsafe path in HLAE archive: {member}")
    archive.extractall(target)


def install_release(release: HlaeRelease, hlae_dir: Path, fetch: Fetcher = _fetch) -> Path:
    """Download a release and swap it in for the copy at hlae_dir."""
    hlae_dir = Path(hlae_dir)
    hlae_dir.parent.mkdir(parents=True, exist_ok=True)
    download = hlae_dir.with_name(f"{hlae_dir.name}-{release.label}.zip")
    staging = hlae_dir.with_name(f"{hlae_dir.name}.new")
    previous = hlae_dir.with_name(f"{hlae_dir.name}.previous")

    logger.info("Downloading HLAE %s", release.label)
    data = fetch(release.zip_url)
    if release.size and len(data) != release.size:
        raise ReleaseError(f"HLAE download was {len(data)} bytes, expected {release.size}")
    download.write_bytes(data)
    try:
        if staging.exists():
            shutil.rmtree(staging)
        with zipfile.ZipFile(download) as archive:
            _safe_extract(archive, staging)
        if not (staging / HLAE_EXE).is_file():
            raise ReleaseError(f"HLAE {release.label} archive has no {HLAE_EXE}")
        (staging / VERSION_FILE).write_text(release.label, encoding="utf-8")
        if hlae_dir.exists():
            if previous.exists():
                shutil.rmtree(previous)
            hlae_dir.rename(previous)
        staging.rename(hlae_dir)
    finally:
        download.unlink(missing_ok=True)
    logger.info("HLAE %s installed at %s", release.label, hlae_dir)
    return hlae_dir


def ensure_current(hlae_dir: Path, fetch: Fetcher = _fetch) -> tuple[str, bool]:
    """Install or update HLAE if a newer release exists. Returns (version, changed)."""
    release = latest_release(fetch)
    if not needs_update(installed_version(hlae_dir), release):
        return release.label, False
    install_release(release, hlae_dir, fetch)
    return release.label, True
