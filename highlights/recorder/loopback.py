"""Game sound for window capture, without any extra audio driver.

Windows can hand out a copy of whatever the speakers play (WASAPI loopback).
ffmpeg cannot open that itself, so it is read here and passed to ffmpeg as raw
audio through a named pipe, beside the window video. Loopback delivers nothing
while nothing plays, so silence is filled in by the clock: the stream never
stalls and stays in step with the video.
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
import uuid
from collections.abc import Callable
from ctypes import wintypes
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SAMPLE_RATE = 48000
CHANNELS = 2
BYTES_PER_FRAME = 4 * CHANNELS  # float32
BLOCK_SECONDS = 0.01


class Source(Protocol):
    def flush(self) -> Any: ...  # numpy float32 array (frames, channels) of what arrived


class LoopbackError(RuntimeError):
    """Raised when the speakers' sound cannot be captured."""


def open_loopback() -> tuple[Any, Any]:
    """(context manager, recorder) for the default speakers' loopback."""
    try:
        import soundcard  # noqa: PLC0415 - only window capture needs it
    except ImportError as error:  # pragma: no cover - a dependency
        raise LoopbackError("soundcard is not installed") from error
    try:
        speaker = soundcard.default_speaker()
        microphone = soundcard.get_microphone(id=str(speaker.name), include_loopback=True)
        context = microphone.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=480)
        return context, context.__enter__()
    except Exception as error:  # soundcard raises plain RuntimeErrors
        raise LoopbackError(f"Could not capture the speakers' sound: {error}") from error


def pipe_name() -> str:
    return rf"\\.\pipe\auto-highlights-audio-{uuid.uuid4().hex[:8]}"


class Feed:
    """Writes loopback audio into a sink (the pipe) until stopped.

    `write` gets raw float32 interleaved stereo; `clock` and `sleep` are
    injectable so the silence filling can be tested without real time.
    """

    def __init__(self, source: Source, write: Callable[[bytes], None],
                 clock: Callable[[], float] = time.perf_counter,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._source, self._write = source, write
        self._clock, self._sleep = clock, sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.frames = 0
        self.error: Exception | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="loopback-feed")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def pump_once(self, started: float) -> None:
        """Pass on what arrived, then pad with silence up to the clock."""
        data = self._source.flush()
        if len(data):
            self._write(data.astype("float32").tobytes())
            self.frames += len(data)
        due = int((self._clock() - started) * SAMPLE_RATE)
        missing = due - self.frames
        if missing > SAMPLE_RATE * BLOCK_SECONDS * 2:  # well behind: nothing is playing
            self._write(bytes(missing * BYTES_PER_FRAME))
            self.frames += missing

    def _run(self) -> None:
        started = self._clock()
        try:
            while not self._stop.is_set():
                self.pump_once(started)
                self._sleep(BLOCK_SECONDS)
        except Exception as error:  # a closed pipe ends the feed; the clip may survive
            self.error = error
            logger.debug("Loopback feed stopped: %s", error)


class NamedPipe:
    """A one-client outbound Windows named pipe that ffmpeg reads as a file."""

    PIPE_ACCESS_OUTBOUND = 0x00000002
    PIPE_TYPE_BYTE = 0x00000000
    INVALID_HANDLE = wintypes.HANDLE(-1).value

    def __init__(self, name: str) -> None:
        self.name = name
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k = kernel32
        kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        self._handle = kernel32.CreateNamedPipeW(
            name, self.PIPE_ACCESS_OUTBOUND, self.PIPE_TYPE_BYTE, 1, 1 << 20, 1 << 20, 0, None)
        if self._handle == self.INVALID_HANDLE:
            raise LoopbackError(f"Could not create {name} (error {ctypes.get_last_error()})")

    def wait_for_reader(self) -> None:
        """Block until ffmpeg opens the pipe."""
        if not self._k.ConnectNamedPipe(self._handle, None):
            if ctypes.get_last_error() != 535:  # ERROR_PIPE_CONNECTED: it already did
                raise LoopbackError(f"ffmpeg never opened {self.name}")

    def write(self, data: bytes) -> None:
        written = wintypes.DWORD()
        if not self._k.WriteFile(self._handle, data, len(data), ctypes.byref(written), None):
            raise LoopbackError(f"Writing game sound failed (error {ctypes.get_last_error()})")

    def close(self) -> None:
        if self._handle not in (None, self.INVALID_HANDLE):
            self._k.FlushFileBuffers(self._handle)  # until the reader has it all
            self._k.CloseHandle(self._handle)  # the reader then sees the end
            self._handle = None
