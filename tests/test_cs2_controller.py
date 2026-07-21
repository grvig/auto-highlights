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


def test_quit_terminates_and_is_idempotent(tmp_path):
    launcher = FakeLauncher()
    controller = Cs2Controller(make_install(tmp_path), launcher=launcher)
    controller.launch()
    controller.quit()
    assert launcher.process.terminated
    controller.quit()  # must not raise
