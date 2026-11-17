"""Where the app keeps its settings, tools and files once installed.

Running from a source checkout, config.toml sits next to the code and wins.
An installed copy has no such folder, so its config, downloaded tools (HLAE,
ffmpeg), parse cache and raw clips live under %LOCALAPPDATA%\\auto-highlights,
and finished reels go to the user's Videos folder where people look for them.
"""

from __future__ import annotations

import os
from pathlib import Path

from highlights.config import CONFIG_FILENAME, repo_root

APP_NAME = "auto-highlights"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME}"


def videos_dir() -> Path:
    home = os.environ.get("USERPROFILE")
    return (Path(home) if home else Path.home()) / "Videos" / APP_NAME


def tools_dir() -> Path:
    return app_data_dir() / "tools"


def config_location() -> Path:
    """The config in use: a source checkout's own, else the installed app's."""
    local = repo_root() / CONFIG_FILENAME
    return local if local.is_file() else app_data_dir() / CONFIG_FILENAME


def starter_config() -> str:
    """A first-run config: everything else is found or has a default."""
    data = app_data_dir().as_posix()
    return (
        "# auto-highlights settings. Edit here or in the app.\n\n"
        "[paths]\n"
        f'output_dir = "{videos_dir().as_posix()}"\n'
        f'clips_dir = "{data}/clips"\n'
        f'cache_dir = "{data}/cache"\n'
        f'hlae = "{data}/tools/hlae"\n'
    )


def ensure_config() -> Path:
    """The config file in use, writing the starter one on a first run."""
    location = config_location()
    if not location.is_file():
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_text(starter_config(), encoding="utf-8", newline="\n")
    return location
