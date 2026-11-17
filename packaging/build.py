"""Build the standalone Windows app with PyInstaller.

    python packaging/build.py [--out D:/auto-highlights/build]

Produces <out>/dist/auto-highlights/auto-highlights.exe with Python and every
dependency inside, so users install nothing else. ffmpeg and HLAE are not
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
NAME = "auto-highlights"
EXCLUDED = ("matplotlib", "scipy", "PIL", "tkinter", "IPython", "notebook")


def pyinstaller_args(out: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "packaging" / "entry.py"),
        "--name", NAME,
        "--onedir",
        "--console",
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
        "--add-data", f"{ROOT / 'config.template.toml'}{';' if sys.platform == 'win32' else ':'}.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "build")
    out = parser.parse_args().out
    shutil.rmtree(out / "dist" / NAME, ignore_errors=True)
    result = subprocess.run(pyinstaller_args(out))
    exe = out / "dist" / NAME / f"{NAME}.exe"
    if result.returncode != 0 or not exe.is_file():
        print("Build failed", file=sys.stderr)
        return 1
    print(f"Built {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
