"""Tests for the CS2 console transport.

These run against a real loopback TCP server, so the socket handling is
genuinely exercised — only the CS2-specific command vocabulary needs the game.
"""

import logging
import socket
import threading

import pytest

from highlights.recorder.cs2_console import ConsoleError, Cs2Console


class FakeConsoleServer:
    """A loopback TCP server that records what it receives."""

    def __init__(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        self.received = b""
        self.reply = b""
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            conn, _ = self._server.accept()
        except OSError:
            return
        with conn:
            if self.reply:
                conn.sendall(self.reply)
            conn.settimeout(2.0)
            while True:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                self.received += chunk

    def close(self) -> None:
        self._server.close()


@pytest.fixture
def server():
    fake = FakeConsoleServer()
    yield fake
    fake.close()


def test_connect_and_send_reaches_the_server(server):
    console = Cs2Console(port=server.port)
    console.connect()
    console.send("demo_pause")
    console.send("demo_gototick 500")
    console.close()

    # Give the server thread a moment to drain the socket.
    for _ in range(50):
        if b"demo_gototick 500" in server.received:
            break
        threading.Event().wait(0.02)

    text = server.received.decode()
    assert "demo_pause\n" in text
    assert "demo_gototick 500\n" in text


def test_send_all_preserves_order(server):
    console = Cs2Console(port=server.port)
    with console:
        console.send_all(["a", "b", "c"])

    for _ in range(50):
        if b"c\n" in server.received:
            break
        threading.Event().wait(0.02)
    assert server.received.decode().splitlines() == ["a", "b", "c"]


def test_connect_failure_explains_netconport():
    # Port 1 is not going to have a CS2 console on it.
    console = Cs2Console(port=1, timeout=0.5)
    with pytest.raises(ConsoleError, match="netconport"):
        console.connect()


def test_send_without_connection_raises():
    console = Cs2Console(port=1)
    with pytest.raises(ConsoleError, match="not connected"):
        console.send("demo_pause")


def test_close_is_safe_when_never_connected():
    Cs2Console(port=1).close()  # must not raise


def test_read_available_returns_server_output(server):
    server.reply = b"CS2 console ready\n"
    console = Cs2Console(port=server.port)
    with console:
        text = ""
        for _ in range(50):
            text = console.read_available()
            if text:
                break
        assert "console ready" in text


def test_commands_are_logged(server, caplog):
    console = Cs2Console(port=server.port)
    with caplog.at_level(logging.INFO):
        with console:
            console.send("spec_mode 4")
    assert "CS2 <- spec_mode 4" in caplog.text


def test_context_manager_closes(server):
    console = Cs2Console(port=server.port)
    with console:
        assert console.connected
    assert not console.connected
