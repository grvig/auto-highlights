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
import importlib.metadata as metadata
import re
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
ICON = ROOT / "highlights" / "app" / "icon.ico"
SEP = ";" if sys.platform == "win32" else ":"


def pyinstaller_args(out: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "packaging" / "entry.py"),
        "--name", NAME,
        "--onedir",
        "--windowed",  # no console behind the app window; see entry.py
        "--icon", str(ICON),
        "--noconfirm",
        "--clean",
        "--distpath", str(out / "dist"),
        "--workpath", str(out / "work"),
        "--specpath", str(out),
        "--paths", str(ROOT),
        # parsers with native code and data files that imports alone miss
        "--collect-all", "demoparser2",
        "--collect-all", "awpy",
        # window-capture sound: soundcard reads its C headers at run time
        "--collect-all", "soundcard",
        "--collect-all", "zstandard",
        "--collect-submodules", "highlights",
        # awpy's plotting and navmesh extras, never used by the app (~95 MB)
        *[arg for module in EXCLUDED for arg in ("--exclude-module", module)],
        "--add-data", f"{ROOT / 'config.template.toml'}{SEP}.",
        "--add-data", f"{WEB}{SEP}highlights/app/web",
        "--add-data", f"{ICON}{SEP}highlights/app",
    ]


# The app's own dependencies (pyproject.toml); what they pull in is followed.
SHIPPED_ROOTS = ("awpy", "demoparser2", "polars", "numpy", "pywebview", "zstandard", "soundcard")
# Pulled in by those, but left out of the build (see EXCLUDED).
NOT_SHIPPED = {"matplotlib", "scipy", "pillow", "contourpy", "cycler", "fonttools", "kiwisolver"}
JS_SHIPPED = ("react", "react-dom", "scheduler")
NOTICES_HEADER = """auto-highlights - third-party notices

The app bundles the Python and JavaScript libraries listed below; each one's
licence follows its name. Two tools are not bundled but downloaded on first
run from their own publishers, under their own licences:

  ffmpeg  - the gyan.dev Windows build (GPL v3), https://www.gyan.dev/ffmpeg/builds/
  HLAE    - advancedfx (MIT), https://github.com/advancedfx/advancedfx

"""


def licence_text(dist: metadata.Distribution) -> str:
    """The licence files a distribution ships, or its licence field."""
    texts = []
    for file in dist.files or ():
        name = file.name.upper()
        if name.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
            try:
                texts.append(Path(file.locate()).read_text(encoding="utf-8", errors="replace").strip())
            except OSError:
                continue
    if texts:
        return "\n\n".join(texts)
    return f"License: {dist.metadata.get('License') or dist.metadata.get('License-Expression') or 'see project'}"


def _requirement_name(requirement: str) -> str | None:
    """"numpy>=1.26; extra == 'x'" -> numpy, or None for an optional extra."""
    if "extra ==" in requirement.replace('"', "'"):
        return None
    name = re.split(r"[\s;<>=!~\[(]", requirement.strip(), maxsplit=1)[0]
    return name.lower().replace("_", "-") or None


def shipped_distributions() -> list[metadata.Distribution]:
    """The installed distributions the packaged app carries: its own
    dependencies and everything they require, minus what the build excludes."""
    found: dict[str, metadata.Distribution] = {}
    todo = list(SHIPPED_ROOTS)
    while todo:
        name = todo.pop().lower().replace("_", "-")
        if name in found or name in NOT_SHIPPED:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        found[name] = dist
        todo += [n for n in map(_requirement_name, dist.requires or ()) if n]
    return sorted(found.values(), key=lambda d: d.metadata["Name"].lower())


def notices(js_root: Path = UI / "node_modules") -> str:
    """Every shipped library with its licence, Python then JavaScript."""
    parts = [NOTICES_HEADER]
    for dist in shipped_distributions():
        parts.append(f"=== {dist.metadata['Name']} {dist.version} ===\n{licence_text(dist)}\n")
    for package in JS_SHIPPED:
        licence = js_root / package / "LICENSE"
        if licence.is_file():
            parts.append(f"=== {package} (JavaScript) ===\n{licence.read_text(encoding='utf-8').strip()}\n")
    return "\n".join(parts)


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
    out = (options.out or default_out()).resolve()  # Inno reads relative paths from packaging/, not here
    if not options.skip_ui:
        build_ui()
    shutil.rmtree(out / "dist" / NAME, ignore_errors=True)
    result = subprocess.run(pyinstaller_args(out))
    exe = out / "dist" / NAME / f"{NAME}.exe"
    if result.returncode != 0 or not exe.is_file():
        print("Build failed", file=sys.stderr)
        return 1
    (exe.parent / "THIRD_PARTY_NOTICES.txt").write_text(notices(), encoding="utf-8")
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
