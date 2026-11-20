"""Tests for CS2 launch and attach.

CS2 is never actually started here — the launcher is faked, since launching
the game would take over the machine.
"""

import logging

import pytest

from highlights.recorder.cs2_console import ConsoleError, Cs2Console
from highlights.recorder.cs2_controller import Cs2Controller, Cs2Error


class FakeProcess:
    def __init__(self, alive: bool = True) -> None:
        self.pid = 4242
        self._alive = alive
        self.terminated = False

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False


class FakeLauncher:
    def __init__(self, process=None, error=None) -> None:
        self.process = process or FakeProcess()
        self.error = error
        self.called_with = None

    def __call__(self, args):
        self.called_with = list(args)
        if self.error:
            raise self.error
        return self.process


def make_install(tmp_path):
    exe = tmp_path / "game" / "bin" / "win64" / "cs2.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    return tmp_path


def test_verify_install_rejects_a_stub_folder(tmp_path):
    controller = Cs2Controller(tmp_path)
    with pytest.raises(Cs2Error, match="No cs2.exe"):
        controller.verify_install()


def test_verify_install_accepts_a_real_layout(tmp_path):
    Cs2Controller(make_install(tmp_path)).verify_install()


def test_launch_args_include_netconport(tmp_path):
    controller = Cs2Controller(make_install(tmp_path), console_port=29123)
    args = controller.build_launch_args()
    assert "-netconport" in args
    assert "29123" in args
    assert args[0].endswith("cs2.exe")


def test_launch_args_windowed_toggle(tmp_path):
    controller = Cs2Controller(make_install(tmp_path))
    assert "-window" in controller.build_launch_args(windowed=True)
    assert "-window" not in controller.build_launch_args(windowed=False)


def test_launch_invokes_the_launcher(tmp_path, caplog):
    launcher = FakeLauncher()
    controller = Cs2Controller(make_install(tmp_path), launcher=launcher)
    with caplog.at_level(logging.INFO):
        controller.launch()
    assert launcher.called_with[0].endswith("cs2.exe")
    assert controller.is_running()
    assert "Launching CS2" in caplog.text


def test_launch_without_install_raises(tmp_path):
    controller = Cs2Controller(tmp_path, launcher=FakeLauncher())
    with pytest.raises(Cs2Error):
        controller.launch()


def test_launch_failure_is_wrapped(tmp_path):
    launcher = FakeLauncher(error=OSError("denied"))
    controller = Cs2Controller(make_install(tmp_path), launcher=launcher)
    with pytest.raises(Cs2Error, match="Could not launch"):
        controller.launch()


def test_is_running_false_before_launch_and_after_exit(tmp_path):
    controller = Cs2Controller(make_install(tmp_path), launcher=FakeLauncher())
    assert not controller.is_running()
    controller.launch()
    controller._process._alive = False
    assert not controller.is_running()


def test_attach_wraps_console_errors(tmp_path):
    class RefusingConsole(Cs2Console):
        def connect(self):
            raise ConsoleError("no console here")

    controller = Cs2Controller(make_install(tmp_path), console=RefusingConsole())
    with pytest.raises(Cs2Error, match="no console here"):
        controller.attach()


class FakeTasks:
    """tasklist/taskkill stand-in: the game closes after `closes_after` checks."""

    def __init__(self, closes_after=1, running=True):
        self.calls = []
        self.running = running
        self.closes_after = closes_after

    def __call__(self, args):
        self.calls.append(list(args))
        if args[0] == "taskkill":
            if "/F" in args:
                self.running = False
            return ""
        if self.running and self.closes_after is not None:
            checks = sum(1 for c in self.calls if c[0] == "tasklist")
            if checks > self.closes_after + 1:
                self.running = False
        return "cs2.exe   1234 Console" if self.running else "INFO: No tasks are running"


