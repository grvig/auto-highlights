"""Finding Steam and the CS2 install on this machine.

Steam records its own location in the registry and its game libraries in
libraryfolders.vdf. A library that lists CS2 is not trusted on its own: Steam
can leave an empty folder with the game's name behind, so the install is only
accepted once cs2.exe is actually there.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from highlights.steam.vdf import VdfError, get_ci, loads

logger = logging.getLogger(__name__)

CS2_APP_ID = "730"
CS2_FOLDER = Path("steamapps/common/Counter-Strike Global Offensive")
CS2_EXE_RELATIVE = Path("game/bin/win64/cs2.exe")

DEFAULT_STEAM_ROOTS = (
    Path("C:/Program Files (x86)/Steam"),
    Path("C:/Program Files/Steam"),
)

# (hive, key, value) -> str | None, injectable so tests need no registry.
RegistryReader = Callable[[str, str, str], "str | None"]


def _read_registry(hive: str, key: str, value: str) -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    root = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}[hive]
    try:
        with winreg.OpenKey(root, key) as handle:
            return str(winreg.QueryValueEx(handle, value)[0])
    except OSError:
        return None


def find_steam_root(read_registry: RegistryReader = _read_registry) -> Path | None:
    """Locate the Steam install from the registry, then from common defaults."""
    candidates = [
        read_registry("HKCU", r"Software\Valve\Steam", "SteamPath"),
        read_registry("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    ]
    for raw in candidates:
        if raw and Path(raw).is_dir():
            return Path(raw)
    for default in DEFAULT_STEAM_ROOTS:
        if default.is_dir():
            return default
    return None


def library_folders(steam_root: Path) -> list[tuple[Path, set[str]]]:
    """Each Steam library with the app IDs Steam says it holds."""
    manifest = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        data = loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, VdfError) as error:
        logger.debug("Could not read %s: %s", manifest, error)
        return [(steam_root, set())]

    folders = get_ci(data, "libraryfolders")
    libraries: list[tuple[Path, set[str]]] = []
    for entry in (folders or {}).values():
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            apps = entry.get("apps")
            libraries.append((Path(entry["path"]), set(apps) if isinstance(apps, dict) else set()))
    return libraries or [(steam_root, set())]


def find_cs2_root(steam_root: Path | None = None) -> Path | None:
    """The CS2 install folder that really contains cs2.exe, or None."""
    steam_root = steam_root or find_steam_root()
    if steam_root is None:
        return None
    libraries = library_folders(steam_root)
    # Libraries Steam says hold CS2 first, then the rest as a fallback.
    ordered = sorted(libraries, key=lambda lib: CS2_APP_ID not in lib[1])
    for library, _apps in ordered:
        candidate = library / CS2_FOLDER
        if (candidate / CS2_EXE_RELATIVE).is_file():
            return candidate
    return None
