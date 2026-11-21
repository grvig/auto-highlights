"""Build the standalone Windows app with PyInstaller.

    python packaging/build.py [--out FOLDER] [--installer]

Produces <out>/dist/auto-highlights/auto-highlights.exe with Python and every
dependency inside, so users install nothing else. The window's interface is
built from ui/ first (needs Node.js) and bundled as highlights/app/web. With --installer it also
compiles <out>/installer/auto-highlights-<version>-setup.exe (Inno Setup). ffmpeg and HLAE are not
bundled: the app downloads them on first run (highlights.setup), which keeps
the installer small and lets HLAE update itself when CS2 changes.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# the app is imported for its version and config, installed or not
sys.path.insert(0, str(ROOT))
NAME = "auto-highlights"
EXCLUDED = ("matplotlib", "scipy", "PIL", "tkinter", "IPython", "notebook")
UI = ROOT / "ui"
WEB = ROOT / "highlights" / "app" / "web"
SEP = ";" if sys.platform == "win32" else ":"


def pyinstaller_args(out: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "packaging" / "entry.py"),
        "--name", NAME,
        "--onedir",
        "--windowed",  # no console behind the app window; see entry.py
        "--icon", str(ROOT / "packaging" / "icon.ico"),
        "--noconfirm",
        "--clean",
        "--distpath", str(out / "dist"),
        "--workpath", str(out / "work"),
        "--specpath", str(out),
        "--paths", str(ROOT),
        # parsers with native code and data files that imports alone miss
        "--collect-all", "demoparser2",
        "--collect-all", "awpy",
        "--collect-submodules", "highlights",
        # awpy's plotting and navmesh extras, never used by the app (~95 MB)
        *[arg for module in EXCLUDED for arg in ("--exclude-module", module)],
        "--add-data", f"{ROOT / 'config.template.toml'}{SEP}.",
        "--add-data", f"{WEB}{SEP}highlights/app/web",
        "--add-data", f"{ROOT / 'packaging' / 'icon.ico'}{SEP}highlights/app",
    ]


def npm() -> str:
    found = shutil.which("npm")
    if found is None:
        raise SystemExit("Node.js (npm) is needed to build the app's interface: https://nodejs.org")
    return found


def ui_commands(install: bool) -> list[list[str]]:
    """npm ci when the dependencies are missing, then the production build."""
    commands = [[npm(), "ci"]] if install else []
    return commands + [[npm(), "run", "build"]]


def build_ui() -> None:
    for command in ui_commands(install=not (UI / "node_modules").exists()):
        subprocess.run(command, cwd=UI, check=True)
    if not (WEB / "index.html").is_file():
        raise SystemExit(f"The interface build left no {WEB / 'index.html'}")


INNO_LOCATIONS = (
    Path("C:/Program Files/Inno Setup 7/ISCC.exe"),
    Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
)


def find_iscc() -> Path | None:
    on_path = shutil.which("ISCC")
    if on_path:
        return Path(on_path)
    return next((p for p in INNO_LOCATIONS if p.is_file()), None)


def app_version() -> str:
    from highlights import __version__

    return __version__


def installer_args(iscc: Path, dist: Path, out: Path, version: str) -> list[str]:
    return [
        str(iscc), "/Q",
        f"/DAppVersion={version}",
        f"/DSourceDir={dist}",
        f"/DOutputDir={out}",
        str(ROOT / "packaging" / "installer.iss"),
    ]


def default_out() -> Path:
    """Beside the parse cache, where big media already goes (not the repo,
    which may sit on a small or synced drive); ./build without a config."""
    try:
        from highlights.config import ConfigError, load_config

        return load_config().resolved_cache_dir.parent / "build"
    except (ImportError, ConfigError):
        return ROOT / "build"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None,
                        help="build folder (default: next to the parse cache, else ./build)")
    parser.add_argument("--installer", action="store_true", help="also compile the setup .exe")
    parser.add_argument("--skip-ui", action="store_true",
                        help="bundle the interface already in highlights/app/web as it is")
    options = parser.parse_args()
    out = options.out or default_out()
    if not options.skip_ui:
        build_ui()
    shutil.rmtree(out / "dist" / NAME, ignore_errors=True)
    result = subprocess.run(pyinstaller_args(out))
    exe = out / "dist" / NAME / f"{NAME}.exe"
    if result.returncode != 0 or not exe.is_file():
        print("Build failed", file=sys.stderr)
        return 1
    print(f"Built {exe}")
    if not options.installer:
        return 0
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup (ISCC.exe) not found; install it to build the installer", file=sys.stderr)
        return 1
    version = app_version()
    result = subprocess.run(installer_args(iscc, exe.parent, out / "installer", version))
    setup = out / "installer" / f"{NAME}-{version}-setup.exe"
    if result.returncode != 0 or not setup.is_file():
        print("Installer build failed", file=sys.stderr)
        return 1
    print(f"Built {setup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
