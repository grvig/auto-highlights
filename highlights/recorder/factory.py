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
from highlights.recorder.cfg_guard import CfgGuard, cs2_cfg_dir
from highlights.recorder.cs2_controller import Cs2Controller
from highlights.recorder.hlae import find_hlae, launch_args, resolve_ffmpeg, write_ffmpeg_ini
from highlights.recorder.hlae_backend import HlaeRecorder
from highlights.recorder.window_backend import WindowRecorder
from highlights.steam.account import signed_in_account
from highlights.steam.locate import find_steam_root

logger = logging.getLogger(__name__)


def build_live_recorder(config: Config) -> HlaeRecorder:
    """The recorder config asks for, falling back to window capture."""
    config.verify_cs2_install()
    rec = config.recording
    cs2 = Cs2Controller(config.cs2_root)
    common = dict(output_dir=config.clips_dir, framerate=rec.framerate, ffmpeg=config.ffmpeg_path)

    if rec.recorder == "hlae":
        hlae_dir = find_hlae(rec.hlae_path)
        if hlae_dir is not None:
            write_ffmpeg_ini(hlae_dir, resolve_ffmpeg(config.ffmpeg_path))
            args = launch_args(hlae_dir, cs2.executable, rec.width, rec.height, cs2.console_port)
            return HlaeRecorder(cs2, launch_args=args, **common)
        logger.warning("HLAE not found; falling back to window capture")

    # Window capture films a game the player has already started with
    # -netconport, at whatever size it is running.
    return WindowRecorder(cs2, **common)


def settings_guard(config: Config, steam_root: Path | None = None) -> AbstractContextManager:
    """Backs up and restores the signed-in player's CS2 settings, if found."""
    steam_root = steam_root or find_steam_root()
    account = signed_in_account(steam_root) if steam_root else None
    if account is None:
        logger.warning("Could not find the Steam account; CS2 settings will not be backed up")
        return contextlib.nullcontext()
    backup_root = config.clips_dir.parent / "backup"
    return CfgGuard(cs2_cfg_dir(steam_root, account.steamid), backup_root)
