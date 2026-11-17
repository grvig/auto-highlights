"""Fetching ffmpeg for an installed copy that has none.

Uses the official Windows release builds linked from ffmpeg.org (gyan.dev),
checked against their published SHA-256, unpacked beside the other tools,
and refused if it lacks a filter the app depends on.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

RELEASE_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
RELEASE_SHA = RELEASE_ZIP + ".sha256"
USER_AGENT = "auto-highlights"

# Filters the recorder and editor use; a build without them is no good.
REQUIRED_FILTERS = (
    "gfxcapture", "drawtext", "xfade", "acrossfade", "loudnorm", "alimiter",
    "sidechaincompress", "zoompan", "freezedetect",
)

Downloader = Callable[[str, Path], None]
TextFetcher = Callable[[str], str]


class FfmpegSetupError(Exception):
    """Raised when ffmpeg cannot be downloaded or is unusable."""


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ffmpeg_exe(folder: Path) -> Path:
    return Path(folder) / "bin" / "ffmpeg.exe"


def missing_filters(ffmpeg: Path) -> list[str]:
    listing = subprocess.run([str(ffmpeg), "-hide_banner", "-filters"],
                             capture_output=True, text=True).stdout
    names = {line.split()[1] for line in listing.splitlines() if len(line.split()) > 2}
    return [name for name in REQUIRED_FILTERS if name not in names]


def install_ffmpeg(
    folder: Path,
    download: Downloader = _download,
    fetch_text: TextFetcher = _fetch_text,
    check: Callable[[Path], list[str]] = missing_filters,
) -> Path:
    """Download, verify and unpack ffmpeg into folder. Returns ffmpeg.exe."""
    folder = Path(folder)
    folder.parent.mkdir(parents=True, exist_ok=True)
    archive = folder.with_name(folder.name + "-download.zip")
    staging = folder.with_name(folder.name + ".new")
    try:
        expected = fetch_text(RELEASE_SHA).split()[0].strip().lower()
        logger.info("Downloading ffmpeg from %s", RELEASE_ZIP)
        download(RELEASE_ZIP, archive)
        if sha256_of(archive) != expected:
            raise FfmpegSetupError("The ffmpeg download did not match its published checksum")
        shutil.rmtree(staging, ignore_errors=True)
        with zipfile.ZipFile(archive) as zipped:
            root = staging.resolve()
            for member in zipped.namelist():
                destination = (staging / member).resolve()
                if root != destination and root not in destination.parents:
                    raise FfmpegSetupError(f"Unsafe path in the ffmpeg archive: {member}")
            zipped.extractall(staging)
        # the archive holds one top folder (ffmpeg-9.0.2-essentials_build)
        inner = next((p for p in staging.iterdir() if ffmpeg_exe(p).is_file()), None)
        if inner is None:
            raise FfmpegSetupError("The ffmpeg download has no bin/ffmpeg.exe")
        lacking = check(ffmpeg_exe(inner))
        if lacking:
            raise FfmpegSetupError(f"This ffmpeg build lacks: {', '.join(lacking)}")
        shutil.rmtree(folder, ignore_errors=True)
        inner.rename(folder)
    except OSError as error:
        raise FfmpegSetupError(f"Could not set up ffmpeg: {error}") from error
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
    logger.info("ffmpeg ready at %s", ffmpeg_exe(folder))
    return ffmpeg_exe(folder)
