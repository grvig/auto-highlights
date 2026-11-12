"""Tests for the CS2 console client against a loopback VConsole2 server.

The server speaks the same binary chunks CS2 does, so the socket handling and
the protocol are exercised for real; only the game itself is absent.
"""

import logging
import socket
import threading
import time

import pytest

from highlights.recorder.cs2_console import ConsoleError, Cs2Console
from highlights.recorder.vconsole import HEADER, VERSION

PREFIX = b"\x00" * 28


def prnt(text: str) -> bytes:
    payload = PREFIX + text.encode() + b"\x00"
    return HEADER.pack(b"PRNT", VERSION, HEADER.size + len(payload), 0) + payload


class FakeVConsole:
    """Accepts one client, records the commands it sends, and can reply."""

    def __init__(self, replies=None) -> None:
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        self.replies = replies or {}
        self.commands: list[str] = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        try:
            conn, _ = self._server.accept()
        except OSError:
            return
        with conn:
            conn.sendall(prnt("Connection in progress..."))
            buffer = b""
            conn.settimeout(3)
            while True:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while len(buffer) >= HEADER.size:
                    kind, _, length, _ = HEADER.unpack_from(buffer)
                    if len(buffer) < length:
                        break
                    command = buffer[HEADER.size:length].rstrip(b"\x00").decode()
                    buffer = buffer[length:]
                    if kind == b"CMND":
                        self.commands.append(command)
                        for reply in self.replies.get(command, []):
                            conn.sendall(prnt(reply))

    def close(self) -> None:
        self._server.close()


@pytest.fixture
def server():
    fake = FakeVConsole(replies={
        "demo_gototick 500": ["Demo Skipping finished at tick 500"],
        "echo hi": ["hi"],
    })
    yield fake
    fake.close()


def wait_until(predicate, seconds=2.0):
    end = time.time() + seconds
    while time.time() < end and not predicate():
        time.sleep(0.02)


def test_commands_arrive_as_cmnd_chunks_in_order(server):
    with Cs2Console(port=server.port) as console:
        console.send_all(["demo_pause", "spec_player \"semi\"", "demo_resume"])
        wait_until(lambda: len(server.commands) == 3)
    assert server.commands == ["demo_pause", 'spec_player "semi"', "demo_resume"]


def test_reads_console_output_lines(server):
    with Cs2Console(port=server.port) as console:
        console.send("echo hi")
        lines = console.read_lines(0.6)
    assert "hi" in lines


def test_wait_for_matches_the_games_confirmation(server):
    with Cs2Console(port=server.port) as console:
        console.send("demo_gototick 500")
        match = console.wait_for(r"Demo Skipping finished at tick (\d+)", 2)
    assert match and match.group(1) == "500"


def test_wait_for_gives_up_after_the_timeout(server, caplog):
    with Cs2Console(port=server.port) as console, caplog.at_level(logging.WARNING):
        assert console.wait_for(r"never printed", 0.4) is None
    assert "Timed out" in caplog.text


def test_drain_discards_stale_output(server):
    with Cs2Console(port=server.port) as console:
        console.drain()  # swallows "Connection in progress..."
        assert console.read_lines(0.3) == []


def test_connect_failure_explains_netconport():
    with pytest.raises(ConsoleError, match="netconport"):
        Cs2Console(port=1, timeout=0.5).connect()


def test_send_without_connection_raises():
    with pytest.raises(ConsoleError, match="not connected"):
        Cs2Console(port=1).send("demo_pause")


def test_close_is_safe_when_never_connected():
    Cs2Console(port=1).close()


def test_commands_are_logged(server, caplog):
    with caplog.at_level(logging.INFO), Cs2Console(port=server.port) as console:
        console.send("spec_mode 4")
    assert "CS2 <- spec_mode 4" in caplog.text
