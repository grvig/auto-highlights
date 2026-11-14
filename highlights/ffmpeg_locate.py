"""Finding ffmpeg when it is not on PATH.

A winget install of ffmpeg only reaches PATH in shells opened afterwards, and
the app ships its own copy, so a bare "ffmpeg" is looked up in those places
too before giving up.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

BUNDLED = Path(__file__).resolve().parents[1] / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
WINGET_PACKAGES = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"


def locate_ffmpeg(
    configured: str = "ffmpeg",
    bundled: Path = BUNDLED,
    winget_packages: Path = WINGET_PACKAGES,
) -> str:
    """The ffmpeg to run: an explicit path as given, else PATH, bundled, winget."""
    if configured != "ffmpeg":
        return configured
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    if bundled.is_file():
        return str(bundled)
    if winget_packages.is_dir():
        found = sorted(winget_packages.glob("*FFmpeg*/*/bin/ffmpeg.exe"), reverse=True)
        if found:
            return str(found[0])
    return configured
