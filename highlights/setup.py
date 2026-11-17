"""First-run setup: making sure the tools recording needs are present.

ffmpeg is used wherever it is already found; an installed copy without one
downloads the official build. HLAE is installed or updated from its official
releases. Both land in the app's tools folder.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from highlights.appdirs import tools_dir
from highlights.config import Config
from highlights.progress import Progress, ProgressFn, ignore
from highlights.recorder.ffmpeg_setup import FfmpegSetupError, install_ffmpeg
from highlights.recorder.hlae_release import ReleaseError
from highlights.recorder.hlae_update import ensure_current

logger = logging.getLogger(__name__)


class SetupError(Exception):
    """Raised when a required tool cannot be put in place."""


def ffmpeg_found(ffmpeg: str) -> bool:
    return shutil.which(ffmpeg) is not None or Path(ffmpeg).is_file()


def ensure_tools(config: Config, progress: ProgressFn = ignore, tools: Path | None = None) -> dict:
    """Find or fetch ffmpeg and HLAE. Returns where each one is."""
    tools = tools or tools_dir()
    result: dict[str, str | None] = {}

    progress(Progress("setup", 0, 2, "Checking ffmpeg"))
    if ffmpeg_found(config.ffmpeg_path):
        result["ffmpeg"] = config.ffmpeg_path
    else:
        progress(Progress("setup", 0, 2, "Downloading ffmpeg (about 115 MB)"))
        try:
            result["ffmpeg"] = str(install_ffmpeg(tools / "ffmpeg"))
        except FfmpegSetupError as error:
            raise SetupError(str(error)) from error

    if config.recording.recorder == "hlae":
        progress(Progress("setup", 1, 2, "Checking HLAE"))
        hlae = config.recording.hlae_path or tools / "hlae"
        try:
            version, changed = ensure_current(hlae)
        except (ReleaseError, OSError) as error:
            if not (Path(hlae) / "HLAE.exe").is_file():
                raise SetupError(f"HLAE could not be installed: {error}") from error
            logger.warning("Could not check for an HLAE update: %s", error)
            version = None
        result["hlae"] = str(hlae)
        result["hlae_version"] = version
    progress(Progress("setup", 2, 2, "Ready"))
    return result
