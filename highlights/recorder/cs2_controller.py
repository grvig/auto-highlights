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
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from highlights.engine.timing import CS2_TICKRATE
from highlights.recorder import cs2_commands as commands
from highlights.recorder.compat import (
    HOOK_BROKEN,
    hook_failure_hint,
    hook_unsupported_message,
    old_demo_hint,
)
from highlights.recorder.cs2_console import DEFAULT_PORT, ConsoleError, Cs2Console

logger = logging.getLogger(__name__)

# Relative to the CS2 root — the same layout config validation checks.
CS2_EXE_RELATIVE = Path("game/bin/win64/cs2.exe")
# Where playdemo looks for demos named without a path.
REPLAYS_RELATIVE = Path("game/csgo") / commands.REPLAYS_FOLDER

# Printed once a demo has loaded far enough to seek in.
DEMO_READY = r"received full update|Demo Skipping finished"
DEMO_LOAD_TIMEOUT = 90.0

# Seconds to let the game boot before the console is expected to answer.
DEFAULT_STARTUP_TIMEOUT = 120.0

# How long to wait for CS2 to confirm a seek, and how often to try one.
SEEK_TIMEOUT_SECONDS = 12.0
SEEK_ATTEMPTS = 3

# Stepped playback can run slower than real time while a recorder renders
# every frame, so its timeout is a multiple of the span plus some slack.
STEP_SLOWDOWN_ALLOWANCE = 3.0
STEP_SLACK_SECONDS = 15.0
STEP_DONE = r"Demo paused at engine time \d+, demo tick (\d+)"

ProcessLauncher = Callable[[Sequence[str]], "subprocess.Popen[bytes]"]
Sleeper = Callable[[float], None]
CommandRunner = Callable[[Sequence[str]], str]

GAME_IMAGE = "cs2.exe"
# Seconds CS2 gets to close its window (and write its settings) before it is
# killed. The console's own quit command can hang the game, so it is not used.
CLOSE_GRACE_SECONDS = 20.0


class Cs2Error(Exception):
    """Raised when CS2 cannot be launched or reached."""


class HookUnsupported(Cs2Error):
    """HLAE's hook does not match the installed CS2 build: nothing will load
    until HLAE ships an update, so the rest of the run should not try."""


