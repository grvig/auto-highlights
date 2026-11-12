"""Launching CS2 through HLAE (Half-Life Advanced Effects).

HLAE injects its hook into CS2 and adds the mirv_streams commands, which
render every frame at a fixed framerate and pipe them straight into ffmpeg,
with the game's own audio written alongside. That gives frame-perfect clips
with sound that is in sync by construction, which window capture cannot.

Nothing here talks to the game; it only builds the launch command and points
HLAE at an ffmpeg, so it is testable without either installed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HLAE_EXE = "HLAE.exe"
HOOK_DLL = Path("x64") / "AfxHookSource2.dll"
FFMPEG_INI = Path("ffmpeg") / "ffmpeg.ini"

# Where the installer puts the copy of HLAE that ships with the app.
BUNDLED_DIR = Path(__file__).resolve().parents[2] / "tools" / "hlae"


class HlaeError(Exception):
    """Raised when HLAE is missing or cannot be set up."""


def find_hlae(configured: Path | None = None) -> Path | None:
    """The HLAE folder to use: the configured one, else the bundled copy."""
    for folder in (configured, BUNDLED_DIR):
        if folder is not None and (Path(folder) / HLAE_EXE).is_file():
            return Path(folder)
    return None


def launch_args(
    hlae_dir: Path,
    cs2_exe: Path,
    width: int = 1440,
    height: int = 1080,
    console_port: int = 29_000,
) -> list[str]:
    """Command line that starts CS2 under HLAE, ready to be driven.

    -insecure is required for the hook. The game runs borderless-windowed at
    the render size, so footage is the exact resolution asked for.
    """
    game_args = (
        f"-insecure -novid -sw -noborder -width {width} -height {height} "
        f"-netconport {console_port} -console"
    )
    return [
        str(Path(hlae_dir) / HLAE_EXE),
        "-noGui",
        "-autoStart",
        "-noConfig",
        "-afxDisableSteamStorage",
        "-customLoader",
        "-hookDllPath",
        str(Path(hlae_dir) / HOOK_DLL),
        "-programPath",
        str(cs2_exe),
        "-cmdLine",
        game_args,
    ]


def resolve_ffmpeg(ffmpeg: str) -> Path:
    """An absolute ffmpeg.exe path; HLAE does not search PATH."""
    found = shutil.which(ffmpeg)
    if found is None:
        raise HlaeError(f"ffmpeg not found: {ffmpeg}")
    return Path(found).resolve()


def write_ffmpeg_ini(hlae_dir: Path, ffmpeg_exe: Path) -> Path:
    """Point HLAE's ffmpeg streams at our ffmpeg. Returns the ini path."""
    ini = Path(hlae_dir) / FFMPEG_INI
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_text(f"[Ffmpeg]\nPath={Path(ffmpeg_exe)}\n", encoding="utf-8")
    return ini
