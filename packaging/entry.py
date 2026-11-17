"""Entry point for the packaged executable (PyInstaller freezes this file)."""

import multiprocessing

from highlights.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
