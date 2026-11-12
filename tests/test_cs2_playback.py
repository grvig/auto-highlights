"""Tests for CS2 playback control.

Uses a recording console and a fake sleeper, so the sequence and timing of
commands are asserted without the game running or the suite actually waiting.
"""

import pytest

from highlights.recorder.cs2_console import Cs2Console
from highlights.recorder.cs2_controller import Cs2Controller, Cs2Error


class RecordingConsole(Cs2Console):
    """A console that records commands instead of sending them."""

    def __init__(self) -> None:
        super().__init__(port=1)
        self.sent: list[str] = []

    def connect(self) -> None:
        return None

    def send(self, command: str) -> None:
        self.sent.append(command)

    def close(self) -> None:
        return None


class FakeSleeper:
    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.fixture
def controller(tmp_path):
    exe = tmp_path / "game" / "bin" / "win64" / "cs2.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    console = RecordingConsole()
    sleeper = FakeSleeper()
    ctrl = Cs2Controller(tmp_path, console=console, sleeper=sleeper)
    ctrl.test_console = console
    ctrl.test_sleeper = sleeper
    return ctrl


def test_load_demo_sends_playdemo_and_waits(controller):
    controller.load_demo("D:/demos/match one.dem", settle_seconds=4.0)
    assert controller.test_console.sent == ["playdemo replays/match one"]
    assert controller.test_sleeper.waits == [4.0]


def test_spectate_locks_pov_in_first_person(controller):
    controller.spectate("semi")
    assert controller.test_console.sent == [
        'spec_player "semi"',
        "spec_mode 4",
    ]


def test_spectate_can_use_third_person(controller):
    controller.spectate("semi", first_person=False)
    assert controller.test_console.sent[-1] == "spec_mode 5"


def test_seek_sends_goto_then_pauses(controller):
    controller.seek_to(10_128)
    assert controller.test_console.sent == ["demo_gototick 10128", "demo_pause"]
    assert controller.test_sleeper.waits  # settled before pausing


def test_play_window_waits_the_tick_span(controller):
    # 320 ticks at 64/s = 5 seconds, plus the tail.
    played = controller.play_window(10_000, 10_320)
    assert controller.test_console.sent == ["demo_resume", "demo_pause"]
    assert played == pytest.approx(5.3, abs=0.01)
    assert controller.test_sleeper.waits == [pytest.approx(5.3, abs=0.01)]


def test_play_window_scales_wait_with_timescale(controller):
    played = controller.play_window(10_000, 10_640, timescale=2.0)
    # 640 ticks = 10s of footage, at 2x it takes 5s
    assert played == pytest.approx(5.3, abs=0.01)
    assert "demo_timescale 2" in controller.test_console.sent


def test_play_window_rejects_inverted_window(controller):
    with pytest.raises(Cs2Error, match="ends before"):
        controller.play_window(2000, 1000)
