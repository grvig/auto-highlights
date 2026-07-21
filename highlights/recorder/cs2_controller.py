"""CS2 process control: launching the game and attaching to its console.

The fiddliest part of the project, so it is isolated here and logs loudly.
Playback control lives alongside this in the same class but is added
separately; this half is only about getting a game process we can talk to.

The process launcher is injectable so the logic is testable without actually
starting CS2 — launching the game takes over the machine, which is not
something a test suite should do.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from highlights.recorder.cs2_console import DEFAULT_PORT, ConsoleError, Cs2Console

logger = logging.getLogger(__name__)

# Relative to the CS2 root — the same layout config validation checks.
CS2_EXE_RELATIVE = Path("game/bin/win64/cs2.exe")

# Seconds to let the game boot before the console is expected to answer.
DEFAULT_STARTUP_TIMEOUT = 60.0

ProcessLauncher = Callable[[Sequence[str]], "subprocess.Popen[bytes]"]


class Cs2Error(Exception):
    """Raised when CS2 cannot be launched or reached."""


def _default_launcher(args: Sequence[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(list(args))


class Cs2Controller:
    """Owns the CS2 process and its console connection."""

    def __init__(
        self,
        cs2_root: Path | str,
        console_port: int = DEFAULT_PORT,
        console: Cs2Console | None = None,
        launcher: ProcessLauncher | None = None,
    ) -> None:
        self.cs2_root = Path(cs2_root)
        self.console_port = console_port
        self.console = console or Cs2Console(port=console_port)
        self._launcher = launcher or _default_launcher
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def executable(self) -> Path:
        return self.cs2_root / CS2_EXE_RELATIVE

    def verify_install(self) -> None:
        """Check the configured root actually holds the game."""
        if not self.executable.is_file():
            raise Cs2Error(
                f"No cs2.exe under {self.cs2_root} (expected {self.executable}). "
                "Steam can leave an empty folder of the same name in another "
                "library — point cs2_root at the one with the executable."
            )

    def build_launch_args(self, windowed: bool = True) -> list[str]:
        """Command line for a demo-watching CS2 instance.

        -netconport opens the console socket this project drives the game
        through. Windowed by default so recording does not fight a fullscreen
        exclusive surface.
        """
        args = [
            str(self.executable),
            "-netconport",
            str(self.console_port),
            "-novid",
        ]
        if windowed:
            args += ["-window"]
        return args

    def launch(self, windowed: bool = True) -> None:
        """Start CS2. Does not wait for the console to become reachable."""
        self.verify_install()
        args = self.build_launch_args(windowed=windowed)
        logger.info("Launching CS2: %s", " ".join(args))
        try:
            self._process = self._launcher(args)
        except OSError as error:
            raise Cs2Error(f"Could not launch CS2: {error}") from error
        logger.info("CS2 launched (pid=%s)", getattr(self._process, "pid", "?"))

    def is_running(self) -> bool:
        """Whether the process this controller launched is still alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def attach(self) -> None:
        """Connect to the console of a running CS2 instance."""
        try:
            self.console.connect()
        except ConsoleError as error:
            raise Cs2Error(str(error)) from error

    def quit(self) -> None:
        """Close the console and stop the game if we started it."""
        self.console.close()
        if self._process is None:
            return
        if self._process.poll() is None:
            logger.info("Terminating CS2 (pid=%s)", self._process.pid)
            self._process.terminate()
        self._process = None
