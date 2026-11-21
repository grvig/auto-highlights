"""Tests for passing the speakers' sound to ffmpeg during window capture."""

import sys
import threading

import numpy as np
import pytest

from highlights.recorder.loopback import Feed, NamedPipe, pipe_name


class FakeSource:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def record(self, numframes=None):
        assert numframes is None  # whatever is there, never a fixed block
        return self.chunks.pop(0) if self.chunks else np.zeros((0, 2), dtype="float32")


def test_sound_is_passed_on_as_raw_float_stereo():
    written = []
    sound = np.full((480, 2), 0.5, dtype="float32")
    feed = Feed(FakeSource([sound]), written.append)
    feed.pump_once()
    assert written == [sound.tobytes()]
    assert feed.frames == 480


def test_nothing_is_written_when_nothing_arrived():
    written = []
    feed = Feed(FakeSource([]), written.append)
    feed.pump_once()
    assert written == [] and feed.frames == 0


def test_a_broken_sink_ends_the_feed_without_raising():
    def broken(data):
        raise OSError("pipe closed")

    sound = np.zeros((480, 2), dtype="float32")
    feed = Feed(FakeSource([sound] * 3), broken)
    feed.start()
    feed.stop()
    assert isinstance(feed.error, OSError)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes")
def test_the_named_pipe_carries_bytes_to_a_reader():
    pipe = NamedPipe(pipe_name())
    received = []

    def reader():
        with open(pipe.name, "rb") as handle:
            received.append(handle.read())

    thread = threading.Thread(target=reader)
    thread.start()
    pipe.wait_for_reader()
    pipe.write(b"abc" * 1000)
    pipe.close()
    thread.join(timeout=5)
    assert received == [b"abc" * 1000]
