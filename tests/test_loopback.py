"""Tests for passing the speakers' sound to ffmpeg during window capture."""

import sys
import threading

import numpy as np
import pytest

from highlights.recorder.loopback import BYTES_PER_FRAME, SAMPLE_RATE, Feed, NamedPipe, pipe_name


class FakeSource:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def flush(self):
        return self.chunks.pop(0) if self.chunks else np.zeros((0, 2), dtype="float32")


def test_sound_is_passed_on_as_raw_float_stereo():
    written = []
    sound = np.full((480, 2), 0.5, dtype="float32")
    feed = Feed(FakeSource([sound]), written.append, clock=lambda: 0.0)
    feed.pump_once(started=0.0)
    assert written == [sound.tobytes()]
    assert feed.frames == 480


def test_silence_is_filled_in_by_the_clock_when_nothing_plays():
    written = []
    now = [0.0]
    feed = Feed(FakeSource([]), written.append, clock=lambda: now[0])
    now[0] = 0.5  # half a second with no sound delivered
    feed.pump_once(started=0.0)
    assert sum(len(w) for w in written) == SAMPLE_RATE // 2 * BYTES_PER_FRAME
    assert feed.frames == SAMPLE_RATE // 2
    feed.pump_once(started=0.0)  # caught up: nothing more until time passes
    assert feed.frames == SAMPLE_RATE // 2


def test_short_gaps_wait_for_real_sound_instead_of_padding():
    written = []
    feed = Feed(FakeSource([]), written.append, clock=lambda: 0.01)
    feed.pump_once(started=0.0)
    assert written == []


def test_a_broken_sink_ends_the_feed_without_raising():
    def broken(data):
        raise OSError("pipe closed")

    sound = np.zeros((480, 2), dtype="float32")
    feed = Feed(FakeSource([sound] * 3), broken, sleep=lambda s: None)
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
