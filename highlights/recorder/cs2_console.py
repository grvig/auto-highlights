"""Console client for CS2's -netconport.

CS2 speaks Valve's binary VConsole2 protocol on that port: commands go out as
CMND chunks and the console's output comes back as PRNT chunks (see
vconsole.py). Plain text sent to the port is silently ignored, and unknown
commands print nothing, so the controller confirms each step by waiting for
the game's own log line rather than trusting that a command ran.

Logging is deliberately loud: every command sent is logged, because when
recording breaks the first question is always which command the game stopped
accepting.
"""

from __future__ import annotations

import logging
import re
import socket
import time
from collections.abc import Callable

from highlights.recorder.vconsole import extract_output, pack_command

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 29_000
DEFAULT_TIMEOUT = 5.0
POLL_SECONDS = 0.1

SocketFactory = Callable[[], socket.socket]


class ConsoleError(Exception):
    """Raised when the game console cannot be reached or written to."""


class Cs2Console:
    """A VConsole2 connection to a running CS2.

    The socket factory is injectable so the transport can be tested against a
    local server without the game running.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        socket_factory: SocketFactory | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket_factory = socket_factory or (
            lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        )
        self._socket: socket.socket | None = None
        self._pending = b""

    @property
    def connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> None:
        """Open the console connection, or raise ConsoleError explaining why not."""
        if self._socket is not None:
            return
        logger.info("Connecting to CS2 console at %s:%s", self.host, self.port)
        sock = self._socket_factory()
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
        except OSError as error:
            sock.close()
            raise ConsoleError(
                f"Could not reach the CS2 console at {self.host}:{self.port} "
                f"({error}). Is CS2 running with -netconport {self.port}?"
            ) from error
        sock.settimeout(POLL_SECONDS)
        self._socket = sock
        logger.info("CS2 console connected")

    def send(self, command: str) -> None:
        """Run one console command."""
        if self._socket is None:
            raise ConsoleError(f"Console not connected; cannot send: {command}")
        logger.info("CS2 <- %s", command)
        try:
            self._socket.sendall(pack_command(command))
        except OSError as error:
            raise ConsoleError(f"Failed sending {command!r}: {error}") from error

    def send_all(self, commands: list[str]) -> None:
        for command in commands:
            self.send(command)

    def read_lines(self, seconds: float) -> list[str]:
        """Console output that arrives within the next `seconds`."""
        if self._socket is None:
            return []
        lines: list[str] = []
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                data = self._socket.recv(1 << 20)
            except (TimeoutError, BlockingIOError):
                continue
            except OSError as error:
                raise ConsoleError(f"Console connection failed: {error}") from error
            if not data:
                break
            new, self._pending = extract_output(self._pending + data)
            for line in new:
                logger.debug("CS2 -> %s", line)
            lines.extend(new)
        return lines

    def read_available(self) -> str:
        """Whatever output is waiting right now, joined into one string."""
        return "\n".join(self.read_lines(POLL_SECONDS))

    def wait_for(self, pattern: str, timeout: float) -> re.Match[str] | None:
        """Read output until a line matches `pattern`, or give up after `timeout`."""
        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for line in self.read_lines(min(POLL_SECONDS * 2, max(deadline - time.monotonic(), 0))):
                match = compiled.search(line)
                if match:
                    return match
        logger.warning("Timed out after %.1fs waiting for /%s/", timeout, pattern)
        return None

    def drain(self) -> None:
        """Discard output already waiting, so stale lines cannot match later waits."""
        self.read_lines(POLL_SECONDS * 3)

    def close(self) -> None:
        """Close the connection. Safe to call when never connected."""
        if self._socket is None:
            return
        logger.info("Closing CS2 console connection")
        try:
            self._socket.close()
        except OSError as error:
            logger.debug("Error closing console socket: %s", error)
        finally:
            self._socket = None
            self._pending = b""

    def __enter__(self) -> Cs2Console:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
