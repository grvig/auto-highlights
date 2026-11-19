"""Entry point for the packaged executable (PyInstaller freezes this file).

Started with no arguments (double-clicked, or from the Start menu) it opens
the app window; with arguments it is the command line.

The exe is built windowed so no black console sits behind the app window.
Run from a prompt with arguments it borrows that prompt's console instead,
so the command line still prints.
"""

import multiprocessing
import os
import sys

from highlights.cli import main


def arguments(argv: list[str]) -> list[str]:
    return argv or ["--app"]


def attach_console() -> bool:
    """Write to the prompt the exe was started from, if there is one."""
    if sys.platform != "win32":
        return False
    import ctypes

    ATTACH_PARENT_PROCESS = -1
    if not ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        return False
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    print()  # the prompt has already been redrawn; start on a fresh line
    return True


def ensure_streams(argv: list[str]) -> None:
    """A windowed exe starts with no stdout or stderr at all."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    if argv and attach_console():
        return
    sink = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or sink
    sys.stderr = sys.stderr or sink


if __name__ == "__main__":
    multiprocessing.freeze_support()
    ensure_streams(sys.argv[1:])
    raise SystemExit(main(arguments(sys.argv[1:])))