def test_quit_closes_the_game_window_politely(tmp_path):
    tasks = FakeTasks(closes_after=1)
    controller = Cs2Controller(make_install(tmp_path), launcher=FakeLauncher(),
                               sleeper=lambda s: None, command_runner=tasks)
    controller.launch()
    controller.quit()
    kills = [c for c in tasks.calls if c[0] == "taskkill"]
    assert kills == [["taskkill", "/IM", "cs2.exe"]]


def test_a_hung_game_is_killed_after_the_grace_period(tmp_path):
    tasks = FakeTasks(closes_after=None)
    controller = Cs2Controller(make_install(tmp_path), launcher=FakeLauncher(),
                               sleeper=lambda s: None, command_runner=tasks)
    controller.launch()
    controller.quit()
    assert ["taskkill", "/F", "/IM", "cs2.exe"] in tasks.calls
    assert tasks.calls[-1][0] == "tasklist"  # confirmed gone before returning


def test_quit_leaves_a_game_it_did_not_start(tmp_path):
    tasks = FakeTasks()
    controller = Cs2Controller(make_install(tmp_path), command_runner=tasks)
    controller.quit()
    assert tasks.calls == []


def test_quit_terminates_and_is_idempotent(tmp_path):
    launcher = FakeLauncher()
    controller = Cs2Controller(make_install(tmp_path), launcher=launcher,
                               command_runner=FakeTasks(running=False))
    controller.launch()
    controller.quit()
    assert launcher.process.terminated
    controller.quit()  # must not raise


def test_launch_can_run_a_custom_command(tmp_path):
    launcher = FakeLauncher()
    controller = Cs2Controller(make_install(tmp_path), launcher=launcher)
    controller.launch(args=["HLAE.exe", "-noGui"])
    assert launcher.called_with == ["HLAE.exe", "-noGui"]


def test_attach_when_ready_retries_until_the_console_answers(tmp_path):
    class SlowConsole(Cs2Console):
        attempts = 0

        def connect(self):
            SlowConsole.attempts += 1
            if SlowConsole.attempts < 3:
                raise ConsoleError("not yet")

    waits = []
    controller = Cs2Controller(make_install(tmp_path), console=SlowConsole(), sleeper=waits.append)
    controller.attach_when_ready(timeout=10, poll_seconds=2)
    assert SlowConsole.attempts == 3 and waits == [2, 2]


def test_attach_when_ready_gives_up(tmp_path):
    class DeadConsole(Cs2Console):
        def connect(self):
            raise ConsoleError("refused")

    controller = Cs2Controller(make_install(tmp_path), console=DeadConsole(), sleeper=lambda s: None)
    with pytest.raises(Cs2Error, match="never opened"):
        controller.attach_when_ready(timeout=4, poll_seconds=2)


def test_quit_never_terminates_steam_when_it_was_the_launcher(tmp_path):
    launcher = FakeLauncher()
    controller = Cs2Controller(make_install(tmp_path), launcher=launcher,
                               command_runner=FakeTasks(running=False), terminate_launcher=False)
    controller.launch(args=["steam.exe", "-applaunch", "730"])
    controller.quit()
    assert not launcher.process.terminated


def test_a_killed_game_is_waited_for_until_it_has_really_gone(tmp_path):
    from highlights.recorder.cs2_controller import CLOSE_GRACE_SECONDS, Cs2Controller

    exe = tmp_path / "game" / "bin" / "win64" / "cs2.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    # running through the grace period, killed, then listed for 3 more checks
    listed = iter([True] * (int(CLOSE_GRACE_SECONDS) + 1) + [True, True, True, False])
    commands, sleeps = [], []

    def run(args):
        commands.append(args)
        if args[0] == "tasklist":
            return "cs2.exe 1234" if next(listed) else "INFO: No tasks"
        return ""

    ctrl = Cs2Controller(tmp_path, command_runner=run, sleeper=sleeps.append)
    ctrl.close_game()
    assert ["taskkill", "/F", "/IM", "cs2.exe"] in commands
    after_kill = commands[commands.index(["taskkill", "/F", "/IM", "cs2.exe"]) + 1:]
    assert len(after_kill) == 4 and all(c[0] == "tasklist" for c in after_kill)
