"""TCP console client for CS2.

CS2 launched with `-netconport <port>` accepts console commands over a plain
TCP socket. This is the transport the controller drives the game through.

Logging is deliberately loud: every command sent is logged, because when
recording breaks the first question is always which command the game stopped
accepting.
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Callable

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 29_000
DEFAULT_TIMEOUT = 5.0

SocketFactory = Callable[[], socket.socket]


class ConsoleError(Exception):
    """Raised when the game console cannot be reached or written to."""


class Cs2Console:
    """A connection to CS2's netcon console.

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

    @property
    def connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> None:
        """Open the console connection, or raise ConsoleError explaining why not."""
        if self._socket is not None:
            logger.debug("Console already connected to %s:%s", self.host, self.port)
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
        self._socket = sock
        logger.info("CS2 console connected")

    def send(self, command: str) -> None:
        """Send one console command."""
        if self._socket is None:
            raise ConsoleError(f"Console not connected; cannot send: {command}")

        logger.info("CS2 <- %s", command)
        try:
            self._socket.sendall(f"{command}\n".encode())
        except OSError as error:
            raise ConsoleError(f"Failed sending {command!r}: {error}") from error

    def send_all(self, commands: list[str]) -> None:
        """Send several commands in order."""
        for command in commands:
            self.send(command)

    def read_available(self, max_bytes: int = 65_536) -> str:
        """Read whatever the game has emitted, or an empty string if nothing.

        Best effort — the console is chatty and unstructured, so this exists
        for diagnostics rather than for parsing.
        """
        if self._socket is None:
            return ""
        self._socket.settimeout(0.1)
        try:
            data = self._socket.recv(max_bytes)
        except (TimeoutError, BlockingIOError):
            return ""
        except OSError as error:
            logger.debug("Console read failed: %s", error)
            return ""
        finally:
            self._socket.settimeout(self.timeout)
        return data.decode(errors="replace")

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

    def __enter__(self) -> Cs2Console:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
