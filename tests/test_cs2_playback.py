"""Tests for CS2 playback control.

Uses a recording console and a fake sleeper, so the sequence and timing of
commands are asserted without the game running or the suite actually waiting.
"""

import re

import pytest

from highlights.recorder.cs2_console import Cs2Console
from highlights.recorder.cs2_controller import Cs2Controller, Cs2Error, HookUnsupported


class RecordingConsole(Cs2Console):
    """A console that records commands instead of sending them."""

    def __init__(self) -> None:
        super().__init__(port=1)
        self.sent: list[str] = []
        self.output: list[str] = []  # lines the "game" prints, oldest first

    def drain(self) -> None:
        return None

    def wait_for(self, pattern, timeout):
        while self.output:
            match = re.search(pattern, self.output.pop(0))
            if match:
                return match
        return None

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


def test_load_demo_waits_for_the_game_then_cleans_the_view(controller):
    controller.test_console.output = ["CL:  CL_ProcessPacketEntities: received full update"]
    controller.load_demo("match_one", settle_seconds=4.0)
    sent = controller.test_console.sent
    assert sent[:2] == ["playdemo replays/match_one", "demoui"]
    assert "spec_show_xray 0" in sent
    assert controller.test_sleeper.waits == [4.0]


def test_load_demo_fails_when_the_demo_never_loads(controller):
    with pytest.raises(Cs2Error, match="never finished loading"):
        controller.load_demo("match_one")


def test_load_demo_stops_at_once_when_hlae_cannot_hook_this_build(controller):
    # what HLAE 2.193.0 printed on CS2 build 26798866 (2026-11-20)
    controller.test_console.output = [
        "Initialized Embree v4.04.00.",
        "Could not find address for pattern: 40 55 53 56 41 56 41 57 48 8B EC",
        "CL:  CL_ProcessPacketEntities: received full update",
    ]
    with pytest.raises(HookUnsupported, match="HLAE cannot hook") as raised:
        controller.load_demo("match_one")
    assert isinstance(raised.value, Cs2Error)
    assert "window" in str(raised.value)


def test_stage_demo_copies_into_replays_with_a_safe_name(controller, tmp_path):
    demo = tmp_path / "my match (1).dem"
    demo.write_bytes(b"demo")
    name = controller.stage_demo(demo)
    assert name == "my_match__1_"
    staged = controller.cs2_root / "game" / "csgo" / "replays" / "my_match__1_.dem"
    assert staged.read_bytes() == b"demo"
    assert controller.stage_demo(demo) == name  # already there: no recopy


def test_spectate_locks_pov_in_first_person(controller):
    controller.spectate("semi")
    assert controller.test_console.sent == [
        'spec_player "semi"',
        "spec_mode 2",
    ]


def test_spectate_can_use_third_person(controller):
    controller.spectate("semi", first_person=False)
    assert controller.test_console.sent[-1] == "spec_mode 3"


def test_seek_clears_a_stepped_pause_then_waits_for_confirmation(controller):
    controller.test_console.output = ["Demo Skipping finished at tick 10128"]
    assert controller.seek_to(10_128)
    assert controller.test_console.sent == ["demo_resume", "demo_pause", "demo_gototick 10128"]


def test_dropped_seek_is_retried(controller):
    controller.test_console.output = ["noise", "Demo Skipping finished at tick 10128"]
    controller.test_console.wait_for = _one_line_per_wait(controller.test_console)
    assert controller.seek_to(10_128)
    assert controller.test_console.sent.count("demo_gototick 10128") == 2


def test_seek_to_a_different_tick_does_not_count(controller):
    controller.test_console.output = ["Demo Skipping finished at tick 101280"] * 3
    controller.test_console.wait_for = _one_line_per_wait(controller.test_console)
    assert not controller.seek_to(10_128)
    assert controller.test_console.sent.count("demo_gototick 10128") == 3


def _one_line_per_wait(console):
    def wait_for(pattern, timeout):
        return re.search(pattern, console.output.pop(0)) if console.output else None
    return wait_for


def test_play_ticks_steps_and_reports_where_it_stopped(controller):
    controller.test_console.output = ["Demo paused at engine time 28376, demo tick 10322"]
    assert controller.play_ticks(320) == 10322
    assert controller.test_console.sent == ["demo_step_tick 320"]


def test_play_ticks_returns_none_when_the_game_stays_silent(controller):
    assert controller.play_ticks(320) is None


def test_play_ticks_rejects_empty_spans(controller):
    with pytest.raises(Cs2Error, match="Nothing to play"):
        controller.play_ticks(0)


def test_play_range_seeks_then_steps_the_span(controller):
    controller.test_console.output = [
        "Demo Skipping finished at tick 10000",
        "Demo paused at engine time 28376, demo tick 10320",
    ]
    assert controller.play_range(10_000, 10_320) == 10_320
    assert controller.test_console.sent[-2:] == ["demo_gototick 10000", "demo_step_tick 320"]


def test_play_range_fails_loudly_when_the_seek_never_lands(controller):
    with pytest.raises(Cs2Error, match="never confirmed"):
        controller.play_range(10_000, 10_320)


def test_play_range_points_the_camera_after_the_seek(controller):
    controller.test_console.output = [
        "Demo Skipping finished at tick 10000",
        "Demo paused at engine time 28376, demo tick 10320",
    ]
    controller.play_range(10_000, 10_320, spectate="臻咘踔")
    sent = controller.test_console.sent
    assert sent.index('spec_player "臻咘踔"') > sent.index("demo_gototick 10000")
    assert sent[-1] == "demo_step_tick 320"


def test_load_demo_keeps_the_full_hud_unless_told_otherwise(controller):
    controller.test_console.output = ["received full update"]
    controller.load_demo("match_one", settle_seconds=0)
    assert "cl_draw_only_deathnotices 0" in controller.test_console.sent
    controller.full_hud = False
    controller.test_console.output = ["received full update"]
    controller.load_demo("match_one", settle_seconds=0)
    assert controller.test_console.sent[-1] == "hud_showtargetid 0"
