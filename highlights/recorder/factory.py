"""Choosing and building the live recorder from config.

HLAE is preferred; when it is missing the window-capture backend is used
instead, with a warning rather than a failure, so a reel still gets made.
Recording is always wrapped in a guard that puts the player's CS2 settings
back afterwards.
"""

from __future__ import annotations

import contextlib
import logging
from contextlib import AbstractContextManager
from pathlib import Path

from highlights.config import Config
from highlights.recorder.cfg_guard import CfgGuard, cs2_cfg_dir, read_convars
from highlights.recorder.cs2_commands import restore_settings
from highlights.recorder.cs2_controller import Cs2Controller
from highlights.recorder.hlae import (
    BUNDLED_DIR,
    find_hlae,
    launch_args,
    resolve_ffmpeg,
    write_ffmpeg_ini,
)
from highlights.recorder.compat import hlae_older_than_game, hlae_worked_on, mark_hlae_working
from highlights.recorder.hlae_release import ReleaseError, installed_published, installed_version
from highlights.recorder.hlae_update import ensure_current
from highlights.recorder.hlae_backend import HlaeRecorder
from highlights.recorder.window_backend import WindowRecorder
from highlights.steam.account import signed_in_account
from highlights.steam.locate import find_steam_root

logger = logging.getLogger(__name__)


def build_live_recorder(config: Config, steam_root: Path | None = None) -> HlaeRecorder:
    """The recorder config asks for, falling back to window capture."""
    config.verify_cs2_install()
    rec = config.recording
    cs2 = Cs2Controller(config.cs2_root, full_hud=rec.hud != "clean")
    common = dict(output_dir=config.clips_dir, framerate=rec.framerate, ffmpeg=config.ffmpeg_path,
                  restore_commands=player_restore_commands(steam_root))

    if rec.recorder == "hlae":
        if rec.auto_update:
            update_hlae(rec.hlae_path or BUNDLED_DIR)
        hlae_dir = find_hlae(rec.hlae_path)
        if hlae_dir is not None and hlae_older_than_game(
                installed_published(hlae_dir), config.cs2_root, worked_on=hlae_worked_on(hlae_dir)):
            logger.warning(
                "HLAE %s was released before this CS2 update; if CS2 fails to start or "
                "record, set recorder = \"window\" until HLAE catches up",
                ".".join(map(str, installed_version(hlae_dir) or ())) or "(installed)",
            )
        if hlae_dir is not None:
            write_ffmpeg_ini(hlae_dir, resolve_ffmpeg(config.ffmpeg_path))
            args = launch_args(hlae_dir, cs2.executable, rec.width, rec.height, cs2.console_port)
            return HlaeRecorder(cs2, launch_args=args,
                                on_working=lambda: mark_hlae_working(hlae_dir, config.cs2_root), **common)
        logger.warning("HLAE not found; falling back to window capture")

    # Window capture: start CS2 through Steam at the render size so the
    # settings backup is taken before CS2 saves anything (it writes its video
    # settings at startup); a CS2 already running is filmed as it is.
    launch = None
    if not cs2.game_running():
        steam = steam_exe(steam_root)
        if steam is not None:
            launch = window_launch_args(steam, rec.width, rec.height, cs2.console_port)
            cs2 = Cs2Controller(config.cs2_root, full_hud=rec.hud != "clean", terminate_launcher=False)
    return WindowRecorder(cs2, audio_device=rec.audio_device, launch_args=launch, **common)


def steam_exe(steam_root: Path | None = None) -> Path | None:
    root = steam_root or find_steam_root()
    exe = Path(root) / "steam.exe" if root else None
    return exe if exe and exe.is_file() else None


def window_launch_args(steam: Path, width: int, height: int, port: int) -> list[str]:
    """CS2 through Steam, windowed at the render size, console open to us."""
    return [str(steam), "-applaunch", "730", "-insecure", "-netconport", str(port), "-novid",
            "-sw", "-w", str(width), "-h", str(height), "-console"]


def player_restore_commands(steam_root: Path | None = None) -> list[str]:
    """Console commands returning the signed-in player's footage settings."""
    steam_root = steam_root or find_steam_root()
    account = signed_in_account(steam_root) if steam_root else None
    if account is None:
        return []
    return restore_settings(read_convars(cs2_cfg_dir(steam_root, account.steamid)))


def update_hlae(hlae_dir: Path) -> str | None:
    """Bring HLAE up to date; offline or failed checks only warn."""
    try:
        version, changed = ensure_current(hlae_dir)
    except (ReleaseError, OSError) as error:
        logger.warning("Could not update HLAE (%s); using the installed copy", error)
        return None
    logger.info("HLAE %s %s", version, "installed" if changed else "is up to date")
    return version


def settings_guard(config: Config, steam_root: Path | None = None) -> AbstractContextManager:
    """Backs up and restores the signed-in player's CS2 settings, if found."""
    steam_root = steam_root or find_steam_root()
    account = signed_in_account(steam_root) if steam_root else None
    if account is None:
        logger.warning("Could not find the Steam account; CS2 settings will not be backed up")
        return contextlib.nullcontext()
    backup_root = config.clips_dir.parent / "backup"
    return CfgGuard(cs2_cfg_dir(steam_root, account.steamid), backup_root)
