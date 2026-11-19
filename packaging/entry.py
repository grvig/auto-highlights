"""Entry point for the packaged executable (PyInstaller freezes this file).

Started with no arguments (double-clicked, or from the Start menu) it opens
the app window; with arguments it is the command line.
"""

import multiprocessing
import sys

from highlights.cli import main


def arguments(argv: list[str]) -> list[str]:
    return argv or ["--app"]


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main(arguments(sys.argv[1:])))
