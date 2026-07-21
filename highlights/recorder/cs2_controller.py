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
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from highlights.engine.timing import CS2_TICKRATE, tick_span_seconds
from highlights.recorder import cs2_commands as commands
from highlights.recorder.cs2_console import DEFAULT_PORT, ConsoleError, Cs2Console

logger = logging.getLogger(__name__)

# Relative to the CS2 root — the same layout config validation checks.
CS2_EXE_RELATIVE = Path("game/bin/win64/cs2.exe")

# Seconds to let the game boot before the console is expected to answer.
DEFAULT_STARTUP_TIMEOUT = 60.0

# Grace period after a seek before playback is trusted to be at the tick.
# Seeking is not instant and the console gives no completion signal.
SEEK_SETTLE_SECONDS = 1.5

# Extra seconds held after a window finishes, so the recorder is not cut off
# by the pause landing a frame early.
PLAY_TAIL_SECONDS = 0.3

ProcessLauncher = Callable[[Sequence[str]], "subprocess.Popen[bytes]"]
Sleeper = Callable[[float], None]


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
        sleeper: Sleeper | None = None,
        tickrate: int = CS2_TICKRATE,
    ) -> None:
        self.cs2_root = Path(cs2_root)
        self.console_port = console_port
        self.console = console or Cs2Console(port=console_port)
        self._launcher = launcher or _default_launcher
        self._sleep = sleeper or time.sleep
        self.tickrate = tickrate
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

    # --- Playback -------------------------------------------------------
    #
    # CS2 gives no reliable completion signal for seeking or for reaching a
    # tick, so these methods are time-based: seek, wait out a settle period,
    # play for exactly the window's duration, pause. That is the pragmatic
    # approach, and it is why every step is logged — a drifting clip shows up
    # as a mismatch between the logged window and the footage.

    def load_demo(self, demo_path: Path | str, settle_seconds: float = 5.0) -> None:
        """Start playing a demo and give it time to load."""
        logger.info("Loading demo %s", demo_path)
        self.console.send(commands.play_demo(str(demo_path)))
        self._sleep(settle_seconds)

    def spectate(self, steamid: str | int, first_person: bool = True) -> None:
        """Lock the camera to one player's point of view."""
        mode = (
            commands.SPEC_MODE_FIRST_PERSON
            if first_person
            else commands.SPEC_MODE_THIRD_PERSON
        )
        logger.info("Spectating %s (mode=%s)", steamid, mode)
        self.console.send_all(
            [commands.spectate_player(steamid), commands.spectator_mode(mode)]
        )

    def seek_to(self, tick: int, settle_seconds: float = SEEK_SETTLE_SECONDS) -> None:
        """Seek to a tick and pause there, ready to play."""
        logger.info("Seeking to tick %d", tick)
        self.console.send(commands.goto_tick(tick))
        self._sleep(settle_seconds)
        self.console.send(commands.pause())

    def play_window(
        self, start_tick: int, end_tick: int, timescale: float = 1.0
    ) -> float:
        """Play from start_tick to end_tick, then pause. Returns seconds played.

        Playback length is derived from the tick span rather than watched for,
        because the console reports no end-of-window event.
        """
        if end_tick < start_tick:
            raise Cs2Error(f"Window ends before it starts: {start_tick}-{end_tick}")

        span = tick_span_seconds(start_tick, end_tick, self.tickrate)
        wait = span / timescale + PLAY_TAIL_SECONDS
        logger.info(
            "Playing ticks %d-%d (%.1fs at %gx, waiting %.1fs)",
            start_tick,
            end_tick,
            span,
            timescale,
            wait,
        )
        if timescale != 1.0:
            self.console.send(commands.set_timescale(timescale))
        self.console.send(commands.resume())
        self._sleep(wait)
        self.console.send(commands.pause())
        logger.info("Window finished at tick %d", end_tick)
        return wait

    def quit(self) -> None:
        """Close the console and stop the game if we started it."""
        self.console.close()
        if self._process is None:
            return
        if self._process.poll() is None:
            logger.info("Terminating CS2 (pid=%s)", self._process.pid)
            self._process.terminate()
        self._process = None