def _default_launcher(args: Sequence[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(list(args))


def _run_command(args: Sequence[str]) -> str:
    result = subprocess.run(list(args), capture_output=True, text=True, errors="replace")
    return result.stdout


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
        command_runner: CommandRunner | None = None,
        full_hud: bool = True,
        terminate_launcher: bool = True,
    ) -> None:
        self.cs2_root = Path(cs2_root)
        self.console_port = console_port
        self.console = console or Cs2Console(port=console_port)
        self._launcher = launcher or _default_launcher
        self._sleep = sleeper or time.sleep
        self._run_command = command_runner or _run_command
        self.tickrate = tickrate
        # Keep the player's normal HUD in footage (False strips it to the kill feed).
        self.full_hud = full_hud
        # False when the launcher is Steam itself: closing the game must never
        # take the player's Steam client down with it.
        self.terminate_launcher = terminate_launcher
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

    def launch(self, windowed: bool = True, args: Sequence[str] | None = None) -> None:
        """Start CS2, or run `args` (such as an HLAE launch) that starts it.

        Does not wait for the console to become reachable.
        """
        self.verify_install()
        args = list(args) if args else self.build_launch_args(windowed=windowed)
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

    def attach_when_ready(
        self, timeout: float = DEFAULT_STARTUP_TIMEOUT, poll_seconds: float = 2.0
    ) -> None:
        """Keep trying the console until a freshly launched game answers."""
        waited = 0.0
        while True:
            try:
                self.console.connect()
                return
            except ConsoleError as error:
                if waited >= timeout:
                    raise Cs2Error(f"CS2 never opened its console: {error}."
                                   + hook_failure_hint(self.cs2_root)) from error
            self._sleep(poll_seconds)
            waited += poll_seconds

    def stage_demo(self, demo_path: Path | str) -> str:
        """Copy a demo where playdemo can reach it. Returns the name to play.

        Names are reduced to safe characters, because the console splits
        playdemo's argument on spaces.
        """
        source = Path(demo_path)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", source.stem) or "demo"
        target = self.cs2_root / REPLAYS_RELATIVE / f"{name}.dem"
        if not (target.is_file() and target.stat().st_size == source.stat().st_size):
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Staging %s as %s", source, target)
            shutil.copy2(source, target)
        return name

    # --- Playback -------------------------------------------------------
    #
    # Every step that can be confirmed is confirmed from the game's own log:
    # seeks by "Demo Skipping finished at tick T" and stepped playback by
    # "Demo paused at engine time E, demo tick T". CS2 occasionally drops a
    # seek, so seeks are retried rather than trusted.

    def load_demo(self, demo_name: str, settle_seconds: float = 3.0) -> None:
        """Play a staged demo, wait until it is seekable, and clean up the view.

        The playback bar returns on every load, so it is toggled off each
        time, and the footage settings are reapplied with it.
        """
        logger.info("Loading demo %s", demo_name)
        self.console.drain()
        self.console.send(commands.play_demo(demo_name))
        loaded = self.console.wait_for(f"(?P<ready>{DEMO_READY})|(?P<broken>{HOOK_BROKEN})", DEMO_LOAD_TIMEOUT)
        if loaded and loaded.group("broken"):
            raise HookUnsupported(hook_unsupported_message(self.cs2_root))
        if not loaded:
            raise Cs2Error(f"Demo {demo_name} never finished loading."
                           + old_demo_hint(self.cs2_root))
        self._sleep(settle_seconds)
        self.console.send(commands.toggle_demo_ui())
        self.console.send_all(commands.movie_setup(self.full_hud))

    def spectate(self, name: str, first_person: bool = True) -> None:
        """Lock the camera to one player's point of view, by in-game name."""
        mode = (
            commands.SPEC_MODE_FIRST_PERSON
            if first_person
            else commands.SPEC_MODE_THIRD_PERSON
        )
        logger.info("Spectating %s (mode=%s)", name, mode)
        self.console.send_all(
            [commands.spectate_player(name), commands.spectator_mode(mode)]
        )

    def seek_to(self, tick: int) -> bool:
        """Seek to a tick and stay paused there. Returns whether CS2 confirmed it.

        After demo_step_tick the demo sits in a stepped pause that ignores the
        next seek, so each attempt first resumes and pauses to clear it.
        """
        confirmation = rf"Demo Skipping finished at tick {int(tick)}\b"
        for attempt in range(1, SEEK_ATTEMPTS + 1):
            logger.info("Seeking to tick %d (attempt %d)", tick, attempt)
            self.console.send(commands.resume())
            self._sleep(0.15)
            self.console.send(commands.pause())
            self._sleep(0.4)
            self.console.drain()
            self.console.send(commands.goto_tick(tick))
            if self.console.wait_for(confirmation, SEEK_TIMEOUT_SECONDS):
                return True
            logger.warning("Seek to tick %d not confirmed", tick)
        return False

    def play_ticks(self, ticks: int) -> int | None:
        """Play exactly `ticks` ticks from the paused position, then pause.

        Returns the demo tick CS2 reports it stopped at (usually within two or
        three ticks of the target), or None if it never reported stopping.
        """
        if ticks <= 0:
            raise Cs2Error(f"Nothing to play: {ticks} ticks")
        timeout = ticks / self.tickrate * STEP_SLOWDOWN_ALLOWANCE + STEP_SLACK_SECONDS
        self.console.drain()
        logger.info("Stepping %d ticks (%.1fs)", ticks, ticks / self.tickrate)
        self.console.send(commands.step_ticks(ticks))
        done = self.console.wait_for(STEP_DONE, timeout)
        if done is None:
            logger.warning("CS2 never reported the end of a %d-tick step", ticks)
            return None
        landed = int(done.group(1))
        logger.info("Stepped playback stopped at demo tick %d", landed)
        return landed

    def play_range(
        self, start_tick: int, end_tick: int, spectate: str | None = None
    ) -> int | None:
        """Seek to start_tick and play through end_tick. Returns the landed tick.

        The camera is pointed after the seek, not before: a seek respawns the
        spectator and drops any earlier spec_player.
        """
        if end_tick <= start_tick:
            raise Cs2Error(f"Window ends before it starts: {start_tick}-{end_tick}")
        if not self.seek_to(start_tick):
            raise Cs2Error(f"CS2 never confirmed the seek to tick {start_tick}")
        if spectate:
            self._sleep(0.4)
            self.spectate(spectate)
            self._sleep(0.5)
        return self.play_ticks(end_tick - start_tick)

    def game_running(self) -> bool:
        listing = self._run_command(["tasklist", "/FI", f"IMAGENAME eq {GAME_IMAGE}", "/NH"])
        return GAME_IMAGE in listing.lower()

    def close_game(self, grace_seconds: float = CLOSE_GRACE_SECONDS) -> None:
        """Ask CS2's window to close, and kill it if it will not."""
        if not self.game_running():
            return
        logger.info("Closing CS2")
        self._run_command(["taskkill", "/IM", GAME_IMAGE])
        waited = 0.0
        while waited < grace_seconds:
            self._sleep(1.0)
            waited += 1.0
            if not self.game_running():
                return
        logger.warning("CS2 did not close within %.0fs; killing it", grace_seconds)
        self._run_command(["taskkill", "/F", "/IM", GAME_IMAGE])

    def quit(self) -> None:
        """Close the console, and the game too if this controller started it.

        Under HLAE the launched process is the loader, not the game, so the
        game is closed by name rather than through the process handle.
        """
        self.console.close()
        if self._process is None:
            return
        self.close_game()
        if self.terminate_launcher and self._process.poll() is None:
            logger.info("Terminating launcher (pid=%s)", self._process.pid)
            self._process.terminate()
        self._process = None
