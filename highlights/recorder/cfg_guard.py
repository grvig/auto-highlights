"""Keeping the player's CS2 settings exactly as they were.

Recording changes console settings (HUD, sound, cheats for demo control) and
CS2 writes its live settings back to the user's cfg folder when it exits. So
the folder is copied aside before recording and put back afterwards, file
for file, whatever happened in between. Backups are kept, never deleted, so
a crash mid-restore can still be undone by hand.
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from pathlib import Path

from highlights.recorder.cs2_commands import account_id_from_steamid64

logger = logging.getLogger(__name__)


def cs2_cfg_dir(steam_root: Path, steamid64: str) -> Path:
    """Where CS2 keeps one account's settings."""
    account = account_id_from_steamid64(steamid64)
    return Path(steam_root) / "userdata" / str(account) / "730" / "local" / "cfg"


CONVAR_FILES = ("cs2_user_convars_0_slot0.vcfg", "cs2_machine_convars.vcfg")
_PAIR = re.compile(r'^\s*"([^"]+)"\s+"([^"]*)"\s*$', re.MULTILINE)


def read_convars(cfg_dir: Path) -> dict[str, str]:
    """The player's saved console settings, name to value."""
    values: dict[str, str] = {}
    for name in CONVAR_FILES:
        try:
            text = (Path(cfg_dir) / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for key, value in _PAIR.findall(text):
            values.setdefault(key, value)
    return values


class CfgGuard:
    """Back up a cfg folder on enter, restore every backed-up file on exit."""

    def __init__(self, cfg_dir: Path, backup_root: Path) -> None:
        self.cfg_dir = Path(cfg_dir)
        self.backup_root = Path(backup_root)
        self.backup_dir: Path | None = None

    def backup(self) -> Path | None:
        if not self.cfg_dir.is_dir():
            logger.warning("No CS2 cfg folder at %s; nothing to protect", self.cfg_dir)
            return None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = self.backup_root / f"cs2_cfg_{stamp}"
        suffix = 1
        while target.exists():
            suffix += 1
            target = self.backup_root / f"cs2_cfg_{stamp}_{suffix}"
        shutil.copytree(self.cfg_dir, target)
        self.backup_dir = target
        logger.info("Backed up CS2 settings to %s", target)
        return target

    def restore(self) -> list[Path]:
        """Put back every file that changed. Returns the files rewritten."""
        if self.backup_dir is None:
            return []
        restored: list[Path] = []
        for saved in sorted(self.backup_dir.rglob("*")):
            if not saved.is_file():
                continue
            live = self.cfg_dir / saved.relative_to(self.backup_dir)
            if live.is_file() and live.read_bytes() == saved.read_bytes():
                continue
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, live)
            restored.append(live)
        logger.info("Restored %d CS2 settings file(s) from %s", len(restored), self.backup_dir)
        return restored

    def __enter__(self) -> CfgGuard:
        self.backup()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.restore()
